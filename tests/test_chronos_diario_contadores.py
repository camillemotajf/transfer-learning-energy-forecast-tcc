"""Confere o rótulo diário por contadores e os limites das janelas temporais."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.chronos_diario_contadores import reconstruir_contadores, datas_validas


def registros(dias=6):
    linhas = []
    for dia in pd.date_range("2025-02-01", periods=dias):
        for inv in range(8):
            energia = 100.+inv
            base = 10000.+dia.day*200+inv
            for hora in [0, 3, 6, 19, 23]:
                instante = (dia+pd.Timedelta(hours=hora)).tz_localize("America/Sao_Paulo").tz_convert("UTC")
                linhas.append(dict(datetime=instante.isoformat(), usine_code="07-07FX", equipment_name=f"inv{inv}",
                                   total_active_power_w=np.nan,
                                   daily_power_yields_kwh=999 if hora<4 else (energia/3 if hora==6 else energia),
                                   total_power_yields_kwh=base+(energia if hora>=19 else 0)))
    return pd.DataFrame(linhas)


class TestContadores(unittest.TestCase):
    def test_contadores_recuperam_total_sem_imputar_telemetria(self):
        d, p, _, meta = reconstruir_contadores(registros())
        dias = d.loc["2025-02-01":"2025-02-06"]
        self.assertEqual(meta["dias_validos"], 6)
        self.assertTrue(dias.valido.all())
        np.testing.assert_allclose(dias.energia_kwh, sum(100.+i for i in range(8)))
        np.testing.assert_allclose(dias.Active_Power*24, dias.energia_kwh)
        self.assertTrue(p.leituras_potencia.eq(0).all())
        self.assertEqual(int(d.janela_3_dias_valida.sum()), 3)
        self.assertEqual(len(d), 365)
        self.assertTrue(d.loc[~d.valido, "Active_Power"].isna().all())

    def test_limite_tolerancia_e_oito_equipamentos_obrigatorios(self):
        x = registros()
        dia = pd.to_datetime(x.datetime, utc=True).dt.tz_convert("America/Sao_Paulo")
        # Diferença 8 kWh é aceita; 8.1 kWh reprova um inversor e o dia inteiro.
        for numero, erro in [(2, 8), (3, 8.1)]:
            m = dia.dt.day.eq(numero) & dia.dt.hour.ge(19) & x.equipment_name.eq("inv0")
            x.loc[m, "total_power_yields_kwh"] += erro
        d, _, _, _ = reconstruir_contadores(x)
        self.assertTrue(d.loc["2025-02-02", "valido"])
        self.assertFalse(d.loc["2025-02-03", "valido"])
        self.assertEqual(d.loc["2025-02-03", "n_consistentes"], 7)
        self.assertTrue(pd.isna(d.loc["2025-02-03", "energia_kwh"]))
        with self.assertRaisesRegex(ValueError, "equipamentos distintos"):
            reconstruir_contadores(x[x.equipment_name.ne("inv7")])

    def test_falta_borda_negativos_e_codigo_outra_usina_nao_criam_energia(self):
        x = registros()
        dt = pd.to_datetime(x.datetime, utc=True).dt.tz_convert("America/Sao_Paulo")
        m = dt.dt.day.eq(2) & dt.dt.hour.ge(19) & x.equipment_name.eq("inv0")
        # Mesmo valor em outra usina não pode reparar a borda da usina selecionada.
        outro = x.loc[m].copy()
        outro["usine_code"] = "07-07TK-2"
        x.loc[m, "total_power_yields_kwh"] = -1
        x = pd.concat([x, outro], ignore_index=True)
        d, _, _, _ = reconstruir_contadores(x)
        self.assertFalse(d.loc["2025-02-02", "valido"])
        self.assertTrue(d.loc["2025-02-01", "valido"])

    def test_nao_comprime_lacunas_nem_exige_clima_futuro(self):
        f = pd.DataFrame({"Active_Power": 1., "temperatura": 20.},
                         index=pd.date_range("2025-02-01", periods=10))
        f.loc["2025-02-04", "Active_Power"] = np.nan
        f.loc["2025-02-09", "temperatura"] = np.nan
        d = datas_validas(f, 3, ["temperatura"])
        self.assertEqual(list(d), list(pd.to_datetime(["2025-02-08", "2025-02-09"])))


if __name__ == "__main__":
    unittest.main()
