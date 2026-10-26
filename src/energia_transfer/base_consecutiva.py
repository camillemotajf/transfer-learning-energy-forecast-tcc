"""Rotina diária histórica: maior bloco de dias aprovados por qualidade.

O fluxo corrente de cinco minutos usa energia_transfer.intradiario e não
descarta um dia inteiro quando há uma lacuna de aquisição.

Reconstrução retrospectiva em cinco minutos; não usa KNN diário nem completa
dias inteiros de geração. Executar: python scripts/executar_fluxo.py base-final
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from .auditoria_base_original import FUSO, METRICAS_INV, _limpar, interpolar_blocos_internos
from .meteorologia_publica import agregar_era5, obter_era5
from .caminhos import CaminhosProjeto


COLUNAS_ELETRICAS = ["Active_Energy_Delivered_Received", "Current_Phase_Average", "Active_Power"]
POTENCIA_NOMINAL_W = 125_000
MAX_POTENCIA_W = 1.05 * POTENCIA_NOMINAL_W


def mascara_lacunas_curtas(serie, max_pontos=3):
    """Bloco original inteiro de até 15 min, com extremos no mesmo dia."""
    return serie.isna() & interpolar_blocos_internos(serie, max_pontos).notna()


def reconstruir_potencia(original, diurno, escuro, falhas=None, min_doadores=100):
    """Só preenche NaNs. Todos os doadores são observações originais.

    Proxy: somente um dos oito ausente, bloco curto interno, razão histórica
    dos últimos 30 dias (excluindo o instante reconstruído). Interpolação é
    alternativa para blocos curtos; zero físico é restrito à elevação < -6°.
    """
    if len(original.columns) != 8:
        raise ValueError("Esperados oito inversores.")
    original = original.astype(float)
    diurno = diurno.reindex(original.index).fillna(False).astype(bool)
    escuro = escuro.reindex(original.index).fillna(False).astype(bool)
    falhas = pd.DataFrame(0., index=original.index, columns=original.columns) if falhas is None else falhas.reindex_like(original)
    saudavel = falhas.fillna(0).eq(0)
    resultado = original.copy()
    origem = pd.DataFrame("ausente", index=original.index, columns=original.columns)
    origem = origem.mask(original.notna(), "observado")
    # Verifica também leituras parciais da planta durante a noite.
    max_noturno = original.sum(axis=1, min_count=1).where(escuro).max()
    zero_fisico_habilitado = bool(pd.notna(max_noturno) and max_noturno <= 1000)
    for equipamento in original.columns:
        outros = original.columns[original.columns != equipamento]
        soma_outros = original[outros].sum(axis=1, min_count=7)
        doadores_validos = saudavel[outros].all(axis=1) & original[outros].le(MAX_POTENCIA_W).all(axis=1)
        razao = (original[equipamento] / soma_outros).where(
            original[equipamento].gt(1000) & soma_outros.gt(7000)
            & saudavel[equipamento] & doadores_validos & original[equipamento].le(MAX_POTENCIA_W)
        )
        coeficiente = razao.rolling("30D", closed="left", min_periods=min_doadores).median()
        estimada = soma_outros * coeficiente
        curta = mascara_lacunas_curtas(original[equipamento])
        proxy = curta & diurno & saudavel[equipamento] & doadores_validos & estimada.between(0, MAX_POTENCIA_W)
        resultado.loc[proxy, equipamento] = estimada.loc[proxy]
        origem.loc[proxy, equipamento] = "outros_7_inversores"
        # Não encadeia valores já imputados como extremos da interpolação.
        temporal = interpolar_blocos_internos(original[equipamento])
        linear = resultado[equipamento].isna() & curta & ~escuro & saudavel[equipamento] & temporal.between(0, MAX_POTENCIA_W)
        resultado.loc[linear, equipamento] = temporal.loc[linear]
        origem.loc[linear, equipamento] = "linear_ate_15min"
        if zero_fisico_habilitado:
            noite = resultado[equipamento].isna() & escuro
            resultado.loc[noite, equipamento] = 0.
            origem.loc[noite, equipamento] = "zero_noturno_solar"
    return resultado, origem, {"zero_noturno_habilitado": zero_fisico_habilitado,
                               "max_potencia_noturna_observada_w": float(max_noturno) if pd.notna(max_noturno) else None}


def localizar_blocos(elegivel):
    """Faltas no calendário ou dias reprovados sempre interrompem a sequência."""
    elegivel = elegivel.sort_index().fillna(False).astype(bool)
    if not elegivel.index.is_unique:
        raise ValueError("Datas duplicadas na seleção diária.")
    salto = elegivel.index.to_series().diff().ne(pd.Timedelta(days=1))
    grupos = (salto | elegivel.ne(elegivel.shift())).cumsum()
    dados = pd.DataFrame({"timestamp": elegivel.index, "aprovado": elegivel, "grupo": grupos})
    blocos = dados.loc[dados.aprovado].groupby("grupo").agg(
        inicio=("timestamp", "min"), fim=("timestamp", "max"), dias=("timestamp", "size"),
    ).reset_index(drop=True)
    blocos.insert(0, "bloco_id", range(1, len(blocos) + 1))
    return blocos.sort_values(["dias", "inicio"], ascending=[False, True]).reset_index(drop=True)


def selecionar_dias(base, qualidade, limiar=95.):
    if not 0 < limiar <= 100:
        raise ValueError("O limiar de cobertura deve estar entre 0 e 100.")
    completa = base.notna().all(axis=1) & np.isfinite(base).all(axis=1)
    elegivel = (
        completa & qualidade.planta_cobertura_diurna_tratada_pct.ge(limiar)
        & qualidade.planta_cobertura_24h_tratada_pct.ge(limiar)
        & qualidade.planta_intervalos_completos_originais.gt(0)
    )
    return elegivel, localizar_blocos(elegivel)


def _diario(serie, calendario):
    resultado = serie.resample("D").sum()
    resultado.index = resultado.index.tz_localize(None)
    return resultado.reindex(calendario, fill_value=0)


def _hash(arquivo):
    h = hashlib.sha256()
    with Path(arquivo).open("rb") as f:
        for trecho in iter(lambda: f.read(1024 * 1024), b""):
            h.update(trecho)
    return h.hexdigest()


def gerar_base(pasta=None, ano=2025, limiar=95., *, caminhos=None):
    caminhos = caminhos or CaminhosProjeto()
    caminhos.preparar_saidas()
    pasta = Path(pasta or caminhos.brutos_brasil)
    calendario = pd.date_range(f"{ano}-01-01", f"{ano}-12-31", freq="D", name="timestamp")
    grade = pd.date_range(calendario.min().tz_localize(FUSO), (calendario.max() + pd.Timedelta(days=1)).tz_localize(FUSO), freq="5min", inclusive="left", name="timestamp")
    colunas = pd.read_csv(caminhos.brutos_australia / "base_diaria_australia.csv", nrows=0).columns.tolist()
    numericas = [c for c in colunas if c != "timestamp"]
    arquivo_inv = pasta / "Leopoldo-fixa-inv.csv"
    bruto = pd.read_csv(arquivo_inv, usecols=["datetime", "real_datetime", "meta.id_usina", "meta.id_inversor", "usine_code", "serial_number", "fault_code", *METRICAS_INV], low_memory=False)
    bruto = bruto.loc[bruto["meta.id_usina"].eq(50)].copy()
    seriais = bruto.groupby("meta.id_inversor").serial_number.nunique()
    if len(seriais) != 8 or not seriais.eq(1).all():
        raise ValueError("A identidade dos oito inversores precisa ser conferida.")
    ids = sorted(seriais.index.tolist())
    bruto["t"] = pd.to_datetime(bruto.datetime, utc=True, format="mixed", errors="coerce").dt.tz_convert(FUSO)
    leituras = _limpar(bruto, "meta.id_inversor", METRICAS_INV)
    leituras = leituras.loc[leituras.slot.isin(grade)].copy()

    def painel(coluna):
        return leituras.pivot(index="slot", columns="meta.id_inversor", values=coluna).reindex(index=grade, columns=ids)

    geometria_path = caminhos.configuracao_usina
    geometria = json.loads(geometria_path.read_text(encoding="utf-8"))
    if not geometria.get("geometria_habilitada"):
        raise ValueError("A geometria precisa estar habilitada para calcular as colunas inclinadas.")
    solar = pvlib.solarposition.get_solarposition(grade, geometria["latitude"], geometria["longitude"], altitude=geometria["altitude_m"])
    diurno, escuro = solar.apparent_elevation.gt(0), solar.apparent_elevation.lt(-6)
    potencia_original = painel("total_active_power_w")
    potencia, origens, diagnostico_noite = reconstruir_potencia(potencia_original, diurno, escuro, painel("fault_code"))
    total_original = potencia_original.sum(axis=1, min_count=8) / 1000
    total = potencia.sum(axis=1, min_count=8) / 1000

    # Corrente e contador conservam sua definição histórica. Só interpolação
    # curta entre observações, sem proxy validado apenas para potência.
    fases = ["phase_a_current_a", "phase_b_current_a", "phase_c_current_a"]
    leituras["corrente_media"] = leituras[fases].mean(axis=1, skipna=False)
    corrente_original = painel("corrente_media")
    contador_original = painel("total_power_yields_kwh")
    contador = contador_original.where(contador_original.gt(0))
    corrente = corrente_original.apply(interpolar_blocos_internos)
    contador = contador.apply(interpolar_blocos_internos)
    eletricos = pd.DataFrame({"Active_Power": total,
                             "Current_Phase_Average": corrente.sum(axis=1, min_count=8),
                             "Active_Energy_Delivered_Received": contador.sum(axis=1, min_count=8)})
    base = eletricos.resample("D").mean()
    base.index = base.index.tz_localize(None)
    base = base.reindex(calendario)

    cache = caminhos.cache_era5
    meta_cache = json.loads((cache / "open_meteo_era5_2025_metadados.json").read_text(encoding="utf-8"))
    consulta = meta_cache["parametros"]
    dados_publicos, meta_era5 = obter_era5(cache, consulta["start_date"], consulta["end_date"],
                                         latitude=consulta["latitude"], longitude=consulta["longitude"],
                                         altitude=consulta["elevation"], fuso=consulta["timezone"])
    _, meteo = agregar_era5(dados_publicos, calendario.min(), calendario.max(), geometria=geometria)
    meteo_colunas = [c for c in numericas if c not in COLUNAS_ELETRICAS]
    base = base.join(meteo[meteo_colunas], validate="one_to_one").reindex(columns=numericas)

    qualidade = pd.DataFrame(index=calendario)
    esperados_sol = _diario(diurno.astype(int), calendario)
    qualidade["intervalos_esperados_24h"] = 288
    qualidade["intervalos_esperados_diurnos"] = esperados_sol
    qualidade["planta_intervalos_completos_originais"] = _diario(total_original.notna().astype(int), calendario)
    qualidade["planta_intervalos_completos_tratados"] = _diario(total.notna().astype(int), calendario)
    qualidade["planta_cobertura_diurna_original_pct"] = 100 * _diario((total_original.notna() & diurno).astype(int), calendario) / esperados_sol
    qualidade["planta_cobertura_diurna_tratada_pct"] = 100 * _diario((total.notna() & diurno).astype(int), calendario) / esperados_sol
    qualidade["planta_cobertura_24h_tratada_pct"] = 100 * qualidade.planta_intervalos_completos_tratados / 288
    mudou = potencia_original.isna() & potencia.notna()
    estimado_completo = mudou.any(axis=1) & total.notna()
    qualidade["planta_diurnos_com_estimativa"] = _diario((estimado_completo & diurno).astype(int), calendario)
    qualidade["planta_diurnos_com_estimativa_pct"] = 100 * qualidade.planta_diurnos_com_estimativa / esperados_sol
    for metodo in ["outros_7_inversores", "linear_ate_15min", "zero_noturno_solar"]:
        qualidade[f"leituras_inversor_{metodo}"] = _diario(origens.eq(metodo).sum(axis=1), calendario)
    for coluna in COLUNAS_ELETRICAS:
        qualidade[f"{coluna}_amostras_validas"] = _diario(eletricos[coluna].notna().astype(int), calendario)
    for coluna, antes, depois in [
        ("Current_Phase_Average", corrente_original, corrente),
        ("Active_Energy_Delivered_Received", contador_original.where(contador_original.gt(0)), contador),
    ]:
        completos = depois.notna().all(axis=1)
        estimados = (antes.isna() & depois.notna()).any(axis=1) & completos
        qualidade[f"{coluna}_intervalos_originais_validos"] = _diario(antes.notna().all(axis=1).astype(int), calendario)
        qualidade[f"{coluna}_intervalos_com_estimativa"] = _diario(estimados.astype(int), calendario)
        qualidade[f"{coluna}_fracao_intervalos_estimados_pct"] = 100 * _diario(estimados.astype(int), calendario) / _diario(completos.astype(int), calendario).replace(0, np.nan)
    qualidade["contadores_zeros_suspeitos"] = _diario(contador_original.eq(0).sum(axis=1), calendario)
    qualidade["meteorologia_horas"] = meteo.Public_Weather_Hours
    qualidade["radiacao_horas"] = meteo.Public_Radiation_Hours
    qualidade["colunas_diarias_faltantes"] = base.isna().sum(axis=1)
    qualidade["colunas_diarias_nao_finitas"] = (~np.isfinite(base)).sum(axis=1)
    elegivel, blocos = selecionar_dias(base, qualidade, limiar)
    if blocos.empty:
        raise ValueError("Nenhum bloco atende ao critério. Não foram relaxados os limiares.")
    qualidade["dia_elegivel"] = elegivel
    qualidade["bloco_id"] = pd.Series(pd.NA, index=calendario, dtype="Int64")
    for bloco in blocos.itertuples(index=False):
        qualidade.loc[bloco.inicio:bloco.fim, "bloco_id"] = bloco.bloco_id
    escolhido = blocos.iloc[0]
    qualidade["selecionado"] = qualidade.bloco_id.eq(escolhido.bloco_id).fillna(False)
    blocos["selecionado"] = blocos.bloco_id.eq(escolhido.bloco_id)
    motivos = pd.Series("", index=calendario)
    for criterio, texto in [
        (qualidade.planta_cobertura_diurna_tratada_pct.lt(limiar), "cobertura_diurna_insuficiente;"),
        (qualidade.planta_cobertura_24h_tratada_pct.lt(limiar), "cobertura_24h_insuficiente;"),
        (qualidade.colunas_diarias_nao_finitas.gt(0), "coluna_diaria_ausente_ou_nao_finita;"),
        (qualidade.planta_intervalos_completos_originais.eq(0), "sem_potencia_completa_observada;"),
    ]:
        motivos.loc[criterio] += texto
    qualidade["motivos_reprovacao"] = motivos.str.rstrip(";")
    final = base.loc[qualidade.selecionado].copy()
    assert final.notna().all().all() and np.isfinite(final).all().all()
    assert final.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all()
    assert len(final) == int(escolhido.dias)

    sensibilidade = []
    for corte in sorted({90., 95., 99., float(limiar)}):
        dias, trechos = selecionar_dias(base, qualidade, corte)
        maior = trechos.iloc[0] if len(trechos) else None
        sensibilidade.append({"cobertura_minima_pct": corte, "dias_elegiveis": int(dias.sum()),
                              "maior_bloco_dias": int(maior.dias) if maior is not None else 0,
                              "inicio": maior.inicio if maior is not None else None,
                              "fim": maior.fim if maior is not None else None})
    for nome, tabela in [("base_diaria_leopoldo_consecutiva.csv", final),
                         ("base_diaria_leopoldo_dias_validos.csv", base.loc[elegivel])]:
        tabela.reset_index().to_csv(caminhos.processados_brasil / nome, index=False, date_format="%Y-%m-%d")
    qualidade.reset_index().to_csv(caminhos.base_final / "qualidade_diaria_base_consecutiva.csv", index=False, date_format="%Y-%m-%d")
    blocos.to_csv(caminhos.base_final / "blocos_consecutivos_leopoldo.csv", index=False, date_format="%Y-%m-%d")
    pd.DataFrame(sensibilidade).to_csv(caminhos.base_final / "sensibilidade_cobertura_base_consecutiva.csv", index=False, date_format="%Y-%m-%d")
    alteracoes = origens.where(mudou).rename_axis(columns="id_inversor").stack().dropna().rename("metodo").reset_index()
    valores = potencia.where(mudou).rename_axis(columns="id_inversor").stack().dropna().rename("potencia_estimada_w").reset_index()
    alteracoes = alteracoes.merge(valores, on=["timestamp", "id_inversor"], validate="one_to_one")
    alteracoes.to_csv(caminhos.base_final / "imputacoes_potencia_5min.csv.gz", index=False, compression="gzip")
    resumo = {"ano": ano, "fuso": FUSO, "limiar_cobertura_diurna_e_24h_pct": limiar,
              "inicio": str(final.index.min().date()), "fim": str(final.index.max().date()),
              "dias_consecutivos": len(final), "dias_elegiveis_ano": int(elegivel.sum()),
              "blocos_elegiveis": len(blocos), "colunas": colunas, "nulos_base_final": int(final.isna().sum().sum()),
              "menor_cobertura_diurna_selecionada_pct": float(qualidade.loc[final.index, "planta_cobertura_diurna_tratada_pct"].min()),
              "menor_cobertura_24h_selecionada_pct": float(qualidade.loc[final.index, "planta_cobertura_24h_tratada_pct"].min()),
              "maior_fracao_diurna_estimada_selecionada_pct": float(qualidade.loc[final.index, "planta_diurnos_com_estimativa_pct"].max()),
              "inversores": ids, "metodos_potencia": {"proxy": "razão mediana dos 30 dias anteriores, mínimo 100 doadores; outros sete medidos e sem falha sinalizada",
                  "linear": "blocos originais inteiros de até 3 amostras; extremos medidos no mesmo dia; sem falha sinalizada no ponto imputado",
                  "noturno": "zero apenas para ausências com elevação aparente < -6°, após verificar leituras noturnas",
                  "teto_estimativas_w_por_inversor": MAX_POTENCIA_W},
              "diagnostico_noturno": diagnostico_noite,
              "alvo": "média diária em kW das amostras completas tratadas, mínimo 95% de cobertura diurna e 24h no corte padrão; não é energia diária",
              "fontes": {"inversores_sha256": _hash(arquivo_inv), "era5_sha256": meta_era5["sha256"],
                         "geometria_sha256": _hash(geometria_path), "era5_parametros": consulta,
                         "geometria": geometria},
              "limitacoes": ["95% não exige completar todos os cinco minutos; valores diários não nulos não garantem medição integral",
                              "interpolação retrospectiva usa extremos posteriores; não deve atravessar a fronteira temporal de treino e teste",
                              "ERA5 é reanálise retrospectiva, não previsão meteorológica disponível em tempo real",
                              "contador de energia acumulada e corrente contemporânea não devem ser preditores do mesmo alvo sem verificar vazamento",
                              "a geometria inclinada usa a hipótese autorizada de 20° e orientação norte",
                              "o cache ERA5 começa em 02/01; 01/01 é reprovado por falta meteorológica; sem extrapolação"]}
    (caminhos.base_final / "resumo_base_consecutiva.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _grafico(caminhos.figuras, base, qualidade, final, limiar)
    _relatorio(caminhos, resumo, blocos, sensibilidade)
    return {"base": final.reset_index(), "dias_validos": base.loc[elegivel].reset_index(),
            "qualidade": qualidade, "blocos": blocos, "resumo": resumo,
            "sensibilidade": pd.DataFrame(sensibilidade)}


def _grafico(pasta, base, qualidade, final, limiar):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(15, 10))
    axes[0].plot(base.index, qualidade.planta_cobertura_diurna_original_pct, label="Cobertura diurna medida", linewidth=.8, alpha=.65)
    axes[0].plot(base.index, qualidade.planta_cobertura_diurna_tratada_pct, label="Após tratamento de cinco minutos", linewidth=1.)
    axes[0].axhline(limiar, color="#a53d3d", linestyle="--", label=f"Critério: {limiar:g}%")
    axes[0].axvspan(final.index.min(), final.index.max(), color="#5b9561", alpha=.25, label="Maior bloco selecionado")
    axes[0].set_ylabel("Cobertura diurna (%)")
    axes[0].legend(fontsize=8, ncol=2, loc="lower left")
    axes[0].set_title("Seleção do maior bloco consecutivo — calendário completo de 2025")
    axes[1].plot(final.index, final.Active_Power, color="#24658e", marker=".", label="Potência média diária tratada")
    axes[1].set_ylabel("Potência média (kW)")
    axes[1].set_title(f"Base final: {len(final)} dias consecutivos, {final.index.min():%d/%m} a {final.index.max():%d/%m/%Y}")
    axes[1].legend(fontsize=8)
    axes[2].plot(final.index, final.Global_Horizontal_Radiation, color="#c28623", label="GHI ERA5")
    axes[2].plot(final.index, final.Radiation_Global_Tilted, color="#a94737", label="Radiação inclinada ERA5 + Perez")
    axes[2].set_ylabel("Radiação média (W/m²)")
    axes[2].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.2)
        ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(pasta / "diagnostico_base_consecutiva.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def _relatorio(caminhos, resumo, blocos, sensibilidade):
    linhas = ["# Base diária consecutiva recomendada", "",
              f"**Período selecionado: {resumo['inicio']} a {resumo['fim']}, {resumo['dias_consecutivos']} dias consecutivos, sem datas ausentes ou valores nulos nas 13 colunas.**", "",
              "Arquivo principal: [base_diaria_leopoldo_consecutiva.csv](base_diaria_leopoldo_consecutiva.csv). A ordem das colunas é a da Austrália. Os CSVs antigos são resultados de procedimentos anteriores; a saída recomendada deste processamento é este novo arquivo.", "",
              "## Critério de seleção", "",
              f"Cobertura da potência completa dos oito inversores de pelo menos {resumo['limiar_cobertura_diurna_e_24h_pct']:g}% tanto no período diurno quanto nas 24 horas, após tratamento; todas as variáveis diárias finitas; pelo menos um intervalo completo originalmente medido. Dias reprovados e datas ausentes interrompem a sequência. Empates no comprimento são resolvidos pelo início mais antigo.", "",
              f"No ano, {resumo['dias_elegiveis_ano']} dias passaram pelo critério, distribuídos em {resumo['blocos_elegiveis']} blocos. [blocos_consecutivos_leopoldo.csv](blocos_consecutivos_leopoldo.csv) lista todos os períodos. [base_diaria_leopoldo_dias_validos.csv](base_diaria_leopoldo_dias_validos.csv) contém todos os dias aprovados, mas **tem saltos de datas**: não concatenar esses blocos como se fossem uma sequência contínua.", "",
              "**Sem faltantes significa que não faltam dias nem células na base diária selecionada. Não significa que todos os 288 horários de cada dia foram medidos ou preenchidos.** Os intervalos residuais permanecem ausentes; a média diária usa somente os válidos, com o controle de cobertura acima. Não se interpolam dias inteiros para alongar o período.", "",
              "## Processamento", "",
              "1. Seleção da usina 50 pelos oito IDs e números de série, incluindo os dois códigos textuais auditados; deduplicação por equipamento e cinco minutos.",
              "2. Potência: preservação dos observados, inclusive zero. Lacunas internas de até três amostras (15 minutos) são estimadas pelos outros sete inversores quando disponíveis e sem falha sinalizada; razão histórica calculada somente em observações nos 30 dias anteriores, com pelo menos 100 doadores. Não há doadores imputados. Estimativas fora de 0–131,25 kW por inversor são rejeitadas (125 kW nominais + tolerância operacional de 5%).",
              "3. Interpolação linear de blocos originais internos de até três amostras como alternativa, com extremos medidos no mesmo dia. Não estima pontos com falha explicitamente sinalizada. Os demais faltantes noturnos recebem zero apenas com elevação solar aparente abaixo de −6°, após conferir que as leituras noturnas não exibem geração significativa. Amanhecer e anoitecer não recebem zero automaticamente. Leituras observadas não são substituídas.",
              "4. Corrente e contador acumulado: somente interpolação curta, sem aplicar o proxy validado para potência. Zeros de contador acumulado de uma instalação madura são marcados como suspeitos e desconsiderados antes dessa interpolação. Contagens válidas por variável são registradas.",
              "5. Meteorologia exclusivamente ERA5, com cache e SHA-256 verificados; POA pelo modelo Perez, inclinação de 20°, norte e albedo 0,3 conforme hipótese autorizada. Sem mistura de escala com a estação. O cache começa em 02/01: 01/01 é excluído, sem extrapolação meteorológica.",
              "6. Soma dos oito inversores por intervalo e média diária das amostras completas; seleção pelo critério e pelo maior bloco. A chuva conserva a média diária do acumulador para compatibilidade com a definição anterior, e não o total de chuva do dia. A direção do vento usa média circular.", "",
              "## Qualidade e rastreabilidade", "",
              f"Menor cobertura diurna selecionada: {resumo['menor_cobertura_diurna_selecionada_pct']:.2f}%. Menor cobertura nas 24 horas: {resumo['menor_cobertura_24h_selecionada_pct']:.2f}%. Maior parcela de intervalos diurnos completos com alguma estimativa: {resumo['maior_fracao_diurna_estimada_selecionada_pct']:.2f}%.", "",
              "[qualidade_diaria_base_consecutiva.csv](qualidade_diaria_base_consecutiva.csv) contém o ano inteiro, cobertura original/tratada, contagens por método, bloco, seleção e motivos de reprovação. [imputacoes_potencia_5min.csv.gz](imputacoes_potencia_5min.csv.gz) registra cada potência efetivamente preenchida, por horário, inversor e método. Fontes, hashes, parâmetros e limitações estão em [resumo_base_consecutiva.json](resumo_base_consecutiva.json).", "",
              "## Sensibilidade aos limiares", "", "| Cobertura mínima diurna e 24h | Dias aprovados no ano | Maior bloco | Início | Fim |", "| --- | ---: | ---: | --- | --- |"]
    for item in sensibilidade:
        linhas.append(f"| {item['cobertura_minima_pct']:g}% | {item['dias_elegiveis']} | {item['maior_bloco_dias']} | {str(item['inicio'])[:10]} | {str(item['fim'])[:10]} |")
    linhas += ["", "Os limiares são decisões operacionais para comparação, não normas universais. Não foram relaxados para obter um período maior.", "",
               "## Uso na previsão", "",
               "O alvo continua sendo **Active_Power em kW médios**, não energia diária em kWh. A coluna Active_Energy_Delivered_Received continua sendo média de contador acumulado de vida útil. Não usar esse contador ou a corrente contemporânea como preditores do mesmo alvo sem verificar vazamento. A auditoria da definição do alvo australiano continua necessária: esquema igual não basta para garantir comparabilidade física.", "",
               "Este arquivo é uma reconstrução retrospectiva para pesquisa. A interpolação usa o extremo posterior: ao dividir treino e teste, refazer o tratamento por partição, sem atravessar as fronteiras. A razão histórica dos inversores já usa somente o passado. A avaliação principal deve usar alvos medidos de boa cobertura, registrando a fração reconstruída. ERA5 histórica não equivale a uma previsão meteorológica disponível no instante de emissão. O tamanho do bloco não garante dados suficientes para treinar um modelo; os demais blocos podem ser usados em experimentos separados com janelas respeitando as datas.", "",
               "## Visualização", "", "![Cobertura, período selecionado, potência e meteorologia](diagnostico_base_consecutiva.png)", "",
               "## Reprodução", "", "```powershell", ".\\.venv\\Scripts\\python.exe scripts\\executar_fluxo.py base-final", "```", ""]
    texto = "\n".join(linhas)
    destinos = {
        "base_diaria_leopoldo_consecutiva.csv": "../data/processed/brasil/base_diaria_leopoldo_consecutiva.csv",
        "base_diaria_leopoldo_dias_validos.csv": "../data/processed/brasil/base_diaria_leopoldo_dias_validos.csv",
        "diagnostico_base_consecutiva.png": "../reports/figures/diagnostico_base_consecutiva.png",
    }
    for nome in ["blocos_consecutivos_leopoldo.csv", "qualidade_diaria_base_consecutiva.csv",
                 "imputacoes_potencia_5min.csv.gz", "resumo_base_consecutiva.json"]:
        destinos[nome] = f"../reports/base_final/{nome}"
    for nome, destino in destinos.items():
        texto = texto.replace(f"]({nome})", f"]({destino})")
    (caminhos.documentacao / "base_consecutiva.md").write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    resultado = gerar_base()
    print(json.dumps({k: resultado["resumo"][k] for k in ["inicio", "fim", "dias_consecutivos", "dias_elegiveis_ano", "blocos_elegiveis", "nulos_base_final"]}, ensure_ascii=False, indent=2))
    print(resultado["blocos"].head(10).to_string(index=False))
