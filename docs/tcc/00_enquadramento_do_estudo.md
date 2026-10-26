# Enquadramento do TCC e roteiro de redação

Documento de trabalho atualizado em 25/10/2026. Descreve o estágio atual; as propostas de novos experimentos abaixo ainda não foram executadas.

## 1. Pergunta de pesquisa e objetivo

**Pergunta:** em que condições o aproveitamento de conhecimento previamente aprendido reduz o erro de previsão diária da geração fotovoltaica quando há poucas janelas de treinamento válidas na usina de destino?

**Objetivo geral proposto:** avaliar a transferência de aprendizagem e o ajuste fino na previsão da geração fotovoltaica de uma usina brasileira com histórico diário limitado, utilizando dados de uma usina australiana e um modelo de séries temporais previamente treinado, com comparação a modelos locais e à persistência.

Fine-tuning é uma estratégia de adaptação dentro de transferência de aprendizagem. A hipótese é de benefício possível, não de ganho garantido. Diferenças entre usinas, sensores, clima e definições dos alvos podem produzir transferência negativa.

Uma formulação possível do título é: **“Transferência de aprendizagem e ajuste fino para previsão diária da geração fotovoltaica com histórico local limitado: estudo entre uma usina brasileira e uma australiana”.**

## 2. Referências que sustentam a hipótese

**Sarmas et al. (2022)** é a referência principal para escassez: compara LSTM local com inicialização e congelamento de camadas a partir de outra usina. Nos casos estudados, estratégias de transferência superaram a abordagem local, com vantagem maior nos recortes menores de treinamento. O artigo considera diferentes quantidades de dados de destino e mantém o teste na comparação desses recortes. É motivação para a hipótese do TCC, não demonstração de que ela se verificará nas nossas bases. [Artigo e DOI](https://doi.org/10.1038/s41598-022-18516-x).

**Bak et al. (2025)** aproxima-se da transferência entre regiões: utiliza dados-fonte majoritariamente do DKASC e avalia adaptação a outros países, comparando treinamento local, transferência sem ajuste, ajuste de saída e ajuste fino. A implementação dos autores ajuda a organizar os controles necessários. [Artigo e DOI](https://doi.org/10.1109/ACCESS.2025.3591040), [implementação dos autores](https://github.com/gist-ailab/transfer-learning-PV-forecasting).

**Ansari et al. (2025)** fundamenta a escolha do Chronos-2 como modelo previamente treinado com suporte a covariáveis. Não substitui uma referência específica sobre escassez em sistemas fotovoltaicos. [Artigo](https://arxiv.org/abs/2510.15821).

As referências em formato BibTeX estão em [referencias.bib](referencias.bib).

## 3. O que foi feito e o que cada comparação permite investigar

Há três protocolos distintos no projeto. Este roteiro prioriza o **experimento diário atual, com referência brasileira pelos contadores**, em `teste_cronos_diario.ipynb`.

| Protocolo | Referência e resolução | Situação no TCC |
|---|---|---|
| Diário anterior | Média brasileira tratada por cobertura; 297 dias, 151/19/23 janelas | Histórico metodológico; não misturar suas métricas ao benchmark atual |
| Cinco minutos | Potência instantânea medida, horizonte de cinco minutos | Experimento separado, caso seja mantido no escopo |
| Diário atual | Energia brasileira validada pelos contadores / 24; 284 dias, 160/26/44 janelas | Base da primeira versão da metodologia e do benchmark diário |

No protocolo diário atual:

| Contraste | Interpretação correta |
|---|---|
| Chronos sem ajuste × Chronos ajustado no Brasil | Efeito exploratório do fine-tuning local de um mesmo modelo previamente treinado |
| Chronos ajustado no Brasil × Chronos ajustado conjuntamente em Austrália e Brasil | Contribuição exploratória de acrescentar a fonte australiana no ajuste conjunto |
| Chronos ajustado somente na Austrália e aplicado ao Brasil | Transferência entre usinas sem usar rótulos brasileiros no ajuste dos pesos ou na escolha do checkpoint desse cenário |
| Chronos × MLP/LSTM treinadas do zero no Brasil | Benchmark entre métodos; muda também arquitetura, objetivo de treino e conhecimento prévio |
| MLP/LSTM brasileiras com e sem inicialização australiana, usando a nova base | Controle direto de transferência para essas arquiteturas; ainda não executado na base reconstruída pelos contadores |

O Chronos já chega pré-treinado. Nós não o treinamos do zero na Austrália. Cada cenário adapta separadamente a mesma base por LoRA. **O portfólio é ajuste conjunto em Austrália + Brasil; não é a sequência “pré-treinar na Austrália e depois fazer fine-tuning no Brasil”.** Os testes antigos de transferência MLP/LSTM usam outra referência brasileira e não podem preencher essa lacuna do protocolo atual.

## 4. Como definir “dados escassos” neste estudo

Na base brasileira, há muitos registros intradiários, mas apenas **160 janelas diárias elegíveis de treinamento**, contra **3392 janelas disponíveis na fonte australiana**. São janelas sobrepostas e não 160 observações estatisticamente independentes. Há também apenas 26 alvos de validação e 44 de teste.

A escassez relevante é a quantidade de históricos completos e rótulos diários aprovados, somada à cobertura temporal limitada da usina de destino. Não foi confirmado que a usina brasileira seja recém-instalada. Ausência de registros, pequeno tamanho de amostra e ausência de informação meteorológica futura são limitações diferentes.

No portfólio atual, o balanceamento utiliza **160 janelas australianas e 160 brasileiras**, e não todas as 3392 australianas. O cenário ajustado somente na Austrália utiliza as 3392. Essa diferença precisa acompanhar a descrição de “abundância de dados-fonte”.

## 5. O que os resultados atuais sustentam

No teste de 44 dias, o Chronos sem covariáveis e sem ajuste teve RMSE de 56,510 kW; após ajuste somente no Brasil, 46,899 kW. Com covariáveis, os valores foram 59,684 e 46,909 kW. São evidências exploratórias favoráveis ao fine-tuning local neste recorte.

O portfólio com covariáveis teve RMSE de 46,811 kW, muito próximo dos 46,909 kW do ajuste somente no Brasil. A diferença de aproximadamente 0,10 kW, obtida com uma semente, não sustenta uma conclusão forte de benefício adicional da fonte australiana. Sem covariáveis, o portfólio foi pior que o ajuste brasileiro. As redes locais são benchmarks úteis, mas a diferença para o Chronos não isola transferência entre países.

A LSTM local foi a escolha pela validação conjunta; seu RMSE de teste foi 51,885 kW. Não devemos trocar a seleção retrospectivamente porque outro método teve menor erro no teste. Os resultados já foram inspecionados, e o diagnóstico dos resíduos não constitui nova validação independente.

Fonte: [benchmark atual](../../experimentos/chronos_diario_contadores/resultados/benchmark_final.csv) e [decisão pela validação](../../experimentos/chronos_diario_contadores/resultados/benchmark_decisao_validacao.json).

## 6. Organização sugerida dos capítulos

1. **Introdução:** previsão fotovoltaica, limitação de históricos locais, pergunta, objetivos e contribuições.
2. **Fundamentação e trabalhos relacionados:** previsão temporal, persistência, MLP/LSTM, transferência, fine-tuning, modelos previamente treinados e LoRA. Separar resultados da literatura das nossas hipóteses.
3. **Bases e preparação dos dados:** procedência, unidades, fusos, qualidade, reconstrução de energia, meteorologia, faltantes, normalização e janelas. Primeira redação em [01_bases_e_preprocessamento.md](01_bases_e_preprocessamento.md).
4. **Protocolo experimental:** métodos, parâmetros, partições temporais, sementes, critérios de seleção, métricas e cenários de disponibilidade de dados.
5. **Resultados e discussão:** benchmark, curvas de disponibilidade, transferência negativa, resíduos, meses e limitações.
6. **Conclusão:** resposta proporcional às evidências, limitações e trabalhos futuros.

## 7. Experimentos que ainda seriam necessários para uma conclusão sobre escassez

Uma curva de aprendizagem com diferentes quantidades de janelas brasileiras, definidas antes de consultar resultados, ajudaria a investigar a hipótese. Os métodos devem receber os mesmos recortes, calendário, covariáveis e referência; a composição sazonal de cada recorte precisa ser registrada. Sarmas et al. oferece um exemplo desse desenho.

Para isolar transferência nas MLP/LSTM, comparar a mesma arquitetura inicializada aleatoriamente e inicializada na fonte australiana, com regras iguais de normalização, validação e orçamento. Para o Chronos, comparar ajuste local e conjunto com múltiplas sementes e explicitar o balanceamento da fonte.

Antes de consolidar novas execuções, é necessário decidir como tratar a cobertura intradiária dos alvos australianos e confirmar ficha técnica, unidades e convenção temporal. O teste atual já foi examinado: análises adicionais sobre ele continuam exploratórias; uma confirmação exigirá outro período ou outra avaliação temporal independente.

Esta etapa documenta e audita o que já foi feito. Não altera modelos, bases ou resultados para buscar uma conclusão favorável.
