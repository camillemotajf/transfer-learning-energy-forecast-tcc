# Legendas para a seção 3.3

PNG: 300 dpi; PDF: vetorial. Numeração provisória.

## fig_3_3_01_etapas_australia

Ausências em cada etapa australiana

Recorte de 3812 dias até 2023. Ausentes finais = ausentes de calendário + inválidos adicionais − preenchidos. As barras representam etapas e não devem ser somadas entre si. Os limites são aplicados às médias diárias; potência não é imputada.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_02_exemplos_ffill

Exemplos do preenchimento causal meteorológico

Para cada variável, mostra-se a primeira ocorrência de preenchimento no recorte. O último valor válido é propagado por no máximo dois dias consecutivos; não se usa informação futura. São exemplos, não uma validação quantitativa da precisão dos valores imputados.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_03_cobertura_alvos

Cobertura intradiária dos alvos australianos usados

95% é apenas uma referência descritiva, não um filtro aplicado no experimento. Treino: 10 de 3392 alvos abaixo de 95%; validação: 84 de 352. A média de leituras disponíveis pode diferir da média integral das 24 horas; o controle diário não elimina essa limitação.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_04_contadores_brasil

Consistência dos contadores e reprovação de dias brasileiros

A dispersão inclui apenas pares com ambos os contadores finitos; a falta das bordas também reprova dias e é contabilizada à direita. Exigem-se oito inversores consistentes por dia. Os motivos se sobrepõem e não devem ser somados para obter 81 dias. Concordância interna não substitui medição independente.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_05_base_brasileira

Disponibilidade após reconstrução brasileira e meteorologia pública

Há 19 dias sem registros de inversores e 62 dias com registros que não satisfazem a validação: 81 dias sem alvo final; 284 aprovados. Cada variável ERA5 tem 364 dias completos; 01/01 permanece ausente. Não se imputam alvos diários nem se combinam medições da estação com ERA5 nesta versão.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_06_alvos_diarios

Séries diárias após os procedimentos vigentes

As lacunas permanecem no calendário e interrompem as linhas. Austrália: média aritmética das amostras presentes. Brasil: soma dos contadores diários de oito inversores aprovados dividida por 24 horas. As definições e os períodos diferem; esta figura não comprova equivalência de qualidade dos alvos.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_07_janelas

Disponibilidade de alvos e de janelas consecutivas

A previsão de um dia recebe três dias civis anteriores completos; não se comprimem as datas e não se atravessam dias sem potência válida. São 3744 janelas australianas e 230 brasileiras (160/26/44 em treino/validação/teste). Janelas sobrepostas não são amostras estatisticamente independentes.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

## fig_3_3_08_escalas

Normalização física e padronização estatística

À esquerda, capacidades AC adotadas no projeto, ainda sujeitas à confirmação técnica. À direita, históricos de potência das janelas brasileiras; as mesmas média/desvio do treino são aplicadas à validação e ao teste, sem reajuste. Repetições de um dia em janelas sobrepostas entram no ajuste, conforme implementação. Chronos usa entradas em p.u./unidades físicas e não recebe este padronizador externo.

Fonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.

