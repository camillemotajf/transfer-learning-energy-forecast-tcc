import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.deep_learning.dados import ajustar_escalas, carregar_config, criar_janelas, entradas_causais, limpar_diario, selecionar


def configuracao():
    return {"fim_treino": "2025-01-04", "fim_validacao": "2025-01-06",
            "limites_operacionais": {"Weather_Temperature_Celsius": [-20, 60]},
            "limite_ffill_meteorologia_dias": 2}


class DadosDeepLearningTests(unittest.TestCase):
    def test_ffill_so_usa_passado_limita_dois_dias_e_preserva_alvo(self):
        dias = pd.date_range("2025-01-01", periods=8)
        df = pd.DataFrame({"Active_Power": [0., 1, 2, np.nan, 4, 5, 6, 7],
                           "Weather_Temperature_Celsius": [20., np.nan, np.nan, np.nan, 40., 30., 32., 34.]}, index=dias)
        _, limpo, _ = limpar_diario(df, configuracao())
        entradas, flags = entradas_causais(limpo, configuracao())
        np.testing.assert_allclose(entradas.iloc[1:3].Weather_Temperature_Celsius, [20., 20.])
        self.assertTrue(np.isnan(entradas.iloc[3].Weather_Temperature_Celsius))
        pd.testing.assert_series_equal(entradas.Active_Power, limpo.Active_Power)
        self.assertEqual(int(flags.Weather_Temperature_Celsius.sum()), 2)
        alterado = limpo.copy()
        alterado.loc[dias[4]:, "Weather_Temperature_Celsius"] = 1e6
        segunda, _ = entradas_causais(alterado, configuracao())
        pd.testing.assert_frame_equal(entradas.loc[:dias[3]], segunda.loc[:dias[3]])

    def test_janelas_nao_atravessam_data_sem_potencia(self):
        dias = pd.date_range("2025-01-01", periods=8).delete(2)
        df = pd.DataFrame({"Active_Power": np.arange(7, dtype=float), "Weather_Temperature_Celsius": 20.}, index=dias)
        _, limpo, _ = limpar_diario(df, configuracao())
        entradas, flags = entradas_causais(limpo, configuracao())
        x, y, meta = criar_janelas(entradas, limpo.Active_Power, ["Active_Power"], 2, configuracao(), flags)
        self.assertEqual(x.shape, (3, 2, 1))
        self.assertEqual(meta.timestamp.tolist(), list(pd.date_range("2025-01-06", periods=3)))
        self.assertTrue(meta.timestamp.sub(meta.entrada_fim).eq(pd.Timedelta(days=1)).all())
        self.assertEqual(meta.particao.tolist(), ["validacao", "teste", "teste"])

    def test_escalas_ignoram_extremos_no_futuro(self):
        dias = pd.date_range("2025-01-01", periods=10)
        df = pd.DataFrame({"Active_Power": np.arange(10, dtype=float)}, index=dias)
        sx, sy = ajustar_escalas(df, df.Active_Power, ["Active_Power"], "2025-01-04")
        df.loc["2025-01-05":] = 1e9
        sx2, sy2 = ajustar_escalas(df, df.Active_Power, ["Active_Power"], "2025-01-04")
        np.testing.assert_array_equal(sx.mean_, sx2.mean_)
        np.testing.assert_array_equal(sy.mean_, sy2.mean_)

    def test_vento_nao_pode_ser_reintroduzido_na_configuracao(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = dict(configuracao(), horizonte_dias=1, grupos_entradas={"ruim": ["Wind_Speed"]}, variaveis_excluidas=[])
            (Path(tmp) / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Vento"):
                carregar_config(tmp)

    def test_selecao_de_inputs_e_lags_nao_consulta_o_teste(self):
        dias = pd.date_range("2025-01-01", periods=120)
        x = pd.DataFrame({"Active_Power": 5 + np.sin(np.arange(120) / 4), "Weather_Temperature_Celsius": 20 + np.cos(np.arange(120) / 7)}, index=dias)
        cfg = dict(configuracao(), fim_treino="2025-02-19", fim_validacao="2025-03-31", max_faltantes_treino_pct=20,
                   grupos_entradas={"base": ["Active_Power"], "meteo": ["Active_Power", "Weather_Temperature_Celsius"]},
                   lags_candidatos=[1, 3], alphas_ridge=[1.])
        flags = pd.DataFrame(False, index=x.index, columns=x.columns)
        _, antes, _, _ = selecionar(x, x.Active_Power, x, cfg, flags)
        alterado = x.copy()
        alterado.loc["2025-04-01":] = 1e6
        _, depois, _, _ = selecionar(alterado, alterado.Active_Power, alterado, cfg, flags)
        pd.testing.assert_frame_equal(antes, depois)


try:
    import torch
    from energia_transfer.deep_learning.modelos import LSTM, MLP, MLPResidual, congelar_encoder
    TEM_TORCH = True
except ImportError:
    TEM_TORCH = False


@unittest.skipUnless(TEM_TORCH, "Instalar requirements do experimento para testar as redes.")
class ModelosDeepLearningTests(unittest.TestCase):
    def test_correcao_nula_reproduz_persistencia_com_escalas_distintas(self):
        contrato = {"lookback": 3, "variaveis_por_passo": ["meteo", "Active_Power"],
                    "x_media_treino": [20., 10.], "x_escala_treino": [3., 2.],
                    "y_media_treino": 7., "y_escala_treino": 4.}
        modelo = MLPResidual(contrato, unidades=(4,))
        for p in modelo.parameters():
            torch.nn.init.zeros_(p)
        x = torch.zeros(2, 3, 2)
        x[:, -1, 1] = torch.tensor([-2., 3.])
        with torch.no_grad():
            potencia = modelo(x) * 4. + 7.
        torch.testing.assert_close(potencia, torch.tensor([6., 16.]))
        x[:, :-1, :] = 1000.
        with torch.no_grad():
            torch.testing.assert_close(modelo(x) * 4. + 7., potencia)

    def test_lstm_nao_carrega_estado_entre_janelas(self):
        torch.manual_seed(42)
        modelo = LSTM(2, unidades=4).eval()
        a, b = torch.randn(2, 3, 2), torch.randn(2, 3, 2)
        with torch.no_grad():
            antes = modelo(a)
            modelo(b)
            depois = modelo(a)
        torch.testing.assert_close(antes, depois, rtol=0, atol=0)

    def test_congelar_encoder_permite_gradiente_apenas_na_saida(self):
        modelo = congelar_encoder(MLP(3, 2, unidades=(4,)))
        modelo(torch.ones(2, 3, 2)).sum().backward()
        self.assertTrue(all(not p.requires_grad and p.grad is None for p in modelo.encoder.parameters()))
        self.assertTrue(all(p.requires_grad and p.grad is not None for p in modelo.head.parameters()))


if __name__ == "__main__":
    unittest.main()
