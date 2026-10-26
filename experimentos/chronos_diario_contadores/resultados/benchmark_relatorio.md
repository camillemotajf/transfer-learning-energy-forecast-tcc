# Benchmark final diário — Brasil

MLP e LSTM treinadas do zero somente no Brasil; sem transferência e sem correção residual de persistência.
Mesmos 160 históricos de treino, 26 de validação e 44 de teste; três dias consecutivos para prever o dia seguinte.
Todas as redes recebem seis variáveis passadas e seno/cosseno conhecidos da data alvo. Sem vento e sem meteorologia futura observada.
Padronização de X/y ajustada somente no treino brasileiro. MLP 32/16 ReLU; LSTM de uma camada com 16 unidades e estado reiniciado a cada janela. Saída direta.
AdamW, taxa 0.001, weight decay 0.0001, lote 16, até 200 épocas, paciência 30. Checkpoint por MSE da validação de outubro.
Tabela principal: semente 42 previamente fixada, uma execução por modelo. Cinco sementes das redes locais são mostradas separadamente; seus desvios medem variação de inicialização, não intervalo de confiança nem significância estatística.
Os orçamentos e as perdas de treinamento diferem: redes locais usam MSE; Chronos usa LoRA e perda de quantis. Comparação dos erros na mesma referência brasileira.
O teste já foi consultado em estudos anteriores: resultado exploratório, sem confirmação independente.

Escolha pela validação conjunta: **lstm_brasil**.

| Modelo | N | MAE kW | RMSE kW | Skill RMSE % |
|---|---:|---:|---:|---:|
| persistencia | 44 | 42.961 | 50.301 | 0.000 |
| zero_shot_univariado | 44 | 46.585 | 56.510 | -12.345 |
| zero_shot_covariaveis | 44 | 50.104 | 59.684 | -18.655 |
| individual | 44 | 38.775 | 46.899 | 6.763 |
| portfolio | 44 | 39.191 | 47.601 | 5.367 |
| individual_covariaveis | 44 | 38.479 | 46.909 | 6.743 |
| portfolio_covariaveis | 44 | 38.610 | 46.811 | 6.938 |
| transferencia_sem_brasil | 44 | 40.537 | 48.721 | 3.141 |
| mlp_brasil | 44 | 41.824 | 53.623 | -6.605 |
| lstm_brasil | 44 | 41.410 | 51.885 | -3.150 |

## Variação entre cinco sementes (teste)

| Rede | Sementes | MAE médio kW | RMSE médio kW | Desvio RMSE kW |
|---|---:|---:|---:|---:|
| lstm_brasil | 5 | 40.607 | 51.288 | 1.914 |
| mlp_brasil | 5 | 41.250 | 52.572 | 2.291 |
