# Diagnóstico dos 44 erros diários

Erro = previsto − referência. Positivo indica superestimação; energia diária tem erro 24 vezes o erro em potência média.
Analisados 44 dias e 10 métodos (440 resíduos), sem alterar previsões, hiperparâmetros ou decisões.
Modelos em foco: persistência, Chronos escolhido pela validação, MLP Brasil e LSTM Brasil (semente 42).

## Distribuição e concentração

| Modelo | MAE kW | RMSE kW | Viés kW | P90 absoluto kW | Top 5: % do erro quadrático |
|---|---:|---:|---:|---:|---:|
| Persistência | 42.96 | 50.30 | 1.14 | 80.25 | 39.4 |
| Chronos com covariáveis | 38.61 | 46.81 | 5.86 | 75.62 | 44.1 |
| MLP Brasil | 41.82 | 53.62 | 25.57 | 93.95 | 53.4 |
| LSTM Brasil | 41.41 | 51.89 | 26.16 | 91.88 | 48.4 |

Se todos os erros tivessem a mesma magnitude, cinco dos 44 dias responderiam por 11,36% da soma de erros quadráticos. A curva de concentração é descritiva, sem teste de uniformidade ou normalidade.

## Dias com maiores desvios

| Modelo | Dia | Variação real kW | Erro kW | Regime |
|---|---|---:|---:|---|
| Persistência | 03/11/2025 | -111.39 | 111.39 | queda_brusca |
| Persistência | 04/11/2025 | 98.70 | -98.70 | subida_brusca |
| Persistência | 05/11/2025 | 91.46 | -91.46 | subida_brusca |
| Persistência | 01/11/2025 | 81.66 | -81.66 | subida_brusca |
| Persistência | 14/11/2025 | 81.54 | -81.54 | subida_brusca |
| Chronos com covariáveis | 05/11/2025 | 91.46 | -108.19 | subida_brusca |
| Chronos com covariáveis | 03/11/2025 | -111.39 | 108.15 | queda_brusca |
| Chronos com covariáveis | 16/11/2025 | -75.01 | 84.32 | queda_brusca |
| Chronos com covariáveis | 14/11/2025 | 81.54 | -78.62 | subida_brusca |
| Chronos com covariáveis | 28/12/2025 | -77.25 | 76.07 | queda_brusca |
| MLP Brasil | 03/11/2025 | -111.39 | 149.18 | queda_brusca |
| MLP Brasil | 22/11/2025 | 40.09 | 112.66 | variacao_moderada |
| MLP Brasil | 05/11/2025 | 91.46 | -112.29 | subida_brusca |
| MLP Brasil | 05/12/2025 | -33.85 | 104.42 | variacao_moderada |
| MLP Brasil | 08/12/2025 | -75.13 | 95.32 | queda_brusca |
| LSTM Brasil | 03/11/2025 | -111.39 | 128.57 | queda_brusca |
| LSTM Brasil | 05/12/2025 | -33.85 | 109.19 | variacao_moderada |
| LSTM Brasil | 22/11/2025 | 40.09 | 105.69 | variacao_moderada |
| LSTM Brasil | 04/12/2025 | -57.43 | 94.47 | queda_brusca |
| LSTM Brasil | 08/12/2025 | -75.13 | 93.70 | queda_brusca |

## Quedas e subidas bruscas

Limiar principal = Q75 das mudanças absolutas de 184 pares consecutivos válidos no treino: 54.75 kW. Sensibilidade Q90: 88.76 kW. Não escolhemos limiares pelos erros de teste.

| Modelo | Regime | Dias | % dos dias | MAE kW | % do erro quadrático | Razão concentração |
|---|---|---:|---:|---:|---:|---:|
| Persistência | queda_brusca | 6 | 13.6 | 75.77 | 32.7 | 2.39 |
| Persistência | variacao_moderada | 32 | 72.7 | 29.45 | 30.2 | 0.42 |
| Persistência | subida_brusca | 6 | 13.6 | 82.22 | 37.1 | 2.72 |
| Chronos com covariáveis | queda_brusca | 6 | 13.6 | 70.00 | 33.9 | 2.48 |
| Chronos com covariáveis | variacao_moderada | 32 | 72.7 | 26.26 | 30.9 | 0.42 |
| Chronos com covariáveis | subida_brusca | 6 | 13.6 | 73.09 | 35.2 | 2.58 |
| MLP Brasil | queda_brusca | 6 | 13.6 | 81.40 | 38.9 | 2.86 |
| MLP Brasil | variacao_moderada | 32 | 72.7 | 33.53 | 45.8 | 0.63 |
| MLP Brasil | subida_brusca | 6 | 13.6 | 46.49 | 15.3 | 1.12 |
| LSTM Brasil | queda_brusca | 6 | 13.6 | 73.81 | 35.0 | 2.57 |
| LSTM Brasil | variacao_moderada | 32 | 72.7 | 35.31 | 51.4 | 0.71 |
| LSTM Brasil | subida_brusca | 6 | 13.6 | 41.57 | 13.5 | 0.99 |

Razão acima de 1 indica mais erro quadrático do que a fração de dias daquele regime. Os resíduos e a variação real compartilham o alvo: a associação é em parte mecânica, especialmente para persistência (erro = −variação). Não demonstra causa nem ausência de informação por si só.

## Novembro e dezembro

| Modelo | Mês | N | MAE kW | RMSE kW | Viés kW |
|---|---|---:|---:|---:|---:|
| Persistência | 2025-11 | 22 | 49.47 | 57.98 | -1.40 |
| Persistência | 2025-12 | 22 | 36.45 | 41.21 | 3.69 |
| Chronos com covariáveis | 2025-11 | 22 | 43.62 | 53.09 | 2.96 |
| Chronos com covariáveis | 2025-12 | 22 | 33.60 | 39.55 | 8.76 |
| MLP Brasil | 2025-11 | 22 | 44.13 | 58.39 | 13.92 |
| MLP Brasil | 2025-12 | 22 | 39.52 | 48.38 | 37.22 |
| LSTM Brasil | 2025-11 | 22 | 38.99 | 51.36 | 11.88 |
| LSTM Brasil | 2025-12 | 22 | 43.83 | 52.41 | 40.44 |

São 44 alvos selecionados entre 61 dias do bimestre. A comparação mensal descreve esses alvos, não o desempenho nos dias reprovados nem sazonalidade geral. Veja também mudanças de geração, GHI e composição de regimes em contexto_mensal.csv.

## Qualidade dos alvos e informações ausentes

Todos os 44 dias têm oito inversores aprovados. O maior desvio entre a referência pela soma dos contadores diários e a soma das diferenças acumuladas é 0.1292 kW (3.10 kWh/dia).
A análise de sensibilidade mantém todas as previsões, inclusive a persistência original, e troca apenas a referência. Esses contadores são dos mesmos equipamentos: a concordância não exclui erro de calibração ou outro erro comum.
A fração de leituras usa 8×288 registros inversor-horário possíveis, não horários com a planta completa. Telemetria esparsa de potência não implica perda do total diário registrado pelo contador.
GHI, umidade e temperatura do próprio dia alvo aparecem somente neste diagnóstico retrospectivo. Os modelos receberam meteorologia passada e calendário; não receberam a meteorologia futura observada. Correlações de postos são descritivas, com 44 dias, possíveis fatores comuns e seleção por qualidade; não estabelecem causalidade.

## Leitura conjunta

- **Persistência:** maior desvio em 03/11: +111.39 kW; os cinco maiores dias somam 39.4% do erro quadrático. RMSE novembro/dezembro: 57.98/41.21 kW.
  Quedas bruscas: 6 dias (13.6%) respondem por 32.7% do erro quadrático; viés geral +1.14 kW.
- **Chronos com covariáveis:** maior desvio em 05/11: -108.19 kW; os cinco maiores dias somam 44.1% do erro quadrático. RMSE novembro/dezembro: 53.09/39.55 kW.
  Quedas bruscas: 6 dias (13.6%) respondem por 33.9% do erro quadrático; viés geral +5.86 kW.
- **MLP Brasil:** maior desvio em 03/11: +149.18 kW; os cinco maiores dias somam 53.4% do erro quadrático. RMSE novembro/dezembro: 58.39/48.38 kW.
  Quedas bruscas: 6 dias (13.6%) respondem por 38.9% do erro quadrático; viés geral +25.57 kW.
- **LSTM Brasil:** maior desvio em 03/11: +128.57 kW; os cinco maiores dias somam 48.4% do erro quadrático. RMSE novembro/dezembro: 51.36/52.41 kW.
  Quedas bruscas: 6 dias (13.6%) respondem por 35.0% do erro quadrático; viés geral +26.16 kW.

No Chronos escolhido em outubro, os 12 dias de mudanças bruscas (27.3% dos dias) concentram 69.1% do erro quadrático. Há concentração tanto nas quedas quanto nas subidas: a dificuldade não se restringe às quedas.
MLP Brasil também superestima fora das grandes mudanças: viés +27.67 kW nos 32 dias moderados. O viés passa de +13.92 kW em novembro para +37.22 kW em dezembro. Isso sugere uma limitação adicional de generalização, sem identificar seu mecanismo.
LSTM Brasil também superestima fora das grandes mudanças: viés +28.11 kW nos 32 dias moderados. O viés passa de +11.88 kW em novembro para +40.44 kW em dezembro. Isso sugere uma limitação adicional de generalização, sem identificar seu mecanismo.
Nos alvos avaliados, a geração média passa de 227.27 kW para 212.23 kW; o GHI médio passa de 258.72 para 228.25 W/m². Essa mudança de composição deve ser considerada ao comparar os meses.
A magnitude do erro tem associação pequena com a magnitude da mudança do GHI, mas a direção contém outro sinal: no Chronos, a correlação de postos entre erro assinado e mudança assinada de GHI é -0.58. Isso é compatível com superestimar em reduções da radiação e subestimar em aumentos. É evidência descritiva, não prova da causa dominante nem estimativa do ganho de acrescentar previsões meteorológicas.
Previsões meteorológicas operacionais poderiam testar essa hipótese em outro período; a reanálise observada no alvo não deve ser fornecida retroativamente como se fosse uma previsão disponível.
Não podemos atribuir os desvios a uma única causa com este teste pequeno.
A concordância interna dos contadores torna improvável que a diferença entre esses dois totais explique erros de dezenas de kW; não substitui uma referência independente. Investigar eventos operacionais ou qualidade comum dos medidores exige registros externos.

Este diagnóstico não autoriza excluir os piores dias do benchmark nem reajustar o modelo pelo teste. Uma alteração motivada por estes resultados exige uma nova avaliação temporal independente.
