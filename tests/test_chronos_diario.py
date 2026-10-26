"""Garante que o cenario diario nao transforma lacunas ou clima futuro em entradas."""
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.chronos_diario import extrair_diarias
from energia_transfer.chronos_experimentos import tarefas


class TestChronosDiario(unittest.TestCase):
    def setUp(self):
        self.cov = ["Weather_Temperature_Celsius", "Weather_Relative_Humidity", "Global_Horizontal_Radiation", "dia_ano_sin", "dia_ano_cos"]
        self.cfg = {"contexto_passos": 3, "colunas_covariaveis": self.cov,
                    "colunas_futuras": ["dia_ano_sin", "dia_ano_cos"]}
        self.frame = pd.DataFrame(index=pd.date_range("2025-10-01", periods=8, freq="D"))
        self.frame["Active_Power"] = np.arange(8)/100
        for c in self.cov:
            self.frame[c] = np.arange(8)+1.

    def test_alvo_e_meteorologia_futura_nao_entram_no_contexto(self):
        datas = self.frame.index[[4]]
        a = extrair_diarias(self.frame, datas, self.cfg)
        self.frame.loc[datas, ["Active_Power"]+self.cov[:3]] = 999
        b = extrair_diarias(self.frame, datas, self.cfg)
        np.testing.assert_array_equal(a["X"], b["X"])
        np.testing.assert_array_equal(a["calendario_futuro"], b["calendario_futuro"])
        self.assertTrue(np.isnan(b["calendario_futuro"][:, :3]).all())
        task = tarefas(b, True, colunas_covariaveis=self.cov, colunas_futuras=self.cfg["colunas_futuras"])[0]
        self.assertEqual(set(task["future_covariates"]), {"dia_ano_sin", "dia_ano_cos"})
        self.assertEqual(task["target"].shape, (1, 4))
        self.assertTrue(np.isnan(task["past_covariates"][self.cov[0]][-1]))

    def test_rejeita_janela_que_comprime_dia_ausente(self):
        f = self.frame.drop(self.frame.index[2])
        with self.assertRaisesRegex(AssertionError, "dias ausentes"):
            extrair_diarias(f, f.index[[3]], self.cfg)

    def test_rejeita_dia_alvo_ausente(self):
        self.frame.loc[self.frame.index[4], "Active_Power"] = np.nan
        with self.assertRaisesRegex(AssertionError, "Alvo diario ausente"):
            extrair_diarias(self.frame, self.frame.index[[4]], self.cfg)


if __name__ == "__main__":
    unittest.main()
