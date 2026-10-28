# Base brasileira após alinhamento temporal

**CSV principal consolidado:** [brasil_merge_5_minutos.csv](../../../data/interim/brasil/brasil_merge_5_minutos.csv). O notebook `03_01_brasil_merge_horarios.ipynb` gera esse arquivo com uma linha por intervalo de cinco minutos, potências AC/DC somadas, energias diária/mensal/acumulada somadas e os 55 canais físicos da estação. Cada total exige os oito inversores. As energias são contadores registrados no horário, sem integração temporal de cinco minutos.

**Auditoria detalhada:** os arquivos abaixo mantêm os valores individuais e o rastreio dos horários.

Execute primeiro o notebook [03_01_brasil_merge_horarios.ipynb](../../../notebooks/tcc/03_01_brasil_merge_horarios.ipynb).

`brasil_merge_5min.csv` tem uma linha por intervalo de cinco minutos, em horário local, com os oito inversores em colunas e a estação associada pela mesma grade.

* `total_active_power_w__inverter121` a `total_active_power_w__inverter128`: potência de cada inversor, em W.
* `potencia_total_w`: soma das oito potências no mesmo intervalo.
* `potencia_total_kw`: soma em W dividida por 1000.
* `n_inversores_com_potencia`: quantidade de inversores com potência numérica finita.
* `potencia_total_disponivel`: indica que todos os oito valores estão disponíveis.
* `estado_potencia`: classifica ausência de registros, potência incompleta ou total disponível.

Registros repetidos do mesmo equipamento e intervalo são consolidados pela mediana. O alinhamento usa `datetime`, convertido de UTC para `America/Sao_Paulo`, e o início do intervalo de cinco minutos (`floor`). `real_datetime` não define a chave do merge. Não se aproximam leituras entre intervalos diferentes, nem se preenchem ausências.

Os mapas de horários preservam a correspondência com as linhas e os horários originais. As tabelas de cobertura nesta pasta se referem à visão consolidada. O dicionário completo das colunas e as estatísticas originais permanecem em `../caracterizacao_dados_crus/`.

O arquivo contém cinco grandezas dos inversores (potência AC, potência DC, energia diária, mensal e acumulada), além de todos os canais físicos da estação, com contagens e sinalizadores. As outras colunas continuam nos CSVs originais.

A soma de potências é feita entre inversores no mesmo intervalo. Não representa energia integrada no tempo nem substitui o alvo diário validado pelos contadores de `teste_cronos_diario.ipynb`.
