"""Auditoria descritiva dos CSVs originais: nenhuma imputação ou correção de valores."""
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
    """Conta existência por chave; não calcula média/mediana nem altera valores originais.

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


def tabelas_cobertura_potencia_australia(diario):
    """Cobertura exclusiva de Active_Power, independente das outras variáveis."""
    diaria = diario[['posicoes_esperadas', 'posicoes_com_Active_Power']].rename(columns={
        'posicoes_esperadas': 'intervalos_esperados',
        'posicoes_com_Active_Power': 'intervalos_com_potencia'})
    diaria.index.name = 'data'
    mensal = diaria.resample('MS').sum()
    mensal.index.name = 'mes'
    for tabela in (diaria, mensal):
        tabela['cobertura_potencia_pct'] = 100 * tabela.intervalos_com_potencia / tabela.intervalos_esperados
    esperados = int(diaria.intervalos_esperados.sum())
    presentes = int(diaria.intervalos_com_potencia.sum())
    resumo = pd.DataFrame([dict(variavel='Active_Power', inicio=str(diaria.index.min().date()),
        fim=str(diaria.index.max().date()), intervalos_esperados=esperados,
        intervalos_com_potencia=presentes, intervalos_sem_potencia=esperados-presentes,
        cobertura_potencia_pct=100*presentes/esperados)])
    return {'australia_cobertura_potencia_diaria': diaria.reset_index(),
            'australia_cobertura_potencia_mensal': mensal.reset_index(),
            'australia_cobertura_potencia_resumo': resumo}


def preparar_caracterizacao(raiz):
    raiz=Path(raiz).resolve(); pasta=raiz/'reports/tcc/caracterizacao_dados_crus'
    figuras=pasta/'figuras'; tabelas=pasta/'tabelas'
    figuras.mkdir(parents=True,exist_ok=True);tabelas.mkdir(exist_ok=True)
    specs=[('australia','Austrália',raiz/'data/raw/australia/87-Site_DKA-M9_A+C-Phases.csv',COLUNAS_AU,'timestamp',None,None,None),
           ('brasil_inversores','Brasil: inversores',raiz/'data/raw/brasil/Leopoldo-fixa-inv.csv',COLUNAS_INV,'datetime','equipment_name','07-07FX',2025),
           ('brasil_estacao','Brasil: estação',raiz/'data/raw/brasil/Leopoldo-fixa-est.csv',COLUNAS_EST,'datetime','equipment_name','07-07FX',2025)]
    hashes={str(s[2].relative_to(raiz)):sha256(s[2]) for s in specs}
    dados={}
    for key,nome,path,cols,tempo,equip,codigo,ano in specs:
        print(f'Lendo arquivo original: {nome}',flush=True)
        dados[key]=_auditar(path,nome,cols,tempo,equip,codigo,ano)
    resumo=pd.DataFrame([d['meta'] for d in dados.values()])
    tabelas_dados={'resumo_fontes':resumo}
    tabelas_dados.update(tabelas_cobertura_potencia_australia(dados['australia']['diario']))
    for nome in ['estatisticas','taxas','flags','lacunas','lacunas_dia']:
        tabelas_dados[nome]=pd.concat([d[nome] for d in dados.values()],ignore_index=True)
    for key,d in dados.items():
        tabelas_dados[f'{key}_por_dia']=d['diario'].reset_index()
        tabelas_dados[f'{key}_inventario_colunas']=d['inventario']
        tabelas_dados[f'{key}_cobertura_por_equipamento']=d['matriz'].reset_index()
    for nome,t in tabelas_dados.items(): t.to_csv(tabelas/f'{nome}.csv',index=False)
    meta=dict(escopo='Somente CSVs originais; Austrália integral 2013 a 2025; Brasil código 07-07FX em calendário de 2025',
              imputacao=False,correcao_de_valores=False,remocao_de_duplicatas=False,agregacao_de_alvos=False,
              denominadores='288 intervalos [t,t+5min) por dia e equipamento; comparação separada com chaves de timestamp exato',
              disponibilidade='Existência em intervalo de cinco minutos e de valor finito. Apenas máscaras de contagem; nenhum valor duplicado é consolidado e os timestamps originais são preservados.',
              ressalvas=['Grade diária completa é uma referência; bordas do arquivo e períodos anteriores ao início da aquisição não comprovam falha.',
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
        ax[0].plot(d.index,d.cobertura_Active_Power_pct,lw=.65,color=CORES[0])
        ax[0].set(title='Austrália: cobertura diária dos dados originais de potência',ylabel='Intervalos com potência disponível (%)',ylim=(-2,102));ax[0].grid(alpha=.2)
        mensal=d.posicoes_com_Active_Power.groupby([d.index.year,d.index.month]).sum()/d.posicoes_esperadas.groupby([d.index.year,d.index.month]).sum()*100
        mat=mensal.unstack().reindex(columns=range(1,13))
        im=ax[1].imshow(np.ma.masked_invalid(mat),aspect='auto',vmin=0,vmax=100,cmap='cividis')
        ax[1].set_xticks(range(12),MESES);ax[1].set_yticks(range(len(mat)),mat.index)
        ax[1].set(ylabel='Ano',xlabel='Mês',title='Cobertura mensal dos dados originais de potência')
        fig.colorbar(im,ax=ax[1],label='Intervalos com potência disponível (%)',pad=.01)
        salvar(fig,'fig_3_2_01_cobertura_australia','Cobertura temporal dos dados originais de potência da base australiana',
               'Cobertura diária e mensal da variável Active_Power entre 25/07/2013 e 23/08/2025. A cobertura corresponde à proporção de intervalos de cinco minutos com ao menos um valor numérico finito de potência, considerando 288 intervalos esperados por dia, inclusive nas datas inicial e final. Intervalos sem registro ou sem potência numérica finita são considerados indisponíveis; zeros são observações disponíveis. As demais variáveis não participam deste indicador. As regiões em branco representam meses externos ao período de observação.')

        fig,ax=plt.subplots(2,1,figsize=(11.7,7),sharex=True)
        mat=inv['matriz'];x0=mdates.date2num(mat.index[0]);x1=mdates.date2num(mat.index[-1]+pd.Timedelta(days=1))
        im=ax[0].imshow(mat.to_numpy().T,aspect='auto',origin='lower',extent=[x0,x1,-.5,len(mat.columns)-.5],vmin=0,vmax=100,cmap='cividis')
        ax[0].set_yticks(range(len(mat.columns)),[c.replace('inverter','Inv. ') for c in mat.columns]);ax[0].set(title='Brasil: cobertura dos dados originais de potência por inversor',ylabel='Equipamento')
        fig.colorbar(im,ax=ax[0],label='Posições com valor finito / 288 (%)',pad=.01)
        dd=inv['diario'];ax[1].plot(dd.index,dd.cobertura_total_active_power_w_pct,label='Cobertura por equipamento e intervalo',color=CORES[1],lw=.9)
        ax[1].plot(dd.index,dd.cobertura_todos_equipamentos_pct,label='Intervalos com os oito inversores',color=CORES[2],lw=.8)
        ax[1].plot(dd.index,dd.cobertura_registro_exato_pct,label='Registros em timestamp exato (diagnóstico)',color='#777777',lw=.6,ls='--')
        ax[1].set(ylabel='Cobertura (%)',xlabel='Mês de 2025',ylim=(-2,103));ax[1].legend();ax[1].grid(alpha=.2)
        ax[1].xaxis.set_major_locator(mdates.MonthLocator());ax[1].xaxis.set_major_formatter(mdates.DateFormatter('%m'))
        salvar(fig,'fig_3_2_02_cobertura_inversores','Cobertura temporal dos dados originais dos inversores brasileiros',
               'Disponibilidade de potência dos oito inversores da usina 07-07FX no calendário local de 2025. O painel superior apresenta a cobertura por equipamento; o inferior compara a cobertura sobre 2304 combinações de equipamento e intervalo por dia, a presença simultânea dos oito inversores em 288 intervalos diários e a presença de registros nos horários exatos da grade. A contagem por intervalos [t, t + 5 min) admite diferenças de segundos entre registros, sem modificar seus horários ou valores.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.6),sharey=True)
        for a,d,c,titulo in [(ax[0],inv,'total_active_power_w','Potência dos inversores (2304 posições/dia)'),(ax[1],est,'air_temperature_med','Temperatura da estação (288 posições/dia)')]:
            m=np.full((12,31),np.nan)
            for data,valor in d['diario'][f'cobertura_{c}_pct'].items():m[data.month-1,data.day-1]=valor
            im=a.imshow(np.ma.masked_invalid(m),aspect='auto',vmin=0,vmax=100,cmap='cividis')
            a.set_xticks([0,4,9,14,19,24,30],[1,5,10,15,20,25,31]);a.set_yticks(range(12),MESES)
            a.set(title=titulo,xlabel='Dia do mês',ylabel='Mês de 2025');fig.colorbar(im,ax=a,label='Posições com valor finito (%)',orientation='horizontal',pad=.14,fraction=.05)
        salvar(fig,'fig_3_2_03_calendario_brasil','Calendário de cobertura dos dados originais brasileiros',
               'Cobertura diária de potência dos inversores e temperatura da estação meteorológica em 2025, anterior ao tratamento. Os denominadores são 2304 combinações de equipamento e intervalo para os inversores e 288 intervalos para a estação. A cobertura considera a presença de valores numéricos finitos. Zero indica ausência de valores disponíveis; células em branco correspondem a datas inexistentes no mês.')

        fig,ax=plt.subplots(1,3,figsize=(11.7,5.7),sharey=True)
        labels=[['Potência','Temperatura','Umidade','GHI'],['Potência','Contador diário','Contador total'],['Temperatura','GHI']]
        for a,d,lab in zip(ax,[au,inv,est],labels):
            t=d['taxas'];x=np.arange(len(t));base=np.zeros(len(t))
            for col,label,cor in [('sem_registro','Sem registro','#b34d3e'),('registro_sem_valor_finito','Registro sem valor finito','#e5b451'),('com_valor_finito','Valor finito presente','#3c8b72')]:
                v=t[col].to_numpy()/t.esperados.to_numpy()*100;a.bar(x,v,bottom=base,color=cor,label=label);base+=v
            a.set_xticks(x,lab,rotation=50,ha='right');a.set(title=d['meta']['fonte'],ylabel='Posições esperadas (%)',ylim=(0,100))
            a.grid(axis='y',alpha=.15)
        handles,ls=ax[0].get_legend_handles_labels();fig.legend(handles,ls,loc='upper center',bbox_to_anchor=(.5,.99),ncol=3,frameon=False)
        salvar(fig,'fig_3_2_04_disponibilidade_variaveis','Disponibilidade das variáveis nos intervalos de aquisição esperados',
               'Distribuição dos intervalos esperados entre ausência de registro, registro sem valor numérico finito e presença de ao menos um valor numérico finito. As classes são mutuamente exclusivas e calculadas por equipamento em intervalos de cinco minutos. Registros repetidos não aumentam a cobertura. Valores finitos fora dos limites de triagem permanecem classificados como disponíveis; disponibilidade não implica validade física.')

        fig,ax=plt.subplots(2,3,figsize=(11.7,7.2))
        series=[(au,'Active_Power','Potência australiana (kW)'),(inv,'total_active_power_w','Potência por inversor brasileiro (W)'),(au,'Weather_Relative_Humidity','Umidade australiana (%)'),
                (au,'Weather_Temperature_Celsius','Temperatura (°C)'),(au,'Global_Horizontal_Radiation','GHI australiano (W/m²)'),(est,'ghi_irr_med','GHI brasileiro (escala original do CSV)')]
        for a,(d,c,titulo) in zip(ax.flat,series):
            s=d['numericos'][c];s=s[np.isfinite(s)]
            a.hist(s,bins=60,density=True,histtype='step',lw=1.3,color=CORES[[au is d,inv is d,est is d].index(True)],label=d['meta']['fonte'])
            if c=='Weather_Temperature_Celsius':
                ss=est['numericos'].air_temperature_med;ss=ss[np.isfinite(ss)]
                a.hist(ss,bins=60,density=True,histtype='step',lw=1.3,color=CORES[2],label='Brasil: estação')
            a.set(xlabel=titulo,ylabel='Densidade');a.legend(fontsize=7);a.grid(alpha=.2)
        salvar(fig,'fig_3_2_05_distribuicoes_originais','Distribuições das variáveis nos dados originais',
               'Histogramas de densidade dos valores numéricos finitos, preservando registros duplicados, zeros, valores negativos e observações sinalizadas na triagem. A potência australiana representa o sistema em kW; a brasileira representa cada inversor em W. O GHI da estação brasileira é apresentado na escala original, sem correção de unidade ou calibração. Os períodos de observação diferem entre as fontes.')

        fig,ax=plt.subplots(1,3,figsize=(11.7,5.3))
        for a,d,lab in zip(ax,[au,inv,est],labels):
            t=d['estatisticas'];pct=100*t.vazios/t.linhas
            bars=a.bar(np.arange(len(t)),pct,color=CORES[0]);a.bar_label(bars,labels=[f'{n}\n({p:.2f}%)' for n,p in zip(t.vazios,pct)],padding=3,fontsize=8)
            a.set_xticks(range(len(t)),lab,rotation=50,ha='right');a.set(title=d['meta']['fonte'],ylabel='Linhas do CSV com campo vazio (%)',ylim=(0,max(5,pct.max()*1.4)))
            a.grid(axis='y',alpha=.2)
        salvar(fig,'fig_3_2_06_campos_vazios','Campos vazios nas linhas presentes dos arquivos originais',
               'Número e proporção de campos vazios nas linhas existentes de cada fonte, incluindo registros duplicados. O denominador corresponde às linhas selecionadas do arquivo, sem contabilizar intervalos sem registro. A umidade relativa não integra o esquema da estação brasileira e não é incluída nesta contagem.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,6.6),gridspec_kw={'width_ratios':[1,1.65]})
        metas=[d['meta'] for d in [au,inv,est]]
        x=np.arange(3);bars=ax[0].bar(x,[m['linhas_excedentes_mesma_chave'] for m in metas],color=CORES)
        ax[0].bar_label(bars,padding=3);ax[0].set_xticks(x,['Austrália','BR inversores','BR estação'],rotation=25,ha='right')
        ax[0].set(ylabel='Linhas além da primeira da mesma chave',title='Duplicatas de timestamp e equipamento');ax[0].margins(y=.15)
        f=r['tabelas']['flags'];yy=np.arange(len(f));bars=ax[1].barh(yy,f.linhas_sinalizadas,color='#b34d3e')
        curtos=['AU potência','AU temperatura','AU umidade','AU GHI','BR potência/inversor','BR contador diário','BR contador total','BR temperatura','BR GHI']
        ax[1].bar_label(bars,padding=3);ax[1].set_yticks(yy,curtos)
        ax[1].invert_yaxis();ax[1].set(title='Valores sinalizados, preservados no arquivo',xlabel='Linhas sinalizadas (ver critérios na tabela)');ax[1].margins(x=.18)
        salvar(fig,'fig_3_2_07_duplicatas_suspeitos','Duplicatas e sinais de inconsistência nos dados originais',
               'À esquerda, número de registros excedentes para a mesma combinação de horário e equipamento. À direita, observações sinalizadas pelos critérios de triagem: temperatura fora de −20 a 60 °C, umidade relativa fora de 0 a 100% e valores negativos nas demais variáveis selecionadas. A sinalização identifica observações para inspeção e não determina sua exclusão ou comprova erro de medição.')

        fig,ax=plt.subplots(2,1,figsize=(11.7,7.3))
        for d,cor in zip([au,inv,est],CORES):
            g=d['lacunas'];horas=g.minutos/60
            bins=np.logspace(np.log10(5/60),np.log10(max(1,r['tabelas']['lacunas'].minutos.max()/60)),35)
            ax[0].hist(horas,bins=bins,histtype='step',lw=1.5,color=cor,label=f"{d['meta']['fonte']} ({len(g)} lacunas)")
            h=d['lacunas_dia']
            if len(h):ax[1].hist(h.dias,bins=np.arange(.5,max(2,r['tabelas']['lacunas_dia'].dias.max())+1.5),histtype='step',lw=1.5,color=cor,label=f"{d['meta']['fonte']} ({len(h)} períodos)")
        ax[0].set(xscale='log',yscale='log',xlabel='Duração sem valor finito da variável principal (horas; escala log)',ylabel='Número de lacunas (escala log)',title='Interrupções na grade de cinco minutos')
        ax[1].set(xlabel='Dias consecutivos sem qualquer registro da fonte',ylabel='Número de períodos',title='Interrupções de dias inteiros')
        for a in ax:a.legend();a.grid(alpha=.2)
        salvar(fig,'fig_3_2_08_lacunas_originais','Distribuição da duração das lacunas nos dados originais',
               'O painel superior apresenta sequências de intervalos de cinco minutos sem valor numérico finito de potência australiana, potência por inversor brasileiro ou temperatura da estação. A duração corresponde ao número de intervalos consecutivos multiplicado por cinco minutos. O painel inferior apresenta sequências de dias sem qualquer registro da fonte. As lacunas dos inversores são contadas separadamente por equipamento; ambos os painéis incluem as bordas do calendário.')

        fig,a=plt.subplots(figsize=(10,4.8))
        for d,cor in zip([au,inv,est],CORES):a.plot(d['cobertura_horaria'].index,d['cobertura_horaria'],marker='o',ms=3,lw=1.2,label=d['meta']['fonte'],color=cor)
        a.set(xticks=range(0,24,2),xlabel='Hora registrada na Austrália / hora local no Brasil',ylabel='Posições com valor finito (%)',ylim=(-2,103),title='Disponibilidade da variável principal ao longo das 24 horas')
        a.legend();a.grid(alpha=.2)
        salvar(fig,'fig_3_2_09_disponibilidade_horaria','Perfil horário da disponibilidade original',
               'Proporção de intervalos de cinco minutos com valor numérico finito por hora do dia, considerando potência australiana, potência dos inversores brasileiros e temperatura da estação. Valores nulos de potência são contabilizados como observados. Os horários seguem a convenção do arquivo australiano e o fuso America/Sao_Paulo para os registros brasileiros. O perfil descreve a disponibilidade sem atribuir causas às interrupções.')
    salvar_json(r['pasta']/'indice_figuras.json',indice)
    texto='# Legendas das figuras: caracterização dos dados originais\n\nPNG em 300 dpi e PDF vetorial. Numeração provisória.\n\n'
    for item in indice:texto+=f"## {item['arquivo']}\n\n{item['titulo']}\n\n{item['legenda']}\n\nFonte: elaboração própria com os CSVs originais identificados por SHA-256 no manifesto.\n\n"
    (r['pasta']/'legendas_figuras.md').write_text(texto,encoding='utf-8')
    r['indice_figuras']=indice
    return indice
