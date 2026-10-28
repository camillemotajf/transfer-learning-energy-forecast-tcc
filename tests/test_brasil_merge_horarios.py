"""Verifica a soma completa, os horários locais e a ausência de duplicação no merge."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from energia_transfer.brasil_merge_horarios import alinhar_fonte, consolidar_inversores, extrair_base_usina, INVERSORES


class TestMergeBrasil(unittest.TestCase):
    def test_energia_e_potencia_sao_somadas_separadamente_sem_soma_parcial(self):
        linhas=[]
        for e in INVERSORES:
            linhas.append(dict(datetime='2025-01-01T03:00:00Z',usine_code='07-07FX',equipment_name=e,
                total_active_power_w=1000.,total_dc_power_w=1100.,daily_power_yields_kwh=10.,
                monthly_power_yields_kwh=100.,total_power_yields_kwh=10000.))
        linhas[-1]['total_power_yields_kwh']=np.nan
        cols=['total_active_power_w','total_dc_power_w','daily_power_yields_kwh','monthly_power_yields_kwh','total_power_yields_kwh']
        alinhados,_,_=alinhar_fonte(pd.DataFrame(linhas),cols)
        base=consolidar_inversores(alinhados,pd.date_range('2025-01-01',periods=2,freq='5min'))
        base['estacao__est_sols1__air_temperature_med']=[25.,np.nan]
        usina=extrair_base_usina(base,['air_temperature_med'])
        self.assertEqual(usina.iloc[0].potencia_total_kw,8.)
        self.assertEqual(usina.iloc[0].potencia_dc_total_kw,8.8)
        self.assertEqual(usina.iloc[0].energia_diaria_kwh,80.)
        self.assertEqual(usina.iloc[0].energia_mensal_kwh,800.)
        self.assertTrue(pd.isna(usina.iloc[0].energia_acumulada_kwh))
        self.assertEqual(usina.iloc[0]['energia_acumulada_kwh__n_inversores'],7)
        self.assertEqual(usina.iloc[0].air_temperature_med,25.)
        self.assertFalse(any('inverter' in c for c in usina.columns))
        self.assertTrue(pd.isna(usina.iloc[1].energia_diaria_kwh))

    def test_utc_intervalo_mediana_e_soma_sem_multiplicar_linhas(self):
        linhas=[dict(datetime='2025-01-02T03:01:30Z',usine_code='07-07FX',equipment_name=e,total_active_power_w=1000.) for e in INVERSORES]
        linhas.append(dict(linhas[0],datetime='2025-01-02T03:04:59Z',total_active_power_w=3000.))
        alinhados,mapa,meta=alinhar_fonte(pd.DataFrame(linhas),['total_active_power_w'])
        grade=pd.date_range('2025-01-02',periods=2,freq='5min')
        base=consolidar_inversores(alinhados,grade)
        self.assertEqual(len(base),2)
        self.assertEqual(base.iloc[0].potencia_total_w,9000.)
        self.assertEqual(base.iloc[0].potencia_total_kw,9.)
        self.assertTrue(pd.isna(base.iloc[1].potencia_total_w))
        self.assertEqual(meta['registros_excedentes_consolidados'],1)
        self.assertEqual(mapa.iloc[0].deslocamento_segundos,90.)
        self.assertEqual(mapa.iloc[0].intervalo,pd.Timestamp('2025-01-02'))

    def test_sete_inversores_nao_geram_total_e_zero_e_observacao(self):
        linhas=[dict(datetime='2025-01-01T03:00:00Z',usine_code='07-07FX',equipment_name=e,total_active_power_w=0.) for e in INVERSORES]
        linhas[-1]['total_active_power_w']=np.inf
        alinhados,_,_=alinhar_fonte(pd.DataFrame(linhas),['total_active_power_w'])
        base=consolidar_inversores(alinhados,pd.date_range('2025-01-01',periods=1,freq='5min'))
        self.assertEqual(base.iloc[0].n_inversores_com_potencia,7)
        self.assertTrue(pd.isna(base.iloc[0].potencia_total_w))
        linhas[-1]['total_active_power_w']=0.
        alinhados,_,_=alinhar_fonte(pd.DataFrame(linhas),['total_active_power_w'])
        base=consolidar_inversores(alinhados,pd.date_range('2025-01-01',periods=1,freq='5min'))
        self.assertEqual(base.iloc[0].potencia_total_w,0.)
        self.assertTrue(base.iloc[0].potencia_total_disponivel)


if __name__=='__main__':
    unittest.main()
