"""Confere regimes, calendário e contribuição dos erros sem usar o teste nos limiares."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from energia_transfer.diagnostico_erros_diarios import calcular_limiares, classificar_variacao, resumo_erros


class TestDiagnosticoErros(unittest.TestCase):
    def test_limiar_usa_treino_sem_comprimir_dias_ausentes(self):
        # Jan 1 -> Jan 3 não é um par diário; apenas Jan 3 -> Jan 4 vale (10 kW).
        base = pd.DataFrame({"Active_Power": [0., 100., 110., 10000., 30000.]},
                            index=pd.to_datetime(["2025-01-01", "2025-01-03", "2025-01-04", "2025-11-01", "2025-11-02"]))
        a = calcular_limiares(base)
        self.assertEqual(a["n_pares_treino"], 1)
        self.assertEqual(a["limiar_principal_kw"], 10.)
        self.assertEqual(a["limiar_sensibilidade_kw"], 10.)
        base.loc["2025-11-02", "Active_Power"] = 9e10
        self.assertEqual(calcular_limiares(base), a)

    def test_regimes_incluem_limite_e_zero_nao_e_mudanca(self):
        a = classificar_variacao(pd.Series([-11., -10., -9., 0., 9., 10., 11.]), 10.)
        self.assertEqual(list(a), ["queda_brusca", "queda_brusca", "variacao_moderada", "variacao_moderada", "variacao_moderada", "subida_brusca", "subida_brusca"])
        self.assertEqual(list(classificar_variacao([-1., 0., 1.], 0.)), ["queda_brusca", "variacao_moderada", "subida_brusca"])

    def test_concentracao_quadratica_nao_confunde_soma_absoluta(self):
        e = np.r_[np.full(5, 10.), np.ones(39)]
        g = pd.DataFrame(dict(erro_kw=e, erro_absoluto_kw=abs(e), real_kw=100., persistencia_kw=98.))
        a = resumo_erros(g)
        self.assertAlmostEqual(a["top5_SSE_pct"], 100*500/539)
        self.assertAlmostEqual(a["top5_erro_absoluto_pct"], 100*50/89)
        self.assertAlmostEqual(a["RMSE_kw"], np.sqrt(539/44))
        self.assertEqual(a["superestimacoes"], 44)

    def test_erros_uniformes_e_zero_tratados_sem_divisao_por_zero(self):
        for valor in [0., 2.]:
            g = pd.DataFrame(dict(erro_kw=np.full(44, valor), erro_absoluto_kw=np.full(44, valor), real_kw=100., persistencia_kw=98.))
            a = resumo_erros(g)
            self.assertEqual(a["gini_erro_absoluto"], 0.)
            self.assertAlmostEqual(a["top5_SSE_pct"], 0. if valor==0 else 100*5/44)


if __name__ == "__main__":
    unittest.main()
