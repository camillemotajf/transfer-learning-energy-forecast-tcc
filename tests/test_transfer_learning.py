import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.transfer_learning.dados import ajustar_escalas_fonte, criar_janelas, carregar_config


class DadosTransferTests(unittest.TestCase):
    def test_janela_nao_atravessa_dia_reprovado_nem_busca_linha_anterior(self):
        dias = pd.date_range("2025-01-01", periods=9).delete(3)
        frame = pd.DataFrame({"Active_Power": np.arange(8, dtype=float) / 10, "meteo": 20.}, index=dias)
        sx, sy = ajustar_escalas_fonte(frame, list(frame), "2025-01-03")
        dados, meta = criar_janelas(frame, list(frame), 2, "2025-01-06", "2025-01-08", sx, sy)
        self.assertEqual(list(dados["datas"]), ["2025-01-03", "2025-01-07", "2025-01-08", "2025-01-09"])
        self.assertEqual(meta.particao.tolist(), ["treino", "validacao", "validacao", "teste"])
        np.testing.assert_allclose(dados["persistencia"], [.1, .4, .5, .6])
        self.assertTrue(meta.timestamp.sub(meta.entrada_fim).eq(pd.Timedelta(days=1)).all())

    def test_normalizacao_ignora_extremos_na_validacao_e_teste(self):
        dias = pd.date_range("2020-01-01", periods=8)
        frame = pd.DataFrame({"Active_Power": np.arange(8) / 20, "meteo": np.arange(8) + 20.}, index=dias)
        sx, sy = ajustar_escalas_fonte(frame, list(frame), "2020-01-04")
        alterado = frame.copy()
        alterado.loc["2020-01-05":] = 1e9
        sx2, sy2 = ajustar_escalas_fonte(alterado, list(frame), "2020-01-04")
        np.testing.assert_array_equal(sx.mean_, sx2.mean_)
        np.testing.assert_array_equal(sx.scale_, sx2.scale_)
        np.testing.assert_array_equal(sy.mean_, sy2.mean_)

    def test_contexto_passado_legitimo_na_fronteira_sem_usar_alvo(self):
        dias = pd.date_range("2025-01-01", periods=8)
        frame = pd.DataFrame({"Active_Power": np.arange(8) / 20}, index=dias)
        sx, sy = ajustar_escalas_fonte(frame, list(frame), "2025-01-04")
        antes, meta = criar_janelas(frame, list(frame), 3, "2025-01-04", "2025-01-06", sx, sy)
        outro = frame.copy()
        outro.loc["2025-01-07":] = 999.
        depois, _ = criar_janelas(outro, list(frame), 3, "2025-01-04", "2025-01-06", sx, sy)
        # Mudar o alvo de 07/01 não altera a entrada da previsão emitida em 06/01.
        pos = list(antes["datas"]).index("2025-01-07")
        np.testing.assert_array_equal(antes["X"][pos], depois["X"][pos])
        self.assertEqual(meta.loc[pos, "entrada_inicio"], pd.Timestamp("2025-01-04"))

    def test_config_nao_reintroduz_vento(self):
        raiz = Path(__file__).resolve().parents[1]
        cfg = json.loads((raiz / "experimentos/transfer_learning_australia_brasil/config.json").read_text(encoding="utf-8"))
        cfg["variaveis"][1] = "Wind_Speed"
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "sem vento"):
                carregar_config(tmp)


try:
    import torch
    from energia_transfer.transfer_learning.treinamento import ajustar, construir, erros, prever
    TEM_TORCH = True
except ImportError:
    TEM_TORCH = False


@unittest.skipUnless(TEM_TORCH, "Instalar dependências do experimento.")
class TreinoTransferTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.contrato = {"variaveis_por_passo": ["Active_Power", "meteo"],
                         "x_media_treino": [.2, 25.], "x_escala_treino": [.1, 5.],
                         "y_media_treino": .15, "y_escala_treino": .08}
        self.cfg = {"mlp_unidades": [4, 3], "lstm_unidades": 3,
                    "weight_decay": .0001, "melhoria_minima": 0.}

    def test_treino_da_saida_preserva_encoder_e_altera_head(self):
        torch.manual_seed(42)
        modelo = construir("mlp_direta", 2, self.contrato, self.cfg)
        estado = copy.deepcopy(modelo.state_dict())
        for p in modelo.encoder.parameters():
            p.requires_grad = False
        dados = {"X": np.ones((12, 2, 2), dtype=np.float32), "y": np.ones(12, dtype=np.float32)}
        modelo, _, _ = ajustar(modelo, dados, dados, 42, .01, 4, 4, 2, self.cfg)
        self.assertTrue(all(torch.equal(v, estado[k]) for k, v in modelo.state_dict().items() if k.startswith("encoder")))
        self.assertFalse(torch.equal(modelo.head.bias, estado["head.bias"]))

    def test_residual_nula_mantem_potencia_pu_sem_usar_capacidade_brasileira_no_modelo(self):
        modelo = construir("mlp_residual", 2, self.contrato, self.cfg)
        for p in modelo.parameters():
            torch.nn.init.zeros_(p)
        x = np.zeros((2, 2, 2), dtype=np.float32)
        x[:, -1, 0] = [-1., 2.]
        pred = prever(modelo, {"X": x}, self.contrato)
        np.testing.assert_allclose(pred, [.1, .4], atol=1e-7)

    def test_skill_negativo_e_r2_negativo_nao_sao_suprimidos(self):
        m = erros([.1, .2, .3], [1., 1., 1.], [.1, .1, .2])
        self.assertLess(m["skill_persistencia_pct"], 0)
        self.assertLess(m["R2"], 0)
        self.assertAlmostEqual(m["MAE_pu"] * 1000, 800.)


if __name__ == "__main__":
    unittest.main()
