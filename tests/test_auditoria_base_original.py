import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.auditoria_base_original import FUSO, _limpar, _maior_bloco, interpolar_blocos_internos


class AuditoriaOriginalTests(unittest.TestCase):
    def test_interpolacao_preserva_zero_e_nao_preenche_parte_de_bloco_longo(self):
        indice = pd.date_range("2025-01-01 10:00", periods=11, freq="5min", tz=FUSO)
        original = pd.Series([np.nan, 0, np.nan, np.nan, 3, np.nan, np.nan, np.nan, np.nan, 8, np.nan], index=indice)
        resultado = interpolar_blocos_internos(original)
        np.testing.assert_allclose(resultado.iloc[2:4], [1, 2])
        self.assertTrue(resultado.iloc[[0, 5, 6, 7, 8, 10]].isna().all())
        pd.testing.assert_series_equal(resultado.loc[original.notna()], original.dropna())

    def test_interpolacao_nao_atravessa_meia_noite(self):
        indice = pd.date_range("2025-01-01 23:50", periods=4, freq="5min", tz=FUSO)
        original = pd.Series([0, np.nan, np.nan, 3], index=indice)
        pd.testing.assert_series_equal(interpolar_blocos_internos(original), original)

    def test_maior_lacuna_diaria_nao_soma_dias_vizinhos(self):
        indice = pd.date_range("2025-01-01", periods=3 * 288, freq="5min", tz=FUSO)
        original = pd.Series(np.nan, index=indice)
        self.assertEqual(_maior_bloco(original).tolist(), [1440, 1440, 1440])

    def test_deduplicacao_prioriza_completude_e_preserva_potencia_zero(self):
        bruto = pd.DataFrame({
            "meta.id_usina": [50, 50, 50, 51],
            "id": [59, 59, 60, 59],
            "usine_code": ["07-07TK-2", "07-07FX", "07-07FX", "07-07FX"],
            "t": pd.to_datetime(["2025-01-01 10:01", "2025-01-01 10:02", "2025-01-01 10:02", "2025-01-01 10:02"]).tz_localize(FUSO),
            "real_datetime": [None] * 4,
            "potencia": [0, np.nan, 10, 999],
        })
        resultado = _limpar(bruto, "id", ["potencia"])
        self.assertEqual(len(resultado), 2)
        self.assertEqual(resultado.set_index("id").loc[59, "potencia"], 0)
        self.assertTrue(resultado["slot"].dt.minute.eq(0).all())


if __name__ == "__main__":
    unittest.main()
