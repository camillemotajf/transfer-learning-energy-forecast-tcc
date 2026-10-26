# Estudo fotovoltaico em cinco minutos

O fluxo principal usa medições originais na grade de **cinco minutos**, para prever a potência **cinco minutos à frente**. Os notebooks existentes foram atualizados no lugar, mantendo os nomes dos arquivos. `teste_cronos.ipynb` foi restaurado e excluído desta migração a pedido do usuário. Notebooks históricos e exploratórios diários permanecem como registro.

## Dados e faltantes

O CSV australiano original foi localizado em `TCC/87-Site_DKA-M9_A+C-Phases.csv` e copiado para `data/raw/australia/`. Não se desagregaram médias diárias. A grade australiana tem 1.270.529 posições: 59.599 faltas de potência após controle de qualidade (4,69%), incluindo 25.023 diurnas. No Brasil, os oito inversores somados têm 15.097 posições incompletas em 105.120 (14,36%), incluindo 5.407 diurnas. Falta de registro, campos ausentes e valores fora dos limites operacionais são contabilizados na auditoria.

Os relatórios [por dia da Austrália](../reports/intradiario/faltantes_australia_por_dia.csv) e [por dia do Brasil](../reports/intradiario/faltantes_brasil_por_dia.csv) preservam as datas. As tabelas `lacunas_*_5min.csv` listam início, fim e duração das interrupções; `blocos_*_5min.csv` descrevem segmentos disponíveis. Contagens diárias são resumos da auditoria, não agregações dos alvos de previsão.

Os dados brasileiros da estação local têm 68,24% de ausência na temperatura/GHI e escala de GHI ainda não validada. ERA5 está disponível em resolução **horária**: sua repetição por até 55 minutos é identificada como tal, sem deslocar médias da hora anterior para seu início e sem usar observações futuras. A latência real de publicação não é simulada. Esses campos são auxiliares e **não entram no modelo principal de cinco minutos**. Não se apresentam valores interpolados como medições meteorológicas de cinco minutos.

## Tratamento e alvos

- O alvo é sempre potência originalmente medida. No Brasil exige os oito inversores, sem preencher o alvo com previsão, proxy ou interpolação.
- A persistência usa a medição original de cinco minutos antes do alvo. Instantes sem essa medição não entram na avaliação principal.
- Históricos podem usar estimativas causais marcadas. Ffill australiano: até três passos. No Brasil: proxy do inversor ausente pelos outros sete medidos, razão dos 30 dias anteriores (mínimo 100 doadores), por até três ausências consecutivas já conhecidas; depois ffill do total por até três passos. A combinação dos dois estágios pode cobrir até 30 minutos, e fica identificada como estimada.
- Não se consulta o extremo futuro nem o comprimento final de uma lacuna. Não há interpolação linear retrospectiva nos inputs deste experimento.
- A hipótese física de zero é restrita a elevação solar abaixo de −6°, apenas em lacunas, preservando toda leitura real. É uma regra fixada antes da avaliação, sem calibrar a decisão com dados de teste.
- Lacunas residuais interrompem as janelas. Não se comprimem timestamps e não se descartam dias inteiros por uma única falha de aquisição.

Bases processadas em `data/processed/{australia,brasil}/base_5min_*.pkl` e `.csv.gz`. O pickle mantém tipos e reduz custo de leitura; CSV comprimido é a versão interoperável. Os dados diários anteriores continuam disponíveis para o notebook particular restaurado e para histórico.

## Modelos e avaliação

Entradas: potência AC dividida pela capacidade AC instalada (Austrália 24 kW; Brasil 1.000 kW), hora local e dia do ano em seno/cosseno. As capacidades e a correspondência do sistema estão em `experimentos/transfer_learning_australia_brasil/fontes_e_hipoteses.json`. Capacidade instalada não é a potência operacional disponível em cada instante; falhas de seguidores/inversores australianos permanecem uma limitação.

Escalas estatísticas ajustadas apenas em medições diurnas do treino australiano e compartilhadas. Históricos de **30/60 minutos** correspondem a **6/12 passos**, e não 6/12 dias. MLP direta, MLP que corrige a persistência e LSTM, com cinco sementes. Estado LSTM reiniciado a cada janela. No Brasil: sem ajuste dos pesos, ajuste só da saída, ajuste completo com taxa menor e controle local dos pesos. O controle local usa o mesmo processamento fonte para isolar o efeito dos pesos.

Treino fonte 2013–2022 com uma de cada 12 janelas diurnas válidas, por custo de CPU. Validação 2023 e teste australiano 2024–2025 em todos os instantes diurnos elegíveis. Os dados brasileiros não ajustam escalas da fonte. Máximos iniciais fixados em 25 épocas na fonte e 40 na adaptação, com parada antecipada; não há busca orientada pelos testes.

No Brasil: treino até setembro de 2025, validação outubro, teste novembro–dezembro. As duas configurações usam os mesmos **4.043 alvos de validação** e **7.668 de teste**. Históricos de treino: 32.275 janelas com 30 minutos e 31.874 com 60 minutos. Os alvos e persistências são medidos. A avaliação principal é **diurna** (elevação solar > 0); o resultado incluindo noite é complementar e não substitui esse resultado. Sobreposição e autocorrelação impedem tratar os instantes como amostras independentes. Sementes não produzem intervalos de confiança temporal.

## Resultado inicial do protocolo de cinco minutos

A validação brasileira favoreceu **LSTM local**, com **60 minutos de histórico**. No teste diurno de 7.668 instantes, a média de cinco sementes foi RMSE **156,97 kW**, MAE **93,18 kW** e R² **0,781**. A persistência teve RMSE **182,62 kW** e MAE **91,20 kW**: a rede reduz RMSE em cerca de 14,05%, mas não melhora o MAE. A LSTM com transferência e ajuste completo teve RMSE **157,03 kW**, praticamente igual e ligeiramente pior que o controle local. **Não foi demonstrado ganho de transferência neste protocolo.** Não houve troca da escolha usando o teste.

Esses erros não são diretamente comparáveis aos diários: mudaram o horizonte, os alvos e as coortes. A avaliação 24h é complementar e não substitui o teste diurno. Os 16 notebooks principais foram executados e os 44 testes passaram; o verificador reconferiu alvos, janelas, pesos congelados e previsões dos 120 checkpoints brasileiros. `teste_cronos.ipynb` ficou excluído, preservando o código do usuário.

## Reprodução

```powershell
.venv\Scripts\python.exe scripts\executar_fluxo.py todas
.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\executar.py preparar
.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\executar.py pretreinar
.venv\Scripts\python.exe experimentos\australia_deep_learning\executar.py comparar
.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\executar.py adaptar
.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\executar.py avaliar
.venv\Scripts\python.exe scripts\executar_notebooks.py
.venv\Scripts\python.exe scripts\executar_notebooks.py --pasta experimentos\australia_deep_learning\notebooks
.venv\Scripts\python.exe scripts\executar_notebooks.py --pasta experimentos\transfer_learning_australia_brasil\notebooks
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O motor corrente está em `src/energia_transfer/intradiario.py` e `src/energia_transfer/transfer_learning/`. Rotinas diárias antigas são compatibilidade histórica, não o caminho ativo. Modelos, dados e resultados diários dos experimentos foram arquivados em `historico_diario/`, com verificação de cópia antes de remover as versões ativas. Nenhum notebook novo foi criado.

[Notebooks da transferência](../experimentos/transfer_learning_australia_brasil/notebooks/01_dados_contrato_e_blocos.ipynb), [notebook da auditoria brasileira](../notebooks/02_brasil_auditoria_original.ipynb) e [relatório de teste](../experimentos/transfer_learning_australia_brasil/resultados/relatorio.md).
