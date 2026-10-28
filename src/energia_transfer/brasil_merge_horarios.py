"""Consolidação temporal brasileira para inspeção, sem imputação de potência."""
from pathlib import Path
import json

import numpy as np
import pandas as pd

from .chronos_experimentos import sha256

INVERSORES = [f'inverter{i}' for i in range(121, 129)]
COLUNAS_INV = ['total_active_power_w', 'total_dc_power_w', 'daily_power_yields_kwh',
               'monthly_power_yields_kwh', 'total_power_yields_kwh']
COLUNAS_EST = ['air_temperature_med', 'ghi_irr_med']
METADADOS_ESTACAO = {'datetime', 'real_datetime', 'usine_code', 'equipment_name', '_id', 'fail_read'}
TOTAIS_INVERSORES = {
    'total_active_power_w': 'potencia_total_w',
    'total_dc_power_w': 'potencia_dc_total_w',
    'daily_power_yields_kwh': 'energia_diaria_kwh',
    'monthly_power_yields_kwh': 'energia_mensal_kwh',
    'total_power_yields_kwh': 'energia_acumulada_kwh',
}


def adicionar_totais_inversores(base, equipamentos=INVERSORES):
    """Soma cada grandeza entre inversores no mesmo intervalo, nunca entre horários."""
    base=base.copy()
    for origem,destino in TOTAIS_INVERSORES.items():
        cols=[f'{origem}__{e}' for e in equipamentos]
        if not all(c in base for c in cols):
            continue
        valores=base[cols].replace([np.inf,-np.inf],np.nan)
        base[destino]=valores.sum(axis=1,min_count=len(equipamentos))
        base[f'{destino}__n_inversores']=valores.notna().sum(axis=1)
    for watts,kw in [('potencia_total_w','potencia_total_kw'),('potencia_dc_total_w','potencia_dc_total_kw')]:
        if watts in base:base[kw]=base[watts]/1000
    return base


def extrair_base_usina(base, colunas_estacao):
    """CSV compacto: totais de potência/energia e todos os canais físicos da estação."""
    principais=['potencia_total_w','potencia_total_kw','potencia_dc_total_w','potencia_dc_total_kw',
                'energia_diaria_kwh','energia_mensal_kwh','energia_acumulada_kwh',
                'n_inversores_com_registro','n_inversores_com_potencia','potencia_total_disponivel']
    contagens=[f'{destino}__n_inversores' for destino in TOTAIS_INVERSORES.values()]
    resultado=base[[c for c in principais+contagens if c in base]].copy()
    resultado.index.name='horario_local'
    equipamentos=sorted({c.split('__')[1] for c in base if c.startswith('estacao__')})
    for equipamento in equipamentos:
        for c in colunas_estacao:
            origem=f'estacao__{equipamento}__{c}'
            if origem in base:
                destino=c if len(equipamentos)==1 else f'{c}__{equipamento}'
                resultado[destino]=base[origem]
    return resultado


def colunas_fisicas_estacao(caminho):
    """Inclui os canais físicos da estação; exclui identificadores e diagnósticos."""
    return [c for c in pd.read_csv(caminho, nrows=0).columns
            if c not in METADADOS_ESTACAO and not c.startswith('meta.')]


def alinhar_fonte(original, colunas, ano=2025, usina='07-07FX'):
    """Uma mediana por equipamento e intervalo [t, t + 5 min), com rastreio."""
    dados = original.loc[original.usine_code.eq(usina)].copy()
    dados['linha_original_csv'] = dados.index + 2  # Cabeçalho na primeira linha.
    dados['datetime_original'] = dados.datetime
    dados['horario_local_original'] = pd.to_datetime(dados.datetime, utc=True, errors='coerce').dt.tz_convert('America/Sao_Paulo')
    dados['intervalo'] = dados.horario_local_original.dt.floor('5min').dt.tz_localize(None)
    invalidos = int((dados.intervalo.isna() | dados.equipment_name.isna()).sum())
    fora = int((dados.intervalo.notna() & dados.intervalo.dt.year.ne(ano)).sum())
    dados = dados.loc[dados.intervalo.dt.year.eq(ano) & dados.equipment_name.notna()].copy()
    dados['deslocamento_segundos'] = (dados.horario_local_original.dt.tz_localize(None) - dados.intervalo).dt.total_seconds()
    dados['timestamp_desalinhado'] = dados.deslocamento_segundos.ne(0)
    for coluna in colunas:
        dados[coluna] = pd.to_numeric(dados[coluna], errors='coerce').replace([np.inf, -np.inf], np.nan)
    grupo = dados.groupby(['intervalo', 'equipment_name'], sort=True)
    alinhados = grupo[colunas].median()
    alinhados['n_registros_originais'] = grupo.size()
    alinhados['n_registros_desalinhados'] = grupo.timestamp_desalinhado.sum()
    alinhados['maior_deslocamento_segundos'] = grupo.deslocamento_segundos.max()
    for coluna in colunas:
        alinhados[f'{coluna}__n_valores_finitos'] = grupo[coluna].count()
        alinhados[f'{coluna}__valores_divergentes'] = grupo[coluna].nunique().gt(1)
    mapa = dados[['linha_original_csv', 'datetime_original', 'horario_local_original', 'intervalo',
                  'equipment_name', 'deslocamento_segundos', 'timestamp_desalinhado']]
    meta = dict(linhas_usina=int(original.usine_code.eq(usina).sum()), linhas_no_ano=len(dados),
                linhas_com_chave_invalida=invalidos, linhas_fora_ano=fora,
                grupos_equipamento_intervalo=len(alinhados),
                registros_excedentes_consolidados=len(dados)-len(alinhados),
                registros_desalinhados=int(dados.timestamp_desalinhado.sum()))
    return alinhados, mapa, meta


def consolidar_inversores(alinhados, grade, equipamentos=INVERSORES):
    """Soma das potências no mesmo intervalo, exigindo todos os equipamentos."""
    presentes = set(alinhados.index.get_level_values('equipment_name'))
    desconhecidos = presentes.difference(equipamentos)
    if desconhecidos:
        raise ValueError(f'Equipamentos não previstos: {sorted(desconhecidos)}')
    partes=[]
    for coluna in alinhados.columns:
        larga = alinhados[coluna].unstack('equipment_name').reindex(index=grade, columns=equipamentos)
        larga.columns = [f'{coluna}__{nome}' for nome in equipamentos]
        partes.append(larga)
    base=pd.concat(partes,axis=1)
    base.index.name='horario_local'
    potencia = alinhados.total_active_power_w.unstack('equipment_name').reindex(index=grade, columns=equipamentos)
    registros = alinhados.n_registros_originais.unstack('equipment_name').reindex(index=grade, columns=equipamentos)
    base['n_inversores_com_registro'] = registros.notna().sum(axis=1)
    base['n_inversores_com_potencia'] = potencia.notna().sum(axis=1)
    base['n_inversores_com_potencia_negativa'] = potencia.lt(0).sum(axis=1)
    base['potencia_total_w'] = potencia.sum(axis=1, min_count=len(equipamentos))
    base['potencia_total_kw'] = base.potencia_total_w / 1000
    base['potencia_total_disponivel'] = base.n_inversores_com_potencia.eq(len(equipamentos))
    base['estado_potencia'] = np.select(
        [base.n_inversores_com_registro.eq(0), base.potencia_total_disponivel],
        ['Sem registros de inversores', 'Potência dos oito inversores disponível'],
        default='Registros presentes, potência incompleta')
    return adicionar_totais_inversores(base,equipamentos)


def preparar_merge_brasil(raiz, ano=2025):
    raiz = Path(raiz).resolve()
    pasta = raiz / 'reports/tcc/brasil_merge_horarios'
    pasta.mkdir(parents=True, exist_ok=True)
    invpath = raiz / 'data/raw/brasil/Leopoldo-fixa-inv.csv'
    estpath = raiz / 'data/raw/brasil/Leopoldo-fixa-est.csv'
    fontes = [invpath, estpath]
    hashes = {str(p.relative_to(raiz)): sha256(p) for p in fontes}
    inv = pd.read_csv(invpath, usecols=['datetime','usine_code','equipment_name']+COLUNAS_INV, low_memory=False)
    colunas_est = colunas_fisicas_estacao(estpath)
    est = pd.read_csv(estpath, usecols=['datetime','usine_code','equipment_name']+colunas_est, low_memory=False)
    inv, mapa_inv, meta_inv = alinhar_fonte(inv, COLUNAS_INV, ano=ano)
    est, mapa_est, meta_est = alinhar_fonte(est, colunas_est, ano=ano)
    grade = pd.date_range(f'{ano}-01-01', f'{ano}-12-31 23:55', freq='5min', name='horario_local')
    base = consolidar_inversores(inv, grade)
    partes_estacao=[]
    for coluna in est.columns:
        larga = est[coluna].unstack('equipment_name').reindex(grade)
        larga.columns = [f'estacao__{nome}__{coluna}' for nome in larga.columns]
        partes_estacao.append(larga)
    base=pd.concat([base,*partes_estacao],axis=1)
    usina=extrair_base_usina(base,colunas_est)
    pasta_dados=raiz/'data/interim/brasil'
    pasta_dados.mkdir(parents=True,exist_ok=True)
    usina.to_csv(pasta_dados/'brasil_merge_5_minutos.csv')
    cobertura_usina=pd.DataFrame([dict(variavel=c,intervalos_esperados=len(usina),
        intervalos_disponiveis=int(usina[c].notna().sum()),cobertura_pct=100*usina[c].notna().mean())
        for c in usina if c not in ['n_inversores_com_registro','n_inversores_com_potencia','potencia_total_disponivel']
        and not c.endswith('__n_inversores')])
    cobertura_usina.to_csv(pasta/'cobertura_csv_usina.csv',index=False)
    diario = base.resample('D').agg(
        intervalos_esperados=('potencia_total_disponivel','size'),
        intervalos_com_potencia_total=('potencia_total_disponivel','sum'),
        intervalos_sem_registros=('n_inversores_com_registro',lambda s: s.eq(0).sum()),
        intervalos_potencia_incompleta=('estado_potencia',lambda s: s.eq('Registros presentes, potência incompleta').sum()))
    diario['cobertura_potencia_total_pct'] = 100*diario.intervalos_com_potencia_total/diario.intervalos_esperados
    mensal = diario.iloc[:,:4].resample('MS').sum()
    mensal['cobertura_potencia_total_pct'] = 100*mensal.intervalos_com_potencia_total/mensal.intervalos_esperados
    cobertura = pd.DataFrame([dict(variavel=c, intervalos_esperados=len(base),
        intervalos_disponiveis=int(base[c].notna().sum()), cobertura_pct=100*base[c].notna().mean())
        for c in base if not any(k in c for k in ['__n_valores_finitos','__valores_divergentes','deslocamento','n_registros'])
        and (c.startswith('total_') or c.startswith('daily_') or c.startswith('monthly_') or c.startswith('estacao__') or c in ['potencia_total_w','potencia_total_kw'])])
    resumo = pd.DataFrame([dict(ano=ano, n_inversores=len(INVERSORES), intervalos_esperados=len(base),
        intervalos_com_potencia_total=int(base.potencia_total_disponivel.sum()),
        cobertura_potencia_total_pct=100*base.potencia_total_disponivel.mean(),
        intervalos_potencia_incompleta=int(base.estado_potencia.eq('Registros presentes, potência incompleta').sum()),
        intervalos_sem_registros=int(base.n_inversores_com_registro.eq(0).sum()))])
    for nome, tabela in [('brasil_merge_5min',base), ('cobertura_potencia_diaria',diario),
                         ('cobertura_potencia_mensal',mensal), ('inversores_consolidados',inv),
                         ('estacao_consolidada',est)]:
        tabela.to_csv(pasta/f'{nome}.csv')
    for nome, tabela in [('mapa_horarios_inversores',mapa_inv),('mapa_horarios_estacao',mapa_est),
                         ('cobertura_por_coluna',cobertura),('resumo_merge',resumo)]:
        tabela.to_csv(pasta/f'{nome}.csv',index=False)
    meta = dict(usina='07-07FX', ano=ano, fuso='America/Sao_Paulo',
        regra_temporal='datetime UTC convertido para horário local; floor de 5 min; intervalo [t, t+5 min)',
        regra_duplicatas='Mediana dos valores numéricos finitos por equipamento e intervalo',
        regra_potencia='Soma no mesmo intervalo, somente com oito valores disponíveis; W / 1000 = kW',
        regra_energia='Soma dos oito contadores no mesmo horário, separadamente para energia diária, mensal e acumulada. Não representa energia gerada nos cinco minutos.',
        arquivo_usina=str((pasta_dados/'brasil_merge_5_minutos.csv').relative_to(raiz)),
        ausencias='Sem interpolação, preenchimento ou substituição de ausências por zero',
        ressalvas=['Alinhamento por intervalo não garante simultaneidade no mesmo segundo.',
            'A soma das potências em um intervalo não é soma de energia ao longo do tempo.',
            'Valores negativos finitos são preservados e sinalizados para inspeção.',
            'Esta tabela não substitui a energia diária validada por contadores do experimento diário.',
            'Estação original mantida na escala recebida; não utiliza ERA5.'],
        inversores=meta_inv,estacao=meta_est,colunas_fisicas_estacao=colunas_est,
        fontes_sha256=hashes,codigo_sha256=sha256(Path(__file__)))
    (pasta/'manifesto.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for p in fontes:
        assert sha256(p)==hashes[str(p.relative_to(raiz))]
    assert base.index.is_unique and len(base)==len(grade)
    assert base.potencia_total_w.notna().equals(base.potencia_total_disponivel)
    assert (diario.intervalos_com_potencia_total+diario.intervalos_sem_registros+diario.intervalos_potencia_incompleta).equals(diario.intervalos_esperados)
    return dict(base=base, usina=usina, arquivo_usina=pasta_dados/'brasil_merge_5_minutos.csv',
                cobertura_usina=cobertura_usina, diario=diario, mensal=mensal, cobertura=cobertura,
                resumo=resumo, meta=meta, pasta=pasta, mapa_inversores=mapa_inv)


def gerar_figuras_merge(resultado):
    import matplotlib.pyplot as plt
    pasta=resultado['pasta'];arquivos=[]
    with plt.rc_context({'font.family':'DejaVu Serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42}):
        fig, ax=plt.subplots(figsize=(11.7,4.5))
        diario=resultado['diario']
        ax.plot(diario.index,diario.cobertura_potencia_total_pct,color='#2166a1',lw=.9)
        ax.set(title='Brasil: cobertura da potência total dos oito inversores após alinhamento temporal',
               ylabel='Intervalos com potência total disponível (%)',xlabel='Data',ylim=(-2,103))
        ax.grid(alpha=.2)
        nome='brasil_cobertura_potencia_total_5min'
        legenda='Cobertura diária da soma das potências dos oito inversores da usina 07-07FX, após alinhamento em intervalos de cinco minutos no horário local. O denominador é de 288 intervalos por dia. A potência total é disponibilizada somente quando os oito inversores possuem valores numéricos finitos no intervalo; registros repetidos são consolidados pela mediana. Os valores ausentes são preservados.'
        for ext in ['png','pdf']:
            fig.tight_layout();fig.savefig(pasta/f'{nome}.{ext}',dpi=300,facecolor='white')
        plt.close(fig);arquivos.append(dict(arquivo=nome,legenda=legenda))
    (pasta/'legendas_figuras.md').write_text('# Potência total após alinhamento temporal\n\n'+legenda+'\n\nFonte: elaboração própria a partir dos registros dos inversores da usina Leopoldo.\n',encoding='utf-8')
    return arquivos
