"""Ausências e estatísticas por sistema após o alinhamento temporal."""
from pathlib import Path
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from energia_transfer.caracterizacao_sistemas_tcc import descrever_fonte, sinalizar_variavel, carregar_csv_brasil, EXCLUIR_AU


class TestCaracterizacaoSistemas(unittest.TestCase):
    def test_grade_completa_preserva_potencia_sem_estacao_e_separa_indicadores(self):
        original=pd.DataFrame({'datetime':['2025-01-01 03:00:00+00:00','2025-01-01 03:05:00+00:00'],
            'usine_code':['07-07FX']*2,'total_active_power_w':[1200.,np.nan],
            'air_temperature_med':[np.nan,25.], 'tem_registro_inversores':[True,False],
            'tem_registro_estacao':[False,True], 'n_inversores':[8,0], 'n_inversores_potencia':[8,0]})
        valores,registros,_,_,meta=carregar_csv_brasil(original)
        self.assertEqual(valores.iloc[0].potencia_total_kw,1.2)
        self.assertTrue(registros.iloc[0].potencia_total_kw)
        self.assertFalse(registros.iloc[0].air_temperature_med)
        self.assertTrue(registros.iloc[1].air_temperature_med)
        self.assertNotIn('n_inversores_potencia',valores.columns)
        self.assertEqual(meta['intervalos_oito_inversores'],1)

    def test_csv_manual_preserva_potencia_sem_presumir_oito_contribuintes(self):
        original=pd.DataFrame({'datetime':['2025-01-01 03:00:00+00:00','2025-01-01 03:05:00+00:00'],
            'usine_code':['07-07FX','07-07FX'],'total_active_power_w':[1200.,np.nan],
            'daily_power_yields_kwh':[30.,np.nan],'air_temperature_med':[25.,26.]})
        antes=original.copy(deep=True)
        valores,registros,desc,unidades,meta=carregar_csv_brasil(original)
        self.assertEqual(valores.iloc[0].potencia_total_kw,1.2)
        self.assertTrue(pd.isna(valores.iloc[1].potencia_total_kw))
        self.assertFalse(registros.iloc[2].potencia_total_kw)
        self.assertTrue(registros.iloc[1].potencia_total_kw)
        self.assertEqual(meta['linhas_usina_no_ano'],2)
        self.assertEqual(len(valores),105120)
        self.assertNotIn('daily_power_yields_kwh',valores)
        pd.testing.assert_frame_equal(original,antes)

    def test_csv_manual_com_horarios_repetidos_nao_e_reconsolidado_silenciosamente(self):
        original=pd.DataFrame({'datetime':['2025-01-01 03:00:00+00:00']*2,
            'usine_code':['07-07FX']*2,'total_active_power_w':[1000.,2000.]})
        with self.assertRaisesRegex(ValueError,'duplicados'):carregar_csv_brasil(original)

    def test_temperatura_dos_modulos_nao_recebe_limite_de_temperatura_do_ar(self):
        s=pd.Series([75.,np.nan])
        ar,_=sinalizar_variavel(s,'air_temperature_max')
        modulo,_=sinalizar_variavel(s,'pv_temperatura_max')
        self.assertEqual(ar.tolist(),[True,False])
        self.assertEqual(modulo.tolist(),[False,False])

    def test_potencia_incompleta_distingue_registro_sem_total_de_ausencia_de_linha(self):
        idx=pd.date_range('2025-01-01',periods=4,freq='5min')
        v=pd.DataFrame({'potencia_total_kw':[0.,8.,np.nan,np.nan],
                        'temperatura':[20.,np.nan,22.,np.nan]},index=idx)
        r=pd.DataFrame({'potencia_total_kw':[True,True,True,False],
                        'temperatura':[True,True,True,False]},index=idx)
        d=descrever_fonte(v,r,'Brasil',dict.fromkeys(v,'Teste'),dict.fromkeys(v,'unidade'))
        t=d['estatisticas'].set_index('variavel').loc['potencia_total_kw']
        self.assertEqual(t.intervalos_disponiveis,2)
        self.assertEqual(t.registro_sem_valor_disponivel,1)
        self.assertEqual(t.intervalos_sem_registro,1)
        self.assertEqual(t.cobertura_pct,50.)
        self.assertEqual(t.media,4.)
        self.assertEqual(t.zeros,1)
        self.assertEqual(d['cobertura_mensal'].iloc[0].potencia_total_kw,50.)

    def test_canal_vazio_permanece_no_inventario_e_eletricas_auxiliares_sao_excluidas(self):
        idx=pd.date_range('2025-01-01',periods=2,freq='5min')
        v=pd.DataFrame({'ghi':[np.nan,np.nan]},index=idx)
        r=pd.DataFrame({'ghi':[True,False]},index=idx)
        d=descrever_fonte(v,r,'Estação',{'ghi':'GHI'},{'ghi':'a confirmar'})
        t=d['estatisticas'].iloc[0]
        self.assertEqual(t.cobertura_pct,0.)
        self.assertEqual(t.registro_sem_valor_disponivel,1)
        self.assertTrue(pd.isna(t.media))
        self.assertIn('Current_Phase_Average',EXCLUIR_AU)
        self.assertIn('Active_Energy_Delivered_Received',EXCLUIR_AU)


if __name__=='__main__':unittest.main()
