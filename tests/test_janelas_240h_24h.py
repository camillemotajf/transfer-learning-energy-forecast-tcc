"""Verifica o contrato de entrada/saída do notebook 04_01 sem executar a análise."""
import ast
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


NOTEBOOK = Path(__file__).resolve().parents[1] / 'notebooks/tcc/04_01_estrategia_entrada_240h_24h.ipynb'
NOMES = {'validar_base_janelas', 'indexar_janelas_multiplos_passos',
         'selecionar_protocolo', 'normalizar_entradas', 'materializar_janelas'}
for celula in json.loads(NOTEBOOK.read_text(encoding='utf-8'))['cells']:
    if celula['cell_type'] != 'code':
        continue
    arvore = ast.parse(''.join(celula['source']))
    funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in NOMES]
    if funcoes:
        exec(compile(ast.Module(body=funcoes, type_ignores=[]), str(NOTEBOOK), 'exec'), globals())


class TestJanelasDayAhead(unittest.TestCase):
    def base(self, n=300):
        idx = pd.date_range('2025-01-01', periods=n, freq='h', name='timestamp')
        return pd.DataFrame({
            'Active_Power': np.arange(n, dtype=float),
            'Temp': np.arange(n, dtype=float) / 10,
            'bloco_id': 1, 'particao_proposta': 'treino',
            'disponivel_em': idx + pd.Timedelta(hours=1),
            'potencia_observada_horaria': True, 'n_5min_Active_Power': 12,
            'interpolado_Active_Power': False, 'interpolado_Temp': False,
        }, index=idx)

    def test_240_entradas_e_vetor_com_as_24_horas_seguidas(self):
        d = self.base()
        indice, _ = indexar_janelas_multiplos_passos(d, ['Temp', 'Active_Power'])
        self.assertEqual(len(indice), 37)
        matriz, _ = normalizar_entradas(d, ['Temp', 'Active_Power'], 100.)
        p = materializar_janelas(d, indice, matriz, ['Temp', 'Active_Power'], 100.)
        self.assertEqual(p['X'].shape, (37, 240, 2))
        self.assertEqual(p['X_potencia'].shape, (37, 240, 1))
        self.assertEqual(p['y'].shape, (37, 24))
        np.testing.assert_allclose(p['y'][0], np.arange(240, 264) / 100.)
        np.testing.assert_allclose(p['y'][1], np.arange(241, 265) / 100.)
        self.assertTrue((p['timestamps_y'][0] == d.index[240:264].to_numpy()).all())
        self.assertTrue((p['timestamps_y'][:, 0] == p['emissao']).all())

    def test_nao_atravessa_blocos_e_preserva_lacuna_no_relogio(self):
        a = self.base()
        b = self.base(); b.index = b.index + pd.Timedelta(days=20)
        b['disponivel_em'] = b.index + pd.Timedelta(hours=1)
        b['bloco_id'] = 2
        d = pd.concat([a, b])
        indice, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'])
        self.assertEqual(len(indice), 74)
        for _, r in indice.iterrows():
            trecho = d.iloc[r.inicio_hist_pos:r.fim_alvo_pos+1]
            self.assertEqual(trecho.bloco_id.nunique(), 1)
            self.assertTrue(trecho.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all())
        d['bloco_id'] = 1
        with self.assertRaises(ValueError):
            indexar_janelas_multiplos_passos(d, ['Active_Power'])

    def test_historico_e_vetor_alvo_na_mesma_particao(self):
        d = self.base(600)
        d.loc[d.index[300:], 'particao_proposta'] = 'teste'
        indice, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'])
        self.assertEqual(len(indice), 74)
        for _, r in indice.iterrows():
            self.assertEqual(d.iloc[r.inicio_hist_pos:r.fim_alvo_pos+1].particao_proposta.nunique(), 1)

    def test_interpolacao_futura_nao_pode_ser_usada_na_emissao(self):
        d = self.base()
        d.loc[d.index[239], 'disponivel_em'] = d.index[241]
        indice, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'])
        self.assertFalse(indice.historico_disponivel.iloc[0])
        self.assertTrue(indice.historico_disponivel.iloc[1])
        self.assertEqual(len(selecionar_protocolo(indice)), 36)

    def test_teste_diario_exige_observacao_em_todo_o_vetor(self):
        d = self.base(); d['particao_proposta'] = 'teste'
        # Uma falta no meio do vetor é suficiente para rejeitar a avaliação diária.
        d.loc[d.index[250], 'potencia_observada_horaria'] = False
        indice, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'])
        selecionadas = selecionar_protocolo(indice)
        self.assertEqual(len(selecionadas), 1)
        self.assertEqual(selecionadas.emissao.iloc[0], d.index[264])
        self.assertTrue(selecionadas.saida_total_observada.all())

    def test_estatisticas_meteorologicas_usam_somente_o_treino(self):
        d = self.base(20)
        d.loc[d.index[10:], 'particao_proposta'] = 'teste'
        _, antes = normalizar_entradas(d, ['Temp', 'Active_Power'], 100.)
        d.loc[d.index[10:], 'Temp'] = 99999.
        _, depois = normalizar_entradas(d, ['Temp', 'Active_Power'], 100.)
        pd.testing.assert_frame_equal(antes, depois)


if __name__ == '__main__':
    unittest.main()
