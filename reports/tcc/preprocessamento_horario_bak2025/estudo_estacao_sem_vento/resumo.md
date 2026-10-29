# Estudo rápido da estação brasileira horária — sem vento

Referência de execução: notebook 03_03_tratamento_e_preprocessamento.ipynb, seção complementar.

Calendário elétrico: 8,736 horas. Potência com média original: 7,542. Temperatura e GHI: 2,870 horas cada; RH: zero, coluna inexistente.

No bloco atual de 792 horas, temperatura e GHI têm 535 horas observadas e 257 ausentes.

Após tratar AP + temperatura (+ GHI condicional à escala): 2544 horas em blocos separados, 106 dias civis completos. Maior bloco: 2025-10-19 00:00:00 a 2025-11-16 23:00:00, 696 horas (29 dias).

A maior lacuna da estação tem 5.017 horas: 31/01/2025 13h a 28/08/2025 13h, aproximadamente 209 dias. A interpolação de uma hora não a recupera. Os canais alternativos não acrescentam registros.

Decisão final: Brasil com AP em todos os blocos; Austrália com AP, GHI, temperatura, RH e vento. Os cenários com estação são diagnósticos, não entradas escolhidas. GHI requer confirmar escala/calibração: máximo horário de janeiro próximo de 1100, contra aproximadamente 80–102 de agosto a dezembro; janeiro possui somente 22 horas de amostra. Não se infere fator de correção. Não há RH local. Temperatura, GHI, RH e vento estão excluídos das entradas brasileiras; AP é a entrada comum.

A Austrália possui temperatura e RH na fonte original; a tabela auxiliar verifica o bloco selecionado. Os dados elétricos brasileiros podem conter somas parciais. Este estudo não altera as bases principais, não treina modelos e não demonstra ganho preditivo.
