# Colunas e cobertura dos dados originais

Significados interpretados a partir dos nomes dos campos e do protocolo local; unidades, códigos e canais marcados como pendentes exigem documentação do fornecedor. Não se corrigem valores nem se imputam registros.

Cobertura nas linhas: campos não vazios / linhas selecionadas, incluindo duplicatas. Cobertura temporal: intervalos de cinco minutos por equipamento com valor numérico finito (ou campo não vazio para metadados), divididos por todos os intervalos esperados no calendário. Duplicatas contam uma vez por intervalo; zeros e valores negativos finitos são presentes, sem garantir validade física. Austrália: arquivo integral, de 25/07/2013 a 23/08/2025. Brasil: código 07-07FX, calendário local completo de 2025; denominador de linhas inclui todas as linhas desse código. Bordas também entram no denominador temporal.

## Austrália

| Coluna original | Significado em português | Unidade | Campos preenchidos (%) | Cobertura temporal (%) |
|---|---|---|---:|---:|
| `timestamp` | Data e hora da medição na convenção temporal australiana | data/hora | 100.00 | 98.86 |
| `Active_Energy_Delivered_Received` | Energia ativa entregue/recebida; convenção e caráter acumulativo a confirmar | a confirmar | 97.86 | 96.74 |
| `Current_Phase_Average` | Corrente média das fases | A, a confirmar | 97.86 | 96.75 |
| `Active_Power` | Potência ativa do sistema fotovoltaico australiano | kW | 97.86 | 96.75 |
| `Wind_Speed` | Velocidade do vento | a confirmar | 27.13 | 26.82 |
| `Weather_Temperature_Celsius` | Temperatura meteorológica | °C | 97.42 | 96.31 |
| `Weather_Relative_Humidity` | Umidade relativa do ar | % | 97.42 | 96.31 |
| `Global_Horizontal_Radiation` | Irradiância global horizontal (GHI) | W/m² | 97.43 | 96.31 |
| `Diffuse_Horizontal_Radiation` | Irradiância difusa horizontal | W/m², a confirmar | 97.43 | 96.31 |
| `Wind_Direction` | Direção do vento | graus, a confirmar | 97.43 | 96.32 |
| `Weather_Daily_Rainfall` | Precipitação diária | mm, a confirmar | 97.43 | 96.32 |
| `Radiation_Global_Tilted` | Irradiância global no plano inclinado | W/m², a confirmar | 88.03 | 87.03 |
| `Radiation_Diffuse_Tilted` | Irradiância difusa no plano inclinado | W/m², a confirmar | 91.39 | 90.34 |

## Brasil: inversores

| Coluna original | Significado em português | Unidade | Campos preenchidos (%) | Cobertura temporal (%) |
|---|---|---|---:|---:|
| `datetime` | Data e hora de referência do registro, em UTC no arquivo | data/hora | 100.00 | 80.95 |
| `meta.id` | Identificador interno nos metadados | identificador | 100.00 | 80.95 |
| `meta.id_inversor` | Identificador do inversor nos metadados | identificador | 100.00 | 80.95 |
| `meta.id_usina` | Identificador da usina nos metadados | identificador | 100.00 | 80.95 |
| `mppt_voltage_v[0]` | Tensão no canal MPPT de índice 0 | V | 98.06 | 79.40 |
| `mppt_voltage_v[1]` | Tensão no canal MPPT de índice 1 | V | 98.06 | 79.40 |
| `mppt_voltage_v[2]` | Tensão no canal MPPT de índice 2 | V | 98.06 | 79.40 |
| `mppt_voltage_v[3]` | Tensão no canal MPPT de índice 3 | V | 98.06 | 79.40 |
| `mppt_voltage_v[4]` | Tensão no canal MPPT de índice 4 | V | 98.06 | 79.40 |
| `mppt_voltage_v[5]` | Tensão no canal MPPT de índice 5 | V | 98.06 | 79.40 |
| `mppt_voltage_v[6]` | Tensão no canal MPPT de índice 6 | V | 98.06 | 79.40 |
| `mppt_voltage_v[7]` | Tensão no canal MPPT de índice 7 | V | 98.06 | 79.40 |
| `mppt_voltage_v[8]` | Tensão no canal MPPT de índice 8 | V | 98.06 | 79.40 |
| `mppt_voltage_v[9]` | Tensão no canal MPPT de índice 9 | V | 98.06 | 79.40 |
| `mppt_voltage_v[10]` | Tensão no canal MPPT de índice 10 | V | 98.06 | 79.40 |
| `mppt_voltage_v[11]` | Tensão no canal MPPT de índice 11 | V | 98.06 | 79.40 |
| `work_state` | Estado de operação do inversor; codificação e distinção entre campos a confirmar | código | 98.06 | 79.40 |
| `_id` | Identificador interno do registro | identificador | 100.00 | 80.95 |
| `real_datetime` | Data e hora adicional do sistema; relação com aquisição/recepção a confirmar | data/hora | 69.46 | 57.32 |
| `daily_power_yields_kwh` | Energia gerada no dia, indicada pelo contador diário do inversor | kWh | 98.06 | 79.40 |
| `monthly_power_yields_kwh` | Energia gerada no mês, indicada pelo contador mensal | kWh | 98.06 | 79.40 |
| `fault_code` | Código de falha; significado dos códigos a confirmar | código | 98.06 | 79.40 |
| `work_state2` | Estado de operação do inversor; codificação e distinção entre campos a confirmar | código | 98.06 | 79.40 |
| `phase_a_voltage_v` | Tensão da fase A | V | 98.06 | 79.40 |
| `phase_b_voltage_v` | Tensão da fase B | V | 98.06 | 79.40 |
| `phase_c_voltage_v` | Tensão da fase C | V | 98.06 | 79.40 |
| `total_active_power_w` | Potência ativa de saída de cada inversor | W | 98.06 | 79.40 |
| `total_dc_power_w` | Potência total em corrente contínua do inversor | W | 98.06 | 79.40 |
| `total_power_yields_kwh` | Energia acumulada indicada pelo contador total do inversor | kWh | 98.06 | 79.40 |
| `usine_code` | Código da usina | identificador | 100.00 | 80.95 |
| `work_state3` | Estado de operação do inversor; codificação e distinção entre campos a confirmar | código | 98.06 | 79.40 |
| `grid_frequency_hz` | Frequência da rede elétrica | Hz | 98.06 | 79.40 |
| `phase_b_current_a` | Corrente da fase B | A | 98.06 | 79.40 |
| `power_factor` | Fator de potência do inversor | adimensional | 98.06 | 79.40 |
| `internal_temparature_celsius` | Temperatura interna do inversor | °C | 98.06 | 79.40 |
| `total_reactive_power_var` | Potência reativa total do inversor | var | 98.06 | 79.40 |
| `equipment_name` | Nome ou identificador do equipamento | identificador | 100.00 | 80.95 |
| `serial_number` | Número de série do equipamento | identificador | 98.03 | 79.38 |
| `phase_a_current_a` | Corrente da fase A | A | 98.06 | 79.40 |
| `phase_c_current_a` | Corrente da fase C | A | 98.06 | 79.40 |
| `mppt_current_a[0]` | Corrente no canal MPPT de índice 0 | A | 98.06 | 79.40 |
| `mppt_current_a[1]` | Corrente no canal MPPT de índice 1 | A | 98.06 | 79.40 |
| `mppt_current_a[2]` | Corrente no canal MPPT de índice 2 | A | 98.06 | 79.40 |
| `mppt_current_a[3]` | Corrente no canal MPPT de índice 3 | A | 98.06 | 79.40 |
| `mppt_current_a[4]` | Corrente no canal MPPT de índice 4 | A | 98.06 | 79.40 |
| `mppt_current_a[5]` | Corrente no canal MPPT de índice 5 | A | 98.06 | 79.40 |
| `mppt_current_a[6]` | Corrente no canal MPPT de índice 6 | A | 98.06 | 79.40 |
| `mppt_current_a[7]` | Corrente no canal MPPT de índice 7 | A | 98.06 | 79.40 |
| `mppt_current_a[8]` | Corrente no canal MPPT de índice 8 | A | 98.06 | 79.40 |
| `mppt_current_a[9]` | Corrente no canal MPPT de índice 9 | A | 98.06 | 79.40 |
| `mppt_current_a[10]` | Corrente no canal MPPT de índice 10 | A | 98.06 | 79.40 |
| `mppt_current_a[11]` | Corrente no canal MPPT de índice 11 | A | 98.06 | 79.40 |

## Brasil: estação

| Coluna original | Significado em português | Unidade | Campos preenchidos (%) | Cobertura temporal (%) |
|---|---|---|---:|---:|
| `datetime` | Data e hora de referência do registro, em UTC no arquivo | data/hora | 100.00 | 31.76 |
| `meta.id` | Identificador interno nos metadados | identificador | 100.00 | 31.76 |
| `meta.id_usina` | Identificador da usina nos metadados | identificador | 100.00 | 31.76 |
| `meta.solar_station_id` | Identificador da estação solar nos metadados | identificador | 95.80 | 31.70 |
| `indice_albedo_medio` | Índice de albedo medio | adimensional, a confirmar | 0.00 | 0.00 |
| `gri_kwh_day_est` | Irradiação do canal GRI (plano/componente a confirmar), diária, estimada | kWh/m², a confirmar | 4.20 | 0.06 |
| `albedo_tracker` | Albedo associado ao rastreador solar | adimensional, a confirmar | 4.20 | 0.06 |
| `gri_irr_med` | Irradiância do canal GRI (plano/componente a confirmar), média | unidade e escala a confirmar | 4.20 | 0.06 |
| `poa_kwh_hour` | Irradiação no plano dos módulos, horária | kWh/m², a confirmar | 100.00 | 31.76 |
| `precipitacao_acc` | Precipitação acumulada | mm, a confirmar | 100.00 | 31.76 |
| `dir_vento` | Direção do vento | graus, a confirmar | 100.00 | 31.76 |
| `poa_irradiancia` | Irradiância no plano dos módulos | unidade e escala a confirmar | 100.00 | 31.76 |
| `poa_irr_med` | Irradiância no plano dos módulos, média | unidade e escala a confirmar | 100.00 | 31.76 |
| `air_speed_max` | Velocidade máxima do vento | a confirmar | 100.00 | 31.76 |
| `air_temperature_med` | Temperatura média do ar | °C, a confirmar | 100.00 | 31.76 |
| `indice_albedo_tracker` | Índice de albedo tracker | adimensional, a confirmar | 4.20 | 0.06 |
| `gri_kwh_acc` | Irradiação do canal GRI (plano/componente a confirmar), acumulada | kWh/m², a confirmar | 4.20 | 0.06 |
| `poa_irr_max` | Irradiância no plano dos módulos, máxima | unidade e escala a confirmar | 100.00 | 31.76 |
| `temperatura_ambiente` | Temperatura ambiente | °C, a confirmar | 100.00 | 31.76 |
| `real_datetime` | Data e hora adicional do sistema; relação com aquisição/recepção a confirmar | data/hora | 95.80 | 31.70 |
| `poa_kwh_min` | Irradiação no plano dos módulos, mínima | kWh/m², a confirmar | 100.00 | 31.76 |
| `tensao_bateria` | Tensão da bateria da estação | V, a confirmar | 100.00 | 31.76 |
| `calculo_albedo_medio` | Campo de cálculo do albedo médio | adimensional, a confirmar | 0.00 | 0.00 |
| `vel_vento` | Velocidade do vento | a confirmar | 100.00 | 31.76 |
| `ghi_irr_max` | Irradiância global horizontal, máxima | unidade e escala a confirmar | 100.00 | 31.76 |
| `air_temperature_min` | Temperatura mínima do ar | °C, a confirmar | 100.00 | 31.76 |
| `ghi_irr_med` | Irradiância global horizontal, média | unidade e escala a confirmar | 100.00 | 31.76 |
| `ghi_irr_min` | Irradiância global horizontal, mínima | unidade e escala a confirmar | 100.00 | 31.76 |
| `ghi_kwh_min` | Irradiação global horizontal, mínima | kWh/m², a confirmar | 100.00 | 31.76 |
| `gri_irradiancia` | Irradiância do canal GRI (plano/componente a confirmar) | unidade e escala a confirmar | 4.20 | 0.06 |
| `temperatura_painel` | Temperatura do painel fotovoltaico | °C, a confirmar | 100.00 | 31.76 |
| `indice_albedo_maximo` | Índice de albedo maximo | adimensional, a confirmar | 0.00 | 0.00 |
| `ghi_kwh_day` | Irradiação global horizontal, diária | kWh/m², a confirmar | 100.00 | 31.76 |
| `gri_irr_min` | Irradiância do canal GRI (plano/componente a confirmar), mínima | unidade e escala a confirmar | 4.20 | 0.06 |
| `ghi_kwh_day_est` | Irradiação global horizontal, diária, estimada | kWh/m², a confirmar | 100.00 | 31.76 |
| `pv_temperatura_med` | Temperatura média do sistema fotovoltaico | °C, a confirmar | 100.00 | 31.76 |
| `poa_irr_min` | Irradiância no plano dos módulos, mínima | unidade e escala a confirmar | 100.00 | 31.76 |
| `ghi_kwh_hour` | Irradiação global horizontal, horária | kWh/m², a confirmar | 100.00 | 31.76 |
| `ghi_irradiancia` | Irradiância global horizontal | unidade e escala a confirmar | 100.00 | 31.76 |
| `dir_vento_med` | Direção média do vento | graus, a confirmar | 100.00 | 31.76 |
| `precipitacao_acc_hour` | Precipitação acumulada, horária | mm, a confirmar | 100.00 | 31.76 |
| `gri_kwh_day` | Irradiação do canal GRI (plano/componente a confirmar), diária | kWh/m², a confirmar | 4.20 | 0.06 |
| `poa_kwh_day_est` | Irradiação no plano dos módulos, diária, estimada | kWh/m², a confirmar | 100.00 | 31.76 |
| `poa_kwh_acc` | Irradiação no plano dos módulos, acumulada | kWh/m², a confirmar | 100.00 | 31.76 |
| `air_temperature_max` | Temperatura máxima do ar | °C, a confirmar | 100.00 | 31.76 |
| `usine_code` | Código da usina | identificador | 100.00 | 31.76 |
| `ghi_kwh_acc` | Irradiação global horizontal, acumulada | kWh/m², a confirmar | 100.00 | 31.76 |
| `precipitacao_acc_min` | Precipitação acumulada, mínima | mm, a confirmar | 100.00 | 31.76 |
| `fail_read` | Indicador de falha de leitura; codificação a confirmar | código | 100.00 | 31.76 |
| `poa_kwh_day` | Irradiação no plano dos módulos, diária | kWh/m², a confirmar | 100.00 | 31.76 |
| `pv_temperatura_max` | Temperatura máxima do sistema fotovoltaico | °C, a confirmar | 100.00 | 31.76 |
| `air_speed_med` | Velocidade média do vento | a confirmar | 100.00 | 31.76 |
| `equipment_name` | Nome ou identificador do equipamento | identificador | 100.00 | 31.76 |
| `indice_albedo_minimo` | Índice de albedo minimo | adimensional, a confirmar | 0.00 | 0.00 |
| `gri_kwh_min` | Irradiação do canal GRI (plano/componente a confirmar), mínima | kWh/m², a confirmar | 4.20 | 0.06 |
| `gri_kwh_hour` | Irradiação do canal GRI (plano/componente a confirmar), horária | kWh/m², a confirmar | 4.20 | 0.06 |
| `pv_temperatura_min` | Temperatura mínima do sistema fotovoltaico | °C, a confirmar | 100.00 | 31.76 |
| `air_speed_min` | Velocidade mínima do vento | a confirmar | 100.00 | 31.76 |
| `precipitacao_acc_day` | Precipitação acumulada, diária | mm, a confirmar | 100.00 | 31.76 |
| `poa_kwh_acc_est` | Irradiação no plano dos módulos, acumulada, estimada | kWh/m², a confirmar | 100.00 | 31.76 |
| `gri_irr_max` | Irradiância do canal GRI (plano/componente a confirmar), máxima | unidade e escala a confirmar | 4.20 | 0.06 |
| `ghi_kwh_acc_est` | Irradiação global horizontal, acumulada, estimada | kWh/m², a confirmar | 100.00 | 31.76 |
| `_id` | Identificador interno do registro | identificador | 100.00 | 31.76 |
| `gri_kwh_acc_est` | Irradiação do canal GRI (plano/componente a confirmar), acumulada, estimada | kWh/m², a confirmar | 4.20 | 0.06 |

## Alvos univariados

* Austrália, `Active_Power`: 1,229,605 de 1,270,944 intervalos com o sistema completo observado (96.75%).
* Brasil: inversores, `total_active_power_w`: 82,787 de 105,120 intervalos com o sistema completo observado (78.75%).

No Brasil, cobertura por inversor não equivale à cobertura da soma simultânea dos oito inversores. Para o protocolo diário, o alvo é derivado dos contadores e não é uma coluna original: 284 de 365 dias foram aprovados (77,81%). Não confundir aprovação diária com presença de telemetria. No experimento australiano até 2023, 3778 de 3812 dias têm potência diária disponível (99,11%); isso não comprova cobertura intradiária integral. O modelo univariado usa somente o histórico do alvo, mesmo quando outras colunas servem à sua reconstrução ou validação.
