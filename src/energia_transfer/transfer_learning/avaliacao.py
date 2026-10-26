"""Avaliação posterior à decisão, nos mesmos dias brasileiros para todos."""

import json

import numpy as np
import pandas as pd
import torch

from ..deep_learning.dados import sha256
from .dados import carregar, particao
from .treinamento import erros, prever, restaurar


ROTULOS = {"sem_ajuste": "Sem ajuste", "cabeca": "Só saída", "completo": "Ajuste completo", "local": "Treino local"}


def avaliar(pasta=None):
    pasta, cfg, contrato = carregar(pasta)
    torch.set_num_threads(cfg["treinamento"]["threads_cpu"])
    decisao = json.loads((pasta / "resultados/decisao_validacao.json").read_text(encoding="utf-8"))
    if decisao["contrato_sha256"] != sha256(pasta / "dados/contrato.json"):
        raise ValueError("Decisão pertence a outro contrato; refaça a adaptação.")
    for arquivo, esperado in decisao["checkpoints_sha256"].items():
        if sha256(pasta / arquivo) != esperado:
            raise ValueError("Modelo mudou após a decisão; refaça a adaptação.")
    resultados, previsoes, sensibilidade = [], [], []
    referencia = None
    cap = cfg["capacidade_ac_kw"]["brasil"]
    for lag in cfg["lags"]:
        dados = particao(pasta, "brasil", lag, "teste")
        if referencia is None:
            referencia = dados
        else:
            np.testing.assert_array_equal(dados["datas"], referencia["datas"])
            np.testing.assert_array_equal(dados["y_original"], referencia["y_original"])
        for arquitetura in cfg["arquiteturas"]:
            for seed in cfg["seeds"]:
                for metodo in cfg["metodos"]:
                    modelo = restaurar(pasta, cfg, contrato, arquitetura, lag, seed, metodo)
                    pred = prever(modelo, dados, contrato)
                    chave = {"arquitetura": arquitetura, "lag": lag, "seed": seed, "metodo": metodo}
                    m = erros(dados["y_original"], pred, dados["persistencia"])
                    resultados.append({**chave, **m, "MAE_kw": m["MAE_pu"] * cap,
                                       "RMSE_kw": m["RMSE_pu"] * cap, "nRMSE_capacidade_pct": m["RMSE_pu"] * 100})
                    previsoes.append(pd.DataFrame({**chave, "timestamp": dados["datas"], "real_kw": dados["y_original"] * cap,
                                                   "previsto_kw": pred * cap, "persistencia_kw": dados["persistencia"] * cap,
                                                   "fracao_alvo_estimada_pct": dados["fracao_alvo_estimada_pct"],
                                                   "cobertura_alvo_original_pct": dados["cobertura_alvo_original_pct"]}))
                    # Compatibilidade com a auditoria diária histórica.
                    mask = dados["cobertura_alvo_original_pct"] >= 95
                    if mask.sum() >= 2:
                        sensibilidade.append({**chave, **erros(dados["y_original"][mask], pred[mask], dados["persistencia"][mask])})
    resultados = pd.DataFrame(resultados)
    resumo = resultados.groupby(["arquitetura", "lag", "metodo"]).agg(
        n=("n", "first"), sementes=("seed", "nunique"), MAE_kw_medio=("MAE_kw", "mean"),
        RMSE_kw_medio=("RMSE_kw", "mean"), RMSE_kw_dp=("RMSE_kw", "std"),
        nRMSE_capacidade_pct=("nRMSE_capacidade_pct", "mean"),
        R2_medio=("R2", "mean"), skill_persistencia_pct=("skill_persistencia_pct", "mean")).reset_index()
    base = erros(referencia["y_original"], referencia["persistencia"], referencia["persistencia"])
    resumo = pd.concat([resumo, pd.DataFrame([{"arquitetura": "persistencia", "lag": 0, "metodo": "persistencia",
                                              "n": base["n"], "sementes": 0, "MAE_kw_medio": base["MAE_pu"] * cap,
                                              "RMSE_kw_medio": base["RMSE_pu"] * cap, "RMSE_kw_dp": np.nan,
                                              "nRMSE_capacidade_pct": base["RMSE_pu"] * 100, "R2_medio": base["R2"],
                                              "skill_persistencia_pct": 0.}])], ignore_index=True)
    pares = resultados.pivot(index=["arquitetura", "lag", "seed"], columns="metodo", values="RMSE_kw").reset_index()
    for metodo in ["cabeca", "completo", "sem_ajuste"]:
        pares[f"ganho_{metodo}_sobre_local_pct"] = 100 * (1 - pares[metodo] / pares.local)
    previsoes = pd.concat(previsoes, ignore_index=True)
    resultados.to_csv(pasta / "resultados/teste_metricas_por_seed.csv", index=False)
    resumo.to_csv(pasta / "resultados/teste_resumo.csv", index=False)
    pares.to_csv(pasta / "resultados/teste_pares_com_local.csv", index=False)
    previsoes.to_csv(pasta / "resultados/teste_previsoes.csv", index=False)
    pd.DataFrame(sensibilidade).to_csv(pasta / "resultados/teste_cobertura_original_95.csv", index=False)
    # A linha destacada é escolhida pela validação; não se reordena pelo teste.
    escolhido = decisao["melhor_rede_validacao"]
    linha = resumo.loc[(resumo.arquitetura == escolhido["arquitetura"]) &
                       (resumo.lag == escolhido["lag"]) & (resumo.metodo == escolhido["metodo"])].iloc[0]
    local = resumo.loc[(resumo.arquitetura == escolhido["arquitetura"]) &
                       (resumo.lag == escolhido["lag"]) & resumo.metodo.eq("local")].iloc[0]
    qualidade = {"alvos": len(referencia["datas"]), "primeiro": referencia["datas"][0], "ultimo": referencia["datas"][-1],
                 "alvos_cobertura_original_95": int((referencia["cobertura_alvo_original_pct"] >= 95).sum()),
                 "fracao_diurna_estimada_media_pct": float(referencia["fracao_alvo_estimada_pct"].mean()),
                 "fracao_diurna_estimada_max_pct": float(referencia["fracao_alvo_estimada_pct"].max()),
                 "nota": "São alvos tratados com cobertura controlada, não alvos integralmente medidos. Não se preencheram dias inteiros."}
    relatorio = {"escolha_validacao": escolhido, "teste_da_escolha_validacao": linha.to_dict(),
                 "controle_local_equivalente": local.to_dict(),
                 "ganho_RMSE_sobre_local_pct": 100 * (1 - linha.RMSE_kw_medio / local.RMSE_kw_medio),
                 "persistencia_RMSE_kw": base["RMSE_pu"] * cap, "qualidade_alvos": qualidade,
                 "teste_mudou_escolha": False, "media_metricas_nao_ensemble": True,
                 "limitacoes": [cfg["escopo"], "Um ano e uma usina de destino; poucos alvos, sem alegação de significância estatística",
                                  "A variabilidade entre sementes não é intervalo de confiança temporal",
                                  "Unidades, capacidade instalada e associação da fonte seguem fontes_e_hipoteses.json",
                                  "Médias diárias com cobertura parcial residual; clima de sensores versus reanálise",
                                  "Candidatos selecionados em validação pequena; ranking pode ser instável"]}
    if cfg.get("resolucao")=="5min":
        relatorio["conclusao_transferencia"] = (
            "A validação favoreceu pesos treinados localmente. Não foi demonstrado benefício da transferência neste protocolo."
            if escolhido["metodo"]=="local" else
            "A validação favoreceu um modelo com pesos fonte; o ganho frente ao controle equivalente deve ser avaliado no teste.")
        relatorio["persistencia_MAE_kw"] = base["MAE_pu"]*cap
        relatorio["qualidade_alvos"]["nota"]="Todos os alvos e persistências são medições originais; imputação somente no histórico. Avaliação principal diurna."
        relatorio["limitacoes"]=["Previsão t+5 minutos; avaliação principal diurna, sem zeros noturnos inflando a métrica.",
             "Janelas sobrepostas e erros autocorrelacionados; sementes não são intervalos de confiança temporal.",
             "Dados horários ERA5 apenas auxiliares, fora dos inputs principais.",
             "Treino fonte usa uma de cada 12 janelas válidas por custo de CPU; validação e teste mantêm todos os alvos elegíveis.",
             "Capacidades AC instaladas não representam capacidade operacional efetiva diária; falhas e mudanças DKA documentadas."]
        complemento=[]
        d24=particao(pasta,"brasil",int(escolhido["lag"]),"teste_24h")
        for seed in cfg["seeds"]:
            mod=restaurar(pasta,cfg,contrato,escolhido["arquitetura"],int(escolhido["lag"]),seed,escolhido["metodo"])
            p24=prever(mod,d24,contrato)
            complemento.append({"seed":seed,**erros(d24["y_original"],p24,d24["persistencia"])})
        pd.DataFrame(complemento).to_csv(pasta/"resultados/teste_24h_complementar.csv",index=False)
        relatorio["avaliacao_24h_complementar"]={"n":len(d24["datas"]),"RMSE_kw_medio":float(pd.DataFrame(complemento).RMSE_pu.mean()*cap)}
    (pasta / "resultados/relatorio_final.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _graficos(pasta, resumo, previsoes, escolhido, base["RMSE_pu"] * cap)
    _relatorio_md(pasta, resumo, relatorio)
    return {"resumo": resumo, "pares": pares, "relatorio": relatorio}


def _graficos(pasta, resumo, previsoes, escolhido, persistencia):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(13, 6))
    tabela = resumo.loc[resumo.arquitetura.eq(escolhido["arquitetura"]) & resumo.lag.eq(escolhido["lag"])].set_index("metodo").reindex(ROTULOS)
    x = np.arange(len(tabela))
    ax.bar(x, tabela.RMSE_kw_medio, yerr=tabela.RMSE_kw_dp, capsize=5, color=["#8e9baa", "#3e8a62", "#527fb7", "#d58c45"])
    ax.set_xticks(x, [ROTULOS[m] for m in tabela.index])
    ax.axhline(persistencia, linestyle="--", color="#a04747", label="Persistência")
    _,cfg,_=carregar(pasta)
    historico=f"{escolhido['lag']*5} minutos" if cfg.get("resolucao")=="5min" else f"{escolhido['lag']} dias"
    ax.set(ylabel="RMSE (kW) — menor é melhor", title=f"Brasil — {escolhido['arquitetura']}, histórico {historico}, escolhido na validação")
    ax.text(.01, .98, "Média de cinco sementes; barras de erro: desvio padrão entre sementes, sem intervalo de confiança", transform=ax.transAxes, va="top", fontsize=8)
    ax.legend(loc="lower right")
    ax.grid(axis="y", alpha=.2)
    fig.tight_layout()
    fig.savefig(pasta / "figuras/comparacao_transferencia.png", dpi=145)
    plt.close(fig)
    # A semente ilustrativa é fixada em 42; não se escolhe o melhor teste.
    dados = previsoes.loc[previsoes.arquitetura.eq(escolhido["arquitetura"]) & previsoes.lag.eq(escolhido["lag"]) & previsoes.seed.eq(42)].copy()
    dados.timestamp = pd.to_datetime(dados.timestamp)
    if cfg.get("resolucao")=="5min":
        # Cinco dias iniciais ilustrativos, sem escolher o trecho por erro.
        dados=dados.loc[dados.timestamp.lt(dados.timestamp.min().normalize()+pd.Timedelta(days=5))]
    calendario = pd.date_range(dados.timestamp.min(), dados.timestamp.max(),freq="5min" if cfg.get("resolucao")=="5min" else "D")
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    base = dados.loc[dados.metodo.eq("local")].set_index("timestamp").reindex(calendario)
    axes[0].plot(calendario, base.real_kw, "o-", color="#222222", markersize=4,
                 label="Medido — oito inversores" if cfg.get("resolucao")=="5min" else "Alvo tratado")
    axes[0].plot(calendario, base.persistencia_kw, "--", color="#a04747", label="Persistência")
    for metodo in ["local", "cabeca", "completo"]:
        curva = dados.loc[dados.metodo.eq(metodo)].set_index("timestamp").reindex(calendario)
        axes[0].plot(calendario, curva.previsto_kw, ".-", label=ROTULOS[metodo])
    axes[0].set(title="Teste brasileiro — lacunas mantidas, semente 42 ilustrativa", ylabel="Potência (kW)")
    axes[0].legend(ncol=3, fontsize=8)
    if cfg.get("resolucao")=="5min":
        axes[1].plot(base.index,base.previsto_kw-base.real_kw,color="#527fb7",label="Erro do controle local")
        axes[1].axhline(0,color="#777777",linewidth=.7)
        axes[1].set(ylabel="Erro (kW)",title="Alvos e persistência originalmente medidos; nenhuma imputação do alvo")
    else:
        axes[1].bar(base.index, base.fracao_alvo_estimada_pct, color="#777777", width=.8)
        axes[1].set(ylabel="Fração diurna estimada (%)", title="Qualidade dos alvos avaliados — sem completar dias inteiros")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(pasta / "figuras/previsoes_brasil.png", dpi=145)
    plt.close(fig)


def _relatorio_md(pasta, resumo, relatorio):
    escolhido = relatorio["escolha_validacao"]
    linhas = ["# Transferência Austrália → Brasil — resultado", "",
              f"Escolha pela validação: **{escolhido['arquitetura']}**, lag **{escolhido['lag']}**, método **{escolhido['metodo']}**.",
              "A seleção considera médias de cinco sementes. O teste não muda a escolha; persistência pode ser a melhor opção operacional.", "",
              f"A rede escolhida teve redução de {relatorio['ganho_RMSE_sobre_local_pct']:.2f}% no RMSE médio frente ao controle local da mesma arquitetura e lag. Valores negativos significam transferência pior que esse controle.",
              f"R² médio dessa rede no teste: {relatorio['teste_da_escolha_validacao']['R2_medio']:.3f}. R² negativo indica erro quadrático maior que a referência descritiva da média dos alvos do próprio teste; essa média não é uma previsão disponível antecipadamente.",
              "Não se troca a escolha por outra configuração que apareça melhor no teste. Ganho frente à persistência não demonstra por si só grande capacidade de generalização.", "",
              "| Arquitetura | Lag | Método | MAE médio (kW) | RMSE médio (kW) | DP RMSE entre sementes | R² médio | Skill persistência (%) |",
              "|---|---:|---|---:|---:|---:|---:|---:|"]
    if "conclusao_transferencia" in relatorio:
        linhas[4:4]=[relatorio["conclusao_transferencia"],
            f"MAE da persistência: {relatorio['persistencia_MAE_kw']:.3f} kW; MAE da rede escolhida: {relatorio['teste_da_escolha_validacao']['MAE_kw_medio']:.3f} kW. A redução de RMSE não implica melhora em todas as métricas.",""]
    for r in resumo.itertuples():
        linhas.append(f"| {r.arquitetura} | {r.lag} | {r.metodo} | {r.MAE_kw_medio:.3f} | {r.RMSE_kw_medio:.3f} | {r.RMSE_kw_dp:.3f} | {r.R2_medio:.3f} | {r.skill_persistencia_pct:.2f} |")
    q = relatorio["qualidade_alvos"]
    linhas += ["", f"Teste: {q['alvos']} alvos de {q['primeiro']} a {q['ultimo']}, iguais para todos os métodos e lags.",
               f"Fração diurna estimada média: {q['fracao_diurna_estimada_media_pct']:.2f}%; máxima: {q['fracao_diurna_estimada_max_pct']:.2f}%.",
               "", "![Comparação](../figuras/comparacao_transferencia.png)", "", "![Previsões](../figuras/previsoes_brasil.png)", "",
               "## Limitações", ""]
    linhas += [f"- {s}" for s in relatorio["limitacoes"]]
    if "avaliacao_24h_complementar" in relatorio:
        linhas += ["",f"Avaliação complementar incluindo noite: {relatorio['avaliacao_24h_complementar']}. Não confundir com o teste diurno principal."]
    linhas += ["", "Treinos locais usam o mesmo contrato de normalização aprendido na fonte; diferem na inicialização dos pesos. Isso isola a transferência de pesos, sem oferecer ao controle um processamento incompatível.",
               "Resultados da média das métricas de redes individuais; não são métricas de um ensemble. Ganho negativo indica pior desempenho que a referência.", ""]
    (pasta / "resultados/relatorio.md").write_text("\n".join(linhas), encoding="utf-8")
