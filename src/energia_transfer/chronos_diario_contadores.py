"""Repete o piloto diário com energia validada pelos contadores dos oito inversores."""
from pathlib import Path
import hashlib
import importlib.metadata
import json

import numpy as np
import pandas as pd

from .chronos_diario import extrair_diarias, avaliar as avaliar_diario
from .chronos_experimentos import salvar_json, sha256, treinar

NUMERICAS = ["total_active_power_w", "daily_power_yields_kwh", "total_power_yields_kwh"]
METEO = ["Weather_Temperature_Celsius", "Weather_Relative_Humidity", "Global_Horizontal_Radiation"]
PERIODOS = {"treino": ("2025-01-01", "2025-09-30"),
            "validacao": ("2025-10-01", "2025-10-31"),
            "teste": ("2025-11-01", "2025-12-31")}


def reconstruir_contadores(inv, usina="07-07FX", n_inversores=8):
    """Segue a regra enviada: máximo diário, diferença acumulada e tolerância max(8, 3%).

    A ausência de registros de potência não invalida um contador de energia completo.
    Um dia só é aprovado quando os oito equipamentos distintos passam a conferência.
    Não interpola energia, potência ou contadores.
    """
    inv = inv.loc[inv.usine_code.eq(usina)].copy()
    inv["instante"] = (pd.to_datetime(inv.datetime, utc=True, errors="coerce")
                       .dt.tz_convert("America/Sao_Paulo").dt.floor("5min"))
    inv = inv.dropna(subset=["instante", "equipment_name"])
    for c in NUMERICAS:
        inv[c] = pd.to_numeric(inv[c], errors="coerce")
        inv.loc[inv[c] < 0, c] = np.nan
    antes = len(inv)
    inv = inv.groupby(["instante", "equipment_name"], as_index=False)[NUMERICAS].median()
    duplicatas = antes - len(inv)
    inv["dia"] = inv.instante.dt.tz_localize(None).dt.normalize()
    inv = inv[inv.dia.dt.year.eq(2025)].copy()
    equipamentos = sorted(inv.equipment_name.unique().tolist())
    if len(equipamentos) != n_inversores:
        raise ValueError(f"Esperados {n_inversores} equipamentos distintos; encontrados {equipamentos}.")
    inv["hora"] = inv.instante.dt.hour + inv.instante.dt.minute/60
    contadores = inv[inv.hora >= 6].groupby(["dia", "equipment_name"]).agg(
        energia_dia_kwh=("daily_power_yields_kwh", "max"),
        leituras_potencia=("total_active_power_w", "count"))
    inicio = (inv[inv.hora < 4].groupby(["dia", "equipment_name"])
              .total_power_yields_kwh.median().rename("acumulado_inicio"))
    fim = (inv[inv.hora >= 19].groupby(["dia", "equipment_name"])
           .total_power_yields_kwh.median().rename("acumulado_fim"))
    por_inv = contadores.join(inicio).join(fim)
    por_inv["energia_pelo_acumulado"] = por_inv.acumulado_fim - por_inv.acumulado_inicio
    e1, e2 = por_inv.energia_dia_kwh, por_inv.energia_pelo_acumulado
    por_inv["diferenca_contadores"] = (e1 - e2).abs()
    por_inv["consistente"] = (e1.between(0, 1600) & e2.ge(0)
                             & por_inv.diferenca_contadores.le(np.maximum(8, .03*e1)))
    # Sinalizadores permitem distinguir falta de bordas, reset e divergência.
    por_inv["sem_inicio"] = por_inv.acumulado_inicio.isna()
    por_inv["sem_fim"] = por_inv.acumulado_fim.isna()
    por_inv["sem_contador_diario"] = e1.isna()
    por_inv["energia_fora_limite"] = e1.notna() & ~e1.between(0, 1600)
    por_inv["acumulado_negativo"] = e2.lt(0)
    por_inv["contadores_divergentes"] = (e1.notna() & e2.notna()
                                        & por_inv.diferenca_contadores.gt(np.maximum(8, .03*e1)))
    diario = por_inv.groupby(level="dia").agg(
        n_inversores=("energia_dia_kwh", "count"), n_consistentes=("consistente", "sum"),
        energia_bruta_kwh=("energia_dia_kwh", "sum"),
        maior_diferenca_contadores_kwh=("diferenca_contadores", "max"))
    diario["valido"] = diario.n_consistentes.eq(n_inversores)
    diario["energia_kwh"] = diario.energia_bruta_kwh.where(diario.valido)
    diario["Active_Power"] = diario.energia_kwh/24
    grade = pd.date_range("2025-01-01", "2025-12-31", freq="D", name="timestamp")
    diario = diario.reindex(grade)
    diario["valido"] = diario.valido.eq(True)
    v = diario.valido
    diario["janela_3_dias_valida"] = v & v.shift(1, fill_value=False) & v.shift(2, fill_value=False) & v.shift(3, fill_value=False)
    # Cobertura dos 288 horários informa a auditoria; não muda a regra de energia.
    cobertura = inv.assign(presente=inv.total_active_power_w.notna()).groupby(["dia", "equipment_name"]).presente.sum()
    por_inv["leituras_potencia_24h"] = cobertura
    completo = pd.MultiIndex.from_product([grade, equipamentos], names=["dia", "equipment_name"])
    falhas = por_inv.reindex(completo)
    falhas["consistente"] = falhas.consistente.eq(True)
    falhas["sem_registro_apos_6h"] = falhas.energia_dia_kwh.isna() & falhas.leituras_potencia.isna()
    meta = {"usina": usina, "n_inversores": n_inversores, "equipamentos": equipamentos,
            "registros_5min_2025": len(inv), "duplicatas_consolidadas": duplicatas,
            "dias_validos": int(v.sum()), "dias_reprovados": int((~v).sum()),
            "timezone": "America/Sao_Paulo", "imputacao_diaria": False,
            "regra": "daily max após 6h; total mediano <4h e >=19h; 0<=e1<=1600, e2>=0, |e1-e2|<=max(8,0.03*e1); oito consistentes"}
    return diario, por_inv, falhas, meta


def datas_validas(frame, contexto, covariaveis):
    """Exige alvo medido e somente as covariáveis dos dias anteriores."""
    potencia = np.isfinite(frame.Active_Power)
    passado = pd.Series(np.isfinite(frame[["Active_Power"]+covariaveis]).all(axis=1), index=frame.index)
    return frame.index[potencia & passado.shift(1, fill_value=False).rolling(contexto).sum().eq(contexto)]


def preparar(raiz):
    raiz = Path(raiz).resolve()
    pasta = raiz / "experimentos/chronos_diario_contadores"
    out = pasta / "resultados"
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["contexto_passos"] == 3 and cfg["horizonte_passos"] == 1
    bruto = raiz / cfg["arquivo_inversores"]
    colunas = ["datetime", "usine_code", "equipment_name"]+NUMERICAS
    inv = pd.read_csv(bruto, usecols=colunas, low_memory=False)
    diario, por_inv, falhas, meta = reconstruir_contadores(inv, cfg["usina"], cfg["n_inversores"])
    meteo_path = raiz / "data/interim/meteorologia/meteorologia_era5_diaria.csv"
    clima = pd.read_csv(meteo_path, parse_dates=["timestamp"]).set_index("timestamp")
    diario = diario.join(clima[METEO])
    grade = diario.index
    angulo = 2*np.pi*(grade.dayofyear-1)/np.where(grade.is_leap_year, 366., 365.)
    diario["dia_ano_sin"], diario["dia_ano_cos"] = np.sin(angulo), np.cos(angulo)
    frame_br = diario[["Active_Power"]+cfg["colunas_covariaveis"]].copy()
    frame_br["Active_Power"] /= 1000.0
    # Coorte comum aos cenários uni/multivariados, sem exigir clima no próprio alvo.
    datas_br = datas_validas(frame_br, cfg["contexto_passos"], cfg["colunas_covariaveis"])
    diario["janela_3_dias_modelo_valida"] = grade.isin(datas_br)
    arquivo_diario = raiz / "data/processed/brasil/leopoldo_diario_contadores_auditado.csv"
    arquivo_diario.parent.mkdir(parents=True, exist_ok=True)
    diario.to_csv(arquivo_diario)
    qualidade_path = out / "leopoldo_qualidade_por_inversor.csv"
    por_inv.to_csv(qualidade_path)
    falhas.to_csv(out / "qualidade_calendario_por_inversor.csv")
    diario.to_csv(out / "auditoria_calendario_brasil.csv")
    frames_path = pasta / "dados"
    frames_path.mkdir(exist_ok=True)
    frame_br.to_csv(frames_path / "brasil_pu.csv")
    origem = raiz / "experimentos/transfer_learning_australia_brasil/historico_diario/dados"
    fonte_au = origem / "australia_pu.csv"
    frame_au = pd.read_csv(fonte_au, parse_dates=["timestamp"]).set_index("timestamp").sort_index().asfreq("D")
    fontes = [bruto, meteo_path, fonte_au, Path(__file__),
              Path(__file__).with_name("chronos_diario.py"), Path(__file__).with_name("chronos_experimentos.py")]
    dados = dict(raiz=raiz, pasta=pasta, out=out, cfg=cfg, janelas={}, qualidade=diario,
                 brasil_original=diario, colunas_qualidade_avaliacao={
                     "energia_real_kwh": "energia_kwh", "n_inversores_consistentes": "n_consistentes",
                     "maior_diferenca_contadores_kwh": "maior_diferenca_contadores_kwh"})
    auditoria = []
    for particao, (inicio, fim) in PERIODOS.items():
        datas = datas_br[(datas_br >= inicio) & (datas_br <= fim)]
        if len(datas) == 0:
            raise ValueError(f"Sem janelas válidas no {particao}.")
        j = extrair_diarias(frame_br, datas, cfg)
        dados["janelas"]["brasil", particao] = j
        np.savez_compressed(frames_path / f"brasil_lag3_{particao}.npz", **{k: v.to_numpy(dtype="datetime64[ns]") if k=="datas" else v for k,v in j.items()})
        sub = diario.loc[inicio:fim]
        auditoria.append(dict(dominio="brasil", particao=particao, n=len(datas),
                              dias_validos=int(sub.valido.sum()),
                              janelas_so_contadores=int(sub.janela_3_dias_valida.sum()),
                              inicio=str(datas.min().date()), fim=str(datas.max().date())))
    for particao in ["treino", "validacao"]:
        arq = origem / f"australia_lag3_{particao}.npz"
        fontes.append(arq)
        with np.load(arq, allow_pickle=False) as z:
            datas, ref = pd.to_datetime(z["datas"]), z["y_original"].copy()
        j = extrair_diarias(frame_au, datas, cfg)
        np.testing.assert_allclose(j["y"], ref, atol=1e-6)
        dados["janelas"]["australia", particao] = j
        auditoria.append(dict(dominio="australia", particao=particao, n=len(datas),
                              inicio=str(datas.min().date()), fim=str(datas.max().date())))
    pd.DataFrame(auditoria).to_csv(out / "particoes.csv", index=False)
    contagens = []
    for lag in [1, 3, 7, 14]:
        d = datas_validas(frame_br, lag, cfg["colunas_covariaveis"])
        apenas_potencia = datas_validas(frame_br, lag, [])
        for p, (inicio, fim) in PERIODOS.items():
            contagens.append(dict(historico_dias=lag, particao=p,
                                  janelas_so_contadores=int(((apenas_potencia>=inicio)&(apenas_potencia<=fim)).sum()),
                                  janelas_modelo=int(((d>=inicio)&(d<=fim)).sum())))
    pd.DataFrame(contagens).to_csv(out / "janelas_por_historico.csv", index=False)
    antigo_path = raiz / "data/processed/brasil/base_diaria_leopoldo_dias_validos.csv"
    antigo = pd.read_csv(antigo_path, parse_dates=["timestamp"]).set_index("timestamp")
    comparacao = diario[["Active_Power", "valido", "energia_kwh"]].join(antigo.Active_Power.rename("potencia_base_anterior_kw"))
    comparacao["diferenca_kw"] = comparacao.Active_Power-comparacao.potencia_base_anterior_kw
    comparacao.to_csv(out / "comparacao_bases.csv")
    meta.update(arquivo_inversores=cfg["arquivo_inversores"],
                nome_mencionado_no_codigo_usuario="Leopoldo-fixa-inv(1).csv (não localizado; usado CSV original do projeto)",
                dias_base_anterior=int(antigo.Active_Power.notna().sum()),
                dias_recuperados=int((diario.valido & comparacao.potencia_base_anterior_kw.isna()).sum()),
                dias_so_base_anterior=int((~diario.valido & comparacao.potencia_base_anterior_kw.notna()).sum()),
                janelas_sem_meteo_passada=int(diario.janela_3_dias_valida.sum()-len(datas_br)),
                particoes=[r for r in auditoria if r["dominio"]=="brasil"])
    salvar_json(out / "resumo_reconstrucao.json", meta)
    pacotes = {p: importlib.metadata.version(p) for p in ["chronos-forecasting", "torch", "peft", "transformers", "accelerate"]}
    hashes = {str(p.relative_to(raiz)): sha256(p) for p in fontes}
    manifesto = dict(versao_contadores=1, cfg=cfg, arquivos_sha256=hashes, pacotes=pacotes)
    assinatura = hashlib.sha256(json.dumps(manifesto, sort_keys=True).encode()).hexdigest()
    dados.update(assinatura=assinatura, manifesto=manifesto, resumo_reconstrucao=meta)
    salvar_json(out / "manifesto.json", dict(manifesto, assinatura=assinatura))
    print(pd.DataFrame(auditoria).to_string(index=False), flush=True)
    print(f"Contadores: {meta['dias_validos']} dias válidos; {meta['dias_reprovados']} lacunas.", flush=True)
    return dados


def _concluir(dados, resumo, previsoes, decisao):
    out = dados["out"]
    final = resumo.copy()
    final["escolhido_validacao_chronos"] = final.modelo.eq(decisao["escolhido"]["modelo"])
    for c in ["MAE", "RMSE", "BIAS"]:
        final[f"{c}_kWh_dia"] = final[f"{c}_kW"]*24
    final.to_csv(out / "comparacao_final.csv", index=False)
    for c in resumo.modelo:
        previsoes[f"energia_prevista_{c}_kwh"] = previsoes[c]*24
    previsoes.to_csv(out / "previsoes_teste.csv", index=False)
    meta = dados["resumo_reconstrucao"]
    linhas = ["# Chronos-2 diário com contadores — Brasil", "",
              "Alvo: soma da energia diária validada dos oito inversores (kWh), dividida por 24 h para obter potência média em kW.",
              f"{meta['dias_validos']} dias aprovados; {meta['dias_reprovados']} dias reprovados permanecem ausentes. Sem imputação diária.",
              "Histórico de três dias consecutivos; previsão de um dia. Partições cronológicas: treino até setembro, validação em outubro, teste em novembro–dezembro.",
              "Covariáveis: temperatura, umidade, GHI e calendário dos dias passados; futuro: somente calendário. Sem vento. ERA5 é reanálise histórica, com disponibilidade operacional não modelada.",
              "Austrália preservada do estudo diário anterior, normalizada por 24 kW AC; Brasil por 1000 kW AC. A origem não foi reconstruída por contadores.",
              "Os contadores validam totais diários apesar das lacunas de telemetria. Concordância entre contadores não prova calibração dos medidores nem exclui erro comum.",
              "Mantidos os cinco cenários e o orçamento do piloto anterior: até 200 passos LoRA, rank 8, semente 42. Transferência sem Brasil usa somente dados australianos para ajuste/checkpoint.",
              "O teste já foi consultado em estudos anteriores. Comparação exploratória, com apenas uma semente e poucos dias de validação.",
              "As métricas MLP/LSTM e Chronos do alvo anterior não entram neste ranking: referência e datas mudaram.", "",
              "| Partição | Dias válidos | Janelas de 3 dias |", "|---|---:|---:|"]
    for r in meta["particoes"]:
        linhas.append(f"| {r['particao']} | {r['dias_validos']} | {r['n']} |")
    linhas += ["", f"Escolha pela validação: **{decisao['escolhido']['modelo']}**.", "",
               "| Modelo | N teste | MAE kW | RMSE kW | MAE kWh/dia | RMSE kWh/dia | WAPE % |", "|---|---:|---:|---:|---:|---:|---:|"]
    for r in final.to_dict("records"):
        linhas.append(f"| {r['modelo']} | {r['n']} | {r['MAE_kW']:.3f} | {r['RMSE_kW']:.3f} | {r['MAE_kWh_dia']:.3f} | {r['RMSE_kWh_dia']:.3f} | {r['WAPE_pct']:.3f} |")
    linhas += ["", "Fonte e implementação de referência: " + dados["cfg"]["implementacao_autor"],
               "", "CSV bruto efetivamente usado: `"+dados["cfg"]["arquivo_inversores"]+"`. Seu hash consta no manifesto."]
    (out / "relatorio.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")


def avaliar(dados):
    return avaliar_diario(dados, concluir=_concluir)


def graficos(dados):
    import matplotlib.pyplot as plt
    out = dados["out"]
    diario = dados["brasil_original"]
    fig, axes = plt.subplots(2, 1, figsize=(15, 7), sharex=True)
    axes[0].plot(diario.index, diario.energia_kwh, ".-", ms=3, lw=.8, label="Energia validada nos oito inversores")
    ruins = diario.index[~diario.valido]
    axes[0].scatter(ruins, np.zeros(len(ruins)), color="tab:red", marker="|", label="Dias reprovados")
    axes[0].set(ylabel="Energia (kWh/dia)", title="Brasil 2025: reconstrução por contadores, sem preencher dias reprovados")
    axes[0].legend()
    axes[1].step(diario.index, diario.n_consistentes, where="mid", label="Inversores consistentes")
    axes[1].axhline(8, color="tab:green", ls="--", lw=1)
    axes[1].set(ylabel="Inversores", xlabel="Data", ylim=(-.3, 8.5))
    for ax in axes:
        ax.grid(alpha=.25)
        ax.axvline(pd.Timestamp("2025-10-01"), color="gray", ls="--", lw=1)
        ax.axvline(pd.Timestamp("2025-11-01"), color="gray", ls="--", lw=1)
    fig.tight_layout()
    fig.savefig(out / "reconstrucao_contadores.png", dpi=150)
    plt.close(fig)
    b = pd.read_csv(out / "comparacao_bases.csv", parse_dates=["timestamp"]).set_index("timestamp")
    fig, ax = plt.subplots(figsize=(15, 4))
    ax.plot(b.index, b.potencia_base_anterior_kw, lw=.9, alpha=.7, label="Base anterior: média tratada")
    ax.plot(b.index, b.Active_Power, lw=.9, label="Contadores: energia validada / 24 h")
    ax.set(ylabel="Potência média (kW)", title="As bases têm definições e critérios de aprovação diferentes")
    ax.legend()
    ax.grid(alpha=.25)
    fig.tight_layout()
    fig.savefig(out / "comparacao_bases.png", dpi=150)
    plt.close(fig)
    if not (out / "comparacao_final.csv").exists():
        return
    m = pd.read_csv(out / "comparacao_final.csv")
    d = pd.read_csv(out / "previsoes_teste.csv", parse_dates=["timestamp"])
    escolhido = json.loads((out / "decisao_validacao.json").read_text(encoding="utf-8"))["escolhido"]["modelo"]
    t = d.set_index("timestamp").reindex(pd.date_range("2025-11-01", "2025-12-31"))
    fig, ax = plt.subplots(figsize=(15, 5))
    curvas = [("referencia_diaria_kw", "Referência pelos contadores"), ("persistencia", "Persistência"),
              ("zero_shot_univariado", "Chronos zero-shot"), (escolhido, f"Escolha na validação: {escolhido}")]
    for nome, rotulo in dict(curvas).items():
        ax.plot(t.index, t[nome]*24, ".-", ms=4, lw=1, label=rotulo)
    ax.set(ylabel="Energia (kWh/dia)", title=f"Teste: {len(d)} alvos comuns, previsão do dia seguinte", xlabel="Data")
    ax.legend()
    ax.grid(alpha=.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out / "previsoes_diarias.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(17, 6))
    for ax, metrica in zip(axes, ["MAE_kW", "RMSE_kW"]):
        ax.barh(m.modelo, m[metrica], color=["#dc902d" if s else "#4185ad" for s in m.escolhido_validacao_chronos])
        ax.invert_yaxis()
        ax.set_xlabel(metrica.replace("_", " "))
        ax.grid(axis="x", alpha=.25)
    fig.suptitle(f"Base reconstruída pelos contadores: mesmos {len(d)} alvos de teste")
    fig.tight_layout()
    fig.savefig(out / "comparacao_diaria.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    for c in dados["cfg"]["cenarios"]:
        h = pd.DataFrame(json.loads((dados["pasta"] / "modelos" / c["nome"] / "historico.json").read_text()))
        for ax, coluna in zip(axes, ["loss", "eval_loss"]):
            v = h.dropna(subset=[coluna])
            ax.plot(v.passo, v[coluna], ".-", label=c["nome"])
            ax.set(xlabel="Passo", ylabel=coluna)
            ax.grid(alpha=.25)
    axes[1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "curvas_lora_diario.png", dpi=150)
    plt.close(fig)
