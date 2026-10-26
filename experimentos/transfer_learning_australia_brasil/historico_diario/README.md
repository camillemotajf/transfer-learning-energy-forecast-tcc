# Transferência diária Austrália → Brasil

Aplicação separada do experimento australiano anterior. Usa uma MLP direta, uma MLP que corrige a persistência e uma LSTM direta, pré-treinadas na Austrália e adaptadas ao Brasil. Mantém datas originais, blocos interrompidos, cortes cronológicos e cinco sementes, sem escolher a melhor semente. O objetivo é medir se a transferência de pesos acrescenta valor à persistência e ao controle sem pesos pré-treinados.

## Notebooks, na ordem

| Notebook | Conteúdo |
|---|---|
| [01 — Dados, contrato e blocos](notebooks/01_dados_contrato_e_blocos.ipynb) | Unidades/capacidades, faltantes, janelas válidas, normalização compartilhada e diferenças entre domínios |
| [02 — Pré-treino australiano](notebooks/02_pre_treino_australia.ipynb) | Três arquiteturas, históricos de 1 e 3 dias, cinco sementes e curvas de aprendizado |
| [03 — Adaptação brasileira](notebooks/03_adaptacao_brasil.ipynb) | Sem ajuste, só saída, ajuste completo e pesos locais; decisão somente na validação |
| [04 — Teste e conclusão](notebooks/04_teste_comparacao_e_conclusao.ipynb) | Mesmos alvos, erros em kW, pares com o controle local, gráficos e qualidade dos alvos |

Notebooks independentes, com caminhos próprios. Reutilizam artefatos conferidos por hash; flags `REFAZER_*` permitem treinar novamente. A lógica reutilizável fica em [src/energia_transfer/transfer_learning](../../src/energia_transfer/transfer_learning/).

## Contrato e dados

- Horizonte: potência média diária do próximo dia, emitida após o fechamento do dia anterior.
- Entradas: potência passada, temperatura, umidade, GHI e calendário anual em seno/cosseno. Sem vento, POA, corrente ou contador acumulado.
- Capacidade AC instalada adotada: Austrália 24 kW (quatro inversores de 6 kW); Brasil 1.000 kW (oito de 125 kW). Potência AC dividida por capacidade AC; os 23,4 kWp DC australianos não são usados como denominador AC.
- Fonte australiana associada ao sistema 1B Trina pela referência ao arquivo DKA-M9 A+C Phases no notebook histórico. O CSV intradiário não está disponível. Confirmar essa procedência e a placa brasileira antes de publicação definitiva.
- Temperatura em °C, umidade em %, GHI médio em W/m². Dados fora dos limites operacionais são tratados como ausentes. Somente meteorologia australiana pode receber ffill causal limitado a dois dias; potência não é imputada nesta etapa.
- StandardScaler das entradas e do alvo ajustado somente no treino australiano e mantido igual para todos os métodos brasileiros. Nenhum rótulo brasileiro recalibra escalas, inclusive no método sem ajuste.
- O controle local aprende **pesos** apenas no Brasil, com a mesma transformação aprendida na fonte. Essa comparação isola a transferência de pesos; não é um controle cujo processamento inteiro foi aprendido só no Brasil.
- Brasil: 297 dias aprovados, 39 blocos. As janelas exigem todas as datas do histórico e alvo; não se completam dias inteiros nem se concatenam blocos como se fossem contínuos.

As hipóteses, fontes oficiais, mudanças de configuração e falhas de seguidores/inversores estão em [fontes_e_hipoteses.json](fontes_e_hipoteses.json). Capacidade instalada não é capacidade operacional disponível em cada dia. As médias diárias brasileiras ainda podem ter cobertura parcial residual e pequenos trechos reconstruídos.

## Cortes e comparação

| Domínio | Treino | Validação | Teste |
|---|---|---|---|
| Austrália | Até 2022 | 2023 | Não usa 2024–2025 neste pré-treino |
| Brasil | Janeiro–setembro de 2025 | Outubro de 2025 | Novembro–dezembro de 2025 |

Treinos brasileiros: 197 janelas para lag 1 e 151 para lag 3. Validação e teste são interseções de alvos dos dois lags: **19 alvos de validação e 23 de teste para todos**. São poucos dados, com janelas sobrepostas; não equivalem a amostras independentes. A decisão entre configurações usa somente o RMSE médio da validação e inclui persistência como possibilidade de melhor referência. A fonte termina antes de qualquer adaptação brasileira.

O lag de sete dias permanece no experimento anterior, com outro contrato e outras datas; seus erros não devem ser comparados diretamente a estes. Aqui priorizamos os históricos curtos para aproveitar os blocos brasileiros.

| Método | Pesos iniciais | Pesos ajustados no Brasil |
|---|---|---|
| `sem_ajuste` | Pré-treino australiano | Nenhum |
| `cabeca` | Pré-treino australiano | Apenas saída, mantendo encoder idêntico |
| `completo` | Pré-treino australiano | Todos, com taxa 0,0001 |
| `local` | Inicialização aleatória | Todos, com taxa 0,001 |

MLPs: camadas 32 e 16; LSTM: 16 unidades, sem estado persistente entre janelas. AdamW/MSE, parada antecipada, cinco sementes fixadas. A residual soma a potência anterior em p.u. a uma correção aprendida, com escalas da fonte preservadas. Só saída e treino local usam taxa 0,001. Todos recebem o mesmo contrato. Não há busca adicional de hiperparâmetros após olhar o teste.

## Executar

Dependências: [requirements.txt](requirements.txt), que reutiliza o ambiente PyTorch do experimento anterior.

```powershell
.\.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\executar.py todas
.\.venv\Scripts\python.exe scripts\executar_notebooks.py --pasta experimentos\transfer_learning_australia_brasil\notebooks
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_transfer_learning.py -v
.\.venv\Scripts\python.exe experimentos\transfer_learning_australia_brasil\verificar.py
```

Etapas isoladas: `preparar`, `pretreinar`, `adaptar`, `avaliar`. Refazer os dados invalida checkpoints se o contrato mudar; refazer o pré-treino exige refazer a adaptação. O executor de notebooks usa processos separados e salva as saídas padrão Jupyter. `criar_notebooks.py` recria somente os documentos, removendo suas saídas salvas; não é necessário para usar os notebooks já fornecidos.

```text
dados/        Calendários em p.u., tensores por domínio/lag/partição e contrato com hashes
modelos/      30 checkpoints fonte e 120 checkpoints brasileiros
resultados/   Auditoria, janelas, treinos, decisão, previsões, métricas e relatório
figuras/      Dados, curvas, ranking de validação, comparação e previsões brasileiras
```

Consulte o [relatório de resultados](resultados/relatorio.md) depois de executar a etapa de teste. Médias são das métricas de cinco redes, sem ensemble; dispersão entre sementes não é intervalo de confiança temporal. A semente 42 aparece nos gráficos ilustrativos, sem ser escolhida pelo desempenho.

Na execução inicial, a validação escolheu **MLP direta, lag 3, ajuste completo**. No teste comum de 23 alvos, o RMSE médio foi **45,55 kW**, contra **47,29 kW** do controle local equivalente e **54,83 kW** da persistência. As reduções são de aproximadamente **3,7%** e **16,9%**, respectivamente. O R² médio ficou em **−0,080**: o ganho frente à persistência não representa uma previsão de alta precisão. A fração diurna reconstruída dos alvos foi em média **5,41%**, chegando a **7,64%**. Apenas cinco alvos de teste têm pelo menos 95% de cobertura diurna original; a análise complementar é ainda mais limitada. Não foi escolhida outra configuração em resposta ao teste.

## Respaldo e alcance

[Sarmas et al. (2022)](https://doi.org/10.1038/s41598-022-18516-x) fundamentam a comparação entre congelamento e ajuste de pesos em previsão fotovoltaica com escassez de dados. Trabalharam com dados horários e não validam automaticamente nossa base diária. [Bak et al. (2025)](https://doi.org/10.1109/ACCESS.2025.3591040) investigam transferência entre continentes e congelamento de camadas com Transformer; a adaptação para MLP/LSTM é uma hipótese deste projeto. Os cortes seguem os princípios de [avaliação temporal](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).

ERA5 é reanálise retrospectiva. Mesmo com lags terminando na véspera, sua latência não garante disponibilidade na emissão: este estudo não demonstra previsão operacional. Meteorologia observada do próprio dia-alvo não entra nas redes. Confirmar capacidades, procedência, médias e equivalência de sensores antes de inferir utilidade operacional. Não prometemos ganho de transferência ou significância estatística com uma usina, um ano e 23 alvos de teste.
