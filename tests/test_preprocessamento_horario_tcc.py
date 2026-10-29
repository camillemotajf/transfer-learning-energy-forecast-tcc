"""Verifica semântica horária dos autores e salvaguardas explicitadas no notebook."""
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

# Executa somente definições auxiliares extraídas do notebook, sem rodar a análise.
import ast
import json
notebook = Path(__file__).resolve().parents[1] / "notebooks/tcc/03_03_tratamento_e_preprocessamento.ipynb"
conteudo = json.loads(notebook.read_text(encoding="utf-8"))
nomes = {"validar_horas", "blocos_consecutivos", "maior_bloco", "agregar_horas",
         "repeticao_autores", "limpar_anomalias", "remover_dias_e_interpolar",
         "identificar_blocos", "auditar_janelas_blocos"}
for celula in conteudo["cells"]:
    if celula["cell_type"] != "code": continue
    arvore = ast.parse("".join(celula["source"]))
    funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in nomes]
    if funcoes:
        exec(compile(ast.Module(body=funcoes, type_ignores=[]), str(notebook), "exec"), globals())



class TestPreprocessamentoHorario(unittest.TestCase):
    def frame(self,n=72):
        return pd.DataFrame({'Active_Power':np.arange(n,dtype=float)+1},
                            index=pd.date_range('2025-01-01',periods=n,freq='h'))

    def test_media_horaria_usa_valores_disponiveis_e_audita_cobertura(self):
        d=pd.DataFrame({'p':np.arange(24,dtype=float)},index=pd.date_range('2025-01-01',periods=24,freq='5min'))
        d.iloc[:4,0]=np.nan
        m,c=agregar_horas(d)
        self.assertEqual(c.p.tolist(),[8,12])
        self.assertEqual(m.p.iloc[0],7.5)

    def test_contador_adicional_usa_ultimo_e_nao_media(self):
        d=pd.DataFrame({'e':range(12)},index=pd.date_range('2025-01-01',periods=12,freq='5min'))
        m,_=agregar_horas(d,['e'])
        self.assertEqual(m.e.iloc[0],11)

    def test_repeticao_exclui_zeros_e_replica_dez_comparacoes(self):
        p=pd.Series([0.]*15+[2.]*12)
        mask=repeticao_autores(p)
        self.assertFalse(mask.iloc[:25].any())
        self.assertEqual(mask.iloc[25:].tolist(),[True,True])

    def test_lacuna_isolada_interpolada_duas_horas_removem_dia(self):
        d=self.frame();d.iloc[5,0]=np.nan;d.iloc[30:32,0]=np.nan
        x,m,disp,dias=remover_dias_e_interpolar(d,['Active_Power'])
        self.assertEqual(x.iloc[5,0],6.)
        self.assertEqual(m.Active_Power.sum(),1)
        self.assertTrue(x.iloc[24:48].Active_Power.isna().all())
        self.assertEqual(disp.Active_Power.iloc[5],d.index[6])
        self.assertEqual(dias.dia_reprovado_duas_nan.tolist(),[False,True,False])

    def test_nao_preenche_bordas_ou_cruza_dia_descartado(self):
        d=self.frame();d.iloc[0,0]=np.nan;d.iloc[23:26,0]=np.nan;d.iloc[-1,0]=np.nan
        x,m,_,_=remover_dias_e_interpolar(d,['Active_Power'])
        self.assertTrue(x.iloc[[0,23,71]].Active_Power.isna().all())
        self.assertFalse(m.any().any())

    def test_limites_do_codigo_e_zero_noturno(self):
        d=pd.DataFrame({'Active_Power':[0.,1.,10.,-.1,1.],
                        'Global_Horizontal_Radiation':[0.,300.,300.,0.,0.],
                        'Weather_Temperature_Celsius':[20.,-15.,20.,20.,20.],
                        'Wind_Speed':[1.]*5,'Weather_Relative_Humidity':[50.]*5},
                       index=pd.date_range('2025-01-01',periods=5,freq='h'))
        x,_,_,maximo=limpar_anomalias(d)
        self.assertEqual(x.Active_Power.iloc[0],0.)
        self.assertTrue(pd.isna(x.Weather_Temperature_Celsius.iloc[1]))
        self.assertEqual(x.Active_Power.iloc[3],0.)
        self.assertEqual(maximo,10.)

    def test_nao_inventa_meteorologia_na_fonte_univariada(self):
        d=self.frame(24)
        x,flags,_,_=limpar_anomalias(d,usar_meteorologia=False)
        self.assertEqual(x.columns.tolist(),['Active_Power'])
        self.assertFalse(any('ghi' in c for c in flags))

    def test_blocos_nao_comprimem_dias_removidos(self):
        d=self.frame();d.iloc[30:32,0]=np.nan
        x,_,_,_=remover_dias_e_interpolar(d,['Active_Power'])
        g=blocos_consecutivos(x.Active_Power.notna())
        self.assertEqual(g.horas.tolist(),[24,24])
        self.assertEqual(maior_bloco(x.Active_Power.notna()).inicio,d.index[0])
        with self.assertRaises(ValueError):blocos_consecutivos(x.dropna().Active_Power.notna())

    def test_identificador_mantem_lacunas_e_todos_os_blocos(self):
        mascara = pd.Series([True, True, False, False, True, True, True],
                            index=pd.date_range('2025-01-01', periods=7, freq='h'))
        self.assertEqual(identificar_blocos(mascara).tolist(), [1,1,0,0,2,2,2])

    def test_janelas_nao_atravessam_blocos_ou_particoes(self):
        d = self.frame(72)
        mascara = pd.Series(True, index=d.index); mascara.iloc[24:48] = False
        d['bloco_id'] = identificar_blocos(mascara)
        d = d.loc[mascara].copy()
        d['particao_proposta'] = np.where(d.bloco_id.eq(1), 'treino', 'teste')
        d['disponivel_em'] = d.index + pd.Timedelta(hours=1)
        d['potencia_observada_horaria'] = True
        j = auditar_janelas_blocos(d, ['Active_Power'], historico=3, horizonte=1)
        self.assertEqual(len(j), 42)
        self.assertTrue(j.alvo.sub(j.fim_historico).eq(pd.Timedelta(hours=1)).all())
        self.assertTrue(j.alvo.sub(j.inicio_historico).eq(pd.Timedelta(hours=3)).all())
        # Uma fronteira dentro de um mesmo bloco também interrompe as janelas.
        d.loc[d.index[:12], 'particao_proposta'] = 'validacao'
        j = auditar_janelas_blocos(d, ['Active_Power'], historico=3, horizonte=1)
        self.assertEqual(len(j), 39)

    def test_janelas_respeitam_borda_futura_da_interpolacao(self):
        d = self.frame(8)
        d['bloco_id'] = 1; d['particao_proposta'] = 'treino'
        d['potencia_observada_horaria'] = True
        d['disponivel_em'] = d.index+pd.Timedelta(hours=1)
        # O valor das 02h usa a hora das 03h, que termina às 04h.
        d.loc[d.index[2], 'disponivel_em'] = d.index[4]
        j = auditar_janelas_blocos(d, ['Active_Power'], historico=3, horizonte=1)
        self.assertEqual(len(j), 4)
        self.assertNotIn(d.index[2], j.fim_historico.tolist())
        self.assertIn(d.index[3], j.fim_historico.tolist())


if __name__=='__main__':unittest.main()
