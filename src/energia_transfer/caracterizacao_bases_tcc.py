"""Auditoria descritiva dos CSVs crus: nenhuma imputação ou correção de valores."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .chronos_experimentos import sha256, salvar_json

COLUNAS_AU = ['Active_Power', 'Weather_Temperature_Celsius', 'Weather_Relative_Humidity', 'Global_Horizontal_Radiation']
COLUNAS_INV = ['total_active_power_w', 'daily_power_yields_kwh', 'total_power_yields_kwh']
COLUNAS_EST = ['air_temperature_med', 'ghi_irr_med']
MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
CORES = ['#2166a1', '#b45f06', '#3c8b72']


def classe_cobertura(contagem, esperados=288):
    x = np.asarray(contagem, dtype=float)
    if not np.isfinite(x).all() or ((x<0)|(x>esperados)).any():
        raise ValueError('Contagens precisam estar entre zero e o total esperado.')
    return np.select([x==0, x<.95*esperados, x<esperados], [0,1,2], default=3)


def extrair_lacunas(ausente, passo='1D'):
    passo = pd.Timedelta(passo)
    if not ausente.index.is_unique or not ausente.index.to_series().diff().dropna().eq(passo).all():
        raise ValueError('Use um calendário completo, regular e único.')
    if ausente.isna().any():
        raise ValueError('A máscara precisa ser explícita, sem NaN.')
    x = np.r_[False, ausente.to_numpy(dtype=bool), False].astype(int)
    ini, fim = np.flatnonzero(np.diff(x)==1), np.flatnonzero(np.diff(x)==-1)-1
    n = fim-ini+1
    d = dict(inicio=ausente.index[ini], fim=ausente.index[fim], posicoes=n, minutos=n*passo.total_seconds()/60)
    if passo==pd.Timedelta(days=1): d['dias']=n
    return pd.DataFrame(d)


def cobertura_por_chave(instantes, equipamentos, finitos, grade, lista_equipamentos):
    """Conta existência por chave; não calcula média/mediana nem altera valores crus.

    A máscara booleana ANY evita que duplicatas inflem cobertura. A disponibilidade
    pode ser verdadeira mesmo se outra linha da mesma chave estiver vazia.
    """
    idx = pd.MultiIndex.from_product([grade, lista_equipamentos], names=['instante','equipamento'])
    chaves = pd.DataFrame({'instante':instantes, 'equipamento':equipamentos})
    validas = chaves.instante.isin(grade) & chaves.equipamento.isin(lista_equipamentos)
    chaves = chaves.loc[validas].copy()
    registros = chaves.groupby(['instante','equipamento']).size().reindex(idx, fill_value=0)
    cobertura = pd.DataFrame({'registro':registros.gt(0)})
    for c in finitos:
        chaves[c] = np.asarray(finitos[c])[validas.to_numpy()]
        cobertura[c] = chaves.groupby(['instante','equipamento'])[c].any().reindex(idx, fill_value=False)
    assert registros.sum()==int(validas.sum())
    return cobertura, registros


def _inventario_colunas(path, codigo):
    linhas, codigos, n = {}, {}, 0
    for parte in pd.read_csv(path, chunksize=100000, low_memory=False):
        n += len(parte)
        if 'usine_code' in parte:
            for k,v in parte.usine_code.fillna('(ausente)').value_counts().items():
                codigos[k] = codigos.get(k,0)+int(v)
        selecao = parte if codigo is None else parte.loc[parte.usine_code.eq(codigo)]
        for c in selecao:
            par = linhas.setdefault(c, [0,0])
            par[0] += len(selecao); par[1] += int(selecao[c].isna().sum())
    return pd.DataFrame([dict(coluna=c, linhas=nobs, ausentes_nas_linhas=na, ausentes_pct=100*na/nobs if nobs else np.nan) for c,(nobs,na) in linhas.items()]), codigos, n


def _auditar(path, nome, cols, tempo, equipamento=None, codigo=None, ano=None):
    extra = ([equipamento] if equipamento else [])+(['usine_code'] if codigo else [])
    original = pd.read_csv(path, usecols=[tempo]+cols+extra, low_memory=False)
    inventario, codigos, n_arquivo = _inventario_colunas(path,codigo)
    bruto = original if codigo is None else original.loc[original.usine_code.eq(codigo)].copy()
    bruto = bruto.reset_index(drop=True)
    ts = pd.to_datetime(bruto[tempo], errors='coerce', utc=bool(codigo), format='mixed')
    if codigo: ts = ts.dt.tz_convert('America/Sao_Paulo').dt.tz_localize(None)
    nums = bruto[cols].apply(pd.to_numeric, errors='coerce')
    finitos = pd.DataFrame(np.isfinite(nums), columns=cols)
    eq = bruto[equipamento] if equipamento else pd.Series('sistema', index=bruto.index)
    lista = sorted(eq.dropna().unique().tolist())
    if ano:
        dias = pd.date_range(f'{ano}-01-01',f'{ano}-12-31',freq='D')
    else:
        dias = pd.date_range(ts.min().normalize(), ts.max().normalize(), freq='D')
    grade = pd.date_range(dias[0], dias[-1]+pd.Timedelta(hours=23,minutes=55), freq='5min')
    cobertura_exata, registros_exatos = cobertura_por_chave(ts, eq, finitos, grade, lista)
    # Classes temporais [t,t+5min) para CONTAGEM de existência, sem mudar ts/bruto
    # nem agregar os valores. Separa desalinhamento do relógio de falta de coleta.
    cobertura, registros = cobertura_por_chave(ts.dt.floor('5min'), eq, finitos, grade, lista)
    # Apenas contagens: não há consolidação dos valores numéricos duplicados.
    keys = pd.DataFrame({'instante':ts, 'equipamento':eq})
    ok = keys.notna().all(axis=1)
    tamanhos = keys.loc[ok].groupby(['instante','equipamento']).size()
    repetidas = tamanhos[tamanhos.gt(1)]
    valores = nums.loc[ok].copy()
    valores['instante']=ts[ok]; valores['equipamento']=eq[ok]
    # Inclui divergência entre valor ausente e presente na mesma chave.
    divergencias = valores.groupby(['instante','equipamento'])[cols].nunique(dropna=False).gt(1).any(axis=1)
    offgrid = ts.notna() & ((ts.dt.minute%5).ne(0)|ts.dt.second.ne(0)|ts.dt.microsecond.ne(0)|ts.dt.nanosecond.ne(0))
    meta = dict(fonte=nome,arquivo=str(path),linhas_arquivo=n_arquivo,linhas_selecionadas=len(bruto),
                codigo_selecionado=codigo,codigos_no_arquivo=codigos,equipamentos=lista,n_equipamentos=len(lista),
                inicio_registrado=str(ts.min()),fim_registrado=str(ts.max()),inicio_calendario=str(dias[0].date()),fim_calendario=str(dias[-1].date()),
                dias_calendario=len(dias),timestamps_invalidos=int(ts.isna().sum()),equipamentos_ausentes=int(eq.isna().sum()),
                linhas_fora_grade_5min=int(offgrid.sum()),linhas_fora_calendario=int((ts.notna()&~ts.dt.normalize().isin(dias)).sum()),
                chaves_repetidas=len(repetidas),linhas_excedentes_mesma_chave=int((repetidas-1).sum()),
                chaves_com_valores_distintos=int(divergencias.sum()),
                grade_esperada=len(grade)*len(lista),fuso='America/Sao_Paulo (apresentação de datetime UTC)' if codigo else 'Convenção do CSV; sem fuso explícito')
    por_dia = pd.DataFrame(index=dias)
    por_dia.index.name='data'
    por_dia['posicoes_esperadas']=288*len(lista)
    por_dia['linhas_no_calendario']=registros.groupby(level=0).sum().resample('D').sum().reindex(dias,fill_value=0)
    por_dia['posicoes_com_registro_exato']=cobertura_exata.registro.groupby(level=0).sum().resample('D').sum().reindex(dias,fill_value=0)
    por_dia['cobertura_registro_exato_pct']=100*por_dia.posicoes_com_registro_exato/por_dia.posicoes_esperadas
    for c in cobertura:
        por_dia[f'posicoes_com_{c}']=cobertura[c].groupby(level=0).sum().resample('D').sum().reindex(dias,fill_value=0)
        por_dia[f'cobertura_{c}_pct']=por_dia[f'posicoes_com_{c}']/por_dia.posicoes_esperadas*100
    por_dia['linhas_adicionais_no_intervalo']=por_dia.linhas_no_calendario-por_dia.posicoes_com_registro
    principal = cols[0]
    matriz = cobertura[principal].unstack('equipamento').resample('D').sum()/288*100
    simultaneos = cobertura[principal].groupby(level=0).sum().eq(len(lista))
    por_dia['cobertura_todos_equipamentos_pct']=simultaneos.resample('D').sum()/288*100
    estatisticas=[]; taxas=[]; flags=[]
    for c in cols:
        s=nums[c]; observados=s[np.isfinite(s)]
        estatisticas.append(dict(fonte=nome,variavel=c,linhas=len(s),n_finitos=len(observados),vazios=int(bruto[c].isna().sum()),
                                 texto_nao_numerico=int((bruto[c].notna()&s.isna()).sum()),infinitos=int(np.isinf(s).sum()),
                                 zeros=int(s.eq(0).sum()),negativos=int(s.lt(0).sum()),media=observados.mean(),desvio_padrao=observados.std(),
                                 minimo=observados.min(),q25=observados.quantile(.25),mediana=observados.median(),q75=observados.quantile(.75),maximo=observados.max()))
        nobs=int(cobertura[c].sum()); nreg=int(cobertura.registro.sum()); esperados=len(cobertura)
        taxas.append(dict(fonte=nome,variavel=c,esperados=esperados,sem_registro=esperados-nreg,registro_sem_valor_finito=nreg-nobs,
                          com_valor_finito=nobs,indisponiveis_pct=100*(1-nobs/esperados),vazios_nas_linhas=int(bruto[c].isna().sum())))
        taxas[-1]['com_valor_finito_timestamp_exato']=int(cobertura_exata[c].sum())
        if 'Temperature' in c or c=='air_temperature_med':
            f=s.notna()&~s.between(-20,60); criterio='Temperatura fora de −20 a 60 °C (triagem)'
        elif 'Humidity' in c:
            f=s.notna()&~s.between(0,100); criterio='Umidade fora de 0 a 100%'
        else:
            f=s.lt(0); criterio='Valor negativo (triagem; não removido)'
        flags.append(dict(fonte=nome,variavel=c,criterio=criterio,linhas_sinalizadas=int(f.sum()),denominador_linhas=len(bruto)))
    lacunas=[]
    for equip in lista:
        g=extrair_lacunas(~cobertura[principal].xs(equip,level='equipamento'),'5min')
        g['fonte']=nome;g['equipamento']=equip;g['variavel']=principal;lacunas.append(g)
    lacunas_dia=extrair_lacunas(por_dia.posicoes_com_registro.eq(0))
    lacunas_dia['fonte']=nome
    repetidas_dia=(repetidas-1).groupby(level=0).sum().resample('D').sum().reindex(dias,fill_value=0)
    por_dia['linhas_duplicadas_chave_exata']=repetidas_dia
    hora=cobertura[principal].groupby(cobertura.index.get_level_values('instante').hour).mean()*100
    meta['dias_sem_qualquer_registro']=int(por_dia.posicoes_com_registro.eq(0).sum())
    meta['dias_com_grade_completa']=int(por_dia.cobertura_registro_pct.eq(100).sum())
    meta['dias_com_registros_parciais']=len(dias)-meta['dias_sem_qualquer_registro']-meta['dias_com_grade_completa']
    return dict(meta=meta,bruto=bruto,numericos=nums,instantes=ts,equipamento=eq,diario=por_dia,matriz=matriz,
                estatisticas=pd.DataFrame(estatisticas),taxas=pd.DataFrame(taxas),flags=pd.DataFrame(flags),
                lacunas=pd.concat(lacunas,ignore_index=True),lacunas_dia=lacunas_dia,inventario=inventario,
                duplicatas_dia=repetidas_dia,cobertura_horaria=hora,cobertura=cobertura)


def preparar_caracterizacao(raiz):
    raiz=Path(raiz).resolve(); pasta=raiz/'reports/tcc/caracterizacao_dados_crus'
    figuras=pasta/'figuras'; tabelas=pasta/'tabelas'
    figuras.mkdir(parents=True,exist_ok=True);tabelas.mkdir(exist_ok=True)
    specs=[('australia','Austrália',raiz/'data/raw/australia/87-Site_DKA-M9_A+C-Phases.csv',COLUNAS_AU,'timestamp',None,None,None),
           ('brasil_inversores','Brasil — inversores',raiz/'data/raw/brasil/Leopoldo-fixa-inv.csv',COLUNAS_INV,'datetime','equipment_name','07-07FX',2025),
           ('brasil_estacao','Brasil — estação',raiz/'data/raw/brasil/Leopoldo-fixa-est.csv',COLUNAS_EST,'datetime','equipment_name','07-07FX',2025)]
    hashes={str(s[2].relative_to(raiz)):sha256(s[2]) for s in specs}
    dados={}
    for key,nome,path,cols,tempo,equip,codigo,ano in specs:
        print(f'Lendo arquivo cru: {nome}',flush=True)
        dados[key]=_auditar(path,nome,cols,tempo,equip,codigo,ano)
    resumo=pd.DataFrame([d['meta'] for d in dados.values()])
    tabelas_dados={'resumo_fontes':resumo}
    for nome in ['estatisticas','taxas','flags','lacunas','lacunas_dia']:
        tabelas_dados[nome]=pd.concat([d[nome] for d in dados.values()],ignore_index=True)
    for key,d in dados.items():
        tabelas_dados[f'{key}_por_dia']=d['diario'].reset_index()
        tabelas_dados[f'{key}_inventario_colunas']=d['inventario']
        tabelas_dados[f'{key}_cobertura_por_equipamento']=d['matriz'].reset_index()
    for nome,t in tabelas_dados.items(): t.to_csv(tabelas/f'{nome}.csv',index=False)
    meta=dict(escopo='Somente CSVs crus; Austrália integral 2013–2025; Brasil código 07-07FX em calendário de 2025',
              imputacao=False,correcao_de_valores=False,remocao_de_duplicatas=False,agregacao_de_alvos=False,
              denominadores='288 intervalos [t,t+5min) por dia civil e equipamento; comparação separada com chaves de timestamp exato',
              disponibilidade='Existência em intervalo de cinco minutos e de valor finito. Apenas máscaras de contagem; nenhum valor duplicado é consolidado e os timestamps crus são preservados.',
              ressalvas=['Grade civil completa é uma referência; bordas do arquivo e períodos anteriores ao início da aquisição não comprovam falha.',
                         'Valores negativos e fora das faixas de triagem permanecem nas estatísticas e distribuições.',
                         'Inventário de todas as colunas; estudo detalhado nas variáveis de potência, contadores e meteorologia, sem vento.',
                         'Umidade não aparece no arquivo da estação brasileira; ausência de variável não é perda de leituras.',
                         'GHI da estação brasileira conserva a escala do CSV; unidade/calibração pendentes de confirmação.',
                         'ERA5, bases diárias reconstruídas, normalização e filtros dos modelos não entram nesta análise.'],
              fontes_sha256=hashes,codigo_sha256=sha256(Path(__file__)),fontes={k:d['meta'] for k,d in dados.items()})
    salvar_json(pasta/'manifesto.json',meta)
    for rel,h in hashes.items(): assert sha256(raiz/rel)==h
    return dict(raiz=raiz,pasta=pasta,figuras=figuras,tabelas_dir=tabelas,tabelas=tabelas_dados,meta=meta,dados=dados)


def gerar_figuras(r):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    au,inv,est=[r['dados'][k] for k in ['australia','brasil_inversores','brasil_estacao']]
    indice=[]
    def salvar(fig,nome,titulo,legenda):
        if fig.legends: fig.tight_layout(rect=(0,0,1,.91))
        else: fig.tight_layout()
        fig.savefig(r['figuras']/f'{nome}.png',dpi=300,facecolor='white')
        fig.savefig(r['figuras']/f'{nome}.pdf',facecolor='white');plt.close(fig)
        indice.append(dict(arquivo=nome,titulo=titulo,legenda=legenda))
    estilo={'font.family':'DejaVu Serif','font.size':10,'axes.titlesize':11,'legend.fontsize':8,'pdf.fonttype':42,
            'axes.spines.top':False,'axes.spines.right':False}
    with plt.rc_context(estilo):
        fig,ax=plt.subplots(2,1,figsize=(11.7,7),gridspec_kw={'height_ratios':[1,1.3]})
        d=au['diario']
        ax[0].plot(d.index,d.cobertura_registro_pct,lw=.65,color=CORES[0])
        ax[0].set(title='Austrália: cobertura do arquivo cru em cada dia civil',ylabel='Intervalos com registro / 288 (%)',ylim=(-2,102));ax[0].grid(alpha=.2)
        mensal=d.posicoes_com_registro.groupby([d.index.year,d.index.month]).sum()/d.posicoes_esperadas.groupby([d.index.year,d.index.month]).sum()*100
        mat=mensal.unstack().reindex(columns=range(1,13))
        im=ax[1].imshow(np.ma.masked_invalid(mat),aspect='auto',vmin=0,vmax=100,cmap='cividis')
        ax[1].set_xticks(range(12),MESES);ax[1].set_yticks(range(len(mat)),mat.index)
        ax[1].set(ylabel='Ano',xlabel='Mês',title='Cobertura mensal dos registros originais')
        fig.colorbar(im,ax=ax[1],label='Posições com registro (%)',pad=.01)
        salvar(fig,'fig_3_2_01_australia_crua','Disponibilidade do arquivo australiano integral',
               'Contagem de intervalos de cinco minutos com registros, sem filtro de valores ou imputação. Os timestamps australianos estão alinhados à grade exata. O período integral do arquivo é usado; não há corte em 2023. Dias civis completos são a referência, inclusive nas bordas parciais do arquivo. Branco: mês fora do intervalo.')

        fig,ax=plt.subplots(2,1,figsize=(11.7,7),sharex=True)
        mat=inv['matriz'];x0=mdates.date2num(mat.index[0]);x1=mdates.date2num(mat.index[-1]+pd.Timedelta(days=1))
        im=ax[0].imshow(mat.to_numpy().T,aspect='auto',origin='lower',extent=[x0,x1,-.5,len(mat.columns)-.5],vmin=0,vmax=100,cmap='cividis')
        ax[0].set_yticks(range(len(mat.columns)),[c.replace('inverter','Inv. ') for c in mat.columns]);ax[0].set(title='Brasil: presença de potência crua por inversor',ylabel='Equipamento')
        fig.colorbar(im,ax=ax[0],label='Posições com valor finito / 288 (%)',pad=.01)
        dd=inv['diario'];ax[1].plot(dd.index,dd.cobertura_total_active_power_w_pct,label='Fração de posições inversor–horário',color=CORES[1],lw=.9)
        ax[1].plot(dd.index,dd.cobertura_todos_equipamentos_pct,label='Intervalos com os oito inversores',color=CORES[2],lw=.8)
        ax[1].plot(dd.index,dd.cobertura_registro_exato_pct,label='Registros em timestamp exato (diagnóstico)',color='#777777',lw=.6,ls='--')
        ax[1].set(ylabel='Cobertura (%)',xlabel='Mês de 2025',ylim=(-2,103));ax[1].legend();ax[1].grid(alpha=.2)
        ax[1].xaxis.set_major_locator(mdates.MonthLocator());ax[1].xaxis.set_major_formatter(mdates.DateFormatter('%m'))
        salvar(fig,'fig_3_2_02_inversores_crus','Disponibilidade dos registros crus dos inversores',
               'Código 07-07FX e datas locais de 2025. As curvas coloridas contam existência em intervalos [t,t+5min): 2304 posições inversor–intervalo por dia, ou 288 intervalos com os oito inversores presentes. A linha cinza exige timestamp exato e mostra o efeito do desalinhamento temporal; não implica ausência real de coleta. Presença no mesmo intervalo não exige o mesmo segundo. Nenhum valor ou timestamp cru é corrigido, somado ou imputado.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.6),sharey=True)
        for a,d,c,titulo in [(ax[0],inv,'total_active_power_w','Potência dos inversores (2304 posições/dia)'),(ax[1],est,'air_temperature_med','Temperatura da estação (288 posições/dia)')]:
            m=np.full((12,31),np.nan)
            for data,valor in d['diario'][f'cobertura_{c}_pct'].items():m[data.month-1,data.day-1]=valor
            im=a.imshow(np.ma.masked_invalid(m),aspect='auto',vmin=0,vmax=100,cmap='cividis')
            a.set_xticks([0,4,9,14,19,24,30],[1,5,10,15,20,25,31]);a.set_yticks(range(12),MESES)
            a.set(title=titulo,xlabel='Dia do mês',ylabel='Mês de 2025');fig.colorbar(im,ax=a,label='Posições com valor finito (%)',orientation='horizontal',pad=.14,fraction=.05)
        salvar(fig,'fig_3_2_03_calendario_brasil_cru','Calendário da disponibilidade original brasileira',
               'Ausências e coberturas parciais antes de qualquer reconstrução diária ou imputação. Zero significa nenhuma posição com valor finito da variável; branco indica dia inexistente no mês. A referência de calendário inclui dias sem aquisição e a borda final parcial do arquivo.')

        fig,ax=plt.subplots(1,3,figsize=(11.7,5.7),sharey=True)
        labels=[['Potência','Temperatura','Umidade','GHI'],['Potência','Contador diário','Contador total'],['Temperatura','GHI']]
        for a,d,lab in zip(ax,[au,inv,est],labels):
            t=d['taxas'];x=np.arange(len(t));base=np.zeros(len(t))
            for col,label,cor in [('sem_registro','Sem registro','#b34d3e'),('registro_sem_valor_finito','Registro sem valor finito','#e5b451'),('com_valor_finito','Valor finito presente','#3c8b72')]:
                v=t[col].to_numpy()/t.esperados.to_numpy()*100;a.bar(x,v,bottom=base,color=cor,label=label);base+=v
            a.set_xticks(x,lab,rotation=50,ha='right');a.set(title=d['meta']['fonte'],ylabel='Posições esperadas (%)',ylim=(0,100))
            a.grid(axis='y',alpha=.15)
        handles,ls=ax[0].get_legend_handles_labels();fig.legend(handles,ls,loc='upper center',bbox_to_anchor=(.5,.99),ncol=3,frameon=False)
        salvar(fig,'fig_3_2_04_ausencias_cruas','Ausência de registros e ausência de valores dentro dos registros',
               'Classes mutuamente exclusivas em intervalos [t,t+5min) por equipamento. Várias linhas no mesmo intervalo não multiplicam a cobertura: basta uma com valor finito. Valores finitos suspeitos, negativos ou fora das faixas de triagem continuam na classe verde; presença não equivale a validade. A classificação é uma contagem, sem consolidar valores ou modificar timestamps crus. As tabelas também mostram vazios nas linhas do CSV e timestamps exatos, com outras definições.')

        fig,ax=plt.subplots(2,3,figsize=(11.7,7.2))
        series=[(au,'Active_Power','Potência australiana (kW)'),(inv,'total_active_power_w','Potência por inversor brasileiro (W)'),(au,'Weather_Relative_Humidity','Umidade australiana (%)'),
                (au,'Weather_Temperature_Celsius','Temperatura (°C)'),(au,'Global_Horizontal_Radiation','GHI australiano (W/m²)'),(est,'ghi_irr_med','GHI brasileiro (escala original do CSV)')]
        for a,(d,c,titulo) in zip(ax.flat,series):
            s=d['numericos'][c];s=s[np.isfinite(s)]
            a.hist(s,bins=60,density=True,histtype='step',lw=1.3,color=CORES[[au is d,inv is d,est is d].index(True)],label=d['meta']['fonte'])
            if c=='Weather_Temperature_Celsius':
                ss=est['numericos'].air_temperature_med;ss=ss[np.isfinite(ss)]
                a.hist(ss,bins=60,density=True,histtype='step',lw=1.3,color=CORES[2],label='Brasil — estação')
            a.set(xlabel=titulo,ylabel='Densidade');a.legend(fontsize=7);a.grid(alpha=.2)
        salvar(fig,'fig_3_2_05_distribuicoes_cruas','Distribuições dos valores originais registrados',
               'Todas as linhas com valores numéricos finitos entram, inclusive duplicatas e valores suspeitos. Não há normalização por capacidade, conversão da escala de GHI brasileira, remoção de negativos ou preenchimento. Potência brasileira é por inversor em W; australiana é a variável do sistema em kW. Infinitos e textos não numéricos ficam fora do histograma e são contados nas tabelas.')

        fig,ax=plt.subplots(1,3,figsize=(11.7,5.3))
        for a,d,lab in zip(ax,[au,inv,est],labels):
            t=d['estatisticas'];pct=100*t.vazios/t.linhas
            bars=a.bar(np.arange(len(t)),pct,color=CORES[0]);a.bar_label(bars,labels=[f'{n}\n({p:.2f}%)' for n,p in zip(t.vazios,pct)],padding=3,fontsize=8)
            a.set_xticks(range(len(t)),lab,rotation=50,ha='right');a.set(title=d['meta']['fonte'],ylabel='Linhas do CSV com campo vazio (%)',ylim=(0,max(5,pct.max()*1.4)))
            a.grid(axis='y',alpha=.2)
        salvar(fig,'fig_3_2_06_campos_vazios','Campos vazios nas linhas presentes dos arquivos originais',
               'Denominador: linhas existentes na seleção de cada CSV, preservadas as duplicatas. Linhas inteiras que não foram registradas não entram aqui. Por isso, poucos NaN no arquivo podem coexistir com grandes lacunas temporais. Não há umidade no esquema da estação brasileira; essa variável não é adicionada artificialmente à contagem.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,6.6),gridspec_kw={'width_ratios':[1,1.65]})
        metas=[d['meta'] for d in [au,inv,est]]
        x=np.arange(3);bars=ax[0].bar(x,[m['linhas_excedentes_mesma_chave'] for m in metas],color=CORES)
        ax[0].bar_label(bars,padding=3);ax[0].set_xticks(x,['Austrália','BR inversores','BR estação'],rotation=25,ha='right')
        ax[0].set(ylabel='Linhas além da primeira da mesma chave',title='Duplicatas de timestamp e equipamento');ax[0].margins(y=.15)
        f=r['tabelas']['flags'];yy=np.arange(len(f));bars=ax[1].barh(yy,f.linhas_sinalizadas,color='#b34d3e')
        curtos=['AU potência','AU temperatura','AU umidade','AU GHI','BR potência/inversor','BR contador diário','BR contador total','BR temperatura','BR GHI']
        ax[1].bar_label(bars,padding=3);ax[1].set_yticks(yy,curtos)
        ax[1].invert_yaxis();ax[1].set(title='Valores sinalizados, preservados no arquivo',xlabel='Linhas sinalizadas (ver critérios na tabela)');ax[1].margins(x=.18)
        salvar(fig,'fig_3_2_07_duplicatas_suspeitos','Duplicatas e sinais de inconsistência nos dados crus',
               'Duplicata significa mesma chave temporal e equipamento, não necessariamente linhas idênticas. Critérios de triagem: temperatura fora de −20 a 60 °C; umidade fora de 0 a 100%; negativos nos demais campos selecionados. Não se afirma que todo valor sinalizado seja erro de sensor e nenhum valor é removido. Divergência entre duplicatas é auditada nas tabelas, incluindo diferenças entre ausência e presença de valor.')

        fig,ax=plt.subplots(2,1,figsize=(11.7,7.3))
        for d,cor in zip([au,inv,est],CORES):
            g=d['lacunas'];horas=g.minutos/60
            bins=np.logspace(np.log10(5/60),np.log10(max(1,r['tabelas']['lacunas'].minutos.max()/60)),35)
            ax[0].hist(horas,bins=bins,histtype='step',lw=1.5,color=cor,label=f"{d['meta']['fonte']} ({len(g)} lacunas)")
            h=d['lacunas_dia']
            if len(h):ax[1].hist(h.dias,bins=np.arange(.5,max(2,r['tabelas']['lacunas_dia'].dias.max())+1.5),histtype='step',lw=1.5,color=cor,label=f"{d['meta']['fonte']} ({len(h)} períodos)")
        ax[0].set(xscale='log',yscale='log',xlabel='Duração sem valor finito da variável principal (horas; escala log)',ylabel='Número de lacunas (escala log)',title='Interrupções na grade de cinco minutos')
        ax[1].set(xlabel='Dias civis consecutivos sem qualquer registro da fonte',ylabel='Número de períodos',title='Interrupções de dias inteiros')
        for a in ax:a.legend();a.grid(alpha=.2)
        salvar(fig,'fig_3_2_08_lacunas_cruas','Duração das lacunas antes do tratamento',
               'No painel superior: intervalos [t,t+5min) sem valor finito de potência australiana, potência por inversor brasileiro e temperatura da estação. Cada inversor tem sua própria sequência; as contagens de oito sequências não são diretamente comparáveis às de uma estação. Duração = número de intervalos ausentes × cinco minutos. No inferior, conta-se ausência de todos os registros da fonte, inclusive fora dos minutos exatos. Bordas do calendário estão incluídas; não se interpreta lacuna como falha física comprovada.')

        fig,a=plt.subplots(figsize=(10,4.8))
        for d,cor in zip([au,inv,est],CORES):a.plot(d['cobertura_horaria'].index,d['cobertura_horaria'],marker='o',ms=3,lw=1.2,label=d['meta']['fonte'],color=cor)
        a.set(xticks=range(0,24,2),xlabel='Hora registrada na Austrália / hora local no Brasil',ylabel='Posições com valor finito (%)',ylim=(-2,103),title='Disponibilidade da variável principal ao longo das 24 horas')
        a.legend();a.grid(alpha=.2)
        salvar(fig,'fig_3_2_09_disponibilidade_horaria','Perfil horário da disponibilidade original',
               'A grade considera as 24 horas. Zero de potência é um valor observado e não é marcado como faltante. Reduções noturnas de disponibilidade podem refletir política de aquisição; a figura não determina a causa. Austrália mantém a convenção temporal do arquivo sem fuso explícito; Brasil usa a apresentação local America/Sao_Paulo dos timestamps UTC.')
    salvar_json(r['pasta']/'indice_figuras.json',indice)
    texto='# Legendas das figuras — dados crus\n\nPNG em 300 dpi e PDF vetorial. Numeração a ajustar ao TCC.\n\n'
    for item in indice:texto+=f"## {item['arquivo']}\n\n{item['titulo']}\n\n{item['legenda']}\n\nFonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.\n\n"
    (r['pasta']/'legendas_figuras.md').write_text(texto,encoding='utf-8')
    r['indice_figuras']=indice
    return indice
