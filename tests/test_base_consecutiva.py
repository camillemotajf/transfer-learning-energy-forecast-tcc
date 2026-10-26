import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.base_consecutiva import localizar_blocos, reconstruir_potencia, selecionar_dias


class BaseConsecutivaTests(unittest.TestCase):
    def test_blocos_nao_unem_dias_reprovados_e_desempatam_pelo_inicio(self):
        dias = pd.date_range("2025-01-01", periods=5)
        blocos = localizar_blocos(pd.Series([True, True, False, True, True], index=dias))
        self.assertEqual(blocos.dias.tolist(), [2, 2])
        self.assertEqual(blocos.iloc[0].inicio, dias[0])

    def test_calendario_incompleto_interrompe_sequencia(self):
        dias = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-04"])
        blocos = localizar_blocos(pd.Series(True, index=dias))
        self.assertEqual(blocos.dias.tolist(), [2, 1])

    def test_selecao_exige_qualidade_colunas_finitas_e_medicao_original(self):
        dias = pd.date_range("2025-01-01", periods=5)
        base = pd.DataFrame({"Active_Power": [1, np.nan, 3, 4, 5]}, index=dias)
        qualidade = pd.DataFrame({
            "planta_cobertura_diurna_tratada_pct": [100, 100, 94, 100, 100],
            "planta_cobertura_24h_tratada_pct": [100, 100, 100, 94, 100],
            "planta_intervalos_completos_originais": [1, 1, 1, 1, 0],
        }, index=dias)
        elegivel, blocos = selecionar_dias(base, qualidade)
        self.assertEqual(elegivel.tolist(), [True, False, False, False, False])
        self.assertEqual(blocos.iloc[0].dias, 1)

    def test_proxy_usa_observacoes_historicas_e_preserva_zeros(self):
        indice = pd.date_range("2025-01-01 09:00", periods=50, freq="5min", tz="America/Sao_Paulo")
        original = pd.DataFrame(10_000., index=indice, columns=range(8))
        original.loc[indice[[19, 23]], 0] = 0
        original.loc[indice[20:23], 0] = np.nan
        diurno = pd.Series(True, index=indice)
        escuro = ~diurno
        resultado, fontes, _ = reconstruir_potencia(original, diurno, escuro, min_doadores=3)
        np.testing.assert_allclose(resultado.loc[indice[20:23], 0], 10_000)
        self.assertTrue(fontes.loc[indice[20:23], 0].eq("outros_7_inversores").all())
        pd.testing.assert_frame_equal(resultado.where(original.notna()), original)
        alterada = original.copy()
        alterada.loc[indice[30:], 0] = 120_000
        segunda, _, _ = reconstruir_potencia(alterada, diurno, escuro, min_doadores=3)
        pd.testing.assert_frame_equal(resultado.loc[indice[20:23]], segunda.loc[indice[20:23]])

    def test_dois_inversores_ausentes_nao_sao_doadores_estimados(self):
        indice = pd.date_range("2025-01-01 09:00", periods=50, freq="5min", tz="America/Sao_Paulo")
        original = pd.DataFrame(10_000., index=indice, columns=range(8))
        original.loc[indice[20], [0, 1]] = np.nan
        resultado, fontes, _ = reconstruir_potencia(original, pd.Series(True, index=indice), pd.Series(False, index=indice), min_doadores=3)
        self.assertTrue(fontes.loc[indice[20], [0, 1]].eq("linear_ate_15min").all())
        np.testing.assert_allclose(resultado.loc[indice[20], [0, 1]], 10_000)

    def test_zero_noturno_nao_preenche_lacuna_diurna_longa(self):
        indice = pd.date_range("2025-01-01", periods=12, freq="5min", tz="America/Sao_Paulo")
        original = pd.DataFrame(0., index=indice, columns=range(8))
        original.loc[indice[1:5], :] = np.nan
        original.loc[indice[7:11], :] = np.nan
        escuro = pd.Series(np.arange(12) < 6, index=indice)
        resultado, fontes, _ = reconstruir_potencia(original, ~escuro, escuro, min_doadores=3)
        self.assertTrue(resultado.loc[indice[1:5]].eq(0).all().all())
        self.assertTrue(fontes.loc[indice[1:5]].eq("zero_noturno_solar").all().all())
        self.assertTrue(resultado.loc[indice[7:11]].isna().all().all())


if __name__ == "__main__":
    unittest.main()
