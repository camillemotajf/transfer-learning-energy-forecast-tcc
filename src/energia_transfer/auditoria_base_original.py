"""Audita ausências nos CSVs originais, sem alterar as bases de modelagem.

Executar: python scripts/executar_fluxo.py auditoria
Compara o filtro textual anterior com o ID da usina e as identidades dos inversores.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib

from .caminhos import CaminhosProjeto


FUSO = "America/Sao_Paulo"
METRICAS_INV = [
    "total_active_power_w", "total_power_yields_kwh", "daily_power_yields_kwh",
    "phase_a_current_a", "phase_b_current_a", "phase_c_current_a",
]
METRICAS_EST = [
    "air_speed_med", "air_temperature_med", "ghi_irr_med", "poa_irr_med",
    "dir_vento_med", "precipitacao_acc_day",
]


def interpolar_blocos_internos(serie, max_pontos=3):
    """Estima somente blocos inteiros curtos com extremos no mesmo dia local."""
    falta = serie.isna()
    grupos = falta.ne(falta.shift()).cumsum()
    comprimento = falta.groupby(grupos).transform("sum")
    horario = pd.Series(serie.index, index=serie.index)
    antes = horario.where(~falta).ffill()
    depois = horario.where(~falta).bfill()
    mesmo_dia = antes.dt.normalize().eq(depois.dt.normalize())
    permitida = falta & comprimento.le(max_pontos) & mesmo_dia
    return serie.mask(permitida, serie.interpolate(method="time", limit_area="inside"))


def _limpar(bruto, equipamento, metricas, codigo=None):
    dados = bruto.loc[bruto["meta.id_usina"].eq(50)].copy()
    if codigo is not None:
        dados = dados.loc[dados.usine_code.eq(codigo)].copy()
    dados = dados.dropna(subset=["t", equipamento])
    if "fail_read" in dados:
        dados = dados.loc[~dados.fail_read.astype("string").str.lower().eq("true").fillna(False)].copy()
    dados["slot"] = dados.t.dt.floor("5min")
    dados["_validos"] = dados[metricas].notna().sum(axis=1)
    dados["_coleta"] = pd.to_datetime(dados.real_datetime.astype("string"), utc=True, errors="coerce", format="mixed")
    dados["_ordem"] = range(len(dados))
    return dados.sort_values(
        ["slot", equipamento, "_validos", "t", "_coleta", "_ordem"], na_position="first",
    ).drop_duplicates(["slot", equipamento], keep="last")


def _por_dia(serie, calendario, operacao="sum"):
    grupos = serie.groupby(serie.index.tz_localize(None).normalize())
    return getattr(grupos, operacao)().reindex(calendario, fill_value=0)


def _maior_bloco(serie):
    falta = serie.isna()
    grupos = falta.ne(falta.shift()).cumsum()
    dias = serie.index.tz_localize(None).normalize()
    comprimentos = falta.groupby([dias, grupos]).transform("sum").where(falta, 0)
    return comprimentos.groupby(dias).max().mul(5)


def _lacunas(serie, fonte):
    falta = serie.isna()
    grupos = falta.ne(falta.shift()).cumsum()
    registros = []
    for _, parte in serie.loc[falta].groupby(grupos[falta]):
        n = len(parte)
        registros.append({"fonte": fonte, "inicio": parte.index.min(), "fim": parte.index.max(),
                          "pontos_5min": n, "duracao_minutos": n * 5,
                          "classe": "5 min" if n == 1 else "10 min" if n == 2 else "15 min" if n == 3 else "20–60 min" if n <= 12 else ">60 min"})
    return registros


def executar_auditoria(pasta=None, ano=2025, *, caminhos=None):
    caminhos = caminhos or CaminhosProjeto()
    caminhos.preparar_saidas()
    pasta = Path(pasta or caminhos.brutos_brasil)
    saida = caminhos.auditoria
    cols_inv = ["datetime", "real_datetime", "meta.id_usina", "meta.id_inversor", "usine_code",
                "serial_number", "fault_code", *METRICAS_INV]
    cols_est = ["datetime", "real_datetime", "meta.id_usina", "meta.id", "usine_code", "fail_read", *METRICAS_EST]
    inv = pd.read_csv(pasta / "Leopoldo-fixa-inv.csv", usecols=cols_inv, low_memory=False)
    est = pd.read_csv(pasta / "Leopoldo-fixa-est.csv", usecols=cols_est, low_memory=False)
    for dados in [inv, est]:
        dados["t"] = pd.to_datetime(dados.datetime, utc=True, format="mixed", errors="coerce").dt.tz_convert(FUSO)
    calendario = pd.date_range(f"{ano}-01-01", f"{ano}-12-31", freq="D", name="timestamp")
    grade = pd.date_range(calendario.min().tz_localize(FUSO), (calendario.max() + pd.Timedelta(days=1)).tz_localize(FUSO), freq="5min", inclusive="left", name="timestamp")
    posicao = pvlib.solarposition.get_solarposition(grade, -16.55, -48.85, altitude=927)
    diurno = posicao.apparent_elevation.gt(0)
    civil = posicao.apparent_elevation.ge(-6)
    escuro = posicao.apparent_elevation.lt(-6)
    esperado_diurno = _por_dia(diurno.astype(int), calendario)
    esperado_noturno = _por_dia((~diurno).astype(int), calendario)

    identidades = inv.groupby(["usine_code", "meta.id_inversor"], as_index=False).agg(
        linhas=("datetime", "size"), serial=("serial_number", lambda s: ",".join(sorted(s.dropna().unique().astype(str)))),
        inicio=("t", "min"), fim=("t", "max"),
    )
    seriais = inv.groupby("meta.id_inversor").serial_number.nunique()
    identidade_consistente = bool(seriais.eq(1).all() and inv["meta.id_usina"].eq(50).all())
    ids = sorted(inv.loc[inv["meta.id_usina"].eq(50), "meta.id_inversor"].unique().tolist())
    if len(ids) != 8 or not identidade_consistente:
        raise ValueError("O cenário por identidade requer exatamente oito inversores e um serial por ID.")

    est_limpa = _limpar(est, "meta.id", METRICAS_EST)
    est_limpa = est_limpa.loc[est_limpa.slot.isin(grade)]
    if est_limpa["meta.id"].nunique() != 1:
        raise ValueError("Esperada uma estação meteorológica.")
    meteo = est_limpa.set_index("slot")[METRICAS_EST].reindex(grade)
    registro_estacao = pd.Series(grade.isin(est_limpa.slot), index=grade)
    meteo_linear = meteo.apply(interpolar_blocos_internos)
    est_validos = meteo.notna().all(axis=1)
    diario_est = pd.DataFrame(index=calendario)
    diario_est["estacao_esperados_5min"] = 288
    diario_est["estacao_registros_presentes"] = _por_dia(registro_estacao.astype(int), calendario)
    bruto_est_ano = est.loc[est.t.ge(grade.min()) & est.t.lt(grade.max() + pd.Timedelta(minutes=5))]
    diario_est["estacao_linhas_brutas"] = bruto_est_ano.groupby(bruto_est_ano.t.dt.tz_localize(None).dt.normalize()).size().reindex(calendario, fill_value=0)
    diario_est["estacao_duplicatas_removidas"] = diario_est.estacao_linhas_brutas - diario_est.estacao_registros_presentes
    diario_est["estacao_registros_ausentes"] = 288 - diario_est.estacao_registros_presentes
    diario_est["estacao_intervalos_validos"] = _por_dia(est_validos.astype(int), calendario)
    diario_est["estacao_faltantes_pct"] = 100 * (1 - diario_est.estacao_intervalos_validos / 288)
    diario_est["estacao_faltantes_diurnos"] = esperado_diurno - _por_dia((est_validos & diurno).astype(int), calendario)
    diario_est["estacao_cobertura_diurna_pct"] = 100 * (1 - diario_est.estacao_faltantes_diurnos / esperado_diurno)
    diario_est["estacao_pontos_recuperaveis_linear15"] = _por_dia((meteo_linear.notna().all(axis=1) & ~est_validos).astype(int), calendario)
    diario_est["estacao_cobertura_diurna_poslinear15_pct"] = 100 * _por_dia((meteo_linear.notna().all(axis=1) & diurno).astype(int), calendario) / esperado_diurno
    diario_est["estacao_maior_lacuna_local_min"] = _maior_bloco(meteo.air_temperature_med).reindex(calendario)

    tabelas_variaveis, detalhe_inv, lacunas = [], [], _lacunas(meteo.air_temperature_med, "estacao")
    for coluna in METRICAS_EST:
        validos = _por_dia(meteo[coluna].notna().astype(int), calendario)
        tabela = pd.DataFrame({"cenario": "original_estacao", "fonte": "estacao", "variavel": coluna,
                              "esperados": 288, "registros_ausentes": diario_est.estacao_registros_ausentes,
                              "valores_vazios_em_registros_presentes": diario_est.estacao_registros_presentes - validos,
                              "valores_validos": validos, "faltantes_total": 288 - validos}, index=calendario)
        tabelas_variaveis.append(tabela.reset_index())

    cenarios, paineis = {}, {}
    for nome, codigo in [("filtro_FX", "07-07FX"), ("identidade", None)]:
        dados = _limpar(inv, "meta.id_inversor", METRICAS_INV, codigo)
        dados = dados.loc[dados.slot.isin(grade)]
        contagem_registros = dados.groupby(dados.slot.dt.tz_localize(None).dt.normalize()).size().reindex(calendario, fill_value=0)
        potencia = dados.pivot(index="slot", columns="meta.id_inversor", values="total_active_power_w").reindex(index=grade, columns=ids)
        linear = potencia.apply(interpolar_blocos_internos)
        total = potencia.sum(axis=1, min_count=len(ids)) / 1000
        total_linear = linear.sum(axis=1, min_count=len(ids)) / 1000
        n = potencia.notna().sum(axis=1)
        diario = pd.DataFrame(index=calendario)
        diario["inversores_slots_esperados"] = 288 * len(ids)
        diario["inversores_registros_presentes"] = contagem_registros
        bruto_inv_ano = inv.loc[inv.t.ge(grade.min()) & inv.t.lt(grade.max() + pd.Timedelta(minutes=5))]
        if codigo is not None:
            bruto_inv_ano = bruto_inv_ano.loc[bruto_inv_ano.usine_code.eq(codigo)]
        diario["inversores_linhas_brutas"] = bruto_inv_ano.groupby(bruto_inv_ano.t.dt.tz_localize(None).dt.normalize()).size().reindex(calendario, fill_value=0)
        diario["inversores_duplicatas_removidas"] = diario.inversores_linhas_brutas - contagem_registros
        diario["inversores_registros_ausentes"] = 288 * len(ids) - contagem_registros
        diario["inversores_potencias_validas"] = _por_dia(n, calendario)
        diario["inversores_potencias_vazias_em_registros"] = contagem_registros - diario.inversores_potencias_validas
        diario["inversores_potencias_faltantes_total"] = 288 * len(ids) - diario.inversores_potencias_validas
        diario["planta_intervalos_completos"] = _por_dia(total.notna().astype(int), calendario)
        diario["planta_intervalos_faltantes"] = 288 - diario.planta_intervalos_completos
        diario["planta_intervalos_parciais"] = _por_dia(n.between(1, len(ids) - 1).astype(int), calendario)
        diario["planta_intervalos_apenas_um_inversor_faltante"] = _por_dia(n.eq(len(ids) - 1).astype(int), calendario)
        diario["planta_intervalos_sem_potencia"] = _por_dia(n.eq(0).astype(int), calendario)
        diario["planta_cobertura_24h_pct"] = 100 * diario.planta_intervalos_completos / 288
        diario["planta_esperados_diurnos"] = esperado_diurno
        diario["planta_diurnos_faltantes"] = esperado_diurno - _por_dia((total.notna() & diurno).astype(int), calendario)
        diario["planta_cobertura_diurna_pct"] = 100 * (1 - diario.planta_diurnos_faltantes / esperado_diurno)
        diario["planta_esperados_noturnos"] = esperado_noturno
        diario["planta_noturnos_faltantes"] = esperado_noturno - _por_dia((total.notna() & ~diurno).astype(int), calendario)
        diario["planta_maior_lacuna_local_min"] = _maior_bloco(total).reindex(calendario)
        diario["planta_intervalos_completos_poslinear15"] = _por_dia(total_linear.notna().astype(int), calendario)
        diario["planta_intervalos_recuperaveis_linear15"] = diario.planta_intervalos_completos_poslinear15 - diario.planta_intervalos_completos
        diario["planta_cobertura_diurna_poslinear15_pct"] = 100 * _por_dia((total_linear.notna() & diurno).astype(int), calendario) / esperado_diurno
        diario["potencia_media_amostras_kw"] = _por_dia(total, calendario, "mean")
        diario["medicoes_positivas_escuro"] = _por_dia((total.gt(1) & escuro).astype(int), calendario)
        diario["contador_lifetime_zerado_suspeito"] = dados.loc[dados.total_power_yields_kwh.eq(0)].groupby(dados.slot.dt.tz_localize(None).dt.normalize()).size().reindex(calendario, fill_value=0)
        diario["inversores_registros_com_falha_sinalizada"] = dados.loc[dados.fault_code.fillna(0).ne(0)].groupby(dados.slot.dt.tz_localize(None).dt.normalize()).size().reindex(calendario, fill_value=0)
        diario = diario.join(diario_est)
        cenarios[nome] = diario
        paineis[nome] = (dados, potencia, total, linear)
        for coluna in METRICAS_INV:
            validos = dados.groupby(dados.slot.dt.tz_localize(None).dt.normalize())[coluna].count().reindex(calendario, fill_value=0)
            tabela = pd.DataFrame({"cenario": nome, "fonte": "inversores", "variavel": coluna,
                                  "esperados": 288 * len(ids), "registros_ausentes": diario.inversores_registros_ausentes,
                                  "valores_vazios_em_registros_presentes": contagem_registros - validos,
                                  "valores_validos": validos, "faltantes_total": 288 * len(ids) - validos}, index=calendario)
            tabelas_variaveis.append(tabela.reset_index())
        for equipamento in ids:
            validos = _por_dia(potencia[equipamento].notna().astype(int), calendario)
            detalhamento = pd.DataFrame({"cenario": nome, "id_inversor": equipamento,
                                        "esperados": 288, "potencias_validas": validos,
                                        "potencias_faltantes": 288 - validos,
                                        "cobertura_pct": 100 * validos / 288}, index=calendario)
            detalhe_inv.append(detalhamento.reset_index())
            if nome == "identidade":
                lacunas.extend(_lacunas(potencia[equipamento], f"inversor_{equipamento}"))
        lacunas.extend(_lacunas(total, f"planta_{nome}"))

    # Alternativa de alvo diário: diferença de medidor acumulado antes/depois
    # do período de luz civil. Não depende de interpolar os pontos internos.
    dados, potencia, total, linear = paineis["identidade"]
    contador = dados.pivot(index="slot", columns="meta.id_inversor", values="total_power_yields_kwh").reindex(index=grade, columns=ids)
    contador = contador.where(contador.gt(0))  # Zero em medidor de instalação madura é suspeito.
    energia = []
    for dia in calendario:
        fatia = grade[grade.tz_localize(None).normalize() == dia]
        luz = fatia[civil.reindex(fatia).to_numpy()]
        primeiro, ultimo = luz.min(), luz.max()
        janela = contador.reindex(fatia)
        inicio = janela.loc[(janela.index >= primeiro - pd.Timedelta(hours=1)) & (janela.index <= primeiro)].ffill().iloc[-1]
        fim = janela.loc[(janela.index >= ultimo) & (janela.index <= ultimo + pd.Timedelta(hours=1))].bfill().iloc[0]
        sem_queda = ~janela.diff().lt(-2).any(axis=0)
        deltas = (fim - inicio).where(sem_queda & fim.ge(inicio))
        energia.append({"timestamp": dia, "inversores_com_contador_fronteiras": int(deltas.notna().sum()),
                        "energia_por_contadores_kwh": deltas.sum(min_count=len(ids)),
                        "potencia_equivalente_24h_kw": deltas.sum(min_count=len(ids)) / 24})
    energia = pd.DataFrame(energia).set_index("timestamp")
    energia = energia.join(cenarios["identidade"][["potencia_media_amostras_kw", "planta_cobertura_24h_pct", "planta_cobertura_diurna_pct"]])
    energia["diferenca_media_amostras_pct"] = 100 * (energia.potencia_media_amostras_kw / energia.potencia_equivalente_24h_kw - 1)

    diario = cenarios["identidade"].copy()
    for coluna in ["planta_intervalos_completos", "planta_cobertura_diurna_pct", "potencia_media_amostras_kw"]:
        diario[f"{coluna}_filtro_FX"] = cenarios["filtro_FX"][coluna]
    diario["intervalos_recuperados_por_identidade"] = diario.planta_intervalos_completos - diario.planta_intervalos_completos_filtro_FX
    diario["dias_energia_contador_disponivel"] = energia.energia_por_contadores_kwh.notna()
    diario["energia_por_contadores_kwh"] = energia.energia_por_contadores_kwh
    diario["potencia_equivalente_24h_kw"] = energia.potencia_equivalente_24h_kw
    variaveis = pd.concat(tabelas_variaveis, ignore_index=True)
    detalhe_inv = pd.concat(detalhe_inv, ignore_index=True)
    lacunas = pd.DataFrame(lacunas)
    resumo_lacunas = lacunas.groupby(["fonte", "classe"], as_index=False).agg(blocos=("pontos_5min", "size"), pontos_faltantes=("pontos_5min", "sum"), minutos_faltantes=("duracao_minutos", "sum"))
    mensal = diario.groupby(diario.index.to_period("M")).agg(
        dias=("planta_intervalos_completos", "size"),
        dias_sem_potencia=("planta_intervalos_completos", lambda x: int(x.eq(0).sum())),
        dias_sem_estacao=("estacao_intervalos_validos", lambda x: int(x.eq(0).sum())),
        faltantes_estacao=("estacao_registros_ausentes", "sum"),
        faltantes_potencia_planta=("planta_intervalos_faltantes", "sum"),
        recuperaveis_linear15=("planta_intervalos_recuperaveis_linear15", "sum"),
        recuperados_por_identidade=("intervalos_recuperados_por_identidade", "sum"),
        cobertura_media_diurna_pct=("planta_cobertura_diurna_pct", "mean"),
    )
    mensal.index = mensal.index.astype(str)
    faixas = []
    for nome, tabela in cenarios.items():
        for limiar in (50, 75, 80, 90, 95, 99, 100):
            faixas.append({"cenario": nome, "cobertura_minima_pct": limiar,
                           "dias_cobertura_24h": int(tabela.planta_cobertura_24h_pct.ge(limiar).sum()),
                           "dias_cobertura_diurna": int(tabela.planta_cobertura_diurna_pct.ge(limiar).sum()),
                           "dias_diurna_poslinear15": int(tabela.planta_cobertura_diurna_poslinear15_pct.ge(limiar).sum()),
                           "dias_com_estacao_e_potencia_diurnas": int((tabela.planta_cobertura_diurna_pct.ge(limiar) & tabela.estacao_cobertura_diurna_pct.ge(limiar)).sum()),
                           "dias_conjuntos_poslinear15": int((tabela.planta_cobertura_diurna_poslinear15_pct.ge(limiar) & tabela.estacao_cobertura_diurna_poslinear15_pct.ge(limiar)).sum())})
    resumo = {
        "ano": ano, "fuso": FUSO, "dias_calendario": len(calendario), "passos_5min_por_dia": 288,
        "inversores": ids, "serial_unico_por_id": identidade_consistente,
        "linhas_brutas_inversores": len(inv), "linhas_brutas_estacao": len(est),
        "potencias_nulas_no_arquivo": int(inv.total_active_power_w.isna().sum()),
        "meteo_valores_nulos_em_linhas_existentes": int(est[METRICAS_EST].isna().sum().sum()),
        "dias_sem_potencia_filtro_FX": int(cenarios["filtro_FX"].planta_intervalos_completos.eq(0).sum()),
        "dias_sem_potencia_identidade": int(diario.planta_intervalos_completos.eq(0).sum()),
        "dias_sem_potencia_poslinear15": int(diario.planta_intervalos_completos_poslinear15.eq(0).sum()),
        "dias_sem_estacao": int(diario.estacao_intervalos_validos.eq(0).sum()),
        "intervalos_planta_recuperados_identidade": int(diario.intervalos_recuperados_por_identidade.sum()),
        "intervalos_planta_recuperaveis_linear15": int(diario.planta_intervalos_recuperaveis_linear15.sum()),
        "intervalos_estacao_recuperaveis_linear15": int(diario.estacao_pontos_recuperaveis_linear15.sum()),
        "dias_energia_contador_disponivel": int(energia.energia_por_contadores_kwh.notna().sum()),
        "dias_recuperados_energia_sem_potencia": int((energia.energia_por_contadores_kwh.notna() & diario.planta_intervalos_completos.eq(0)).sum()),
        "faltantes_planta_diurnos": int(diario.planta_diurnos_faltantes.sum()),
        "faltantes_planta_noturnos": int(diario.planta_noturnos_faltantes.sum()),
        "intervalos_potencia_positiva_escuro": int(diario.medicoes_positivas_escuro.sum()),
    }
    colunas_resumo = ["estacao_registros_presentes", "estacao_registros_ausentes", "estacao_faltantes_pct",
                      "inversores_potencias_validas", "inversores_potencias_faltantes_total",
                      "planta_intervalos_completos", "planta_intervalos_faltantes", "planta_diurnos_faltantes",
                      "planta_noturnos_faltantes", "planta_cobertura_diurna_pct", "intervalos_recuperados_por_identidade",
                      "planta_intervalos_recuperaveis_linear15", "estacao_pontos_recuperaveis_linear15"]
    validacao = validar_lacunas_potencia(paineis["identidade"][1], diurno)
    validacao_resumo = validacao.groupby(["metodo", "lacuna_minutos"], as_index=False).agg(
        casos=("caso", "nunique"), pontos=("erro_kw", "size"),
        MAE_kw=("erro_kw", lambda s: float(s.abs().mean())),
        RMSE_kw=("erro_kw", lambda s: float(np.sqrt((s ** 2).mean()))),
        erro_absoluto_p95_kw=("erro_kw", lambda s: float(s.abs().quantile(0.95))),
    )
    validacao_resumo["NRMSE_potencia_nominal_125kw_pct"] = 100 * validacao_resumo.RMSE_kw / 125
    tabelas = {"faltantes_por_dia.csv": diario.reset_index(), "resumo_por_dia.csv": diario[colunas_resumo].reset_index(), "faltantes_por_dia_filtro_FX.csv": cenarios["filtro_FX"].reset_index(),
               "faltantes_por_inversor_dia.csv": detalhe_inv, "faltantes_por_variavel_dia.csv": variaveis,
               "resumo_mensal.csv": mensal.rename_axis("mes").reset_index(), "identidades_e_codigos.csv": identidades,
               "lacunas_continuas.csv": lacunas, "resumo_tamanhos_lacunas.csv": resumo_lacunas,
               "cobertura_por_limiar.csv": pd.DataFrame(faixas), "alternativa_energia_por_contadores.csv": energia.reset_index(),
               "validacao_lacunas_curtas.csv": validacao_resumo, "validacao_lacunas_curtas_detalhada.csv": validacao}
    for nome, tabela in tabelas.items():
        tabela.to_csv(saida / nome, index=False)
    (saida / "resumo_auditoria.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _graficos(caminhos.figuras, diario, detalhe_inv)
    return {"diario": diario, "mensal": mensal, "limiares": pd.DataFrame(faixas), "energia": energia, "resumo": resumo}


def validar_lacunas_potencia(potencia, diurno, seed=42, casos_mes=15):
    """Oculta um inversor por vez em blocos curtos medidos, sem ajustar no teste.

    Compara interpolação entre extremos com a razão histórica do equipamento
    para os outros sete. A razão usa somente os 30 dias anteriores ao bloco.
    Os outros sete devem estar medidos em todos os pontos do bloco.
    """
    rng = np.random.default_rng(seed)
    todos = potencia.notna().all(axis=1)
    registros, caso = [], 0
    for n in (1, 2, 3):
        janela_valida = todos & diurno
        candidatos = np.flatnonzero(janela_valida.rolling(n + 2).sum().eq(n + 2).to_numpy()) - n
        candidatos = candidatos[(candidatos > 0) & (candidatos + n < len(potencia))]
        for mes in range(1, 13):
            opcoes = candidatos[potencia.index[candidatos].month == mes]
            escolhidos = rng.choice(opcoes, size=min(casos_mes, len(opcoes)), replace=False)
            for inicio in escolhidos:
                equipamento = rng.choice(potencia.columns.to_numpy())
                outros = potencia.columns[potencia.columns != equipamento]
                horario = potencia.index[inicio]
                historico = potencia.loc[horario - pd.Timedelta(days=30):horario - pd.Timedelta(minutes=5)]
                soma_outros = historico[outros].sum(axis=1, min_count=len(outros))
                razoes = (historico[equipamento] / soma_outros).where(historico[equipamento].gt(1000) & soma_outros.gt(7000)).dropna()
                if len(razoes) < 100:
                    continue  # Os dois métodos são comparados sobre os mesmos casos.
                alvo = potencia.iloc[inicio:inicio + n][equipamento].to_numpy() / 1000
                esquerdo, direito = potencia.iloc[inicio - 1][equipamento], potencia.iloc[inicio + n][equipamento]
                linear = np.linspace(esquerdo, direito, n + 2)[1:-1] / 1000
                vizinhos = potencia.iloc[inicio:inicio + n][outros].sum(axis=1).to_numpy() * float(razoes.median()) / 1000
                caso += 1
                for metodo, previsto in [("linear_temporal", linear), ("outros_7_inversores", vizinhos)]:
                    for j, (real, estimado) in enumerate(zip(alvo, previsto)):
                        registros.append({"caso": caso, "id_inversor": equipamento, "metodo": metodo,
                                          "lacuna_minutos": n * 5, "timestamp": potencia.index[inicio + j],
                                          "potencia_real_kw": real, "potencia_estimada_kw": estimado,
                                          "erro_kw": estimado - real, "doadores_historicos": len(razoes)})
    return pd.DataFrame(registros)


def _graficos(saida, diario, detalhe_inv):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig, eixos = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    eixos[0].plot(diario.index, diario.estacao_registros_ausentes, color="#ac3939", linewidth=1)
    eixos[0].set_title("Estação: registros ausentes por dia (esperados: 288)")
    eixos[1].plot(diario.index, 288 - diario.planta_intervalos_completos_filtro_FX, color="#b4512b", label="Filtro textual anterior", linewidth=1)
    eixos[1].plot(diario.index, diario.planta_intervalos_faltantes, color="#24658e", label="Usina 50 e mesmos oito inversores", linewidth=1)
    eixos[1].plot(diario.index, 288 - diario.planta_intervalos_completos_poslinear15, color="#3f855d", label="Simulação: interpolação interna até 15 min", linewidth=1)
    eixos[1].set_title("Planta: intervalos sem potência completa dos oito inversores")
    eixos[1].legend(fontsize=8)
    eixos[2].plot(diario.index, diario.planta_diurnos_faltantes, label="Com sol acima do horizonte", color="#bd741e", linewidth=1)
    eixos[2].plot(diario.index, diario.planta_noturnos_faltantes, label="Sol abaixo do horizonte", color="#586b8d", linewidth=1)
    eixos[2].set_title("Onde faltam as leituras da planta: dia e noite")
    eixos[2].legend(fontsize=8)
    for ax in eixos:
        ax.set_ylabel("Intervalos de 5 minutos")
        ax.set_ylim(-5, 300)
        ax.grid(alpha=0.2)
    eixos[-1].xaxis.set_major_locator(mdates.MonthLocator())
    eixos[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    fig.suptitle("Auditoria dos arquivos originais — 2025, America/Sao_Paulo")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(saida / "faltantes_originais_por_dia.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    inv = detalhe_inv.loc[detalhe_inv.cenario.eq("identidade")].pivot(index="id_inversor", columns="timestamp", values="cobertura_pct")
    matriz = [diario.estacao_faltantes_pct.to_numpy()]
    rotulos = ["Estação"]
    for equipamento in inv.index:
        matriz.append(100 - inv.loc[equipamento].reindex(diario.index).to_numpy())
        rotulos.append(f"Inversor {equipamento}")
    matriz.append(100 - diario.planta_cobertura_24h_pct.to_numpy())
    rotulos.append("Planta: oito completos")
    fig, ax = plt.subplots(figsize=(16, 5))
    imagem = ax.imshow(matriz, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=100, interpolation="none")
    ax.set_yticks(range(len(rotulos)), rotulos)
    meses = diario.index[diario.index.day == 1]
    ax.set_xticks(diario.index.get_indexer(meses), meses.strftime("%m/%Y"))
    ax.set_title("Percentual de ausências por dia — registros únicos esperados a cada 5 minutos")
    fig.colorbar(imagem, ax=ax, label="Faltantes (%)")
    fig.tight_layout()
    fig.savefig(saida / "mapa_faltantes_originais.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    resultado = executar_auditoria()
    print(json.dumps(resultado["resumo"], ensure_ascii=False, indent=2))
    print(resultado["mensal"].round(2).to_string())
    print(resultado["limiares"].to_string(index=False))
