"""Verifica denominadores de cobertura e interrupções sem comprimir o calendário."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from energia_transfer.caracterizacao_bases_tcc import classe_cobertura, extrair_lacunas, cobertura_por_chave


class TestCaracterizacaoBases(unittest.TestCase):
    def test_duplicatas_nao_inflam_cobertura_nem_criam_media(self):
        grade = pd.date_range('2025-01-01', periods=2, freq='5min')
        ts = pd.Series([grade[0], grade[0], grade[1]])
        eq = pd.Series(['A', 'A', 'A'])
        valores = pd.DataFrame({'p': [False, True, False]})
        cov, reg = cobertura_por_chave(ts, eq, valores, grade, ['A', 'B'])
        self.assertEqual(reg.sum(), 3)
        self.assertEqual(cov.registro.sum(), 2)
        self.assertEqual(cov.p.sum(), 1)
        self.assertEqual(valores.p.tolist(), [False, True, False])

    def test_desalinhamento_nao_se_confunde_com_intervalo_sem_registro(self):
        grade = pd.date_range('2025-01-01', periods=2, freq='5min')
        ts = pd.Series([grade[0]+pd.Timedelta(seconds=20), grade[1]])
        eq = pd.Series(['A','A'])
        finitos = pd.DataFrame({'p':[True,True]})
        exata, _ = cobertura_por_chave(ts, eq, finitos, grade, ['A'])
        intervalos, _ = cobertura_por_chave(ts.dt.floor('5min'), eq, finitos, grade, ['A'])
        self.assertEqual(exata.p.sum(), 1)
        self.assertEqual(intervalos.p.sum(), 2)
        self.assertEqual(ts.iloc[0].second, 20)

    def test_limites_de_95pct_em_grade_de_288(self):
        np.testing.assert_array_equal(classe_cobertura([0, 97, 273, 274, 287, 288]), [0, 1, 1, 2, 2, 3])

    def test_contagens_fora_da_grade_nao_viram_percentuais_validos(self):
        for x in [[-1], [289], [np.nan]]:
            with self.assertRaises(ValueError):
                classe_cobertura(x)

    def test_lacunas_incluem_as_bordas_e_fim_do_calendario(self):
        i = pd.date_range("2025-01-01", periods=7)
        g = extrair_lacunas(pd.Series([True, True, False, True, False, False, True], index=i))
        self.assertEqual(g.dias.tolist(), [2, 1, 1])
        self.assertEqual(list(g.inicio), list(i[[0, 3, 6]]))
        self.assertEqual(list(g.fim), list(i[[1, 3, 6]]))

    def test_rejeita_calendario_comprimido_e_nao_inventa_lacuna(self):
        with self.assertRaises(ValueError):
            extrair_lacunas(pd.Series([True, True], index=pd.to_datetime(["2025-01-01", "2025-01-03"])))
        self.assertTrue(extrair_lacunas(pd.Series(False, index=pd.date_range("2025-01-01", periods=5))).empty)


if __name__ == "__main__":
    unittest.main()
