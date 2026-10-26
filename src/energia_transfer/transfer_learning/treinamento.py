"""Pré-treino e adaptação recebem somente treino/validação; teste separado."""

import copy
import json
import random

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ..deep_learning.dados import sha256
from ..deep_learning.modelos import MLP, MLPResidual, LSTM
from .dados import carregar, particao


def construir(arquitetura, lag, contrato, config):
    n = len(contrato["variaveis_por_passo"])
    if arquitetura == "mlp_direta":
        return MLP(lag, n, config["mlp_unidades"])
    if arquitetura == "mlp_residual":
        return MLPResidual(dict(contrato, lookback=lag), config["mlp_unidades"])
    if arquitetura == "lstm_direta":
        return LSTM(n, config["lstm_unidades"])
    raise ValueError("Arquitetura desconhecida.")


def prever(modelo, dados, contrato):
    modelo.eval()
    with torch.no_grad():
        z = np.concatenate([modelo(torch.from_numpy(dados["X"][i:i+2048])).numpy()
                            for i in range(0,len(dados["X"]),2048)])
    return (z * contrato["y_escala_treino"] + contrato["y_media_treino"]).clip(0)


def erros(real, previsto, persistencia):
    real, previsto, persistencia = [np.asarray(v, dtype=float) for v in [real, previsto, persistencia]]
    e = previsto - real
    rmse = float(np.sqrt(np.mean(e ** 2)))
    ref = float(np.sqrt(np.mean((persistencia - real) ** 2)))
    total = float(np.sum((real - real.mean()) ** 2))
    return {"n": len(real), "MAE_pu": float(np.abs(e).mean()), "RMSE_pu": rmse,
            "R2": 1 - float(np.sum(e ** 2)) / total if total else np.nan,
            "vies_pu": float(e.mean()), "skill_persistencia_pct": 100 * (1 - rmse / ref) if ref else np.nan}


def ajustar(modelo, treino, validacao, seed, lr, batch, epocas, paciencia, config):
    """Não recebe nem consulta dados de teste. Preserva flags requires_grad."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    for dados in [treino, validacao]:
        if not np.isfinite(dados["X"]).all() or not np.isfinite(dados["y"]).all():
            raise ValueError("Treino e validação precisam ser finitos.")
    lotes = DataLoader(TensorDataset(torch.from_numpy(treino["X"]), torch.from_numpy(treino["y"])),
                       batch_size=batch, shuffle=True, generator=torch.Generator().manual_seed(seed))
    opt = torch.optim.AdamW([p for p in modelo.parameters() if p.requires_grad], lr=lr,
                            weight_decay=config["weight_decay"])
    perda = nn.MSELoss()
    xv, yv = torch.from_numpy(validacao["X"]), torch.from_numpy(validacao["y"])
    melhor, melhor_epoca, esperas, estado = float("inf"), 0, 0, None
    historico = []
    for epoca in range(1, epocas + 1):
        modelo.train()
        acumulada = 0.
        for x, y in lotes:
            opt.zero_grad(set_to_none=True)
            loss = perda(modelo(x), y)
            loss.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), 1.)
            opt.step()
            acumulada += loss.item() * len(y)
        modelo.eval()
        with torch.no_grad():
            val = sum(float(perda(modelo(xv[i:i+2048]), yv[i:i+2048]).item()) * len(yv[i:i+2048])
                      for i in range(0,len(yv),2048))/len(yv)
        historico.append({"epoca": epoca, "MSE_treino": acumulada / len(treino["y"]), "MSE_validacao": val})
        if val < melhor - config["melhoria_minima"]:
            melhor, melhor_epoca, esperas = val, epoca, 0
            estado = copy.deepcopy(modelo.state_dict())
        else:
            esperas += 1
        if esperas >= paciencia:
            break
    if estado is None:
        raise RuntimeError("Não foi aprendido um estado válido.")
    modelo.load_state_dict(estado)
    return modelo.eval(), historico, melhor_epoca


def caminho_modelo(pasta, arquitetura, lag, seed, metodo="fonte"):
    diretorio = "fonte" if metodo == "fonte" else "brasil"
    return pasta / "modelos" / diretorio / f"{arquitetura}_lag{lag}_seed{seed}_{metodo}.pt"


def salvar(modelo, arquivo, pasta, arquitetura, lag, seed, metodo, epoca, origem=None):
    torch.save({"state_dict": modelo.state_dict(), "arquitetura": arquitetura, "lag": lag, "seed": seed,
                "metodo": metodo, "melhor_epoca": epoca, "contrato_sha256": sha256(pasta / "dados/contrato.json"),
                "checkpoint_fonte_sha256": sha256(origem) if origem else None,
                "torch_version": str(torch.__version__)}, arquivo)


def restaurar(pasta, cfg, contrato, arquitetura, lag, seed, metodo="fonte"):
    arquivo = caminho_modelo(pasta, arquitetura, lag, seed, metodo)
    ck = torch.load(arquivo, map_location="cpu", weights_only=True)
    if ck["contrato_sha256"] != sha256(pasta / "dados/contrato.json"):
        raise ValueError("Checkpoint incompatível com o contrato atual; refaça os treinos.")
    if metodo not in ["fonte", "local"]:
        if ck["checkpoint_fonte_sha256"] != sha256(caminho_modelo(pasta, arquitetura, lag, seed)):
            raise ValueError("Pré-treino mudou; refaça a adaptação.")
    modelo = construir(arquitetura, lag, contrato, cfg["treinamento"])
    modelo.load_state_dict(ck["state_dict"])
    return modelo.eval()


def _ambiente(cfg):
    torch.set_num_threads(cfg["treinamento"]["threads_cpu"])
    torch.use_deterministic_algorithms(True)


def pretreinar(pasta=None):
    pasta, cfg, contrato = carregar(pasta)
    _ambiente(cfg)
    t = cfg["treinamento"]
    resultados, historicos, treinos = [], [], []
    for lag in cfg["lags"]:
        treino, va = [particao(pasta, "australia", lag, p) for p in ["treino", "validacao"]]
        for arquitetura in cfg["arquiteturas"]:
            for seed in cfg["seeds"]:
                torch.manual_seed(seed)
                modelo = construir(arquitetura, lag, contrato, t)
                modelo, hist, epoca = ajustar(modelo, treino, va, seed, t["lr_fonte"], t["batch_fonte"],
                                              t["epocas_fonte"], t["paciencia_fonte"], t)
                chave = {"arquitetura": arquitetura, "lag": lag, "seed": seed}
                salvar(modelo, caminho_modelo(pasta, arquitetura, lag, seed), pasta, arquitetura, lag, seed, "fonte", epoca)
                for nome, dados in [("treino", treino), ("validacao", va)]:
                    resultados.append({**chave, "particao": nome, **erros(dados["y_original"], prever(modelo, dados, contrato), dados["persistencia"])})
                historicos.extend({**chave, **h} for h in hist)
                treinos.append({**chave, "melhor_epoca": epoca, "epocas": len(hist),
                                "parametros": sum(p.numel() for p in modelo.parameters())})
                print(f"Fonte: {arquitetura}, L={lag}, seed={seed}, época {epoca}", flush=True)
    resultado = pd.DataFrame(resultados)
    resultado.to_csv(pasta / "resultados/pretreino_metricas.csv", index=False)
    pd.DataFrame(historicos).to_csv(pasta / "resultados/pretreino_historicos.csv", index=False)
    pd.DataFrame(treinos).to_csv(pasta / "resultados/pretreino_execucoes.csv", index=False)
    return resultado


def adaptar(pasta=None):
    pasta, cfg, contrato = carregar(pasta)
    _ambiente(cfg)
    t = cfg["treinamento"]
    resultados, historicos, treinos, manifest = [], [], [], {}
    for lag in cfg["lags"]:
        treino, va = [particao(pasta, "brasil", lag, p) for p in ["treino", "validacao"]]
        for arquitetura in cfg["arquiteturas"]:
            for seed in cfg["seeds"]:
                fonte = restaurar(pasta, cfg, contrato, arquitetura, lag, seed)
                origem = caminho_modelo(pasta, arquitetura, lag, seed)
                for metodo in cfg["metodos"]:
                    torch.manual_seed(seed)
                    modelo = construir(arquitetura, lag, contrato, t) if metodo == "local" else copy.deepcopy(fonte)
                    if metodo == "cabeca":
                        for p in modelo.encoder.parameters():
                            p.requires_grad = False
                    hist, epoca = [], 0
                    if metodo != "sem_ajuste":
                        modelo, hist, epoca = ajustar(modelo, treino, va, seed, t[f"lr_{metodo}"], t["batch_brasil"],
                                                      t["epocas_brasil"], t["paciencia_brasil"], t)
                    encoder_igual = all(torch.equal(p, fonte.encoder.state_dict()[k]) for k, p in modelo.encoder.state_dict().items())
                    if metodo in ["cabeca", "sem_ajuste"] and not encoder_igual:
                        raise AssertionError("Camadas congeladas foram alteradas.")
                    chave = {"arquitetura": arquitetura, "lag": lag, "seed": seed, "metodo": metodo}
                    arquivo = caminho_modelo(pasta, arquitetura, lag, seed, metodo)
                    salvar(modelo, arquivo, pasta, arquitetura, lag, seed, metodo, epoca, origem if metodo != "local" else None)
                    manifest[str(arquivo.relative_to(pasta))] = sha256(arquivo)
                    for nome, dados in [("treino", treino), ("validacao", va)]:
                        resultados.append({**chave, "particao": nome, **erros(dados["y_original"], prever(modelo, dados, contrato), dados["persistencia"])})
                    historicos.extend({**chave, **h} for h in hist)
                    treinos.append({**chave, "melhor_epoca": epoca, "epocas": len(hist), "encoder_igual_fonte": encoder_igual,
                                    "parametros_treinaveis": sum(p.numel() for p in modelo.parameters() if p.requires_grad) if metodo != "sem_ajuste" else 0})
                print(f"Brasil: {arquitetura}, L={lag}, seed={seed}; quatro estratégias concluídas", flush=True)
    resultados = pd.DataFrame(resultados)
    validacao = resultados.loc[resultados.particao.eq("validacao")].groupby(["arquitetura", "lag", "metodo"]).agg(
        RMSE_medio=("RMSE_pu", "mean"), RMSE_dp=("RMSE_pu", "std"), MAE_medio=("MAE_pu", "mean"), sementes=("seed", "nunique")).reset_index()
    va = particao(pasta, "brasil", cfg["lags"][0], "validacao")
    persistencia = erros(va["y_original"], va["persistencia"], va["persistencia"])
    melhor = validacao.sort_values(["RMSE_medio", "arquitetura", "lag", "metodo"]).iloc[0]
    transferencia = validacao.loc[validacao.metodo.isin(["cabeca", "completo"])].sort_values("RMSE_medio").iloc[0]
    decisao = {"criterio": "Menor RMSE médio de cinco sementes na mesma coorte de validação brasileira, sem escolher semente.",
               "melhor_rede_validacao": melhor.to_dict(), "melhor_transferencia_validacao": transferencia.to_dict(),
               "RMSE_persistencia_validacao": persistencia["RMSE_pu"],
               "melhor_incluindo_persistencia": "persistencia" if persistencia["RMSE_pu"] <= melhor.RMSE_medio else "rede",
               "teste_usado_na_selecao": False, "contrato_sha256": sha256(pasta / "dados/contrato.json"),
               "checkpoints_sha256": manifest,
               "limite": "Poucos alvos de validação, configurações correlacionadas e somente um ano brasileiro; ranking exploratório."}
    (pasta / "resultados/decisao_validacao.json").write_text(json.dumps(decisao, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    resultados.to_csv(pasta / "resultados/brasil_metricas_desenvolvimento.csv", index=False)
    validacao.to_csv(pasta / "resultados/brasil_ranking_validacao.csv", index=False)
    pd.DataFrame(historicos).to_csv(pasta / "resultados/brasil_historicos.csv", index=False)
    pd.DataFrame(treinos).to_csv(pasta / "resultados/brasil_execucoes.csv", index=False)
    return {"validacao": validacao, "decisao": decisao}
