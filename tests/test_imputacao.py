import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.imputacao import estimar_knn, imputar_diario, interpolar_interno, validar_metodos


class ImputacaoTests(unittest.TestCase):
    def test_interpolacao_nao_extrapola_nem_preenche_parte_de_bloco_longo(self):
        indice = pd.date_range("2025-01-01", periods=12)
        original = pd.Series([np.nan, 1, np.nan, np.nan, 4, np.nan, np.nan, np.nan, 8, 9, 10, np.nan], index=indice)
        resultado = interpolar_interno(original, limite=2)
        np.testing.assert_allclose(resultado.iloc[2:4], [2, 3])
        self.assertTrue(resultado.iloc[[0, 5, 6, 7, 11]].isna().all())
        pd.testing.assert_series_equal(resultado.loc[original.notna()], original.loc[original.notna()])

    def test_restricao_dos_doadores_ignora_valores_futuros(self):
        indice = pd.date_range("2025-01-01", periods=20)
        serie = pd.Series(np.arange(20, dtype=float), index=indice, name="temperatura")
        serie.iloc[8] = np.nan
        treino = indice[:7]
        primeira = estimar_knn(serie, vizinhos=3, indices_doadores=treino)
        alterada = serie.copy()
        alterada.iloc[10:] = 1e9
        segunda = estimar_knn(alterada, vizinhos=3, indices_doadores=treino)
        pd.testing.assert_series_equal(primeira, segunda)

    def test_coluna_sem_medicoes_permanece_ausente(self):
        serie = pd.Series(np.nan, index=pd.date_range("2025-01-01", periods=10))
        self.assertTrue(estimar_knn(serie).isna().all())

    def test_reconstrucao_preserva_observados_e_identifica_bloco_nao_validado(self):
        indice = pd.date_range("2025-01-01", periods=50)
        original = pd.DataFrame({"potencia": np.arange(50, dtype=float), "sem_sensor": np.nan}, index=indice)
        original.loc[indice[20:28], "potencia"] = np.nan
        _, validacao = validar_metodos(original[["potencia"]], blocos=(1, 3), repeticoes=2, candidatos=(3, 5))
        resultado, indicadores, _ = imputar_diario(original, validacao)
        self.assertFalse(resultado.potencia.isna().any())
        self.assertTrue(resultado.sem_sensor.isna().all())
        pd.testing.assert_frame_equal(resultado.where(original.notna()), original)
        self.assertEqual(int(indicadores.potencia__imputado.sum()), 8)
        self.assertEqual(int(indicadores.potencia__alem_validacao.sum()), 8)
        self.assertFalse(indicadores.sem_sensor__imputado.any())
        # Contador linear não ganha oscilações artificiais em valores intermediários.
        self.assertTrue(resultado.potencia.between(0, 49).all())


if __name__ == "__main__":
    unittest.main()
