"""Dicionário investigado da base Leopoldo: código, fontes técnicas e evidência local."""
from pathlib import Path

import numpy as np
import pandas as pd

from .dicionario_colunas import significado

REFERENCIAS = {
    'NREL': ('Guia de dados de albedo: definições de GHI, GRI, vento e precipitação',
        'https://datahub.duramat.org/dataset/d1c1fc62-eb76-477e-a07b-6bb0dc8e813c/resource/6206db10-c5b4-4635-a870-ec23efd1c181/download/users-guide-for-albedo-data-sets-rev3.pdf'),
    'SANDIA': ('Sandia PVPMC: irradiância no plano dos módulos (POA)',
        'https://pvpmc.sandia.gov/modeling-guide/1-weather-design-inputs/plane-of-array-poa-irradiance/'),
    'SANDIA_RTC': ('Sandia: instrumentação meteorológica e temperatura dos módulos',
        'https://rtc.sandia.gov/technical-capabilities/'),
    'PVSYST': ('PVsyst: irradiância em W/m² e irradiação em kWh/m²',
        'https://www.pvsyst.com/help-pvsyst7/models_meteo_incidentmodels.htm'),
    'ALBEDO': ('Kipp & Zonen: definições de albedo e irradiância',
        'https://www.kippzonen.com/Download/64/Manual-Albedometers-English'),
    'PANDAS': ('Pandas: soma por grupo e parâmetro min_count',
        'https://pandas.pydata.org/pandas-docs/version/2.0/reference/api/pandas.core.groupby.DataFrameGroupBy.sum.html'),
}


def descrever_coluna(coluna):
    """Descreve o significado sem presumir o manual do sensor ou do fornecedor."""
    def item(grupo, descricao, unidade, temporal, tratamento, evidencia, pendencia='', fontes=''):
        return dict(coluna=coluna,grupo=grupo,significado_pt=descricao,unidade=unidade,
            interpretacao_temporal=temporal,origem_tratamento=tratamento,
            fundamento=evidencia,confirmacao_pendente=pendencia,referencias=fontes)
    if coluna=='datetime':
        return item('Tempo e identificação','Início do intervalo de cinco minutos usado como chave do merge',
            'data/hora UTC','UTC no CSV; a grade de 2025 é construída no fuso America/Sao_Paulo e convertida para UTC',
            'Gerado pela grade; horários das fontes são associados por floor de cinco minutos',
            'Confirmado pelo código de data.ipynb')
    if coluna=='usine_code':
        return item('Tempo e identificação','Código da usina selecionada: 07-07FX','identificador',
            'Constante em todos os intervalos da grade','Preenchido pela configuração USINA, mesmo sem medições',
            'Confirmado pelo código de data.ipynb')
    ids={'meta.id':'Identificador interno do equipamento/registro de estação nos metadados',
         'meta.id_usina':'Identificador interno da usina nos metadados da estação',
         'meta.solar_station_id':'Identificador interno da estação solarimétrica',
         '_id':'Identificador do registro original selecionado da estação',
         'equipment_name':'Nome do equipamento da estação; neste arquivo, est_sols1'}
    if coluna in ids:
        return item('Tempo e identificação',ids[coluna],'identificador',
            'Atributo do registro da estação, não uma medição temporal',
            'Copiado da estação selecionada; não identifica um inversor nem o agregado da usina',
            'Origem confirmada pelo código; interpretação nominal pelo esquema',
            'Esquema dos identificadores do fornecedor; NaN sem estação é esperado')
    if coluna=='real_datetime':
        return item('Tempo e identificação','Horário adicional fornecido pela estação, preservado no formato original',
            'data/hora; valores observados em UTC','Não é a chave de cinco minutos; pode diferir de datetime',
            'Copiado do registro original da estação','Nome e formato observados no CSV',
            'Confirmar se representa aquisição, relógio do equipamento, transmissão ou recepção')
    eletricas={
        'total_active_power_w':('Potência ativa AC agregada dos inversores disponíveis','W','Leitura de potência no horário; não é energia'),
        'total_dc_power_w':('Potência DC agregada dos inversores disponíveis','W','Leitura de potência em corrente contínua no horário'),
        'daily_power_yields_kwh':('Energia elétrica do contador diário, somada entre os inversores disponíveis','kWh','Estado do contador diário registrado no horário; não é energia dos cinco minutos'),
        'monthly_power_yields_kwh':('Energia elétrica do contador mensal, somada entre os inversores disponíveis','kWh','Estado do contador mensal registrado no horário; não somar novamente ao longo dos horários'),
        'total_power_yields_kwh':('Energia elétrica acumulada dos contadores totais dos inversores disponíveis','kWh','Estado dos contadores acumulados; horizonte e reinicializações dependem do equipamento'),
    }
    if coluna in eletricas:
        desc,unidade,temporal=eletricas[coluna]
        return item('Potência e energia dos inversores',desc,unidade,temporal,
            'Uma leitura por inversor e intervalo, priorizando preenchimento e horário mais recente; soma com min_count=1',
            'Agregação confirmada pelo código; unidade indicada pelo nome original',
            'A soma pode ser parcial; n_inversores_potencia conta contribuintes da potência AC, não de cada contador. Validação física dos contadores é outra etapa',
            'PANDAS')
    indicadores={
        'tem_registro_estacao':('Indica que existe uma linha da estação selecionada naquele intervalo',
            'Não exige que todos os canais físicos estejam preenchidos; True não significa leitura validada'),
        'tem_registro_inversores':('Indica que existe um grupo de inversores com pelo menos uma das cinco medições úteis naquele intervalo',
            'Grupos sem todas as cinco medições são descartados antes deste indicador; não equivale à existência de qualquer linha bruta'),
        'n_inversores':('Quantidade de identificadores distintos de inversor com alguma medição útil após deduplicação',
            'Não exige que a potência ou todos os contadores estejam preenchidos'),
        'n_inversores_potencia':('Quantidade de inversores com potência AC não ausente naquele intervalo',
            'Oito indica soma com os oito equipamentos; de um a sete indica potência parcial; zero não indica geração nula'),
    }
    if coluna in indicadores:
        desc,obs=indicadores[coluna]
        return item('Indicadores de disponibilidade',desc,'booleano' if coluna.startswith('tem_') else 'contagem de 0 a 8',
            'Calculado separadamente para cada intervalo de cinco minutos',
            'Criado pelo notebook; ausência da fonte vira False ou zero apenas nestes indicadores',
            'Confirmado pelo código de data.ipynb',obs)
    if coluna=='fail_read':
        return item('Diagnóstico da estação','Indicador original de falha de leitura, pelo nome do campo','booleano/código',
            'Associado ao registro da estação','Copiado sem alteração; NaN quando não há estação',
            'Interpretação pelo nome; distribuição dos valores verificada no arquivo',
            'Confirmar codificação com o fornecedor; False não comprova calibração ou qualidade física')
    if coluna.startswith(('ghi_','poa_','gri_')):
        partes=coluna.split('_');prefixo=partes[0]
        planos={'ghi':'global horizontal (GHI)', 'poa':'no plano dos módulos (POA)',
                'gri':'refletida pelo solo (GRI, acepção técnica usual; canal local a confirmar)'}
        plano=planos[prefixo]
        fonte='NREL; PVSYST' if prefixo!='poa' else 'SANDIA; PVSYST'
        if partes[1]=='kwh':
            periodo=partes[2]
            descricao={'min':'Irradiação associada a um minuto', 'hour':'Irradiação horária',
                       'day':'Irradiação diária', 'acc':'Irradiação acumulada'}[periodo]+' '+plano
            temporal={'min':'Forte evidência numérica de intervalo de um minuto; não equivale aos cinco minutos da grade',
                      'hour':'Não confirmado se hora corrente, hora encerrada ou janela móvel',
                      'day':'Valor rotulado diário; pode estar repetido em vários horários; disponibilidade e instante de fechamento não confirmados',
                      'acc':'Período de acumulação e regras de reinicialização não documentados'}[periodo]
            pendencia='Unidade e janela de integração do fornecedor; não confundir com energia elétrica em kWh'
            if partes[-1]=='est':
                descricao+='; variante com sufixo est'
                pendencia+='; est não tem definição documentada e não deve ser apresentado automaticamente como previsão ou estimativa independente'
            return item('Radiação solar',descricao,'kWh/m², interpretação nominal a confirmar',temporal,
                'Valor copiado da estação; não é integrado nem somado pelo notebook',
                'Conceito físico documentado; nome e relações numéricas locais',pendencia,fonte)
        estatistica={'med':'média','min':'mínima','max':'máxima'}
        if partes[1]=='irr':
            descricao='Irradiância '+estatistica[partes[2]]+' '+plano
            temporal='Estatística da janela original do sensor; a janela não é comprovadamente de cinco minutos'
        else:
            descricao='Leitura de irradiância '+plano
            temporal='Leitura principal do canal; resposta e agregação temporal do sensor não documentadas'
        return item('Radiação solar',descricao,'W/m², nominal; escala local a confirmar',temporal,
            'Copiado do registro da estação escolhido pelo notebook; não representa soma de energia',
            'Conceito técnico documentado; associação ao campo inferida do nome',
            'Modelo do sensor, plano/orientação, calibração e escala; não aplicar fator de correção sem documentação',fonte)
    if coluna.startswith('indice_albedo_') or coluna in {'albedo_tracker','calculo_albedo_medio'}:
        nomes={'albedo_tracker':'Albedo rotulado como tracker: razão de radiação refletida e incidente, segundo a nomenclatura',
               'indice_albedo_tracker':'Índice de albedo rotulado como tracker, com escala aproximadamente percentual nos valores observados',
               'calculo_albedo_medio':'Campo de cálculo do albedo médio, pelo nome original',
               'indice_albedo_medio':'Índice de albedo médio, pelo nome do campo',
               'indice_albedo_maximo':'Índice de albedo máximo, pelo nome do campo',
               'indice_albedo_minimo':'Índice de albedo mínimo, pelo nome do campo'}
        unidade=('razão adimensional, nominal' if coluna=='albedo_tracker' else
                 '% sugerido pelos dados; confirmar' if coluna=='indice_albedo_tracker' else 'não confirmada: razão ou %')
        return item('Albedo',nomes[coluna],unidade,'Janela da estatística e método de cálculo não documentados',
            'Copiado da estação; o notebook não calcula albedo',
            'Conceito documentado; mapeamento local pelo nome e evidência numérica',
            'Confirmar fórmula e sensores; tracker no nome não comprova que a usina tenha rastreamento. Índices vazios não permitem confirmar a escala',
            'NREL; ALBEDO')
    if coluna.startswith('precipitacao_acc'):
        periodo=coluna.removeprefix('precipitacao_acc').strip('_')
        desc={'':'Precipitação acumulada, com período de acumulação não documentado',
              'min':'Precipitação acumulada associada ao minuto, interpretação pelo nome',
              'hour':'Precipitação acumulada horária', 'day':'Precipitação acumulada diária'}[periodo]
        return item('Precipitação',desc,'mm, provável; confirmar no sensor',
            'Janela exata, fechamento e reinicialização do contador precisam de confirmação',
            'Copiado da estação; não é somado ao longo dos horários pelo notebook',
            'Convenção meteorológica e nome do campo','min é indicação temporal provável, não comprovação de precipitação mínima','NREL')
    if coluna in {'dir_vento','dir_vento_med'} or coluna=='vel_vento' or coluna.startswith('air_speed_'):
        desc={'dir_vento':'Direção do vento, leitura principal', 'dir_vento_med':'Direção média do vento',
              'vel_vento':'Velocidade do vento, leitura principal', 'air_speed_min':'Velocidade mínima do vento',
              'air_speed_med':'Velocidade média do vento', 'air_speed_max':'Velocidade máxima do vento'}[coluna]
        return item('Vento',desc,'graus, nominal' if coluna.startswith('dir_') else 'm/s, provável; confirmar',
            'Janela original não documentada; média de direção pode exigir tratamento circular',
            'Copiado da estação, sem recomputar médias ou extremos',
            'Convenção meteorológica e nome do campo',
            'Orientação/referência, unidade e calibração. Direções constantes em 360 exigem verificação; não demonstram vento sempre ao norte' if coluna.startswith('dir_') else 'Não confundir a velocidade principal com estatísticas; valores negativos precisam de inspeção',
            'NREL')
    if coluna.startswith(('air_temperature_','pv_temperatura_')) or coluna in {'temperatura_ambiente','temperatura_painel'}:
        nomes={'air_temperature_min':'Temperatura mínima do ar','air_temperature_med':'Temperatura média do ar',
               'air_temperature_max':'Temperatura máxima do ar','temperatura_ambiente':'Temperatura ambiente, leitura principal',
               'temperatura_painel':'Temperatura do painel fotovoltaico, leitura principal',
               'pv_temperatura_min':'Temperatura mínima dos módulos fotovoltaicos',
               'pv_temperatura_med':'Temperatura média dos módulos fotovoltaicos',
               'pv_temperatura_max':'Temperatura máxima dos módulos fotovoltaicos'}
        return item('Temperatura',nomes[coluna],'°C, interpretação nominal',
            'Janela de mínimos, máximos e médias não documentada; não presumir agregação de cinco minutos',
            'Copiado da estação sem agregação temporal adicional','Nome, faixa de valores observada e convenção física',
            'Sensor, calibração e posição de medição; temperatura de módulo não é necessariamente temperatura de célula','SANDIA_RTC')
    if coluna=='tensao_bateria':
        return item('Alimentação da estação','Tensão da bateria ou da alimentação monitorada pela estação','V, provável; confirmar',
            'Leitura registrada pela estação','Copiado da estação; não é tensão dos inversores ou dos módulos',
            'Nome do campo e faixa observada','Confirmar circuito e escala; há valores em faixas diferentes no arquivo')
    raise ValueError(f'Coluna sem descrição investigada: {coluna}')


def investigar_e_exportar(dados, pasta):
    """Gera as 73 explicações e comprovações numéricas, sem modificar dados."""
    pasta=Path(pasta);pasta.mkdir(parents=True,exist_ok=True)
    linhas=[]
    for c in dados:
        registro=descrever_coluna(c);obs=dados[c].dropna()
        registro.update(preenchidos=len(obs),cobertura_grade_pct=100*dados[c].notna().mean(),
                        valores_distintos=int(obs.nunique()),exemplo=str(obs.iloc[0]) if len(obs) else '(sem valores)')
        registro['observacoes_dados']=''
        if obs.empty:registro['observacoes_dados']='Coluna totalmente vazia; significado e unidade específicos não podem ser validados pelos dados.'
        elif obs.nunique()==1:registro['observacoes_dados']=f'Campo constante entre os valores presentes: {obs.iloc[0]}.'
        if c.startswith('dir_vento') and len(obs) and obs.eq(360).all():
            registro['observacoes_dados']+=' Todos os valores presentes são 360 neste arquivo; a causa não é determinada.'
        linhas.append(registro)
    dicionario=pd.DataFrame(linhas)
    comprovacoes=[]
    for prefixo in ['ghi','poa','gri']:
        k=f'{prefixo}_kwh_min';i=f'{prefixo}_irr_med'
        mask=dados[k].notna() & dados[i].notna() & dados[i].abs().gt(10)
        n=int(mask.sum())
        pct=float(100*np.isclose(dados.loc[mask,k]*60000,dados.loc[mask,i],rtol=1e-4,atol=.05).mean()) if n else np.nan
        comprovacoes.append(dict(tipo='Janela de um minuto',campos=f'{k}; {i}',pares=n,
            resultado=f'{pct:.2f}% compatíveis com kWh_min = irradiância média / 60000',
            limite='Filtro |irr_med| > 10; rtol=1e-4, atol=0,05 W/m²; evidência numérica, não calibração.'))
        dias=pd.to_datetime(dados.datetime,utc=True).dt.tz_convert('America/Sao_Paulo').dt.normalize()
        por_dia=dados[f'{prefixo}_kwh_day'].groupby(dias).nunique()
        por_dia=por_dia[por_dia.gt(0)]
        comprovacoes.append(dict(tipo='Temporalidade diária',campos=f'{prefixo}_kwh_day',pares=len(por_dia),
            resultado=f'{int(por_dia.eq(1).sum())} dias têm um único valor diário repetido; {int(por_dia.gt(1).sum())} têm mais de um',
            limite='Valor repetido não comprova que o total estava disponível naquele horário; fechamento e fuso do contador precisam de confirmação.'))
        for periodo in ['day','acc']:
            original=f'{prefixo}_kwh_{periodo}';variante=original+'_est'
            mask=dados[original].notna() & dados[variante].notna();n=int(mask.sum())
            pct=float(100*np.isclose(dados.loc[mask,original],dados.loc[mask,variante]).mean()) if n else np.nan
            comprovacoes.append(dict(tipo='Variante est',campos=f'{original}; {variante}',pares=n,
                resultado=f'{pct:.2f}% de pares numericamente iguais',
                limite='Igualdade neste arquivo não documenta o significado de est nem demonstra previsão independente.'))
            dicionario.loc[dicionario.coluna.eq(variante),'observacoes_dados']=f'{n} pares disponíveis; {pct:.2f}% iguais à coluna sem est (np.isclose padrão).'
    mask=dados.albedo_tracker.notna() & dados.indice_albedo_tracker.notna()
    delta=(dados.loc[mask,'indice_albedo_tracker']-100*dados.loc[mask,'albedo_tracker']).abs()
    comprovacoes.append(dict(tipo='Escala do albedo',campos='albedo_tracker; indice_albedo_tracker',pares=int(mask.sum()),
        resultado=f'Maior diferença em relação a 100 × albedo_tracker: {delta.max():.6f}',
        limite='Escala percentual sugerida; igualdade exata e fórmula não confirmadas.'))
    evidencia=pd.DataFrame(comprovacoes)
    auxiliares=pd.DataFrame([
        dict(coluna='meta.id_inversor',significado_pt='Identificador do inversor usado na deduplicação e na contagem de equipamentos',origem='CSV original dos inversores',destino='Não é exportado no CSV agregado'),
        dict(coluna='data_5min',significado_pt='datetime original em UTC associado ao início do intervalo por floor de cinco minutos',origem='Criado em ambas as fontes',destino='Renomeado para datetime na consolidação'),
        dict(coluna='_validos',significado_pt='Contagem para priorizar duplicatas: na estação conta todas as colunas preenchidas; nos inversores somente as cinco medições selecionadas',origem='Criado pelo notebook',destino='Não é exportado; não representa uma validação física'),
    ])
    dicionario.to_csv(pasta/'dicionario_colunas.csv',index=False,encoding='utf-8-sig')
    auxiliares.to_csv(pasta/'colunas_auxiliares.csv',index=False,encoding='utf-8-sig')
    evidencia.to_csv(pasta/'evidencias_numericas.csv',index=False,encoding='utf-8-sig')
    texto=('# Dicionário investigado das colunas da base Leopoldo\n\n'
           'As definições combinam o código de data.ipynb, nomes originais, evidências numéricas e referências técnicas gerais. '
           'Não foi identificado um manual do fornecedor com esses nomes de campo. Fontes gerais confirmam os conceitos, não o mapeamento ou a calibração dos sensores locais.\n\n'
           'Potência elétrica é dada em W; energia elétrica em kWh. Irradiância solar é potência por área (W/m²); irradiação é energia por área (kWh/m²). '
           'A grade de cinco minutos não transforma a janela original de cada sensor em cinco minutos. Nos campos *_kwh_min, os dados sustentam a interpretação de um minuto, em contraste com *_irr_min (mínimo).\n\n')
    for grupo in dicionario.grupo.unique():
        texto+=f'## {grupo}\n\n'
        for _,r in dicionario.loc[dicionario.grupo.eq(grupo)].iterrows():
            texto+=(f"### {r.coluna}\n\n{r.significado_pt}.\n\n"
                    f"Unidade: {r.unidade}. Temporalidade: {r.interpretacao_temporal}.\n\n"
                    f"Origem e tratamento: {r.origem_tratamento}. Fundamento: {r.fundamento}.\n\n")
            if r.confirmacao_pendente:texto+=f'Confirmação pendente: {r.confirmacao_pendente}.\n\n'
            if r.observacoes_dados:texto+=f'Observação no arquivo: {r.observacoes_dados}\n\n'
            texto+=f'Referências: {r.referencias or "código do notebook e esquema local"}.\n\n'
    texto+='## Colunas auxiliares\n\n'
    for _,r in auxiliares.iterrows():texto+=f'* `{r.coluna}`: {r.significado_pt}. {r.destino}.\n'
    texto+='\n## Referências técnicas\n\n'
    for sigla,(titulo,url) in REFERENCIAS.items():texto+=f'* {sigla}: [{titulo}]({url}).\n'
    (pasta/'dicionario_colunas.md').write_text(texto,encoding='utf-8')
    return dict(dicionario=dicionario,auxiliares=auxiliares,evidencias=evidencia,pasta=pasta)
