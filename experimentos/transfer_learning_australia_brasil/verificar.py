"""Verify original 5-minute targets, windows, frozen weights and saved metrics."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
import torch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
from energia_transfer.transfer_learning.dados import carregar,particao
from energia_transfer.transfer_learning.treinamento import prever,restaurar,erros

def main():
 pasta,cfg,ct=carregar();torch.set_num_threads(2)
 root=pasta.parents[1]
 frames={d:pd.read_pickle(root/f'data/processed/{d}/base_5min_{d}.pkl') for d in ['australia','brasil']}
 cont=pd.read_csv(pasta/'resultados/particoes.csv')
 for r in cont.itertuples():
  d=particao(pasta,r.dominio,r.lag,r.particao);t=pd.DatetimeIndex(d['datas'])
  f=frames[r.dominio];cap=cfg['capacidade_ac_kw'][r.dominio]
  assert t.is_unique and t.is_monotonic_increasing
  np.testing.assert_allclose(d['y_original'],f.Active_Power_original.reindex(t)/cap,atol=1e-7)
  np.testing.assert_allclose(d['persistencia'],f.Active_Power_original.reindex(t-pd.Timedelta(minutes=5))/cap,atol=1e-7)
  assert d['diurno'].all() and (d['fracao_alvo_estimada_pct']==0).all()
  for pos in range(r.lag):
   raw=f[ct['variaveis_por_passo']].reindex(t-pd.Timedelta(minutes=5*(r.lag-pos))).copy()
   raw['Active_Power']/=cap
   got=d['X'][:,pos]*np.array(ct['x_escala_treino'])+np.array(ct['x_media_treino'])
   np.testing.assert_allclose(got,raw.to_numpy(),atol=1e-6)
 src=frames['australia'].loc[:cfg['fim_treino_australia']]
 fit=src.loc[src.Active_Power_original.notna() & src.diurno,ct['variaveis_por_passo']].copy()
 fit.Active_Power/=cfg['capacidade_ac_kw']['australia']
 np.testing.assert_allclose(ct['x_media_treino'],fit.mean(),atol=1e-10)
 np.testing.assert_allclose(ct['x_escala_treino'],fit.std(ddof=0),atol=1e-10)
 pred=pd.read_csv(pasta/'resultados/teste_previsoes.csv');ms=pd.read_csv(pasta/'resultados/teste_metricas_por_seed.csv')
 total=0
 for lag in cfg['lags']:
  d=particao(pasta,'brasil',lag,'teste')
  for arq in cfg['arquiteturas']:
   for seed in cfg['seeds']:
    fonte=restaurar(pasta,cfg,ct,arq,lag,seed)
    for metodo in cfg['metodos']:
     modelo=restaurar(pasta,cfg,ct,arq,lag,seed,metodo)
     if metodo in ['cabeca','sem_ajuste']:
      assert all(torch.equal(v,fonte.encoder.state_dict()[k]) for k,v in modelo.encoder.state_dict().items())
     if metodo=='sem_ajuste':assert all(torch.equal(v,fonte.state_dict()[k]) for k,v in modelo.state_dict().items())
     v=pred.query('lag==@lag and arquitetura==@arq and seed==@seed and metodo==@metodo')
     assert list(v.timestamp)==list(d['datas'])
     np.testing.assert_allclose(v.previsto_kw,prever(modelo,d,ct)*cfg['capacidade_ac_kw']['brasil'],atol=1e-3,rtol=0)
     m=ms.query('lag==@lag and arquitetura==@arq and seed==@seed and metodo==@metodo').iloc[0]
     check=erros(v.real_kw,v.previsto_kw,v.persistencia_kw)
     np.testing.assert_allclose(m.RMSE_kw,check['RMSE_pu'],atol=1e-3)
     total+=1
 notebooks=[]
 for base in [root/'notebooks',root/'experimentos/australia_deep_learning/notebooks',pasta/'notebooks']:
  for arquivo in sorted(base.glob('[0-9][0-9]_*.ipynb')):
   n=json.loads(arquivo.read_text(encoding='utf-8'))
   assert all(c.get('execution_count') is not None for c in n['cells'] if c['cell_type']=='code')
   assert not any(o['output_type']=='error' for c in n['cells'] for o in c.get('outputs',[]))
   notebooks.append(str(arquivo.relative_to(root)))
 r={'resolucao':'5min','horizonte_minutos':5,'particoes':len(cont),'checkpoints_brasil_recarregados':total,
    'alvos_somente_medidos':True,'persistencia_t_menos_5min_medida':True,'janelas_conferidas':True,
    'escalas_so_fonte_treino':True,'encoder_congelado_preservado':True,'notebooks_executados':notebooks}
 (pasta/'resultados/verificacao.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(r,indent=2))
if __name__=='__main__':main()
