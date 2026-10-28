# Dicionário investigado das colunas da base Leopoldo

As definições combinam o código de data.ipynb, nomes originais, evidências numéricas e referências técnicas gerais. Não foi identificado um manual do fornecedor com esses nomes de campo. Fontes gerais confirmam os conceitos, não o mapeamento ou a calibração dos sensores locais.

Potência elétrica é dada em W; energia elétrica em kWh. Irradiância solar é potência por área (W/m²); irradiação é energia por área (kWh/m²). A grade de cinco minutos não transforma a janela original de cada sensor em cinco minutos. Nos campos *_kwh_min, os dados sustentam a interpretação de um minuto, em contraste com *_irr_min (mínimo).

## Tempo e identificação

### datetime

Início do intervalo de cinco minutos usado como chave do merge.

Unidade: data/hora UTC. Temporalidade: UTC no CSV; a grade de 2025 é construída no fuso America/Sao_Paulo e convertida para UTC.

Origem e tratamento: Gerado pela grade; horários das fontes são associados por floor de cinco minutos. Fundamento: Confirmado pelo código de data.ipynb.

Referências: código do notebook e esquema local.

### usine_code

Código da usina selecionada: 07-07FX.

Unidade: identificador. Temporalidade: Constante em todos os intervalos da grade.

Origem e tratamento: Preenchido pela configuração USINA, mesmo sem medições. Fundamento: Confirmado pelo código de data.ipynb.

Observação no arquivo: Campo constante entre os valores presentes: 07-07FX.

Referências: código do notebook e esquema local.

### meta.id

Identificador interno do equipamento/registro de estação nos metadados.

Unidade: identificador. Temporalidade: Atributo do registro da estação, não uma medição temporal.

Origem e tratamento: Copiado da estação selecionada; não identifica um inversor nem o agregado da usina. Fundamento: Origem confirmada pelo código; interpretação nominal pelo esquema.

Confirmação pendente: Esquema dos identificadores do fornecedor; NaN sem estação é esperado.

Observação no arquivo: Campo constante entre os valores presentes: 1.0.

Referências: código do notebook e esquema local.

### meta.id_usina

Identificador interno da usina nos metadados da estação.

Unidade: identificador. Temporalidade: Atributo do registro da estação, não uma medição temporal.

Origem e tratamento: Copiado da estação selecionada; não identifica um inversor nem o agregado da usina. Fundamento: Origem confirmada pelo código; interpretação nominal pelo esquema.

Confirmação pendente: Esquema dos identificadores do fornecedor; NaN sem estação é esperado.

Observação no arquivo: Campo constante entre os valores presentes: 50.0.

Referências: código do notebook e esquema local.

### meta.solar_station_id

Identificador interno da estação solarimétrica.

Unidade: identificador. Temporalidade: Atributo do registro da estação, não uma medição temporal.

Origem e tratamento: Copiado da estação selecionada; não identifica um inversor nem o agregado da usina. Fundamento: Origem confirmada pelo código; interpretação nominal pelo esquema.

Confirmação pendente: Esquema dos identificadores do fornecedor; NaN sem estação é esperado.

Observação no arquivo: Campo constante entre os valores presentes: 89.0.

Referências: código do notebook e esquema local.

### real_datetime

Horário adicional fornecido pela estação, preservado no formato original.

Unidade: data/hora; valores observados em UTC. Temporalidade: Não é a chave de cinco minutos; pode diferir de datetime.

Origem e tratamento: Copiado do registro original da estação. Fundamento: Nome e formato observados no CSV.

Confirmação pendente: Confirmar se representa aquisição, relógio do equipamento, transmissão ou recepção.

Referências: código do notebook e esquema local.

### equipment_name

Nome do equipamento da estação; neste arquivo, est_sols1.

Unidade: identificador. Temporalidade: Atributo do registro da estação, não uma medição temporal.

Origem e tratamento: Copiado da estação selecionada; não identifica um inversor nem o agregado da usina. Fundamento: Origem confirmada pelo código; interpretação nominal pelo esquema.

Confirmação pendente: Esquema dos identificadores do fornecedor; NaN sem estação é esperado.

Observação no arquivo: Campo constante entre os valores presentes: est_sols1.

Referências: código do notebook e esquema local.

### _id

Identificador do registro original selecionado da estação.

Unidade: identificador. Temporalidade: Atributo do registro da estação, não uma medição temporal.

Origem e tratamento: Copiado da estação selecionada; não identifica um inversor nem o agregado da usina. Fundamento: Origem confirmada pelo código; interpretação nominal pelo esquema.

Confirmação pendente: Esquema dos identificadores do fornecedor; NaN sem estação é esperado.

Referências: código do notebook e esquema local.

## Albedo

### indice_albedo_medio

Índice de albedo médio, pelo nome do campo.

Unidade: não confirmada: razão ou %. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Observação no arquivo: Coluna totalmente vazia; significado e unidade específicos não podem ser validados pelos dados.

Referências: NREL; ALBEDO.

### albedo_tracker

Albedo rotulado como tracker: razão de radiação refletida e incidente, segundo a nomenclatura.

Unidade: razão adimensional, nominal. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Referências: NREL; ALBEDO.

### indice_albedo_tracker

Índice de albedo rotulado como tracker, com escala aproximadamente percentual nos valores observados.

Unidade: % sugerido pelos dados; confirmar. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Referências: NREL; ALBEDO.

### calculo_albedo_medio

Campo de cálculo do albedo médio, pelo nome original.

Unidade: não confirmada: razão ou %. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Observação no arquivo: Coluna totalmente vazia; significado e unidade específicos não podem ser validados pelos dados.

Referências: NREL; ALBEDO.

### indice_albedo_maximo

Índice de albedo máximo, pelo nome do campo.

Unidade: não confirmada: razão ou %. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Observação no arquivo: Coluna totalmente vazia; significado e unidade específicos não podem ser validados pelos dados.

Referências: NREL; ALBEDO.

### indice_albedo_minimo

Índice de albedo mínimo, pelo nome do campo.

Unidade: não confirmada: razão ou %. Temporalidade: Janela da estatística e método de cálculo não documentados.

Origem e tratamento: Copiado da estação; o notebook não calcula albedo. Fundamento: Conceito documentado; mapeamento local pelo nome e evidência numérica.

Confirmação pendente: Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala.

Observação no arquivo: Coluna totalmente vazia; significado e unidade específicos não podem ser validados pelos dados.

Referências: NREL; ALBEDO.

## Radiação solar

### gri_kwh_day_est

Irradiação diária refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 62 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: NREL; PVSYST.

### gri_irr_med

Irradiância média refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### poa_kwh_hour

Irradiação horária no plano dos módulos (POA).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Não confirmado se hora corrente, hora encerrada ou janela móvel.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: SANDIA; PVSYST.

### poa_irradiancia

Leitura de irradiância no plano dos módulos (POA).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Leitura principal do canal; resposta e agregação temporal do sensor não documentadas.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: SANDIA; PVSYST.

### poa_irr_med

Irradiância média no plano dos módulos (POA).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: SANDIA; PVSYST.

### gri_kwh_acc

Irradiação acumulada refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### poa_irr_max

Irradiância máxima no plano dos módulos (POA).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: SANDIA; PVSYST.

### poa_kwh_min

Irradiação associada a um minuto no plano dos módulos (POA).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Forte evidência numérica de intervalo de um minuto; não equivale aos cinco minutos da grade.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: SANDIA; PVSYST.

### ghi_irr_max

Irradiância máxima global horizontal (GHI).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_irr_med

Irradiância média global horizontal (GHI).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_irr_min

Irradiância mínima global horizontal (GHI).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_kwh_min

Irradiação associada a um minuto global horizontal (GHI).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Forte evidência numérica de intervalo de um minuto; não equivale aos cinco minutos da grade.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### gri_irradiancia

Leitura de irradiância refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Leitura principal do canal; resposta e agregação temporal do sensor não documentadas.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_kwh_day

Irradiação diária global horizontal (GHI).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### gri_irr_min

Irradiância mínima refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_kwh_day_est

Irradiação diária global horizontal (GHI); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 33383 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: NREL; PVSYST.

### poa_irr_min

Irradiância mínima no plano dos módulos (POA).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: SANDIA; PVSYST.

### ghi_kwh_hour

Irradiação horária global horizontal (GHI).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Não confirmado se hora corrente, hora encerrada ou janela móvel.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### ghi_irradiancia

Leitura de irradiância global horizontal (GHI).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Leitura principal do canal; resposta e agregação temporal do sensor não documentadas.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### gri_kwh_day

Irradiação diária refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### poa_kwh_day_est

Irradiação diária no plano dos módulos (POA); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 33383 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: SANDIA; PVSYST.

### poa_kwh_acc

Irradiação acumulada no plano dos módulos (POA).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: SANDIA; PVSYST.

### ghi_kwh_acc

Irradiação acumulada global horizontal (GHI).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### poa_kwh_day

Irradiação diária no plano dos módulos (POA).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: SANDIA; PVSYST.

### gri_kwh_min

Irradiação associada a um minuto refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Forte evidência numérica de intervalo de um minuto; não equivale aos cinco minutos da grade.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### gri_kwh_hour

Irradiação horária refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Não confirmado se hora corrente, hora encerrada ou janela móvel.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh.

Referências: NREL; PVSYST.

### poa_kwh_acc_est

Irradiação acumulada no plano dos módulos (POA); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 33383 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: SANDIA; PVSYST.

### gri_irr_max

Irradiância máxima refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar).

Unidade: W/m², nominal; escala local a confirmar. Temporalidade: Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos.

Origem e tratamento: Copiado do registro da estação escolhido pelo notebook; não representa soma de energia. Fundamento: Conceito técnico documentado; associação ao campo inferida do nome.

Confirmação pendente: Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação.

Referências: NREL; PVSYST.

### ghi_kwh_acc_est

Irradiação acumulada global horizontal (GHI); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 33383 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: NREL; PVSYST.

### gri_kwh_acc_est

Irradiação acumulada refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar); variante com sufixo est.

Unidade: kWh/m², interpretação nominal a confirmar. Temporalidade: Período de acumulação e regras de reinicialização não documentados.

Origem e tratamento: Valor copiado da estação; não é integrado nem somado pelo notebook. Fundamento: Conceito físico documentado; nome e relações numéricas locais.

Confirmação pendente: Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente.

Observação no arquivo: 62 pares disponíveis; 100.00% iguais à coluna sem est (np.isclose padrão).

Referências: NREL; PVSYST.

## Precipitação

### precipitacao_acc

Precipitação acumulada, com período de acumulação não documentado.

Unidade: mm, provável; confirmar no sensor. Temporalidade: Janela exata, fechamento e reinicialização do contador precisam de confirmação.

Origem e tratamento: Copiado da estação; não é somado ao longo dos horários pelo notebook. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: min é indicação temporal provável, não comprovação de precipitação mínima.

Referências: NREL.

### precipitacao_acc_hour

Precipitação acumulada horária.

Unidade: mm, provável; confirmar no sensor. Temporalidade: Janela exata, fechamento e reinicialização do contador precisam de confirmação.

Origem e tratamento: Copiado da estação; não é somado ao longo dos horários pelo notebook. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: min é indicação temporal provável, não comprovação de precipitação mínima.

Referências: NREL.

### precipitacao_acc_min

Precipitação acumulada associada ao minuto, interpretação pelo nome.

Unidade: mm, provável; confirmar no sensor. Temporalidade: Janela exata, fechamento e reinicialização do contador precisam de confirmação.

Origem e tratamento: Copiado da estação; não é somado ao longo dos horários pelo notebook. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: min é indicação temporal provável, não comprovação de precipitação mínima.

Referências: NREL.

### precipitacao_acc_day

Precipitação acumulada diária.

Unidade: mm, provável; confirmar no sensor. Temporalidade: Janela exata, fechamento e reinicialização do contador precisam de confirmação.

Origem e tratamento: Copiado da estação; não é somado ao longo dos horários pelo notebook. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: min é indicação temporal provável, não comprovação de precipitação mínima.

Referências: NREL.

## Vento

### dir_vento

Direção do vento, leitura principal.

Unidade: graus, nominal. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Orientação/referência, unidade e calibração. Direções constantes em 360 exigem verificação; não demonstram vento sempre ao norte.

Observação no arquivo: Campo constante entre os valores presentes: 360.0. Todos os valores presentes são 360 neste arquivo; a causa não é determinada.

Referências: NREL.

### air_speed_max

Velocidade máxima do vento.

Unidade: m/s, provável; confirmar. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Não confundir a velocidade principal com estatísticas; valores negativos precisam de inspeção.

Referências: NREL.

### vel_vento

Velocidade do vento, leitura principal.

Unidade: m/s, provável; confirmar. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Não confundir a velocidade principal com estatísticas; valores negativos precisam de inspeção.

Referências: NREL.

### dir_vento_med

Direção média do vento.

Unidade: graus, nominal. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Orientação/referência, unidade e calibração. Direções constantes em 360 exigem verificação; não demonstram vento sempre ao norte.

Observação no arquivo: Campo constante entre os valores presentes: 360.0. Todos os valores presentes são 360 neste arquivo; a causa não é determinada.

Referências: NREL.

### air_speed_med

Velocidade média do vento.

Unidade: m/s, provável; confirmar. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Não confundir a velocidade principal com estatísticas; valores negativos precisam de inspeção.

Referências: NREL.

### air_speed_min

Velocidade mínima do vento.

Unidade: m/s, provável; confirmar. Temporalidade: Janela original não documentada; média de direção pode exigir tratamento circular.

Origem e tratamento: Copiado da estação, sem recomputar médias ou extremos. Fundamento: Convenção meteorológica e nome do campo.

Confirmação pendente: Não confundir a velocidade principal com estatísticas; valores negativos precisam de inspeção.

Referências: NREL.

## Temperatura

### air_temperature_med

Temperatura média do ar.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### temperatura_ambiente

Temperatura ambiente, leitura principal.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### air_temperature_min

Temperatura mínima do ar.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### temperatura_painel

Temperatura do painel fotovoltaico, leitura principal.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### pv_temperatura_med

Temperatura média dos módulos fotovoltaicos.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### air_temperature_max

Temperatura máxima do ar.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### pv_temperatura_max

Temperatura máxima dos módulos fotovoltaicos.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

### pv_temperatura_min

Temperatura mínima dos módulos fotovoltaicos.

Unidade: °C, interpretação nominal. Temporalidade: Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos.

Origem e tratamento: Copiado da estação sem agregação temporal adicional. Fundamento: Nome, faixa de valores observada e convenção física.

Confirmação pendente: Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula.

Referências: SANDIA_RTC.

## Alimentação da estação

### tensao_bateria

Tensão da bateria ou da alimentação monitorada pela estação.

Unidade: V, provável; confirmar. Temporalidade: Leitura registrada pela estação.

Origem e tratamento: Copiado da estação; não é tensão dos inversores ou dos módulos. Fundamento: Nome do campo e faixa observada.

Confirmação pendente: Confirmar circuito e escala; há valores em faixas diferentes no arquivo.

Referências: código do notebook e esquema local.

## Diagnóstico da estação

### fail_read

Indicador original de falha de leitura, pelo nome do campo.

Unidade: booleano/código. Temporalidade: Associado ao registro da estação.

Origem e tratamento: Copiado sem alteração; NaN quando não há estação. Fundamento: Interpretação pelo nome; distribuição dos valores verificada no arquivo.

Confirmação pendente: Confirmar codificação com o fornecedor; False não comprova calibração ou qualidade física.

Observação no arquivo: Campo constante entre os valores presentes: False.

Referências: código do notebook e esquema local.

## Indicadores de disponibilidade

### tem_registro_estacao

Indica que existe uma linha da estação selecionada naquele intervalo.

Unidade: booleano. Temporalidade: Calculado separadamente para cada intervalo de cinco minutos.

Origem e tratamento: Criado pelo notebook; ausência da fonte vira False ou zero apenas nestes indicadores. Fundamento: Confirmado pelo código de data.ipynb.

Confirmação pendente: Não exige que todos os canais físicos estejam preenchidos; True não significa leitura validada.

Referências: código do notebook e esquema local.

### n_inversores

Quantidade de identificadores distintos de inversor com alguma medição útil após deduplicação.

Unidade: contagem de 0 a 8. Temporalidade: Calculado separadamente para cada intervalo de cinco minutos.

Origem e tratamento: Criado pelo notebook; ausência da fonte vira False ou zero apenas nestes indicadores. Fundamento: Confirmado pelo código de data.ipynb.

Confirmação pendente: Não exige que a potência ou todos os contadores estejam preenchidos.

Referências: código do notebook e esquema local.

### n_inversores_potencia

Quantidade de inversores com potência AC não ausente naquele intervalo.

Unidade: contagem de 0 a 8. Temporalidade: Calculado separadamente para cada intervalo de cinco minutos.

Origem e tratamento: Criado pelo notebook; ausência da fonte vira False ou zero apenas nestes indicadores. Fundamento: Confirmado pelo código de data.ipynb.

Confirmação pendente: Oito indica soma com os oito equipamentos; de um a sete indica potência parcial; zero não indica geração nula.

Referências: código do notebook e esquema local.

### tem_registro_inversores

Indica que existe um grupo de inversores com pelo menos uma das cinco medições úteis naquele intervalo.

Unidade: booleano. Temporalidade: Calculado separadamente para cada intervalo de cinco minutos.

Origem e tratamento: Criado pelo notebook; ausência da fonte vira False ou zero apenas nestes indicadores. Fundamento: Confirmado pelo código de data.ipynb.

Confirmação pendente: Grupos sem todas as cinco medições são descartados antes deste indicador; não equivale à existência de qualquer linha bruta.

Referências: código do notebook e esquema local.

## Potência e energia dos inversores

### daily_power_yields_kwh

Energia elétrica do contador diário, somada entre os inversores disponíveis.

Unidade: kWh. Temporalidade: Estado do contador diário registrado no horário; não é energia dos cinco minutos.

Origem e tratamento: Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1. Fundamento: Agregação confirmada pelo código; unidade indicada pelo nome original.

Confirmação pendente: A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa.

Referências: PANDAS.

### monthly_power_yields_kwh

Energia elétrica do contador mensal, somada entre os inversores disponíveis.

Unidade: kWh. Temporalidade: Estado do contador mensal registrado no horário; não somar novamente ao longo dos horários.

Origem e tratamento: Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1. Fundamento: Agregação confirmada pelo código; unidade indicada pelo nome original.

Confirmação pendente: A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa.

Referências: PANDAS.

### total_power_yields_kwh

Energia elétrica acumulada dos contadores totais dos inversores disponíveis.

Unidade: kWh. Temporalidade: Estado dos contadores acumulados; horizonte e reinicializações dependem do equipamento.

Origem e tratamento: Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1. Fundamento: Agregação confirmada pelo código; unidade indicada pelo nome original.

Confirmação pendente: A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa.

Referências: PANDAS.

### total_active_power_w

Potência ativa AC agregada dos inversores disponíveis.

Unidade: W. Temporalidade: Leitura de potência no horário; não é energia.

Origem e tratamento: Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1. Fundamento: Agregação confirmada pelo código; unidade indicada pelo nome original.

Confirmação pendente: A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa.

Referências: PANDAS.

### total_dc_power_w

Potência DC agregada dos inversores disponíveis.

Unidade: W. Temporalidade: Leitura de potência em corrente contínua no horário.

Origem e tratamento: Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1. Fundamento: Agregação confirmada pelo código; unidade indicada pelo nome original.

Confirmação pendente: A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa.

Referências: PANDAS.

## Colunas auxiliares

* `meta.id_inversor`: Identificador do inversor usado na deduplicação e na contagem de equipamentos. Não é exportado no CSV agregado.
* `data_5min`: datetime original em UTC associado ao início do intervalo por floor de cinco minutos. Renomeado para datetime na consolidação.
* `_validos`: Contagem para priorizar duplicatas: na estação conta todas as colunas preenchidas; nos inversores somente as cinco medições selecionadas. Não é exportado; não representa uma validação física.

## Referências técnicas

* NREL: [Guia de dados de albedo: definições de GHI, GRI, vento e precipitação](https://datahub.duramat.org/dataset/d1c1fc62-eb76-477e-a07b-6bb0dc8e813c/resource/6206db10-c5b4-4635-a870-ec23efd1c181/download/users-guide-for-albedo-data-sets-rev3.pdf).
* SANDIA: [Sandia PVPMC: irradiância no plano dos módulos (POA)](https://pvpmc.sandia.gov/modeling-guide/1-weather-design-inputs/plane-of-array-poa-irradiance/).
* SANDIA_RTC: [Sandia: instrumentação meteorológica e temperatura dos módulos](https://rtc.sandia.gov/technical-capabilities/).
* PVSYST: [PVsyst: irradiância em W/m² e irradiação em kWh/m²](https://www.pvsyst.com/help-pvsyst7/models_meteo_incidentmodels.htm).
* ALBEDO: [Kipp & Zonen: definições de albedo e irradiância](https://www.kippzonen.com/Download/64/Manual-Albedometers-English).
* PANDAS: [Pandas: soma por grupo e parâmetro min_count](https://pandas.pydata.org/pandas-docs/version/2.0/reference/api/pandas.core.groupby.DataFrameGroupBy.sum.html).
