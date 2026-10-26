"""Dados horários ERA5/Open-Meteo para preencher lacunas meteorológicas diárias.

Reanálise regional não é uma medição da estação da usina. Os dados brutos e
os metadados da consulta são mantidos para permitir reprodução sem rede.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


VARIAVEIS_HORARIAS = [
    "temperature_2m", "relative_humidity_2m", "wind_speed_10m", "wind_direction_10m",
    "rain", "shortwave_radiation", "diffuse_radiation", "direct_normal_irradiance",
]
COLUNAS_ELETRICAS = [
    "Active_Energy_Delivered_Received", "Current_Phase_Average", "Active_Power",
]
MAPA_INSTANTANEAS = {
    "temperature_2m": "Weather_Temperature_Celsius",
    "relative_humidity_2m": "Weather_Relative_Humidity",
    "wind_speed_10m": "Wind_Speed",
}
MAPA_RADIACAO = {
    "shortwave_radiation": "Global_Horizontal_Radiation",
    "diffuse_radiation": "Diffuse_Horizontal_Radiation",
}


def obter_era5(pasta, inicio, fim, latitude=-16.55, longitude=-48.85, altitude=927,
              fuso="America/Sao_Paulo", atualizar=False):
    """Reutiliza o cache validado ou baixa uma consulta explícita de ERA5.

    Os dias inicial/final são os da consulta horária, incluindo margens para
    as variáveis que representam a hora anterior. Sem dados em cache, requer rede.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    parametros = dict(
        latitude=latitude, longitude=longitude, elevation=altitude,
        start_date=str(pd.Timestamp(inicio).date()), end_date=str(pd.Timestamp(fim).date()),
        timezone=fuso, models="era5", wind_speed_unit="ms", hourly=",".join(VARIAVEIS_HORARIAS),
    )
    nome = f"open_meteo_era5_{pd.Timestamp(inicio).year}"
    bruto = pasta / f"{nome}.json"
    metadados = pasta / f"{nome}_metadados.json"
    if bruto.exists() and metadados.exists() and not atualizar:
        meta = json.loads(metadados.read_text(encoding="utf-8"))
        if meta["parametros"] != parametros:
            raise ValueError("O cache pertence a outra consulta. Use atualizar=True ou outra pasta.")
        conteudo = bruto.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != meta["sha256"]:
            raise ValueError("O arquivo ERA5 em cache foi alterado: SHA-256 não confere.")
        return json.loads(conteudo), meta
    url = "https://archive-api.open-meteo.com/v1/archive?" + urlencode(parametros)
    with urlopen(Request(url, headers={"User-Agent": "Leopoldo-TCC/1.0"}), timeout=45) as resposta:
        conteudo = resposta.read()
    dados = json.loads(conteudo)
    if "hourly" not in dados:
        raise ValueError(f"Resposta ERA5 sem dados horários: {dados}")
    meta = {
        "fonte": "Copernicus ERA5, via Open-Meteo", "parametros": parametros,
        "documentacao": "https://open-meteo.com/en/docs/historical-weather-api",
        "licenca": "https://open-meteo.com/en/licence", "url": url,
        "download_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(conteudo).hexdigest(),
        "resposta_localizacao": {k: dados.get(k) for k in [
            "latitude", "longitude", "elevation", "timezone", "utc_offset_seconds",
        ]}, "unidades": dados["hourly_units"],
    }
    bruto.write_bytes(conteudo)
    metadados.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dados, meta


def media_circular_graus(valores):
    valores = pd.Series(valores).dropna().to_numpy(dtype=float)
    if len(valores) == 0:
        return np.nan
    radianos = np.deg2rad(valores)
    seno, cosseno = np.sin(radianos).mean(), np.cos(radianos).mean()
    if np.hypot(seno, cosseno) < 1e-10:
        return np.nan  # Resultante nula não define uma direção média.
    return float(np.rad2deg(np.arctan2(seno, cosseno)) % 360) % 360


def _media_dia_completo(serie):
    grupos = serie.resample("D")
    return grupos.mean().where(grupos.count().eq(24))


def agregar_era5(dados, inicio, fim, geometria=None):
    """Converte as variáveis horárias para o mesmo calendário diário da usina.

    Radiação: W/m² médios, sem confundir com energia diária. Chuva: média do
    contador acumulado no dia, amostrado de 5 em 5 minutos, conforme a base atual.
    O total diário de chuva também é exportado separadamente.
    """
    unidades = dados["hourly_units"]
    esperadas = {
        "wind_speed_10m": "m/s", "temperature_2m": "°C", "relative_humidity_2m": "%",
        "shortwave_radiation": "W/m²", "diffuse_radiation": "W/m²",
        "direct_normal_irradiance": "W/m²", "rain": "mm", "wind_direction_10m": "°",
    }
    for coluna, unidade in esperadas.items():
        if unidades.get(coluna) != unidade:
            raise ValueError(f"Unidade inesperada para {coluna}: {unidades.get(coluna)}")
    horario = pd.DataFrame(dados["hourly"]).rename(columns={"time": "timestamp"})
    horario["timestamp"] = pd.to_datetime(horario["timestamp"]).dt.tz_localize(dados["timezone"])
    horario = horario.set_index("timestamp").sort_index()
    if not horario.index.is_unique or not horario.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all():
        raise ValueError("A série pública deve ter horários únicos e frequência horária regular.")
    calendario = pd.date_range(inicio, fim, freq="D", name="timestamp")
    diario = pd.DataFrame(index=calendario)

    def alinhar(serie):
        serie = serie.copy()
        serie.index = serie.index.tz_localize(None)
        return serie.reindex(calendario)

    for origem, destino in MAPA_INSTANTANEAS.items():
        diario[destino] = alinhar(_media_dia_completo(horario[origem]))
    direcao = horario.wind_direction_10m.resample("D").apply(media_circular_graus)
    direcao = direcao.where(horario.wind_direction_10m.resample("D").count().eq(24))
    diario["Wind_Direction"] = alinhar(direcao)

    # Open-Meteo rotula médias de radiação e chuva pelo FIM da hora anterior.
    # Passar ao início do intervalo inclui exatamente 00h–24h de cada dia local.
    intervalos = horario[list(MAPA_RADIACAO) + ["rain", "direct_normal_irradiance"]].copy()
    intervalos.index = intervalos.index - pd.Timedelta(hours=1)
    for origem, destino in MAPA_RADIACAO.items():
        diario[destino] = alinhar(_media_dia_completo(intervalos[origem]))
    chuva = intervalos.rain
    anterior = chuva.groupby(chuva.index.normalize()).cumsum() - chuva
    # Hipótese explícita: chuva uniforme dentro da hora; pontos 00:00..00:55
    # têm frações 0/12..11/12, cuja média é 11/24 do total horário.
    diario["Weather_Daily_Rainfall"] = alinhar(_media_dia_completo(anterior + (11 / 24) * chuva))
    diario["Rainfall_Total_mm"] = alinhar(chuva.resample("D").sum(min_count=24))
    diario["GHI_Energy_kWh_m2"] = alinhar(intervalos.shortwave_radiation.resample("D").sum(min_count=24) / 1000)
    diario["Direct_Normal_Radiation"] = alinhar(_media_dia_completo(intervalos.direct_normal_irradiance))
    diario["Public_Weather_Hours"] = alinhar(horario[list(MAPA_INSTANTANEAS)].notna().all(axis=1).astype(int).resample("D").sum())
    diario["Public_Radiation_Hours"] = alinhar(intervalos[list(MAPA_RADIACAO)].notna().all(axis=1).astype(int).resample("D").sum())

    if geometria is not None:
        poa = calcular_poa(horario, geometria)
        # POA também representa a hora anterior.
        poa.index = poa.index - pd.Timedelta(hours=1)
        for coluna in poa:
            diario[coluna] = alinhar(_media_dia_completo(poa[coluna]))
        diario.attrs["fontes"] = {c: "ERA5_Perez" for c in poa.columns}
    return horario, diario


def calcular_poa(horario, geometria):
    """Transposição Perez com geometria CONFIRMADA e azimute horário desde norte."""
    import pvlib

    tilt, azimute = geometria["inclinacao_graus"], geometria["azimute_norte_horario_graus"]
    if not 0 <= tilt <= 90 or not 0 <= azimute < 360:
        raise ValueError("Inclinação ou azimute fora do intervalo físico esperado.")
    meio = horario.index - pd.Timedelta(minutes=30)
    local = pvlib.location.Location(geometria["latitude"], geometria["longitude"],
                                    tz=str(horario.index.tz), altitude=geometria["altitude_m"])
    posicao = local.get_solarposition(meio)
    # Usar vetores evita alinhar por engano índices de fim de hora e meio da hora.
    resultado = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt, surface_azimuth=azimute,
        solar_zenith=posicao.apparent_zenith.to_numpy(), solar_azimuth=posicao.azimuth.to_numpy(),
        dni=horario.direct_normal_irradiance.to_numpy(), ghi=horario.shortwave_radiation.to_numpy(),
        dhi=horario.diffuse_radiation.to_numpy(), dni_extra=pvlib.irradiance.get_extra_radiation(meio).to_numpy(),
        airmass=pvlib.atmosphere.get_relative_airmass(posicao.apparent_zenith).to_numpy(),
        albedo=geometria["albedo"], model="perez",
    )
    saida = pd.DataFrame({
        "Radiation_Global_Tilted": resultado["poa_global"],
        "Radiation_Diffuse_Tilted": resultado["poa_diffuse"],
    }, index=horario.index)
    noite = posicao.apparent_zenith.to_numpy() >= 90
    saida.loc[noite] = 0.0
    return saida


def preencher_com_publicos(observado, publico, eletrico_estimado=None):
    """Preenche somente ausências, sem sobrescrever medições reais."""
    if not observado.index.is_unique or not publico.index.is_unique:
        raise ValueError("Datas duplicadas impedem uma junção diária inequívoca.")
    resultado = observado.copy()
    auditoria = pd.DataFrame(index=observado.index)
    resumo = []
    for coluna in observado:
        original = observado[coluna]
        fonte = pd.Series(np.where(original.notna(), "inversores" if coluna in COLUNAS_ELETRICAS else "estacao", "ausente"), index=observado.index)
        if coluna not in COLUNAS_ELETRICAS and coluna in publico:
            externo = publico[coluna].reindex(observado.index)
            usar = original.isna() & externo.notna()
            resultado.loc[usar, coluna] = externo.loc[usar]
            nome = publico.attrs.get("fontes", {}).get(coluna, "ERA5")
            fonte.loc[usar] = nome
        elif coluna in COLUNAS_ELETRICAS and eletrico_estimado is not None:
            estimado = eletrico_estimado[coluna].reindex(observado.index)
            usar = original.isna() & estimado.notna()
            resultado.loc[usar, coluna] = estimado.loc[usar]
            fonte.loc[usar] = "imputacao_eletrica_anterior"
        auditoria[f"{coluna}__fonte"] = fonte
        auditoria[f"{coluna}__preenchido"] = original.isna() & resultado[coluna].notna()
        resumo.append({
            "coluna": coluna, "dias_observados": int(original.notna().sum()),
            "dias_ERA5": int(fonte.str.startswith("ERA5").sum()),
            "dias_imputacao_eletrica": int(fonte.eq("imputacao_eletrica_anterior").sum()),
            "faltantes_antes_pct": 100 * original.isna().mean(),
            "faltantes_depois_pct": 100 * resultado[coluna].isna().mean(),
        })
        pd.testing.assert_series_equal(resultado.loc[original.notna(), coluna], original.loc[original.notna()])
    auditoria["potencia_original_observada"] = observado.Active_Power.notna()
    return resultado, auditoria, pd.DataFrame(resumo)


def comparar_com_estacao(observado, publico, cobertura=None, cobertura_minima=80):
    """Verifica compatibilidade, sem ajustar automaticamente sensores divergentes."""
    linhas = []
    for coluna in observado.columns.intersection(publico.columns):
        pares = pd.concat([observado[coluna].rename("estacao"), publico[coluna].rename("publico")], axis=1).dropna()
        if cobertura is not None:
            pares = pares.loc[cobertura.reindex(pares.index).ge(cobertura_minima)]
        if pares.empty:
            continue
        erro = pares.publico - pares.estacao
        constante = pares.estacao.nunique() == 1
        if coluna == "Wind_Direction":
            erro = (erro + 180) % 360 - 180
        mediana = float(pares.estacao.median())
        razao = float(pares.publico.median() / mediana) if abs(mediana) > 1e-12 else np.nan
        linhas.append({
            "coluna": coluna, "dias_comparados": len(pares),
            "MAE": float(erro.abs().mean()), "RMSE": float(np.sqrt((erro ** 2).mean())),
            "vies_publico_menos_estacao": float(erro.mean()),
            "correlacao": pares.estacao.corr(pares.publico) if not constante else np.nan,
            "mediana_estacao": mediana, "mediana_publica": float(pares.publico.median()),
            "razao_mediana_publico_estacao": razao, "estacao_constante": constante,
            "escala_a_revisar": coluna != "Wind_Direction" and np.isfinite(razao) and (razao > 2 or razao < 0.5),
        })
    return pd.DataFrame(linhas)

