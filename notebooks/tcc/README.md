# Notebooks de apoio ao TCC

| Notebook | Escopo | Figuras |
|---|---|---:|
| [03_01_brasil_merge_horarios.ipynb](03_01_brasil_merge_horarios.ipynb) | Gera o CSV de cinco minutos com potência e energia somadas dos oito inversores e canais da estação | 1 |
| [03_02_caracterizacao_dados_crus.ipynb](03_02_caracterizacao_dados_crus.ipynb) | Potência e meteorologia; Brasil a partir de Leopoldo_base_consolidada_5min.csv fornecido pelo pesquisador | 7 |
| [03_03_tratamento_e_preprocessamento.ipynb](03_03_tratamento_e_preprocessamento.ipynb) | Protocolo diário aplicado, subseções 3.3.1 a 3.3.5 | 8 |

O [mapa de figuras e tabelas](../../docs/tcc/02_mapa_notebooks_e_figuras.md) indica
qual material usar em cada subseção. Os notebooks contêm explicações, saídas com
imagens e tabelas. Selecione um kernel Python com as dependências de
`requirements.txt` e execute de cima para baixo para reproduzir.
Neste computador, a reprodução foi feita com o ambiente Conda `anomaly_detection`.
A `.venv` atual não contém todas as dependências necessárias, incluindo `pandas`.

As figuras são exportadas em PNG (300 dpi) e PDF vetorial; cada relatório inclui
legendas propostas, tabelas CSV e manifesto das fontes. Os dados originais e os
modelos não são regravados. O 03_02 lê exclusivamente o CSV manual
`Leopoldo_base_consolidada_5min.csv` na raiz do projeto para a análise brasileira.
Não executa nem modifica `data.ipynb`, não refaz o merge e não exige novamente oito
contribuintes. O `data.ipynb` agora usa a grade completa de cinco minutos como base,
preservando potência mesmo sem registros da estação. A soma admite parcelas
disponíveis e `n_inversores_potencia` informa a quantidade de contribuintes.
Os indicadores `tem_registro_estacao` e `tem_registro_inversores` distinguem a
presença de cada fonte das linhas vazias da grade. O 03_01 permanece como um gerador
alternativo e não substitui a fonte escolhida para o 03_02.

As saídas ficam em:

- [Fonte brasileira do 03_02: Leopoldo_base_consolidada_5min.csv](../../Leopoldo_base_consolidada_5min.csv);
- [CSV alternativo gerado pelo 03_01: brasil_merge_5_minutos.csv](../../data/interim/brasil/brasil_merge_5_minutos.csv);
- [Brasil após alinhamento de horários](../../reports/tcc/brasil_merge_horarios/);
- [Caracterização atual dos sistemas](../../reports/tcc/caracterizacao_sistemas/);
- [Auditoria original anterior](../../reports/tcc/caracterizacao_dados_crus/);
- [Pré-processamento diário](../../reports/tcc/preprocessamento_diario/).

A caracterização atual também pode ser executada pela linha de comando, usando
um Python com as dependências do projeto:

```powershell
python scripts/caracterizar_bases_tcc.py
```

As figuras 3.2-01 e 3.2-02 medem exclusivamente a disponibilidade de potência dos
sistemas australiano e brasileiro. As tabelas selecionam somente potência e
canais meteorológicos: excluem contadores de energia, corrente, tensão e outras
grandezas elétricas. O dicionário mantém todos os canais físicos da estação,
inclusive canais vazios, com cobertura calculada individualmente.
Zeros são observações disponíveis; ausências não são imputadas. A presença de
uma linha não garante potência total disponível. A meteorologia é descritiva e
não se torna entrada do cenário univariado.

O `03_01` é o notebook gerador de `data/interim/brasil/brasil_merge_5_minutos.csv`.
Cada linha representa um intervalo de cinco minutos. A potência AC, a potência DC
e as energias diária, mensal e acumulada são somadas separadamente entre os oito
inversores; os 55 canais físicos da estação são associados na mesma linha.
As energias são leituras de contadores no horário, não energia integrada nos cinco
minutos. Cada total exige oito contribuintes, sem substituir ausências por zero.
O arquivo `reports/tcc/brasil_merge_horarios/brasil_merge_5min.csv` permanece como
auditoria detalhada dos equipamentos; ele não é o CSV principal consolidado.
