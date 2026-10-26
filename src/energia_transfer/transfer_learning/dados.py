"""Contrato físico compartilhado, calendários completos e cortes cronológicos."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from ..caminhos import CaminhosProjeto
from ..deep_learning.dados import sha256, limpar_diario, entradas_causais


def pasta_experimento(pasta=None):
    return Path(pasta or CaminhosProjeto().raiz / "experimentos/transfer_learning_australia_brasil").resolve()


def carregar_config(pasta=None):
    pasta = pasta_experimento(pasta)
    cfg = json.loads((pasta / "config.json").read_text(encoding="utf-8"))
    if cfg.get("resolucao") == "5min":
        from ..intradiario import COLUNAS
        if cfg["variaveis"] != COLUNAS or cfg["horizonte_passos"] != 1:
            raise ValueError("Contrato de cinco minutos sem vento e horizonte de um passo obrigatório.")
        return cfg
    permitidas = {"Active_Power", "Weather_Temperature_Celsius", "Weather_Relative_Humidity",
                  "Global_Horizontal_Radiation", "dia_ano_sin", "dia_ano_cos"}
    if set(cfg["variaveis"]) != permitidas or len(cfg["variaveis"]) != 6:
        raise ValueError("Esperadas somente as seis variáveis básicas, sem vento.")
    if cfg["horizonte_dias"] != 1 or not cfg["lags"] or min(cfg["lags"]) < 1:
        raise ValueError("Históricos positivos e horizonte diário de um dia obrigatórios.")
    if not cfg["seeds"] or len(set(cfg["seeds"])) != len(cfg["seeds"]):
        raise ValueError("Sementes precisam ser distintas e não vazias.")
    for dominio in ["australia", "brasil"]:
        if cfg["capacidade_ac_kw"][dominio] <= 0:
            raise ValueError("Capacidades AC precisam ser positivas.")
        if cfg[f"fim_treino_{dominio}"] >= cfg[f"fim_validacao_{dominio}"]:
            raise ValueError("Treino precisa preceder validação.")
    if cfg["fim_validacao_australia"] >= cfg["fim_treino_brasil"]:
        raise ValueError("Pré-treino deve preceder a adaptação brasileira neste protocolo.")
    return cfg


def arquivos_fonte():
    c = CaminhosProjeto()
    return {"australia": c.brutos_australia / "base_diaria_australia.csv",
            "brasil": c.processados_brasil / "base_diaria_leopoldo_dias_validos.csv",
            "qualidade": c.base_final / "qualidade_diaria_base_consecutiva.csv"}


def ajustar_escalas_fonte(frame, colunas, fim_treino):
    treino = frame.loc[:fim_treino]
    sx = StandardScaler().fit(treino[colunas])
    sy = StandardScaler().fit(treino[["Active_Power"]].dropna())
    return sx, sy


def criar_janelas(frame, colunas, lag, fim_treino, fim_validacao, sx, sy):
    """Datas ausentes quebram a janela; y_original e persistência estão em p.u."""
    if not frame.index.is_unique or not frame.index.equals(frame.index.normalize()):
        raise ValueError("Esperadas datas diárias únicas.")
    if lag < 1:
        raise ValueError("Histórico deve ser positivo.")
    dias = pd.date_range(frame.index.min(), frame.index.max(), name="timestamp")
    diario = frame.reindex(dias)
    matriz = diario[colunas].to_numpy(dtype=float)
    potencia = diario.Active_Power.to_numpy(dtype=float)
    xs, ys, datas = [], [], []
    for i in range(lag, len(diario)):
        trecho = matriz[i-lag:i]
        if not np.isfinite(trecho).all() or not np.isfinite(potencia[i-lag:i+1]).all():
            continue
        xs.append(trecho)
        ys.append(potencia[i])
        datas.append(dias[i])
    x = np.asarray(xs, dtype=np.float32).reshape(-1, lag, len(colunas))
    x = ((x - sx.mean_) / sx.scale_).astype(np.float32)
    y_pu = np.asarray(ys, dtype=np.float32)
    y = ((y_pu - sy.mean_[0]) / sy.scale_[0]).astype(np.float32)
    datas = pd.DatetimeIndex(datas)
    meta = pd.DataFrame({"timestamp": datas, "entrada_inicio": datas - pd.Timedelta(days=lag),
                         "entrada_fim": datas - pd.Timedelta(days=1)})
    meta["particao"] = np.select([datas <= pd.Timestamp(fim_treino), datas <= pd.Timestamp(fim_validacao)],
                                 ["treino", "validacao"], default="teste")
    persistencia = diario.Active_Power.reindex(datas - pd.Timedelta(days=1)).to_numpy(dtype=np.float32)
    return {"X": x, "y": y, "y_original": y_pu, "persistencia": persistencia,
            "datas": datas.strftime("%Y-%m-%d").to_numpy(dtype="U10")}, meta


def preparar(pasta=None):
    pasta = pasta_experimento(pasta)
    cfg = carregar_config(pasta)
    if cfg.get("resolucao") == "5min":
        from ..intradiario import preparar_experimento
        return preparar_experimento(pasta,cfg)
    for nome in ["dados", "resultados", "modelos/fonte", "modelos/brasil", "figuras"]:
        (pasta / nome).mkdir(parents=True, exist_ok=True)
    fontes = arquivos_fonte()
    au = pd.read_csv(fontes["australia"], parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    au = au.loc[:cfg["fim_validacao_australia"]]
    qc = {"limites_operacionais": cfg["limites_operacionais"],
          "limite_ffill_meteorologia_dias": cfg["limite_ffill_australia_dias"]}
    original, limpo, invalidos = limpar_diario(au, qc)
    au, estimados = entradas_causais(limpo, qc)
    au["Active_Power"] /= cfg["capacidade_ac_kw"]["australia"]
    br = pd.read_csv(fontes["brasil"], parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    br = br.loc[:cfg["fim_teste_brasil"]]
    qualidade = pd.read_csv(fontes["qualidade"], parse_dates=["timestamp"]).set_index("timestamp")
    if not qualidade.reindex(br.index).dia_elegivel.fillna(False).all():
        raise ValueError("Base brasileira contém dias reprovados.")
    for coluna, (inferior, superior) in cfg["limites_operacionais"].items():
        if not br[coluna].between(inferior, superior).all():
            raise ValueError(f"Meteorologia brasileira fora dos limites: {coluna}.")
    if not br.Active_Power.ge(0).all():
        raise ValueError("Potência brasileira deve ser não negativa.")
    # Reindexação mantém lacunas; não preenche potência nem dias reprovados.
    br = br.reindex(pd.date_range(br.index.min(), br.index.max(), name="timestamp"))
    br["Active_Power"] /= cfg["capacidade_ac_kw"]["brasil"]
    periodo = np.where(br.index.is_leap_year, 366., 365.)
    angulo = 2 * np.pi * (br.index.dayofyear - 1) / periodo
    br["dia_ano_sin"], br["dia_ano_cos"] = np.sin(angulo), np.cos(angulo)
    colunas = cfg["variaveis"]
    sx, sy = ajustar_escalas_fonte(au, colunas, cfg["fim_treino_australia"])
    candidatos, metas = {}, []
    comuns = {}
    for dominio, frame in [("australia", au), ("brasil", br)]:
        for lag in cfg["lags"]:
            dados, meta = criar_janelas(frame, colunas, lag, cfg[f"fim_treino_{dominio}"],
                                        cfg[f"fim_validacao_{dominio}"], sx, sy)
            meta["dominio"], meta["lag"] = dominio, lag
            candidatos[dominio, lag] = (dados, meta)
        for particao in ["validacao", "teste"]:
            listas = [pd.Index(meta.loc[meta.particao.eq(particao), "timestamp"])
                      for (dom, _), (_, meta) in candidatos.items() if dom == dominio]
            comuns[dominio, particao] = listas[0]
            for datas in listas[1:]:
                comuns[dominio, particao] = comuns[dominio, particao].intersection(datas)
    contagens = []
    for (dominio, lag), (dados, meta) in candidatos.items():
        meta["coorte_comum"] = meta.particao.eq("treino")
        for particao in ["validacao", "teste"]:
            meta.loc[meta.particao.eq(particao), "coorte_comum"] = meta.timestamp.isin(comuns[dominio, particao])
        if dominio == "brasil":
            q = qualidade.reindex(meta.timestamp)
            meta["alvo_fracao_diurna_estimada_pct"] = q.planta_diurnos_com_estimativa_pct.to_numpy()
            meta["alvo_cobertura_diurna_original_pct"] = q.planta_cobertura_diurna_original_pct.to_numpy()
            meta["bloco_id"] = q.bloco_id.to_numpy()
        metas.append(meta)
        for particao in ["treino", "validacao", "teste"]:
            if dominio == "australia" and particao == "teste":
                continue
            mask = (meta.particao.eq(particao) & meta.coorte_comum).to_numpy()
            if mask.sum() < 10:
                raise ValueError(f"Partição insuficiente: {dominio}, lag={lag}, {particao}.")
            exportado = {k: v[mask] for k, v in dados.items()}
            if dominio == "brasil":
                exportado["fracao_alvo_estimada_pct"] = meta.loc[mask, "alvo_fracao_diurna_estimada_pct"].to_numpy(dtype=np.float32)
                exportado["cobertura_alvo_original_pct"] = meta.loc[mask, "alvo_cobertura_diurna_original_pct"].to_numpy(dtype=np.float32)
            arquivo = pasta / "dados" / f"{dominio}_lag{lag}_{particao}.npz"
            np.savez_compressed(arquivo, **exportado)
            contagens.append({"dominio": dominio, "lag": lag, "particao": particao,
                              "janelas_antes_coorte": int(meta.particao.eq(particao).sum()),
                              "janelas": int(mask.sum()), "primeiro_alvo": exportado["datas"][0],
                              "ultimo_alvo": exportado["datas"][-1], "sha256": sha256(arquivo)})
    au[colunas].to_csv(pasta / "dados/australia_pu.csv")
    br[colunas].to_csv(pasta / "dados/brasil_pu.csv")
    pd.concat(metas, ignore_index=True).to_csv(pasta / "resultados/janelas.csv", index=False)
    contagens = pd.DataFrame(contagens)
    contagens.to_csv(pasta / "resultados/particoes.csv", index=False)
    treino_br = br.loc[:cfg["fim_treino_brasil"], colunas]
    shift = pd.DataFrame({"media_australia_treino": au.loc[:cfg["fim_treino_australia"], colunas].mean(),
                          "media_brasil_treino": treino_br.mean(),
                          "dp_australia_treino": au.loc[:cfg["fim_treino_australia"], colunas].std(),
                          "dp_brasil_treino": treino_br.std()})
    shift.to_csv(pasta / "resultados/diferencas_dominios_treino.csv", index_label="variavel")
    faltantes = pd.DataFrame({"faltantes_calendario": original[colunas[:4]].isna().sum(),
                              "invalidos": invalidos[colunas[:4]].sum(),
                              "ffill": estimados[colunas[:4]].sum()})
    faltantes.to_csv(pasta / "resultados/auditoria_australia.csv", index_label="variavel")
    contrato = {"variaveis_por_passo": colunas, "unidade_Active_Power": "Potência AC / capacidade AC instalada (p.u.)",
                "x_media_treino": sx.mean_.tolist(), "x_escala_treino": sx.scale_.tolist(),
                "y_media_treino": float(sy.mean_[0]), "y_escala_treino": float(sy.scale_[0]),
                "config_sha256": sha256(pasta / "config.json"),
                "hipoteses_sha256": sha256(pasta / "fontes_e_hipoteses.json"),
                "fontes_sha256": {k: sha256(v) for k, v in fontes.items()},
                "npz_sha256": {str(Path("dados") / f"{r.dominio}_lag{r.lag}_{r.particao}.npz"): r.sha256 for r in contagens.itertuples()},
                "normalizacao": "Escalas aprendidas apenas no treino australiano; compartilhadas com todos os métodos brasileiros.",
                "coortes": "Validação e teste são interseções dos alvos elegíveis de todos os lags. Treinos usam todas as janelas válidas de cada lag.",
                "tipo_estudo": cfg["escopo"]}
    (pasta / "dados/contrato.json").write_text(json.dumps(contrato, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"particoes": contagens.drop(columns="sha256"), "shift": shift, "faltantes": faltantes, "contrato": contrato}


def carregar(pasta=None):
    pasta = pasta_experimento(pasta)
    cfg = carregar_config(pasta)
    contrato = json.loads((pasta / "dados/contrato.json").read_text(encoding="utf-8"))
    if contrato["config_sha256"] != sha256(pasta / "config.json") or contrato["hipoteses_sha256"] != sha256(pasta / "fontes_e_hipoteses.json"):
        raise ValueError("Configuração mudou; refaça os notebooks desde o 01.")
    fontes = arquivos_fonte()
    if cfg.get("resolucao") == "5min":
        c=CaminhosProjeto()
        fontes={d:c.raiz/f"data/processed/{d}/base_5min_{d}.pkl" for d in ["australia","brasil"]}
    for k, arquivo in fontes.items():
        if sha256(arquivo) != contrato["fontes_sha256"][k]:
            raise ValueError("Fonte mudou; refaça os notebooks desde o 01.")
    for relativo, esperado in contrato["npz_sha256"].items():
        if sha256(pasta / relativo) != esperado:
            raise ValueError("Partições mudaram; refaça os notebooks desde o 01.")
    return pasta, cfg, contrato


def particao(pasta, dominio, lag, nome):
    with np.load(pasta / "dados" / f"{dominio}_lag{lag}_{nome}.npz", allow_pickle=False) as arq:
        return dict(arq)
