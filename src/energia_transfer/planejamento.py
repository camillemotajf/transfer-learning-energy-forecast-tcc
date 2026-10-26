"""Planejamento diário histórico; o atual usa intradiario.janelas em cinco minutos."""

import pandas as pd

from .caminhos import CaminhosProjeto


def listar_janelas(historico=3, horizonte=1, caminhos=None):
    if historico < 1 or horizonte < 1:
        raise ValueError("Histórico e horizonte devem ser positivos.")
    c = caminhos or CaminhosProjeto()
    blocos = pd.read_csv(c.base_final / "blocos_consecutivos_leopoldo.csv", parse_dates=["inicio", "fim"])
    base = pd.read_csv(c.processados_brasil / "base_diaria_leopoldo_dias_validos.csv", parse_dates=["timestamp"]).set_index("timestamp")
    registros = []
    for b in blocos.itertuples(index=False):
        dias = pd.date_range(b.inicio, b.fim, freq="D")
        if len(dias) != b.dias or not dias.isin(base.index).all():
            raise ValueError(f"Bloco {b.bloco_id} tem datas ausentes.")
        for inicio in range(max(0, len(dias) - historico - horizonte + 1)):
            registros.append({"bloco_id": b.bloco_id, "entrada_inicio": dias[inicio],
                              "entrada_fim": dias[inicio + historico - 1],
                              "alvo_inicio": dias[inicio + historico],
                              "alvo_fim": dias[inicio + historico + horizonte - 1]})
    return pd.DataFrame(registros, columns=["bloco_id", "entrada_inicio", "entrada_fim", "alvo_inicio", "alvo_fim"])


def resumir_planejamento(caminhos=None):
    c = caminhos or CaminhosProjeto()
    resumo = []
    for historico in (1, 3, 7, 14):
        janelas = listar_janelas(historico, caminhos=c)
        resumo.append({"historico_dias": historico, "horizonte_dias": 1, "janelas_totais": len(janelas),
                       "treino_ate_setembro": int(janelas.alvo_fim.lt("2025-10-01").sum()),
                       "validacao_outubro": int((janelas.alvo_inicio.ge("2025-10-01") & janelas.alvo_fim.lt("2025-11-01")).sum()),
                       "teste_novembro_dezembro": int(janelas.alvo_inicio.ge("2025-11-01").sum())})
    return pd.DataFrame(resumo)
