# Chronos diário com energia reconstruída pelos contadores

O notebook existente [teste_cronos_diario.ipynb](../../teste_cronos_diario.ipynb) agora executa este experimento. A definição e os resultados anteriores permanecem em [chronos_diario](../chronos_diario/README.md).

## Base e reconstrução

Aplicamos a regra do código enviado ao CSV disponível, `data/raw/brasil/Leopoldo-fixa-inv.csv`. O arquivo `Leopoldo-fixa-inv(1).csv` mencionado no trecho não foi localizado. O manifesto registra o caminho usado e seu SHA-256.

Filtramos somente `07-07FX`, convertemos UTC para `America/Sao_Paulo`, agrupamos leituras por inversor e horário de cinco minutos pela mediana e descartamos valores negativos. Existem oito equipamentos distintos, `inverter121` a `inverter128`.

Por inversor e dia, `e1` é o máximo do contador diário depois das 6h; `e2` é a diferença entre as medianas do contador total depois das 19h e antes das 4h. Aceitamos `0 ≤ e1 ≤ 1600 kWh`, `e2 ≥ 0` e `abs(e1-e2) ≤ max(8 kWh, 0.03*e1)`. Somente dias com os oito inversores aprovados recebem `energia_kwh`. `Active_Power = energia_kwh / 24` representa potência média de 24 horas, em kW.

São **284 dias aprovados e 81 reprovados**, mantidos na grade de 365 dias. Nenhum dia ou contador é imputado. São recuperados 33 dias que não passavam na regra antiga e reprovados 46 dias que passavam nela. O código da reconstrução foi conferido numericamente contra a execução independente do trecho enviado.

O arquivo [leopoldo_diario_contadores_auditado.csv](../../data/processed/brasil/leopoldo_diario_contadores_auditado.csv) contém a base completa, qualidade, meteorologia pública e calendário. `energia_bruta_kwh` é diagnóstico e pode ser parcial; o alvo aprovado é `energia_kwh`. Os arquivos por inversor ficam em `resultados/`.

## Repetição do experimento

Usamos os três dias anteriores consecutivos para prever o próximo dia. As lacunas não são comprimidas nem cruzadas pelas janelas. A coorte é comum aos cenários com e sem covariáveis.

| Partição brasileira | Período | Dias válidos | Janelas |
|---|---|---:|---:|
| Treino | Janeiro–setembro de 2025 | 202 | 160 |
| Validação | Outubro de 2025 | 29 | 26 |
| Teste | Novembro–dezembro de 2025 | 53 | 44 |

O primeiro alvo de treino é 02/02/2025, pois janeiro não contém os quatro dias consecutivos aprovados necessários. Temperatura, umidade e radiação horizontal vêm do ERA5 diário já armazenado. Usamos meteorologia somente dos dias anteriores. Para o alvo futuro, somente seno/cosseno do dia do ano são fornecidos. Sem vento. Não há janelas excluídas adicionalmente por falta de meteorologia passada nesta reconstrução.

A Austrália mantém o conjunto diário anterior: 3392 origens de treino até 2022 e 352 de validação em 2023. Potência é normalizada por capacidade AC (24 kW na Austrália e 1000 kW no Brasil). A origem australiana não foi reconstruída por contadores.

Repetimos os cinco cenários do [artigo solicitado](https://towardsdatascience.com/five-ways-to-fine-tune-chronos-2-the-time-series-foundation-model/) e da [implementação do autor](https://github.com/ShuaiGuo16/chronos-2-forecasting/blob/main/02_chronos2_fine_tuning_building_demand.ipynb): individual, portfólio, individual com covariáveis, portfólio com covariáveis e transferência sem Brasil. Também avaliamos persistência e dois cenários sem ajuste.

Mantemos rank 8, alpha 16, taxa 2e-5, lote de oito origens, até 200 passos, avaliação a cada 25 passos, paciência de quatro verificações e semente 42. O portfólio equilibra 160 origens de cada usina. Checkpoints individuais brasileiros usam 26 datas de outubro; portfólio usa 19 datas de cada usina; transferência sem Brasil usa 38 datas australianas. Conferimos hashes dos pesos congelados e dos adaptadores.

A escolha brasileira usa o menor RMSE da validação, incluindo persistência e excluindo a transferência sem Brasil. A decisão é gravada antes de calcular as métricas de teste. MAE/RMSE em kW se referem à potência média de 24 h; multiplicados por 24 resultam em kWh/dia.

Não juntamos métricas antigas de MLP/LSTM ao novo ranking, porque suas referências e datas são diferentes. Os resultados entre bases não isolam o efeito da reconstrução. O teste já foi consultado em estudos anteriores, há poucos dias e uma única semente nos adaptadores: análise exploratória. A concordância entre contadores não comprova calibração nem exclui erro comum; ERA5 é reanálise retrospectiva, sem simulação de latência operacional.

## Execução e arquivos

```powershell
.venv\Scripts\python.exe experimentos/chronos_diario_contadores/executar.py todas
```

Etapas: `preparar`, `treinar`, `avaliar`, `todas`. Notebook e CLI compartilham bloqueio por experimento. Adaptadores concluídos e previsões em cache são reutilizados somente após conferir assinaturas e hashes. A primeira célula recarrega as funções para permitir a execução em um kernel que já utilizou a versão anterior.

`config.json` define os parâmetros; `dados/` contém as entradas brasileiras por partição; `modelos/` contém adaptadores, curvas e auditorias; `resultados/` contém partições, qualidade por inversor, manifesto, comparação entre bases, métricas, decisão, previsões, figuras e relatório. A implementação está em [chronos_diario_contadores.py](../../src/energia_transfer/chronos_diario_contadores.py), com as rotinas LoRA compartilhadas dos experimentos anteriores.

## Benchmark final com MLP e LSTM locais

As seções 7 e 8 do mesmo notebook acrescentam redes treinadas do zero somente no Brasil, sem pré-treinamento australiano e sem correção residual de persistência. Usam os mesmos três dias consecutivos, seis variáveis históricas e seno/cosseno conhecidos da data alvo dos cenários Chronos com covariáveis. Nenhuma meteorologia futura observada é fornecida.

A MLP tem camadas de 32 e 16 unidades com ReLU. A LSTM tem uma camada com 16 unidades, estado iniciado em zero a cada janela e calendário futuro concatenado antes da saída. As duas produzem um valor direto. A normalização X/y usa somente as 160 janelas brasileiras de treino; o calendário futuro permanece em [-1,1]. AdamW usa taxa 0.001, weight decay 0.0001, lote 16, até 200 épocas, paciência de 30 e checkpoint pelo MSE nas 26 datas de validação.

`benchmark_config.json` fixa esses parâmetros e as sementes 42, 7, 21, 84 e 123. A tabela principal compara uma execução por modelo, usando a semente 42 previamente fixada. Média e desvio de métricas das cinco sementes são mostrados separadamente; não são métricas de um ensemble nem intervalos de confiança. Os orçamentos e perdas do treinamento local diferem do LoRA; a comparação é feita nos mesmos alvos brasileiros.

A seleção conjunta pelo RMSE de outubro escolheu a LSTM local (49.050 kW na validação). No teste, seu RMSE foi 51.885 kW, contra 53.623 kW da MLP, 50.301 kW da persistência e 46.811 kW do Chronos de portfólio com covariáveis. A escolha de validação foi preservada, mesmo com essa inversão no teste. Os valores entre sementes e todos os métodos constam nos resultados.

Para executar somente essa etapa, após os resultados Chronos estarem disponíveis:

```powershell
.venv\Scripts\python.exe experimentos/chronos_diario_contadores/executar_benchmark.py
```

Essa CLI abre somente as partições brasileiras auditadas, verifica datas e referências e compartilha o bloqueio do experimento. Checkpoints ficam em `modelos/benchmark_brasil/`. A tabela principal é `resultados/benchmark_final.csv`, as previsões são `resultados/benchmark_previsoes_teste.csv`, a variação entre sementes fica em `resultados/benchmark_robustez_seeds.csv` e o relatório em `resultados/benchmark_relatorio.md`. Os arquivos Chronos existentes continuam separados. Implementação: [benchmark_diario_brasil.py](../../src/energia_transfer/benchmark_diario_brasil.py).

## Diagnóstico dos 44 erros individuais

As seções 9 a 13 do mesmo notebook analisam os resíduos congelados, sem retreino nem mudança dos alvos ou das decisões. A análise cobre dez modelos (440 resíduos) e destaca persistência, Chronos escolhido em outubro, MLP e LSTM locais. Inclui os 44 dias, os maiores desvios, distribuições, concentração da soma dos erros quadráticos (SSE), meses, regimes de mudança e indicadores de qualidade.

Erro positivo significa superestimação. O limite de mudança brusca é 54.753 kW, percentil 75 da variação absoluta de 184 pares consecutivos válidos do treino brasileiro. O percentil 90 (88.763 kW) é mostrado como sensibilidade. Esses limites não são ajustados pelos erros do teste. O erro e a variação real compartilham o alvo; suas correlações, especialmente a identidade da persistência, não demonstram causalidade.

No Chronos, 12 dias de mudanças bruscas (27.3% dos alvos) concentram 69.1% do SSE, distribuído entre quedas e subidas. Os cinco maiores desvios concentram 44.1%. As redes locais também apresentam viés positivo nos 32 dias moderados (MLP: +27.675 kW; LSTM: +28.113 kW). O viés da LSTM aumenta de +11.883 kW em novembro para +40.436 kW em dezembro. O recorte mensal contém 22 alvos por mês, sem representar os dias reprovados.

Todos os alvos têm oito contadores aprovados. A maior diferença entre as duas reconstruções dos totais é 0.1292 kW. A sensibilidade troca somente a referência, mantendo as previsões originais. A concordância é interna aos mesmos equipamentos e não exclui erro comum de calibração. A cobertura disponível é a fração das 2304 leituras inversor-horário possíveis, não a cobertura simultânea da planta. Meteorologia do dia alvo aparece apenas para explicação retrospectiva, não como entrada futura dos modelos.

```powershell
.venv\Scripts\python.exe experimentos/chronos_diario_contadores/diagnosticar_erros.py
```

Os CSVs, quatro figuras, relatório e manifesto ficam em `resultados/diagnostico_erros/`; a implementação está em [diagnostico_erros_diarios.py](../../src/energia_transfer/diagnostico_erros_diarios.py). Os hashes das entradas são conferidos antes e depois da análise. Os piores dias permanecem no benchmark. Uma mudança do modelo motivada pelo diagnóstico exigirá nova avaliação temporal independente.
