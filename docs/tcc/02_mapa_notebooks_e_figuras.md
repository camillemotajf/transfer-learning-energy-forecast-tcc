# Material para as seções 3.2 e 3.3 do TCC

Os dois notebooks seguem a divisão proposta. A seção 3.2 caracteriza arquivos crus;
a seção 3.3 reproduz o protocolo diário aplicado, com as respectivas limitações.
Os arquivos originais e os resultados preditivos não são alterados.

| Seção | Notebook | Material |
|---|---|---|
| 3.2 Caracterização das bases | [03_02_caracterizacao_dados_crus.ipynb](../../notebooks/tcc/03_02_caracterizacao_dados_crus.ipynb) | 9 figuras; tabelas descritivas, ausências por dia/variável e inventário de colunas |
| 3.3 Tratamento e pré-processamento | [03_03_tratamento_e_preprocessamento.ipynb](../../notebooks/tcc/03_03_tratamento_e_preprocessamento.ipynb) | 8 figuras; contagens por etapa, validação de contadores, alvos diários, janelas e parâmetros de escala |

## 3.2 — onde usar cada figura e tabela

Pasta: [caracterizacao_dados_crus](../../reports/tcc/caracterizacao_dados_crus/).

| Subseção | Figuras sugeridas | Tabelas principais |
|---|---|---|
| 3.2.1 Base australiana | 3.2-01: cobertura diária/mensal do arquivo integral | `resumo_fontes.csv`, `australia_inventario_colunas.csv` |
| 3.2.2 Base brasileira | 3.2-02: inversores; 3.2-03: calendário da coleta | `resumo_fontes.csv`, inventários brasileiros |
| 3.2.3 Descritiva e disponibilidade | 3.2-05: distribuições cruas; 3.2-04: presença/ausência; 3.2-09: disponibilidade horária | `estatisticas.csv`, `taxas.csv`, `disponibilidade_mensal.csv` |
| 3.2.4 Ausências e inconsistências | 3.2-06: campos vazios; 3.2-07: duplicatas e valores suspeitos; 3.2-08: duração das lacunas | `flags.csv`, `lacunas.csv`, `lacunas_dia.csv`, tabelas `*_por_dia.csv` |

Nesta seção, distinguir três situações: campo vazio em uma linha presente, intervalo
sem registro e timestamp desalinhado. A presença em intervalos [t,t+5min) é uma
contagem de aquisição, sem corrigir timestamps ou consolidar valores. Os registros
crus continuam nas estatísticas, inclusive duplicatas e valores sinalizados.

O arquivo australiano integral tem 4413 dias civis, entre 25/07/2013 e 23/08/2025.
Já a aplicação diária usa somente 3812 dias até 31/12/2023. No Brasil, o inventário
explicita os dois códigos existentes no CSV dos inversores antes de detalhar 07-07FX.
Não confundir período de coleta, recorte de experimento e número de dias utilizáveis.

## 3.3 — onde usar cada figura e tabela

Pasta: [preprocessamento_diario](../../reports/tcc/preprocessamento_diario/).

| Subseção | Figuras sugeridas | Tabelas principais |
|---|---|---|
| 3.3.1 Tratamento australiano | 3.3-01: etapas e faltantes; 3.3-03: cobertura intradiária dos alvos | `australia_etapas.csv`, `australia_cobertura_alvos.csv` |
| 3.3.2 Tratamento brasileiro | 3.3-04: contadores/motivos; 3.3-05: dias aprovados e ERA5 | `brasil_motivos.csv`, `brasil_estados.csv`, `meteorologia_era5.csv` |
| 3.3.3 Potência média diária | 3.3-06: séries diárias das duas bases | séries finais exportadas; `brasil_contadores_por_inversor.csv` |
| 3.3.4 Valores ausentes | 3.3-02: exemplos de ffill; 3.3-07: dias e janelas disponíveis | `faltantes_finais_por_variavel.csv`, `lacunas_alvo_diario.csv`, `particoes.csv` |
| 3.3.5 Normalização/padronização | 3.3-08: potência p.u. e padronização do histórico brasileiro | `escalas_treino_brasil.csv`, capacidades no manifesto |

A Austrália usa médias de leituras disponíveis; o Brasil usa soma da energia dos oito
inversores aprovados dividida por 24 horas. Somente a meteorologia australiana recebe
ffill limitado a dois dias. Não há imputação de potência diária no protocolo vigente.
A base brasileira final possui 284 dias aprovados e 230 janelas de três dias mais alvo,
distribuídas em 160/26/44 para treino/validação/teste.

As capacidades de 24 kW e 1000 kW são parâmetros adotados, pendentes de confirmação
técnica definitiva. O controle dos alvos não é idêntico entre as bases: a Austrália
não recebeu filtro de cobertura mínima, e a referência brasileira exige concordância
dos contadores. A meteorologia pública é retrospectiva; a latência operacional não
foi simulada. Essas limitações devem acompanhar a metodologia.

## Exportação e numeração

Todas as figuras têm PNG em 300 dpi e PDF vetorial. Cada pasta inclui
`legendas_figuras.md`, `indice_figuras.json` e `manifesto.json` com hashes das fontes.
A numeração é provisória; a ordem de aparição no TCC determina a numeração definitiva.
As legendas descrevem denominadores e ressalvas para evitar interpretar disponibilidade
como validação física ou somar motivos de reprovação sobrepostos.
