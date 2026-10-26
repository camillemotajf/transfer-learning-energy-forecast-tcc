"""Experimento pareado: MLP direta versus correção da persistência.

Mantém as entradas, partições, arquitetura e treino do experimento original.
Somente o caminho direto da última potência para a saída muda entre os pares.
"""

import copy
import json
import random

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .dados import carregar_config, garantir_dados, sha256
from .modelos import MLP, MLPResidual
from .treinamento import carregar_particoes, metricas


NOMES = {"direta": "MLP direta", "residual": "MLP + persistência"}


def _modelo(formulacao, contrato, config):
    if formulacao == "direta":
        return MLP(contrato["lookback"], len(contrato["variaveis_por_passo"]), config["mlp_unidades"])
    if formulacao == "residual":
        return MLPResidual(contrato, config["mlp_unidades"])
    raise ValueError("Formulação deve ser direta ou residual.")


def _ajustar(formulacao, seed, contrato, config, treino, validacao):
    # Este ajuste não recebe a partição de teste.
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    lotes = DataLoader(TensorDataset(torch.from_numpy(treino["X"]), torch.from_numpy(treino["y"])),
                       batch_size=config["batch_size"], shuffle=True,
                       generator=torch.Generator().manual_seed(seed), num_workers=0)
    modelo = _modelo(formulacao, contrato, config)
    otimizador = torch.optim.AdamW(modelo.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    perda = nn.MSELoss()
    x_va, y_va = torch.from_numpy(validacao["X"]), torch.from_numpy(validacao["y"])
    melhor, melhor_epoca, esperas, estado = float("inf"), 0, 0, None
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
            acumulada += erro.item() * len(y)
        modelo.eval()
        with torch.no_grad():
            erro_va = float(perda(modelo(x_va), y_va).item())
        historico.append({"formulacao": formulacao, "seed": seed, "epoca": epoca,
                          "MSE_treino_padronizado": acumulada / len(treino["y"]),
                          "MSE_validacao_padronizado": erro_va})
        if erro_va < melhor - config["melhoria_minima"]:
            melhor, melhor_epoca, esperas = erro_va, epoca, 0
            estado = copy.deepcopy(modelo.state_dict())
        else:
            esperas += 1
        if esperas >= config["paciencia"]:
            break
    if estado is None:
        raise RuntimeError("Nenhum checkpoint válido.")
    modelo.load_state_dict(estado)
    modelo.eval()
    return modelo, historico, melhor_epoca


def _prever(modelo, dados, contrato):
    with torch.no_grad():
        z = modelo(torch.from_numpy(dados["X"])).numpy()
    return (z * contrato["y_escala_treino"] + contrato["y_media_treino"]).clip(0)


def executar_correcao(pasta=None):
    pasta, contrato = garantir_dados(pasta)
    config = carregar_config(pasta)["treinamento"]
    arquivo_config = pasta / "config_correcao_persistencia.json"
    experimento = json.loads(arquivo_config.read_text(encoding="utf-8"))
    if experimento["formulacoes"] != ["direta", "residual"]:
        raise ValueError("Esperadas as duas formulações na ordem direta, residual.")
    seeds = experimento["seeds"]
    if not seeds or len(seeds) != len(set(seeds)):
        raise ValueError("Sementes precisam ser distintas e não vazias.")
    torch.set_num_threads(config["threads_cpu"])
    torch.use_deterministic_algorithms(True)
    particoes = carregar_particoes(pasta)
    indice = contrato["variaveis_por_passo"].index("Active_Power")
    for dados in particoes.values():
        if not all(np.isfinite(dados[k]).all() for k in ["X", "y", "y_original", "persistencia"]):
            raise ValueError("Tensores devem ser finitos.")
        # Confere unidades e ordem temporal: o último passo é a persistência.
        ultima = dados["X"][:, -1, indice] * contrato["x_escala_treino"][indice] + contrato["x_media_treino"][indice]
        np.testing.assert_allclose(ultima, dados["persistencia"], atol=2e-6, rtol=1e-6)
    saida = pasta / "resultados/correcao_persistencia"
    modelos = pasta / "modelos/correcao_persistencia"
    saida.mkdir(parents=True, exist_ok=True)
    modelos.mkdir(parents=True, exist_ok=True)
    hashes = {"contrato_sha256": sha256(pasta / "dados/contrato_inputs.json"),
              "config_experimento_sha256": sha256(arquivo_config),
              "particoes_sha256": {p: sha256(pasta / "dados" / f"{p}.npz") for p in particoes}}
    resultados, historicos, metadados = [], [], []
    # Primeiro ajusta todos os modelos, sem usar teste na parada antecipada.
    for seed in seeds:
        for formulacao in experimento["formulacoes"]:
            modelo, historico, epoca = _ajustar(formulacao, seed, contrato, config,
                                               particoes["treino"], particoes["validacao"])
            checkpoint = {"formulacao": formulacao, "seed": seed, "contrato": contrato,
                          "config_modelo": config, "state_dict": modelo.state_dict(),
                          "melhor_epoca": epoca, "torch_version": str(torch.__version__), **hashes}
            torch.save(checkpoint, modelos / f"mlp_{formulacao}_seed_{seed}.pt")
            historicos.extend(historico)
            metadados.append({"formulacao": formulacao, "seed": seed, "melhor_epoca": epoca,
                              "epocas_executadas": len(historico),
                              "parametros": sum(p.numel() for p in modelo.parameters())})
            for nome in ["treino", "validacao"]:
                dados = particoes[nome]
                pred = _prever(modelo, dados, contrato)
                resultados.append({"modelo": NOMES[formulacao], "formulacao": formulacao, "seed": seed,
                                   "particao": nome, **metricas(dados["y_original"], pred, dados["persistencia"])})
            print(f"MLP {formulacao}, seed {seed}: melhor época {epoca}, {len(historico)} executadas", flush=True)
    validacao = pd.DataFrame(resultados).query("particao == 'validacao'").groupby("modelo").RMSE.mean().to_dict()
    va = particoes["validacao"]
    validacao["Persistência"] = metricas(va["y_original"], va["persistencia"], va["persistencia"])["RMSE"]
    decisao = {"criterio": experimento["criterio"], "RMSE_validacao": validacao,
               "melhor_por_validacao": min(validacao, key=validacao.get),
               "seleciona_melhor_seed": False, "teste_usado_na_escolha": False,
               "avaliacao_teste": experimento["teste"], "configuracao": experimento,
               "treinamento": config, "torch_version": str(torch.__version__), **hashes}
    # Registra a decisão antes de calcular qualquer previsão de teste.
    (saida / "decisao_validacao.json").write_text(json.dumps(decisao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    previsoes = []
    for seed in seeds:
        for formulacao in experimento["formulacoes"]:
            modelo = carregar_modelo_correcao(formulacao, seed, pasta)
            for nome, dados in particoes.items():
                pred = _prever(modelo, dados, contrato)
                previsoes.append(pd.DataFrame({"timestamp": dados["datas"], "particao": nome,
                                               "formulacao": formulacao, "modelo": NOMES[formulacao], "seed": seed,
                                               "real": dados["y_original"], "previsto": pred,
                                               "persistencia": dados["persistencia"]}))
                if nome == "teste":
                    resultados.append({"modelo": NOMES[formulacao], "formulacao": formulacao, "seed": seed,
                                       "particao": nome, **metricas(dados["y_original"], pred, dados["persistencia"])})
    for nome, dados in particoes.items():
        resultados.append({"modelo": "Persistência", "formulacao": "persistencia", "seed": None,
                           "particao": nome, **metricas(dados["y_original"], dados["persistencia"], dados["persistencia"])})
    resultados = pd.DataFrame(resultados)
    previsoes = pd.concat(previsoes, ignore_index=True)
    resumo = resultados.groupby(["particao", "modelo"], sort=False).agg(
        n_amostras=("n_amostras", "first"), execucoes=("RMSE", "size"),
        MAE_medio=("MAE", "mean"), MAE_dp=("MAE", "std"),
        RMSE_medio=("RMSE", "mean"), RMSE_dp=("RMSE", "std"),
        R2_medio=("R2", "mean"), ganho_RMSE_persistencia_pct=("ganho_RMSE_persistencia_pct", "mean")).reset_index()
    pares = resultados.loc[resultados.formulacao.ne("persistencia")].pivot(index=["particao", "seed"], columns="formulacao", values="RMSE").reset_index()
    pares["ganho_residual_sobre_direta_pct"] = 100 * (1 - pares.residual / pares.direta)
    resultados.to_csv(saida / "metricas_por_seed.csv", index=False)
    resumo.to_csv(saida / "resumo_metricas.csv", index=False)
    pares.to_csv(saida / "comparacao_pareada.csv", index=False)
    previsoes.to_csv(saida / "previsoes.csv", index=False)
    pd.DataFrame(historicos).to_csv(saida / "historicos.csv", index=False)
    pd.DataFrame(metadados).to_csv(saida / "treinamentos.csv", index=False)
    _graficos(pasta, resultados, resumo, previsoes)
    return {"metricas": resultados, "resumo": resumo, "pares": pares, "previsoes": previsoes, "decisao": decisao}


def carregar_modelo_correcao(formulacao, seed, pasta=None):
    pasta, contrato = garantir_dados(pasta)
    ck = torch.load(pasta / "modelos/correcao_persistencia" / f"mlp_{formulacao}_seed_{seed}.pt",
                    map_location="cpu", weights_only=True)
    if ck["contrato_sha256"] != sha256(pasta / "dados/contrato_inputs.json"):
        raise ValueError("Checkpoint pertence a outro contrato de entradas.")
    if ck["config_experimento_sha256"] != sha256(pasta / "config_correcao_persistencia.json"):
        raise ValueError("Configuração do experimento mudou; refaça o treino.")
    for nome, esperado in ck["particoes_sha256"].items():
        if sha256(pasta / "dados" / f"{nome}.npz") != esperado:
            raise ValueError("Partições mudaram; refaça o treino.")
    modelo = _modelo(formulacao, contrato, ck["config_modelo"])
    modelo.load_state_dict(ck["state_dict"])
    return modelo.eval()


def _graficos(pasta, resultados, resumo, previsoes):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    cores = {"MLP direta": "#d57622", "MLP + persistência": "#28804c", "Persistência": "#2874a6"}
    for i, particao in enumerate(["validacao", "teste"]):
        for j, (nome, cor) in enumerate(cores.items()):
            valores = resultados.loc[resultados.particao.eq(particao) & resultados.modelo.eq(nome), "RMSE"]
            x = i * 4 + j
            axes[0].bar(x, valores.mean(), width=.65, color=cor, alpha=.7,
                        label=nome if i == 0 else None)
            axes[0].scatter(x + np.linspace(-.18, .18, len(valores)), valores, s=24, color=cor, edgecolor="black", zorder=3)
    axes[0].set_xticks([1, 5], ["Validação de 2023", "Teste de 2024–2025 (exploratório)"])
    axes[0].set(ylabel="RMSE — unidade da fonte", title="Barras: média das métricas; pontos: cada semente (sem escolher a melhor)")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=.2)
    # Mesma semente e primeiro mês completo do teste: sem escolher por desempenho.
    parte = previsoes.loc[previsoes.particao.eq("teste") & previsoes.seed.eq(42)].copy()
    parte["timestamp"] = pd.to_datetime(parte.timestamp)
    inicio = parte.timestamp.min().to_period("M").start_time
    fim = inicio + pd.offsets.MonthEnd(0)
    diario = pd.date_range(inicio, fim)
    base = parte.loc[parte.formulacao.eq("direta")].set_index("timestamp").reindex(diario)
    axes[1].plot(diario, base.real, "o-", color="#222222", markersize=3, label="Real")
    axes[1].plot(diario, base.persistencia, "--", color=cores["Persistência"], label="Persistência")
    for formulacao, nome in NOMES.items():
        curva = parte.loc[parte.formulacao.eq(formulacao)].set_index("timestamp").reindex(diario)
        axes[1].plot(diario, curva.previsto, color=cores[nome], label=nome)
    axes[1].set(ylabel="Potência — unidade da fonte", title=f"Exemplo: primeiro mês do teste ({inicio:%Y-%m}), semente 42")
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    axes[1].legend()
    axes[1].grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(pasta / "figuras/correcao_persistencia_mlp.png", dpi=145)
    plt.close(fig)
