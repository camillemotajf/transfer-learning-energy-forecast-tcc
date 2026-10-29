"""Contrato multistep do 03_04, sem executar dados ou exportações do notebook."""
import ast
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


NOTEBOOK = Path(__file__).resolve().parents[1] / 'notebooks/tcc/03_04_construcao_sequencias_temporais.ipynb'
NOMES = {'validar_base_janelas', 'indexar_janelas_multiplos_passos',
         'selecionar_observadas', 'normalizar_entradas', 'materializar_sequencias'}
for celula in json.loads(NOTEBOOK.read_text(encoding='utf-8'))['cells']:
    if celula['cell_type'] == 'code':
        arvore = ast.parse(''.join(celula['source']))
        funcoes = [n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name in NOMES]
        exec(compile(ast.Module(body=funcoes, type_ignores=[]), str(NOTEBOOK), 'exec'), globals())


class TestSequenciasTemporais(unittest.TestCase):
    def base(self, n):
        idx = pd.date_range('2025-01-01', periods=n, freq='h', name='timestamp')
        return pd.DataFrame(dict(Active_Power=np.arange(n, dtype=float),
            bloco_id=1, particao_proposta='treino', disponivel_em=idx+pd.Timedelta(hours=1),
            potencia_observada_horaria=True, n_5min_Active_Power=12,
            interpolado_Active_Power=False), index=idx)

    def test_cada_historico_produz_vetor_completo_com_alinhamento_correto(self):
        for h in [24, 48, 168, 240]:
            with self.subTest(h=h):
                d = self.base(h+25)
                idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], h, 24)
                idx = selecionar_observadas(idx)
                matriz, _ = normalizar_entradas(d, ['Active_Power'], 100.)
                pacote = materializar_sequencias(d, idx, matriz, ['Active_Power'], 100., h)
                self.assertEqual(pacote['X'].shape, (2, h, 1))
                self.assertEqual(pacote['y'].shape, (2, 24))
                np.testing.assert_array_equal(pacote['y_kw'][0], np.arange(h, h+24))
                np.testing.assert_array_equal(pacote['timestamps_y'][1], d.index[h+1:h+25])

    def test_rejeita_alvo_intermediario_nao_observado_inclusive_no_treino(self):
        d = self.base(72)
        d.loc[d.index[35], 'potencia_observada_horaria'] = False
        idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], 24, 24)
        sel = selecionar_observadas(idx)
        self.assertEqual(len(sel), 13)
        self.assertEqual(sel.emissao.iloc[0], d.index[36])

    def test_rejeita_interpolacao_ainda_indisponivel(self):
        d = self.base(49)
        d.loc[d.index[23], 'disponivel_em'] = d.index[25]
        idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], 24, 24)
        sel = selecionar_observadas(idx)
        self.assertEqual(sel.emissao.tolist(), [d.index[25]])

    def test_fronteira_de_particao_interrompe_janelas(self):
        d = self.base(96)
        d.loc[d.index[48:], 'particao_proposta'] = 'teste'
        idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], 24, 24)
        self.assertEqual(len(idx), 2)
        self.assertEqual(idx.inicio_hist_pos.tolist(), [0, 48])

    def test_blocos_separados_nao_sao_concatenados(self):
        a, b = self.base(48), self.base(48)
        b.index = b.index+pd.Timedelta(days=7)
        b['disponivel_em'] = b.index+pd.Timedelta(hours=1)
        b['bloco_id'] = 2
        d = pd.concat([a, b])
        idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], 24, 24)
        self.assertEqual(len(idx), 2)
        d['bloco_id'] = 1
        with self.assertRaises(ValueError):
            indexar_janelas_multiplos_passos(d, ['Active_Power'], 24, 24)

    def test_base_curta_exporta_tensores_vazios_com_dimensoes(self):
        d = self.base(10)
        idx, _ = indexar_janelas_multiplos_passos(d, ['Active_Power'], 240, 24)
        matriz, _ = normalizar_entradas(d, ['Active_Power'], 100.)
        pacote = materializar_sequencias(d, selecionar_observadas(idx), matriz,
                                        ['Active_Power'], 100., 240)
        self.assertEqual(pacote['X'].shape, (0, 240, 1))
        self.assertEqual(pacote['y'].shape, (0, 24))
        self.assertEqual(pacote['timestamps_y'].shape, (0, 24))


if __name__ == '__main__':
    unittest.main()
