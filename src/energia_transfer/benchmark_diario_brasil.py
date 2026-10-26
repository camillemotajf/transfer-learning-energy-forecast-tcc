"""MLP/LSTM do zero, somente Brasil, na coorte diária reconstruída pelos contadores."""
import copy
import hashlib
import json
from pathlib import Path
import random
import time

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from .chronos_experimentos import execucao_exclusiva, metricas, salvar_json, sha256


class MLPDiaria(nn.Module):
    """Previsão direta com três dias achatados e calendário conhecido do alvo."""
    def __init__(self, contexto, n_features, n_futuras, unidades):
        super().__init__()
        tamanho = contexto*n_features+n_futuras
        camadas = []
        for largura in unidades:
            camadas.extend([nn.Linear(tamanho, largura), nn.ReLU()])
            tamanho = largura
        self.rede = nn.Sequential(*camadas, nn.Linear(tamanho, 1))

    def forward(self, x, futuro):
        return self.rede(torch.cat([x.flatten(start_dim=1), futuro], dim=1)).squeeze(-1)


class LSTMDiaria(nn.Module):
    """Uma camada recorrente; estado zerado em cada janela, sem carregar entre blocos."""
    def __init__(self, n_features, n_futuras, unidades):
        super().__init__()
        self.encoder = nn.LSTM(n_features, unidades, num_layers=1, batch_first=True)
        self.saida = nn.Linear(unidades+n_futuras, 1)

    def forward(self, x, futuro):
        sequencia, _ = self.encoder(x)
        return self.saida(torch.cat([sequencia[:, -1], futuro], dim=1)).squeeze(-1)


def construir(tipo, cfg):
    n, nf = len(cfg["colunas_historicas"]), len(cfg["colunas_futuras"])
    if tipo == "mlp":
        return MLPDiaria(cfg["contexto_passos"], n, nf, cfg["mlp_unidades"])
    if tipo == "lstm":
        return LSTMDiaria(n, nf, cfg["lstm_unidades"])
    raise ValueError(f"Arquitetura desconhecida: {tipo}")


def ajustar_normalizacao(treino):
    """Recebe exclusivamente o treino; nenhuma estatística da validação/teste."""
    x, y = np.asarray(treino["X"], dtype=float), np.asarray(treino["y"], dtype=float)
    assert np.isfinite(x).all() and np.isfinite(y).all()
    mu, escala = x.mean(axis=(0, 1)), x.std(axis=(0, 1))
    escala = np.where(escala > 1e-8, escala, 1.)
    escala_y = float(y.std())
    return dict(x_media=mu.tolist(), x_escala=escala.tolist(), y_media=float(y.mean()),
                y_escala=escala_y if escala_y > 1e-8 else 1.,
                ajuste_somente="brasil/treino", calendario_futuro="identidade: seno/cosseno em [-1,1]")


def transformar(j, contrato, cfg):
    cov = cfg["colunas_historicas"][1:]
    idx = [cov.index(c) for c in cfg["colunas_futuras"]]
    futuro = np.asarray(j["calendario_futuro"])[:, idx]
    x = (j["X"]-np.asarray(contrato["x_media"]))/np.asarray(contrato["x_escala"])
    y = (j["y"]-contrato["y_media"])/contrato["y_escala"]
    assert np.isfinite(x).all() and np.isfinite(y).all() and np.isfinite(futuro).all()
    return dict(X=x.astype(np.float32), futuro=futuro.astype(np.float32), y=y.astype(np.float32))


def ajustar(modelo, treino, validacao, seed, cfg):
    """A função não recebe o teste; aprende todos os pesos de uma rede nova."""
    lotes = DataLoader(TensorDataset(*[torch.from_numpy(treino[c]) for c in ["X", "futuro", "y"]]),
                       batch_size=cfg["batch_size"], shuffle=True,
                       generator=torch.Generator().manual_seed(seed), num_workers=0)
    xv, fv, yv = [torch.from_numpy(validacao[c]) for c in ["X", "futuro", "y"]]
    opt = torch.optim.AdamW(modelo.parameters(), lr=cfg["learning_rate"], weight_decay=cfg["weight_decay"])
    perda = nn.MSELoss()
    melhor, melhor_epoca, esperas, estado, hist = float("inf"), 0, 0, None, []
    for epoca in range(1, cfg["epocas_maximas"]+1):
        modelo.train()
        soma = 0.
        for x, futuro, y in lotes:
            opt.zero_grad(set_to_none=True)
            erro = perda(modelo(x, futuro), y)
            assert torch.isfinite(erro), "Perda não finita."
            erro.backward()
            nn.utils.clip_grad_norm_(modelo.parameters(), 1.)
            opt.step()
            soma += erro.item()*len(y)
        modelo.eval()
        with torch.inference_mode():
            val = float(perda(modelo(xv, fv), yv))
        hist.append(dict(epoca=epoca, MSE_treino=soma/len(treino["y"]), MSE_validacao=val))
        if val < melhor-cfg["melhoria_minima"]:
            melhor, melhor_epoca, esperas = val, epoca, 0
            estado = copy.deepcopy(modelo.state_dict())
        else:
            esperas += 1
        if esperas >= cfg["paciencia"]:
            break
    assert estado is not None
    modelo.load_state_dict(estado)
    return modelo.eval(), hist, melhor_epoca


def prever(modelo, j, contrato, cfg):
    entradas = transformar(j, contrato, cfg)
    modelo.eval()
    with torch.inference_mode():
        z = modelo(torch.from_numpy(entradas["X"]), torch.from_numpy(entradas["futuro"])).numpy()
    return np.maximum(z.astype(float)*contrato["y_escala"]+contrato["y_media"], 0)*cfg["capacidade_ac_kw"]


def carregar_brasil(raiz):
    """Entrada isolada da CLI: abre somente as três partições brasileiras já auditadas."""
    raiz = Path(raiz).resolve()
    pasta = raiz/"experimentos/chronos_diario_contadores"
    dados = dict(raiz=raiz, pasta=pasta, out=pasta/"resultados", janelas={})
    for part in ["treino", "validacao", "teste"]:
        with np.load(pasta/"dados"/f"brasil_lag3_{part}.npz", allow_pickle=False) as z:
            j = dict(z)
        j["datas"] = pd.DatetimeIndex(j["datas"])
        dados["janelas"]["brasil", part] = j
    return dados


def _conferir_dados(dados, cfg):
    janelas = {part: dados["janelas"]["brasil", part] for part in ["treino", "validacao", "teste"]}
    limites = {"treino": ("2025-01-01", "2025-09-30"), "validacao": ("2025-10-01", "2025-10-31"), "teste": ("2025-11-01", "2025-12-31")}
    for part, j in janelas.items():
        datas = pd.DatetimeIndex(j["datas"])
        assert datas.is_unique and datas.is_monotonic_increasing
        assert j["X"].shape == (len(datas), cfg["contexto_passos"], len(cfg["colunas_historicas"]))
        inicio, fim = limites[part]
        assert ((datas>=inicio)&(datas<=fim)).all()
        # Confere os tensores em memória contra o arquivo cuja assinatura é registrada.
        with np.load(dados["pasta"]/"dados"/f"brasil_lag3_{part}.npz", allow_pickle=False) as z:
            for c in ["X", "y", "real_kw", "persistencia", "calendario_futuro"]:
                np.testing.assert_array_equal(j[c], z[c])
            np.testing.assert_array_equal(datas.to_numpy(), z["datas"])
    return janelas


@execucao_exclusiva
def executar_benchmark(dados):
    """Treina todos os modelos/seleciona por outubro antes de prever novembro–dezembro."""
    pasta, out = dados["pasta"], dados["out"]
    cfg_path = pasta/"benchmark_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg["dominio_treinamento"]=="brasil" and not cfg["pre_treinamento"] and not cfg["residual_persistencia"]
    assert cfg["seed_principal"] in cfg["seeds"]
    j = _conferir_dados(dados, cfg)
    hashes = {f"dados/brasil_lag3_{p}.npz": sha256(pasta/"dados"/f"brasil_lag3_{p}.npz") for p in j}
    manifesto = dict(config=cfg, arquivos_sha256=hashes, codigo_sha256=sha256(Path(__file__)), torch=str(torch.__version__))
    assinatura = hashlib.sha256(json.dumps(manifesto, sort_keys=True).encode()).hexdigest()
    salvar_json(out/"benchmark_manifesto.json", dict(manifesto, assinatura=assinatura))
    contrato = ajustar_normalizacao(j["treino"])
    salvar_json(out/"benchmark_normalizacao.json", contrato)
    tr, va = [transformar(j[p], contrato, cfg) for p in ["treino", "validacao"]]
    previa_determinismo = torch.are_deterministic_algorithms_enabled()
    torch.set_num_threads(cfg["threads_cpu"])
    torch.use_deterministic_algorithms(True)
    linhas, previsoes, modelos, execucoes = [], [], {}, []
    try:
        for tipo in ["mlp", "lstm"]:
            for seed in cfg["seeds"]:
                torch.manual_seed(seed)
                np.random.seed(seed)
                random.seed(seed)
                modelo = construir(tipo, cfg)
                destino = pasta/"modelos/benchmark_brasil"/tipo/f"seed{seed}"
                destino.mkdir(parents=True, exist_ok=True)
                pronto, peso = destino/"concluido.json", destino/"modelo.pt"
                if pronto.exists():
                    meta = json.loads(pronto.read_text(encoding="utf-8"))
                    assert meta["assinatura"]==assinatura, "Benchmark mudou: use outra pasta ou remova apenas os modelos do benchmark."
                    assert sha256(peso)==meta["checkpoint_sha256"]
                    ck = torch.load(peso, map_location="cpu", weights_only=True)
                    assert ck["assinatura"]==assinatura
                    modelo.load_state_dict(ck["state_dict"])
                    print(f"Reutilizando {tipo} Brasil seed={seed}.", flush=True)
                else:
                    t0 = time.perf_counter()
                    modelo, hist, epoca = ajustar(modelo, tr, va, seed, cfg)
                    torch.save(dict(state_dict=modelo.state_dict(), assinatura=assinatura, contrato=contrato,
                                    config=cfg, tipo=tipo, seed=seed, melhor_epoca=epoca), peso)
                    pd.DataFrame(hist).to_csv(destino/"historico.csv", index=False)
                    meta = dict(arquitetura=tipo, seed=seed, melhor_epoca=epoca, epocas_executadas=len(hist),
                                parametros=sum(p.numel() for p in modelo.parameters()), segundos=time.perf_counter()-t0,
                                pre_treinamento=False, dominio_treinamento="brasil", dispositivo="CPU",
                                residual_persistencia=False, estado_recorrente_persistente=False,
                                teste_usado_na_selecao=False, assinatura=assinatura, checkpoint_sha256=sha256(peso))
                    salvar_json(pronto, meta)
                    print(f"{tipo} Brasil seed={seed}: época escolhida={epoca}/{len(hist)}.", flush=True)
                modelos[tipo, seed] = modelo.eval()
                execucoes.append(meta)
                # Apenas validação, até todos os checkpoints/decisões estarem fixados.
                pred = prever(modelo, j["validacao"], contrato, cfg)
                linhas.append(dict(metricas(f"{tipo}_brasil", j["validacao"]["real_kw"], pred, j["validacao"]["persistencia"]*1000), seed=seed, particao="validacao"))
                previsoes.append(_tabela_pred(tipo, seed, "validacao", j["validacao"], pred))
        pd.DataFrame(execucoes).to_csv(out/"benchmark_execucoes.csv", index=False)
        val = pd.DataFrame(linhas)
        val.to_csv(out/"benchmark_metricas_validacao_por_seed.csv", index=False)
        # Mesmas referências e persistência, antes da decisão conjunta.
        chronos_val = pd.read_csv(out/"previsoes_validacao.csv", parse_dates=["timestamp"])
        _conferir_referencia(chronos_val, j["validacao"])
        candidatos = pd.concat([pd.read_csv(out/"metricas_validacao.csv"), val[val.seed.eq(cfg["seed_principal"])].drop(columns=["seed", "particao"])], ignore_index=True)
        candidatos = candidatos[candidatos.modelo.ne("transferencia_sem_brasil")]
        escolha = candidatos.sort_values("RMSE_kW", kind="stable").iloc[0].to_dict()
        decisao = dict(escolhido=escolha, seed_principal=cfg["seed_principal"], selecao="Menor RMSE em outubro; seed 42 pré-fixada; transferência sem Brasil fora da seleção brasileira.",
                       teste_usado_na_selecao=False, teste_previamente_consultado=True, assinatura=assinatura)
        salvar_json(out/"benchmark_decisao_validacao.json", decisao)
        for (tipo, seed), modelo in modelos.items():
            pred = prever(modelo, j["teste"], contrato, cfg)
            linhas.append(dict(metricas(f"{tipo}_brasil", j["teste"]["real_kw"], pred, j["teste"]["persistencia"]*1000), seed=seed, particao="teste"))
            previsoes.append(_tabela_pred(tipo, seed, "teste", j["teste"], pred))
        por_seed = pd.DataFrame(linhas)
        por_seed.to_csv(out/"benchmark_metricas_por_seed.csv", index=False)
        pd.concat(previsoes, ignore_index=True).to_csv(out/"benchmark_previsoes_por_seed.csv", index=False)
        _finalizar(dados, por_seed, previsoes, decisao, cfg)
    finally:
        torch.use_deterministic_algorithms(previa_determinismo)
    graficos_benchmark(dados)
    return pd.read_csv(out/"benchmark_final.csv")


def _tabela_pred(tipo, seed, part, j, pred):
    return pd.DataFrame(dict(modelo=f"{tipo}_brasil", seed=seed, particao=part, timestamp=j["datas"],
                             real_kw=j["real_kw"], previsto_kw=pred, persistencia_kw=j["persistencia"]*1000))


def _conferir_referencia(t, j):
    np.testing.assert_array_equal(pd.to_datetime(t.timestamp).to_numpy(), pd.DatetimeIndex(j["datas"]).to_numpy())
    np.testing.assert_allclose(t.referencia_diaria_kw, j["real_kw"], atol=1e-8)
    np.testing.assert_allclose(t.persistencia, j["persistencia"]*1000, atol=1e-8)


def _finalizar(dados, por_seed, previsoes, decisao, cfg):
    out = dados["out"]
    chronos = pd.read_csv(out/"comparacao_final.csv")
    t = pd.read_csv(out/"previsoes_teste.csv", parse_dates=["timestamp"])
    _conferir_referencia(t, dados["janelas"]["brasil", "teste"])
    redes = por_seed[por_seed.particao.eq("teste") & por_seed.seed.eq(cfg["seed_principal"])].drop(columns=["particao", "seed"]).copy()
    for c in ["MAE", "RMSE", "BIAS"]:
        redes[f"{c}_kWh_dia"] = redes[f"{c}_kW"]*24
    redes["escolhido_validacao_chronos"] = False
    final = pd.concat([chronos, redes], ignore_index=True)
    final["semente"] = cfg["seed_principal"]
    final["n_sementes_na_linha"] = 1
    final["escolhido_validacao_geral"] = final.modelo.eq(decisao["escolhido"]["modelo"])
    final.to_csv(out/"benchmark_final.csv", index=False)
    for pred in previsoes:
        if pred.particao.iloc[0]=="teste" and pred.seed.iloc[0]==cfg["seed_principal"]:
            np.testing.assert_array_equal(pd.to_datetime(pred.timestamp).to_numpy(), pd.to_datetime(t.timestamp).to_numpy())
            nome = pred.modelo.iloc[0]
            t[nome] = pred.previsto_kw.to_numpy()
            t[f"energia_prevista_{nome}_kwh"] = t[nome]*24
    t.to_csv(out/"benchmark_previsoes_teste.csv", index=False)
    robustez = por_seed.groupby(["modelo", "particao"], as_index=False).agg(
        n_seeds=("seed", "nunique"), MAE_kW_media=("MAE_kW", "mean"), MAE_kW_desvio=("MAE_kW", "std"),
        RMSE_kW_media=("RMSE_kW", "mean"), RMSE_kW_desvio=("RMSE_kW", "std"),
        RMSE_kW_min=("RMSE_kW", "min"), RMSE_kW_max=("RMSE_kW", "max"))
    robustez.to_csv(out/"benchmark_robustez_seeds.csv", index=False)
    linhas = ["# Benchmark final diário — Brasil", "",
              "MLP e LSTM treinadas do zero somente no Brasil; sem transferência e sem correção residual de persistência.",
              "Mesmos 160 históricos de treino, 26 de validação e 44 de teste; três dias consecutivos para prever o dia seguinte.",
              "Todas as redes recebem seis variáveis passadas e seno/cosseno conhecidos da data alvo. Sem vento e sem meteorologia futura observada.",
              "Padronização de X/y ajustada somente no treino brasileiro. MLP 32/16 ReLU; LSTM de uma camada com 16 unidades e estado reiniciado a cada janela. Saída direta.",
              "AdamW, taxa 0.001, weight decay 0.0001, lote 16, até 200 épocas, paciência 30. Checkpoint por MSE da validação de outubro.",
              "Tabela principal: semente 42 previamente fixada, uma execução por modelo. Cinco sementes das redes locais são mostradas separadamente; seus desvios medem variação de inicialização, não intervalo de confiança nem significância estatística.",
              "Os orçamentos e as perdas de treinamento diferem: redes locais usam MSE; Chronos usa LoRA e perda de quantis. Comparação dos erros na mesma referência brasileira.",
              "O teste já foi consultado em estudos anteriores: resultado exploratório, sem confirmação independente.", "",
              f"Escolha pela validação conjunta: **{decisao['escolhido']['modelo']}**.", "",
              "| Modelo | N | MAE kW | RMSE kW | Skill RMSE % |", "|---|---:|---:|---:|---:|"]
    for r in final.itertuples():
        linhas.append(f"| {r.modelo} | {r.n} | {r.MAE_kW:.3f} | {r.RMSE_kW:.3f} | {r.Skill_RMSE_pct:.3f} |")
    linhas += ["", "## Variação entre cinco sementes (teste)", "", "| Rede | Sementes | MAE médio kW | RMSE médio kW | Desvio RMSE kW |", "|---|---:|---:|---:|---:|"]
    for r in robustez[robustez.particao.eq("teste")].itertuples():
        linhas.append(f"| {r.modelo} | {r.n_seeds} | {r.MAE_kW_media:.3f} | {r.RMSE_kW_media:.3f} | {r.RMSE_kW_desvio:.3f} |")
    (out/"benchmark_relatorio.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")


def graficos_benchmark(dados):
    import matplotlib.pyplot as plt
    out, pasta = dados["out"], dados["pasta"]
    m = pd.read_csv(out/"benchmark_final.csv")
    fig, axes = plt.subplots(1, 2, figsize=(17, 6))
    cores = ["#dd8b27" if s else ("#298858" if n in ["mlp_brasil", "lstm_brasil"] else "#4185ad")
             for n, s in zip(m.modelo, m.escolhido_validacao_geral)]
    for ax, metrica in zip(axes, ["MAE_kW", "RMSE_kW"]):
        ax.barh(m.modelo, m[metrica], color=cores)
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.25)
        ax.set_xlabel(metrica.replace("_", " "))
    fig.suptitle(f"Benchmark final: mesmos {int(m.n.iloc[0])} dias de teste, semente 42; laranja = escolha pela validação")
    fig.tight_layout()
    fig.savefig(out/"benchmark_comparacao_final.png", dpi=150)
    plt.close(fig)
    d = pd.read_csv(out/"benchmark_previsoes_teste.csv", parse_dates=["timestamp"])
    t = d.set_index("timestamp").reindex(pd.date_range("2025-11-01", "2025-12-31"))
    escolhido_chronos = json.loads((out/"decisao_validacao.json").read_text(encoding="utf-8"))["escolhido"]["modelo"]
    fig, ax = plt.subplots(figsize=(15, 5))
    for nome, rotulo in [("referencia_diaria_kw", "Referência pelos contadores"), ("persistencia", "Persistência"),
                         (escolhido_chronos, "Chronos escolhido em outubro"), ("mlp_brasil", "MLP somente Brasil"), ("lstm_brasil", "LSTM somente Brasil")]:
        ax.plot(t.index, t[nome]*24, ".-", ms=3, lw=1, label=rotulo)
    ax.set(ylabel="Energia (kWh/dia)", title="Previsão de um dia: mesmas datas e histórico observado atualizado", xlabel="Data")
    ax.grid(alpha=.25)
    ax.legend(fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out/"benchmark_previsoes_diarias.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    for ax, tipo in zip(axes, ["mlp", "lstm"]):
        pasta_modelo = pasta/"modelos/benchmark_brasil"/tipo/"seed42"
        h = pd.read_csv(pasta_modelo/"historico.csv")
        meta = json.loads((pasta_modelo/"concluido.json").read_text())
        ax.plot(h.epoca, h.MSE_treino, label="Treino")
        ax.plot(h.epoca, h.MSE_validacao, label="Validação")
        ax.axvline(meta["melhor_epoca"], ls="--", color="gray", label="Checkpoint")
        ax.set(title=tipo.upper()+" somente Brasil — semente 42", xlabel="Época", ylabel="MSE padronizado")
        ax.grid(alpha=.25)
        ax.legend()
    fig.tight_layout()
    fig.savefig(out/"benchmark_curvas_redes.png", dpi=150)
    plt.close(fig)
