"""Chronos diario com blocos reais e a mesma coorte dos modelos diarios anteriores."""
from pathlib import Path
import gc
import hashlib
import importlib.metadata
import json

import numpy as np
import pandas as pd

from .chronos_experimentos import (caminho_base, indices_distribuidos, metricas,
                                  prever, salvar_json, sha256, treinar, execucao_exclusiva)


def extrair_diarias(frame, datas, cfg):
    """Preserva dias ausentes; meteorologia do dia alvo nunca e uma entrada."""
    datas = pd.DatetimeIndex(datas)
    contexto = cfg["contexto_passos"]
    cov, futuras = cfg["colunas_covariaveis"], cfg["colunas_futuras"]
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    pos = frame.index.get_indexer(datas)
    assert (pos >= contexto).all()
    idx = pos[:, None] - np.arange(contexto, 0, -1)[None, :]
    tempos = frame.index.to_numpy()[idx]
    assert (np.diff(tempos, axis=1) == np.timedelta64(1, "D")).all(), "Historico atravessa dias ausentes."
    assert (datas.to_numpy()-tempos[:, -1] == np.timedelta64(1, "D")).all()
    valores = frame[["Active_Power"] + cov].to_numpy(dtype=float)
    x, y = valores[idx], valores[pos, 0]
    assert np.isfinite(x).all(), "Historico contem dia reprovado ou covariavel ausente."
    assert np.isfinite(y).all(), "Alvo diario ausente: nao imputar dias."
    futuro = np.full((len(datas), len(cov)), np.nan, dtype=np.float32)
    periodo = np.where(datas.is_leap_year, 366., 365.)
    angulo = 2*np.pi*(datas.dayofyear-1)/periodo
    calendario = {"dia_ano_sin": np.sin(angulo), "dia_ano_cos": np.cos(angulo)}
    for nome in futuras:
        # Calculo somente por data; nao consulta meteorologia no instante alvo.
        futuro[:, cov.index(nome)] = calendario[nome]
    return {"X": x.astype(np.float32), "y": y.copy(), "real_kw": y*1000,
            "persistencia": valores[pos-1, 0], "datas": datas,
            "calendario_futuro": futuro}


def preparar(raiz):
    raiz = Path(raiz).resolve()
    pasta = raiz / "experimentos/chronos_diario"
    out = pasta / "resultados"
    out.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    assert cfg["contexto_passos"] == 3 and cfg["horizonte_passos"] == 1
    origem = raiz / "experimentos/transfer_learning_australia_brasil/historico_diario/dados"
    fonte_br = raiz / "data/processed/brasil/base_diaria_leopoldo_dias_validos.csv"
    fonte_q = raiz / "reports/base_final/qualidade_diaria_base_consecutiva.csv"
    br = pd.read_csv(fonte_br, parse_dates=["timestamp"]).set_index("timestamp")
    qualidade = pd.read_csv(fonte_q, parse_dates=["timestamp"]).set_index("timestamp")
    assert len(br) == 297 and qualidade.loc[br.index].dia_elegivel.all()
    hashes = {str(p.relative_to(raiz)): sha256(p) for p in [fonte_br, fonte_q]}
    resultado = {"raiz": raiz, "pasta": pasta, "out": out, "cfg": cfg,
                 "janelas": {}, "qualidade": qualidade, "brasil_original": br}
    auditoria = []
    for dominio in ["brasil", "australia"]:
        arquivo_csv = origem / f"{dominio}_pu.csv"
        hashes[str(arquivo_csv.relative_to(raiz))] = sha256(arquivo_csv)
        frame = pd.read_csv(arquivo_csv, parse_dates=["timestamp"]).set_index("timestamp").sort_index().asfreq("D")
        if dominio == "brasil":
            np.testing.assert_allclose(frame.loc[br.index].Active_Power*1000, br.Active_Power, atol=1e-8)
            assert frame.Active_Power.notna().sum() == 297
        for particao in ["treino", "validacao", "teste"]:
            if dominio == "australia" and particao == "teste":
                continue
            arq = origem / f"{dominio}_lag3_{particao}.npz"
            hashes[str(arq.relative_to(raiz))] = sha256(arq)
            with np.load(arq, allow_pickle=False) as z:
                datas, ref = pd.to_datetime(z["datas"]), z["y_original"].copy()
            j = extrair_diarias(frame, datas, cfg)
            np.testing.assert_allclose(j["y"], ref, atol=1e-6)
            resultado["janelas"][dominio, particao] = j
            auditoria.append({"dominio": dominio, "particao": particao, "n": len(datas),
                              "inicio": str(datas.min().date()), "fim": str(datas.max().date())})
    pd.DataFrame(auditoria).to_csv(out / "particoes.csv", index=False)
    grade = pd.date_range("2025-01-01", "2025-12-31", name="timestamp")
    diario = br.reindex(grade)
    diario = diario.join(qualidade[["planta_cobertura_diurna_original_pct", "planta_diurnos_com_estimativa_pct", "bloco_id"]])
    diario["dia_disponivel"] = diario.Active_Power.notna()
    diario.to_csv(out / "auditoria_calendario_brasil.csv")
    contagens = []
    for lag in [1, 3, 7, 14]:
        validas = diario.Active_Power.notna().rolling(lag+1).sum().eq(lag+1)
        for particao, mask in [("treino", grade<=pd.Timestamp("2025-09-30")),
                               ("validacao", (grade>=pd.Timestamp("2025-10-01")) & (grade<=pd.Timestamp("2025-10-31"))),
                               ("teste", grade>=pd.Timestamp("2025-11-01"))]:
            contagens.append({"historico_dias": lag, "particao": particao,
                              "janelas_consecutivas": int((validas.to_numpy() & mask).sum())})
    pd.DataFrame(contagens).to_csv(out / "janelas_por_historico.csv", index=False)
    pacotes = {p: importlib.metadata.version(p) for p in ["chronos-forecasting", "torch", "peft", "transformers", "accelerate"]}
    manifesto = {"versao_diaria": 1, "cfg": cfg, "arquivos_sha256": hashes, "pacotes": pacotes}
    assinatura = hashlib.sha256(json.dumps(manifesto, sort_keys=True).encode()).hexdigest()
    resultado.update(assinatura=assinatura, manifesto=manifesto)
    salvar_json(out / "manifesto.json", dict(manifesto, assinatura=assinatura))
    print(pd.DataFrame(auditoria).to_string(index=False), flush=True)
    return resultado


@execucao_exclusiva
def avaliar(dados, concluir=None):
    import torch
    from chronos import Chronos2Pipeline
    cfg, out, pasta = dados["cfg"], dados["out"], dados["pasta"]
    torch.set_num_threads(2)
    definicoes = [dict(nome="zero_shot_univariado", calendario=False),
                  dict(nome="zero_shot_covariaveis", calendario=True)] + cfg["cenarios"]
    for particao in ["validacao", "teste"]:
        j = dados["janelas"]["brasil", particao]
        real, pers = j["real_kw"], j["persistencia"]*1000
        tabela = pd.DataFrame({"timestamp": j["datas"], "referencia_diaria_kw": real, "persistencia": pers})
        q = dados["qualidade"].reindex(j["datas"])
        colunas_qualidade = dados.get("colunas_qualidade_avaliacao", {
            "cobertura_diurna_original_pct": "planta_cobertura_diurna_original_pct",
            "fracao_diurna_estimada_pct": "planta_diurnos_com_estimativa_pct",
        })
        for destino, fonte in colunas_qualidade.items():
            tabela[destino] = q[fonte].to_numpy()
        linhas = [metricas("persistencia", real, pers, pers)]
        for c in definicoes:
            nome = c["nome"]
            local = caminho_base(cfg) if nome.startswith("zero_shot") else pasta / "modelos" / nome / "adaptador"
            peso = local / ("model.safetensors" if nome.startswith("zero_shot") else "adapter_model.safetensors")
            chave = hashlib.sha256((dados["assinatura"]+sha256(peso)+nome+particao).encode()).hexdigest()
            cache = out / f"previsoes_{particao}_{nome}.npz"
            if cache.exists():
                with np.load(cache, allow_pickle=False) as z:
                    assert str(z["assinatura"]) == chave
                    pred = z["previsto_kw"].copy()
            else:
                pipeline = Chronos2Pipeline.from_pretrained(str(local), device_map="cuda" if torch.cuda.is_available() else "cpu", local_files_only=True)
                pred = prever(pipeline, j, c["calendario"], cfg["batch_inferencia"], cfg["colunas_covariaveis"], cfg["colunas_futuras"])
                np.savez_compressed(cache, assinatura=chave, previsto_kw=pred)
                del pipeline
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            assert len(pred) == len(real)
            tabela[nome] = pred
            linhas.append(metricas(nome, real, pred, pers))
            print(f"{particao}: {nome}; RMSE {linhas[-1]['RMSE_kW']:.3f} kW", flush=True)
        resumo = pd.DataFrame(linhas)
        resumo.to_csv(out / f"metricas_{particao}.csv", index=False)
        tabela.to_csv(out / f"previsoes_{particao}.csv", index=False)
        if particao == "validacao":
            melhor = resumo[resumo.modelo != "transferencia_sem_brasil"].sort_values("RMSE_kW").iloc[0].to_dict()
            decisao = {"escolhido": melhor, "teste_usado_na_selecao": False, "teste_previamente_consultado": True,
                       "criterio": f"Menor RMSE nas {len(real)} datas de outubro; held-out fora da selecao brasileira.",
                       "assinatura": dados["assinatura"]}
            salvar_json(out / "decisao_validacao.json", decisao)
        else:
            (concluir or _concluir)(dados, resumo, tabela, decisao)
    salvar_json(out / "progresso.json", {"fase": "concluido", "resolucao": "diaria", "cenarios_lora": 5})
    return pd.read_csv(out / "comparacao_final.csv")


def _concluir(dados, resumo, previsoes, decisao):
    out = dados["out"]
    antigo = dados["raiz"] / "experimentos/transfer_learning_australia_brasil/historico_diario/resultados/teste_previsoes.csv"
    ref = pd.read_csv(antigo, parse_dates=["timestamp"])
    ref = ref[(ref.lag==3) & ref.arquitetura.isin(["mlp_direta", "lstm_direta"]) & ref.metodo.isin(["local", "completo"])]
    por_seed = []
    real, pers = previsoes.referencia_diaria_kw.to_numpy(), previsoes.persistencia.to_numpy()
    for (arq, metodo, seed), g in ref.groupby(["arquitetura", "metodo", "seed"]):
        g = g.set_index("timestamp").reindex(previsoes.timestamp)
        assert g.previsto_kw.notna().all()
        np.testing.assert_allclose(g.real_kw, real, atol=1e-3)
        np.testing.assert_allclose(g.persistencia_kw, pers, atol=1e-3)
        nome = f"{arq}_{metodo}"
        previsoes[f"{nome}_seed{seed}"] = g.previsto_kw.to_numpy()
        por_seed.append(dict(metricas(nome, real, g.previsto_kw.to_numpy(), pers), seed=seed))
    sementes = pd.DataFrame(por_seed)
    sementes.to_csv(out / "referencias_por_seed.csv", index=False)
    medias = sementes.groupby("modelo", as_index=False)[["n", "MAE_kW", "RMSE_kW", "WAPE_pct", "Skill_RMSE_pct", "BIAS_kW"]].mean()
    final = pd.concat([resumo, medias], ignore_index=True)
    final["escolhido_validacao_chronos"] = final.modelo.eq(decisao["escolhido"]["modelo"])
    final.to_csv(out / "comparacao_final.csv", index=False)
    previsoes.to_csv(out / "previsoes_teste.csv", index=False)
    sensibilidade = []
    mask = previsoes.cobertura_diurna_original_pct.ge(95).to_numpy()
    if mask.sum()>1:
        for nome in ["persistencia"]+list(resumo.modelo[resumo.modelo.ne("persistencia")]):
            sensibilidade.append(metricas(nome, real[mask], previsoes[nome].to_numpy()[mask], pers[mask]))
    pd.DataFrame(sensibilidade).to_csv(out / "sensibilidade_original_95pct.csv", index=False)
    linhas = ["# Chronos-2 diário — Brasil", "", "Horizonte de um dia; histórico de três dias consecutivos.",
              "297 dias aprovados; 151 janelas de treino, 19 de validação e 23 de teste. Uma semente nos adaptadores; cinco nas referências MLP/LSTM.",
              "A referência é potência AC média diária tratada em kW, com lacunas intradiárias estimadas; não é energia diária nem medição integral.",
              "Dados meteorológicos ERA5 apenas passados; calendário futuro conhecido. Sem vento e sem meteorologia futura observada.",
              "Comparação exploratória: teste previamente consultado e validação brasileira pequena.", "",
              f"Escolha pela validação: **{decisao['escolhido']['modelo']}**.", "",
              "| Modelo | MAE kW | RMSE kW | WAPE % |", "|---|---:|---:|---:|"]
    for r in final.itertuples():
        linhas.append(f"| {r.modelo} | {r.MAE_kW:.3f} | {r.RMSE_kW:.3f} | {r.WAPE_pct:.3f} |")
    linhas += ["", f"Sensibilidade: {int(mask.sum())} alvos com cobertura diurna originalmente medida de pelo menos 95%.",
               "", dados["cfg"]["implementacao_autor"]]
    (out / "relatorio.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")


def graficos(dados):
    import matplotlib.pyplot as plt
    out = dados["out"]
    d = pd.read_csv(out / "previsoes_teste.csv", parse_dates=["timestamp"])
    m = pd.read_csv(out / "comparacao_final.csv")
    escolhido = json.loads((out / "decisao_validacao.json").read_text())["escolhido"]["modelo"]
    grade = pd.date_range("2025-11-01", "2025-12-31", freq="D")
    t = d.set_index("timestamp").reindex(grade)
    fig, ax = plt.subplots(figsize=(15, 5))
    for nome, rotulo in dict.fromkeys([("referencia_diaria_kw", "Referência diária tratada"), ("persistencia", "Persistência"),
                                       ("zero_shot_univariado", "Chronos zero-shot"), (escolhido, "Escolha na validação")]):
        ax.plot(grade, t[nome], '.-', lw=1.2, label=rotulo)
    ax.set(title="Brasil diário: prever amanhã com os três dias anteriores — lacunas preservadas", ylabel="Potência AC média diária (kW)", xlabel="Data")
    ax.grid(alpha=.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out / "previsoes_diarias.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))
    for ax, metrica in zip(axes, ["MAE_kW", "RMSE_kW"]):
        ax.barh(m.modelo, m[metrica], color=["#dc902d" if s else "#4185ad" for s in m.escolhido_validacao_chronos])
        ax.invert_yaxis()
        ax.set_xlabel(metrica.replace("_", " "))
        ax.grid(axis="x", alpha=.25)
    fig.suptitle("Mesmos 23 alvos diários — LoRA: uma semente; MLP/LSTM: média de cinco sementes")
    fig.tight_layout()
    fig.savefig(out / "comparacao_diaria.png", dpi=160)
    plt.close(fig)
    a = pd.read_csv(out / "auditoria_calendario_brasil.csv", parse_dates=["timestamp"])
    fig, ax = plt.subplots(figsize=(15, 3))
    ax.scatter(a.timestamp, a.Active_Power, s=13, label="Dias aprovados (potência tratada)")
    faltantes = a.Active_Power.isna()
    ax.scatter(a.loc[faltantes, 'timestamp'], np.zeros(faltantes.sum()), marker='|', color='tab:red', label="Dias ausentes/reprovados")
    ax.set(ylabel="Potência média (kW)", title="Brasil: calendário diário e interrupções em 2025")
    ax.legend()
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out / "faltantes_diarios.png", dpi=160)
    plt.close(fig)
