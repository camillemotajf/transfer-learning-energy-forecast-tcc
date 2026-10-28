"""Reproduz o pré-processamento diário existente e exporta material para a seção 3.3."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .chronos_experimentos import sha256, salvar_json
from .deep_learning.dados import limpar_diario, entradas_causais
from .chronos_diario_contadores import reconstruir_contadores, datas_validas, NUMERICAS
from .caracterizacao_bases_tcc import extrair_lacunas

COLS=['Active_Power','Weather_Temperature_Celsius','Weather_Relative_Humidity','Global_Horizontal_Radiation']
NOMES=['Potência','Temperatura','Umidade relativa','GHI']


def preparar_preprocessamento(raiz):
    raiz=Path(raiz).resolve();pasta=raiz/'reports/tcc/preprocessamento_diario';figuras=pasta/'figuras';tabdir=pasta/'tabelas'
    figuras.mkdir(parents=True,exist_ok=True);tabdir.mkdir(exist_ok=True)
    hist=raiz/'experimentos/transfer_learning_australia_brasil/historico_diario';exp=raiz/'experimentos/chronos_diario_contadores'
    arquivos=[raiz/'data/raw/australia/87-Site_DKA-M9_A+C-Phases.csv',raiz/'data/raw/australia/base_diaria_australia.csv',hist/'config.json',hist/'dados/australia_pu.csv',
              raiz/'data/raw/brasil/Leopoldo-fixa-inv.csv',raiz/'data/processed/brasil/leopoldo_diario_contadores_auditado.csv',
              raiz/'data/interim/meteorologia/meteorologia_era5_diaria.csv',exp/'resultados/benchmark_normalizacao.json',exp/'benchmark_config.json']
    for p in ['treino','validacao']:arquivos.append(hist/'dados'/f'australia_lag3_{p}.npz')
    for p in ['treino','validacao','teste']:arquivos.append(exp/'dados'/f'brasil_lag3_{p}.npz')
    hashes={str(p.relative_to(raiz)):sha256(p) for p in arquivos}
    cfg=json.loads(arquivos[2].read_text(encoding='utf-8'))
    raw=pd.read_csv(arquivos[0],usecols=['timestamp']+COLS)
    raw.timestamp=pd.to_datetime(raw.timestamp,format='mixed');raw=raw.set_index('timestamp').sort_index().loc[:'2023-12-31']
    medias=raw.resample('D').mean();contagens=raw.Active_Power.resample('D').count()
    recebida=pd.read_csv(arquivos[1],parse_dates=['timestamp']).set_index('timestamp').loc[:'2023-12-31',COLS].sort_index()
    qc={'limites_operacionais':cfg['limites_operacionais'],'limite_ffill_meteorologia_dias':cfg['limite_ffill_australia_dias']}
    original,limpo,invalidos=limpar_diario(recebida,qc);au,imputados=entradas_causais(limpo,qc)
    np.testing.assert_allclose(medias.reindex(original.index)[COLS],original[COLS],atol=1e-10,equal_nan=True)
    au_pu=pd.read_csv(arquivos[3],parse_dates=['timestamp']).set_index('timestamp')
    esperado=au.copy();esperado.Active_Power/=cfg['capacidade_ac_kw']['australia']
    np.testing.assert_allclose(esperado[au_pu.columns],au_pu,atol=1e-10,equal_nan=True)
    etapas=pd.DataFrame({'variavel':COLS,'ausentes_calendario':original[COLS].isna().sum().to_numpy(),
                        'invalidos_adicionais':invalidos[COLS].sum().to_numpy(),'ffill':imputados[COLS].sum().to_numpy(),'ausentes_finais':au[COLS].isna().sum().to_numpy()})
    cobertura=[];particoes=[]
    for part in ['treino','validacao']:
        with np.load(hist/'dados'/f'australia_lag3_{part}.npz',allow_pickle=False) as z:ds=pd.DatetimeIndex(z['datas'])
        c=contagens.reindex(ds)
        cobertura.append(dict(particao=part,alvos=len(ds),menos_95pct=int(c.lt(.95*288).sum()),entre_95_e_100=int((c.ge(.95*288)&c.lt(288)).sum()),completos=int(c.eq(288).sum()),menor_contagem=int(c.min())))
        particoes.append(dict(dominio='Austrália',particao=part,n=len(ds),inicio=ds.min(),fim=ds.max()))
    invraw=pd.read_csv(arquivos[4],usecols=['datetime','usine_code','equipment_name']+NUMERICAS,low_memory=False)
    diario,por_inv,falhas,meta_br=reconstruir_contadores(invraw)
    br=pd.read_csv(arquivos[5],parse_dates=['timestamp']).set_index('timestamp')
    pd.testing.assert_frame_equal(diario,br[diario.columns],check_dtype=False,check_freq=False,atol=1e-8)
    inv=invraw[invraw.usine_code.eq('07-07FX')].copy()
    inv['instante']=pd.to_datetime(inv.datetime,utc=True,errors='coerce').dt.tz_convert('America/Sao_Paulo').dt.floor('5min')
    inv=inv.dropna(subset=['instante','equipment_name'])
    for c in NUMERICAS:
        inv[c]=pd.to_numeric(inv[c],errors='coerce');inv.loc[inv[c]<0,c]=np.nan
    inv=inv.groupby(['instante','equipment_name'],as_index=False)[NUMERICAS].median()
    inv['dia']=inv.instante.dt.tz_localize(None).dt.normalize();inv=inv[inv.dia.dt.year.eq(2025)]
    idx=pd.MultiIndex.from_product([diario.index,meta_br['equipamentos']],names=['dia','equipment_name'])
    q=por_inv.reindex(idx)
    reg=inv.groupby(['dia','equipment_name']).size().reindex(idx,fill_value=0)
    h=inv.instante.dt.hour+inv.instante.dt.minute/60
    ini=inv[h<4].groupby(['dia','equipment_name']).total_power_yields_kwh.median().reindex(idx)
    fim=inv[h>=19].groupby(['dia','equipment_name']).total_power_yields_kwh.median().reindex(idx)
    motivos=pd.DataFrame(index=idx)
    motivos['sem_registro_no_dia']=reg.eq(0);motivos['sem_contador_diario_apos6']=q.energia_dia_kwh.isna()
    motivos['sem_borda_inicial']=ini.isna();motivos['sem_borda_final']=fim.isna()
    motivos['energia_fora_limite']=q.energia_dia_kwh.notna()&~q.energia_dia_kwh.between(0,1600)
    motivos['acumulado_negativo']=(fim-ini).lt(0)
    motivos['contadores_divergentes']=(q.energia_dia_kwh-(fim-ini)).abs().gt(np.maximum(8,.03*q.energia_dia_kwh))
    diarios=motivos.groupby(level=0).any();assert diarios.any(axis=1).equals(~diario.valido.rename_axis('dia'))
    tabela_motivos=pd.DataFrame({'motivo':diarios.columns,'dias_com_motivo':diarios.sum().to_numpy()})
    sem_reg=reg.groupby(level=0).sum().eq(0)
    estados=pd.DataFrame({'data':br.index,'estado':np.select([sem_reg.to_numpy(),~br.valido.to_numpy()],['Sem registros','Reprovado com registros'],default='Aprovado'),'n_consistentes':br.n_consistentes.to_numpy()})
    era=pd.read_csv(arquivos[6],parse_dates=['timestamp']).set_index('timestamp').reindex(br.index)
    np.testing.assert_allclose(era[COLS[1:]],br[COLS[1:]],atol=1e-10,equal_nan=True)
    meteo=pd.DataFrame({'variavel':COLS[1:],'dias_completos':era[COLS[1:]].notna().sum().to_numpy(),'ausentes':era[COLS[1:]].isna().sum().to_numpy(),'dias_calendario':len(br)})
    br_pu=br[cfg['variaveis']].copy();br_pu.Active_Power/=cfg['capacidade_ac_kw']['brasil']
    janelas={}
    for part in ['treino','validacao','teste']:
        with np.load(exp/'dados'/f'brasil_lag3_{part}.npz',allow_pickle=False) as z:janelas[part]={k:z[k].copy() for k in z.files}
        ds=pd.DatetimeIndex(janelas[part]['datas'])
        particoes.append(dict(dominio='Brasil',particao=part,n=len(ds),inicio=ds.min(),fim=ds.max()))
        np.testing.assert_allclose(janelas[part]['real_kw'],br.loc[ds].Active_Power,atol=1e-8)
    escala=json.loads(arquivos[7].read_text(encoding='utf-8'));bcfg=json.loads(arquivos[8].read_text(encoding='utf-8'))
    xt=np.asarray(janelas['treino']['X'],dtype=float);yt=np.asarray(janelas['treino']['y'],dtype=float)
    np.testing.assert_allclose(xt.mean(axis=(0,1)),escala['x_media'],atol=1e-8)
    np.testing.assert_allclose(xt.std(axis=(0,1)),escala['x_escala'],atol=1e-8)
    np.testing.assert_allclose([yt.mean(),yt.std()],[escala['y_media'],escala['y_escala']],atol=1e-8)
    escalas=pd.DataFrame({'variavel':bcfg['colunas_historicas'],'media_treino':escala['x_media'],'desvio_treino_ddof0':escala['x_escala']})
    escalas=pd.concat([escalas,pd.DataFrame([dict(variavel='Alvo y (potência p.u.)',media_treino=escala['y_media'],desvio_treino_ddof0=escala['y_escala'])])],ignore_index=True)
    funil=[];lacunas=[]
    for dom,frame in [('Austrália',au_pu),('Brasil',br_pu)]:
        n=len(datas_validas(frame,3,cfg['variaveis'][1:]))
        for etapa,valor in [('Calendário',len(frame)),('Alvo disponível',int(frame.Active_Power.notna().sum())),('Janela de 3 dias + alvo',n)]:funil.append(dict(dominio=dom,etapa=etapa,n=valor,pct=100*valor/len(frame)))
        g=extrair_lacunas(frame.Active_Power.isna());g['dominio']=dom;lacunas.append(g)
    out={'australia_etapas':etapas,'australia_cobertura_alvos':pd.DataFrame(cobertura),'brasil_motivos':tabela_motivos,'brasil_estados':estados,
         'meteorologia_era5':meteo,'escalas_treino_brasil':escalas,'particoes':pd.DataFrame(particoes),'funil_disponibilidade':pd.DataFrame(funil),
         'lacunas_alvo_diario':pd.concat(lacunas,ignore_index=True),'brasil_contadores_por_inversor':por_inv.reset_index(),
         'australia_diario_apos_tratamento':au.reset_index(),'brasil_diario_apos_tratamento':br.reset_index()}
    for nome,t in out.items():t.to_csv(tabdir/f'{nome}.csv',index=False)
    meta=dict(escopo='Reprodução do protocolo diário atual; sem alterar bases/modelos',australia_dias=len(au),brasil=meta_br,
              capacidades_ac_kw=cfg['capacidade_ac_kw'],limites_diarios=cfg['limites_operacionais'],ffill_meteorologia_au_dias=2,
              imputacao_potencia=False,meteorologia_br='ERA5 homogêneo; sem combinação com estação',
              normalizacao='Potência em p.u.; MLP/LSTM locais padronizam X/y somente com treino brasileiro. Chronos não recebe o padronizador externo.',
              codigo_sha256=sha256(Path(__file__)),fontes_sha256=hashes)
    salvar_json(pasta/'manifesto.json',meta)
    for rel,hsh in hashes.items():assert sha256(raiz/rel)==hsh
    return dict(raiz=raiz,pasta=pasta,figuras=figuras,tabelas_dir=tabdir,tabelas=out,meta=meta,au_original=original,au_limpo=limpo,au=au,au_imputados=imputados,au_pu=au_pu,
                br=br,br_pu=br_pu,por_inv=por_inv,janelas=janelas,escala=escala)


def gerar_figuras_preprocessamento(r):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap,BoundaryNorm
    t=r['tabelas'];indice=[]
    def salvar(fig,nome,titulo,legenda):
        fig.tight_layout();fig.savefig(r['figuras']/f'{nome}.png',dpi=300,facecolor='white');fig.savefig(r['figuras']/f'{nome}.pdf',facecolor='white');plt.close(fig)
        indice.append(dict(arquivo=nome,titulo=titulo,legenda=legenda))
    with plt.rc_context({'font.family':'DejaVu Serif','font.size':10,'axes.titlesize':11,'legend.fontsize':8,'pdf.fonttype':42,'axes.spines.top':False,'axes.spines.right':False}):
        fig,a=plt.subplots(figsize=(10,5.4));x=np.arange(4);g=t['australia_etapas'];largura=.19
        for k,(c,l,cor) in enumerate([('ausentes_calendario','Ausentes no calendário','#777777'),('invalidos_adicionais','Inválidos adicionais','#b34d3e'),('ffill','Preenchidos pelo passado','#3c8b72'),('ausentes_finais','Ausentes finais','#2166a1')]):
            b=a.bar(x+(k-1.5)*largura,g[c],largura,label=l,color=cor);a.bar_label(b,padding=2,fontsize=8)
        a.set_xticks(x,NOMES);a.set(ylabel='Número de dias',title='Austrália: efeito das etapas diárias',ylim=(0,47));a.legend(ncol=2);a.grid(axis='y',alpha=.2)
        salvar(fig,'fig_3_3_01_etapas_australia','Efeito das etapas de pré-processamento sobre a disponibilidade da base australiana',
               'Número de dias com valores ausentes, invalidados, preenchidos e ausentes após o tratamento, no calendário de 3812 dias até 31/12/2023. As ausências finais correspondem às ausências iniciais acrescidas das invalidações e descontadas as imputações. Os limites operacionais são aplicados às médias diárias. Apenas as variáveis meteorológicas recebem preenchimento; a potência permanece sem imputação.')

        fig,ax=plt.subplots(3,1,figsize=(10,8.2))
        for a,c,nome in zip(ax,COLS[1:],['Temperatura (°C)','Umidade relativa (%)','GHI (W/m²)']):
            d=r['au_imputados'].index[r['au_imputados'][c]][0];ini=d-pd.Timedelta(days=4);fim=d+pd.Timedelta(days=5)
            a.plot(r['au_original'].loc[ini:fim].index,r['au_original'].loc[ini:fim,c],marker='o',lw=.9,color='#777777',label='Média diária recebida')
            a.plot(r['au'].loc[ini:fim].index,r['au'].loc[ini:fim,c],marker='.',lw=1,color='#2166a1',label='Após controle e preenchimento')
            m=r['au_imputados'].loc[ini:fim,c];a.scatter(m.index[m],r['au'].loc[m.index[m],c],s=65,marker='x',color='#b34d3e',label='Preenchido pelo passado',zorder=4)
            a.set(ylabel=nome,title=f'Exemplo ao redor de {d.date()}');a.grid(alpha=.2);a.legend(loc='best',ncol=3)
        salvar(fig,'fig_3_3_02_exemplos_ffill','Exemplos do preenchimento causal meteorológico',
               'Séries diárias de temperatura, umidade relativa e GHI no entorno da primeira ocorrência de imputação de cada variável. O preenchimento propaga a última observação válida por até dois dias consecutivos, utilizando exclusivamente informações passadas. Os marcadores identificam os valores imputados. Os exemplos ilustram o procedimento e não constituem uma avaliação de sua precisão.')

        fig,a=plt.subplots(figsize=(9,5.3));g=t['australia_cobertura_alvos'];x=np.arange(2);base=np.zeros(2)
        for c,l,cor in [('menos_95pct','<95%','#b34d3e'),('entre_95_e_100','95% a <100%','#e5b451'),('completos','100%','#3c8b72')]:
            v=100*g[c]/g.alvos;a.bar(x,v,bottom=base,label=l,color=cor)
            for i,(n,h,b) in enumerate(zip(g[c],v,base)):
                if h>=4:a.text(i,b+h/2,str(n),ha='center',va='center')
            base+=v.to_numpy()
        a.text(.03,.98,'Treino: 10 dias <95%; 43 dias entre 95% e <100%',transform=a.transAxes,va='top',fontsize=8,bbox=dict(facecolor='white',alpha=.9,edgecolor='none'))
        a.set_xticks(x,['Treino (3392 alvos)','Validação (352 alvos)']);a.set(ylabel='Alvos da partição (%)',title='Cobertura das leituras de potência no alvo australiano',ylim=(0,101));a.legend(loc='upper center',bbox_to_anchor=(.5,-.08),ncol=3)
        salvar(fig,'fig_3_3_03_cobertura_alvos','Cobertura intradiária dos alvos australianos usados',
               'Distribuição dos alvos de treino e validação segundo a proporção de leituras de potência disponíveis em relação às 288 leituras esperadas por dia. Apresentam cobertura inferior a 95% dez dos 3392 alvos de treino e 84 dos 352 alvos de validação. O limiar de 95% é descritivo e não foi aplicado como critério de exclusão. A média das leituras disponíveis pode diferir da média integral de 24 horas.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.6));q=r['por_inv'];ok=np.isfinite(q.energia_dia_kwh)&np.isfinite(q.energia_pelo_acumulado)
        for flag,cor,label in [(True,'#3c8b72','Aprovado'),(False,'#b34d3e','Reprovado')]:
            s=q[ok&q.consistente.eq(flag)];ax[0].scatter(s.energia_dia_kwh,s.energia_pelo_acumulado,s=7,alpha=.5,color=cor,label=f'{label} (n={len(s)})')
        ax[0].plot([0,1200],[0,1200],ls='--',color='gray',lw=1);ax[0].set(xlabel='Máximo do contador diário após 06h (kWh)',ylabel='Diferença dos acumulados (kWh)',title='Concordância entre contadores por inversor');ax[0].legend();ax[0].grid(alpha=.2)
        labels=['Sem registros em algum inversor','Sem contador diário após 06h','Sem borda inicial (<04h)','Sem borda final (≥19h)','Energia fora de 0 a 1600 kWh','Acumulado negativo','Contadores divergentes']
        g=t['brasil_motivos'];b=ax[1].barh(range(len(g)),g.dias_com_motivo,color='#b45f06');ax[1].bar_label(b,padding=3);ax[1].set_yticks(range(len(g)),labels);ax[1].invert_yaxis();ax[1].set(title='Motivos de reprovação (podem se sobrepor)',xlabel='Dias com ao menos um inversor na condição');ax[1].margins(x=.15)
        salvar(fig,'fig_3_3_04_contadores_brasil','Consistência dos contadores e reprovação de dias brasileiros',
               'Comparação entre a energia do contador diário e a diferença do contador acumulado por inversor, restrita aos pares com valores numéricos finitos. O painel direito apresenta a frequência dos critérios de reprovação diária, incluindo ausência das observações necessárias nas bordas do dia. A aprovação exige concordância dos oito inversores. Os critérios podem ocorrer simultaneamente; suas contagens não são aditivas. A concordância representa consistência interna dos contadores.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,4.8));g=t['brasil_estados'].estado.value_counts().reindex(['Sem registros','Reprovado com registros','Aprovado'],fill_value=0)
        b=ax[0].bar(range(3),g,color=['#a63535','#e5b451','#3c8b72']);ax[0].bar_label(b,padding=3);ax[0].set_xticks(range(3),['Sem registros','Com registros,\nreprovado','Aprovado']);ax[0].set(ylabel='Dias de 2025',title='Resultado da validação diária',ylim=(0,320))
        g=t['meteorologia_era5'];b=ax[1].bar(range(3),g.dias_completos,color='#2166a1');ax[1].bar_label(b,padding=3);ax[1].set_xticks(range(3),NOMES[1:]);ax[1].set(ylabel='Dias de 2025',title='Meteorologia ERA5 disponível por dia',ylim=(0,410));ax[1].axhline(365,color='gray',ls='--',lw=1,label='Calendário: 365 dias');ax[1].legend(loc='lower left')
        salvar(fig,'fig_3_3_05_base_brasileira','Disponibilidade após reconstrução brasileira e meteorologia pública',
               'Classificação dos 365 dias de 2025 quanto à reconstrução do alvo brasileiro: 19 dias sem registros, 62 dias com registros reprovados e 284 dias aprovados. As três variáveis meteorológicas do ERA5 apresentam 364 dias completos, permanecendo ausentes em 01/01/2025. Os alvos diários não recebem imputação; as covariáveis meteorológicas provêm integralmente da reanálise.')

        fig,ax=plt.subplots(2,1,figsize=(11.7,6.7))
        for a,d,nome,cor in [(ax[0],r['au'],'Austrália: média das leituras disponíveis','#2166a1'),(ax[1],r['br'],'Brasil: energia validada / 24 h','#b45f06')]:
            a.plot(d.index,d.Active_Power,lw=.75,color=cor);a.set(title=nome,ylabel='Potência média diária (kW)',xlabel='Data');a.grid(alpha=.2)
        salvar(fig,'fig_3_3_06_alvos_diarios','Séries de potência média diária após o pré-processamento',
               'Potência média diária australiana calculada pela média aritmética das leituras disponíveis e potência média equivalente brasileira calculada pela soma da energia diária dos oito inversores aprovados dividida por 24 horas. As lacunas são preservadas no calendário e interrompem as séries. As bases apresentam períodos de observação e procedimentos de construção do alvo distintos.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.2))
        for a,dom,cor in zip(ax,['Austrália','Brasil'],['#2166a1','#b45f06']):
            g=t['funil_disponibilidade'].query('dominio == @dom');b=a.bar(range(3),g.pct,color=cor)
            a.bar_label(b,labels=[f'{n}\n({p:.1f}%)' for n,p in zip(g.n,g.pct)],padding=3,fontsize=9)
            a.set_xticks(range(3),['Calendário','Alvo disponível','Três dias anteriores\n+ alvo']);a.set(title=dom,ylabel='Fração do calendário (%)',ylim=(0,117));a.grid(axis='y',alpha=.2)
        salvar(fig,'fig_3_3_07_janelas','Disponibilidade de alvos e de janelas consecutivas',
               'Disponibilidade relativa ao calendário diário em três etapas: calendário completo, alvo disponível e janela elegível com três dias anteriores consecutivos e um alvo. São obtidas 3744 janelas australianas e 230 brasileiras; estas se distribuem em 160, 26 e 44 janelas de treino, validação e teste. O calendário é preservado e as janelas não atravessam dias sem potência válida. Janelas sobrepostas apresentam dependência temporal.')

        fig,ax=plt.subplots(1,2,figsize=(11.7,5.1))
        for d,label,cor in [(r['au_pu'],'Austrália: divisão por 24 kW','#2166a1'),(r['br_pu'],'Brasil: divisão por 1000 kW','#b45f06')]:ax[0].hist(d.Active_Power.dropna(),bins=30,density=True,histtype='step',lw=1.5,label=label,color=cor)
        ax[0].set(xlabel='Potência diária em p.u.',ylabel='Densidade',title='Normalização física por capacidade AC');ax[0].legend()
        for part,label,cor in [('treino','Treino','#2166a1'),('validacao','Validação','#b45f06'),('teste','Teste','#3c8b72')]:
            x=np.asarray(r['janelas'][part]['X'],dtype=float)[:,:,0].ravel();z=(x-r['escala']['x_media'][0])/r['escala']['x_escala'][0]
            ax[1].hist(z,bins=25,density=True,histtype='step',lw=1.5,color=cor,label=label)
        ax[1].set(xlabel='Histórico de potência padronizado (z)',ylabel='Densidade',title='MLP/LSTM: parâmetros ajustados só no treino');ax[1].legend()
        for a in ax:a.grid(alpha=.2)
        salvar(fig,'fig_3_3_08_escalas','Normalização física e padronização estatística',
               'À esquerda, distribuições da potência diária normalizada pelas capacidades AC adotadas de 24 kW e 1000 kW, respectivamente para Austrália e Brasil, sujeitas à confirmação documental. À direita, distribuições do histórico brasileiro após padronização pela média e pelo desvio padrão ajustados exclusivamente nas janelas de treino e mantidos na validação e no teste. Dias repetidos em janelas sobrepostas participam do ajuste. A padronização externa é utilizada nas MLP/LSTM locais; o Chronos recebe potência em p.u. e meteorologia em unidades físicas.')
    salvar_json(r['pasta']/'indice_figuras.json',indice)
    texto='# Legendas para a seção 3.3\n\nPNG: 300 dpi; PDF: vetorial. Numeração provisória.\n\n'
    for item in indice:texto+=f"## {item['arquivo']}\n\n{item['titulo']}\n\n{item['legenda']}\n\nFonte: elaboração própria com os arquivos e procedimentos identificados no manifesto.\n\n"
    (r['pasta']/'legendas_figuras.md').write_text(texto,encoding='utf-8');r['indice_figuras']=indice
    return indice
