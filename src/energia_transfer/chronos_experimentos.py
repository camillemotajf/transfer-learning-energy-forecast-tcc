"""Adapta os cinco cenarios de Shuai Guo aos dados solares reais de 5 minutos.

O notebook teste_cronos.ipynb e a CLI usam as mesmas funcoes. As tarefas de
treinamento contem exatamente 12 passos passados tratados e um alvo medido:
min_past=12 impede amostrar um alvo imputado dentro do historico.
"""
from __future__ import annotations

import gc
import hashlib
import importlib.metadata
import json
from functools import wraps
from pathlib import Path
import time

import numpy as np
import pandas as pd

CALENDARIO = ["hora_sin", "hora_cos", "dia_ano_sin", "dia_ano_cos"]
CAPACIDADES = {"brasil": 1000.0, "australia": 24.0}
VERSAO = 1


def execucao_exclusiva(func):
    """Notebook e CLI nao devem sobrescrever o mesmo adaptador simultaneamente."""
    @wraps(func)
    def executar(dados, *args, **kwargs):
        from filelock import FileLock, Timeout
        lock = FileLock(str(dados["pasta"] / ".execucao.lock"))
        try:
            lock.acquire(timeout=0)
        except Timeout:
            print("Outra execucao deste experimento esta em andamento; aguardando sua conclusao.", flush=True)
            lock.acquire()
        try:
            return func(dados, *args, **kwargs)
        finally:
            lock.release()
    return executar


def sha256(p):
    with Path(p).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def salvar_json(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def indices_distribuidos(n, limite):
    return np.unique(np.linspace(0, n - 1, min(n, limite), dtype=int))


def extrair_janelas(frame, datas, capacidade, contexto=12):
    """Constroi janelas independentes, sem comprimir o calendario nem estimar alvos."""
    datas = pd.DatetimeIndex(datas)
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    pos = frame.index.get_indexer(datas)
    assert (pos >= contexto).all(), "Data fora da base ou historico insuficiente."
    idx = pos[:, None] - np.arange(contexto, 0, -1)[None, :]
    tempos = frame.index.to_numpy()[idx]
    passo = np.timedelta64(5, "m")
    assert (np.diff(tempos, axis=1) == passo).all(), "Historico atravessa lacuna temporal."
    assert (datas.to_numpy() - tempos[:, -1] == passo).all()
    assert frame.iloc[pos].diurno.all()
    original = frame.Active_Power_original.to_numpy(dtype=float)
    assert np.isfinite(original[pos]).all(), "Alvo precisa ser medido."
    assert np.isfinite(original[pos - 1]).all(), "Persistencia precisa ser medida."
    valores = frame[["Active_Power"] + CALENDARIO].to_numpy(dtype=np.float32)
    valores[:, 0] /= capacidade
    x = valores[idx]
    assert np.isfinite(x).all()
    return {"X": x, "y": original[pos] / capacidade, "real_kw": original[pos].copy(),
            "datas": datas, "calendario_futuro": valores[pos, 1:].copy(),
            "persistencia": original[pos - 1] / capacidade}


def preparar(raiz):
    raiz = Path(raiz).resolve()
    pasta = raiz / "experimentos/chronos_5min"
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["contexto_passos"] == 12 and cfg["horizonte_passos"] == 1
    origem = raiz / "experimentos/transfer_learning_australia_brasil/dados"
    resultado = {"raiz": raiz, "pasta": pasta, "cfg": cfg, "janelas": {}}
    auditoria, hashes = [], {}
    for dominio, capacidade in CAPACIDADES.items():
        base = raiz / f"data/processed/{dominio}/base_5min_{dominio}.pkl"
        hashes[str(base.relative_to(raiz))] = sha256(base)
        frame = pd.read_pickle(base)
        for particao in ["treino", "validacao", "teste"]:
            if dominio == "australia" and particao == "teste":
                continue
            arquivo = origem / f"{dominio}_lag12_{particao}.npz"
            hashes[str(arquivo.relative_to(raiz))] = sha256(arquivo)
            with np.load(arquivo, allow_pickle=False) as z:
                datas = pd.to_datetime(z["datas"])
                assert (z["fracao_alvo_estimada_pct"] == 0).all()
                alvo_ref = z["y_original"].copy()
            # AU valida checkpoints em 512 origens distribuídas por 2023.
            if dominio == "australia" and particao == "validacao":
                ids = indices_distribuidos(len(datas), cfg["janelas_checkpoint"])
                datas, alvo_ref = datas[ids], alvo_ref[ids]
            janelas = extrair_janelas(frame, datas, capacidade, cfg["contexto_passos"])
            np.testing.assert_allclose(janelas["y"], alvo_ref, atol=1e-6)
            if dominio == "brasil":
                assert (datas <= pd.Timestamp("2025-09-30 23:59:59")).all() if particao == "treino" else True
                assert (datas.year == 2025).all()
                assert (datas.month == 10).all() if particao == "validacao" else True
                assert (datas.month >= 11).all() if particao == "teste" else True
            else:
                assert (datas.year <= 2022).all() if particao == "treino" else (datas.year == 2023).all()
            resultado["janelas"][dominio, particao] = janelas
            auditoria.append({"dominio": dominio, "particao": particao, "n": len(datas),
                              "inicio": str(datas.min()), "fim": str(datas.max()),
                              "capacidade_ac_kw": capacidade})
        del frame
    out = pasta / "resultados"
    out.mkdir(parents=True, exist_ok=True)
    pacotes = {p: importlib.metadata.version(p) for p in
               ["chronos-forecasting", "torch", "transformers", "peft", "accelerate"]}
    manifesto = {"versao": VERSAO, "cfg": cfg, "pacotes": pacotes, "arquivos_sha256": hashes}
    assinatura = hashlib.sha256(json.dumps(manifesto, sort_keys=True).encode()).hexdigest()
    resultado.update(out=out, assinatura=assinatura, manifesto=manifesto)
    pd.DataFrame(auditoria).to_csv(out / "particoes.csv", index=False)
    salvar_json(out / "manifesto.json", dict(manifesto, assinatura=assinatura))
    print(pd.DataFrame(auditoria).to_string(index=False), flush=True)
    return resultado


def tarefas(janelas, calendario, ids=None, colunas_covariaveis=None, colunas_futuras=None):
    """Forma publica de fit(): historico seguido de um alvo separado."""
    nomes = CALENDARIO if colunas_covariaveis is None else colunas_covariaveis
    futuras = nomes if colunas_futuras is None else colunas_futuras
    ids = np.arange(len(janelas["y"])) if ids is None else ids
    entradas = []
    for i in ids:
        # O ultimo alvo vem da referencia explicita, nao do historico preenchido.
        alvo = np.r_[janelas["X"][i, :, 0], janelas["y"][i]].astype(np.float32)[None, :]
        task = {"target": alvo}
        if calendario:
            cov = np.vstack([janelas["X"][i, :, 1:], janelas["calendario_futuro"][i]])
            task.update(past_covariates={nome: cov[:, k] for k, nome in enumerate(nomes)},
                        future_covariates={nome: None for nome in futuras})
        entradas.append(task)
    return entradas


def caminho_base(cfg):
    from huggingface_hub.constants import HF_HUB_CACHE
    p = Path(HF_HUB_CACHE) / "models--amazon--chronos-2/snapshots" / cfg["revisao"]
    assert (p / "model.safetensors").exists(), f"Modelo nao encontrado: {p}"
    return p


def hash_congelados(model):
    h = hashlib.sha256()
    for nome, parametro in model.named_parameters():
        if not parametro.requires_grad:
            h.update(nome.encode())
            h.update(parametro.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


@execucao_exclusiva
def treinar(dados):
    import torch
    import peft  # Falhar explicitamente: nunca recuar silenciosamente para ajuste completo.
    from chronos import Chronos2Pipeline
    from transformers import EarlyStoppingCallback, TrainerCallback, set_seed

    cfg, pasta, out = dados["cfg"], dados["pasta"], dados["out"]
    covariaveis = cfg.get("colunas_covariaveis", CALENDARIO)
    futuras = cfg.get("colunas_futuras", covariaveis)
    contexto = cfg["contexto_passos"]
    torch.set_num_threads(2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base = Chronos2Pipeline.from_pretrained(str(caminho_base(cfg)), device_map=device, local_files_only=True)

    for cenario in cfg["cenarios"]:
        nome = cenario["nome"]
        destino = pasta / "modelos" / nome
        pronto = destino / "concluido.json"
        if pronto.exists():
            m = json.loads(pronto.read_text(encoding="utf-8"))
            assert m["assinatura"] == dados["assinatura"], "Configuracao mudou: use outra pasta de resultados."
            assert sha256(destino / "adaptador/adapter_model.safetensors") == m["adaptador_sha256"]
            print("Reutilizando adaptador verificado:", nome, flush=True)
            continue
        destino.mkdir(parents=True, exist_ok=True)
        set_seed(cfg["semente"])
        dominios, calendario = cenario["dominios"], cenario["calendario"]
        # Portfolio tem o mesmo numero de origens por usina para equilibrar a amostragem.
        n_train = min(len(dados["janelas"][d, "treino"]["y"]) for d in dominios)
        train, val, composicao = [], [], []
        for d in dominios:
            jt, jv = dados["janelas"][d, "treino"], dados["janelas"][d, "validacao"]
            it = indices_distribuidos(len(jt["y"]), n_train)
            iv = indices_distribuidos(len(jv["y"]), cfg["janelas_checkpoint"] // len(dominios))
            train.extend(tarefas(jt, calendario, it, covariaveis, futuras))
            val.extend(tarefas(jv, calendario, iv, covariaveis, futuras))
            composicao.append({"dominio": d, "treino": len(it), "validacao_checkpoint": len(iv)})
        salvar_json(destino / "composicao.json", composicao)
        eventos, auditoria = [], {}

        class Registro(TrainerCallback):
            def on_train_begin(self, args, state, control, model=None, **kwargs):
                treinaveis = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
                assert treinaveis and all("lora_" in n for n, _ in treinaveis)
                auditoria.update(parametros_treinaveis=sum(p.numel() for _, p in treinaveis),
                                 parametros_totais=sum(p.numel() for p in model.parameters()),
                                 congelados_sha256_antes=hash_congelados(model))

            def on_step_end(self, args, state, control, **kwargs):
                if state.global_step % 25 == 0:
                    salvar_json(out / "progresso.json", {"fase": "treino", "cenario": nome,
                                "passo": state.global_step, "maximo": cfg["num_steps"]})

            def on_log(self, args, state, control, logs=None, **kwargs):
                eventos.append(dict(passo=state.global_step, **(logs or {})))
                salvar_json(destino / "historico.json", eventos)

            def on_train_end(self, args, state, control, model=None, **kwargs):
                auditoria["congelados_sha256_depois"] = hash_congelados(model)
                assert auditoria["congelados_sha256_antes"] == auditoria["congelados_sha256_depois"]
                auditoria.update(passos_executados=state.global_step, melhor_loss=state.best_metric,
                                 melhor_checkpoint=state.best_model_checkpoint)

        print(f"Treinando {nome}: {len(train)} origens; {len(val)} validacoes.", flush=True)
        t0 = time.perf_counter()
        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        ajustado = base.fit(
            train, validation_inputs=val, prediction_length=1, context_length=contexto,
            min_past=contexto, finetune_mode="lora", lora_config=cfg["lora_config"],
            learning_rate=cfg["learning_rate"], num_steps=cfg["num_steps"],
            batch_size=cfg["batch_origens"] * (1+len(covariaveis) if calendario else 1),
            output_dir=destino, finetuned_ckpt_name="adaptador",
            callbacks=[Registro(), EarlyStoppingCallback(early_stopping_patience=cfg["paciencia"])],
            eval_steps=cfg["eval_steps"], save_steps=cfg["eval_steps"],
            logging_steps=cfg["eval_steps"], disable_tqdm=True, seed=cfg["semente"],
            data_seed=cfg["semente"], dataloader_pin_memory=False,
        )
        auditoria.update(cenario=nome, semente=cfg["semente"], composicao=composicao,
                         assinatura=dados["assinatura"], segundos=time.perf_counter() - t0,
                         memoria_cuda_max_mib=torch.cuda.max_memory_allocated()/2**20 if device=="cuda" else 0,
                         adaptador_sha256=sha256(destino / "adaptador/adapter_model.safetensors"))
        salvar_json(pronto, auditoria)
        print(f"OK {nome}: {auditoria['passos_executados']} passos; {auditoria['segundos']:.1f}s.", flush=True)
        del ajustado, train, val
        gc.collect()
        if device == "cuda":
            torch.cuda.empty_cache()
    del base
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()


def prever(pipeline, janelas, calendario, batch_size=64, colunas_covariaveis=None, colunas_futuras=None):
    """Predicao recebe somente o historico e as covariaveis conhecidas futuras."""
    import torch
    from chronos.chronos2.preprocess import from_list_of_dicts
    nomes = CALENDARIO if colunas_covariaveis is None else colunas_covariaveis
    futuras = nomes if colunas_futuras is None else colunas_futuras
    partes = []
    for inicio in range(0, len(janelas["y"]), 128):
        entradas = []
        for i in range(inicio, min(inicio + 128, len(janelas["y"]))):
            task = {"target": janelas["X"][i, :, 0][None, :]}
            if calendario:
                task.update(past_covariates={n: janelas["X"][i, :, k+1] for k, n in enumerate(nomes)},
                            future_covariates={n: janelas["calendario_futuro"][i, nomes.index(n):nomes.index(n)+1] for n in futuras})
            entradas.append(task)
        prepared = from_list_of_dicts(entradas, prediction_length=1)
        with torch.inference_mode():
            _, medias = pipeline.predict_quantiles(
                prepared, prediction_length=1, quantile_levels=[0.1, 0.5, 0.9],
                context_length=janelas["X"].shape[1], batch_size=batch_size, cross_learning=False,
            )
        partes.append(np.array([float(m[0, 0]) for m in medias]))
    valores = np.maximum(np.concatenate(partes), 0) * 1000.0
    assert np.isfinite(valores).all()
    return valores


def metricas(nome, real, previsto, persistencia):
    e = np.asarray(previsto) - real
    rmse = float(np.sqrt(np.mean(e**2)))
    mae = float(np.abs(e).mean())
    ref = float(np.sqrt(np.mean((persistencia-real)**2)))
    return {"modelo": nome, "n": len(real), "MAE_kW": mae, "RMSE_kW": rmse,
            "WAPE_pct": 100*float(np.abs(e).sum()/np.abs(real).sum()),
            "Skill_RMSE_pct": 100*(1-rmse/ref), "BIAS_kW": float(e.mean())}


@execucao_exclusiva
def avaliar(dados):
    import torch
    from chronos import Chronos2Pipeline
    cfg, out, pasta = dados["cfg"], dados["out"], dados["pasta"]
    torch.set_num_threads(2)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    definicoes = [dict(nome="zero_shot_univariado", calendario=False),
                  dict(nome="zero_shot_calendario", calendario=True)] + cfg["cenarios"]
    metricas_val, previsoes = [], {}
    # Concluir e salvar a decisao usando OUTUBRO antes de calcular metricas no teste.
    for particao in ["validacao", "teste"]:
        j = dados["janelas"]["brasil", particao]
        real, pers = j["real_kw"], j["persistencia"]*1000
        tabela = pd.DataFrame({"timestamp": j["datas"], "real_kw": real, "persistencia": pers})
        linhas = [metricas("persistencia", real, pers, pers)]
        for c in definicoes:
            nome = c["nome"]
            local = caminho_base(cfg) if nome.startswith("zero_shot") else pasta / "modelos" / nome / "adaptador"
            # Arquivo final pequeno; assinatura inclui os pesos adaptados.
            peso = local / ("model.safetensors" if nome.startswith("zero_shot") else "adapter_model.safetensors")
            chave = hashlib.sha256((dados["assinatura"] + sha256(peso) + nome + particao).encode()).hexdigest()
            cache = out / f"previsoes_{particao}_{nome}.npz"
            if cache.exists():
                with np.load(cache, allow_pickle=False) as z:
                    assert str(z["assinatura"]) == chave
                    np.testing.assert_array_equal(z["datas"], j["datas"].to_numpy().astype("datetime64[s]").astype(str))
                    pred = z["previsto_kw"].copy()
            else:
                pipeline = Chronos2Pipeline.from_pretrained(str(local), device_map=device, local_files_only=True)
                pred = prever(pipeline, j, c["calendario"], cfg["batch_inferencia"])
                np.savez_compressed(cache, assinatura=chave, previsto_kw=pred,
                                    datas=j["datas"].to_numpy().astype("datetime64[s]").astype(str))
                del pipeline
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()
            tabela[nome] = pred
            linhas.append(metricas(nome, real, pred, pers))
            salvar_json(out / "progresso.json", {"fase": particao, "cenario": nome, "n": len(pred)})
            print(f"{particao}: {nome}; RMSE {linhas[-1]['RMSE_kW']:.3f} kW", flush=True)
        resumo = pd.DataFrame(linhas)
        resumo.to_csv(out / f"metricas_{particao}.csv", index=False)
        tabela.to_csv(out / f"previsoes_{particao}.csv", index=False)
        previsoes[particao] = tabela
        if particao == "validacao":
            # Held-out nao usa Brasil nem para escolher checkpoints, nem para selecao global.
            elegiveis = resumo[resumo.modelo != "transferencia_sem_brasil"]
            melhor = elegiveis.sort_values("RMSE_kW").iloc[0].to_dict()
            decisao = {"escolhido": melhor, "criterio": "Menor RMSE em todas as 4043 origens de outubro de 2025.",
                       "held_out_excluido_da_selecao_brasileira": True, "semente": cfg["semente"],
                       "teste_usado_na_selecao": False, "teste_previamente_consultado": True,
                       "assinatura": dados["assinatura"]}
            salvar_json(out / "decisao_validacao.json", decisao)
        else:
            _comparar_e_plotar(dados, resumo, tabela, decisao)
    salvar_json(out / "progresso.json", {"fase": "concluido", "cenarios_lora": 5})
    return pd.read_csv(out / "comparacao_final.csv")


def _comparar_e_plotar(dados, resumo, previsoes, decisao):
    import matplotlib.pyplot as plt
    out = dados["out"]
    anteriores = pd.read_csv(dados["raiz"] / "resultados_chronos/5min/metricas_chronos_5min.csv")
    lstm = anteriores[anteriores.modelo.isin(["LSTM_local", "LSTM_completo"])]
    colunas = ["modelo", "n", "MAE_kW", "RMSE_kW", "WAPE_pct", "Skill_RMSE_pct", "BIAS_kW"]
    final = pd.concat([resumo[colunas], lstm[colunas]], ignore_index=True)
    final["escolhido_validacao_chronos"] = final.modelo.eq(decisao["escolhido"]["modelo"])
    final.to_csv(out / "comparacao_final.csv", index=False)
    pares = []
    for c in dados["cfg"]["cenarios"]:
        nome = c["nome"]
        ref = "zero_shot_calendario" if c["calendario"] else "zero_shot_univariado"
        a, b = final.set_index("modelo").loc[[nome, ref]].to_dict("records")
        pares.append({"cenario": nome, "referencia": ref,
                      "ganho_RMSE_pct": 100*(1-a["RMSE_kW"]/b["RMSE_kW"]),
                      "ganho_WAPE_pct": 100*(1-a["WAPE_pct"]/b["WAPE_pct"])})
    pd.DataFrame(pares).to_csv(out / "ganhos_pareados.csv", index=False)
    fig, axs = plt.subplots(1, 2, figsize=(17, 6))
    rotulos = {"persistencia": "Persistência", "zero_shot_univariado": "Zero-shot potência",
               "zero_shot_calendario": "Zero-shot calendário", "individual": "LoRA Brasil",
               "portfolio": "LoRA AU+BR", "individual_calendario": "LoRA Brasil + calendário",
               "portfolio_calendario": "LoRA AU+BR + calendário",
               "transferencia_sem_brasil": "LoRA AU → Brasil", "LSTM_local": "LSTM local (5 sementes)",
               "LSTM_completo": "LSTM transferência (5 sementes)"}
    for ax, metrica in zip(axs, ["MAE_kW", "RMSE_kW"]):
        ax.barh([rotulos[n] for n in final.modelo], final[metrica], color=["#e19335" if s else "#4689b4" for s in final.escolhido_validacao_chronos])
        ax.invert_yaxis()
        ax.set_xlabel(metrica.replace("_", " ") + " — menor é melhor")
        ax.grid(axis="x", alpha=.25)
    fig.suptitle("Previsão +5 minutos — mesmas 7.668 observações medidas\nLoRA: semente 42; laranja: escolha na validação brasileira")
    fig.tight_layout()
    fig.savefig(out / "comparacao_cinco_cenarios.png", dpi=150)
    plt.close(fig)
    escolhido = decisao["escolhido"]["modelo"]
    inicio = previsoes.timestamp.min().normalize()
    grade = pd.date_range(inicio, inicio+pd.Timedelta(days=5), freq="5min", inclusive="left")
    t = previsoes.set_index("timestamp").reindex(grade)
    fig, ax = plt.subplots(figsize=(16, 5))
    ax.plot(grade, t.real_kw, color="black", lw=1.2, label="Medido — oito inversores")
    for nome in dict.fromkeys(["persistencia", "zero_shot_univariado", escolhido]):
        ax.plot(grade, t[nome], lw=.9, label=rotulos[nome])
    ax.set(ylabel="Potência AC (kW)", xlabel="Data/hora local — America/Sao_Paulo",
           title="Primeiros cinco dias do teste — modelo escolhido em outubro")
    ax.grid(alpha=.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out / "previsoes_escolha_validacao.png", dpi=150)
    plt.close(fig)
    linhas = ["# Chronos-2: cinco cenários de LoRA em dados solares de cinco minutos", "",
              "Adaptação do artigo de Shuai Guo e de seu notebook público; não é uma reprodução dos dados sintéticos do autor.",
              "Contexto de 60 minutos; horizonte de 5 minutos; uma semente (42). LSTMs: média das métricas de cinco sementes.",
              "O teste de novembro–dezembro já foi consultado antes desta hipótese: resultados exploratórios, sem confirmação independente.", "",
              f"Escolha pelo RMSE de outubro: **{escolhido}**. O cenário AU → Brasil não usou rótulos brasileiros para ajustar nem escolher checkpoints e ficou fora da seleção brasileira.", "",
              "| Modelo | MAE kW | RMSE kW | WAPE % |", "|---|---:|---:|---:|"]
    for r in final.itertuples():
        linhas.append(f"| {r.modelo} | {r.MAE_kW:.3f} | {r.RMSE_kW:.3f} | {r.WAPE_pct:.3f} |")
    linhas += ["", "Fontes:", "", dados["cfg"]["artigo"], "", dados["cfg"]["implementacao_autor"], "",
               "API oficial: https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py"]
    (out / "relatorio.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")
