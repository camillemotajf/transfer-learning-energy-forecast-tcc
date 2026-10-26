"""Garantias temporais e de alvo das tarefas de fine-tuning."""
import sys
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.chronos_experimentos import CALENDARIO, extrair_janelas, tarefas


class TestJanelasChronos(unittest.TestCase):
    def setUp(self):
        self.frame = pd.DataFrame(index=pd.date_range("2025-09-01 10:00", periods=15, freq="5min"))
        self.frame["Active_Power"] = np.arange(15, dtype=float)
        self.frame["Active_Power_original"] = self.frame.Active_Power
        self.frame["diurno"] = True
        for c in CALENDARIO:
            self.frame[c] = 0.5
        self.datas = self.frame.index[[12]]

    def test_alterar_alvo_nao_altera_contexto(self):
        a = extrair_janelas(self.frame, self.datas, 1000)
        self.frame.loc[self.datas, "Active_Power_original"] = 500
        self.frame.loc[self.datas, "Active_Power"] = 600
        b = extrair_janelas(self.frame, self.datas, 1000)
        np.testing.assert_array_equal(a["X"], b["X"])
        task = tarefas(b, True)[0]
        self.assertAlmostEqual(float(task["target"][0, -1]), 0.5)
        self.assertEqual(task["target"].shape, (1, 13))
        self.assertEqual(set(task["future_covariates"]), set(CALENDARIO))

    def test_rejeita_alvo_imputado(self):
        self.frame.loc[self.datas, "Active_Power_original"] = np.nan
        with self.assertRaisesRegex(AssertionError, "Alvo precisa"):
            extrair_janelas(self.frame, self.datas, 1000)

    def test_rejeita_compressao_de_lacuna(self):
        frame = self.frame.drop(self.frame.index[3])
        with self.assertRaisesRegex(AssertionError, "lacuna temporal"):
            extrair_janelas(frame, frame.index[[12]], 1000)


if __name__ == "__main__":
    unittest.main()
