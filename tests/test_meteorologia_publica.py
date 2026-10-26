import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.meteorologia_publica import agregar_era5, media_circular_graus, preencher_com_publicos


def resposta_exemplo():
    horas = pd.date_range("2025-01-01", periods=72, freq="h")
    valores = np.arange(72, dtype=float).tolist()
    return {
        "timezone": "America/Sao_Paulo",
        "hourly_units": {
            "temperature_2m": "°C", "relative_humidity_2m": "%", "wind_speed_10m": "m/s",
            "wind_direction_10m": "°", "rain": "mm", "shortwave_radiation": "W/m²",
            "diffuse_radiation": "W/m²", "direct_normal_irradiance": "W/m²",
        },
        "hourly": {
            "time": horas.strftime("%Y-%m-%dT%H:%M").tolist(),
            "temperature_2m": [22.] * 72, "relative_humidity_2m": [80.] * 72,
            "wind_speed_10m": [2.] * 72, "wind_direction_10m": [0.] * 72,
            "rain": [1.] * 72, "shortwave_radiation": valores,
            "diffuse_radiation": [10.] * 72, "direct_normal_irradiance": [0.] * 72,
        },
    }


class MeteorologiaPublicaTests(unittest.TestCase):
    def test_radicao_representa_hora_anterior_e_mantem_unidade_de_potencia(self):
        _, diario = agregar_era5(resposta_exemplo(), "2025-01-02", "2025-01-02")
        self.assertAlmostEqual(diario.iloc[0].Global_Horizontal_Radiation, np.arange(25, 49).mean())
        self.assertAlmostEqual(diario.iloc[0].GHI_Energy_kWh_m2, np.arange(25, 49).sum() / 1000)
        self.assertEqual(diario.iloc[0].Public_Radiation_Hours, 24)

    def test_chuva_acumulada_media_nao_e_total_diario(self):
        _, diario = agregar_era5(resposta_exemplo(), "2025-01-02", "2025-01-02")
        self.assertAlmostEqual(diario.iloc[0].Rainfall_Total_mm, 24.)
        self.assertAlmostEqual(diario.iloc[0].Weather_Daily_Rainfall, np.arange(288).mean() / 12)

    def test_dia_incompleto_nao_recebe_media_como_se_fosse_completo(self):
        dados = resposta_exemplo()
        dados["hourly"]["temperature_2m"][25] = None
        _, diario = agregar_era5(dados, "2025-01-02", "2025-01-02")
        self.assertTrue(pd.isna(diario.iloc[0].Weather_Temperature_Celsius))
        self.assertEqual(diario.iloc[0].Public_Weather_Hours, 23)

    def test_unidade_incompativel_nao_e_aceita_silenciosamente(self):
        dados = resposta_exemplo()
        dados["hourly_units"]["wind_speed_10m"] = "km/h"
        with self.assertRaises(ValueError):
            agregar_era5(dados, "2025-01-02", "2025-01-02")

    def test_media_de_direcao_respeita_passagem_pelo_norte(self):
        media = media_circular_graus([359, 1])
        self.assertLess(min(abs(media), abs(media - 360)), 1e-9)
        self.assertTrue(np.isnan(media_circular_graus([0, 180])))

    def test_fontes_preservam_medicoes_zero_e_nao_inventam_potencia(self):
        indice = pd.date_range("2025-01-01", periods=2, name="timestamp")
        original = pd.DataFrame({"Weather_Temperature_Celsius": [0., np.nan], "Active_Power": [1., np.nan]}, index=indice)
        publico = pd.DataFrame({"Weather_Temperature_Celsius": [25., 26.], "Active_Power": [999., 999.]}, index=indice)
        final, audit, _ = preencher_com_publicos(original, publico)
        self.assertEqual(final.iloc[0].Weather_Temperature_Celsius, 0.)
        self.assertEqual(final.iloc[1].Weather_Temperature_Celsius, 26.)
        self.assertTrue(pd.isna(final.iloc[1].Active_Power))
        self.assertEqual(audit.iloc[0].Weather_Temperature_Celsius__fonte, "estacao")
        self.assertEqual(audit.iloc[1].Weather_Temperature_Celsius__fonte, "ERA5")

    def test_poa_tem_componentes_fisicas_e_origem_especifica(self):
        geometria = dict(inclinacao_graus=20, azimute_norte_horario_graus=0,
                         latitude=-16.55, longitude=-48.85, altitude_m=927, albedo=0.3)
        horario, diario = agregar_era5(resposta_exemplo(), "2025-01-02", "2025-01-02", geometria)
        self.assertFalse(diario[["Radiation_Global_Tilted", "Radiation_Diffuse_Tilted"]].isna().any().any())
        self.assertTrue(diario.Radiation_Global_Tilted.ge(diario.Radiation_Diffuse_Tilted - 1e-9).all())
        original = pd.DataFrame({"Radiation_Global_Tilted": [np.nan], "Active_Power": [1.]}, index=diario.index)
        _, auditoria, _ = preencher_com_publicos(original, diario)
        self.assertEqual(auditoria.iloc[0].Radiation_Global_Tilted__fonte, "ERA5_Perez")


if __name__ == "__main__":
    unittest.main()
