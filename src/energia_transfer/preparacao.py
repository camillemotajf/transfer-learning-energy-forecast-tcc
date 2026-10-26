"""Rotinas diárias históricas, preservadas para os resultados anteriores.

O fluxo corrente em cinco minutos está em energia_transfer.intradiario.
"""

import json
import shutil

import pandas as pd

from .auditoria_base_original import FUSO, _limpar
from .caminhos import CaminhosProjeto
from .meteorologia_publica import agregar_era5, comparar_com_estacao, obter_era5


ELETRICAS = ["Active_Energy_Delivered_Received", "Current_Phase_Average", "Active_Power"]
FASES = ["phase_a_current_a", "phase_b_current_a", "phase_c_current_a"]
MAPA_ESTACAO = {
    "air_speed_med": "Wind_Speed", "air_temperature_med": "Weather_Temperature_Celsius",
    "ghi_irr_med": "Global_Horizontal_Radiation", "dir_vento_med": "Wind_Direction",
    "precipitacao_acc_day": "Weather_Daily_Rainfall", "poa_irr_med": "Radiation_Global_Tilted",
}


def preparar_australia(caminhos=None):
    """Usa a base diária recebida; refaz a agregação se o CSV intradiário existir."""
    c = caminhos or CaminhosProjeto()
    c.preparar_saidas()
    intradiario = c.brutos_australia / "87-Site_DKA-M9_A+C-Phases.csv"
    recebida = c.brutos_australia / "base_diaria_australia.csv"
    destino = c.processados_australia / "base_diaria_australia.csv"
    if intradiario.exists():
        bruto = pd.read_csv(intradiario)
        bruto["timestamp"] = pd.to_datetime(bruto.timestamp, errors="coerce", format="mixed")
        bruto = bruto.dropna(subset=["timestamp"]).sort_values("timestamp")
        diario = bruto.set_index("timestamp").select_dtypes(include="number").resample("D").mean().dropna(how="all").reset_index()
        diario.to_csv(destino, index=False)
        origem = "Agregado do CSV intradiário disponível em data/raw/australia."
    else:
        diario = pd.read_csv(recebida, parse_dates=["timestamp"])
        shutil.copyfile(recebida, destino)
        origem = "Base diária recebida no projeto; o CSV intradiário australiano não está incluído."
    if not diario.timestamp.is_unique or not diario.timestamp.is_monotonic_increasing:
        raise ValueError("A série australiana precisa estar ordenada e sem datas duplicadas.")
    cobertura = pd.DataFrame({"dias_validos": diario.drop(columns="timestamp").count(),
                              "faltantes_pct": 100 * diario.drop(columns="timestamp").isna().mean()})
    cobertura.rename_axis("coluna").reset_index().to_csv(c.raiz / "reports/metadados/qualidade_australia.csv", index=False)
    _grafico_australia(c, diario)
    return {"diario": diario, "qualidade": cobertura, "origem": origem}


def preparar_brasil_observado(caminhos=None, ano=2025, filtro_codigo=None):
    """Soma os oito inversores e agrega por dia. None usa a identidade da usina.

    O filtro textual é mantido somente para reproduzir o experimento histórico.
    A versão atual mantém todos os dias do calendário, inclusive dias sem dados.
    """
    c = caminhos or CaminhosProjeto()
    c.preparar_saidas()
    medidas_inv = ["total_active_power_w", "total_power_yields_kwh", *FASES]
    inv = pd.read_csv(c.brutos_brasil / "Leopoldo-fixa-inv.csv", usecols=[
        "datetime", "real_datetime", "meta.id_usina", "meta.id_inversor", "usine_code", "serial_number", *medidas_inv,
    ], low_memory=False)
    est = pd.read_csv(c.brutos_brasil / "Leopoldo-fixa-est.csv", usecols=[
        "datetime", "real_datetime", "meta.id_usina", "meta.id", "usine_code", "fail_read", *MAPA_ESTACAO,
    ], low_memory=False)
    identidade = inv.loc[inv["meta.id_usina"].eq(50)].groupby("meta.id_inversor").serial_number.nunique()
    if len(identidade) != 8 or not identidade.eq(1).all():
        raise ValueError("Conferir IDs e números de série dos oito inversores.")
    for bruto, equipamento, metricas in [(inv, "meta.id_inversor", medidas_inv), (est, "meta.id", list(MAPA_ESTACAO))]:
        bruto["t"] = pd.to_datetime(bruto.datetime, utc=True, format="mixed", errors="coerce").dt.tz_convert(FUSO)
        bruto[metricas] = bruto[metricas].apply(pd.to_numeric, errors="coerce")
    inv = _limpar(inv, "meta.id_inversor", medidas_inv, codigo=filtro_codigo)
    est = _limpar(est, "meta.id", list(MAPA_ESTACAO), codigo=filtro_codigo)
    if est["meta.id"].nunique() != 1:
        raise ValueError("Esperada exatamente uma estação.")
    inv["Active_Power"] = inv.total_active_power_w / 1000
    inv["Current_Phase_Average"] = inv[FASES].mean(axis=1, skipna=False)
    inv["Active_Energy_Delivered_Received"] = inv.total_power_yields_kwh
    usina = inv.groupby("slot")[ELETRICAS].sum(min_count=8)
    estacao = est.set_index("slot")[list(MAPA_ESTACAO)].rename(columns=MAPA_ESTACAO)
    colunas = pd.read_csv(c.brutos_australia / "base_diaria_australia.csv", nrows=0).columns.tolist()
    unificado = usina.join(estacao, how="outer").reindex(columns=colunas[1:]).sort_index().rename_axis("timestamp")
    # Retira apenas as horas locais fora do ano selecionado.
    unificado = unificado.loc[unificado.index.year == ano]
    diario = unificado.resample("D").mean()
    if filtro_codigo is None:
        diario = diario.reindex(pd.date_range(f"{ano}-01-01", f"{ano}-12-31", tz=FUSO, name="timestamp"))
    else:
        diario = diario.dropna(how="all")
    diario.index = diario.index.tz_localize(None)
    qualidade = pd.DataFrame({
        "potencia_completa": usina.Active_Power.notna().astype(int),
        "estacao_disponivel": estacao.notna().all(axis=1).astype(int),
    }).fillna(0).resample("D").sum()
    qualidade.index = qualidade.index.tz_localize(None)
    calendario = pd.date_range(diario.index.min(), diario.index.max(), name="timestamp")
    qualidade = qualidade.reindex(calendario, fill_value=0)
    qualidade["cobertura_potencia_pct"] = 100 * qualidade.potencia_completa / 288
    qualidade["cobertura_estacao_pct"] = 100 * qualidade.estacao_disponivel / 288
    saida = diario.reset_index().reindex(columns=colunas)
    if filtro_codigo is None:
        saida.to_csv(c.intermediarios_brasil / "base_diaria_leopoldo_observada.csv", index=False, date_format="%Y-%m-%d")
        qualidade.reset_index().to_csv(c.auditoria / "qualidade_base_observada.csv", index=False)
    else:
        saida.to_csv(c.exploratorios / "base_diaria_leopoldo.csv", index=False, date_format="%Y-%m-%d")
        qualidade.reset_index().to_csv(c.exploratorio_imputacao / "qualidade_base_observada.csv", index=False)
    return {"diario": saida, "qualidade": qualidade, "intervalos": unificado}


def preparar_meteorologia(caminhos=None, ano=2025):
    c = caminhos or CaminhosProjeto()
    c.preparar_saidas()
    config = json.loads(c.configuracao_usina.read_text(encoding="utf-8"))
    meta = json.loads((c.cache_era5 / "open_meteo_era5_2025_metadados.json").read_text(encoding="utf-8"))
    p = meta["parametros"]
    bruto, meta = obter_era5(c.cache_era5, p["start_date"], p["end_date"], latitude=p["latitude"],
                            longitude=p["longitude"], altitude=p["elevation"], fuso=p["timezone"])
    geometria = config if config.get("geometria_habilitada") else None
    horario, diario = agregar_era5(bruto, f"{ano}-01-01", f"{ano}-12-31", geometria)
    diario.reset_index().to_csv(c.intermediarios_meteo / "meteorologia_era5_diaria.csv", index=False)
    horario.reset_index().to_csv(c.intermediarios_meteo / "meteorologia_era5_horaria.csv", index=False)
    base_observada = c.intermediarios_brasil / "base_diaria_leopoldo_observada.csv"
    if not base_observada.exists():
        preparar_brasil_observado(c)
    observado = pd.read_csv(base_observada, parse_dates=["timestamp"]).set_index("timestamp")
    qualidade = pd.read_csv(c.auditoria / "qualidade_base_observada.csv", parse_dates=["timestamp"]).set_index("timestamp")
    comparacao = comparar_com_estacao(observado, diario, qualidade.cobertura_estacao_pct, cobertura_minima=80)
    comparacao.to_csv(c.meteo / "comparacao_era5_estacao.csv", index=False)
    resumo = {"ano": ano, "dias_calendario": len(diario),
              "dias_com_todas_as_colunas_publicas": int(diario.notna().all(axis=1).sum()),
              "sha256_bruto": meta["sha256"], "fonte": meta["fonte"], "geometria": config,
              "observacao": "O cache começa em 02/01/2025; não há extrapolação para 01/01."}
    (c.meteo / "processamento_meteorologia.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _grafico_meteo(c, diario)
    return {"diario": diario, "horario": horario, "comparacao": comparacao, "resumo": resumo}


def _grafico_australia(c, diario):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(diario.timestamp, diario.Active_Power, linewidth=.6)
    ax.set(title="Austrália — potência média diária recebida", ylabel="Active_Power — unidade a confirmar na fonte")
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(c.figuras / "australia_base_diaria.png", dpi=140)
    plt.close(fig)


def _grafico_meteo(c, diario):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    for ax, coluna, titulo in zip(axes, ["Weather_Temperature_Celsius", "Global_Horizontal_Radiation", "Radiation_Global_Tilted"],
                                  ["Temperatura ERA5 (°C)", "GHI ERA5 (W/m² médios)", "POA ERA5 + Perez (W/m² médios)"]):
        ax.plot(diario.index, diario[coluna], linewidth=.8)
        ax.set_ylabel(titulo)
        ax.grid(alpha=.2)
    fig.suptitle("Meteorologia pública homogênea — dados retrospectivos")
    fig.tight_layout()
    fig.savefig(c.figuras / "meteorologia_publica_diaria.png", dpi=140)
    plt.close(fig)
