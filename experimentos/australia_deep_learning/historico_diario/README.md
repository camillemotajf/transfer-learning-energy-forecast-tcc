# Austrália — pré-treinamento com MLP e LSTM

Experimento separado da preparação das bases. O objetivo é prever a potência média do dia seguinte a partir do histórico, salvar dois modelos fonte e definir as entradas que serão reproduzidas na futura adaptação ao Brasil. **Velocidade e direção do vento foram excluídas por solicitação do usuário.**

## Notebooks

| Ordem | Notebook | Conteúdo |
| --- | --- | --- |
| 01 | [Inputs, lags e faltantes](notebooks/01_inputs_lags_e_faltantes.ipynb) | Calendário, valores ausentes/suspeitos, entradas candidatas, correlações no treino e seleção por validação |
| 02 | [Treino da MLP](notebooks/02_treino_mlp.ipynb) | Rede pequena, parada antecipada, previsões e checkpoint |
| 03 | [Treino da LSTM](notebooks/03_treino_lstm.ipynb) | Sequências sem estado persistente entre janelas, métricas e checkpoint |
| 04 | [Comparação](notebooks/04_comparacao_modelos.ipynb) | Mesmos alvos, persistência como referência e decisão somente pela validação |
| 05 | [MLP com correção da persistência](notebooks/05_mlp_correcao_persistencia.ipynb) | MLP direta versus residual, cinco sementes pareadas, sem alterar os modelos originais |

Cada notebook inicializa seus próprios caminhos. O 01 produz os arquivos de entrada dos demais; o 04 precisa dos checkpoints de 02 e 03. Os cálculos estão em `src/energia_transfer/deep_learning/`, para não duplicar a lógica entre notebooks.

O 05 precisa apenas das entradas do 01. Testa `previsão = potência anterior + correção`, com cinco sementes iguais às da MLP direta refeita como controle. A comparação mantém arquitetura, lags e treino fixos. A decisão usa o RMSE médio da validação de 2023, sem escolher a melhor semente; 2024–2025 já foi inspecionado e sua avaliação é exploratória. Configuração em [config_correcao_persistencia.json](config_correcao_persistencia.json); resultados e checkpoints em subpastas `correcao_persistencia/`. Para executar somente este experimento: `.venv\Scripts\python.exe experimentos\australia_deep_learning\executar.py correcao`.

Resultado inicial do 05: RMSE médio da validação de 0,7288 (direta) para 0,7213 (residual); no teste exploratório, de 0,8586 para 0,8353. A residual venceu em quatro dos cinco pares e teve menor dispersão entre sementes. Na semente 42 do modelo original, o RMSE de teste piorou ligeiramente de 0,8371 para 0,8433. O ganho médio é pequeno; não representa um salto sobre o modelo original nem comprova ganho de transferência. Tabelas em [resumo_metricas.csv](resultados/correcao_persistencia/resumo_metricas.csv).

## Dados e faltantes

A entrada preservada é `data/raw/australia/base_diaria_australia.csv`: 4.378 linhas recebidas, 4.413 dias de calendário, 35 datas ausentes e dois campos de potência vazios nas linhas existentes. Após reindexar, há 37 alvos ausentes. Nenhum alvo nem histórico de potência é imputado; zeros observados são mantidos.

Os limites de sensores em [config.json](config.json) são critérios operacionais editáveis, não normas universais. Temperaturas fora de −20 a 60 °C, umidade fora de 0–100%, radiação diária média fora de 0–600 W/m² e chuva negativa são marcadas na cópia de trabalho. O diagnóstico separa valores inválidos de células vazias e de datas ausentes. Não se corrige automaticamente a mudança de nível da potência ao longo dos anos.

As entradas meteorológicas podem receber o último valor observado no passado por no máximo dois dias consecutivos. Não há interpolação com informação futura. Datas sem potência no histórico ou no alvo impedem a criação da janela. A fonte disponível já é diária e não permite verificar quantos horários contribuíram para cada média.

## Seleção de variáveis e lags

Grupos candidatos:

- Potência passada e calendário anual em seno/cosseno.
- Os anteriores com temperatura, umidade, GHI, radiação difusa horizontal e chuva.
- Os anteriores com radiação global e difusa no plano inclinado.

Corrente e contador de energia acumulada são excluídos para reduzir dependência da instalação e risco de atributos inadequados à transferência. Vento não participa de nenhum grupo. Elegibilidade por faltantes e escalas usa somente o treino. As correlações por lag são diagnósticas e não demonstram causalidade.

Históricos candidatos: 1, 3 e 7 dias. Uma regressão Ridge avalia cada grupo/lag na validação, sempre no mesmo conjunto de alvos comuns aos candidatos. O contrato escolhido pelo menor RMSE é usado nas duas redes, dando a ambas os mesmos dados de entrada. A seleção por Ridge é inicial e não garante a configuração ótima para redes ou transferência.

Cada amostra contém `t-L ... t-1` para prever `t`. A MLP achata o tensor; a LSTM preserva a dimensão temporal. O contrato com ordem, variáveis, lags, escalas e hashes está em [dados/contrato_inputs.json](dados/contrato_inputs.json).

## Separação temporal e treino

- Treino: até 31/12/2022.
- Validação: 2023, usada para lags, grupos e parada antecipada.
- Teste: 01/01/2024 até o fim da série, sem participar dessas decisões.

As escalas são ajustadas somente no treino. A MLP usa camadas de 32 e 16 unidades; a LSTM usa 16 unidades. Ambas usam AdamW, MSE padronizado, semente 42, CPU e no máximo 150 épocas, com paciência de 20 épocas. O checkpoint restaurado é o de menor perda de validação. O estado da LSTM é reiniciado em cada janela; os pesos são compartilhados. A persistência prevê amanhã com a potência observada hoje. Predições finais são limitadas inferiormente a zero.

O teste representa previsões diárias atualizadas: a cada dia, o histórico real anterior já está disponível, sem reajustar pesos. Não é uma previsão de todo o período de teste emitida de uma única vez. Métricas são calculadas nos mesmos alvos disponíveis para MLP, LSTM e persistência. Ganho negativo significa desempenho pior que a referência.

## Arquivos gerados

```text
dados/        Calendário, inputs, tensores .npz por partição, escalas e contrato
resultados/   Faltantes, seleção, janelas, históricos, previsões e métricas
modelos/      mlp_australia.pt e lstm_australia.pt
figuras/      Diagnósticos, seleção, curvas e comparação
```

Os checkpoints contêm arquitetura, pesos, contrato, escalas e melhor época. `encoder` e `head` estão separados para permitir congelar o primeiro na futura adaptação. O treino no Brasil ainda não é executado aqui.

## Executar

Com a `.venv` do projeto, instalar o PyTorch CPU pelo índice oficial e as dependências do experimento:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r experimentos\australia_deep_learning\requirements.txt
.\.venv\Scripts\python.exe scripts\executar_notebooks.py --pasta experimentos\australia_deep_learning\notebooks
```

Ou, para executar sem interface de notebook:

```powershell
.\.venv\Scripts\python.exe experimentos\australia_deep_learning\executar.py todas
```

Se a fonte ou configuração mudar, executar novamente o notebook 01 e os treinos. Os hashes impedem reutilizar silenciosamente um contrato antigo com outra fonte/configuração.

## Limites e transferência

As métricas estão na unidade numérica da fonte; a potência nominal e a unidade física australianas ainda precisam ser confirmadas. Padronização estatística não é potência por unidade de capacidade instalada. Não rotular os resultados como kW sem essa confirmação.

O contrato selecionado deve ser reproduzido no Brasil, com as escalas brasileiras ajustadas somente nos dados de treino local. Os sensores australianos e ERA5 no Brasil têm representações diferentes: o benefício da transferência precisa ser medido. Históricos mais longos também reduzem o número de janelas brasileiras; sete dias permitem 119 janelas nos blocos atuais, enquanto três dias permitem 193, antes da divisão temporal.

Pesos e escolhas de desenvolvimento usam dados até 2023. O teste australiano posterior não modifica os pesos. Há somente uma semente neste experimento inicial; não representa uma comparação conclusiva entre arquiteturas.

Referências de implementação: [LSTM do PyTorch](https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html), [AdamW](https://docs.pytorch.org/docs/stable/generated/torch.optim.AdamW.html). A descrição da fonte está no [DKA Solar Centre](https://www.dkasolarcentre.com.au/download?location=alice-springs).
