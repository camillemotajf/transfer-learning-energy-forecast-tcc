# Legendas das figuras: caracterização dos dados originais

PNG em 300 dpi e PDF vetorial. Numeração provisória.

## fig_3_2_01_cobertura_australia

Cobertura temporal dos dados originais de potência da base australiana

Cobertura diária e mensal da variável Active_Power entre 25/07/2013 e 23/08/2025. A cobertura corresponde à proporção de intervalos de cinco minutos com ao menos um valor numérico finito de potência, considerando 288 intervalos esperados por dia, inclusive nas datas inicial e final. Intervalos sem registro ou sem potência numérica finita são considerados indisponíveis; zeros são observações disponíveis. As demais variáveis não participam deste indicador. As regiões em branco representam meses externos ao período de observação.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_02_cobertura_inversores

Cobertura temporal dos dados originais dos inversores brasileiros

Disponibilidade de potência dos oito inversores da usina 07-07FX no calendário local de 2025. O painel superior apresenta a cobertura por equipamento; o inferior compara a cobertura sobre 2304 combinações de equipamento e intervalo por dia, a presença simultânea dos oito inversores em 288 intervalos diários e a presença de registros nos horários exatos da grade. A contagem por intervalos [t, t + 5 min) admite diferenças de segundos entre registros, sem modificar seus horários ou valores.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_03_calendario_brasil

Calendário de cobertura dos dados originais brasileiros

Cobertura diária de potência dos inversores e temperatura da estação meteorológica em 2025, anterior ao tratamento. Os denominadores são 2304 combinações de equipamento e intervalo para os inversores e 288 intervalos para a estação. A cobertura considera a presença de valores numéricos finitos. Zero indica ausência de valores disponíveis; células em branco correspondem a datas inexistentes no mês.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_04_disponibilidade_variaveis

Disponibilidade das variáveis nos intervalos de aquisição esperados

Distribuição dos intervalos esperados entre ausência de registro, registro sem valor numérico finito e presença de ao menos um valor numérico finito. As classes são mutuamente exclusivas e calculadas por equipamento em intervalos de cinco minutos. Registros repetidos não aumentam a cobertura. Valores finitos fora dos limites de triagem permanecem classificados como disponíveis; disponibilidade não implica validade física.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_05_distribuicoes_originais

Distribuições das variáveis nos dados originais

Histogramas de densidade dos valores numéricos finitos, preservando registros duplicados, zeros, valores negativos e observações sinalizadas na triagem. A potência australiana representa o sistema em kW; a brasileira representa cada inversor em W. O GHI da estação brasileira é apresentado na escala original, sem correção de unidade ou calibração. Os períodos de observação diferem entre as fontes.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_06_campos_vazios

Campos vazios nas linhas presentes dos arquivos originais

Número e proporção de campos vazios nas linhas existentes de cada fonte, incluindo registros duplicados. O denominador corresponde às linhas selecionadas do arquivo, sem contabilizar intervalos sem registro. A umidade relativa não integra o esquema da estação brasileira e não é incluída nesta contagem.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_07_duplicatas_suspeitos

Duplicatas e sinais de inconsistência nos dados originais

À esquerda, número de registros excedentes para a mesma combinação de horário e equipamento. À direita, observações sinalizadas pelos critérios de triagem: temperatura fora de −20 a 60 °C, umidade relativa fora de 0 a 100% e valores negativos nas demais variáveis selecionadas. A sinalização identifica observações para inspeção e não determina sua exclusão ou comprova erro de medição.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_08_lacunas_originais

Distribuição da duração das lacunas nos dados originais

O painel superior apresenta sequências de intervalos de cinco minutos sem valor numérico finito de potência australiana, potência por inversor brasileiro ou temperatura da estação. A duração corresponde ao número de intervalos consecutivos multiplicado por cinco minutos. O painel inferior apresenta sequências de dias sem qualquer registro da fonte. As lacunas dos inversores são contadas separadamente por equipamento; ambos os painéis incluem as bordas do calendário.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

## fig_3_2_09_disponibilidade_horaria

Perfil horário da disponibilidade original

Proporção de intervalos de cinco minutos com valor numérico finito por hora do dia, considerando potência australiana, potência dos inversores brasileiros e temperatura da estação. Valores nulos de potência são contabilizados como observados. Os horários seguem a convenção do arquivo australiano e o fuso America/Sao_Paulo para os registros brasileiros. O perfil descreve a disponibilidade sem atribuir causas às interrupções.

Fonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.

