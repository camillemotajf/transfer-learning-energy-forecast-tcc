# Proposta de revisão do capítulo de dados

A proposta pronta para adaptação ao TCC está em [proposta_secao_bases_dados.tex](proposta_secao_bases_dados.tex). É um fragmento LaTeX com capítulo, seções, duas tabelas e referências; não substitui automaticamente o texto anexado nem altera os notebooks ou seus resultados.

## Mudança central

Substituir o inventário extenso de colunas e percentuais por uma cadeia de decisões verificável: **origem dos dados → variáveis selecionadas → tratamento aplicado → blocos elegíveis → amostras supervisionadas**. A análise de faltantes continua necessária para justificar o recorte; seu detalhamento pode ficar no apêndice e nos notebooks. O corpo do TCC precisa apresentar o que afeta a interpretação e a reprodução do experimento.

### Como as duas referências organizam essa parte

- **Bak et al. (2025):** a seção III separa descrição das bases e pré-processamento. As tabelas sintetizam características das instalações, períodos, variáveis e configurações. Isso sustenta uma caracterização compacta, acompanhada de critérios explícitos. Não justifica copiar suas datas para outra instalação ou declarar reprodução integral quando o código foi adaptado. [Artigo](https://doi.org/10.1109/ACCESS.2025.3591040); [implementação dos autores](https://github.com/gist-ailab/transfer-learning-PV-forecasting).
- **Ren et al. (2024):** as seções 4.1 e 4.2 apresentam instalação, período, resolução e entradas, seguidas do processamento e da organização por janelas. O estudo utiliza outra instalação do DKASC e resolução de 15 minutos; seus números não descrevem a nossa base. Serve como referência de exposição e de construção supervisionada, enquanto a escolha 240/24 vem de Bak. [Artigo](https://doi.org/10.3390/en17030698); arquivo local consultado: `C:\Users\Camille\Downloads\energies-17-00698.pdf`.

O texto proposto é uma adaptação aos resultados locais, não uma tradução das referências. As referências não demonstram, por si só, que o tratamento escolhido seja ótimo para estas duas instalações.

## O que manter, reduzir e deslocar

| Elemento do texto anterior | Proposta | Motivo |
|---|---|---|
| Origem e identificação das instalações | Manter em dois parágrafos por domínio | Define procedência e papel experimental |
| Dicionários completos de colunas | Deslocar para apêndice/material de apoio | Muitas grandezas não entram nos modelos |
| Disponibilidade de todos os grupos de sensores | Resumir a restrição que orientou a escolha das entradas | O resultado relevante é a viabilidade conjunta, não cada percentual isolado |
| Figuras de cobertura bruta | Manter na caracterização ou no apêndice | São auditoria; não comprovam o período final após tratamento |
| Período utilizado | Acrescentar tabela antes/depois e regra de seleção | Distingue o arquivo completo dos blocos realmente elegíveis |
| Construção diária | Substituir por potência média horária e saída de 24 horas | Corresponde aos notebooks atuais |
| Discussão de modelos e ganhos | Reservar para metodologia e resultados | A preparação de dados ainda não prova benefício da transferência |

Se for necessária **uma única figura** nesta parte, priorizar o mapa dos blocos após tratamento: [fig_3_3_h04_selecao_blocos.png](../../reports/tcc/preprocessamento_horario_bak2025/figuras/fig_3_3_h04_selecao_blocos.png). Ele explica a escolha temporal mais diretamente que várias tabelas de valores presentes. Não foi inserido automaticamente no LaTeX porque a estrutura de pastas e figuras do projeto final do TCC não foi fornecida.

## Correções substantivas incorporadas

1. Localização brasileira corrigida para **Goiás**, conforme confirmação da autora e coordenadas informadas.
2. Austrália: **13 colunas = timestamp + 12 colunas numéricas**, não 13 variáveis físicas.
3. Brasil: **105.120 posições de calendário**, sem equiparar linhas com medições existentes.
4. Potência em kW, energia em kWh e irradiância em W/m² são grandezas distintas. O alvo atual é a curva de potência média horária.
5. A soma de inversores pode ser parcial. Uma leitura existente não comprova geração total medida pelos oito equipamentos.
6. O período australiano de 2013–2016 é condicionado pelas **cinco variáveis exigidas**, especialmente vento. Não se afirma que toda a potência posterior esteja indisponível.
7. Não se apresenta nenhum dos períodos como uma série única sem lacunas: são **28 blocos australianos e 30 brasileiros**. Os 33 dias brasileiros representam apenas o maior bloco.
8. Fontes externas não são excluídas por serem incompatíveis com “dados reais”. Sua inclusão demandaria outro protocolo; a opção atual delimita o escopo.
9. Transferir diretamente uma camada que recebe cinco variáveis para outra que recebe uma não é uma operação definida. A comparação com entradas comuns usa AP em ambos; qualquer ramo multivariado requer explicação da adaptação.

## Resultados rastreáveis e seu significado

| Medida | Austrália | Brasil |
|---|---:|---:|
| Horas elegíveis após tratamento | 26.710 | 6.310 |
| Dias civis completos elegíveis | 1.111 | 261 |
| Blocos contínuos | 28 | 30 |
| Janelas horárias de treino no protocolo 240/24 | 16.876 | 1.227 |
| Dias-alvo de validação | 63 | 17 |
| Dias-alvo de teste | 62 | 9 |

Fontes: [resumo dos blocos](../../reports/tcc/preprocessamento_horario_bak2025/tabelas/resumo_todos_blocos.csv), [notebook 03_03](../../notebooks/tcc/03_03_tratamento_e_preprocessamento.ipynb) e [notebook 04_01](../../notebooks/tcc/04_01_estrategia_entrada_240h_24h.ipynb).

As contagens de dias-alvo decorrem das janelas de 264 horas, das fronteiras de partição e da exigência de alvos sem alteração. Não são equivalentes ao total de dias da base. Janelas horárias sobrepostas não são observações independentes. No Brasil, os nove dias de teste atuais concentram-se em dezembro; isso limita conclusões sobre desempenho anual e condições sazonais. Recomenda-se apresentar essas contagens na metodologia experimental, sem sobrecarregar a caracterização das bases.

## Pontos a resolver antes da versão definitiva

- **Decisão principal sobre o recorte:** se a comparação central de transferência utilizar apenas potência nos dois domínios, recomenda-se auditar um recorte australiano cuja elegibilidade também dependa apenas de potência. Exigir vento para uma entrada que não o utiliza reduz o histórico sem uma necessidade direta do modelo. O recorte de cinco variáveis pode permanecer como uma coorte comum para comparar configurações no mesmo período, mas essa escolha precisa ser declarada. As datas e contagens apresentadas aqui descrevem o protocolo atual; não substituem essa auditoria alternativa nem demonstram que 2013–2016 seja o melhor período para a configuração univariada.
- **Escala de capacidade:** os notebooks usam 24 kW e 1.000 kW como referências adotadas. Confirmar em documentação técnica e distinguir potência AC e potência nominal DC antes de apresentá-las como capacidades comprovadas.
- **Vento:** o glossário oficial identifica o canal histórico `Wind Speed` em m/s. A proposta usa essa unidade com citação. Os metadados dos notebooks ainda registram a confirmação como pendente; atualizar essa rastreabilidade quando a correspondência com o arquivo for formalmente fechada. [Glossário DKASC](https://dkasolarcentre.com.au/glossary).
- **Referência de potência nos filtros:** o máximo usado no controle de qualidade é calculado retrospectivamente. Isso não é a mesma operação que ajustar a escala das entradas só no treino. Para uma avaliação prospectiva, convém fixar os limites a partir da documentação técnica ou do treino e quantificar o efeito da alteração; essa mudança não foi feita nesta revisão textual.
- **Cobertura intrahorária e dos inversores:** “alvo sem alteração” não significa 12 leituras por hora nem oito inversores presentes. Avaliar a sensibilidade a uma exigência de cobertura antes de atribuir os erros apenas aos modelos.
- **Diferenças artigo/código:** o pseudocódigo de Bak usa temperatura inferior a −30 °C e AP normalizada igual a zero em um dos filtros; o código e o notebook atual usam −10 °C e AP ≤ 0,05. A proposta relata a implementação efetiva e evita dizer que o procedimento é idêntico ao algoritmo publicado.
- **Escolha temporal:** as datas são consequência dos critérios aplicados nesta versão. Antes de treinar/selecionar modelos, registrar o protocolo final e evitar ajustar filtros em função do desempenho no teste.

Esses pontos distinguem o que já foi executado do que ainda precisa ser validado. Não houve novo tratamento de dados, treinamento ou alteração das contagens nesta tarefa. O fragmento foi verificado estruturalmente; a compilação e a paginação dependem do template LaTeX do TCC.
