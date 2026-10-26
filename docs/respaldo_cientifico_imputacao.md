# Avaliação científica do preenchimento meteorológico

Data da revisão: 23/10/2026.

## Conclusão

**Há respaldo científico para reconstruir lacunas meteorológicas usando fontes
externas, incluindo reanálises ERA5. O respaldo ao método não equivale à validação
automática do conjunto preenchido de Leopoldo.**

A implementação atual é defensável como reconstrução retrospectiva exploratória
e como construção de covariáveis meteorológicas de reanálise. A temperatura tem
concordância local preliminar favorável. A irradiância horizontal da série híbrida
ainda não deve ser apresentada como validada, devido à diferença de escala entre
as duas fontes. Umidade e radiações difusas, sem medições locais disponíveis,
devem ser identificadas como variáveis externas/modeladas.

Esta é uma avaliação metodológica baseada na literatura e nos arquivos do projeto,
não uma certificação metrológica da estação ou dos valores reconstruídos.

## Evidência diretamente relacionada

| Referência primária | O que sustenta | Limite da extrapolação para Leopoldo |
|---|---|---|
| [El Hachimi et al. (2023), ClimateFiller](https://doi.org/10.1016/j.simpa.2023.100575) | Uso de reanálise ERA5-Land e aprendizado de máquina para preenchimento e controle de qualidade de séries meteorológicas | O trabalho não valida nossa usina, nosso preenchimento direto com ERA5 nem seus erros locais |
| [Lipson et al. (2022), Harmonized gap-filled datasets from 20 urban flux tower sites](https://doi.org/10.5194/essd-14-5157-2022) | Séries meteorológicas preenchidas com auxílio de ERA5, avaliação contra observações e tratamento de viés por variável | Os locais estudados são urbanos e as correções são específicas; não devem ser transferidas automaticamente à usina |
| [Koubli et al. (2016), Inference of missing data in photovoltaic monitoring datasets](https://doi.org/10.1049/iet-rpg.2015.0355) | Reconstrução fotovoltaica com informação meteorológica externa e validação por retirada artificial de dados | Usa rede meteorológica e modelagem próprias, não reproduz exatamente nossa implementação |
| [Hersbach et al. (2020), The ERA5 global reanalysis](https://doi.org/10.1002/qj.3803) | Fundamentação do produto meteorológico ERA5 | Referência do produto, não prova de precisão no ponto da usina |

Implementações e documentação primárias verificadas:

- [ClimateFiller, repositório dos autores](https://github.com/elhachimi-ch/climatefiller).
- [Urban-PLUMBER, código associado ao artigo](https://doi.org/10.5281/zenodo.7108466).
- [Open-Meteo, API histórica e definições das variáveis](https://open-meteo.com/en/docs/historical-weather-api).
- [pvlib, transposição de irradiância](https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.irradiance.get_total_irradiance.html).

Esses trabalhos sustentam a estratégia geral. Nenhum deles estabelece que reduzir
os faltantes para 5% ou 0% seja, isoladamente, um critério de validade científica.
A meta de 5% adotada anteriormente foi uma escolha operacional deste projeto.

## Evidência disponível na nossa base

Foi revisada a comparação armazenada em `comparacao_era5_estacao.csv`, usando
somente dias com cobertura original da estação de pelo menos 80%.

| Variável | Dias | MAE | RMSE | Correlação de Pearson r | Interpretação desta revisão |
|---|---:|---:|---:|---:|---|
| Temperatura | 109 | 0,687 °C | 0,887 °C | 0,896 | Concordância preliminar favorável; não valida outros meses |
| Velocidade do vento | 109 | 0,773 m/s | 0,968 m/s | 0,794 | Há relação temporal, com viés médio público-local de +0,760 m/s |
| Irradiância horizontal | 109 | 234,406 W/m² | 239,493 W/m² | 0,749 | Diferença de escala impede afirmar compatibilidade da série híbrida |
| Irradiância no plano dos módulos | 109 | 37,113 W/m² | 48,898 W/m² | 0,719 | Estimativa física preliminar, condicionada à geometria assumida |
| Indicador de chuva da base atual | 109 | 1,146 mm | 2,412 mm | 0,266 | Concordância limitada; não confundir com chuva total diária |

Para a direção do vento, a medição local é constante em 360°. A correlação não é
definida para essa série. O erro angular disponível não demonstra capacidade de
reproduzir variabilidade direcional da estação.

Os 109 dias comparados estão distribuídos assim: agosto = 3, setembro = 30,
outubro = 29, novembro = 22 e dezembro = 25. Portanto, a comparação disponível
**não cobre a estação do ano correspondente a fevereiro–julho**.

As estatísticas são diferenças entre observação e produto público, não erros
contra uma verdade sem incerteza. As medições locais também podem conter erros,
e as médias de dias com cobertura parcial podem representar horários diferentes
dos dias completos da reanálise. Comparações em janelas horárias coincidentes
devem complementar a análise diária.

## Limitações que precisam aparecer no TCC

### Extensão e origem do preenchimento

No calendário de 363 dias, seis variáveis meteorológicas têm 140 dias com dados
locais e 223 dias preenchidos externamente: **61,43% dos dias são estimados**.
O maior bloco sem estação tem 208 dias. A contagem de NaNs caiu a zero, mas a
quantidade de medições locais não aumentou.

Umidade, radiação difusa horizontal e difusa inclinada têm **100% dos dias
provenientes de reanálise ou de transposição física**. É mais preciso descrevê-las
como inclusão de covariáveis externas/modeladas do que como recuperação de
leituras locais perdidas. Sem referência observada, sua validação local permanece
pendente; uma estação independente pode servir à comparação.

### Irradiância horizontal

A razão entre as medianas pública e local é aproximadamente **10,70** nos dias
comparados. Uma correlação relativamente alta não elimina esse viés. Verificar
unidades, escala de aquisição, calibração, definição da variável e períodos de
média antes de ajustar ou misturar as séries. Não aplicar uma correção por dez
somente por ela aproximar as curvas.

Até esclarecer isso, a versão meteorológica homogênea pode ser estudada como
**cenário com covariáveis ERA5**. Isso evita a troca de escala no meio da série,
mas não demonstra que o ERA5 seja a verdade local ou que essa versão produza o
melhor modelo de previsão.

### Geometria e radiação inclinada

Inclinação de 20° e orientação norte foram adotadas com base na conversa, sendo
a direção uma hipótese. A sensibilidade dos azimutes 20° e 340° foi de cerca de
+0,061% e -1,001% na energia do período em relação ao norte. A maior diferença
diária chegou a cerca de 6,65%. Isso **não é intervalo de confiança** nem limite
para o erro total: não inclui incerteza meteorológica, albedo, horizonte ou sensores.

### Chuva e agregação temporal

`Weather_Daily_Rainfall` é atualmente a média do contador acumulado durante o dia,
para reproduzir a transformação do notebook australiano. Não é o total diário
de precipitação. Esse indicador e a hipótese de chuva uniforme dentro da hora
precisam ser declarados. Para analisar precipitação física diária, usar
`Rainfall_Total_mm` e harmonizar a definição entre as duas bases.

### Previsão e potência imputada

O ERA5 é retrospectivo. Usar meteorologia do próprio dia que só ficou disponível
posteriormente como se fosse informação conhecida na emissão de uma previsão
pode gerar vazamento temporal. A validade depende do horizonte e dos atributos
que estarão disponíveis no uso pretendido do modelo.

Também há 25 dias de potência imputada. Não usá-los como verdade de referência
para testar previsões. O indicador `avaliacao_potencia_permitida` já exige potência
observada e cobertura de pelo menos 80%, totalizando 271 dias no conjunto atual.
O limiar de 80% é operacional e precisa de justificativa/sensibilidade, não é um
consenso extraído das referências.

## Protocolo necessário para fortalecer a defesa

1. **Controle de qualidade e unidades:** resolver a escala da GHI e verificar
   metadados dos sensores, alturas de vento, acumuladores e dias incompletos.
2. **Validação temporal:** usar blocos observados retirados artificialmente para
   comparar métodos e correções; avaliar MAE, RMSE e viés, por variável e estação
   do ano. Não ajustar uma correção com os mesmos pontos usados para avaliá-la.
3. **Referência externa independente:** buscar dados de estação regional no período
   sem observações locais, especialmente fevereiro–julho. Sem essa evidência,
   declarar que o bloco de 208 dias não foi validado diretamente.
4. **Sensibilidade do estudo de previsão:** comparar resultados usando somente
   observações elegíveis, preenchimento híbrido e meteorologia homogênea. Manter
   os mesmos períodos de teste e avaliar somente alvos elétricos observados.
5. **Rastreabilidade:** publicar origem por célula, percentuais estimados, hashes,
   coordenadas, fuso, unidades, parâmetros físicos e código, como já iniciado.

Não é necessário provar igualdade com medições indisponíveis. É necessário
delimitar a conclusão: estudo de previsão com covariáveis de reanálise e análise
de sensibilidade, em vez de afirmar reconstrução comprovada de todas as leituras.

## Texto possível para a metodologia

As lacunas meteorológicas foram preenchidas por associação temporal com dados
horários da reanálise ERA5 disponibilizados pela API Open-Meteo, para a região da
usina. As séries foram convertidas para dias locais e harmonizadas em unidades,
preservando-se os valores observados e identificando-se a origem de cada
estimativa. A estratégia é apoiada por trabalhos de preenchimento meteorológico
com reanálises (El Hachimi et al., 2023; Lipson et al., 2022) e de reconstrução de
dados fotovoltaicos com informação meteorológica externa (Koubli et al., 2016).
A concordância local foi examinada nos períodos com observações disponíveis.
Os intervalos sem referência local, as variáveis inteiramente externas e as
hipóteses geométricas foram tratados como limitações do estudo. O preenchimento
não foi interpretado como obtenção de novas medições da estação.
