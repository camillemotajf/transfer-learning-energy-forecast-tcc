# Estratégia 04.01: 240 horas de entrada e 24 horas de saída

Treino: sliding window com passo de uma hora. Validação/teste: emissão diária às 00h, com 24 alvos sem alteração. Blocos, partições e disponibilidade das interpolações são respeitados.

Brasil: 1227 janelas horárias de treino, 17 dias de validação e 9 dias de teste. As amostras sobrepostas não são independentes. As contagens dependem das partições conservadoras herdadas.

AU: X=(N,240,5); BR: X=(N,240,1); y=(N,24) nos dois domínios. X_potencia permite usar AP isoladamente na origem. Metadados de cobertura dos inversores não são entradas físicas adicionais.

As capacidades são parâmetros adotados a confirmar; a unidade original do vento AU também requer confirmação. Este notebook não treina modelos e não altera as bases do 03_03.
