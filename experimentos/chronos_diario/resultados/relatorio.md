# Chronos-2 diário — Brasil

Horizonte de um dia; histórico de três dias consecutivos.
297 dias aprovados; 151 janelas de treino, 19 de validação e 23 de teste. Uma semente nos adaptadores; cinco nas referências MLP/LSTM.
A referência é potência AC média diária tratada em kW, com lacunas intradiárias estimadas; não é energia diária nem medição integral.
Dados meteorológicos ERA5 apenas passados; calendário futuro conhecido. Sem vento e sem meteorologia futura observada.
Comparação exploratória: teste previamente consultado e validação brasileira pequena.

Escolha pela validação: **portfolio_covariaveis**.

| Modelo | MAE kW | RMSE kW | WAPE % |
|---|---:|---:|---:|
| persistencia | 46.756 | 54.834 | 19.732 |
| zero_shot_univariado | 47.045 | 58.782 | 19.853 |
| zero_shot_covariaveis | 51.066 | 62.945 | 21.551 |
| individual | 43.627 | 52.238 | 18.411 |
| portfolio | 43.811 | 52.401 | 18.489 |
| individual_covariaveis | 43.785 | 52.296 | 18.478 |
| portfolio_covariaveis | 42.897 | 51.487 | 18.103 |
| transferencia_sem_brasil | 44.519 | 53.285 | 18.788 |
| lstm_direta_completo | 39.935 | 47.655 | 16.853 |
| lstm_direta_local | 37.178 | 47.001 | 15.690 |
| mlp_direta_completo | 37.968 | 45.552 | 16.023 |
| mlp_direta_local | 36.344 | 47.288 | 15.338 |

Sensibilidade: 5 alvos com cobertura diurna originalmente medida de pelo menos 95%.

https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb
