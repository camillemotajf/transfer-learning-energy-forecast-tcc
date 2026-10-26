"""Auditoria, seleção somente em treino/validação e contrato de entradas."""

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from ..caminhos import CaminhosProjeto


ALVO = "Active_Power"
VENTO = {"Wind_Speed", "Wind_Direction"}


def caminhos_experimento(pasta=None):
    pasta = Path(pasta or CaminhosProjeto().raiz / "experimentos/australia_deep_learning").resolve()
    for nome in ["dados", "resultados", "modelos", "figuras"]:
        (pasta / nome).mkdir(parents=True, exist_ok=True)
    return pasta


def sha256(arquivo):
    return hashlib.sha256(Path(arquivo).read_bytes()).hexdigest()


def carregar_config(pasta=None):
    pasta = caminhos_experimento(pasta)
    config = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    if config["horizonte_dias"] != 1:
        raise ValueError("Esta implementação é para previsão diária de um dia à frente.")
    if pd.Timestamp(config["fim_treino"]) >= pd.Timestamp(config["fim_validacao"]):
        raise ValueError("Treino precisa preceder validação.")
    for colunas in config["grupos_entradas"].values():
        if VENTO.intersection(colunas):
            raise ValueError("Vento foi excluído pelo usuário e não pode entrar nos modelos.")
        if set(config["variaveis_excluidas"]).intersection(colunas):
            raise ValueError("Um grupo contém variáveis explicitamente excluídas.")
    return config


def limpar_diario(recebido, config):
    """Conserva o calendário e zeros medidos; nunca preenche o alvo."""
    original = recebido.copy().sort_index()
    if not original.index.is_unique or not original.index.equals(original.index.normalize()):
        raise ValueError("Esperadas datas diárias únicas, sem horas.")
    calendario = pd.date_range(original.index.min(), original.index.max(), freq="D", name="timestamp")
    original = original.reindex(calendario)
    limpo = original.replace([np.inf, -np.inf], np.nan).copy()
    invalidos = original.notna() & limpo.isna()
    limites = dict(config["limites_operacionais"], Active_Power=[0., None])
    for coluna, (inferior, superior) in limites.items():
        ruim = limpo[coluna].notna() & limpo[coluna].lt(inferior)
        if superior is not None:
            ruim |= limpo[coluna].gt(superior)
        invalidos[coluna] |= ruim
        limpo.loc[ruim, coluna] = np.nan
    return original, limpo, invalidos


def entradas_causais(limpo, config):
    """Somente ffill meteorológico limitado ao passado; potência não é imputada."""
    entradas = limpo.copy()
    estimados = pd.DataFrame(False, index=limpo.index, columns=limpo.columns)
    for coluna in config["limites_operacionais"]:
        if coluna in VENTO:
            continue
        reconstruido = limpo[coluna].ffill(limit=config["limite_ffill_meteorologia_dias"])
        estimados[coluna] = limpo[coluna].isna() & reconstruido.notna()
        entradas[coluna] = reconstruido
    periodo = np.where(entradas.index.is_leap_year, 366., 365.)
    angulo = 2 * np.pi * (entradas.index.dayofyear - 1) / periodo
    entradas["dia_ano_sin"] = np.sin(angulo)
    entradas["dia_ano_cos"] = np.cos(angulo)
    estimados["dia_ano_sin"] = False
    estimados["dia_ano_cos"] = False
    pd.testing.assert_series_equal(entradas[ALVO], limpo[ALVO])
    return entradas, estimados


def criar_janelas(entradas, alvo, colunas, lag, config, estimados=None):
    """Entrada t-L..t-1, alvo t; datas ausentes do alvo quebram o histórico."""
    if lag < 1 or not entradas.index.is_unique:
        raise ValueError("Lag positivo e datas únicas são obrigatórios.")
    if not entradas.index.to_series().diff().dropna().eq(pd.Timedelta(days=1)).all():
        raise ValueError("Reindexe o calendário diário antes de montar janelas.")
    matriz = entradas[colunas].to_numpy(dtype=float)
    ys = alvo.reindex(entradas.index).to_numpy(dtype=float)
    xs, valores, datas, inicios, fins, fracoes = [], [], [], [], [], []
    for i in range(lag, len(entradas)):
        trecho = matriz[i - lag:i]
        if not np.isfinite(trecho).all() or not np.isfinite(ys[i]):
            continue
        # O alvo pode ser válido enquanto falta potência em algum dia anterior.
        if not np.isfinite(ys[i - lag:i]).all():
            continue
        xs.append(trecho)
        valores.append(ys[i])
        datas.append(entradas.index[i])
        inicios.append(entradas.index[i - lag])
        fins.append(entradas.index[i - 1])
        fracoes.append(float(estimados.iloc[i - lag:i][colunas].to_numpy().mean()) if estimados is not None else 0.)
    n_features = len(colunas)
    x = np.asarray(xs, dtype=np.float32).reshape(-1, lag, n_features)
    y = np.asarray(valores, dtype=np.float32)
    metadados = pd.DataFrame({"timestamp": pd.to_datetime(datas), "entrada_inicio": pd.to_datetime(inicios),
                              "entrada_fim": pd.to_datetime(fins), "fracao_inputs_estimados": fracoes})
    metadados["particao"] = np.select(
        [metadados.timestamp.le(config["fim_treino"]), metadados.timestamp.le(config["fim_validacao"])],
        ["treino", "validacao"], default="teste")
    return x, y, metadados


def ajustar_escalas(entradas, alvo, colunas, fim_treino):
    treino = entradas.index <= pd.Timestamp(fim_treino)
    x_scaler = StandardScaler().fit(entradas.loc[treino, colunas])
    y_scaler = StandardScaler().fit(alvo.loc[treino].dropna().to_numpy().reshape(-1, 1))
    return x_scaler, y_scaler


def escalar_x(x, scaler):
    formato = x.shape
    return ((x.reshape(-1, formato[-1]) - scaler.mean_) / scaler.scale_).reshape(formato).astype(np.float32)


def auditar(recebido, original, limpo, invalidos, estimados, config):
    treino = original.index <= pd.Timestamp(config["fim_treino"])
    resumo = pd.DataFrame({"registros_recebidos": recebido.count(), "ausentes_no_csv": recebido.isna().sum(),
                           "ausentes_calendario": original.isna().sum(), "invalidos_operacionais": invalidos.sum(),
                           "faltantes_treino_apos_qc_pct": 100 * limpo.loc[treino].isna().mean(),
                           "inputs_ffill_causal": estimados.reindex(columns=original.columns).sum()})
    resumo["uso"] = ["excluída pelo usuário/transferibilidade" if col in config["variaveis_excluidas"] else "alvo e histórico" if col == ALVO else "candidata meteorológica" for col in resumo.index]
    diario = pd.DataFrame({"registro_original": original.index.isin(recebido.index),
                          "colunas_ausentes": original.isna().sum(axis=1), "colunas_invalidas": invalidos.sum(axis=1),
                          "alvo_valido": limpo[ALVO].notna(), "inputs_preenchidos_passado": estimados.sum(axis=1)}, index=original.index)
    return resumo, diario


def selecionar(entradas, alvo, limpo, config, estimados):
    candidatos, rejeicoes = [], []
    for grupo, cols in config["grupos_entradas"].items():
        for coluna in cols:
            if coluna not in limpo:
                continue
            pct = 100 * limpo.loc[:config["fim_treino"], coluna].isna().mean()
            if pct > config["max_faltantes_treino_pct"]:
                rejeicoes.append({"grupo": grupo, "variavel": coluna, "faltantes_treino_pct": pct})
        if any(r["grupo"] == grupo for r in rejeicoes):
            continue
        sx, sy = ajustar_escalas(entradas, alvo, cols, config["fim_treino"])
        for lag in config["lags_candidatos"]:
            x, y, meta = criar_janelas(entradas, alvo, cols, lag, config, estimados)
            candidatos.append({"grupo": grupo, "colunas": cols, "lag": lag, "x": escalar_x(x, sx),
                               "y": y, "meta": meta, "sx": sx, "sy": sy})
    datas_comuns = None
    for candidato in candidatos:
        datas = pd.Index(candidato["meta"].loc[candidato["meta"].particao.eq("validacao"), "timestamp"])
        datas_comuns = datas if datas_comuns is None else datas_comuns.intersection(datas)
    if datas_comuns is None or len(datas_comuns) < 30:
        raise ValueError("Validação comum insuficiente para comparar os grupos/lags.")
    scores = []
    for item in candidatos:
        meta, x, y, sy = item["meta"], item["x"], item["y"], item["sy"]
        tr = meta.particao.eq("treino").to_numpy()
        va = (meta.particao.eq("validacao") & meta.timestamp.isin(datas_comuns)).to_numpy()
        for alpha in config["alphas_ridge"]:
            reg = Ridge(alpha=alpha).fit(x[tr].reshape(tr.sum(), -1), sy.transform(y[tr, None]).ravel())
            pred = sy.inverse_transform(reg.predict(x[va].reshape(va.sum(), -1))[:, None]).ravel().clip(0)
            erro = pred - y[va]
            scores.append({"grupo": item["grupo"], "lag_dias": item["lag"], "alpha_ridge": alpha,
                           "n_features": len(item["colunas"]), "janelas_treino": int(tr.sum()),
                           "janelas_validacao_comum": int(va.sum()), "MAE_validacao": float(np.abs(erro).mean()),
                           "RMSE_validacao": float(np.sqrt(np.mean(erro ** 2)))})
    tabela = pd.DataFrame(scores).sort_values(["RMSE_validacao", "n_features", "lag_dias", "alpha_ridge"]).reset_index(drop=True)
    melhor = tabela.iloc[0]
    escolhido = next(x for x in candidatos if x["grupo"] == melhor.grupo and x["lag"] == melhor.lag_dias)
    return escolhido, tabela, pd.DataFrame(rejeicoes), datas_comuns


def preparar_experimento(pasta=None):
    pasta = caminhos_experimento(pasta)
    config = carregar_config(pasta)
    fonte = CaminhosProjeto().brutos_australia / "base_diaria_australia.csv"
    recebido = pd.read_csv(fonte, parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    original, limpo, invalidos = limpar_diario(recebido, config)
    entradas, estimados = entradas_causais(limpo, config)
    resumo, diario = auditar(recebido, original, limpo, invalidos, estimados, config)
    escolhido, scores, rejeitados, datas_comuns = selecionar(entradas, limpo[ALVO], limpo, config, estimados)
    cols, lag = escolhido["colunas"], int(escolhido["lag"])
    x, y, meta = criar_janelas(entradas, limpo[ALVO], cols, lag, config, estimados)
    sx, sy = escolhido["sx"], escolhido["sy"]
    x_norm = escalar_x(x, sx)
    y_norm = sy.transform(y[:, None]).ravel().astype(np.float32)
    particoes = []
    for particao in ["treino", "validacao", "teste"]:
        mask = meta.particao.eq(particao).to_numpy()
        if mask.sum() < 10:
            raise ValueError(f"Partição {particao} insuficiente.")
        np.savez_compressed(pasta / "dados" / f"{particao}.npz", X=x_norm[mask], y=y_norm[mask], y_original=y[mask],
                            datas=meta.loc[mask, "timestamp"].dt.strftime("%Y-%m-%d").to_numpy(dtype="U10"),
                            persistencia=entradas[ALVO].reindex(meta.loc[mask, "entrada_fim"]).to_numpy(dtype=np.float32))
        particoes.append({"particao": particao, "janelas": int(mask.sum()),
                          "primeiro_alvo": str(meta.loc[mask, "timestamp"].min().date()),
                          "ultimo_alvo": str(meta.loc[mask, "timestamp"].max().date())})
    # Diagnóstico de correlação usa somente alvos e lags anteriores dentro do treino.
    correlacoes = []
    candidatas = list(dict.fromkeys(col for grupo in config["grupos_entradas"].values() for col in grupo))
    for col in candidatas:
        for atraso in range(1, 15):
            pares = pd.concat([limpo[ALVO], entradas[col].shift(atraso).rename("input")], axis=1).loc[:config["fim_treino"]].dropna()
            correlacoes.append({"variavel": col, "lag_dias": atraso, "pares_treino": len(pares),
                               "spearman_treino": float(pares[ALVO].corr(pares.input, method="spearman"))})
    correlacoes = pd.DataFrame(correlacoes)
    melhores_lags = correlacoes.assign(absoluto=lambda t: t.spearman_treino.abs()).sort_values("absoluto", ascending=False).drop_duplicates("variavel").drop(columns="absoluto")
    resumo.rename_axis("variavel").reset_index().to_csv(pasta / "resultados/faltantes_por_variavel.csv", index=False)
    diario.reset_index().to_csv(pasta / "resultados/faltantes_por_dia.csv", index=False)
    scores.to_csv(pasta / "resultados/selecao_inputs_lags_validacao.csv", index=False)
    correlacoes.to_csv(pasta / "resultados/correlacoes_lags_treino.csv", index=False)
    melhores_lags.to_csv(pasta / "resultados/melhor_lag_correlacao_treino.csv", index=False)
    pd.DataFrame(particoes).to_csv(pasta / "resultados/particoes.csv", index=False)
    meta.to_csv(pasta / "resultados/janelas.csv", index=False)
    limpo.reset_index().to_csv(pasta / "dados/calendario_auditado.csv", index=False)
    entradas[cols].reset_index().to_csv(pasta / "dados/entradas_causais.csv", index=False)
    joblib.dump({"x": sx, "y": sy, "colunas": cols}, pasta / "dados/escalas_treino.joblib")
    contrato = {"alvo": ALVO, "horizonte_dias": 1, "emissao": "Após o fechamento do dia anterior ao alvo",
                "grupo_selecionado": escolhido["grupo"], "variaveis_por_passo": cols,
                "lags_dias": list(range(1, lag + 1)), "lookback": lag,
                "ordem_tensor": "amostra, tempo do mais antigo ao mais recente, variáveis na ordem declarada",
                "shape_mlp": [lag * len(cols)], "shape_lstm": [lag, len(cols)],
                "selecao": "Menor RMSE Ridge na validação comum; teste não participa. Proxy de seleção, não ótimo garantido para as redes.",
                "n_alvos_validacao_comum": len(datas_comuns),
                "fonte_sha256": sha256(fonte), "config_sha256": sha256(pasta / "config.json"),
                "fim_treino": config["fim_treino"], "fim_validacao": config["fim_validacao"],
                "x_media_treino": sx.mean_.tolist(), "x_escala_treino": sx.scale_.tolist(),
                "y_media_treino": float(sy.mean_[0]), "y_escala_treino": float(sy.scale_[0]),
                "vento_excluido": True, "unidade_alvo": "Unidade numérica da fonte; potência nominal/unidade física ainda precisam ser confirmadas",
                "transferencia": "Reproduzir variáveis, ordem e lags no Brasil; ajustar escalas brasileiras somente no treino local. Padronização estatística não é potência por unidade de capacidade nominal."}
    (pasta / "dados/contrato_inputs.json").write_text(json.dumps(contrato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estado = {"linhas_recebidas": len(recebido), "dias_calendario": len(original),
              "datas_ausentes": int((~original.index.isin(recebido.index)).sum()),
              "alvos_ausentes_ou_invalidos": int(limpo[ALVO].isna().sum()),
              "alvos_imputados": 0, "invalidos_por_variavel": invalidos.sum().to_dict(),
              "limites": config["limites_operacionais"], "particoes": particoes}
    (pasta / "resultados/resumo_preparacao.json").write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _graficos(pasta, original, invalidos, scores, correlacoes, config)
    return {"resumo": resumo, "diario": diario, "contrato": contrato, "scores": scores,
            "correlacoes": correlacoes, "melhores_lags": melhores_lags, "particoes": pd.DataFrame(particoes), "estado": estado}


def garantir_dados(pasta=None):
    pasta = caminhos_experimento(pasta)
    arquivo = pasta / "dados/contrato_inputs.json"
    if not arquivo.exists():
        preparar_experimento(pasta)
    contrato = json.loads(arquivo.read_text(encoding="utf-8"))
    fonte = CaminhosProjeto().brutos_australia / "base_diaria_australia.csv"
    if contrato["config_sha256"] != sha256(pasta / "config.json") or contrato["fonte_sha256"] != sha256(fonte):
        raise ValueError("Fonte ou configuração mudou. Execute novamente o notebook 01 antes de treinar.")
    return pasta, contrato


def _graficos(pasta, original, invalidos, scores, correlacoes, config):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(15, 8))
    estado = np.where(original.isna(), 1, np.where(invalidos, 2, 0)).T
    from matplotlib.colors import ListedColormap
    im = axes[0].imshow(estado, aspect="auto", interpolation="none", cmap=ListedColormap(["#e8f0e9", "#c54e45", "#dca13a"]), vmin=0, vmax=2)
    axes[0].set_yticks(range(len(original.columns)), original.columns, fontsize=8)
    anos = original.index[original.index.is_year_start]
    axes[0].set_xticks(original.index.get_indexer(anos), anos.year)
    axes[0].set_title("Austrália — calendário completo; verde: presente, vermelho: ausente, amarelo: fora dos limites operacionais")
    axes[1].plot(original.index, original[ALVO], linewidth=.6)
    axes[1].axvline(pd.Timestamp(config["fim_treino"]), color="#a34739", linestyle="--", label="Fim do treino")
    axes[1].axvline(pd.Timestamp(config["fim_validacao"]), color="#388347", linestyle="--", label="Fim da validação")
    axes[1].set_ylabel("Potência média — unidade da fonte")
    axes[1].legend()
    axes[1].grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(pasta / "figuras/faltantes_e_particoes.png", dpi=140)
    plt.close(fig)
    tabela = correlacoes.pivot(index="variavel", columns="lag_dias", values="spearman_treino")
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(tabela, aspect="auto", vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_yticks(range(len(tabela)), tabela.index, fontsize=8)
    ax.set_xticks(range(len(tabela.columns)), tabela.columns)
    ax.set(xlabel="Lag em dias (somente passado)", title="Correlação de Spearman no treino — diagnóstico, não causalidade")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(pasta / "figuras/correlacoes_lags_treino.png", dpi=140)
    plt.close(fig)
    melhor_alpha = scores.sort_values("RMSE_validacao").drop_duplicates(["grupo", "lag_dias"])
    tabela = melhor_alpha.pivot(index="lag_dias", columns="grupo", values="RMSE_validacao")
    ax = tabela.plot.bar(figsize=(12, 5), rot=0)
    ax.set(ylabel="RMSE — unidade da fonte", xlabel="Histórico em dias", title="Seleção inicial por Ridge — mesmos alvos de validação, teste intocado")
    ax.grid(axis="y", alpha=.2)
    ax.figure.tight_layout()
    ax.figure.savefig(pasta / "figuras/selecao_inputs_lags.png", dpi=140)
    plt.close(ax.figure)
