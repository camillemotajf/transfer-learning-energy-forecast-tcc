"""Treino diário histórico; modelos genéricos reutilizados no fluxo de cinco minutos.

Execução corrente: energia_transfer.transfer_learning.treinamento.
"""

import copy
import json
import random

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .dados import carregar_config, garantir_dados, sha256
from .modelos import criar_modelo


def carregar_particoes(pasta):
    resultado = {}
    for nome in ["treino", "validacao", "teste"]:
        with np.load(pasta / "dados" / f"{nome}.npz", allow_pickle=False) as arquivo:
            resultado[nome] = dict(arquivo)
    return resultado


def metricas(real, previsto, persistencia):
    rmse = float(np.sqrt(mean_squared_error(real, previsto)))
    rmse_p = float(np.sqrt(mean_squared_error(real, persistencia)))
    return {"n_amostras": len(real), "MAE": float(mean_absolute_error(real, previsto)),
            "RMSE": rmse, "R2": float(r2_score(real, previsto)),
            "RMSE_persistencia": rmse_p, "ganho_RMSE_persistencia_pct": 100 * (1 - rmse / rmse_p) if rmse_p > 0 else None}


def treinar(tipo, pasta=None):
    pasta, contrato = garantir_dados(pasta)
    config = carregar_config(pasta)["treinamento"]
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config["threads_cpu"])
    torch.use_deterministic_algorithms(True)
    particoes = carregar_particoes(pasta)
    for item in particoes.values():
        if not np.isfinite(item["X"]).all() or not np.isfinite(item["y"]).all():
            raise ValueError("O treinamento não aceita NaN/inf nos tensores.")
    treino, validacao = particoes["treino"], particoes["validacao"]
    x_tr, y_tr = torch.from_numpy(treino["X"]), torch.from_numpy(treino["y"])
    x_va, y_va = torch.from_numpy(validacao["X"]), torch.from_numpy(validacao["y"])
    gerador = torch.Generator().manual_seed(seed)
    lotes = DataLoader(TensorDataset(x_tr, y_tr), batch_size=config["batch_size"], shuffle=True,
                       generator=gerador, num_workers=0)
    modelo = criar_modelo(tipo, contrato, config)
    otimizador = torch.optim.AdamW(modelo.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    perda = nn.MSELoss()
    melhor_perda, melhor_epoca, esperas, melhor_estado = float("inf"), 0, 0, None
    historico = []
    for epoca in range(1, config["epocas_maximas"] + 1):
        modelo.train()
        acumulada = 0.
        for x, y in lotes:
            otimizador.zero_grad(set_to_none=True)
            erro = perda(modelo(x), y)
            erro.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), max_norm=1.)
            otimizador.step()
            acumulada += float(erro.item()) * len(y)
        modelo.eval()
        with torch.no_grad():
            erro_validacao = float(perda(modelo(x_va), y_va).item())
        historico.append({"epoca": epoca, "MSE_treino_padronizado": acumulada / len(y_tr),
                          "MSE_validacao_padronizado": erro_validacao})
        if erro_validacao < melhor_perda - config["melhoria_minima"]:
            melhor_perda, melhor_epoca = erro_validacao, epoca
            melhor_estado = copy.deepcopy(modelo.state_dict())
            esperas = 0
        else:
            esperas += 1
        if epoca == 1 or epoca % 25 == 0:
            print(f"{tipo.upper()}: época {epoca}, MSE validação={erro_validacao:.5f}", flush=True)
        if esperas >= config["paciencia"]:
            break
    if melhor_estado is None:
        raise RuntimeError("Nenhum estado válido foi aprendido.")
    modelo.load_state_dict(melhor_estado)
    modelo.eval()
    torch.save({"tipo": tipo, "state_dict": melhor_estado, "contrato": contrato,
                "contrato_sha256": sha256(pasta / "dados/contrato_inputs.json"),
                "config_modelo": config, "melhor_epoca": melhor_epoca,
                "torch_version": str(torch.__version__), "estado_recorrente_persistente": False},
               pasta / "modelos" / f"{tipo}_australia.pt")
    previsoes, resultados = [], []
    with torch.no_grad():
        for particao, dados in particoes.items():
            padronizado = modelo(torch.from_numpy(dados["X"])).numpy()
            original = (padronizado * contrato["y_escala_treino"] + contrato["y_media_treino"]).clip(0)
            resultados.append({"modelo": tipo.upper(), "particao": particao,
                               **metricas(dados["y_original"], original, dados["persistencia"])})
            previsoes.append(pd.DataFrame({"timestamp": dados["datas"], "particao": particao,
                                           "real": dados["y_original"], "previsto": original,
                                           "persistencia": dados["persistencia"]}))
    previsoes = pd.concat(previsoes, ignore_index=True)
    resultados = pd.DataFrame(resultados)
    historico = pd.DataFrame(historico)
    previsoes.to_csv(pasta / "resultados" / f"previsoes_{tipo}.csv", index=False)
    resultados.to_csv(pasta / "resultados" / f"metricas_{tipo}.csv", index=False)
    historico.to_csv(pasta / "resultados" / f"historico_{tipo}.csv", index=False)
    metadados = {"modelo": tipo, "melhor_epoca": melhor_epoca, "epocas_executadas": len(historico),
                 "parametros": sum(p.numel() for p in modelo.parameters()), "seed": seed,
                 "dispositivo": "CPU", "contrato_sha256": sha256(pasta / "dados/contrato_inputs.json"),
                 "torch_version": str(torch.__version__), "teste_usado_na_selecao": False,
                 "observacao": "Parada antecipada pelo MSE padronizado da validação. Predições finais limitadas inferiormente a zero. Nenhum alvo foi imputado."}
    (pasta / "resultados" / f"treinamento_{tipo}.json").write_text(json.dumps(metadados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _grafico_treino(pasta, tipo, historico, previsoes, melhor_epoca)
    return {"metricas": resultados, "historico": historico, "previsoes": previsoes, "metadados": metadados}


def carregar_checkpoint(tipo, pasta=None):
    pasta, contrato = garantir_dados(pasta)
    checkpoint = torch.load(pasta / "modelos" / f"{tipo}_australia.pt", map_location="cpu", weights_only=True)
    if checkpoint["contrato_sha256"] != sha256(pasta / "dados/contrato_inputs.json"):
        raise ValueError("O checkpoint pertence a outro contrato de entradas. Refaça o treino.")
    modelo = criar_modelo(tipo, contrato, checkpoint["config_modelo"])
    modelo.load_state_dict(checkpoint["state_dict"])
    modelo.eval()
    return modelo, checkpoint


def comparar(pasta=None):
    pasta, contrato = garantir_dados(pasta)
    tabelas = []
    for tipo in ["mlp", "lstm"]:
        carregar_checkpoint(tipo, pasta)
        tabelas.append(pd.read_csv(pasta / "resultados" / f"metricas_{tipo}.csv"))
    resultado = pd.concat(tabelas, ignore_index=True)
    mlp = pd.read_csv(pasta / "resultados/previsoes_mlp.csv")
    lstm = pd.read_csv(pasta / "resultados/previsoes_lstm.csv")
    assert mlp[["timestamp", "particao"]].equals(lstm[["timestamp", "particao"]])
    np.testing.assert_allclose(mlp.real, lstm.real, rtol=0, atol=0)
    for particao, dados in mlp.groupby("particao"):
        resultado = pd.concat([resultado, pd.DataFrame([{"modelo": "Persistência", "particao": particao,
                                                          **metricas(dados.real, dados.persistencia, dados.persistencia)}])], ignore_index=True)
    resultado.to_csv(pasta / "resultados/comparacao_modelos.csv", index=False)
    escolha = resultado.loc[resultado.particao.eq("validacao") & resultado.modelo.ne("Persistência")].sort_values("RMSE").iloc[0].modelo
    decisao = {"candidato_transferencia_por_validacao": escolha, "criterio": "Menor RMSE da validação entre MLP e LSTM; sem escolher pelo teste",
               "nota": "Se ambas perderem para persistência, a transferência continua sendo uma hipótese a avaliar; não há ganho demonstrado.",
               "ajuste_brasil_executado": False}
    (pasta / "resultados/decisao_validacao.json").write_text(json.dumps(decisao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _grafico_comparacao(pasta, resultado, mlp, lstm)
    return resultado, decisao


def _grafico_treino(pasta, tipo, historico, previsoes, melhor_epoca):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    axes[0].plot(historico.epoca, historico.MSE_treino_padronizado, label="Treino")
    axes[0].plot(historico.epoca, historico.MSE_validacao_padronizado, label="Validação")
    axes[0].axvline(melhor_epoca, linestyle="--", color="#777777", label="Checkpoint escolhido")
    axes[0].set(xlabel="Época", ylabel="MSE padronizado", title=f"{tipo.upper()} — treino e parada antecipada cronológica")
    dados = previsoes.loc[previsoes.particao.eq("teste")].copy()
    dados.timestamp = pd.to_datetime(dados.timestamp)
    # Não desenha uma linha ligando dias separados por lacunas no teste.
    dados = dados.set_index("timestamp").reindex(pd.date_range(dados.timestamp.min(), dados.timestamp.max(), name="timestamp"))
    axes[1].plot(dados.index, dados.real, label="Real", linewidth=1)
    axes[1].plot(dados.index, dados.previsto, label=tipo.upper(), linewidth=.8)
    axes[1].plot(dados.index, dados.persistencia, label="Persistência", linewidth=.6, alpha=.5)
    axes[1].set(ylabel="Potência — unidade da fonte", title="Teste posterior — sem ajuste de pesos neste período")
    for ax in axes:
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(pasta / "figuras" / f"treino_{tipo}.png", dpi=140)
    plt.close(fig)


def _grafico_comparacao(pasta, resultados, mlp, lstm):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tabela = resultados.pivot(index="modelo", columns="particao", values="RMSE")
    ax = tabela[["treino", "validacao", "teste"]].plot.bar(figsize=(11, 5), rot=0)
    ax.set(ylabel="RMSE — unidade da fonte", title="Mesmo contrato e mesmos alvos; escolha do modelo somente na validação")
    ax.grid(axis="y", alpha=.2)
    ax.figure.tight_layout()
    ax.figure.savefig(pasta / "figuras/comparacao_modelos.png", dpi=140)
    plt.close(ax.figure)


def diagnosticar_persistencia(tipo="mlp", pasta=None):
    """Inspeção descritiva do teste; não ajusta pesos, lags ou hiperparâmetros."""
    if tipo not in ["mlp", "lstm"]:
        raise ValueError("Modelo deve ser mlp ou lstm.")
    pasta, contrato = garantir_dados(pasta)
    dados = pd.read_csv(pasta / "resultados" / f"previsoes_{tipo}.csv", parse_dates=["timestamp"])
    dados = dados.loc[dados.particao.eq("teste")].copy().sort_values("timestamp")
    if dados.empty or not dados.timestamp.is_unique:
        raise ValueError("Esperadas previsões de teste com datas únicas.")
    # Conferência independente da persistência: valor do dia civil anterior.
    from ..caminhos import CaminhosProjeto
    fonte = pd.read_csv(CaminhosProjeto().brutos_australia / "base_diaria_australia.csv", parse_dates=["timestamp"]).set_index("timestamp")
    real_fonte = fonte.Active_Power.reindex(dados.timestamp).to_numpy()
    anterior = fonte.Active_Power.reindex(dados.timestamp - pd.Timedelta(days=1)).to_numpy()
    np.testing.assert_allclose(dados.real, real_fonte, atol=1e-6, rtol=1e-6)
    np.testing.assert_allclose(dados.persistencia, anterior, atol=1e-6, rtol=1e-6)
    dados["erro_modelo"] = dados.previsto - dados.real
    dados["erro_persistencia"] = dados.persistencia - dados.real
    dados["erro_abs_modelo"] = dados.erro_modelo.abs()
    dados["erro_abs_persistencia"] = dados.erro_persistencia.abs()
    dados["vencedor_dia"] = np.select(
        [dados.erro_abs_modelo.lt(dados.erro_abs_persistencia), dados.erro_abs_modelo.gt(dados.erro_abs_persistencia)],
        [tipo.upper(), "Persistência"], default="Empate")
    mensal = []
    for mes, parte in dados.groupby(dados.timestamp.dt.to_period("M")):
        mensal.append({"mes": str(mes), "previsoes": len(parte),
                       "MAE_modelo": float(parte.erro_abs_modelo.mean()),
                       "MAE_persistencia": float(parte.erro_abs_persistencia.mean()),
                       "RMSE_modelo": float(np.sqrt((parte.erro_modelo ** 2).mean())),
                       "RMSE_persistencia": float(np.sqrt((parte.erro_persistencia ** 2).mean()))})
    mensal = pd.DataFrame(mensal)
    mensal["menor_RMSE"] = np.where(mensal.RMSE_modelo.lt(mensal.RMSE_persistencia), tipo.upper(), "Persistência")
    resumo = pd.DataFrame([
        {"metodo": nome, "previsoes": len(dados), "MAE": float(erro.abs().mean()),
         "RMSE": float(np.sqrt((erro ** 2).mean())), "erro_absoluto_mediano": float(erro.abs().median()),
         "vies_medio": float(erro.mean()), "dias_menor_erro_absoluto": int(dados.vencedor_dia.eq(nome).sum())}
        for nome, erro in [(tipo.upper(), dados.erro_modelo), ("Persistência", dados.erro_persistencia)]
    ])
    resumo.to_csv(pasta / "resultados" / f"diagnostico_persistencia_{tipo}.csv", index=False)
    mensal.to_csv(pasta / "resultados" / f"metricas_mensais_{tipo}_persistencia.csv", index=False)
    dados.to_csv(pasta / "resultados" / f"erros_diarios_{tipo}_persistencia.csv", index=False)
    _grafico_diagnostico_persistencia(pasta, tipo, dados, mensal)
    return {"resumo": resumo, "mensal": mensal, "diario": dados}


def _grafico_diagnostico_persistencia(pasta, tipo, dados, mensal):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    # Meses ilustrativos: um favorável a cada método, escolhidos após inspeção.
    # Não são usados para selecionar modelos nem substituir o teste completo.
    for ax, mes in zip(axes[0], ["2024-04", "2024-09"]):
        trecho = dados.loc[dados.timestamp.dt.strftime("%Y-%m").eq(mes)].copy()
        trecho = trecho.set_index("timestamp")
        if not trecho.empty:
            trecho = trecho.reindex(pd.date_range(trecho.index.min(), trecho.index.max()))
            ax.plot(trecho.index, trecho.real, color="#222222", marker="o", markersize=3, linewidth=1.4, label="Real")
            ax.plot(trecho.index, trecho.persistencia, color="#2874a6", linestyle="--", linewidth=1.2, label="Persistência")
            ax.plot(trecho.index, trecho.previsto, color="#d57622", marker=".", linewidth=1.1, label=tipo.upper())
        ax.set_title(f"Ampliação ilustrativa: {mes}")
        ax.set_ylabel("Potência — unidade da fonte")
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    x = np.arange(len(mensal))
    axes[1, 0].bar(x - .18, mensal.RMSE_modelo, width=.36, color="#d57622", label=tipo.upper())
    axes[1, 0].bar(x + .18, mensal.RMSE_persistencia, width=.36, color="#2874a6", label="Persistência")
    axes[1, 0].set_xticks(x, mensal.mes, rotation=90, fontsize=7)
    axes[1, 0].set(title="RMSE em todos os meses do teste", ylabel="RMSE — menor é melhor")
    axes[1, 0].legend(fontsize=8)
    axes[1, 0].grid(axis="y", alpha=.2)
    limite = max(dados.erro_abs_modelo.max(), dados.erro_abs_persistencia.max()) * 1.03
    cores = np.where(dados.erro_abs_modelo.lt(dados.erro_abs_persistencia), "#d57622", "#2874a6")
    axes[1, 1].scatter(dados.erro_abs_persistencia, dados.erro_abs_modelo, c=cores, s=12, alpha=.45)
    axes[1, 1].plot([0, limite], [0, limite], color="#555555", linestyle="--", linewidth=1)
    axes[1, 1].set(xlim=(0, limite), ylim=(0, limite), xlabel="Erro absoluto da persistência",
                   ylabel=f"Erro absoluto da {tipo.upper()}", title=f"Cada ponto é um dia; abaixo da diagonal: {tipo.upper()} melhor")
    axes[1, 1].grid(alpha=.2)
    fig.suptitle("Comparação descritiva no teste — vantagem média e diferenças entre períodos", fontsize=14)
    fig.tight_layout()
    fig.savefig(pasta / "figuras" / f"diagnostico_persistencia_{tipo}.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
