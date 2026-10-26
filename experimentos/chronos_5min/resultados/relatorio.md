# Chronos-2: cinco cenários de LoRA em dados solares de cinco minutos

Adaptação do artigo de Shuai Guo e de seu notebook público; não é uma reprodução dos dados sintéticos do autor.
Contexto de 60 minutos; horizonte de 5 minutos; uma semente (42). LSTMs: média das métricas de cinco sementes.
O teste de novembro–dezembro já foi consultado antes desta hipótese: resultados exploratórios, sem confirmação independente.

Escolha pelo RMSE de outubro: **individual_calendario**. O cenário AU → Brasil não usou rótulos brasileiros para ajustar nem escolher checkpoints e ficou fora da seleção brasileira.

| Modelo | MAE kW | RMSE kW | WAPE % |
|---|---:|---:|---:|
| persistencia | 91.201 | 182.621 | 21.294 |
| zero_shot_univariado | 90.138 | 171.547 | 21.046 |
| zero_shot_calendario | 93.021 | 175.652 | 21.719 |
| individual | 89.193 | 171.961 | 20.825 |
| portfolio | 89.777 | 174.585 | 20.961 |
| individual_calendario | 88.014 | 170.156 | 20.550 |
| portfolio_calendario | 88.116 | 171.200 | 20.574 |
| transferencia_sem_brasil | 88.814 | 172.921 | 20.737 |
| LSTM_local | 93.182 | 156.969 | 21.757 |
| LSTM_completo | 93.055 | 157.029 | 21.727 |

Fontes:

https://towardsdatascience.com/five-ways-to-fine-tune-chronos-2-the-time-series-foundation-model/

https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb

API oficial: https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py
