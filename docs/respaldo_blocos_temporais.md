# Uso de blocos temporais interrompidos no transfer learning

Consulta e contagens verificadas em 24/10/2026.

## Resposta para esta base

**É metodologicamente possível aproveitar os 39 blocos, somando 297 dias aprovados, em modelos treinados por janelas.** Cada exemplo precisa conter histórico e alvo nas datas corretas, sem atravessar um período excluído. O modelo pode compartilhar parâmetros entre os exemplos dos diferentes blocos. A avaliação precisa preservar a ordem cronológica e a disponibilidade real das informações.

Uma sequência contínua de 297 dias não foi recuperada: há 39 segmentos. O maior tem 43 dias, de 01/02 a 15/03/2025. O arquivo [base_diaria_leopoldo_dias_validos.csv](../data/processed/brasil/base_diaria_leopoldo_dias_validos.csv) conserva as datas reais; [blocos_consecutivos_leopoldo.csv](../reports/base_final/blocos_consecutivos_leopoldo.csv) define os limites dos segmentos.

## O que as referências sustentam

### Modelos compartilhados entre sequências

[Montero-Manso e Hyndman (2021), *Principles and algorithms for forecasting groups of time series: Locality and globality*](https://doi.org/10.1016/j.ijforecast.2021.03.004), International Journal of Forecasting, 37(4), 1632–1653. [Manuscrito dos autores](https://arxiv.org/abs/2008.00444).

O trabalho estuda modelos globais, que aprendem uma função de previsão compartilhada entre séries, em comparação com modelos locais. Dá fundamento ao compartilhamento de parâmetros entre sequências. **Tratar os segmentos válidos da mesma usina como unidades de extração de janelas é nossa aplicação metodológica desse princípio.** O artigo não é um estudo específico das lacunas da usina Leopoldo nem uma prova de que sua exclusão seja estatisticamente neutra.

### Exemplos de treino extraídos por janelas

[Salinas, Flunkert, Gasthaus e Januschowski (2020), *DeepAR: Probabilistic forecasting with autoregressive recurrent networks*](https://doi.org/10.1016/j.ijforecast.2019.07.001), International Journal of Forecasting, 36(3), 1181–1191, seção 4.2. [Manuscrito](https://arxiv.org/abs/1704.04110).

O artigo descreve exemplos formados por janelas com diferentes pontos iniciais dentro das séries e exige dados de referência no intervalo de previsão selecionado. Sustenta a aprendizagem a partir de múltiplas janelas, sem exigir que todos os exemplos pertençam a uma única sequência global. Aqui adotamos uma regra conservadora: tanto a entrada quanto o alvo devem caber integralmente no mesmo bloco diário aprovado. Isso não reproduz automaticamente todos os detalhes do DeepAR.

### Implementação reconhecida desse mecanismo

A [documentação oficial do Darts — Torch Forecasting Models](https://unit8co.github.io/darts/userguide/torch_forecasting_models.html) descreve treino por segmentos de comprimento fixo, com entrada e saída, e treino com uma lista de séries. O comprimento mínimo para extrair um exemplo é a soma dos comprimentos de entrada e saída. É uma referência de implementação, não evidência de precisão para nossa usina. Não foi instalado Darts nem treinado um modelo nesta etapa.

### Avaliação que respeita o tempo

[Hyndman e Athanasopoulos (2021), *Forecasting: Principles and Practice*, 3ª edição, seção 5.10](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation) descrevem avaliação com origem de previsão móvel: cada previsão é construída com informação anterior ao alvo. Aplicamos esse princípio usando cortes por data e mantendo blocos posteriores para validação e teste. A referência fundamenta a ordem temporal da avaliação; não dispensa o controle das lacunas na geração das janelas.

## Protocolo recomendado

1. **Preservar datas e identificador de bloco.** Uma linha de 15/03 não vira o dia anterior a 29/03 só porque ambas aparecem em linhas consecutivas de um CSV. Características de calendário usam as datas originais.
2. **Construir janelas dentro de cada bloco.** Para prever um dia usando três dias anteriores, exigir quatro datas diárias consecutivas aprovadas. Descartar blocos menores que quatro dias para esse experimento. Não colocar dias de outros blocos no histórico para completar a janela.
3. **Compartilhar os pesos do modelo entre as janelas.** Em uma rede recorrente com estado persistente, reiniciar o estado ao trocar de bloco; em treino por janelas independentes, não carregar estado entre exemplos. Não se está afirmando independência estatística entre os segmentos da mesma usina.
4. **Separar os alvos por datas.** O treino precede a validação, e a validação precede o teste. Um bloco que cruza uma data de corte não deve ser atribuído inteiro a uma partição se isso colocar alvos futuros no treino. Separar pelo período dos alvos e verificar o horizonte de previsão.
5. **Permitir contexto passado legítimo.** A entrada da primeira previsão de teste pode usar observações anteriores ao corte, inclusive do período de treino, desde que já conhecidas na emissão e sem lacuna na janela. Isso não significa treinar com o alvo de teste. Se o bloco reinicia depois de uma lacuna, aguardar o histórico mínimo dentro dele.
6. **Ajustar transformações no treino.** Normalização, seleção de atributos, hiperparâmetros e ajustes aprendidos de imputação não podem usar o teste. A reconstrução retrospectiva atual deve ser auditada ao montar as partições: nenhuma característica pode depender de dados posteriores à emissão da previsão. Avaliar preferencialmente alvos medidos, mostrando a fração reconstruída.
7. **Definir o horizonte.** Para previsão diária de um dia à frente, usar apenas informações disponíveis na véspera. Meteorologia ERA5 do próprio dia-alvo caracteriza um cenário retrospectivo com clima conhecido, não uma previsão operacional de véspera.
8. **Aplicar a cronologia também à fonte australiana.** Se a simulação prevê março de 2025, o pré-treinamento não pode usar observações australianas de agosto de 2025 como se estivessem disponíveis em março. O arquivo australiano vai até 23/08/2025; truncar conforme a origem simulada, ou declarar outro desenho experimental.
9. **Usar exatamente os mesmos alvos de teste para todos os modelos.** Comparar persistência, treinamento local, transferência sem ajuste e transferência com ajuste. No teste com atualização a cada dia, usar o valor real do dia anterior somente depois que ele estiver disponível. Uma previsão de vários dias emitida de uma vez não pode utilizar esse valor futuro.

Embaralhar a ordem dos exemplos já pertencentes ao treino pode fazer parte da otimização de uma rede sem estado persistente. **Sortear quais janelas entram em treino e teste é outra operação** e não corresponde ao protocolo cronológico recomendado aqui.

## Quantas janelas realmente existem

Para histórico de `L` dias e saída de `H` dias consecutivos, um bloco com `n_b` dias fornece, com passo de um dia:

```text
janelas_b = max(0, n_b - L - H + 1)
janelas_totais = soma(janelas_b nos 39 blocos)
```

Para `H = 1`, calculado diretamente da lista atual de blocos:

| Histórico | Janelas nos 297 dias | Janelas no maior bloco de 43 dias |
| --- | ---: | ---: |
| 1 dia | 258 | 42 |
| 3 dias | 193 | 40 |
| 7 dias | 119 | 36 |
| 14 dias | 59 | 29 |

Essas janelas podem se sobrepor e não são observações estatisticamente independentes. São quantidades antes da divisão temporal; aumentar o comprimento do histórico reduz o aproveitamento dos segmentos curtos.

### Exemplo de separação por datas

Um desenho candidato seria treino com alvos até 30/09/2025, validação em outubro e teste em novembro–dezembro. Com entrada de três dias e saída de um dia, há:

| Partição | Dias aprovados no período | Janelas com alvo no período |
| --- | ---: | ---: |
| Treino — janeiro a setembro | 225 | 151 |
| Validação — outubro | 27 | 19 |
| Teste — novembro e dezembro | 45 | 23 |
| Total | 297 | 193 |

A contagem admite contexto anterior à fronteira entre partições, quando as datas continuam dentro do mesmo bloco e o contexto já estaria disponível. É um **exemplo de planejamento**, não um teste de modelo já executado, nem um corte escolhido pela precisão. No regime de previsão a cada dia, as observações anteriores dentro do teste podem atualizar o contexto sem entrar em ajuste dos pesos. Com emissão única de múltiplos dias, é necessário outro cálculo de janelas e disponibilidade.

Os 23 alvos de teste desse exemplo ainda são poucos para conclusões amplas. Uma avaliação com várias origens temporais predefinidas pode ampliar a análise, mantendo o passado como treino em cada origem e sem contar previsões repetidas como evidência independente.

### Evitar compressão do calendário na validação

O [`TimeSeriesSplit` do scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) opera sobre a ordem das linhas e ressalta espaçamento igual para comparar a duração dos testes entre divisões. Aplicá-lo diretamente às 297 linhas removidas do calendário não verifica as datas nem os limites dos blocos. Neste projeto, recomendamos cortes explícitos por data e verificação das janelas, com contagens e duração de cada período relatadas.

## Limites da conclusão científica

- O respaldo é para **treino compartilhado por janelas e avaliação temporal**, não para juntar todos os segmentos como uma sequência contínua.
- Os artigos citados não garantem ganho de transferência Austrália–Brasil. A normalização física, a compatibilidade das variáveis e a comparação com modelos de referência continuam necessárias.
- Há viés possível de seleção: os dias reprovados podem coincidir com falhas operacionais ou condições difíceis. A precisão nos dias aprovados não representa automaticamente desempenho em todos os dias do ano, em falhas ou no começo de um bloco sem histórico.
- O subconjunto de teste deve mostrar cobertura original e fração imputada. Uma referência completamente sintetizada não deve ser apresentada como alvo medido.
- O procedimento conservador descrito serve a modelos por janelas compartilhadas. Outros modelos, inclusive modelos de espaço de estados capazes de lidar com observações ausentes no calendário completo, têm protocolos próprios.

## Texto metodológico adaptável para o TCC

> Após o controle de qualidade, a série foi particionada em segmentos diários contíguos. Os exemplos supervisionados foram extraídos exclusivamente de janelas cujo histórico e horizonte de previsão estavam integralmente contidos em um segmento, preservando as datas originais. Os parâmetros do modelo foram compartilhados entre exemplos dos segmentos de treinamento. A avaliação utilizou cortes cronológicos pelas datas dos alvos e somente informação disponível na origem da previsão. A estratégia foi fundamentada na literatura de modelos globais e treinamento por janelas (Montero-Manso e Hyndman, 2021; Salinas et al., 2020) e nos princípios de avaliação temporal de Hyndman e Athanasopoulos (2021).

Esse parágrafo descreve o protocolo proposto. Deve ser atualizado para corresponder à implementação e ao horizonte que forem efetivamente usados no experimento.
