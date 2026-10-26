"""Imputação diária retrospectiva, com validação por blocos e rastreabilidade.

As estimativas não substituem medições de referência para avaliar previsões.
O argumento ``indices_doadores`` restringe o ajuste aos dias de treino quando
estas funções forem reutilizadas dentro de uma divisão temporal.
"""

import numpy as np
import pandas as pd
from sklearn.impute import KNNImputer
from sklearn.preprocessing import StandardScaler


def calendario_diario(dados):
    diario = dados.set_index("timestamp").sort_index().copy()
    if not diario.index.is_unique:
        raise ValueError("Há datas diárias duplicadas.")
    indice = pd.date_range(diario.index.min(), diario.index.max(), freq="D", name="timestamp")
    return diario.reindex(indice)


def tamanho_lacunas(serie):
    faltante = serie.isna()
    grupos = faltante.ne(faltante.shift()).cumsum()
    return faltante.groupby(grupos).transform("sum").where(faltante, 0).astype(int)


def interpolar_interno(serie, limite=None):
    """Preenche somente blocos internos inteiros dentro do limite solicitado."""
    interpolada = serie.interpolate(method="time", limit_area="inside")
    if limite is None:
        return interpolada
    permitida = serie.isna() & tamanho_lacunas(serie).le(limite)
    return serie.mask(permitida, interpolada)


def estimar_knn(serie, vizinhos=5, indices_doadores=None):
    """KNN com tempo e sazonalidade; nunca usa potência para estimar o clima.

    Como uma estação inteira pode estar ausente, os preditores são o calendário:
    seno/cosseno do dia do ano e tendência temporal. Não são dados externos.
    A escala e o KNN são ajustados somente em valores realmente observados.
    """
    doadores = serie.notna()
    if indices_doadores is not None:
        doadores &= serie.index.isin(indices_doadores)
    if not doadores.any():
        return pd.Series(np.nan, index=serie.index, name=serie.name)
    periodo = np.where(serie.index.is_leap_year, 366.0, 365.0)
    angulo = 2 * np.pi * (serie.index.dayofyear - 1) / periodo
    matriz = pd.DataFrame({
        "valor": serie,
        "tempo_anos": (serie.index - pd.Timestamp("2000-01-01")).days / 365.2425,
        "seno_anual": np.sin(angulo),
        "cosseno_anual": np.cos(angulo),
    }, index=serie.index)
    escala = StandardScaler().fit(matriz.loc[doadores])
    ajustada = escala.transform(matriz.loc[doadores])
    consulta = escala.transform(matriz)
    # Esconder valores fora do conjunto doador também na consulta permite
    # testar a reconstrução de observações sem que elas entrem no ajuste.
    consulta[~doadores.to_numpy(), 0] = np.nan
    modelo = KNNImputer(n_neighbors=min(vizinhos, int(doadores.sum())), weights="distance")
    modelo.fit(ajustada)
    reconstruida = escala.inverse_transform(modelo.transform(consulta))[:, 0]
    return pd.Series(reconstruida, index=serie.index, name=serie.name)


def validar_metodos(dados, blocos=(1, 7, 30), repeticoes=4, candidatos=(3, 5, 7), seed=42):
    """Oculta blocos observados; compara somente com seus valores originais.

    Este ensaio mede reconstrução retrospectiva, e não previsão de futuro.
    Blocos de 208 dias não são validáveis com o histórico meteorológico atual.
    """
    rng = np.random.default_rng(seed)
    registros = []
    for coluna in dados:
        original = dados[coluna].astype(float)
        if original.notna().sum() < 4:
            continue
        for dias in blocos:
            inicios = [
                inicio for inicio in range(1, len(original) - dias)
                if original.iloc[inicio - 1:inicio + dias + 1].notna().all()
            ]
            if not inicios:
                continue
            escolhidos = rng.choice(inicios, size=min(repeticoes, len(inicios)), replace=False)
            for repeticao, inicio in enumerate(escolhidos):
                ocultos = original.index[inicio:inicio + dias]
                visivel = original.copy()
                visivel.loc[ocultos] = np.nan
                escala = float(visivel.std())
                if not np.isfinite(escala) or escala < 1e-12:
                    escala = max(abs(float(visivel.mean())), 1.0)
                previsoes = {"linear": interpolar_interno(visivel)}
                previsoes.update({f"knn_{k}": estimar_knn(visivel, k) for k in candidatos})
                for metodo, previsao in previsoes.items():
                    erro = (previsao.loc[ocultos] - original.loc[ocultos]).to_numpy()
                    if not np.isfinite(erro).all():
                        raise ValueError(f"Falha na validação: {coluna}, {metodo}.")
                    rmse = float(np.sqrt(np.mean(erro ** 2)))
                    registros.append({
                        "coluna": coluna, "metodo": metodo, "bloco_dias": dias,
                        "repeticao": repeticao, "inicio": ocultos.min(), "fim": ocultos.max(),
                        "pontos": len(erro), "MAE": float(np.mean(np.abs(erro))),
                        "RMSE": rmse, "NRMSE": rmse / escala,
                    })
    detalhes = pd.DataFrame(registros)
    if detalhes.empty:
        raise ValueError("Não há blocos observados suficientes para validar os métodos.")
    resumo = detalhes.groupby(["coluna", "metodo", "bloco_dias"], as_index=False).agg(
        MAE=("MAE", "mean"), RMSE=("RMSE", "mean"), NRMSE=("NRMSE", "mean"),
        pontos=("pontos", "sum"), repeticoes=("repeticao", "count"),
    )
    return detalhes, resumo


def imputar_diario(dados, validacao, limite_linear=2, indices_doadores=None):
    """Linear curta; método validado em blocos médios; KNN nos demais casos.

    Dados observados são preservados. Colunas sem qualquer observação permanecem
    ausentes. Blocos maiores que os ensaiados são identificados no relatório.
    """
    resultado = dados.copy()
    indicadores = pd.DataFrame(index=dados.index)
    escolhas = []
    # Cada tamanho de bloco tem o mesmo peso na escolha de k.
    scores = validacao.groupby(["coluna", "metodo"]).NRMSE.mean()
    for coluna in dados:
        original = dados[coluna].astype(float)
        faltante = original.isna()
        indicadores[f"{coluna}__imputado"] = False
        indicadores[f"{coluna}__metodo"] = np.where(faltante, "sem_dados", "observado")
        indicadores[f"{coluna}__lacuna_dias"] = tamanho_lacunas(original)
        indicadores[f"{coluna}__alem_validacao"] = False
        if not original.notna().any():
            continue
        notas_coluna = scores.loc[coluna]
        notas = notas_coluna.loc[notas_coluna.index.str.startswith("knn_")].sort_values(kind="stable")
        melhor = notas.index[0]
        k = int(melhor.split("_")[1])
        linear_venceu = notas_coluna.loc["linear"] <= notas.iloc[0]
        maior_bloco_testado = int(validacao.loc[validacao.coluna.eq(coluna), "bloco_dias"].max())
        limite = maior_bloco_testado if linear_venceu else limite_linear
        fonte = original.copy()
        if indices_doadores is not None:
            fonte.loc[~fonte.index.isin(indices_doadores)] = np.nan
        linear = interpolar_interno(fonte, limite)
        usar_linear = faltante & linear.notna() & tamanho_lacunas(original).le(limite)
        resultado.loc[usar_linear, coluna] = linear.loc[usar_linear]
        usar_knn = resultado[coluna].isna()
        # Doadores sempre vêm das medições, sem reaproveitar valores interpolados.
        knn = estimar_knn(original, k, indices_doadores)
        usar_knn &= knn.notna()
        resultado.loc[usar_knn, coluna] = knn.loc[usar_knn]
        indicadores.loc[usar_linear, f"{coluna}__metodo"] = "linear"
        indicadores.loc[usar_knn, f"{coluna}__metodo"] = melhor
        indicadores[f"{coluna}__imputado"] = faltante & resultado[coluna].notna()
        indicadores[f"{coluna}__alem_validacao"] = (
            indicadores[f"{coluna}__imputado"]
            & indicadores[f"{coluna}__lacuna_dias"].gt(maior_bloco_testado)
        )
        if fonte.notna().any():
            dias = (original.index - pd.Timestamp("2000-01-01")).days.to_numpy()
            dias_doadores = dias[fonte.notna().to_numpy()]
            distancia = np.abs(dias[:, None] - dias_doadores[None, :]).min(axis=1)
            indicadores[f"{coluna}__distancia_observacao_dias"] = distancia
        escolhas.append({
            "coluna": coluna, "knn_escolhido": melhor,
            "melhor_metodo_validacao": "linear" if linear_venceu else melhor,
            "NRMSE_validacao_knn": float(notas.iloc[0]),
            "NRMSE_validacao_linear": float(notas_coluna.loc["linear"]),
            "limite_linear_aplicado_dias": limite,
            "maior_bloco_validado_dias": maior_bloco_testado,
            "dias_lineares": int(usar_linear.sum()), "dias_knn": int(usar_knn.sum()),
        })
        pd.testing.assert_series_equal(resultado.loc[~faltante, coluna], original.loc[~faltante])
    return resultado, indicadores, pd.DataFrame(escolhas)
