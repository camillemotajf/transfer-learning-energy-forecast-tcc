# Material para as seções 3.2 e 3.3 do TCC

O [03_02](../../notebooks/tcc/03_02_caracterizacao_dados_crus.ipynb) utiliza a potência por sistema e os canais meteorológicos. No Brasil, a fonte é `Leopoldo_base_consolidada_5min.csv`, fornecida pelo pesquisador. A potência é `total_active_power_w` dividida por 1000, e as demais variáveis são os canais físicos da estação existentes no mesmo CSV. Na Austrália, utiliza-se Active_Power e os canais meteorológicos do arquivo. Contadores de energia e outras grandezas elétricas não entram nessa caracterização.

O 03_02 apenas lê o CSV manual, sem executar ou modificar `data.ipynb`. Não refaz o merge nem substitui a fonte pelo CSV alternativo gerado pelo [03_01](../../notebooks/tcc/03_01_brasil_merge_horarios.ipynb). A [auditoria original anterior](../../reports/tcc/caracterizacao_dados_crus/) permanece separada. O 03_03 agora contém o novo tratamento horário, com código diretamente nas células. Os relatórios e experimentos diários anteriores permanecem separados como históricos.

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

A Austrália é caracterizada de 25/07/2013 a 23/08/2025; os experimentos diários anteriores utilizaram somente o recorte até 2023; o novo tratamento horário do 03_03 consulta o arquivo integral. O Brasil utiliza o calendário de 2025. A disponibilidade de potência de cinco minutos não equivale à aprovação dos alvos diários pelos contadores.

## 3.3: tratamento horário baseado em Bak et al. (2025)

Notebook: [03_03_tratamento_e_preprocessamento.ipynb](../../notebooks/tcc/03_03_tratamento_e_preprocessamento.ipynb). Todas as etapas e figuras estão implementadas nas suas células; não há módulo externo de pré-processamento nem execução de código remoto.

Pasta: [preprocessamento_horario_bak2025](../../reports/tcc/preprocessamento_horario_bak2025/). As figuras possuem o prefixo `fig_3_3_h`.

| Subseção | Figuras | Tabelas principais |
|---|---|---|
| 3.3.1 Tratamento australiano | H01: cobertura original por hora; H02: anomalias | `cobertura_5min_por_hora.csv`, `regras_anomalias.csv` |
| 3.3.2 Tratamento brasileiro | H03: dias aprovados/reprovados; H06: potência e contribuição dos inversores | `dias_auditados.csv`, `brasil_contagens_5min.csv` |
| 3.3.3 Potência média horária e diária derivada | H06: séries de todos os blocos | `intervalos_escolhidos.csv`; bases horárias e diárias auxiliares exportadas |
| 3.3.4 Valores ausentes | H04: seleção; H05: interpolação; H07: maiores blocos | `faltantes_por_etapa.csv`, `australia_blocos.csv`, `brasil_blocos.csv` |
| 3.3.5 Normalização e padronização | H08: potência p.u. e z-score | `escalas_treino.csv`, `particoes_propostas.csv` |

A média horária utiliza as leituras presentes, como no código dos autores; não exige doze amostras de cinco minutos. Depois da triagem de anomalias, dias com duas horas NaN consecutivas em qualquer variável exigida são reprovados. Interpolam-se somente faltas isoladas de uma hora, internas, preservando o calendário e as máscaras de imputação. Essas salvaguardas e as diferenças entre o artigo e o código dos autores estão explicitadas no notebook e no manifesto.

A configuração final utiliza **todos os blocos elegíveis**. No Brasil, são **6.310 horas, 261 dias completos e 30 blocos** de potência; o maior continua com 792 horas (33 dias), de 18/08/2025 a 19/09/2025. Na Austrália, exigem-se as cinco variáveis da imagem: **AP, GHI, temperatura do ar, RH e velocidade do vento**. São **26.710 horas, 1.111 dias completos e 28 blocos**; a maior sequência tem 258 dias. A cobertura dos cinco canais restringe a base australiana a períodos entre 2013 e 2016, principalmente pela disponibilidade do vento. Isso não significa que a potência australiana termine em 2016.

As bases principais são `data/processed/brasil/brasil_horario_bak2025_todos_blocos.csv.gz` e `data/processed/australia/australia_horario_bak2025_todos_blocos.csv.gz`. As datas originais e `bloco_id` são preservados. Os arquivos `*_bloco.csv.gz` contêm o maior bloco somente para diagnóstico; os arquivos `*_calendario.csv.gz` conservam a grade com lacunas. A base diária auxiliar contém todos os dias de 24 horas aprovados, não apenas os do maior intervalo.

O CSV `australia_horario_bak2025_auditoria_canais.csv.gz` preserva onze canais australianos, exceto direção do vento, com contagens e valores após QC. Canais auxiliares não restringem o cenário principal. Energia acumulada e chuva acumulada usam a última leitura horária, sem interpretação como potência ou energia incremental. A unidade de `Wind_Speed` conserva o valor original e ainda requer confirmação antes de comparar magnitudes com o vento externo em m/s dos autores.

A fonte brasileira é exclusivamente `Leopoldo_base_consolidada_5min.csv`. Nenhuma estação restringe os blocos brasileiros; preservam-se as flags de contribuição parcial dos inversores. A Austrália aplica a triagem elétrica e meteorológica disponível, incluindo vento negativo e AP × GHI; o Brasil aplica somente QC elétrico. Máscaras, bloco, partição, contagens e versões normalizadas são metadados ou representações alternativas, não medições independentes.

A auditoria de janelas demonstra 24 horas de histórico e alvo uma hora à frente, sem atravessar blocos ou partições e sem acessar interpolações antes da disponibilidade. Esses números são exemplos, não hiperparâmetros validados. As partições seguem a ordem cronológica de todas as horas elegíveis, e os z-scores usam somente treino. A média horária só está disponível ao terminar a hora; a borda direita da interpolação também respeita esse término.

A entrada física comum para transferência direta é AP. O modelo australiano com cinco entradas tem contrato diferente do brasileiro univariado; sua arquitetura de adaptação ainda precisa ser definida no experimento, antes de transferir pesos. As novas tabelas `resumo_todos_blocos.csv`, `decisao_final_todos_blocos.csv`, `contrato_entradas_por_dominio.csv` e `resumo_janelas_blocos.csv` identificam a configuração vigente.

As capacidades adotadas de 24 kW e 1000 kW continuam pendentes de confirmação técnica definitiva. O máximo do período serve à triagem retrospectiva; o z-score usa somente o treino proposto. As novas partições 70/15/15 são preparatórias: nenhum modelo foi retreinado. Os antigos 284 dias e 44 alvos de teste pertencem ao protocolo anterior e não descrevem estas novas bases.

## Estudo complementar da estação brasileira — sem vento

A seção final do [03_03](../../notebooks/tcc/03_03_tratamento_e_preprocessamento.ipynb) verifica AP, temperatura do ar, GHI e RH, com vento excluído das entradas brasileiras; na Austrália, o vento está incluído conforme a imagem. O [resumo](../../reports/tcc/preprocessamento_horario_bak2025/estudo_estacao_sem_vento/resumo.md) e seis tabelas estão em `preprocessamento_horario_bak2025/estudo_estacao_sem_vento/`.

- `estacao_h01_cobertura_e_blocos`: cobertura mensal e efeito das entradas exigidas sobre o maior bloco.
- `estacao_h02_diagnostico_ghi`: diferenças observadas da escala do GHI entre meses, sem correção automática.

AP + temperatura fornece 106 dias civis completos, distribuídos em blocos; o maior tem 29 dias (19/10/2025 a 16/11/2025). GHI não reduz esse intervalo sob os filtros individuais, mas continua condicionado à confirmação de sua escala. RH não existe no consolidado brasileiro. A maior lacuna da estação tem 5.017 horas e não é recuperada pela interpolação curta proposta. O estudo fundamenta a decisão final de usar apenas AP no Brasil; seus cenários com estação são diagnósticos e não entradas escolhidas. Ele não comprova equivalência física ou ganho preditivo.

## Exportação e numeração

Todas as figuras têm PNG em 300 dpi e PDF vetorial. Cada pasta inclui
`legendas_figuras.md`, `indice_figuras.json` e `manifesto.json` com hashes das fontes.
A numeração é provisória; a ordem de aparição no TCC determina a numeração definitiva.
As legendas descrevem denominadores e ressalvas para evitar interpretar disponibilidade
como validação física ou somar motivos de reprovação sobrepostos.

CSV principal de cinco minutos: [brasil_merge_5_minutos.csv](../../data/interim/brasil/brasil_merge_5_minutos.csv), gerado pelo 03_01 com potências AC/DC, contadores de energia somados e os canais da estação. Esse CSV alternativo não é a fonte brasileira do 03_02, que utiliza exclusivamente o arquivo manual Leopoldo_base_consolidada_5min.csv.
