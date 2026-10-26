# Chronos-2 diário — Brasil

Este diretório preserva o experimento com a definição anterior de potência diária. O notebook existente [teste_cronos_diario.ipynb](../../teste_cronos_diario.ipynb) foi atualizado para a [base reconstruída por contadores](../chronos_diario_contadores/README.md). Os resultados abaixo continuam disponíveis para consulta; uma cópia do conteúdo anterior do notebook foi guardada em `resultados/notebook_antes_contadores.json`. O notebook de cinco minutos é preservado.

Previsão da **potência AC média do dia seguinte, em kW**, usando três dias anteriores consecutivos. A base é `data/processed/brasil/base_diaria_leopoldo_dias_validos.csv`: 297 dias aprovados em 2025. O arquivo `base_diaria_leopoldo_consecutiva.csv` contém apenas o maior bloco, com 43 dias, e não é a base completa usada aqui.

As lacunas de dias inteiros continuam ausentes. Mantemos as mesmas datas do estudo diário arquivado: 151 origens de treino até setembro, 19 de validação em outubro e 23 de teste em novembro–dezembro. A auditoria também mostra as contagens para históricos de 1, 3, 7 e 14 dias. O histórico de três dias é fixado antes da comparação e não escolhido pelo teste.

## Entradas e qualidade

O cenário univariado recebe somente potência passada. Os cenários com covariáveis recebem potência, temperatura, umidade, radiação horizontal e seno/cosseno anual do passado. Para o dia futuro, fornecemos **somente o calendário**, calculado pela data; meteorologia futura é NaN. Vento e grandezas contemporâneas ao alvo ficam fora das entradas.

Temperatura, umidade e radiação brasileiras usam a base histórica tratada, que inclui ERA5. O estudo é retrospectivo: não se presume que a reanálise estivesse disponível operacionalmente naquela data, nem que seja uma previsão meteorológica.

A referência diária é a média tratada de intervalos com critérios de cobertura, com pequenas lacunas intradiárias estimadas. Não é energia diária em kWh e não é integralmente medida. Exportamos cobertura original e fração estimada dos alvos, além de uma avaliação complementar restrita a cobertura diurna originalmente medida de pelo menos 95%. Não imputamos dias inteiros para criar janelas.

## Métodos

Aplicamos os cinco cenários do [artigo solicitado](https://towardsdatascience.com/five-ways-to-fine-tune-chronos-2-the-time-series-foundation-model/) e do [notebook de Shuai Guo](https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb): Brasil; Austrália+Brasil; Brasil com covariáveis; Austrália+Brasil com covariáveis; Austrália com covariáveis aplicada ao Brasil sem usar rótulos brasileiros no ajuste/checkpoint.

O portfólio tem 151 origens de cada usina. O piloto usa rank 8, alpha 16, taxa 2e-5, lote de oito origens, até 200 passos, verificação a cada 25 e paciência de quatro verificações, com semente 42. Esse orçamento é menor que o intradiário porque há apenas 151 origens brasileiras de treino. Os pesos originais ficam congelados e seus hashes são verificados.

Checkpoints individuais brasileiros usam as 19 origens de outubro; portfólio usa 19 de cada usina; transferência sem Brasil usa 38 australianas distribuídas em 2023. Depois, o RMSE em todas as 19 origens brasileiras de outubro escolhe o cenário; a transferência que exclui o Brasil fica fora dessa seleção. O teste é avaliado posteriormente, sem mudar a estratégia escolhida.

As referências MLP/LSTM usam os mesmos 23 alvos e suas métricas são médias de cinco sementes; o Chronos usa uma semente. Chronos prevê a mediana e ajusta perda de quantis; as redes anteriores usam MSE. O teste já foi consultado no estudo diário anterior e a validação tem poucos dias: resultados exploratórios, sem confirmação independente ou inferência estatística de superioridade.

## Execução

Com o ambiente e o modelo em cache já utilizados no experimento de cinco minutos:

```powershell
.venv\Scripts\python.exe experimentos/chronos_diario/executar.py todas
```

Etapas disponíveis: `preparar`, `treinar`, `avaliar`, `todas`. Adaptadores concluídos são reutilizados após conferir assinatura e hash. `config.json` define o piloto; `modelos/` contém adaptadores e históricos; `resultados/` contém auditoria, métricas, previsões, decisão de validação, figuras e relatório.

Notebook e CLI compartilham um bloqueio por experimento para impedir ajustes simultâneos sobre os mesmos arquivos. Ao executar em paralelo em processos novos, a segunda execução aguarda a primeira e depois reutiliza os resultados verificados.

A implementação está em [chronos_diario.py](../../src/energia_transfer/chronos_diario.py), compartilhando as rotinas de LoRA com [chronos_experimentos.py](../../src/energia_transfer/chronos_experimentos.py). As dependências do ambiente estão fixadas em [requirements.txt do experimento Chronos](../chronos_5min/requirements.txt).
