"""Significados das colunas originais; unidades pendentes permanecem explicitadas."""
import re

DICIONARIO = {
    'timestamp': ('Data e hora da medição na convenção temporal australiana', 'data/hora'),
    'datetime': ('Data e hora de referência do registro, em UTC no arquivo', 'data/hora'),
    'real_datetime': ('Data e hora adicional do sistema; relação com aquisição/recepção a confirmar', 'data/hora'),
    'Active_Energy_Delivered_Received': ('Energia ativa entregue/recebida; convenção e caráter acumulativo a confirmar', 'a confirmar'),
    'Current_Phase_Average': ('Corrente média das fases', 'A, a confirmar'),
    'Active_Power': ('Potência ativa do sistema fotovoltaico australiano', 'kW'),
    'Wind_Speed': ('Velocidade do vento', 'a confirmar'),
    'Weather_Temperature_Celsius': ('Temperatura meteorológica', '°C'),
    'Weather_Relative_Humidity': ('Umidade relativa do ar', '%'),
    'Global_Horizontal_Radiation': ('Irradiância global horizontal (GHI)', 'W/m²'),
    'Diffuse_Horizontal_Radiation': ('Irradiância difusa horizontal', 'W/m², a confirmar'),
    'Wind_Direction': ('Direção do vento', 'graus, a confirmar'),
    'Weather_Daily_Rainfall': ('Precipitação diária', 'mm, a confirmar'),
    'Radiation_Global_Tilted': ('Irradiância global no plano inclinado', 'W/m², a confirmar'),
    'Radiation_Diffuse_Tilted': ('Irradiância difusa no plano inclinado', 'W/m², a confirmar'),
    'meta.id': ('Identificador interno nos metadados', 'identificador'),
    'meta.id_inversor': ('Identificador do inversor nos metadados', 'identificador'),
    'meta.id_usina': ('Identificador da usina nos metadados', 'identificador'),
    'meta.solar_station_id': ('Identificador da estação solar nos metadados', 'identificador'),
    '_id': ('Identificador interno do registro', 'identificador'),
    'usine_code': ('Código da usina', 'identificador'),
    'equipment_name': ('Nome ou identificador do equipamento', 'identificador'),
    'serial_number': ('Número de série do equipamento', 'identificador'),
    'daily_power_yields_kwh': ('Energia gerada no dia, indicada pelo contador diário do inversor', 'kWh'),
    'monthly_power_yields_kwh': ('Energia gerada no mês, indicada pelo contador mensal', 'kWh'),
    'total_power_yields_kwh': ('Energia acumulada indicada pelo contador total do inversor', 'kWh'),
    'total_active_power_w': ('Potência ativa de saída de cada inversor', 'W'),
    'total_dc_power_w': ('Potência total em corrente contínua do inversor', 'W'),
    'total_reactive_power_var': ('Potência reativa total do inversor', 'var'),
    'grid_frequency_hz': ('Frequência da rede elétrica', 'Hz'),
    'power_factor': ('Fator de potência do inversor', 'adimensional'),
    'internal_temparature_celsius': ('Temperatura interna do inversor', '°C'),
    'fault_code': ('Código de falha; significado dos códigos a confirmar', 'código'),
    'fail_read': ('Indicador de falha de leitura; codificação a confirmar', 'código'),
    'air_temperature_med': ('Temperatura média do ar', '°C, a confirmar'),
    'air_temperature_min': ('Temperatura mínima do ar', '°C, a confirmar'),
    'air_temperature_max': ('Temperatura máxima do ar', '°C, a confirmar'),
    'temperatura_ambiente': ('Temperatura ambiente', '°C, a confirmar'),
    'temperatura_painel': ('Temperatura do painel fotovoltaico', '°C, a confirmar'),
    'tensao_bateria': ('Tensão da bateria da estação', 'V, a confirmar'),
    'dir_vento': ('Direção do vento', 'graus, a confirmar'),
    'dir_vento_med': ('Direção média do vento', 'graus, a confirmar'),
    'vel_vento': ('Velocidade do vento', 'a confirmar'),
    'albedo_tracker': ('Albedo associado ao rastreador solar', 'adimensional, a confirmar'),
    'calculo_albedo_medio': ('Campo de cálculo do albedo médio', 'adimensional, a confirmar'),
}


def significado(coluna):
    if coluna in DICIONARIO:
        return DICIONARIO[coluna]
    m = re.fullmatch(r'mppt_(voltage_v|current_a)\[(\d+)\]', coluna)
    if m:
        return (f'{"Tensão" if m[1] == "voltage_v" else "Corrente"} no canal MPPT de índice {m[2]}',
                'V' if m[1] == 'voltage_v' else 'A')
    m = re.fullmatch(r'phase_([abc])_(voltage_v|current_a)', coluna)
    if m:
        return (f'{"Tensão" if m[2] == "voltage_v" else "Corrente"} da fase {m[1].upper()}',
                'V' if m[2] == 'voltage_v' else 'A')
    if coluna.startswith('work_state'):
        return ('Estado de operação do inversor; codificação e distinção entre campos a confirmar', 'código')
    sufixos = {'med': 'média', 'min': 'mínima', 'max': 'máxima', 'day': 'diária',
               'hour': 'horária', 'acc': 'acumulada', 'est': 'estimada'}
    if coluna.startswith(('ghi_', 'gri_', 'poa_')):
        partes = coluna.split('_')
        plano = {'ghi': 'global horizontal', 'poa': 'no plano dos módulos',
                 'gri': 'do canal GRI (plano/componente a confirmar)'}[partes[0]]
        energia = partes[1] == 'kwh'
        qualificadores = ', '.join('por minuto (janela a confirmar)' if energia and s=='min'
                                  else sufixos.get(s, s) for s in partes[2:])
        return (f'{"Irradiação" if energia else "Irradiância"} {plano}' +
                (f', {qualificadores}' if qualificadores else ''),
                'kWh/m², a confirmar' if energia else 'unidade e escala a confirmar')
    if coluna.startswith('indice_albedo_'):
        return ('Índice de albedo ' + coluna.removeprefix('indice_albedo_').replace('_', ' '),
                'adimensional, a confirmar')
    if coluna.startswith('pv_temperatura_'):
        return ('Temperatura ' + sufixos[coluna.split('_')[-1]] + ' do sistema fotovoltaico', '°C, a confirmar')
    if coluna.startswith('air_speed_'):
        return ('Velocidade ' + sufixos[coluna.split('_')[-1]] + ' do vento', 'a confirmar')
    if coluna.startswith('precipitacao_acc'):
        ultimo=coluna.split('_')[-1]
        periodo='por minuto (janela a confirmar)' if ultimo=='min' else sufixos.get(ultimo,ultimo)
        return ('Precipitação acumulada' + (', ' + periodo if coluna != 'precipitacao_acc' else ''), 'mm, a confirmar')
    raise ValueError(f'Coluna sem descrição: {coluna}')

