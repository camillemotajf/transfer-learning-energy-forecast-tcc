# Imputação das séries diárias de Leopoldo

A seção final do notebook agora usa meteorologia pública ERA5 nas lacunas.
Veja `meteorologia_publica.md` para a fonte e o método. Os resultados linear/KNN
abaixo descrevem a etapa anterior e foram mantidos para comparação.

Pesquisa consultada em 22/10/2026. As referências abaixo são artigos originais,
documentação oficial e repositórios dos próprios autores. Os métodos publicados
não garantem desempenho equivalente nesta usina: é necessário testar as lacunas
e a resolução temporal do conjunto local.

## Bibliografia e relação com o projeto

1. **MORITZ, Steffen; BARTZ-BEIELSTEIN, Thomas.** imputeTS: Time Series Missing Value
   Imputation in R. *The R Journal*, v. 9, n. 1, p. 207–218, 2017.
   [Artigo e DOI](https://doi.org/10.32614/RJ-2017-009).
   Discute métodos específicos de séries temporais, incluindo interpolação e
   modelos estruturais. Fundamenta usar dependências no tempo e inspecionar o
   padrão de ausência antes da imputação. O pacote é em R; não foi instalado aqui.

2. **CHO, Brian; DAYRIT, Teresa; GAO, Yuan; WANG, Zhe; HONG, Tianzhen; SIM, Alex;
   WU, Kesheng.** Effective Missing Value Imputation Methods for Building Monitoring
   Data. *2020 IEEE International Conference on Big Data*, 2020.
   [DOI](https://doi.org/10.1109/BigData50022.2020.9378230) e
   [texto depositado pelo LBNL](https://eta-publications.lbl.gov/sites/default/files/effective_missing_value_imputation_methods_for_building_monitoring_data_bcho_0.pdf).
   Compara interpolação, KNN e outros métodos em dados de sensores. O desempenho
   depende do tamanho do bloco ausente. Seus limites em número de amostras não
   devem ser convertidos diretamente em dias para Leopoldo.

3. **MANTUANO, Claudio; OMOYELE, Olalekan; HOFFMANN, Maximilian; WEINAND, Jann Michael;
   PANELLA, Massimo; STOLTEN, Detlef.** Data imputation methods for intermittent renewable energy sources:
   Implications for energy system modeling.** *Energy Conversion and Management*,
   v. 339, artigo 119857, 2025.
   [DOI](https://doi.org/10.1016/j.enconman.2025.119857) e
   [registro institucional](https://publications.rwth-aachen.de/record/1013121).
   Compara métodos em irradiância e vento, considerando pontos isolados e lacunas
   contínuas. Relata que precisão pontual não garante preservar a distribuição.
   Aqui serve de apoio à comparação linear/KNN, não de validação dos 208 dias.

4. **KOUBLI, Eleni; PALMER, Diane; ROWLEY, Paul; GOTTSCHALG, Ralph.** Inference of
   missing data in photovoltaic monitoring datasets. *IET Renewable Power
   Generation*, v. 10, p. 434–439, 2016.
   [DOI e publicação original](https://doi.org/10.1049/iet-rpg.2015.0355).
   Referência específica de monitoramento fotovoltaico e reconstrução com dados
   ambientais/modelagem elétrica. É uma alternativa para investigação quando
   houver fonte meteorológica externa adequada.

5. **LEE, Hyomun; KIM, Dongsu; CHO, Heejin; SONG, Gwanghyun; YOON, Jongho.**
   Evaluation of data imputation models for building-integrated photovoltaic
   systems with practical performance and reproducibility. *Solar Energy*,
   v. 308, artigo 114428, 2026.
   [DOI e publicação original](https://doi.org/10.1016/j.solener.2026.114428).
   Compara regressão linear, KNN e redes neurais em variáveis elétricas de sistemas
   fotovoltaicos. O resumo consultado destaca a influência do histórico disponível,
   da proporção de ausência e do ruído. Regressão linear não é o mesmo algoritmo
   que interpolação linear; não tratamos esses métodos como equivalentes.

6. **DU, Wenjie; COTE, David; LIU, Yan.** SAITS: Self-Attention-based Imputation
   for Time Series. *Expert Systems with Applications*, artigo 119619, 2023.
   [DOI](https://doi.org/10.1016/j.eswa.2023.119619) e
   [manuscrito dos autores](https://arxiv.org/abs/2202.08516).
   Alternativa de imputação multivariada com atenção. Foi identificada para
   trabalhos futuros; não foi treinada nem comparada no conjunto local.

## Implementações consultadas

| Método/recurso | Implementação original | Uso neste projeto |
|---|---|---|
| Interpolação temporal | [pandas.DataFrame.interpolate](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.interpolate.html) | `method="time"`, sem extrapolação nas extremidades; controle do tamanho do bloco inteiro |
| KNN | [KNNImputer — documentação](https://scikit-learn.org/stable/modules/generated/sklearn.impute.KNNImputer.html) e [código-fonte](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/impute/_knn.py) | Vizinhos ponderados pela distância; calendário como contexto conhecido |
| Métodos temporais em R | [SteffenMoritz/imputeTS](https://github.com/SteffenMoritz/imputeTS) | Referência conceitual e alternativa futura |
| SAITS | [WenjieDu/SAITS](https://github.com/WenjieDu/SAITS) | Implementação oficial identificada, sem execução local |
| BRITS | [caow13/BRITS](https://github.com/caow13/BRITS) e [artigo NeurIPS 2018](https://papers.neurips.cc/paper/7911-brits-bidirectional-recurrent-imputation-for-time-series) | Outra alternativa de pesquisa, sem execução local |
| Separação treino/teste | [scikit-learn: data leakage](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage) | Ajustar escalas, seleção e doadores somente no treino em uma avaliação preditiva |

## Protocolo implementado em Python

O código de cálculo está em `src/energia_transfer/imputacao.py`; as chamadas, tabelas e gráficos estão em `notebooks/exploratorio/01_imputacao_linear_knn.ipynb`. Essa experiência reproduz o procedimento histórico; a seleção atual está em `notebooks/05_brasil_base_final.ipynb`. As dependências estão em `requirements.txt`, na raiz do projeto.

1. Reindexar em um calendário diário completo, de 03/01 a 31/12/2025: **363 dias**.
2. Separar as nove variáveis que têm medições das três completamente ausentes.
3. Simular blocos de 1, 7 e 30 dias em posições com valores observados, com até
   quatro repetições por coluna/tamanho e semente 42. O valor ocultado não entra
   no ajuste do método. Os blocos podem se sobrepor entre repetições: não são
   ensaios independentes para intervalos de confiança.
4. Comparar interpolação e KNN com 3, 5 e 7 vizinhos. Registrar MAE, RMSE e
   RMSE normalizado pelo desvio padrão dos valores visíveis. Para série constante,
   usar escala não nula, indicada no código. A média dos ensaios dá o mesmo peso
   a cada tamanho de bloco na seleção.
5. Interpolar blocos internos de até dois dias. Se a interpolação superar o
   melhor KNN na validação, permitir seu uso até o maior bloco testado (30 dias).
   Usar o melhor KNN nos demais blocos e nas extremidades.
6. O KNN usa seno/cosseno do dia do ano e tempo contínuo, além da coluna a estimar.
   Padronização e doadores são ajustados somente nas medições visíveis da coluna.
   Como falta a estação inteira durante meses, a distância nesses dias se baseia
   apenas no calendário: o método não recupera as condições meteorológicas reais.
7. Preservar cada valor observado e registrar o método de cada estimativa.
   Não usar valores já estimados como novos doadores.

## Resultado e limites de interpretação

- As nove variáveis com doadores passaram de **43,25% para 0% de faltantes**.
  Essa redução mede completude, não acurácia física.
- Cada variável elétrica tinha 25 dias ausentes no calendário completo.
  Cada variável meteorológica tinha 223, correspondendo a **61,43% estimados**.
- O bloco meteorológico de **208 dias** é maior que os blocos validados e recebe
  sinalização explícita. Não temos verdade de referência para medir seu erro.
- As três variáveis sem medições permanecem vazias: considerando as 12 variáveis
  numéricas da referência australiana, o arquivo de 13 colunas ainda tem **25% de
  faltantes estruturais**. A versão comum as exclui; não foram reconstruídas.
- Janeiro tem códigos de usina divergentes no arquivo de inversores. O filtro de
  `07-07FX` foi preservado: não há evidência suficiente para reclassificar os
  registros de `07-07TK-2` como medições desta usina.
- A irradiância horizontal observada muda de escala/distribuição entre janeiro
  e o período de agosto a dezembro. Precisamos conferir sensor, unidade e
  cobertura horária. Um NRMSE global baixo pode esconder esse problema.
- A direção de vento observada é constante em 360 graus. Preencher suas lacunas
  não acrescenta variabilidade informativa.
- A interpolação/ponderação suaviza variações. Em particular, estimativas de chuva
  não recuperam datas reais dos eventos nem garantem preservar sua distribuição.
- As médias diárias observadas podem se basear em cobertura parcial; imputar
  células ausentes não corrige automaticamente esse viés de amostragem.

Os arquivos reconstruídos são destinados a análise retrospectiva e experimentos
de sensibilidade. Para avaliação de previsão, dividir cronologicamente **antes**
do ajuste e repetir seleção/validação dentro do treino. As funções aceitam
`indices_doadores` para restringir doadores; não usar os CSVs retrospectivos
como evidência de uma avaliação sem vazamento.

Nunca avaliar previsões contra potência imputada. O arquivo de indicadores contém
`potencia_original_observada` e `avaliacao_potencia_permitida`; o segundo também
exige cobertura original de pelo menos 80% dos intervalos (limiar operacional
configurável, não um consenso da literatura).

## Arquivos produzidos

- `base_diaria_leopoldo.csv`: agregação observada, preservada.
- `base_diaria_leopoldo_imputada.csv`: 363 dias e as 13 colunas de referência.
- `base_diaria_leopoldo_comum_imputada.csv`: 363 dias, data e nove variáveis com doadores.
- `indicadores_imputacao_leopoldo.csv`: origem, método, tamanho da lacuna e cobertura.
- `relatorio_imputacao_leopoldo.csv`: faltantes e proporção estimada por variável.
- `validacao_imputacao_leopoldo.csv`: erros por variável, método e tamanho de bloco.
- `validacao_imputacao_detalhada.csv`: resultados de cada repetição.
- `metodos_imputacao_leopoldo.csv`: seleção do método e número de vizinhos.
- `diagnostico_imputacao_leopoldo.png`: medições e estimativas no tempo.

As porcentagens são calculadas sobre o calendário completo, incluindo os dias
que não apareciam na exportação observada por não terem nenhuma variável válida.

As seis referências principais também estão em `referencias_imputacao.bib`,
para importação no gerenciador bibliográfico ou no projeto LaTeX do TCC.
