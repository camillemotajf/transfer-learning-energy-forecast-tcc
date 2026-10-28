"""Seção 3.2: potência por sistema e canais meteorológicos, após alinhamento."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from .brasil_merge_horarios import COLUNAS_INV, METADADOS_ESTACAO
from .caracterizacao_bases_tcc import extrair_lacunas, MESES
from .chronos_experimentos import sha256
from .dicionario_colunas import significado

EXCLUIR_AU = {'timestamp', 'Active_Energy_Delivered_Received', 'Current_Phase_Average'}
COLUNAS_AUDITORIA_BRASIL = {'tem_registro_estacao','tem_registro_inversores',
                          'n_inversores','n_inversores_potencia'}


def sinalizar_variavel(serie, variavel):
    """A faixa de temperatura do ar não se aplica à temperatura dos módulos."""
    if (variavel == 'Weather_Temperature_Celsius' or variavel.startswith('air_temperature_')
            or variavel == 'temperatura_ambiente'):
        return serie.notna() & ~serie.between(-20,60), 'Temperatura do ar fora de −20 a 60 °C'
    if 'Humidity' in variavel:
        return serie.notna() & ~serie.between(0,100), 'Umidade fora de 0 a 100%'
    return serie.lt(0), 'Valor negativo; inspeção segundo a variável'


def descrever_fonte(valores, registros, fonte, descricoes, unidades):
    """Estatísticas por intervalo, distinguindo ausência de linha e de variável."""
    valores = valores.replace([np.inf, -np.inf], np.nan)
    if not valores.index.is_unique or not valores.index.equals(registros.index):
        raise ValueError('Valores e indicadores devem ter a mesma grade, sem horários duplicados.')
    linhas = []
    for c in valores:
        s = valores[c]; obs = s.dropna(); presente = registros[c].astype(bool)
        if (s.notna() & ~presente).any():
            raise ValueError(f'Valor disponível sem registro de origem: {c}')
        linhas.append(dict(fonte=fonte, variavel=c, significado_pt=descricoes[c], unidade=unidades[c],
            intervalos_esperados=len(s), intervalos_com_registro=int(presente.sum()),
            intervalos_sem_registro=int((~presente).sum()),
            registro_sem_valor_disponivel=int((presente & s.isna()).sum()),
            intervalos_disponiveis=int(s.notna().sum()), cobertura_pct=100*s.notna().mean(),
            preenchimento_nos_intervalos_com_registro_pct=100*s.notna().sum()/presente.sum() if presente.any() else np.nan,
            zeros=int(s.eq(0).sum()), negativos=int(s.lt(0).sum()),
            media=obs.mean(), desvio_padrao=obs.std(), minimo=obs.min(), q25=obs.quantile(.25),
            mediana=obs.median(), q75=obs.quantile(.75), maximo=obs.max()))
    diario = valores.notna().resample('D').sum()
    esperados = valores.iloc[:,0].resample('D').size()
    cobertura = diario.div(esperados, axis=0)*100
    mensal = valores.notna().resample('MS').sum().div(valores.iloc[:,0].resample('MS').size(), axis=0)*100
    return dict(valores=valores, registros=registros, estatisticas=pd.DataFrame(linhas),
                cobertura_diaria=cobertura, cobertura_mensal=mensal)


def carregar_csv_brasil(original, ano=2025, usina='07-07FX'):
    """Lê a base manual sem refazer o merge, imputar ou exigir oito inversores."""
    obrigatorias={'datetime','usine_code','total_active_power_w'}
    if not obrigatorias.issubset(original.columns):
        raise ValueError(f'Colunas obrigatórias ausentes: {sorted(obrigatorias-set(original.columns))}')
    dados=original.loc[original.usine_code.eq(usina)].copy()
    ts=pd.to_datetime(dados.datetime,utc=True,errors='coerce',format='mixed')
    if ts.isna().any():raise ValueError('Há horários inválidos no CSV consolidado brasileiro.')
    local=ts.dt.tz_convert('America/Sao_Paulo').dt.tz_localize(None)
    if local.ne(local.dt.floor('5min')).any():
        raise ValueError('O CSV consolidado contém horários fora da grade de cinco minutos.')
    if local.duplicated().any():raise ValueError('O CSV consolidado contém horários duplicados para a usina.')
    selecionados=local.dt.year.eq(ano)
    dados=dados.loc[selecionados].copy();local=local.loc[selecionados]
    if dados.empty:raise ValueError(f'Não há dados de {usina} no ano {ano}.')
    colunas_est=[c for c in original if c not in METADADOS_ESTACAO and c not in COLUNAS_INV
                 and c not in COLUNAS_AUDITORIA_BRASIL and not c.startswith('meta.')]
    grade=pd.date_range(f'{ano}-01-01',f'{ano}-12-31 23:55',freq='5min',name='horario_local')
    valores=dados[['total_active_power_w',*colunas_est]].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    valores.index=pd.DatetimeIndex(local)
    valores=valores.rename(columns={'total_active_power_w':'potencia_total_kw'})
    valores['potencia_total_kw']/=1000
    valores=valores.reindex(grade)
    presente=pd.Series(grade.isin(local),index=grade)
    registros=pd.DataFrame({c:presente for c in valores})
    origem=dados.copy();origem.index=pd.DatetimeIndex(local)
    for flag,cols in [('tem_registro_inversores',['potencia_total_kw']),('tem_registro_estacao',colunas_est)]:
        if flag in origem:
            mascara=origem[flag].astype('string').str.lower().map({'true':True,'false':False,'1':True,'0':False})
            if mascara.isna().any():raise ValueError(f'Indicador de origem inválido: {flag}')
            mascara=mascara.reindex(grade,fill_value=False).astype(bool)
            for coluna in cols:registros[coluna]=mascara
    descricoes={'potencia_total_kw':'Potência agregada informada em total_active_power_w no CSV manual'}
    unidades={'potencia_total_kw':'kW (W do CSV divididos por 1000)'}
    for c in colunas_est:descricoes[c],unidades[c]=significado(c)
    meta=dict(linhas_csv=len(original),linhas_usina_no_ano=len(dados),ano=ano,usina=usina,
        inicio_utc=str(ts.min()),fim_utc=str(ts.max()),inicio_local=str(local.min()),fim_local=str(local.max()),
        intervalos_calendario=len(grade),horarios_duplicados=0,horarios_desalinhados=0,
        intervalos_com_potencia=int(valores.potencia_total_kw.notna().sum()),
        regra_presenca='Indicadores tem_registro_estacao e tem_registro_inversores quando disponíveis; caso contrário, presença da linha no CSV',
        regra_merge_documentada='data.ipynb usa a grade completa de cinco minutos como base e associa estação e inversores independentemente; soma com min_count=1',
        contribuintes='n_inversores_potencia distingue somas completas e parciais; a presença da potência não exige oito contribuintes',
        colunas_fisicas_estacao=colunas_est)
    if 'n_inversores_potencia' in dados:
        n=pd.to_numeric(dados.n_inversores_potencia,errors='coerce')
        meta.update(intervalos_oito_inversores=int(n.eq(8).sum()),
                    intervalos_soma_parcial=int(n.between(1,7).sum()))
    return valores,registros,descricoes,unidades,meta


def preparar_caracterizacao_sistemas(raiz, arquivo_brasil=None):
    raiz = Path(raiz).resolve()
    pasta = raiz/'reports/tcc/caracterizacao_sistemas'
    tabdir = pasta/'tabelas';figdir=pasta/'figuras'
    tabdir.mkdir(parents=True,exist_ok=True);figdir.mkdir(exist_ok=True)
    au_path=raiz/'data/raw/australia/87-Site_DKA-M9_A+C-Phases.csv'
    br_path=Path(arquivo_brasil) if arquivo_brasil is not None else raiz/'Leopoldo_base_consolidada_5min.csv'
    if not br_path.is_absolute():br_path=raiz/br_path
    if not br_path.is_file():raise FileNotFoundError(f'CSV brasileiro solicitado não encontrado: {br_path}')
    fontes_arquivos=[au_path,br_path]
    hashes={str(p.relative_to(raiz)) if p.is_relative_to(raiz) else str(p):sha256(p) for p in fontes_arquivos}
    print('Lendo potência do sistema australiano e canais meteorológicos.',flush=True)
    au=pd.read_csv(au_path,low_memory=False)
    colunas_au=[c for c in au if c not in EXCLUIR_AU]
    ts=pd.to_datetime(au.timestamp,errors='coerce',format='mixed')
    numericos=au[colunas_au].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    numericos.index=ts.dt.floor('5min')
    numericos=numericos.loc[numericos.index.notna()]
    grade_au=pd.date_range(ts.min().normalize(),ts.max().normalize()+pd.Timedelta(hours=23,minutes=55),freq='5min',name='horario')
    grupos=numericos.groupby(level=0)
    valores_au=grupos.median().reindex(grade_au)
    presenca_au=grupos.size().reindex(grade_au,fill_value=0).gt(0)
    registros_au=pd.DataFrame({c:presenca_au for c in colunas_au})
    desc_au={c:significado(c)[0] for c in colunas_au};uni_au={c:significado(c)[1] for c in colunas_au}

    print(f'Lendo exclusivamente a base brasileira fornecida: {br_path.name}',flush=True)
    valores_br,registros_br,desc_br,uni_br,meta_br=carregar_csv_brasil(pd.read_csv(br_path,low_memory=False))
    fontes={
        'australia':descrever_fonte(valores_au,registros_au,'Austrália',desc_au,uni_au),
        'brasil':descrever_fonte(valores_br,registros_br,'Brasil: CSV consolidado',desc_br,uni_br)}
    estatisticas=pd.concat([d['estatisticas'] for d in fontes.values()],ignore_index=True)
    resumo=[];lacunas=[];flags=[]
    alvos={'australia':'Active_Power','brasil':'potencia_total_kw'}
    for chave,d in fontes.items():
        v=d['valores'];c=alvos[chave];s=v[c]
        resumo.append(dict(fonte=chave,variavel_potencia=c,inicio=str(v.index[0]),fim=str(v.index[-1]),
            intervalos_esperados=len(v),intervalos_com_potencia=int(s.notna().sum()),
            cobertura_potencia_pct=100*s.notna().mean(),variaveis_meteorologicas=len(v.columns)-1))
        g=extrair_lacunas(s.isna(),'5min');g['fonte']=chave;g['variavel']=c;lacunas.append(g)
        for var in v:
            mascara,criterio=sinalizar_variavel(v[var],var)
            flags.append(dict(fonte=chave,variavel=var,criterio=criterio,intervalos_sinalizados=int(mascara.sum())))
        for nome in ['cobertura_diaria','cobertura_mensal']:
            d[nome].to_csv(tabdir/f'{chave}_{nome}.csv')
    tabelas={'resumo_fontes':pd.DataFrame(resumo),'estatisticas':estatisticas,
             'dicionario_cobertura':estatisticas.iloc[:,:13],
             'lacunas_potencia':pd.concat(lacunas,ignore_index=True),'flags':pd.DataFrame(flags),
             'auditoria_csv_brasil':pd.DataFrame([meta_br]).drop(columns=['colunas_fisicas_estacao'])}
    for nome,tabela in tabelas.items():tabela.to_csv(tabdir/f'{nome}.csv',index=False)
    valores_br.to_csv(tabdir/'brasil_potencia_estacao_5min.csv')
    meta=dict(escopo='Potência por sistema e canais meteorológicos; Brasil a partir do CSV consolidado manual',
        arquivo_brasil=str(br_path),potencia_brasil='total_active_power_w do CSV manual, convertido de W para kW; sem novo filtro de contribuintes',
        australia='Potência Active_Power e canais meteorológicos; energia ativa e corrente excluídas',
        estacao_brasil='Todos os canais físicos presentes no esquema; sem metadados ou códigos de diagnóstico',
        duplicatas='O CSV brasileiro é lido sem reconsolidar valores; horários duplicados ou desalinhados geram erro. Austrália: mediana por intervalo.',
        ausencias='Grade completa de cinco minutos, sem imputação; zeros finitos são observados',
        periodos='Austrália integral de 2013 a 2025; Brasil em 2025. O experimento diário australiano termina em 2023.',
        uso_modelo='Meteorologia é descritiva; o cenário univariado utiliza apenas potência. Nenhum alvo diário foi alterado.',
        unidades='Unidades e escalas não confirmadas permanecem identificadas no dicionário',
        auditoria_csv_brasil=meta_br,fontes_sha256=hashes,codigo_sha256=sha256(Path(__file__)))
    (pasta/'manifesto.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for p in fontes_arquivos:
        chave=str(p.relative_to(raiz)) if p.is_relative_to(raiz) else str(p)
        assert hashes[chave]==sha256(p)
    for d in fontes.values():
        t=d['estatisticas']
        assert (t.intervalos_sem_registro+t.registro_sem_valor_disponivel+t.intervalos_disponiveis==t.intervalos_esperados).all()
    return dict(pasta=pasta,figuras=figdir,tabelas_dir=tabdir,fontes=fontes,tabelas=tabelas,meta=meta,alvos=alvos)


def gerar_figuras_sistemas(r):
    import matplotlib.pyplot as plt
    indice=[];cores=['#2166a1','#b45f06']
    def salvar(fig,nome,titulo,legenda):
        if fig.legends: fig.tight_layout(rect=(0,0,1,.90))
        else: fig.tight_layout()
        for ext in ['png','pdf']:fig.savefig(r['figuras']/f'{nome}.{ext}',dpi=300,facecolor='white')
        plt.close(fig);indice.append(dict(arquivo=nome,titulo=titulo,legenda=legenda))
    with plt.rc_context({'font.family':'DejaVu Serif','font.size':10,'axes.titlesize':11,'legend.fontsize':8,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False}):
        for numero,(chave,cor) in enumerate(zip(['australia','brasil'],cores),1):
            d=r['fontes'][chave];alvo=r['alvos'][chave];pais='Austrália' if chave=='australia' else 'Brasil'
            unico_ano=d['cobertura_mensal'].index.year.nunique()==1
            fig,ax=plt.subplots(2,1,figsize=(11.7,5 if unico_ano else 7),
                gridspec_kw={'height_ratios':[1,.35 if unico_ano else 1.3]})
            s=d['cobertura_diaria'][alvo];ax[0].plot(s.index,s,color=cor,lw=.7)
            ax[0].set(title=f'{pais}: cobertura diária da potência do sistema',ylabel='Intervalos com potência disponível (%)',ylim=(-2,103));ax[0].grid(alpha=.2)
            mensal=d['cobertura_mensal'][alvo];mat=mensal.groupby([mensal.index.year,mensal.index.month]).first().unstack().reindex(columns=range(1,13))
            im=ax[1].imshow(np.ma.masked_invalid(mat),aspect='auto',vmin=0,vmax=100,cmap='cividis')
            ax[1].set_xticks(range(12),MESES);ax[1].set_yticks(range(len(mat)),mat.index)
            ax[1].set(title=f'{pais}: cobertura mensal da potência do sistema',ylabel='Ano',xlabel='Mês');fig.colorbar(im,ax=ax[1],label='Potência disponível (%)')
            legenda=('Proporção de intervalos de cinco minutos com potência numérica finita, considerando 288 intervalos esperados por dia. '
                     'Os dois painéis representam exclusivamente potência; zeros observados são contabilizados como disponíveis. ')
            legenda+=('A potência brasileira é a coluna total_active_power_w de Leopoldo_base_consolidada_5min.csv, convertida para kW. O arquivo utiliza uma grade completa e preserva potência mesmo sem meteorologia; n_inversores_potencia identifica somas completas e parciais. A cobertura inclui todas as potências finitas informadas, sem exigir oito contribuintes. ' if chave=='brasil' else 'A variável australiana é Active_Power; o período integral do arquivo é apresentado, enquanto o experimento diário utiliza somente dados até 2023. ')
            legenda+='Regiões em branco representam meses externos ao período analisado.'
            salvar(fig,f'fig_3_2_{numero:02d}_cobertura_{chave}',f'Cobertura temporal da potência do sistema: {pais}',legenda)

        br=r['fontes']['brasil'];meteo=br['cobertura_mensal'].drop(columns='potencia_total_kw')
        fig,ax=plt.subplots(figsize=(12,max(6,.26*len(meteo.columns))))
        im=ax.imshow(meteo.to_numpy().T,aspect='auto',vmin=0,vmax=100,cmap='cividis')
        ax.set_yticks(range(len(meteo.columns)),meteo.columns,fontsize=8);ax.set_xticks(range(len(meteo)),[str(i.month).zfill(2) for i in meteo.index])
        ax.set(title='Brasil: cobertura dos canais da estação no CSV consolidado',xlabel='Mês de 2025',ylabel='Variável da estação');fig.colorbar(im,ax=ax,label='Intervalos com valor disponível (%)')
        salvar(fig,'fig_3_2_03_estacao_solarimetrica','Cobertura mensal dos canais da estação solarimétrica brasileira',
            'Proporção de intervalos do calendário completo de 2025 com valor numérico finito em cada canal físico da estação, utilizando exclusivamente Leopoldo_base_consolidada_5min.csv. Os valores são lidos sem nova consolidação ou imputação. Cada variável possui contagem independente. Canais totalmente ausentes são preservados no inventário; sua ausência não comprova falha de sensor. Nenhuma variável ERA5 é incluída.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,4.8))
        for a,(chave,cor) in zip(ax,zip(['australia','brasil'],cores)):
            s=r['fontes'][chave]['valores'][r['alvos'][chave]].dropna()
            a.hist(s,bins=60,density=True,histtype='step',lw=1.4,color=cor)
            a.set(title='Austrália' if chave=='australia' else 'Brasil: CSV consolidado',xlabel='Potência ativa do sistema (kW)',ylabel='Densidade');a.grid(alpha=.2)
        salvar(fig,'fig_3_2_04_distribuicoes_potencia','Distribuições de potência dos sistemas australiano e brasileiro',
            'Histogramas de densidade da potência em kW, utilizando todos os intervalos disponíveis, inclusive zeros e valores negativos finitos. No Brasil, utiliza-se a potência agregada informada no CSV consolidado manual, sem exigir novamente oito contribuintes ou refazer as somas. As escalas de potência e os períodos de observação diferem entre os sistemas; não se aplica normalização por capacidade nesta etapa.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.6))
        for a,chave in zip(ax,['australia','brasil']):
            t=r['fontes'][chave]['estatisticas'];selecionadas=([r['alvos'][chave],'Weather_Temperature_Celsius','Weather_Relative_Humidity','Global_Horizontal_Radiation'] if chave=='australia' else ['potencia_total_kw','air_temperature_med','ghi_irr_med'])
            t=t.set_index('variavel').loc[selecionadas];base=np.zeros(len(t))
            for c,label,cor in [('intervalos_sem_registro','Sem registro','#b34d3e'),('registro_sem_valor_disponivel','Registro sem valor disponível','#e5b451'),('intervalos_disponiveis','Valor disponível','#3c8b72')]:
                v=100*t[c]/t.intervalos_esperados;a.bar(range(len(t)),v,bottom=base,color=cor,label=label);base+=v.to_numpy()
            labels=['Potência','Temperatura','Umidade','GHI'] if chave=='australia' else ['Potência total','Temperatura','GHI']
            a.set_xticks(range(len(t)),labels,rotation=35,ha='right');a.set(title='Austrália' if chave=='australia' else 'Brasil: CSV consolidado',ylabel='Intervalos esperados (%)',ylim=(0,100))
        handles,labels=ax[0].get_legend_handles_labels();fig.legend(handles,labels,loc='upper center',ncol=3,frameon=False);fig.subplots_adjust(top=.85)
        salvar(fig,'fig_3_2_05_disponibilidade_variaveis','Disponibilidade da potência e de variáveis meteorológicas selecionadas',
            'Distribuição dos intervalos esperados entre ausência de registro da fonte, registro presente sem valor disponível e presença de valor numérico finito. No Brasil, os indicadores tem_registro_inversores e tem_registro_estacao identificam a presença de cada fonte independentemente das linhas da grade completa. As tabelas apresentam todos os canais meteorológicos; a figura seleciona temperatura, umidade disponível na Austrália e GHI.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,4.8))
        g=r['tabelas']['lacunas_potencia'];maximo=max(1,g.minutos.max()/60);bins=np.logspace(np.log10(5/60),np.log10(maximo),35)
        for a,(chave,cor) in zip(ax,zip(['australia','brasil'],cores)):
            a.hist(g.loc[g.fonte.eq(chave),'minutos']/60,bins=bins,histtype='step',color=cor,lw=1.4)
            a.set(title='Austrália' if chave=='australia' else 'Brasil: CSV consolidado',xscale='log',yscale='log',xlabel='Duração da lacuna de potência (horas)',ylabel='Número de lacunas');a.grid(alpha=.2)
        salvar(fig,'fig_3_2_06_lacunas_potencia','Distribuição da duração das lacunas de potência por sistema',
            'Sequências consecutivas de intervalos de cinco minutos sem potência numérica finita. No Brasil, incluem-se tanto os horários sem linha no CSV consolidado manual quanto as linhas com potência ausente. A duração corresponde ao número de intervalos consecutivos multiplicado por cinco minutos. Incluem-se as bordas do calendário. Os eixos utilizam escala logarítmica.')

        fig,a=plt.subplots(figsize=(10,4.5))
        for chave,cor in zip(['australia','brasil'],cores):
            s=r['fontes'][chave]['valores'][r['alvos'][chave]];perfil=100*s.notna().groupby(s.index.hour).mean()
            a.plot(perfil.index,perfil,marker='o',ms=3,color=cor,label='Austrália' if chave=='australia' else 'Brasil: CSV consolidado')
        a.set(title='Disponibilidade horária da potência dos sistemas',xlabel='Hora do dia',ylabel='Intervalos com potência disponível (%)',xticks=range(0,24,2),ylim=(-2,103));a.legend();a.grid(alpha=.2)
        salvar(fig,'fig_3_2_07_disponibilidade_horaria','Perfil horário da disponibilidade de potência dos sistemas',
            'Proporção de intervalos com potência numérica finita por hora do dia, incluindo as 24 horas e os zeros observados. A Austrália mantém a convenção temporal do arquivo; o Brasil utiliza America/Sao_Paulo após conversão dos horários UTC. O perfil é descritivo e não atribui causa às ausências.')
    (r['pasta']/'indice_figuras.json').write_text(json.dumps(indice,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    texto='# Legendas: potência dos sistemas e estações meteorológicas\n\n'
    for i,item in enumerate(indice,1):texto+=f"## Figura 3.2-{i:02d}: {item['titulo']}\n\n{item['legenda']}\n\nFonte: elaboração própria a partir dos dados das instalações analisadas.\n\n"
    (r['pasta']/'legendas_figuras.md').write_text(texto,encoding='utf-8')
    return indice
