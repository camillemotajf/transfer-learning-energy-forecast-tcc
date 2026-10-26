"""Bases reais de cinco minutos, auditoria e reconstrução estritamente causal.

As médias diárias não entram nesta etapa. Alvos nunca são imputados.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge

from .caminhos import CaminhosProjeto
from .auditoria_base_original import _limpar
from .deep_learning.dados import sha256

METEO = ["Weather_Temperature_Celsius", "Weather_Relative_Humidity", "Global_Horizontal_Radiation"]
CALENDARIO = ["hora_sin", "hora_cos", "dia_ano_sin", "dia_ano_cos"]
COLUNAS = ["Active_Power", *CALENDARIO]
PASSO = pd.Timedelta(minutes=5)


def preencher_passado(serie, limite=3):
    """Limita a idade do último valor medido; não encadeia estimativas."""
    return serie.ffill(limit=limite)


def calendario(frame):
    frame = frame.copy()
    minutos = frame.index.hour * 60 + frame.index.minute
    frame["hora_sin"] = np.sin(2*np.pi*minutos/1440)
    frame["hora_cos"] = np.cos(2*np.pi*minutos/1440)
    ano = np.where(frame.index.is_leap_year, 366., 365.)
    frame["dia_ano_sin"] = np.sin(2*np.pi*(frame.index.dayofyear-1)/ano)
    frame["dia_ano_cos"] = np.cos(2*np.pi*(frame.index.dayofyear-1)/ano)
    return frame


def proxy_causal(potencia, falhas, escuro, max_pontos=3):
    """Outros sete no instante + razão observada anterior; sem extremo futuro."""
    original = potencia.copy().astype(float)
    resultado = original.copy()
    origem = pd.DataFrame("ausente", index=original.index, columns=original.columns).mask(original.notna(), "observado")
    saudavel = falhas.fillna(0).eq(0)
    for equipamento in original.columns:
        outros = original.columns[original.columns != equipamento]
        soma = original[outros].sum(axis=1, min_count=7)
        doadores = saudavel[outros].all(axis=1) & original[outros].le(131250).all(axis=1)
        razao = (original[equipamento]/soma).where(original[equipamento].gt(1000) & soma.gt(7000) & saudavel[equipamento] & doadores)
        coeficiente = razao.rolling("30D", closed="left", min_periods=100).median()
        falta = original[equipamento].isna()
        grupos = falta.ne(falta.shift()).cumsum()
        idade = falta.groupby(grupos).cumsum()
        estimada = soma*coeficiente
        pode = falta & idade.le(max_pontos) & doadores & saudavel[equipamento] & estimada.between(0,131250)
        resultado.loc[pode, equipamento] = estimada.loc[pode]
        origem.loc[pode, equipamento] = "proxy_causal"
        # Hipótese física fixada antes do estudo, sem consultar valores futuros.
        # Nunca sobrescreve uma leitura medida, mesmo durante a noite.
        noite = falta & escuro
        resultado.loc[noite,equipamento] = 0.
        origem.loc[noite,equipamento] = "zero_fisico"
    return resultado, origem


def _solar(index, lat, lon, tz, altitude):
    local = index.tz_localize(tz)
    return pvlib.solarposition.get_solarposition(local, lat, lon, altitude=altitude).apparent_elevation.to_numpy()


def _auditar(frame, nome, saida):
    """Contagem por variável/dia, inclusive ausência de registro e maiores blocos."""
    linhas = []
    lacunas=[]
    extras=[c for c in ["temperatura_estacao_original","ghi_estacao_original_escala_nao_validada"] if c in frame]
    for coluna in ["Active_Power_original", *METEO,*extras]:
        serie = frame[coluna]
        falta = serie.isna()
        grupo = falta.ne(falta.shift()).cumsum()
        gaps=pd.DataFrame({"t":frame.index,"grupo":grupo.to_numpy(),"falta":falta.to_numpy()})
        gaps=gaps.loc[gaps.falta].groupby("grupo").agg(inicio=("t","min"),fim=("t","max"),pontos=("t","size")).reset_index(drop=True)
        gaps["variavel"],gaps["duracao_min"],gaps["dominio"]=coluna,gaps.pontos*5,nome
        lacunas.append(gaps)
        tamanho = falta.groupby(grupo).transform("sum").where(falta,0)
        tabela = pd.DataFrame({"faltantes": falta, "faltantes_diurnos": falta & frame.diurno,
                              "validos": serie.notna(), "registro_ausente": ~frame.registro_original,
                              "maior_lacuna_global_min": tamanho*5}, index=frame.index).resample("D").agg(
                                  {"faltantes":"sum","faltantes_diurnos":"sum","validos":"sum","registro_ausente":"sum","maior_lacuna_global_min":"max"})
        tabela["esperados"] = frame[coluna].resample("D").size()
        tabela["faltantes_pct"] = 100*tabela.faltantes/tabela.esperados
        tabela["variavel"], tabela["dominio"] = coluna, nome
        linhas.append(tabela.reset_index())
    diario = pd.concat(linhas,ignore_index=True)
    diario.to_csv(saida/f"faltantes_{nome}_por_dia.csv",index=False)
    pd.concat(lacunas,ignore_index=True).to_csv(saida/f"lacunas_{nome}_5min.csv",index=False)
    resumo = diario.groupby("variavel").agg(esperados=("esperados","sum"), faltantes=("faltantes","sum"),
        faltantes_diurnos=("faltantes_diurnos","sum"), maior_lacuna_min=("maior_lacuna_global_min","max")).reset_index()
    resumo["faltantes_pct"] = 100*resumo.faltantes/resumo.esperados
    resumo.to_csv(saida/f"faltantes_{nome}_resumo.csv",index=False)
    valida = frame.Active_Power.notna()
    grupos = (valida.ne(valida.shift()) | frame.index.to_series().diff().ne(PASSO)).cumsum()
    blocos = pd.DataFrame({"timestamp":frame.index,"valido":valida.to_numpy(),"grupo":grupos.to_numpy()})
    blocos = blocos.loc[blocos.valido].groupby("grupo").agg(inicio=("timestamp","min"), fim=("timestamp","max"), pontos=("timestamp","size")).reset_index(drop=True)
    blocos["duracao_min"] = blocos.pontos*5
    blocos.to_csv(saida/f"blocos_{nome}_5min.csv",index=False)
    return resumo


def auditar_bases():
    c=CaminhosProjeto()
    saida=c.raiz/"reports/intradiario"
    frames={d:pd.read_pickle(c.raiz/f"data/processed/{d}/base_5min_{d}.pkl") for d in ["australia","brasil"]}
    for d,f in frames.items(): _auditar(f,d,saida)
    auditar_invalidos_fonte()
    _graficos_auditoria(frames["australia"],frames["brasil"],saida)
    return {d:pd.read_csv(saida/f"faltantes_{d}_resumo.csv") for d in frames}


def auditar_invalidos_fonte():
    c=CaminhosProjeto()
    f=pd.read_csv(c.brutos_australia/"87-Site_DKA-M9_A+C-Phases.csv",usecols=["timestamp","Active_Power",*METEO],parse_dates=["timestamp"]).set_index("timestamp")
    tabelas=[]
    for col,lim in zip(["Active_Power",*METEO],[(0,25.2),(-20,60),(0,100),(0,1500)]):
        ruim=f[col].notna() & ~f[col].between(*lim)
        d=pd.DataFrame({"campos_vazios":f[col].isna(),"invalidos_operacionais":ruim},index=f.index).resample("D").sum()
        d["variavel"]=col;tabelas.append(d.reset_index())
    pd.concat(tabelas,ignore_index=True).to_csv(c.raiz/"reports/intradiario/invalidos_australia_por_dia.csv",index=False)


def gerar_bases():
    c = CaminhosProjeto()
    saida = c.raiz/"reports/intradiario"
    saida.mkdir(parents=True,exist_ok=True)
    au_arquivo = c.brutos_australia/"87-Site_DKA-M9_A+C-Phases.csv"
    au = pd.read_csv(au_arquivo,usecols=["timestamp","Active_Power",*METEO],parse_dates=["timestamp"])
    linhas_au, duplicatas_au = len(au), int(au.timestamp.duplicated().sum())
    au = au.sort_values("timestamp").drop_duplicates("timestamp",keep="last").set_index("timestamp")
    if not au.index.equals(au.index.floor("5min")):
        raise ValueError("Timestamps australianos fora da grade de cinco minutos.")
    presentes = au.index
    au = au.reindex(pd.date_range(au.index.min(),au.index.max(),freq="5min",name="timestamp"))
    au["registro_original"] = au.index.isin(presentes)
    for col, lim in {"Active_Power":(0,25.2),METEO[0]:(-20,60),METEO[1]:(0,100),METEO[2]:(0,1500)}.items():
        au.loc[~au[col].between(*lim),col] = np.nan
    au["Active_Power_original"] = au.Active_Power
    au["Active_Power"] = preencher_passado(au.Active_Power,3)
    au["potencia_estimada"] = au.Active_Power_original.isna() & au.Active_Power.notna()
    au["diurno"] = _solar(au.index,-23.76,133.87,"Australia/Darwin",560)>0
    au = calendario(au)
    print(f"Austrália: {len(au)} posições reais de cinco minutos; calculando Brasil",flush=True)
    cols = ["datetime","real_datetime","meta.id_usina","meta.id_inversor","usine_code","serial_number","fault_code","total_active_power_w"]
    bruto = pd.read_csv(c.brutos_brasil/"Leopoldo-fixa-inv.csv",usecols=cols,low_memory=False)
    bruto["t"] = pd.to_datetime(bruto.datetime,utc=True,format="mixed",errors="coerce").dt.tz_convert("America/Sao_Paulo")
    limpo = _limpar(bruto,"meta.id_inversor",["total_active_power_w"])
    ids = sorted(limpo["meta.id_inversor"].unique())
    if len(ids)!=8 or not limpo.groupby("meta.id_inversor").serial_number.nunique().eq(1).all():
        raise ValueError("Identidade dos oito inversores precisa ser conferida.")
    grade = pd.date_range("2025-01-01","2026-01-01",freq="5min",inclusive="left",tz="America/Sao_Paulo",name="timestamp")
    limpo = limpo.loc[limpo.slot.isin(grade)]
    painel = limpo.pivot(index="slot",columns="meta.id_inversor",values="total_active_power_w").reindex(index=grade,columns=ids)
    painel = painel.where(painel.ge(0) & painel.le(131250))
    falhas = limpo.pivot(index="slot",columns="meta.id_inversor",values="fault_code").reindex_like(painel)
    elev = pvlib.solarposition.get_solarposition(grade,-16.55,-48.85,altitude=927).apparent_elevation
    tratado, origens = proxy_causal(painel,falhas,elev.lt(-6))
    br = pd.DataFrame({"Active_Power_original":painel.sum(axis=1,min_count=8)/1000,
                       "Active_Power":tratado.sum(axis=1,min_count=8)/1000,
                       "registro_original": painel.notna().any(axis=1),"diurno":elev.gt(0),
                       "inversores_medidos":painel.notna().sum(axis=1),
                       "inversores_proxy":origens.eq("proxy_causal").sum(axis=1),
                       "inversores_zero_fisico":origens.eq("zero_fisico").sum(axis=1)},index=grade)
    br["Active_Power"] = preencher_passado(br.Active_Power,3)
    br["potencia_estimada"] = br.Active_Power_original.isna() & br.Active_Power.notna()
    meteo = pd.read_csv(c.intermediarios_meteo/"meteorologia_era5_horaria.csv",parse_dates=["timestamp"]).set_index("timestamp")
    # Não desloca radiação para o início da hora (isso revelaria a hora futura).
    mapa = {"temperature_2m":METEO[0],"relative_humidity_2m":METEO[1],"shortwave_radiation":METEO[2]}
    br = br.join(meteo[list(mapa)].rename(columns=mapa).reindex(grade,method="ffill",tolerance=pd.Timedelta(minutes=55)))
    br.index = br.index.tz_localize(None)
    br = calendario(br)
    br["meteo_resolucao_nativa_min"] = 60
    br["meteo_idade_min"] = br.index.minute % 60
    est = pd.read_csv(c.brutos_brasil/"Leopoldo-fixa-est.csv",usecols=["datetime","real_datetime","meta.id_usina","meta.id","usine_code","fail_read","air_temperature_med","ghi_irr_med"],low_memory=False)
    est["t"] = pd.to_datetime(est.datetime,utc=True,format="mixed",errors="coerce").dt.tz_convert("America/Sao_Paulo")
    est = _limpar(est,"meta.id",["air_temperature_med","ghi_irr_med"]).set_index("slot")
    est.index = est.index.tz_localize(None)
    br["temperatura_estacao_original"] = est.air_temperature_med.reindex(br.index)
    br["ghi_estacao_original_escala_nao_validada"] = est.ghi_irr_med.reindex(br.index)
    for nome, frame in [("australia",au),("brasil",br)]:
        _auditar(frame,nome,saida)
        destino = c.raiz/f"data/processed/{nome}"
        destino.mkdir(exist_ok=True,parents=True)
        frame.to_pickle(destino/f"base_5min_{nome}.pkl")
        frame.to_csv(destino/f"base_5min_{nome}.csv.gz",compression="gzip")
    resumo = {"resolucao":"5min","horizonte_minutos":5,"linhas_australia_brutas":linhas_au,"duplicatas_australia":duplicatas_au,
               "australia":{"grade":len(au),"alvos_medidos":int(au.Active_Power_original.notna().sum()),"inputs_estimados":int(au.potencia_estimada.sum())},
               "brasil":{"grade":len(br),"alvos_medidos":int(br.Active_Power_original.notna().sum()),"inputs_estimados":int(br.potencia_estimada.sum()),
                          "estacao_temperatura_presente":int(br.temperatura_estacao_original.notna().sum())},
               "alvos_imputados":0,"meteo_brasil":"ERA5 horária carregada para frente até 55 minutos; somente auxiliar, excluída do contrato principal",
               "reconstrucao":"Proxy causal e ffill de até três passos nos inputs; sem interpolação com ponto posterior. Alvos exigem medição original.",
               "fontes_sha256":{"australia":sha256(au_arquivo),"brasil":sha256(c.brutos_brasil/"Leopoldo-fixa-inv.csv"),"estacao":sha256(c.brutos_brasil/"Leopoldo-fixa-est.csv")}}
    (saida/"resumo.json").write_text(json.dumps(resumo,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    auditar_invalidos_fonte()
    _graficos_auditoria(au,br,saida)
    return resumo


def janelas(frame,colunas,lag,contrato,cfg,dominio):
    """Último input t-5 min; alvo t medido; nunca comprime lacunas."""
    if not frame.index.is_unique or not frame.index.to_series().diff().dropna().eq(PASSO).all():
        raise ValueError("Grade regular de cinco minutos obrigatória.")
    raw = frame[colunas].to_numpy(dtype=np.float32)
    norm = ((raw-np.array(contrato["x_media_treino"]))/np.array(contrato["x_escala_treino"])).astype(np.float32)
    valido = np.isfinite(raw).all(axis=1)
    ruim = np.r_[0,np.cumsum(~valido)]
    pos = np.arange(lag,len(frame))
    # Persistência avaliada somente se o instante anterior também foi medido.
    alvo = frame.Active_Power_original.to_numpy(dtype=float)
    mask = (ruim[pos]-ruim[pos-lag]==0) & np.isfinite(alvo[pos]) & np.isfinite(alvo[pos-1])
    pos = pos[mask]
    datas = frame.index[pos]
    corte_tr = pd.Timestamp(cfg[f"fim_treino_{dominio}"])+pd.Timedelta(days=1)
    corte_va = pd.Timestamp(cfg[f"fim_validacao_{dominio}"])+pd.Timedelta(days=1)
    classes = np.select([datas<corte_tr,datas<corte_va],["treino","validacao"],default="teste")
    indices = pos[:,None]-lag+np.arange(lag)
    x = norm[indices]
    y_pu = (alvo[pos]/cfg["capacidade_ac_kw"][dominio]).astype(np.float32)
    y = ((y_pu-contrato["y_media_treino"])/contrato["y_escala_treino"]).astype(np.float32)
    meta = pd.DataFrame({"timestamp":datas,"entrada_inicio":frame.index[pos-lag],"entrada_fim":frame.index[pos-1],
                         "particao":classes,"diurno":frame.diurno.to_numpy()[pos],
                         "fracao_inputs_estimados_pct":frame.potencia_estimada.to_numpy()[indices].mean(axis=1)*100})
    dados = {"X":x,"y":y,"y_original":y_pu,"persistencia":(alvo[pos-1]/cfg["capacidade_ac_kw"][dominio]).astype(np.float32),
             "datas":datas.strftime("%Y-%m-%dT%H:%M:%S").to_numpy(dtype="U19"),"diurno":meta.diurno.to_numpy(),
             "fracao_inputs_estimados_pct":meta.fracao_inputs_estimados_pct.to_numpy(dtype=np.float32),
             "fracao_alvo_estimada_pct":np.zeros(len(pos),dtype=np.float32),"cobertura_alvo_original_pct":np.full(len(pos),100,dtype=np.float32)}
    return dados,meta


def preparar_experimento(pasta,cfg):
    c = CaminhosProjeto()
    for sub in ["dados","resultados","modelos/fonte","modelos/brasil","figuras"]:
        (pasta/sub).mkdir(exist_ok=True,parents=True)
    if not (c.raiz/"reports/intradiario/resumo.json").exists(): gerar_bases()
    fontes = {d:c.raiz/f"data/processed/{d}/base_5min_{d}.pkl" for d in ["australia","brasil"]}
    au = pd.read_pickle(fontes["australia"])
    br = pd.read_pickle(fontes["brasil"])
    au = au.loc[cfg["inicio_treino_australia"]:cfg["fim_teste_australia"]].copy()
    br = br.loc[:cfg["fim_teste_brasil"]].copy()
    quadros = {"australia":au,"brasil":br}
    cols = cfg["variaveis"]
    # Escalas aprendidas em horários de treino com potência original medida.
    fit = au.loc[:cfg["fim_treino_australia"]].loc[lambda f:f.Active_Power_original.notna() & f.diurno].copy()
    fit["Active_Power"] /= cfg["capacidade_ac_kw"]["australia"]
    sx = StandardScaler().fit(fit[cols])
    sy = StandardScaler().fit((fit.Active_Power_original/cfg["capacidade_ac_kw"]["australia"]).to_numpy()[:,None])
    contrato = {"resolucao":"5min","horizonte_minutos":5,"variaveis_por_passo":cols,
                "x_media_treino":sx.mean_.tolist(),"x_escala_treino":sx.scale_.tolist(),
                "y_media_treino":float(sy.mean_[0]),"y_escala_treino":float(sy.scale_[0]),
                "config_sha256":sha256(pasta/"config.json"),"hipoteses_sha256":sha256(pasta/"fontes_e_hipoteses.json"),
                "fontes_sha256":{d:sha256(f) for d,f in fontes.items()},"npz_sha256":{},
                "normalizacao":"Potência AC em p.u.; escalas do treino australiano diurno compartilhadas no Brasil.",
                "alvos":"Somente valores originais medidos; nenhum alvo reconstruído.",
                "avaliacao_principal":"Diurna (elevação solar > 0), com persistência t-5 min medida; avaliação 24h complementar.",
                "meteo":"Excluída do contrato; dados ERA5 nativos horários mantidos na auditoria auxiliar."}
    candidatos,metas,contagens = {},[],[]
    for dominio,frame in quadros.items():
        bruto = frame.copy()
        frame["Active_Power"] /= cfg["capacidade_ac_kw"][dominio]
        frame[cols].to_pickle(pasta/f"dados/{dominio}_pu.pkl")
        # janelas recebe inputs em p.u. e alvos originais em kW.
        for lag in cfg["lags"]:
            dados,meta = janelas(frame,cols,lag,contrato,cfg,dominio)
            candidatos[dominio,lag] = dados,meta
        for parte in ["treino","validacao","teste"]:
            datas_comuns = None
            for lag in cfg["lags"]:
                _,m = candidatos[dominio,lag]
                datas = pd.Index(m.loc[m.particao.eq(parte)&m.diurno,"timestamp"])
                datas_comuns = datas if datas_comuns is None else datas_comuns.intersection(datas)
            for lag in cfg["lags"]:
                dados,meta = candidatos[dominio,lag]
                mask = meta.particao.eq(parte)&meta.diurno
                if parte!="treino": mask &= meta.timestamp.isin(datas_comuns)
                pos = np.flatnonzero(mask)
                if parte=="treino": pos=pos[::cfg["stride_treino_fonte"] if dominio=="australia" else cfg["stride_treino_brasil"]]
                if len(pos)<10: raise ValueError("Partição de cinco minutos insuficiente.")
                export = {k:v[pos] for k,v in dados.items()}
                arquivo=pasta/f"dados/{dominio}_lag{lag}_{parte}.npz"
                np.savez_compressed(arquivo,**export)
                contrato["npz_sha256"][str(arquivo.relative_to(pasta))]=sha256(arquivo)
                contagens.append({"dominio":dominio,"lag":lag,"historico_min":lag*5,"particao":parte,
                                  "janelas_antes_coorte":int(mask.sum()),"janelas":len(pos),"primeiro_alvo":export["datas"][0],"ultimo_alvo":export["datas"][-1]})
        for lag in cfg["lags"]:
            dados,meta = candidatos.pop((dominio,lag))
            meta["dominio"],meta["lag"]=dominio,lag
            metas.append(meta)
            # Coorte 24h complementar com checkpoint escolhido na avaliação posterior.
            mask=meta.particao.eq("teste").to_numpy()
            arquivo24=pasta/f"dados/{dominio}_lag{lag}_teste_24h.npz"
            np.savez_compressed(arquivo24,**{k:v[mask] for k,v in dados.items()})
            contrato["npz_sha256"][str(arquivo24.relative_to(pasta))]=sha256(arquivo24)
    pd.concat(metas,ignore_index=True).to_csv(pasta/"resultados/janelas.csv.gz",index=False,compression="gzip")
    contagens=pd.DataFrame(contagens)
    contagens.to_csv(pasta/"resultados/particoes.csv",index=False)
    (pasta/"dados/contrato.json").write_text(json.dumps(contrato,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    # Diagnóstico de lags apenas na validação australiana, sem consultar teste.
    scores=[]
    for lag in cfg["lags"]:
        with np.load(pasta/f"dados/australia_lag{lag}_treino.npz") as a, np.load(pasta/f"dados/australia_lag{lag}_validacao.npz") as b:
            reg=Ridge(alpha=10).fit(a["X"].reshape(len(a["y"]),-1),a["y"])
            pred=(reg.predict(b["X"].reshape(len(b["y"]),-1))*sy.scale_[0]+sy.mean_[0]).clip(0)
            scores.append({"historico_min":lag*5,"n_validacao":len(pred),"MAE_pu":float(np.abs(pred-b["y_original"]).mean()),"RMSE_pu":float(np.sqrt(np.mean((pred-b["y_original"])**2)))})
    pd.DataFrame(scores).to_csv(pasta/"resultados/inputs_lags_validacao.csv",index=False)
    return {"particoes":contagens,"contrato":contrato}


def _graficos_auditoria(au,br,pasta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for nome,f in [("australia",au),("brasil",br)]:
        cols=["Active_Power_original",*METEO]
        rotulos=["Potência medida","Temperatura (ERA5 no Brasil)","Umidade (ERA5 no Brasil)","GHI (ERA5 no Brasil)"]
        if nome=="brasil":
            cols += ["temperatura_estacao_original","ghi_estacao_original_escala_nao_validada"]
            rotulos += ["Temperatura estação 5 min","GHI estação 5 min"]
        falta=f[cols].isna().resample("D").mean()*100
        fig,ax=plt.subplots(figsize=(14,4))
        im=ax.imshow(falta.T,aspect="auto",vmin=0,vmax=100,cmap="Reds",interpolation="nearest")
        ticks=np.linspace(0,len(falta)-1,8).astype(int)
        ax.set_xticks(ticks,falta.index[ticks].strftime("%Y-%m"))
        ax.set_yticks(range(len(cols)),rotulos)
        ax.set_title(f"{nome.title()} — faltantes em cada dia na grade de 5 minutos; meteo Brasil: ERA5 horária")
        fig.colorbar(im,ax=ax,label="Faltantes (%)")
        fig.tight_layout();fig.savefig(pasta/f"faltantes_{nome}_5min.png",dpi=140);plt.close(fig)


def avaliar_australia():
    """Teste fonte depois de selecionar o lag de cada família na validação."""
    from .transfer_learning.dados import carregar,particao
    from .transfer_learning.treinamento import restaurar,prever,erros
    import torch
    pasta,cfg,contrato=carregar()
    torch.set_num_threads(2)
    destino=CaminhosProjeto().raiz/"experimentos/australia_deep_learning"
    for s in ["resultados","figuras","dados"]: (destino/s).mkdir(exist_ok=True,parents=True)
    va=pd.read_csv(pasta/"resultados/pretreino_metricas.csv").query("particao == 'validacao'")
    ranking=va.groupby(["arquitetura","lag"]).RMSE_pu.mean().reset_index()
    escolhas=ranking.sort_values("RMSE_pu").drop_duplicates("arquitetura").set_index("arquitetura").lag.to_dict()
    linhas,curvas=[],[]
    cap=cfg["capacidade_ac_kw"]["australia"]
    for arquitetura in cfg["arquiteturas"]:
        for lag in cfg["lags"]:
            dados=particao(pasta,"australia",lag,"teste")
            for seed in cfg["seeds"]:
                modelo=restaurar(pasta,cfg,contrato,arquitetura,lag,seed)
                pred=prever(modelo,dados,contrato)
                linhas.append({"arquitetura":arquitetura,"lag":lag,"historico_min":lag*5,"seed":seed,
                               "selecionado_validacao":lag==escolhas[arquitetura],**erros(dados["y_original"],pred,dados["persistencia"])})
                if seed==42 and lag==escolhas[arquitetura]:
                    curvas.append(pd.DataFrame({"timestamp":dados["datas"],"arquitetura":arquitetura,
                      "real_kw":dados["y_original"]*cap,"previsto_kw":pred*cap,"persistencia_kw":dados["persistencia"]*cap}))
    medidas=pd.DataFrame(linhas)
    medidas["RMSE_kw"]=medidas.RMSE_pu*cap
    medidas["MAE_kw"]=medidas.MAE_pu*cap
    medidas.to_csv(destino/"resultados/metricas_teste_5min.csv",index=False)
    resumo=medidas.groupby(["arquitetura","lag","historico_min","selecionado_validacao"]).agg(
       RMSE_kw_medio=("RMSE_kw","mean"),RMSE_kw_dp=("RMSE_kw","std"),MAE_kw_medio=("MAE_kw","mean"),
       skill_persistencia_pct=("skill_persistencia_pct","mean"),R2_medio=("R2","mean"),n=("n","first")).reset_index()
    resumo.to_csv(destino/"resultados/comparacao_modelos_5min.csv",index=False)
    curvas=pd.concat(curvas,ignore_index=True)
    curvas.to_csv(destino/"resultados/previsoes_5min_seed42.csv.gz",index=False,compression="gzip")
    pares=medidas.pivot(index=["lag","seed"],columns="arquitetura",values="RMSE_kw").reset_index()
    pares["ganho_residual_sobre_direta_pct"]=100*(1-pares.mlp_residual/pares.mlp_direta)
    pares.to_csv(destino/"resultados/correcao_persistencia_5min.csv",index=False)
    (destino/"dados/referencia_contrato.json").write_text(json.dumps({"contrato":str(pasta/"dados/contrato.json"),
      "sha256":sha256(pasta/"dados/contrato.json"),"escolhas_por_validacao_australiana":escolhas},indent=2)+"\n",encoding="utf-8")
    _graficos_australia_5min(pasta,destino,curvas,escolhas,resumo)
    return resumo


def _graficos_australia_5min(pasta,destino,curvas,escolhas,resumo):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    curvas.timestamp=pd.to_datetime(curvas.timestamp)
    hist=pd.read_csv(pasta/"resultados/pretreino_historicos.csv")
    for arq,nome in [("mlp_direta","mlp"),("lstm_direta","lstm"),("mlp_residual","mlp_residual")]:
        fig,axes=plt.subplots(2,1,figsize=(14,8))
        h=hist.loc[hist.arquitetura.eq(arq)&hist.lag.eq(escolhas[arq])&hist.seed.eq(42)]
        axes[0].plot(h.epoca,h.MSE_treino,label="Treino");axes[0].plot(h.epoca,h.MSE_validacao,label="Validação")
        axes[0].set(title=f"{arq}, histórico {escolhas[arq]*5} min; horizonte 5 min",ylabel="MSE padronizado",xlabel="Época")
        d=curvas.loc[curvas.arquitetura.eq(arq)].copy()
        d=d.loc[d.timestamp.lt(d.timestamp.min().normalize()+pd.Timedelta(days=3))].set_index("timestamp")
        d=d.reindex(pd.date_range(d.index.min(),d.index.max(),freq="5min"))
        axes[1].plot(d.index,d.real_kw,label="Medido",color="#222222",linewidth=.8)
        axes[1].plot(d.index,d.previsto_kw,label=arq,linewidth=.8)
        axes[1].plot(d.index,d.persistencia_kw,label="Persistência 5 min",linewidth=.7,alpha=.6)
        axes[1].set(title="Primeiros três dias do teste fonte, somente alvos diurnos medidos",ylabel="Potência (kW)")
        for ax in axes: ax.legend();ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(destino/f"figuras/treino_{nome}.png",dpi=140);plt.close(fig)
    ax=resumo.loc[resumo.selecionado_validacao].set_index("arquitetura").RMSE_kw_medio.plot.bar(rot=0,figsize=(11,4))
    ax.set(ylabel="RMSE (kW)",title="Teste australiano diurno, horizonte 5 minutos; lag escolhido na validação")
    ax.figure.tight_layout();ax.figure.savefig(destino/"figuras/comparacao_modelos.png",dpi=140);plt.close(ax.figure)


def atualizar_proveniencia_5min():
    """Corrige textos herdados do diário sem alterar tensores ou pesos.

    Revalida todos os hashes e registra a transação. Requer adaptação concluída.
    """
    import torch
    from .transfer_learning.dados import carregar
    pasta,cfg,ct=carregar()
    decisao_arq=pasta/"resultados/decisao_validacao.json"
    decisao=json.loads(decisao_arq.read_text(encoding="utf-8"))
    n=len(cfg["lags"])*len(cfg["arquiteturas"])*len(cfg["seeds"])
    fontes=sorted((pasta/"modelos/fonte").glob("*.pt"))
    brasileiros=sorted((pasta/"modelos/brasil").glob("*.pt"))
    if len(fontes)!=n or len(brasileiros)!=n*len(cfg["metodos"]): raise ValueError("Aguardar todos os treinos.")
    antigo_sha=sha256(pasta/"dados/contrato.json")
    objetos={p:torch.load(p,map_location="cpu",weights_only=True) for p in fontes+brasileiros}
    if any(ck["contrato_sha256"]!=antigo_sha for ck in objetos.values()): raise ValueError("Contrato divergente antes da revisão.")
    meta_arq=pasta/"fontes_e_hipoteses.json"
    meta=json.loads(meta_arq.read_text(encoding="utf-8"))
    meta["australia"]["alertas"]=[s for s in meta["australia"]["alertas"] if "Sem CSV intradiário" not in s]
    meta["australia"]["alertas"].append("CSV original de cinco minutos localizado e usado diretamente; sem desagregação diária.")
    meta["australia"]["mascara_solar"]={"latitude_aproximada":-23.76,"longitude_aproximada":133.87,"altitude_m_adotada":560,"fuso":"Australia/Darwin"}
    meta["brasil"]["reconstrucao"]="Inputs: proxy causal de até três passos e depois ffill do total de até três passos; combinação pode chegar a 30 minutos. Alvos e persistência exigem medições originais. Sem interpolação com extremo futuro."
    meta["brasil"]["alvo"]="Potência AC no instante t+5 min, originalmente medida nos oito inversores; avaliação principal diurna, complementar 24h. Não é média diária."
    meta["normalizacao"]="Potência AC/capacidade AC. Escalas de potência e calendário aprendidas só no treino australiano diurno. Nenhuma escala recalibrada no destino."
    meta["latencia"]="Horizonte por timestamps; latência real de coleta e publicação da ERA5 não é simulada. ERA5 não é input principal."
    meta_arq.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    ct["hipoteses_sha256"]=sha256(meta_arq)
    for arquivo24 in (pasta/"dados").glob("*_teste_24h.npz"):
        ct["npz_sha256"][str(arquivo24.relative_to(pasta))]=sha256(arquivo24)
    (pasta/"dados/contrato.json").write_text(json.dumps(ct,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    novo_sha=sha256(pasta/"dados/contrato.json")
    for arquivo in fontes+brasileiros:
        ck=objetos[arquivo]
        ck["contrato_sha256"]=novo_sha
        if arquivo in brasileiros and ck["metodo"]!="local":
            origem=pasta/"modelos/fonte"/f"{ck['arquitetura']}_lag{ck['lag']}_seed{ck['seed']}_fonte.pt"
            ck["checkpoint_fonte_sha256"]=sha256(origem)
        torch.save(ck,arquivo)
        relido=torch.load(arquivo,map_location="cpu",weights_only=True)
        assert all(torch.equal(v,relido["state_dict"][k]) for k,v in ck["state_dict"].items())
    decisao["contrato_sha256"]=novo_sha
    decisao["checkpoints_sha256"]={str(p.relative_to(pasta)):sha256(p) for p in brasileiros}
    decisao_arq.write_text(json.dumps(decisao,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    au=pasta.parent/"australia_deep_learning/dados/referencia_contrato.json"
    ref=json.loads(au.read_text(encoding="utf-8"));ref["sha256"]=novo_sha
    au.write_text(json.dumps(ref,indent=2)+"\n",encoding="utf-8")
    log={"motivo":"Corrigir descrições diárias herdadas nos metadados após a migração, sem refazer ou alterar treinamento.",
         "contrato_anterior_sha256":antigo_sha,"contrato_atual_sha256":novo_sha,
         "pesos_bit_a_bit_preservados":len(objetos),"tensores_npz_inalterados":ct["npz_sha256"],
         "ranking_validacao_inalterado":True}
    (pasta/"resultados/revisao_proveniencia.json").write_text(json.dumps(log,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return log
