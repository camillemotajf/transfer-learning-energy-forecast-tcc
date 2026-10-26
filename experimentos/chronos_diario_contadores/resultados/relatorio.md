# Chronos-2 diário com contadores — Brasil

Alvo: soma da energia diária validada dos oito inversores (kWh), dividida por 24 h para obter potência média em kW.
284 dias aprovados; 81 dias reprovados permanecem ausentes. Sem imputação diária.
Histórico de três dias consecutivos; previsão de um dia. Partições cronológicas: treino até setembro, validação em outubro, teste em novembro–dezembro.
Covariáveis: temperatura, umidade, GHI e calendário dos dias passados; futuro: somente calendário. Sem vento. ERA5 é reanálise histórica, com disponibilidade operacional não modelada.
Austrália preservada do estudo diário anterior, normalizada por 24 kW AC; Brasil por 1000 kW AC. A origem não foi reconstruída por contadores.
Os contadores validam totais diários apesar das lacunas de telemetria. Concordância entre contadores não prova calibração dos medidores nem exclui erro comum.
Mantidos os cinco cenários e o orçamento do piloto anterior: até 200 passos LoRA, rank 8, semente 42. Transferência sem Brasil usa somente dados australianos para ajuste/checkpoint.
O teste já foi consultado em estudos anteriores. Comparação exploratória, com apenas uma semente e poucos dias de validação.
As métricas MLP/LSTM e Chronos do alvo anterior não entram neste ranking: referência e datas mudaram.

| Partição | Dias válidos | Janelas de 3 dias |
|---|---:|---:|
| treino | 202 | 160 |
| validacao | 29 | 26 |
| teste | 53 | 44 |

Escolha pela validação: **portfolio_covariaveis**.

| Modelo | N teste | MAE kW | RMSE kW | MAE kWh/dia | RMSE kWh/dia | WAPE % |
|---|---:|---:|---:|---:|---:|---:|
| persistencia | 44 | 42.961 | 50.301 | 1031.061 | 1207.213 | 19.550 |
| zero_shot_univariado | 44 | 46.585 | 56.510 | 1118.029 | 1356.249 | 21.199 |
| zero_shot_covariaveis | 44 | 50.104 | 59.684 | 1202.484 | 1432.423 | 22.800 |
| individual | 44 | 38.775 | 46.899 | 930.593 | 1125.565 | 17.645 |
| portfolio | 44 | 39.191 | 47.601 | 940.577 | 1142.419 | 17.834 |
| individual_covariaveis | 44 | 38.479 | 46.909 | 923.491 | 1125.815 | 17.510 |
| portfolio_covariaveis | 44 | 38.610 | 46.811 | 926.633 | 1123.454 | 17.570 |
| transferencia_sem_brasil | 44 | 40.537 | 48.721 | 972.880 | 1169.294 | 18.447 |

Fonte e implementação de referência: https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb

CSV bruto efetivamente usado: `data/raw/brasil/Leopoldo-fixa-inv.csv`. Seu hash consta no manifesto.
