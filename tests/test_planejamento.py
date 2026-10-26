import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from energia_transfer.caminhos import CaminhosProjeto, localizar_raiz
from energia_transfer.planejamento import listar_janelas


class PlanejamentoTests(unittest.TestCase):
    def preparar(self, raiz):
        caminhos = CaminhosProjeto(raiz)
        caminhos.preparar_saidas()
        blocos = pd.DataFrame({"bloco_id": [1, 2], "inicio": ["2025-02-01", "2025-02-10"],
                               "fim": ["2025-02-04", "2025-02-14"], "dias": [4, 5]})
        blocos.to_csv(caminhos.base_final / "blocos_consecutivos_leopoldo.csv", index=False)
        datas = pd.date_range("2025-02-01", "2025-02-04").append(pd.date_range("2025-02-10", "2025-02-14"))
        pd.DataFrame({"timestamp": datas, "Active_Power": 1.}).to_csv(caminhos.processados_brasil / "base_diaria_leopoldo_dias_validos.csv", index=False)
        return caminhos

    def test_horizonte_multiplos_dias_nao_atravessa_lacuna(self):
        with tempfile.TemporaryDirectory() as raiz:
            caminhos = self.preparar(raiz)
            janelas = listar_janelas(historico=2, horizonte=2, caminhos=caminhos)
            self.assertEqual(len(janelas), 3)
            self.assertEqual(janelas.bloco_id.tolist(), [1, 2, 2])
            self.assertTrue(janelas.alvo_fim.sub(janelas.alvo_inicio).eq(pd.Timedelta(days=1)).all())
            self.assertEqual(janelas.iloc[0].alvo_fim, pd.Timestamp("2025-02-04"))
            self.assertEqual(janelas.iloc[1].entrada_inicio, pd.Timestamp("2025-02-10"))

    def test_data_ausente_dentro_de_bloco_declaro_e_detectada(self):
        with tempfile.TemporaryDirectory() as raiz:
            caminhos = self.preparar(raiz)
            arquivo = caminhos.processados_brasil / "base_diaria_leopoldo_dias_validos.csv"
            base = pd.read_csv(arquivo)
            base.loc[base.timestamp.ne("2025-02-12")].to_csv(arquivo, index=False)
            with self.assertRaisesRegex(ValueError, "datas ausentes"):
                listar_janelas(caminhos=caminhos)

    def test_raiz_e_localizada_a_partir_de_subpasta_do_notebook(self):
        with tempfile.TemporaryDirectory() as raiz:
            raiz = Path(raiz).resolve()
            (raiz / "src/energia_transfer").mkdir(parents=True)
            pasta = raiz / "notebooks/exploratorio"
            pasta.mkdir(parents=True)
            self.assertEqual(localizar_raiz(pasta), raiz)


if __name__ == "__main__":
    unittest.main()
