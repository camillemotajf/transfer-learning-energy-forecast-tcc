from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from energia_transfer.intradiario import preencher_passado,proxy_causal,calendario,janelas,COLUNAS

class IntradiarioTests(unittest.TestCase):
    def test_ffill_nao_consulta_futuro_e_nao_se_encadeia(self):
        s=pd.Series([1.,np.nan,np.nan,np.nan,np.nan,99.])
        a=preencher_passado(s);s.iloc[-1]=999999.;b=preencher_passado(s)
        np.testing.assert_allclose(a.iloc[:5],b.iloc[:5],equal_nan=True)
        np.testing.assert_allclose(a.iloc[:4],[1,1,1,1])
        self.assertTrue(np.isnan(a.iloc[4]))

    def test_proxy_limita_idade_e_nao_consulta_fim_da_lacuna(self):
        t=pd.date_range('2025-01-01',periods=300,freq='5min')
        p=pd.DataFrame(10000.,index=t,columns=range(8));p.loc[t[150:155],0]=np.nan
        falhas=pd.DataFrame(0.,index=t,columns=p.columns)
        a,_=proxy_causal(p,falhas,pd.Series(False,index=t))
        futuro=p.copy();futuro.loc[t[151]:]=20000.
        b,_=proxy_causal(futuro,falhas,pd.Series(False,index=t))
        self.assertEqual(a.loc[t[150],0],b.loc[t[150],0])
        np.testing.assert_allclose(a.loc[t[150:153],0],10000.)
        self.assertTrue(np.isnan(a.loc[t[153],0]))

    def test_alvo_e_persistencia_devem_ser_medidos(self):
        t=pd.date_range('2025-01-01',periods=12,freq='5min')
        f=pd.DataFrame({'Active_Power':np.arange(12)/100,'Active_Power_original':np.arange(12,dtype=float),
                        'diurno':True,'potencia_estimada':False},index=t)
        f.loc[t[5],'Active_Power_original']=np.nan;f=calendario(f)
        cfg={'capacidade_ac_kw':{'brasil':100},'fim_treino_brasil':'2025-01-01','fim_validacao_brasil':'2025-01-02'}
        ct={'x_media_treino':[0]*5,'x_escala_treino':[1]*5,'y_media_treino':0,'y_escala_treino':1}
        d,m=janelas(f,COLUNAS,3,ct,cfg,'brasil');datas=pd.to_datetime(d['datas'])
        self.assertNotIn(t[5],datas);self.assertNotIn(t[6],datas);self.assertIn(t[7],datas)
        self.assertTrue((m.timestamp-m.entrada_fim).eq(pd.Timedelta(minutes=5)).all())
        self.assertTrue((m.timestamp-m.entrada_inicio).eq(pd.Timedelta(minutes=15)).all())

    def test_calendario_representa_hora_local_na_resolucao_5min(self):
        t=pd.to_datetime(['2025-01-01 06:00','2025-01-01 18:00'])
        np.testing.assert_allclose(calendario(pd.DataFrame(index=t)).hora_sin,[1,-1])

    def test_hipotese_noturna_nao_e_calibrada_com_dados_futuros(self):
        t=pd.date_range('2025-01-01',periods=10,freq='5min')
        p=pd.DataFrame(0.,index=t,columns=range(8));p.loc[t[2],0]=np.nan
        falhas=pd.DataFrame(0.,index=t,columns=p.columns)
        a,_=proxy_causal(p,falhas,pd.Series(True,index=t))
        p.loc[t[-1]]=99999.
        b,_=proxy_causal(p,falhas,pd.Series(True,index=t))
        self.assertEqual(a.loc[t[2],0],b.loc[t[2],0])

if __name__=='__main__':unittest.main()
