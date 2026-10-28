# Material para as seções 3.2 e 3.3 do TCC

O [03_02](../../notebooks/tcc/03_02_caracterizacao_dados_crus.ipynb) utiliza a potência por sistema e os canais meteorológicos. No Brasil, a fonte é `Leopoldo_base_consolidada_5min.csv`, fornecida pelo pesquisador. A potência é `total_active_power_w` dividida por 1000, e as demais variáveis são os canais físicos da estação existentes no mesmo CSV. Na Austrália, utiliza-se Active_Power e os canais meteorológicos do arquivo. Contadores de energia e outras grandezas elétricas não entram nessa caracterização.

O 03_02 apenas lê o CSV manual, sem executar ou modificar `data.ipynb`. Não refaz o merge nem substitui a fonte pelo CSV alternativo gerado pelo [03_01](../../notebooks/tcc/03_01_brasil_merge_horarios.ipynb). A [auditoria original anterior](../../reports/tcc/caracterizacao_dados_crus/) permanece separada. O protocolo diário documentado no 03_03 e seus alvos não são alterados.

## 3.2: figuras e tabelas atuais

Pasta: [caracterizacao_sistemas](../../reports/tcc/caracterizacao_sistemas/).

| Subseção | Figuras | Tabelas |
|---|---|---|
| 3.2.1 Base australiana | 3.2-01: cobertura diária e mensal de Active_Power | resumo_fontes.csv; dicionario_cobertura.csv, filtrado por fonte |
| 3.2.2 Base brasileira | 3.2-02: cobertura da potência total; 3.2-03: canais da estação | auditoria_csv_brasil.csv; dicionario_cobertura.csv; brasil_potencia_estacao_5min.csv |
| 3.2.3 Descritiva e disponibilidade | 3.2-04: distribuições de potência; 3.2-05: disponibilidade individual | estatisticas.csv; *_cobertura_diaria.csv; *_cobertura_mensal.csv |
| 3.2.4 Ausências e inconsistências | 3.2-06: lacunas de potência; 3.2-07: perfil horário da potência | lacunas_potencia.csv; flags.csv; auditoria_csv_brasil.csv |

Os valores brasileiros são preservados como informados no CSV manual. O gerador `data.ipynb` usa a grade completa de cinco minutos como base e associa cada fonte independentemente. Potência existente é preservada mesmo sem meteorologia. A soma com `min_count=1` admite contribuição parcial; `n_inversores_potencia` identifica a quantidade de parcelas. Indicadores separados distinguem a presença de estação e inversores. Cada canal da estação possui cobertura independente dos inversores e das demais variáveis. Os canais totalmente vazios permanecem no dicionário. Valores negativos finitos são preservados e sinalizados; a disponibilidade não comprova qualidade física.

As duas potências são apresentadas em kW. Não se aplica normalização por capacidade nesta etapa. Unidades meteorológicas pendentes permanecem identificadas, especialmente a escala do GHI brasileiro e os canais GRI. A meteorologia é descritiva e não entra no cenário univariado.

A Austrália é caracterizada de 25/07/2013 a 23/08/2025; o modelo diário utiliza somente o recorte até 2023. O Brasil utiliza o calendário de 2025. A disponibilidade de potência de cinco minutos não equivale à aprovação dos alvos diários pelos contadores.

## 3.3 : onde usar cada figura e tabela

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

CSV principal de cinco minutos: [brasil_merge_5_minutos.csv](../../data/interim/brasil/brasil_merge_5_minutos.csv), gerado pelo 03_01 com potências AC/DC, contadores de energia somados e os canais da estação. Esse CSV alternativo não é a fonte brasileira do 03_02, que utiliza exclusivamente o arquivo manual Leopoldo_base_consolidada_5min.csv.
