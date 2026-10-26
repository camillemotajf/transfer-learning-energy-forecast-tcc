"""Reconstrói e documenta o processamento diário usado no TCC, sem alterar bases/modelos."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ/"src"))
from energia_transfer.deep_learning.dados import limpar_diario, entradas_causais
from energia_transfer.chronos_diario_contadores import reconstruir_contadores


def sha(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def executar():
    out = RAIZ/"docs/tcc"
    out.mkdir(parents=True, exist_ok=True)
    historico = RAIZ/"experimentos/transfer_learning_australia_brasil/historico_diario"
    atual = RAIZ/"experimentos/chronos_diario_contadores"
    fontes = [RAIZ/"data/raw/australia/87-Site_DKA-M9_A+C-Phases.csv", RAIZ/"data/raw/australia/base_diaria_australia.csv",
              historico/"config.json", historico/"dados/australia_pu.csv", RAIZ/"data/raw/brasil/Leopoldo-fixa-inv.csv",
              RAIZ/"data/processed/brasil/leopoldo_diario_contadores_auditado.csv",
              RAIZ/"data/interim/meteorologia/meteorologia_era5_diaria.csv", atual/"resultados/particoes.csv", atual/"resultados/benchmark_final.csv"]
    hashes = {str(p.relative_to(RAIZ)): sha(p) for p in fontes}
    cfg = json.loads((historico/"config.json").read_text(encoding="utf-8"))
    cols = cfg["variaveis"][:4]
    bruto = pd.read_csv(fontes[0], usecols=["timestamp"]+cols)
    bruto.timestamp = pd.to_datetime(bruto.timestamp, errors="coerce", format="mixed")
    assert bruto.timestamp.notna().all() and not bruto.timestamp.duplicated().any()
    bruto = bruto.set_index("timestamp").sort_index()
    medias, n_leituras = bruto.resample("D").mean(), bruto.resample("D").count()
    recebida = pd.read_csv(fontes[1], parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    datas = medias.index.intersection(recebida.index)
    diferenca = (recebida.loc[datas, cols]-medias.loc[datas, cols]).abs().max()
    np.testing.assert_allclose(recebida.loc[datas, cols], medias.loc[datas, cols], atol=1e-10, rtol=0, equal_nan=True)
    qc = dict(limites_operacionais=cfg["limites_operacionais"], limite_ffill_meteorologia_dias=cfg["limite_ffill_australia_dias"])
    original, limpo, invalidos = limpar_diario(recebida.loc[:"2023-12-31", cols], qc)
    tratado, estimados = entradas_causais(limpo, qc)
    tratado.Active_Power /= cfg["capacidade_ac_kw"]["australia"]
    au = pd.read_csv(fontes[3], parse_dates=["timestamp"]).set_index("timestamp")
    np.testing.assert_allclose(tratado[au.columns], au, atol=1e-10, rtol=0, equal_nan=True)
    auditoria = pd.DataFrame(dict(faltantes_calendario=original[cols].isna().sum(), invalidos=invalidos[cols].sum(),
                                  ffill_causal=estimados[cols].sum(), faltantes_finais=au[cols].isna().sum()))
    auditoria.to_csv(out/"auditoria_faltantes_australia.csv", index_label="variavel")
    alvos, coberturas = [], []
    for part in ["treino", "validacao"]:
        arquivo = historico/"dados"/f"australia_lag3_{part}.npz"
        hashes[str(arquivo.relative_to(RAIZ))] = sha(arquivo)
        with np.load(arquivo, allow_pickle=False) as z:
            datas = pd.DatetimeIndex(pd.to_datetime(z["datas"]))
        contagens = n_leituras.Active_Power.reindex(datas)
        alvos.append(pd.DataFrame(dict(dominio="australia", particao=part, timestamp=datas,
                                       leituras_potencia_no_dia=contagens.to_numpy(), cobertura_amostras_pct=100*contagens.to_numpy()/288)))
        coberturas.append(dict(particao=part, n=len(datas), alvos_com_288_leituras=int(contagens.eq(288).sum()),
                               alvos_com_menos_95pct_leituras=int(contagens.lt(.95*288).sum()),
                               menor_numero_leituras=int(contagens.min())))
    pd.concat(alvos, ignore_index=True).to_csv(out/"auditoria_cobertura_alvos_australia.csv", index=False)
    res_au = dict(linhas_brutas=len(bruto), duplicatas_timestamp=0, inicio_bruto=str(bruto.index.min()), fim_bruto=str(bruto.index.max()),
                  dias_recebidos=len(recebida), inicio_diario_usado=str(au.index.min().date()), fim_diario_usado=str(au.index.max().date()),
                  calendario_usado=len(au), dias_potencia_disponivel=int(au.Active_Power.notna().sum()),
                  faltantes_por_coluna=au.isna().sum().to_dict(), max_diferenca_media_bruta_diaria=diferenca.to_dict(),
                  max_diferenca_reconstrucao_pu=(tratado[au.columns]-au).abs().max().to_dict(), cobertura_alvos=coberturas)
    (out/"auditoria_australia.json").write_text(json.dumps(res_au, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    col_inv = ["datetime", "usine_code", "equipment_name", "total_active_power_w", "daily_power_yields_kwh", "total_power_yields_kwh"]
    diario, _, _, meta_br = reconstruir_contadores(pd.read_csv(fontes[4], usecols=col_inv, low_memory=False))
    br = pd.read_csv(fontes[5], parse_dates=["timestamp"]).set_index("timestamp")
    pd.testing.assert_frame_equal(diario, br[diario.columns], check_dtype=False, check_freq=False, atol=1e-8)
    meteo = pd.read_csv(fontes[6], parse_dates=["timestamp"]).set_index("timestamp")
    weather = cfg["variaveis"][1:4]
    np.testing.assert_allclose(br[weather], meteo.reindex(br.index)[weather], atol=1e-10, equal_nan=True)
    meta_br.update(meteorologia="ERA5 diário homogêneo; estação local não participa das três entradas meteorológicas",
                   dias_meteo_completa=int(br[weather].notna().all(axis=1).sum()))
    for part in ["treino", "validacao", "teste"]:
        arquivo = atual/"dados"/f"brasil_lag3_{part}.npz"
        hashes[str(arquivo.relative_to(RAIZ))] = sha(arquivo)
        with np.load(arquivo, allow_pickle=False) as z:
            datas = pd.DatetimeIndex(z["datas"])
            np.testing.assert_allclose(z["real_kw"], br.loc[datas].energia_kwh/24, atol=1e-8)
            for atraso in [1, 2, 3]:
                assert br.loc[datas-pd.Timedelta(days=atraso)].valido.all()
        meta_br[f"janelas_{part}"] = len(datas)
    res = dict(data_auditoria_cliente="2026-10-25", experimento="chronos_diario_contadores", australia=res_au, brasil=meta_br,
               arquivos_sha256=hashes, alterou_bases_ou_modelos=False)
    for caminho, h in hashes.items():
        assert sha(RAIZ/caminho)==h
    (out/"auditoria_preprocessamento.json").write_text(json.dumps(res, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Reprodução AU e BR conferida; bases e modelos preservados.")
    print(pd.DataFrame(coberturas).to_string(index=False))
    print(f"Brasil: {meta_br['dias_validos']} dias; janelas {meta_br['janelas_treino']}/{meta_br['janelas_validacao']}/{meta_br['janelas_teste']}.")


if __name__ == "__main__":
    executar()
