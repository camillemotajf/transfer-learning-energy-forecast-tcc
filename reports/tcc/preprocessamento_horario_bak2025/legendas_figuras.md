# Figuras 3.3 — tratamento horário baseado em Bak et al.

PNG: 300 dpi; PDF vetorial. Numeração provisória.

## fig_3_3_h01_cobertura_horaria

Cobertura de cinco minutos das horas agregadas

O resample horário usa a média dos valores presentes, como os autores, sem exigir doze amostras. A auditoria separa horas vazias, médias de 1–11 valores e médias de 12 valores. A Austrália exige AP/GHI/temperatura/RH/vento; o Brasil exige somente AP.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h02_anomalias

Triagem dos canais disponíveis em cada domínio

A Austrália aplica QC elétrico e meteorológico e os testes cruzados AP × GHI. O Brasil aplica somente QC elétrico, pois a fonte final é univariada e a escala do GHI local não foi confirmada. Vento incluído somente na Austrália, com valores negativos invalidados. Contagens podem se sobrepor e não demonstram qualidade física completa.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h03_dias

Efeito da remoção de dias e interpolação de horas isoladas

Um dia é reprovado quando há duas horas NaN consecutivas em qualquer coluna exigida. A contagem segue a varredura cronológica do código; a detecção pode alcançar meia-noite. Lacunas residuais nas bordas são mantidas sem extrapolação. Dias de calendário, reprovados e completos são etapas, não parcelas somáveis.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h04_selecao_blocos

Todos os blocos horários incluídos na base final

As faixas mostram todos os blocos elegíveis após QC, descarte de dias e interpolação isolada. AU exige as cinco entradas e BR somente AP. As interrupções são preservadas; os blocos não são concatenados para formar janelas através de lacunas. Continuidade das médias não comprova doze amostras originais por hora.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h05_interpolacao

Exemplos de preenchimento de uma hora isolada

Só se preenche uma lacuna inteira de uma hora com duas bordas válidas. A estimativa é retrospectiva e passa a estar disponível ao término da hora da borda direita. A máscara exportada identifica alvos interpolados. Esses exemplos não constituem validação quantitativa da precisão da imputação.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h06_series

Séries de todos os blocos e cobertura brasileira

Cada linha é desenhada dentro de seu bloco, sem ligar períodos separados. Potência brasileira é soma das parcelas disponíveis; horas com contribuição parcial e menos de doze leituras permanecem identificadas. O maior bloco de 33 dias não limita os demais blocos aproveitados.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h07_maiores_blocos

Comparação dos maiores blocos após o tratamento horário

Duração de cobertura = número de horas / 24. Os blocos são detectados por relógio regular, sem concatenar dias separados. Todos os blocos são exportados e identificados. Os cinco maiores são apresentados como diagnóstico, sem excluir os menores.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

## fig_3_3_h08_escalas

Normalização de potência e preparação das novas escalas

Distingue-se AP/máximo do período, usada apenas para replicar a triagem retrospectiva dos autores, de AP/capacidade adotada (24/1000 kW) e do z-score ajustado nos primeiros 70% das horas elegíveis de todos os blocos. As partições 70/15/15 são propostas preparatórias; nenhum modelo ou resultado antigo foi recalculado.

Fonte: elaboração própria; método e adaptações registrados no manifesto.

