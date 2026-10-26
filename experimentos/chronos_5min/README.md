# Chronos-2: cinco cenários de adaptação com LoRA

O notebook existente [teste_cronos.ipynb](../../teste_cronos.ipynb) contém a aplicação, as saídas e os gráficos. Não foi criado outro notebook. A implementação compartilhada está em [chronos_experimentos.py](../../src/energia_transfer/chronos_experimentos.py).

Base metodológica: [artigo solicitado](https://towardsdatascience.com/five-ways-to-fine-tune-chronos-2-the-time-series-foundation-model/), [implementação original de Shuai Guo](https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb) e [API oficial de fine-tuning](https://github.com/amazon-science/chronos-forecasting/blob/main/src/chronos/chronos2/pipeline.py). O artigo trabalha com consumo sintético de oito edifícios, em resolução horária, para prever uma semana. Aqui adaptamos os cinco cenários às duas usinas reais disponíveis, com resolução e horizonte de cinco minutos.

| Cenário | Dados que ajustam o adaptador | Covariáveis |
|---|---|---|
| `individual` | Brasil | Nenhuma |
| `portfolio` | Austrália e Brasil | Nenhuma |
| `individual_calendario` | Brasil | Calendário |
| `portfolio_calendario` | Austrália e Brasil | Calendário |
| `transferencia_sem_brasil` | Apenas Austrália | Calendário |

O cenário de transferência não ajusta pesos nem escolhe checkpoints com rótulos brasileiros. Recebe os últimos 60 minutos brasileiros na inferência e fica fora da escolha de estratégia na validação brasileira. O portfólio é uma adaptação entre duas usinas, sem equivaler à frota de oito ativos simulados do artigo.

## Dados e avaliação

- Horizonte: um passo, cinco minutos; contexto: 12 passos, 60 minutos.
- Brasil: treino até setembro de 2025; validação em outubro; teste em novembro e dezembro, com as mesmas 7.668 origens diurnas dos experimentos anteriores.
- Austrália: treino até 2022; validação em 2023. Mantemos o orçamento de janelas fonte já estabelecido no experimento anterior.
- Alvos e último valor da persistência são originalmente medidos. As potências são normalizadas pelas capacidades AC de 24 kW e 1.000 kW.
- Cada tarefa de treinamento contém exatamente 13 passos: 12 do histórico tratado e um alvo medido. `min_past=12` impede a API de usar um valor imputado do histórico como alvo. Janelas não atravessam lacunas da grade real.
- No portfólio, os dois domínios fornecem o mesmo número de origens de treino, escolhidas uniformemente no calendário disponível.
- Calendário é a única covariável conhecida no futuro. Não são fornecidas observações futuras de geração ou meteorologia. `cross_learning=False` na inferência impede compartilhar dados entre origens de previsão diferentes.

## Ajuste e seleção

Os cinco adaptadores começam no mesmo `amazon/chronos-2`, revisão fixada no arquivo de configuração. Usamos LoRA rank 8, alpha 16, Q/K/V/O e projeção de saída, taxa de aprendizado 2e-5 e até 1.000 passos. O lote tem 16 origens; com calendário ele corresponde a 80 variáveis na API. Checkpoints são avaliados a cada 50 passos, com paciência de seis verificações. O artigo usa verificações a cada 25 passos; espaçamos para 50 e reduzimos o lote para a GPU disponível.

Cada checkpoint é escolhido pela perda de quantis da API, em 512 origens de validação distribuídas no tempo: 512 brasileiras no ajuste individual, 256 de cada usina no portfólio, ou 512 australianas na transferência sem Brasil. Uma origem corresponde a uma tarefa de validação, evitando o erro de validar apenas a última previsão de uma série longa.

Depois de treinar, comparamos as estratégias em todas as 4.043 origens brasileiras de outubro e gravamos a escolha por RMSE **antes** de avaliar os adaptadores no teste. As métricas de MAE, RMSE e WAPE são salvas para todos os cenários, com comparação pareada ao zero-shot de mesmas covariáveis. Também mostramos persistência e as LSTMs anteriores.

A previsão pontual do Chronos é a mediana (quantil 0,5), como na API `predict_df`. Seu ajuste minimiza perda de quantis; as LSTMs anteriores foram treinadas com MSE. Essa diferença de objetivo deve acompanhar a interpretação de eventuais trocas entre MAE e RMSE.

**Interpretação:** esta etapa usa uma semente (42), enquanto as LSTMs foram repetidas em cinco sementes. O teste de novembro–dezembro já havia sido consultado antes desta nova hipótese: a comparação é exploratória e precisa de confirmação em período ainda não consultado. Não se afirma ganho antecipadamente, nem se comparam numericamente as métricas de previsão diária com as de cinco minutos.

## Executar e retomar

No ambiente do projeto, com os pesos já presentes no cache:

```powershell
.venv\Scripts\python.exe experimentos/chronos_5min/executar.py todas
```

As etapas `preparar`, `treinar` e `avaliar` também podem ser executadas separadamente. A configuração está em [config.json](config.json); as versões adicionais estão em [requirements.txt](requirements.txt). Modelos concluídos são reutilizados se a assinatura das bases, configurações, versões e hash do adaptador coincidirem. Uma configuração diferente exige outra pasta de execução.

Os adaptadores e históricos ficam em `modelos/`; métricas, previsões, decisão de validação, manifesto, progresso e figuras em `resultados/`. A auditoria verifica que somente parâmetros LoRA são treináveis e que os parâmetros congelados conservam o mesmo hash antes e depois do ajuste.
