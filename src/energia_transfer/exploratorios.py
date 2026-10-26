"""Reprodução das tentativas anteriores; não são a base recomendada de treino.

Mantém o filtro textual FX e o calendário antigo para permitir comparação
com os resultados históricos. A seleção atual fica em base_consecutiva.py.
"""

import json

import pandas as pd

from . import imputacao
from .caminhos import CaminhosProjeto
from .meteorologia_publica import COLUNAS_ELETRICAS, agregar_era5, comparar_com_estacao, obter_era5, preencher_com_publicos
from .preparacao import preparar_brasil_observado


def executar_imputacao_diaria(caminhos=None):
    c = caminhos or CaminhosProjeto()
    c.preparar_saidas()
    preparacao = preparar_brasil_observado(c, filtro_codigo="07-07FX")
    diario = preparacao["diario"]
    observado = imputacao.calendario_diario(diario)
    colunas = observado.columns.tolist()
    com_dados = [col for col in colunas if observado[col].notna().any()]
    detalhes, validacao = imputacao.validar_metodos(observado[com_dados], blocos=(1, 7, 30), repeticoes=4, candidatos=(3, 5, 7), seed=42)
    reconstruido, indicadores, escolhas = imputacao.imputar_diario(observado, validacao, limite_linear=2)
    relatorio = pd.DataFrame({"dias_observados": observado.count(), "faltantes_antes_pct": 100 * observado.isna().mean(),
                              "maior_lacuna_dias": [int(imputacao.tamanho_lacunas(observado[col]).max()) for col in colunas]}, index=colunas)
    relatorio["dias_interpolados"] = [int(indicadores[f"{col}__metodo"].str.startswith("linear").sum()) for col in colunas]
    relatorio["dias_knn"] = [int(indicadores[f"{col}__metodo"].str.startswith("knn_").sum()) for col in colunas]
    relatorio["faltantes_depois_pct"] = 100 * reconstruido.isna().mean()
    relatorio["estimados_pct"] = [100 * indicadores[f"{col}__imputado"].mean() for col in colunas]
    relatorio["dias_estimados_alem_validacao"] = [int(indicadores[f"{col}__alem_validacao"].sum()) for col in colunas]
    for coluna in ["cobertura_potencia_pct", "cobertura_estacao_pct"]:
        indicadores[coluna] = preparacao["qualidade"][coluna].reindex(observado.index).fillna(0)
    indicadores["potencia_original_observada"] = observado.Active_Power.notna()
    indicadores["avaliacao_potencia_permitida"] = indicadores.potencia_original_observada & indicadores.cobertura_potencia_pct.ge(80)
    pd.testing.assert_frame_equal(reconstruido.where(observado.notna()), observado)
    reconstruido.reset_index().to_csv(c.exploratorios / "base_diaria_leopoldo_imputada.csv", index=False)
    reconstruido[com_dados].reset_index().to_csv(c.exploratorios / "base_diaria_leopoldo_comum_imputada.csv", index=False)
    for nome, tabela in {
        "indicadores_imputacao_leopoldo.csv": indicadores.reset_index(),
        "relatorio_imputacao_leopoldo.csv": relatorio.rename_axis("coluna").reset_index(),
        "validacao_imputacao_leopoldo.csv": validacao, "validacao_imputacao_detalhada.csv": detalhes,
        "metodos_imputacao_leopoldo.csv": escolhas,
    }.items():
        tabela.to_csv(c.exploratorio_imputacao / nome, index=False)
    _grafico_knn(c, observado, reconstruido, indicadores)
    return {"observado": observado, "reconstruido": reconstruido, "indicadores": indicadores,
            "validacao": validacao, "detalhes": detalhes, "relatorio": relatorio, "escolhas": escolhas}


def comparar_fontes_publicas(caminhos=None):
    c = caminhos or CaminhosProjeto()
    c.preparar_saidas()
    if not (c.exploratorio_imputacao / "indicadores_imputacao_leopoldo.csv").exists():
        executar_imputacao_diaria(c)
    observado = imputacao.calendario_diario(pd.read_csv(c.exploratorios / "base_diaria_leopoldo.csv", parse_dates=["timestamp"]))
    reconstruido = pd.read_csv(c.exploratorios / "base_diaria_leopoldo_imputada.csv", parse_dates=["timestamp"]).set_index("timestamp")
    indicadores = pd.read_csv(c.exploratorio_imputacao / "indicadores_imputacao_leopoldo.csv", parse_dates=["timestamp"]).set_index("timestamp")
    config = json.loads(c.configuracao_usina.read_text(encoding="utf-8"))
    geometria = config if config.get("geometria_habilitada") else None
    bruto, meta = obter_era5(c.cache_era5, "2025-01-02", "2026-01-01", latitude=config["latitude"], longitude=config["longitude"], altitude=config["altitude_m"])
    horario, publico = agregar_era5(bruto, observado.index.min(), observado.index.max(), geometria)
    comparacao = comparar_com_estacao(observado, publico, indicadores.cobertura_estacao_pct, cobertura_minima=80)
    preenchido, origens, relatorio = preencher_com_publicos(observado, publico, eletrico_estimado=reconstruido)
    for coluna in ["cobertura_potencia_pct", "cobertura_estacao_pct", "avaliacao_potencia_permitida"]:
        origens[coluna] = indicadores[coluna]
    for coluna in COLUNAS_ELETRICAS:
        origens[f"{coluna}__metodo_eletrico"] = indicadores[f"{coluna}__metodo"]
    meteo_cols = [col for col in observado if col not in COLUNAS_ELETRICAS and col in publico]
    homogeneo = preenchido.copy()
    homogeneo[meteo_cols] = publico[meteo_cols]
    for nome, tabela in {
        "meteorologia_era5_diaria.csv": publico.reset_index(),
        "base_diaria_leopoldo_meteo_publica.csv": preenchido.reset_index(),
        "base_diaria_leopoldo_meteo_homogenea.csv": homogeneo.reset_index(),
    }.items():
        tabela.to_csv(c.exploratorios / nome, index=False)
    for nome, tabela in {"origens_meteorologia_publica.csv": origens.reset_index(),
                         "relatorio_meteorologia_publica.csv": relatorio, "comparacao_era5_estacao.csv": comparacao}.items():
        tabela.to_csv(c.exploratorio_meteo / nome, index=False)
    sensibilidade = []
    if geometria:
        referencia = publico.Radiation_Global_Tilted
        for azimute in (0, 20, 340):
            if azimute == 0:
                alternativa = referencia
            else:
                _, simulado = agregar_era5(bruto, observado.index.min(), observado.index.max(), dict(geometria, azimute_norte_horario_graus=azimute))
                alternativa = simulado.Radiation_Global_Tilted
            sensibilidade.append({"azimute_norte_horario_graus": azimute, "inclinacao_graus": 20,
                                   "variacao_energia_periodo_pct": 100 * (alternativa.sum() / referencia.sum() - 1),
                                   "max_variacao_diaria_absoluta_pct": float((100 * (alternativa / referencia - 1)).abs().max())})
    sensibilidade = pd.DataFrame(sensibilidade)
    sensibilidade.to_csv(c.exploratorio_meteo / "sensibilidade_azimute_era5.csv", index=False)
    _grafico_publico(c, observado, reconstruido, publico, preenchido)
    return {"observado": observado, "publico": publico, "preenchido": preenchido,
            "homogeneo": homogeneo, "comparacao": comparacao, "relatorio": relatorio,
            "sensibilidade": sensibilidade, "metadados": meta}


def _grafico_knn(c, observado, reconstruido, indicadores):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharex=True)
    for ax, coluna in zip(axes.flat, ["Active_Power", "Weather_Temperature_Celsius", "Global_Horizontal_Radiation", "Wind_Speed"]):
        ax.plot(reconstruido.index, reconstruido[coluna], color="#c67a21", alpha=.65, label="Reconstruído linear/KNN")
        ax.plot(observado.index, observado[coluna], color="#176b91", linewidth=1, label="Observado — filtro histórico")
        fora = indicadores[f"{coluna}__alem_validacao"]
        ax.scatter(reconstruido.index[fora], reconstruido.loc[fora, coluna], s=7, color="#b34236", label="Lacuna além da validação")
        ax.set_title(coluna)
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle("Exploratório — imputação diária anterior, sem validação do semestre ausente")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(c.figuras / "diagnostico_imputacao_leopoldo.png", dpi=150)
    plt.close(fig)


def _grafico_publico(c, observado, reconstruido, publico, preenchido):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(15, 10), sharex=True)
    for ax, coluna in zip(axes.flat, ["Weather_Temperature_Celsius", "Wind_Speed", "Global_Horizontal_Radiation", "Radiation_Global_Tilted", "Weather_Relative_Humidity", "Weather_Daily_Rainfall"]):
        ax.plot(reconstruido.index, reconstruido[coluna], color="#999999", linestyle=":", label="Linear/KNN anterior")
        ax.plot(publico.index, publico[coluna], color="#2b875d", linewidth=1, label="ERA5/Perez")
        ax.plot(observado.index, observado[coluna], color="#24658e", linewidth=1, label="Estação")
        ax.set_title(coluna, fontsize=9)
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.suptitle("Exploratório — comparação com o preenchimento meteorológico anterior")
    fig.tight_layout()
    fig.savefig(c.figuras / "diagnostico_meteorologia_publica.png", dpi=150)
    plt.close(fig)
