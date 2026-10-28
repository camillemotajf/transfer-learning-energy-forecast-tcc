"""Evita confundir energia elétrica, irradiação por minuto e extremos de irradiância."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from energia_transfer.dicionario_leopoldo import descrever_coluna
from energia_transfer.dicionario_colunas import significado


class TestDicionarioLeopoldo(unittest.TestCase):
    def test_minuto_em_energia_solar_e_minimo_em_irradiancia(self):
        minuto=descrever_coluna('ghi_kwh_min')
        minimo=descrever_coluna('ghi_irr_min')
        self.assertIn('um minuto',minuto['significado_pt'])
        self.assertIn('mínima',minimo['significado_pt'])
        self.assertIn('por minuto',significado('ghi_kwh_min')[0])
        self.assertIn('por minuto',significado('precipitacao_acc_min')[0])

    def test_energia_eletrica_nao_e_energia_por_area(self):
        self.assertEqual(descrever_coluna('daily_power_yields_kwh')['unidade'],'kWh')
        self.assertIn('kWh/m²',descrever_coluna('ghi_kwh_day')['unidade'])
        self.assertIn('min_count=1',descrever_coluna('total_active_power_w')['origem_tratamento'])

    def test_sufixo_est_e_escala_local_permanecem_pendentes(self):
        self.assertIn('não tem definição',descrever_coluna('poa_kwh_day_est')['confirmacao_pendente'])
        self.assertIn('a confirmar',descrever_coluna('gri_irr_med')['significado_pt'])


if __name__=='__main__':unittest.main()
