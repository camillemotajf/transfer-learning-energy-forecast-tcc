# Notebooks de apoio ao TCC

| Notebook | Escopo | Figuras |
|---|---|---:|
| [03_01_brasil_merge_horarios.ipynb](03_01_brasil_merge_horarios.ipynb) | Gera o CSV de cinco minutos com potência e energia somadas dos oito inversores e canais da estação | 1 |
| [03_02_caracterizacao_dados_crus.ipynb](03_02_caracterizacao_dados_crus.ipynb) | Potência e meteorologia; Brasil a partir de Leopoldo_base_consolidada_5min.csv fornecido pelo pesquisador | 7 |
| [03_03_tratamento_e_preprocessamento.ipynb](03_03_tratamento_e_preprocessamento.ipynb) | Tratamento horário em todos os blocos; Brasil com AP, Austrália com AP/GHI/temperatura/RH/vento; código e diagnóstico nas células | 10 |
| [03_04_construcao_sequencias_temporais.ipynb](03_04_construcao_sequencias_temporais.ipynb) | Compara históricos 24/48/168/240 → 24 h; auditoria estrita dos 24 alvos, tensores e cobertura sazonal | 0 |
| [04_01_estrategia_entrada_240h_24h.ipynb](04_01_estrategia_entrada_240h_24h.ipynb) | Sliding window: 240 horas anteriores → vetor das próximas 24 horas; treino horário e avaliação diária | 3 |

O [mapa de figuras e tabelas](../../docs/tcc/02_mapa_notebooks_e_figuras.md) indica
qual material usar em cada subseção. Os notebooks contêm explicações, saídas com
imagens e tabelas. Selecione um kernel Python com as dependências de
`requirements.txt` e execute de cima para baixo para reproduzir.
O 03_03 foi executado com o Python da `.venv`, com `pandas`, `numpy`,
`matplotlib` e `IPython`. Execute suas células de cima para baixo; os links do
GitHub são referências bibliográficas e não executam código externo.

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
- [Tratamento horário atual do 03_03](../../reports/tcc/preprocessamento_horario_bak2025/);
- [Pré-processamento diário anterior](../../reports/tcc/preprocessamento_diario/).

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

O 03_03 agrega cinco minutos em horas, aplica a triagem disponível em cada domínio,
reprova dias com duas faltas horárias consecutivas e interpola faltas isoladas.
A configuração final inclui **todos os blocos**, preservando datas e `bloco_id`.
No Brasil, usa AP; na Austrália, usa as cinco variáveis da imagem: AP, GHI,
temperatura, umidade e velocidade do vento. As contagens e máscaras de interpolação
são exportadas. A unidade original do vento australiano precisa ser confirmada.

As bases principais têm sufixo `*_todos_blocos.csv.gz`; os arquivos `*_bloco.csv.gz`
conservam o maior bloco apenas como diagnóstico. O calendário completo com lacunas
é exportado separadamente. A base diária derivada contém todos os dias com 24 horas
aprovadas. Brasil: 6.310 horas, 261 dias completos, 30 blocos. Austrália: 26.710 horas,
1.111 dias completos, 28 blocos com as cinco variáveis.

A seção complementar mantém o estudo da estação brasileira, com duas figuras,
seis tabelas e [resumo](../../reports/tcc/preprocessamento_horario_bak2025/estudo_estacao_sem_vento/resumo.md).
Seus cenários meteorológicos são diagnósticos e não integram as entradas brasileiras.

A auditoria exemplifica janelas de 24 horas e alvo uma hora à frente, respeitando
blocos, partições e disponibilidade das interpolações. As partições 70/15/15 são
cronológicas sobre todas as horas elegíveis; nenhum modelo foi treinado. AP é a
entrada comum entre domínios: utilizar cinco entradas no modelo de origem exige
uma arquitetura de adaptação explícita para o Brasil univariado.

## Estratégia 04_01: previsão das próximas 24 horas

O [04_01](04_01_estrategia_entrada_240h_24h.ipynb) consome as bases horárias de todos os
blocos do 03_03 e preserva suas partições. Cada amostra contém 240 horas de histórico
e um vetor-alvo de 24 potências horárias futuras, conforme o comprimento de entrada
e saída da Tabela 5 de Bak et al. (2025). O avanço no treino é de uma hora; validação
e teste principais usam emissão às 00h e exigem os 24 alvos sem alteração/interpolação.
Histórico e alvo permanecem no mesmo bloco e na mesma partição. A disponibilidade
da borda direita das interpolações também é verificada.

Austrália: `X=(N,240,5)` com GHI, temperatura, RH, vento e AP; Brasil: `X=(N,240,1)`.
`X_potencia` prepara o cenário univariado também na origem, e `y=(N,24)` nos dois países.
A potência usa p.u. pela capacidade adotada; meteorologia recebe z-score só no treino.
São escolhas explícitas de preparação, sem implementação de PatchTST, destilação ou treino.

- [Tensores NPZ](../../data/processed/janelas_240h_24h/): seis arquivos, separados por país e partição;
- [Relatório e figuras](../../reports/tcc/04_01_estrategia_240h_24h/): contagens, índices, escalas, verificações e manifesto.

Brasil: **1.227 janelas horárias de treino, 17 dias de validação e 9 dias de teste**.
As contagens dependem das fronteiras conservadoras herdadas. Janelas sobrepostas não
são amostras independentes. O treino conserva máscaras dos alvos tratados; a avaliação
principal utiliza somente vetores sem alteração, mantendo indicadores de soma parcial.

## Construção de sequências 03_04

O [03_04](03_04_construcao_sequencias_temporais.ipynb) compara quatro históricos
com horizonte fixo de 24 horas, preservando as bases do 03_03. Exige todos os
alvos observados nas três partições e disponibilidade do histórico na emissão.
Exporta 24 NPZ com X, X_potencia, y, y_kw, timestamps, máscaras e cobertura.
As partições 70/15/15 permanecem provisórias; a cobertura mensal ajuda a revisá-las.

- [Auditoria e contagens](../../reports/tcc/03_04_sequencias_temporais/)
- [Tensores](../../data/processed/sequencias_temporais_24h/)
- [Análise dos resultados e limitações](../../reports/tcc/03_04_sequencias_temporais/resumo.md)

O protocolo principal é horário para todas as partições. Também informa emissões
à meia-noite e a interseção de emissões entre os quatro históricos. O 04_01 conserva
seu protocolo anterior: treino com alvos tratados e avaliação diária. Suas contagens
não são diretamente equivalentes às do 03_04. Nenhuma etapa treina modelos.
