"""Isolamento do treino e invariantes da comparação MLP/LSTM com Chronos."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from energia_transfer.benchmark_diario_brasil import (
    ajustar_normalizacao, construir, prever, transformar, _conferir_referencia)


class TestBenchmarkDiarioBrasil(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.cfg = dict(contexto_passos=3, mlp_unidades=[32, 16], lstm_unidades=16, capacidade_ac_kw=1000.,
                        colunas_historicas=["Active_Power", "temperatura", "umidade", "GHI", "dia_ano_sin", "dia_ano_cos"],
                        colunas_futuras=["dia_ano_sin", "dia_ano_cos"])
        self.j = dict(X=np.random.default_rng(4).uniform(.1, .4, (8, 3, 6)).astype(np.float32),
                      y=np.linspace(.1, .3, 8), calendario_futuro=np.tile([np.nan, np.nan, np.nan, .2, -.5], (8, 1)))
        self.c = ajustar_normalizacao(self.j)

    def test_normalizacao_fixa_do_treino_nao_reajusta_nos_extremos_futuros(self):
        mu = np.array(self.c["x_media"]).copy()
        out = {k: v.copy() for k, v in self.j.items()}
        out["X"] += 100
        out["y"] += 100
        t = transformar(out, self.c, self.cfg)
        np.testing.assert_allclose(t["X"], (out["X"]-mu)/np.array(self.c["x_escala"]), rtol=1e-6)
        np.testing.assert_array_equal(self.c["x_media"], mu)
        np.testing.assert_allclose(t["futuro"], out["calendario_futuro"][:, 3:])

    def test_previsao_ignora_y_e_meteorologia_futura(self):
        outro = {k: v.copy() for k, v in self.j.items()}
        outro["y"][:] = 9999
        outro["calendario_futuro"][:, :3] = 9999
        for tipo in ["mlp", "lstm"]:
            torch.manual_seed(42)
            modelo = construir(tipo, self.cfg)
            a = prever(modelo, self.j, self.c, self.cfg)
            b = prever(modelo, outro, self.c, self.cfg)
            np.testing.assert_array_equal(a, b)

    def test_lstm_nao_carrega_estado_entre_janelas_ou_lotes(self):
        torch.manual_seed(42)
        modelo = construir("lstm", self.cfg).eval()
        t = transformar(self.j, self.c, self.cfg)
        x, f = torch.from_numpy(t["X"]), torch.from_numpy(t["futuro"])
        with torch.inference_mode():
            lote = modelo(x, f).numpy()
            independentes = np.array([modelo(x[i:i+1], f[i:i+1]).item() for i in range(len(x))])
            perm = np.arange(len(x))[::-1].copy()
            invertido = modelo(x[perm], f[perm]).numpy()[::-1]
        np.testing.assert_allclose(lote, independentes, atol=1e-6)
        np.testing.assert_allclose(lote, invertido, atol=1e-6)

    def test_comparacao_rejeita_mesmo_n_com_datas_ou_alvos_diferentes(self):
        j = dict(datas=pd.date_range("2025-11-01", periods=2), real_kw=np.array([100., 200.]), persistencia=np.array([.2, .3]))
        t = pd.DataFrame(dict(timestamp=j["datas"], referencia_diaria_kw=j["real_kw"], persistencia=j["persistencia"]*1000))
        _conferir_referencia(t, j)
        outro = t.copy()
        outro["timestamp"] += pd.Timedelta(days=1)
        with self.assertRaises(AssertionError):
            _conferir_referencia(outro, j)
        outro = t.copy()
        outro.loc[0, "referencia_diaria_kw"] += 1
        with self.assertRaises(AssertionError):
            _conferir_referencia(outro, j)


if __name__ == "__main__":
    unittest.main()
