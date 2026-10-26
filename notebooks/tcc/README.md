# Notebooks de apoio ao TCC

| Notebook | Escopo | Figuras |
|---|---|---:|
| [03_02_caracterizacao_dados_crus.ipynb](03_02_caracterizacao_dados_crus.ipynb) | Dados crus, subseções 3.2.1 a 3.2.4 | 9 |
| [03_03_tratamento_e_preprocessamento.ipynb](03_03_tratamento_e_preprocessamento.ipynb) | Protocolo diário aplicado, subseções 3.3.1 a 3.3.5 | 8 |

O [mapa de figuras e tabelas](../../docs/tcc/02_mapa_notebooks_e_figuras.md) indica
qual material usar em cada subseção. Os notebooks contêm explicações, saídas com
imagens e tabelas. Use o kernel `.venv` e execute de cima para baixo para reproduzir.

As figuras são exportadas em PNG (300 dpi) e PDF vetorial; cada relatório inclui
legendas propostas, tabelas CSV e manifesto das fontes. Os dados originais e os
modelos não são regravados. Na auditoria crua, intervalos de cinco minutos servem
apenas para contar presença de coleta; valores e timestamps originais são preservados.

As saídas ficam em:

- [Dados crus](../../reports/tcc/caracterizacao_dados_crus/);
- [Pré-processamento diário](../../reports/tcc/preprocessamento_diario/).

Apenas a auditoria crua também pode ser executada pela linha de comando:

```powershell
.venv\Scripts\python.exe scripts/caracterizar_bases_tcc.py
```
