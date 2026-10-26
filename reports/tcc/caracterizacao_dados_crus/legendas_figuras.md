# Legendas das figuras — dados crus

PNG em 300 dpi e PDF vetorial. Numeração a ajustar ao TCC.

## fig_3_2_01_australia_crua

Disponibilidade do arquivo australiano integral

Contagem de intervalos de cinco minutos com registros, sem filtro de valores ou imputação. Os timestamps australianos estão alinhados à grade exata. O período integral do arquivo é usado; não há corte em 2023. Dias civis completos são a referência, inclusive nas bordas parciais do arquivo. Branco: mês fora do intervalo.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_02_inversores_crus

Disponibilidade dos registros crus dos inversores

Código 07-07FX e datas locais de 2025. As curvas coloridas contam existência em intervalos [t,t+5min): 2304 posições inversor–intervalo por dia, ou 288 intervalos com os oito inversores presentes. A linha cinza exige timestamp exato e mostra o efeito do desalinhamento temporal; não implica ausência real de coleta. Presença no mesmo intervalo não exige o mesmo segundo. Nenhum valor ou timestamp cru é corrigido, somado ou imputado.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_03_calendario_brasil_cru

Calendário da disponibilidade original brasileira

Ausências e coberturas parciais antes de qualquer reconstrução diária ou imputação. Zero significa nenhuma posição com valor finito da variável; branco indica dia inexistente no mês. A referência de calendário inclui dias sem aquisição e a borda final parcial do arquivo.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_04_ausencias_cruas

Ausência de registros e ausência de valores dentro dos registros

Classes mutuamente exclusivas em intervalos [t,t+5min) por equipamento. Várias linhas no mesmo intervalo não multiplicam a cobertura: basta uma com valor finito. Valores finitos suspeitos, negativos ou fora das faixas de triagem continuam na classe verde; presença não equivale a validade. A classificação é uma contagem, sem consolidar valores ou modificar timestamps crus. As tabelas também mostram vazios nas linhas do CSV e timestamps exatos, com outras definições.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_05_distribuicoes_cruas

Distribuições dos valores originais registrados

Todas as linhas com valores numéricos finitos entram, inclusive duplicatas e valores suspeitos. Não há normalização por capacidade, conversão da escala de GHI brasileira, remoção de negativos ou preenchimento. Potência brasileira é por inversor em W; australiana é a variável do sistema em kW. Infinitos e textos não numéricos ficam fora do histograma e são contados nas tabelas.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_06_campos_vazios

Campos vazios nas linhas presentes dos arquivos originais

Denominador: linhas existentes na seleção de cada CSV, preservadas as duplicatas. Linhas inteiras que não foram registradas não entram aqui. Por isso, poucos NaN no arquivo podem coexistir com grandes lacunas temporais. Não há umidade no esquema da estação brasileira; essa variável não é adicionada artificialmente à contagem.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_07_duplicatas_suspeitos

Duplicatas e sinais de inconsistência nos dados crus

Duplicata significa mesma chave temporal e equipamento, não necessariamente linhas idênticas. Critérios de triagem: temperatura fora de −20 a 60 °C; umidade fora de 0 a 100%; negativos nos demais campos selecionados. Não se afirma que todo valor sinalizado seja erro de sensor e nenhum valor é removido. Divergência entre duplicatas é auditada nas tabelas, incluindo diferenças entre ausência e presença de valor.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_08_lacunas_cruas

Duração das lacunas antes do tratamento

No painel superior: intervalos [t,t+5min) sem valor finito de potência australiana, potência por inversor brasileiro e temperatura da estação. Cada inversor tem sua própria sequência; as contagens de oito sequências não são diretamente comparáveis às de uma estação. Duração = número de intervalos ausentes × cinco minutos. No inferior, conta-se ausência de todos os registros da fonte, inclusive fora dos minutos exatos. Bordas do calendário estão incluídas; não se interpreta lacuna como falha física comprovada.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_09_disponibilidade_horaria

Perfil horário da disponibilidade original

A grade considera as 24 horas. Zero de potência é um valor observado e não é marcado como faltante. Reduções noturnas de disponibilidade podem refletir política de aquisição; a figura não determina a causa. Austrália mantém a convenção temporal do arquivo sem fuso explícito; Brasil usa a apresentação local America/Sao_Paulo dos timestamps UTC.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

