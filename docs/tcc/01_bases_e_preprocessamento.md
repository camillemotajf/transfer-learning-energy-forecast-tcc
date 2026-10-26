# Bases de dados e pré-processamento — primeira versão para o TCC

Escopo: experimento diário atual de `teste_cronos_diario.ipynb`, com referência brasileira reconstruída pelos contadores. Auditoria de 25/10/2026. Os procedimentos abaixo descrevem a implementação existente; pontos pendentes de confirmação estão explicitados.

## 1. Visão geral

O problema é prever a geração do próximo dia a partir dos três dias anteriores completos. O alvo brasileiro é a energia diária validada dividida por 24 horas, em kW de potência média. Na Austrália, a variável usada é a média aritmética das leituras de potência disponíveis no dia.

| Aspecto | Austrália — domínio-fonte | Brasil — domínio de destino |
|---|---|---|
| Sistema | Arquivo DKA-M9 A+C Phases, associado ao DKASC em Alice Springs | Usina Leopoldo, código `07-07FX` |
| Arquivo elétrico original | `87-Site_DKA-M9_A+C-Phases.csv` | `Leopoldo-fixa-inv.csv` |
| Unidade temporal original | Leituras de cinco minutos | Registros por inversor consolidados em posições de cinco minutos |
| Formação do alvo diário | Média das leituras de `Active_Power` disponíveis | Soma de oito contadores diários aprovados, dividida por 24 h |
| Fonte meteorológica no modelo | Canais meteorológicos do conjunto australiano | ERA5 regional, via Open-Meteo |
| Capacidade AC adotada | 24 kW | 1000 kW |
| Período utilizado no modelo diário | 25/07/2013–31/12/2023 | Calendário de 2025 |
| Potência diária disponível | 3778 dias em 3812 posições de calendário | 284 dias aprovados em 365 posições |
| Janelas de treino | 3392 disponíveis | 160 |
| Janelas de validação | 352 disponíveis | 26 |
| Janelas de teste brasileiro | Não se aplica | 44 |

As capacidades são parâmetros adotados no projeto, apoiados no registro [fontes_e_hipoteses.json](../../experimentos/transfer_learning_australia_brasil/historico_diario/fontes_e_hipoteses.json). A documentação final deve confirmar as placas técnicas e a associação exata do arquivo australiano à configuração da instalação. Capacidade nominal instalada não equivale à disponibilidade operacional em todos os dias.

## 2. Rastreabilidade dos dados e escolha da versão

O conjunto australiano recebido tem 4378 linhas diárias, de 25/07/2013 a 23/08/2025. O experimento atual recorta somente até 31/12/2023. Seu SHA-256 coincide com o registrado no contrato diário histórico. A auditoria também releu o CSV original de cinco minutos, com 1.256.431 linhas, sem timestamps inválidos ou duplicados, e reproduziu numericamente suas médias diárias.

A base brasileira atual não é o arquivo antigo de 297 dias baseado na cobertura de uma série de potência tratada. Também não é a base de cinco minutos usada para prever cinco minutos à frente. Usar estatísticas ou métricas dessas versões como se fossem o mesmo experimento produziria uma descrição incorreta.

Os hashes e verificações desta etapa estão em [auditoria_preprocessamento.json](auditoria_preprocessamento.json). A reprodução é feita por [auditar_bases_diarias_tcc.py](../../scripts/auditar_bases_diarias_tcc.py), que não altera bases nem modelos.

## 3. Tratamento da base australiana

### 3.1 Agregação diária

O CSV intradiário contém potência, grandezas elétricas e meteorológicas. Os timestamps são interpretados, ordenados e agrupados por dia. A potência diária é calculada como:

\[
\bar P_{AU,d} = \frac{1}{n_d}\sum_{k \in \mathcal O_d} P_{d,k},
\]

em que \(\mathcal O_d\) representa as leituras disponíveis e \(n_d\) sua quantidade. As variáveis meteorológicas selecionadas também são agregadas pela média.

O cálculo inclui os valores noturnos presentes. **Não é automaticamente uma média integral das 24 horas quando faltam leituras.** A série diária recebida coincide com essa média das amostras disponíveis, com diferença numérica inferior a \(10^{-10}\). Não foi aplicado um corte mínimo de cobertura intradiária antes de aceitar esses alvos no protocolo diário atual.

Os carimbos são mantidos na convenção temporal do arquivo; o processamento diário não converte o relógio australiano para o brasileiro. A convenção exata do timestamp australiano precisa acompanhar a documentação definitiva da fonte, pois não há offset explícito no CSV. O [glossário oficial do DKASC](https://dkasolarcentre.com.au/glossary) é uma referência para grandezas e unidades; a ficha do sistema está associada a [DKA-M9 A+C Phases](https://dkasolarcentre.com.au/source/alice-springs/dka-m9-a-c-phases).

### 3.2 Calendário completo e controle de qualidade diário

O recorte até 2023 é reindexado para todos os 3812 dias entre suas datas inicial e final. Datas não registradas permanecem ausentes. Valores infinitos são convertidos em ausentes; potência média negativa é reprovada. Os limites operacionais adotados para as três covariáveis são:

| Variável | Limite inferior | Limite superior |
|---|---:|---:|
| Temperatura | −20 °C | 60 °C |
| Umidade relativa | 0% | 100% |
| GHI médio diário | 0 W/m² | 600 W/m² |

Esses limites são regras operacionais do projeto, não padrões universais de validação fotovoltaica. O controle desta etapa atua sobre os valores já agregados por dia.

### 3.3 Faltantes e preenchimento causal de meteorologia

Somente temperatura, umidade e GHI recebem propagação do último valor válido, por no máximo dois dias consecutivos (`ffill(limit=2)`). O procedimento usa apenas valores passados. **Potência não é preenchida.** Ausências que restam impedem a criação das janelas correspondentes.

| Variável | Ausentes após completar calendário | Reprovados pelos limites | Preenchidos pelo passado | Ausentes finais |
|---|---:|---:|---:|---:|
| Potência | 34 | 0 | 0 | 34 |
| Temperatura | 34 | 9 | 18 | 25 |
| Umidade relativa | 34 | 2 | 16 | 20 |
| GHI | 34 | 0 | 14 | 20 |

As colunas contam etapas diferentes: ausentes finais = ausentes de calendário + reprovados − preenchidos. Seno e cosseno anuais são calculados a partir da data e não têm faltantes.

Fonte: [auditoria_faltantes_australia.csv](auditoria_faltantes_australia.csv). A aplicação das regras existentes reproduziu `australia_pu.csv` com diferenças inferiores a \(10^{-10}\).

### 3.4 Limitação encontrada na cobertura dos alvos

A grade de cinco minutos tem 288 posições por dia. A auditoria contou as leituras de potência nos próprios dias usados como alvos:

| Partição australiana | Alvos | Alvos com 288 leituras | Alvos com menos de 95% das leituras | Menor contagem |
|---|---:|---:|---:|---:|
| Treino | 3392 | 3339 | 10 | 145 |
| Validação | 352 | 239 | 84 | 97 |

Um dia pode ter menos de 288 leituras e ainda superar 95%; por isso, as duas colunas não são complementares. Contagem de leituras não comprova qualidade física das medições.

Esse resultado mostra que a completude da **tabela diária** não garante a cobertura das **amostras intradiárias**. No texto final, não se deve afirmar que os alvos australianos representam invariavelmente 24 horas completas ou que receberam o mesmo controle de qualidade do Brasil.

A metodologia definitiva precisará fixar como tratar essa questão: por exemplo, um critério de cobertura e uma análise de sensibilidade, com nova preparação e avaliação se os alvos forem alterados. Nenhuma exclusão ou alteração foi feita nesta auditoria. Lista dos dias em [auditoria_cobertura_alvos_australia.csv](auditoria_cobertura_alvos_australia.csv).

## 4. Tratamento da base brasileira

### 4.1 Seleção, tempo e duplicatas

O arquivo original tem registros de mais de um código de usina. A reconstrução atual filtra **somente `07-07FX`** e identifica os oito equipamentos `inverter121` a `inverter128`.

Os timestamps são lidos em UTC, convertidos para `America/Sao_Paulo` e associados à posição de cinco minutos imediatamente anterior (`floor('5min')`). Registros sem timestamp ou equipamento são removidos. Potência e contadores são convertidos para números; valores negativos passam a ausentes. Duplicatas do mesmo equipamento e posição são consolidadas pela mediana.

O resumo registra 52.617 linhas excedentes consolidadas nessa etapa e 680.772 registros equipamento-horário mantidos em 2025 após os filtros. A contagem de duplicatas é produzida antes do recorte pelo ano local; não deve ser apresentada como número de dias ou como faltantes do calendário.

### 4.2 Reconstrução da energia e validação cruzada dos contadores

Para cada inversor \(i\) e dia local \(d\), definem-se:

\[
E^{dia}_{i,d} = \max_{h \geq 6} daily\_power\_yields\_kwh,
\]

\[
E^{acum}_{i,d} = \operatorname{mediana}_{h\geq19}(total\_power\_yields\_kwh)
- \operatorname{mediana}_{h<4}(total\_power\_yields\_kwh).
\]

O máximo diário após as 6h evita usar valores residuais do dia anterior logo após a meia-noite. As janelas de madrugada e noite procuram comparar o acumulado antes e depois da geração do dia. São regras adotadas neste conjunto, não limiares universalmente validados.

O inversor é aprovado quando:

\[
0 \leq E^{dia}_{i,d} \leq 1600\ \mathrm{kWh},\quad E^{acum}_{i,d}\geq0,
\]

\[
|E^{dia}_{i,d}-E^{acum}_{i,d}| \leq \max(8\ \mathrm{kWh},\ 0{,}03 E^{dia}_{i,d}).
\]

Ausência dos valores necessários nas bordas do dia impede a aprovação. Exigem-se oito inversores distintos consistentes. Só então se calcula:

\[
E_{BR,d}=\sum_{i=1}^{8}E^{dia}_{i,d},\qquad \bar P_{BR,d}=E_{BR,d}/24.
\]

Assim, a saída em kW é **potência média equivalente de 24 horas**, calculada a partir da energia em kWh. O contador pode conservar o total de energia apesar de lacunas de aquisição de potência; não estamos interpolando cada leitura perdida.

A concordância entre dois contadores do mesmo equipamento é uma verificação de consistência interna. Não substitui calibração nem uma referência independente.

### 4.3 Dias aprovados e ausentes

O calendário de 2025 mantém 365 linhas. São **284 dias aprovados e 81 reprovados**, estes com `energia_kwh` e `Active_Power` ausentes. Não foram imputados dias inteiros, somados apenas sete inversores para criar um alvo ou aplicados KNN/interpolação à referência final.

Em comparação à seleção histórica, 33 dias entram e 46 saem. O resultado atual não é a antiga base de 297 dias nem apenas o maior bloco consecutivo de 43 dias.

O diagnóstico dos 44 alvos de teste encontrou diferença máxima de aproximadamente 0,1292 kW entre as referências pelo contador diário e pelo acumulado. Isso não valida automaticamente os 81 dias reprovados nem exclui erro comum dos medidores.

Fonte final: [leopoldo_diario_contadores_auditado.csv](../../data/processed/brasil/leopoldo_diario_contadores_auditado.csv). Implementação: [chronos_diario_contadores.py](../../src/energia_transfer/chronos_diario_contadores.py).

## 5. Meteorologia brasileira usada nesta aplicação

Para esta versão do experimento, temperatura, umidade e GHI vêm **integralmente de uma fonte pública homogênea**, e não de uma mistura da estação local com ERA5. A localização solicitada foi latitude −16,55°, longitude −48,85° e altitude 927 m; a célula retornada pelo serviço é centrada aproximadamente em −16,50° e −48,75°.

O ERA5 é uma reanálise em grade. Seus fundamentos são descritos por [Hersbach et al. (2020)](https://doi.org/10.1002/qj.3803), e o acesso adotado utiliza a [API histórica do Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api), com `models=era5` explicitamente selecionado.

| Entrada | Fonte horária | Agregação |
|---|---|---|
| `Weather_Temperature_Celsius` | `temperature_2m` | Média de 24 valores horários |
| `Weather_Relative_Humidity` | `relative_humidity_2m` | Média de 24 valores horários |
| `Global_Horizontal_Radiation` | `shortwave_radiation` | Média de 24 intervalos horários; W/m² |

A radiação é rotulada pelo serviço no fim da hora anterior. O código desloca seu índice em uma hora para trás antes de agrupar pelo dia local. A média inclui a noite e não deve ser confundida com energia solar diária em kWh/m². Dias sem as 24 horas necessárias permanecem ausentes na variável correspondente.

O cache consultado começa em 02/01/2025 e inclui a borda até 01/01/2026. O arquivo diário tem meteorologia completa em 364 dias de 2025; não extrapola 01/01. Nos três históricos brasileiros finais, não houve perda adicional de janelas por falta de meteorologia passada.

A estação local foi investigada em etapas anteriores, com lacunas e diferença de escala no GHI. O experimento atual evita misturar essas escalas escolhendo ERA5 para as três covariáveis. Inclinação de painéis, radiação inclinada, vento e chuva não entram neste benchmark; a hipótese geométrica discutida antes não é necessária para o GHI utilizado aqui.

Reanálise histórica não equivale a previsão meteorológica operacional. O modelo usa apenas meteorologia dos dias anteriores; a latência real de disponibilização do ERA5 não foi simulada. Os valores do próprio dia alvo aparecem somente no diagnóstico retrospectivo dos erros.

## 6. Correspondência das entradas e escalas

As seis variáveis históricas são potência, temperatura, umidade, GHI e seno/cosseno do dia do ano. Para uma data com ordinal \(j\) e ano com \(D\) dias:

\[
s=\sin(2\pi(j-1)/D),\qquad c=\cos(2\pi(j-1)/D),\quad D\in\{365,366\}.
\]

O calendário do dia previsto também é conhecido e fornecido aos cenários com covariáveis. Meteorologia observada no futuro não é fornecida. Vento foi excluído a pedido do pesquisador.

A escala física da potência é:

\[
P^{pu}=\bar P/P^{AC}_{nominal},
\]

com 24 kW na Austrália e 1000 kW no Brasil. Essa divisão aproxima escalas de capacidade; não elimina diferenças de clima, tecnologia, disponibilidade operacional ou definição da média diária.

É necessário distinguir as etapas estatísticas:

| Método/protocolo | Padronização utilizada |
|---|---|
| Chronos diário atual | Recebe potência em p.u., meteorologia nas unidades físicas e calendário; não aplicamos o `StandardScaler` histórico externo a essas entradas |
| MLP/LSTM brasileiras atuais | Médias e desvios de X/y ajustados somente nas 160 janelas de treino brasileiras; aplicados sem reajuste à validação/teste. Calendário futuro mantém [-1,1] |
| MLP/LSTM com transferência no estudo diário antigo | Escalas do treino australiano compartilhadas com o Brasil; outra base e outro protocolo |

O Chronos possui seu processamento interno; a ausência de um padronizador externo não significa ausência de transformações internas do modelo. O arquivo australiano em p.u. é reaproveitado, mas os tensores historicamente padronizados não são passados ao Chronos: as janelas são refeitas a partir do CSV em unidades físicas/p.u.

## 7. Janelas e partições cronológicas

Uma origem de previsão em \(d\) recebe os dias \(d-3,d-2,d-1\) e tem como alvo \(d\). Exigem-se potência válida nos quatro dias e covariáveis completas nos três dias anteriores. Uma janela não atravessa dia reprovado; as datas não são comprimidas após a remoção de ausências.

Isso não exige um único bloco contínuo para todo o treino: cada janela válida é uma amostra. Na LSTM, o estado é reiniciado a cada janela. Na avaliação de um passo, o histórico observado é atualizado em cada origem; não é uma previsão recursiva de todo o bimestre.

| Domínio | Partição | Período do alvo | Janelas |
|---|---|---|---:|
| Austrália | Treino | Até 31/12/2022 | 3392 |
| Austrália | Validação | 2023 | 352 |
| Brasil | Treino | Até 30/09/2025; primeiro alvo elegível em 02/02 | 160 |
| Brasil | Validação | Outubro de 2025 | 26 |
| Brasil | Teste | Novembro e dezembro de 2025 | 44 |

As validações podem usar históricos anteriores ao seu início, pois são informações passadas disponíveis na emissão. Nenhum alvo de validação/teste ajusta os padronizadores locais. A regra de parada e as decisões usam validação, não o erro de teste.

No ajuste conjunto Chronos, são amostradas 160 janelas australianas distribuídas no tempo e 160 brasileiras para balancear as usinas. Checkpoints do portfólio usam 19 origens de validação de cada usina; ajuste individual brasileiro usa 26; ajuste só australiano usa 38 australianas. A avaliação final brasileira mantém os mesmos 44 alvos entre os métodos.

## 8. Texto-base para a seção de metodologia

> Foram utilizados dados de uma instalação fotovoltaica australiana como domínio-fonte e de uma usina brasileira como domínio de destino. Na fonte australiana, as leituras intradiárias foram agregadas por média aritmética diária, mantendo-se o calendário completo e identificando-se ausências e valores fora dos limites operacionais adotados. Apenas lacunas meteorológicas receberam propagação limitada a dois dias anteriores; a potência não foi imputada. Na usina brasileira, a energia diária foi reconstruída pela soma dos contadores dos oito inversores, condicionada à concordância com as diferenças dos contadores acumulados. A energia aprovada foi dividida por 24 horas para representar potência média diária. A meteorologia brasileira foi obtida de ERA5 e agregada ao calendário local. As potências foram expressas por unidade da capacidade AC nominal adotada. Formaram-se janelas de três dias consecutivos para previsão de um dia, preservando as interrupções e realizando-se a separação cronológica entre treinamento, validação e teste.

Esse parágrafo descreve o processamento atual. Deve acompanhar a limitação de cobertura australiana, as diferenças entre as referências e a condição retrospectiva da meteorologia; não deve ser usado sozinho como prova de equivalência física perfeita entre as bases.

## 9. Conferências e decisões pendentes antes de fechar a metodologia

- Confirmar a ficha técnica, capacidades AC e convenção temporal australiana com a documentação primária da instalação.
- Fixar e justificar um critério de cobertura dos dias australianos. Se ele alterar a base, preparar e avaliar novamente os modelos; não substituir silenciosamente suas métricas atuais.
- Justificar os horários e tolerâncias dos contadores brasileiros como regras adotadas e realizar sensibilidade, evitando apresentá-los como normas da literatura.
- Separar a comparação entre arquiteturas da comparação que isola o efeito de transferência/ajuste fino; ver [enquadramento do estudo](00_enquadramento_do_estudo.md).
- Definir cenários de escassez e nova avaliação temporal antes de novas buscas. O teste atual já foi consultado e seus 44 alvos são sobrepostos temporalmente por seus históricos.

## 10. Evidências e reprodução

```powershell
.venv\Scripts\python.exe scripts/auditar_bases_diarias_tcc.py
```

| Etapa | Evidência local |
|---|---|
| Média diária australiana | [preparacao.py](../../src/energia_transfer/preparacao.py), [auditoria_australia.json](auditoria_australia.json) |
| Qualidade e preenchimento australianos | [deep_learning/dados.py](../../src/energia_transfer/deep_learning/dados.py), [configuração diária arquivada](../../experimentos/transfer_learning_australia_brasil/historico_diario/config.json) |
| Correspondência da fonte efetivamente usada | [contrato diário arquivado](../../experimentos/transfer_learning_australia_brasil/historico_diario/dados/contrato.json) |
| Contadores e janelas brasileiras | [chronos_diario_contadores.py](../../src/energia_transfer/chronos_diario_contadores.py) |
| Consulta meteorológica | [metadados ERA5](../../data/external/era5/open_meteo_era5_2025_metadados.json), [meteorologia_publica.py](../../src/energia_transfer/meteorologia_publica.py) |
| Entradas do Chronos | [extrair_diarias em chronos_diario.py](../../src/energia_transfer/chronos_diario.py) |
| Padronização local e redes de referência | [benchmark_diario_brasil.py](../../src/energia_transfer/benchmark_diario_brasil.py) |
| Partições usadas | [particoes.csv](../../experimentos/chronos_diario_contadores/resultados/particoes.csv) |

Referências externas verificadas para esta etapa estão em [referencias.bib](referencias.bib). Os arquivos descritivos antigos do repositório incluem outros protocolos e não substituem a rastreabilidade da execução diária atual.
