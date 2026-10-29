# Sequências temporais: quatro históricos e horizonte de 24 horas

Resultados da execução do `03_04_construcao_sequencias_temporais.ipynb` sobre
os CSVs de todos os blocos exportados pelo `03_03`. As fontes, suas assinaturas
SHA-256 e os 24 arquivos NPZ constam de `manifesto.json`.

Cada amostra exige histórico finito e disponível na emissão, 24 alvos observados,
continuidade de uma hora e permanência no mesmo bloco e na mesma partição.
O requisito de observação vale também para o treino. `X=(N,L,C)`,
`X_potencia=(N,L,1)` e `y=(N,24)`. Os arquivos também incluem `y_kw`,
timestamps, máscaras e contagens da cobertura original dos alvos.

## Janelas horárias aproveitáveis

| Domínio | Histórico (h) | Treino | Validação | Teste |
|---|---:|---:|---:|---:|
| Austrália | 24 | 5.486 | 2.601 | 2.275 |
| Austrália | 48 | 5.462 | 2.434 | 2.159 |
| Austrália | 168 | 5.303 | 1.787 | 1.662 |
| Austrália | 240 | 5.160 | 1.503 | 1.476 |
| Brasil | 24 | 3.269 | 827 | 662 |
| Brasil | 48 | 2.945 | 779 | 588 |
| Brasil | 168 | 1.682 | 539 | 290 |
| Brasil | 240 | 1.162 | 395 | 193 |

Estas contagens usam passo de uma hora em todas as partições. As janelas se
sobrepõem e não são amostras estatisticamente independentes.

## Emissões brasileiras às 00h

| Histórico (h) | Treino | Validação | Teste |
|---|---:|---:|---:|
| 24 | 150 | 35 | 32 |
| 48 | 135 | 33 | 27 |
| 168 | 79 | 23 | 14 |
| 240 | 54 | 17 | 9 |

O notebook exporta `emissoes_comuns.csv`, com a interseção entre os quatro
históricos por domínio e partição. Essa seleção permite comparar modelos nas
mesmas datas. A comparação de desempenho não deve usar conjuntos de avaliação
diferentes apenas porque um histórico permite mais amostras.

## Disponibilidade e limitações

`australia_disponibilidade_canal_ano.csv` confirma que `Wind_Speed` não tem
leituras de 2017 a 2025. Há 7.070 horas com vento disponível em 2016; depois
disso a exigência simultânea dos cinco canais impede aproveitar os anos
posteriores. Essa auditoria mede presença antes do QC, sem atribuir uma causa
física ou confirmar a unidade do canal.

As capacidades de 24 kW e 1000 kW continuam como parâmetros adotados a confirmar.
`y_kw` permite recuperar a potência física sem depender da escala normalizada.
`cobertura_inversores_brasil.csv` informa as horas com somas parciais; a
observação de uma soma disponível não garante medição completa da usina.

As divisões 70/15/15 por horas elegíveis continuam provisórias. No Brasil,
o treino termina em setembro de 2025, a validação cobre parte de setembro a
novembro e o teste cobre parte de novembro a dezembro. Isso não garante
cobertura sazonal comparável. As tabelas mensais mostram as horas elegíveis
e as emissões efetivas, para subsidiar a decisão de períodos antes do treino.

## Relação com os demais notebooks

O `03_02` e o `03_03` foram preservados. A auditoria 24 → 1 do `03_03`
continua sendo demonstrativa. O `04_01` já implementava o vetor completo
240 → 24, aceitando alvos tratados no treino e avaliando validação/teste
às 00h. Por isso seus 1.227 exemplos brasileiros de treino diferem dos
1.162 exemplos estritamente observados deste protocolo.

Os testes verificam os quatro históricos, os 24 alvos consecutivos,
fronteiras de partição, lacunas entre blocos, alvos intermediários não
observados, disponibilidade futura da interpolação e tensores vazios.
O notebook foi executado integralmente e reabriu os 24 NPZ para validar
dimensões, valores finitos, timestamps, blocos, partições e máscaras.

Não houve treinamento, destilação ou transferência de pesos. A escolha de
arquiteturas e os períodos definitivos de avaliação pertencem à modelagem.
