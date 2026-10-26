"""Diagnóstico descritivo do teste diário congelado; não treina nem seleciona modelos."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .chronos_experimentos import salvar_json, sha256

REGIMES = ["queda_brusca", "variacao_moderada", "subida_brusca"]
ROTULOS = {"persistencia": "Persistência", "portfolio_covariaveis": "Chronos com covariáveis",
           "mlp_brasil": "MLP Brasil", "lstm_brasil": "LSTM Brasil"}


def classificar_variacao(delta, limiar):
    if not np.isfinite(limiar) or limiar < 0:
        raise ValueError("Limiar precisa ser finito e não negativo.")
    delta = pd.Series(delta)
    return pd.Series(np.select([delta.lt(0) & delta.le(-limiar), delta.gt(0) & delta.ge(limiar)],
                               ["queda_brusca", "subida_brusca"], default="variacao_moderada"), index=delta.index)


def calcular_limiares(base):
    """Percentis 75/90 das mudanças absolutas, somente em pares diários do treino."""
    assert base.index.is_unique and base.index.is_monotonic_increasing
    calendario = base.asfreq("D")
    delta = calendario.Active_Power.diff().loc[:"2025-09-30"].dropna()
    if delta.empty:
        raise ValueError("Sem pares consecutivos de treino para definir mudanças bruscas.")
    return dict(limiar_principal_kw=float(delta.abs().quantile(.75)),
                limiar_sensibilidade_kw=float(delta.abs().quantile(.90)), n_pares_treino=len(delta),
                periodo="2025-01-01 a 2025-09-30", regra="Q75 da variação absoluta no treino; Q90 como sensibilidade")


def resumo_erros(g):
    e, absoluto = g.erro_kw.to_numpy(), g.erro_absoluto_kw.to_numpy()
    soma2 = float(np.sum(e**2))
    ordenado = np.sort(absoluto)[::-1]
    total_abs = float(ordenado.sum())
    rmse_p = float(np.sqrt(np.mean((g.persistencia_kw-g.real_kw)**2)))
    rmse = float(np.sqrt(np.mean(e**2)))
    n = len(e)
    # Gini descritivo: 0 = erros absolutos iguais; não é um teste de uniformidade.
    asc = ordenado[::-1]
    gini = float(np.sum((2*np.arange(1, n+1)-n-1)*asc)/(n*total_abs)) if total_abs else 0.
    return dict(n=n, MAE_kw=float(absoluto.mean()), RMSE_kw=rmse, BIAS_kw=float(e.mean()),
                mediana_erro_kw=float(np.median(e)), desvio_erro_kw=float(np.std(e, ddof=1)) if n>1 else np.nan,
                P50_absoluto_kw=float(np.quantile(absoluto, .5)), P90_absoluto_kw=float(np.quantile(absoluto, .9)),
                P95_absoluto_kw=float(np.quantile(absoluto, .95)), max_absoluto_kw=float(absoluto.max()),
                superestimacoes=int((e>0).sum()), subestimacoes=int((e<0).sum()),
                WAPE_pct=100*total_abs/float(g.real_kw.abs().sum()) if g.real_kw.abs().sum() else np.nan,
                Skill_RMSE_pct=100*(1-rmse/rmse_p) if rmse_p else np.nan,
                top5_SSE_pct=100*float(np.sum(ordenado[:5]**2))/soma2 if soma2 else 0.,
                top10_SSE_pct=100*float(np.sum(ordenado[:10]**2))/soma2 if soma2 else 0.,
                top5_erro_absoluto_pct=100*float(ordenado[:5].sum())/total_abs if total_abs else 0.,
                gini_erro_absoluto=gini)


def correlacao_postos(a, b):
    x = pd.DataFrame(dict(a=a, b=b)).dropna()
    rho = float(x.a.rank().corr(x.b.rank())) if len(x)>2 and x.a.nunique()>1 and x.b.nunique()>1 else np.nan
    return rho, len(x)


def _qualidade_por_dia(inv):
    assert not inv.duplicated(["dia", "equipment_name"]).any()
    grupos = inv.groupby("dia")
    q = grupos.agg(n_equipamentos=("equipment_name", "nunique"), n_consistentes=("consistente", "sum"),
                  energia_diario_soma_kwh=("energia_dia_kwh", "sum"), energia_acumulado_soma_kwh=("energia_pelo_acumulado", "sum"),
                  max_diferenca_inversor_kwh=("diferenca_contadores", "max"),
                  soma_diferencas_absolutas_kwh=("diferenca_contadores", "sum"),
                  leituras_potencia_24h_soma=("leituras_potencia_24h", "sum"),
                  leituras_potencia_24h_minimo=("leituras_potencia_24h", "min"))
    q["fracao_leituras_potencia_pct"] = 100*q.leituras_potencia_24h_soma/(8*288)
    q["menor_cobertura_inversor_pct"] = 100*q.leituras_potencia_24h_minimo/288
    # A soma é referência alternativa somente quando todos os equipamentos passam.
    ok = q.n_equipamentos.eq(8) & q.n_consistentes.eq(8)
    q["referencia_acumulado_kw"] = (q.energia_acumulado_soma_kwh/24).where(ok)
    q["diferenca_referencias_kw"] = (q.energia_diario_soma_kwh-q.energia_acumulado_soma_kwh)/24
    return q


def analisar_erros(raiz):
    raiz = Path(raiz).resolve()
    pasta = raiz/"experimentos/chronos_diario_contadores"
    resultados = pasta/"resultados"
    out = resultados/"diagnostico_erros"
    out.mkdir(exist_ok=True)
    fontes = [resultados/n for n in ["benchmark_previsoes_teste.csv", "benchmark_final.csv", "benchmark_decisao_validacao.json",
                                     "decisao_validacao.json", "auditoria_calendario_brasil.csv", "leopoldo_qualidade_por_inversor.csv"]]
    hashes = {str(p.relative_to(raiz)): sha256(p) for p in fontes}
    d = pd.read_csv(fontes[0], parse_dates=["timestamp"]).set_index("timestamp").sort_index()
    met = pd.read_csv(fontes[1])
    modelos = met.modelo.tolist()
    assert len(d)==44 and d.index.is_unique and d.index.is_monotonic_increasing
    assert len(modelos)==len(set(modelos)) and met.n.eq(len(d)).all()
    escolha = json.loads(fontes[2].read_text(encoding="utf-8"))["escolhido"]["modelo"]
    chronos = json.loads(fontes[3].read_text(encoding="utf-8"))["escolhido"]["modelo"]
    foco = list(dict.fromkeys(["persistencia", chronos, "mlp_brasil", "lstm_brasil"]))
    base = pd.read_csv(fontes[4], parse_dates=["timestamp"]).set_index("timestamp").sort_index().asfreq("D")
    limiares = calcular_limiares(base)
    np.testing.assert_allclose(d.referencia_diaria_kw, base.loc[d.index].Active_Power, atol=1e-8)
    np.testing.assert_allclose(d.persistencia, base.Active_Power.shift(1).loc[d.index], atol=1e-8)
    assert base.loc[d.index].valido.all()
    inv = pd.read_csv(fontes[5], parse_dates=["dia"])
    qualidade = _qualidade_por_dia(inv).reindex(d.index)
    assert qualidade.n_equipamentos.eq(8).all() and qualidade.n_consistentes.eq(8).all()
    np.testing.assert_allclose(qualidade.energia_diario_soma_kwh/24, d.referencia_diaria_kw, atol=1e-8)
    assert qualidade.referencia_acumulado_kw.notna().all()
    d = d.join(qualidade)
    d["mes"] = d.index.strftime("%Y-%m")
    d["variacao_real_kw"] = d.referencia_diaria_kw-d.persistencia
    d["variacao_real_pct"] = 100*d.variacao_real_kw/d.persistencia.replace(0, np.nan)
    d["regime"] = classificar_variacao(d.variacao_real_kw, limiares["limiar_principal_kw"])
    d["ghi_dia_alvo_wm2"] = base.Global_Horizontal_Radiation.reindex(d.index)
    d["variacao_ghi_wm2"] = base.Global_Horizontal_Radiation.diff().reindex(d.index)
    d["umidade_dia_alvo_pct"] = base.Weather_Relative_Humidity.reindex(d.index)
    d["temperatura_dia_alvo_c"] = base.Weather_Temperature_Celsius.reindex(d.index)
    erros = []
    for modelo in modelos:
        t = d[["mes", "variacao_real_kw", "variacao_real_pct", "regime", "fracao_leituras_potencia_pct",
               "max_diferenca_inversor_kwh", "diferenca_referencias_kw", "referencia_acumulado_kw", "variacao_ghi_wm2"]].copy()
        t["modelo"], t["real_kw"], t["persistencia_kw"], t["previsto_kw"] = modelo, d.referencia_diaria_kw, d.persistencia, d[modelo]
        t["erro_kw"] = t.previsto_kw-t.real_kw
        t["erro_absoluto_kw"] = t.erro_kw.abs()
        t["erro_quadratico_kw2"] = t.erro_kw**2
        t["erro_kwh_dia"] = t.erro_kw*24
        t["ganho_absoluto_sobre_persistencia_kw"] = (t.persistencia_kw-t.real_kw).abs()-t.erro_absoluto_kw
        sse = t.erro_quadratico_kw2.sum()
        t["fracao_SSE_modelo_pct"] = 100*t.erro_quadratico_kw2/sse if sse else 0.
        t["rank_erro_absoluto"] = t.erro_absoluto_kw.rank(method="first", ascending=False).astype(int)
        t["maior_desvio_top5"] = t.rank_erro_absoluto.le(5)
        erros.append(t.reset_index())
        d[f"erro_{modelo}_kw"] = t.erro_kw
        # Confere a reprodução do benchmark antes de interpretar os resíduos.
        r = met[met.modelo.eq(modelo)].iloc[0]
        np.testing.assert_allclose([t.erro_absoluto_kw.mean(), np.sqrt(sse/len(t))], [r.MAE_kW, r.RMSE_kW], rtol=1e-10)
    e = pd.concat(erros, ignore_index=True)
    resumo, mensal, regimes, contribuicoes, correlacoes, sensibilidade = [], [], [], [], [], []
    for modelo, g in e.groupby("modelo", sort=False):
        resumo.append(dict(modelo=modelo, **resumo_erros(g)))
        for mes, gm in g.groupby("mes"):
            mensal.append(dict(modelo=modelo, mes=mes, **resumo_erros(gm)))
        for quantil, limiar in [(75, limiares["limiar_principal_kw"]), (90, limiares["limiar_sensibilidade_kw"])]:
            gg = g.assign(regime_limiar=classificar_variacao(g.variacao_real_kw, limiar))
            for regime in REGIMES:
                gr = gg[gg.regime_limiar.eq(regime)]
                if gr.empty:
                    continue
                pct_dias = 100*len(gr)/len(gg)
                pct_sse = 100*gr.erro_quadratico_kw2.sum()/gg.erro_quadratico_kw2.sum() if gg.erro_quadratico_kw2.sum() else 0.
                regimes.append(dict(modelo=modelo, quantil_treino=quantil, limiar_kw=limiar, regime=regime,
                                    fracao_dias_pct=pct_dias, fracao_SSE_pct=pct_sse,
                                    concentracao_SSE_por_fracao_dias=pct_sse/pct_dias, **resumo_erros(gr)))
        ordenado = g.sort_values("erro_quadratico_kw2", ascending=False)
        cumulativo = ordenado.erro_quadratico_kw2.cumsum()
        for k, valor in enumerate(cumulativo, 1):
            contribuicoes.append(dict(modelo=modelo, n_maiores_dias=k, fracao_dias_pct=100*k/len(g),
                                      fracao_SSE_acumulada_pct=100*valor/cumulativo.iloc[-1] if cumulativo.iloc[-1] else 0.))
        for indicador, absoluto in [("variacao_real_kw", True), ("variacao_ghi_wm2", True),
                                     ("fracao_leituras_potencia_pct", False), ("max_diferenca_inversor_kwh", False)]:
            v = g[indicador].abs() if absoluto else g[indicador]
            rho, n = correlacao_postos(g.erro_absoluto_kw, v)
            correlacoes.append(dict(modelo=modelo, indicador=("abs_" if absoluto else "")+indicador,
                                    tipo_erro="absoluto", rho_spearman_descritivo=rho, n=n))
        rho, n = correlacao_postos(g.erro_kw, g.variacao_ghi_wm2)
        correlacoes.append(dict(modelo=modelo, indicador="variacao_ghi_wm2", tipo_erro="assinado",
                                rho_spearman_descritivo=rho, n=n))
        alt = g.previsto_kw-g.referencia_acumulado_kw
        sensibilidade.append(dict(modelo=modelo, n=len(g), RMSE_referencia_diario_kw=float(np.sqrt(g.erro_quadratico_kw2.mean())),
                                  RMSE_referencia_acumulado_kw=float(np.sqrt((alt**2).mean())),
                                  MAE_referencia_diario_kw=float(g.erro_absoluto_kw.mean()), MAE_referencia_acumulado_kw=float(alt.abs().mean())))
    tabelas = dict(erros_individuais=e, erros_por_dia=d.reset_index(), resumo_distribuicao=pd.DataFrame(resumo),
                   metricas_mensais=pd.DataFrame(mensal), metricas_por_regime=pd.DataFrame(regimes),
                   concentracao_cumulativa=pd.DataFrame(contribuicoes), correlacoes_descritivas=pd.DataFrame(correlacoes),
                   sensibilidade_referencia=pd.DataFrame(sensibilidade))
    tabelas["maiores_desvios"] = e.sort_values(["modelo", "rank_erro_absoluto"]).groupby("modelo", sort=False).head(5)
    contexto_mensal = []
    for mes, g in d.groupby("mes"):
        completo = base.loc[mes]
        contexto_mensal.append(dict(mes=mes, dias_calendario=len(completo), dias_contadores_validos=int(completo.valido.sum()),
                                   alvos_avaliados=len(g), media_real_kw=float(g.referencia_diaria_kw.mean()),
                                   media_variacao_absoluta_kw=float(g.variacao_real_kw.abs().mean()),
                                   quedas_bruscas=int(g.regime.eq("queda_brusca").sum()), subidas_bruscas=int(g.regime.eq("subida_brusca").sum()),
                                   media_ghi_alvos_wm2=float(g.ghi_dia_alvo_wm2.mean()),
                                   media_fracao_leituras_pct=float(g.fracao_leituras_potencia_pct.mean())))
    tabelas["contexto_mensal"] = pd.DataFrame(contexto_mensal)
    for nome, tabela in tabelas.items():
        tabela.to_csv(out/f"{nome}.csv", index=False)
    meta = dict(n_dias=44, n_modelos=len(modelos), n_erros=len(e), foco=foco, escolhido_validacao_geral=escolha,
                chronos_escolhido_validacao=chronos, definicao_erro="previsto - referência; positivo = superestimação",
                **limiares, max_diferenca_referencias_kw=float(d.diferenca_referencias_kw.abs().max()),
                percentil75_calculado_sem_teste=True, treino_ou_selecao_executados=False,
                meteorologia_dia_alvo="somente diagnóstico retrospectivo, não foi entrada do modelo",
                cobertura="fração das 2304 leituras inversor-horário possíveis; não é cobertura simultânea da planta",
                referencia_alternativa="soma das diferenças do contador acumulado / 24; todas as previsões originais mantidas, inclusive persistência",
                referencias_contadores_independentes=False, observacao_referencia="contadores dos mesmos equipamentos; não são medição independente de calibração",
                codigo_sha256=sha256(Path(__file__)), arquivos_sha256=hashes)
    meta["assinatura"] = hashlib.sha256(json.dumps(meta, sort_keys=True).encode()).hexdigest()
    salvar_json(out/"manifesto.json", meta)
    resultado = dict(raiz=raiz, pasta=pasta, out=out, meta=meta, tabelas=tabelas, foco=foco)
    graficos(resultado)
    relatorio(resultado)
    # A análise deve preservar integralmente as previsões, decisões e alvos de entrada.
    for caminho, h in hashes.items():
        assert sha256(raiz/caminho)==h
    print(f"Diagnóstico concluído: {len(d)} dias, {len(modelos)} modelos, {len(e)} resíduos; sem retreino.", flush=True)
    return resultado


def graficos(r):
    import matplotlib.pyplot as plt
    out, tab, foco = r["out"], r["tabelas"], r["foco"]
    e, dia = tab["erros_individuais"], tab["erros_por_dia"]
    cores = dict(zip(foco, ["#777777", "#287db1", "#b76c18", "#379155"]))
    rotulo = lambda nome: ROTULOS.get(nome, nome)
    grade = pd.date_range("2025-11-01", "2025-12-31")
    t = dia.set_index("timestamp").reindex(grade)
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), gridspec_kw=dict(height_ratios=[1.2, 1, 1]))
    for modelo in foco:
        axes[0].plot(grade, t[f"erro_{modelo}_kw"], ".-", lw=1, ms=3, color=cores[modelo], label=rotulo(modelo))
    axes[0].axhline(0, color="black", lw=.8)
    axes[0].set(ylabel="Erro assinado (kW)", title="44 alvos de teste: positivo = superestimação; lacunas preservadas")
    axes[0].legend(ncol=2, fontsize=9)
    for ax, modelo in zip(axes[1:], [r["meta"]["chronos_escolhido_validacao"], "lstm_brasil"]):
        top = e[e.modelo.eq(modelo)].nlargest(5, "erro_absoluto_kw").iloc[::-1]
        ax.barh(top.timestamp.dt.strftime("%d/%m"), top.erro_kw, color=np.where(top.erro_kw>0, "#c86c3e", "#397fad"))
        ax.axvline(0, color="black", lw=.8)
        ax.set(xlabel="Erro assinado (kW)", title=f"Cinco maiores desvios — {rotulo(modelo)}")
    for ax in axes:
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out/"erros_individuais_e_maiores.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    erros_foco = e[e.modelo.isin(foco)].erro_kw
    bordas = np.linspace(float(erros_foco.min())-1, float(erros_foco.max())+1, 16)
    for modelo in foco:
        g = e[e.modelo.eq(modelo)]
        axes[0, 0].hist(g.erro_kw, bins=bordas, histtype="step", linewidth=1.7, color=cores[modelo], label=rotulo(modelo))
        v = np.sort(g.erro_absoluto_kw)
        axes[1, 0].step(v, np.arange(1, len(v)+1)/len(v), where="post", color=cores[modelo], label=rotulo(modelo))
        c = tab["concentracao_cumulativa"].query("modelo == @modelo")
        axes[1, 1].plot(c.fracao_dias_pct, c.fracao_SSE_acumulada_pct, color=cores[modelo], label=rotulo(modelo))
    axes[0, 0].axvline(0, color="black", lw=.8)
    axes[0, 0].set(xlabel="Erro assinado (kW)", ylabel="Número de dias", title="Distribuição dos resíduos; bins comuns")
    axes[0, 1].boxplot([e[e.modelo.eq(n)].erro_kw for n in foco], tick_labels=[rotulo(n) for n in foco], showmeans=True)
    axes[0, 1].axhline(0, color="black", lw=.8)
    axes[0, 1].set(ylabel="Erro assinado (kW)", title="Mediana, dispersão e extremos")
    axes[0, 1].tick_params(axis="x", rotation=15)
    axes[1, 0].set(xlabel="Erro absoluto (kW)", ylabel="Fração acumulada de dias", title="Distribuição empírica do erro absoluto")
    axes[1, 1].plot([0, 100], [0, 100], "--", color="gray", label="Erros de mesma magnitude")
    axes[1, 1].set(xlabel="% de dias, dos maiores para os menores erros", ylabel="% da soma dos erros quadráticos", title="Concentração do erro em poucos dias", xlim=(0, 100), ylim=(0, 101))
    for ax in axes.flat:
        ax.grid(alpha=.2)
    axes[0, 0].legend(fontsize=8)
    axes[1, 1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out/"distribuicao_e_concentracao.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for ax, valor in zip(axes[0], ["RMSE_kw", "BIAS_kw"]):
        mensal = tab["metricas_mensais"].query("modelo in @foco").pivot(index="modelo", columns="mes", values=valor).reindex(foco)
        mensal.index = [rotulo(n) for n in mensal.index]
        mensal.plot.bar(ax=ax, rot=15, color=["#377fb1", "#d49a37"])
        ax.set(xlabel="", ylabel=valor.replace("_", " "), title="Novembro × dezembro: mesmos recortes entre modelos")
        ax.axhline(0, color="black", lw=.7)
    reg = tab["metricas_por_regime"].query("modelo in @foco and quantil_treino == 75")
    v = reg.pivot(index="regime", columns="modelo", values="MAE_kw").reindex(REGIMES)[foco]
    v.columns = [rotulo(n) for n in v.columns]
    v.index = ["Queda brusca", "Moderada", "Subida brusca"]
    v.plot.bar(ax=axes[1, 0], rot=0, color=[cores[n] for n in foco])
    axes[1, 0].set(xlabel="", ylabel="MAE (kW)", title=f"Regimes: limiar do treino = {r['meta']['limiar_principal_kw']:.2f} kW")
    for modelo in foco:
        g = e[e.modelo.eq(modelo)]
        axes[1, 1].scatter(g.variacao_real_kw, g.erro_kw, s=24, alpha=.65, color=cores[modelo], label=rotulo(modelo))
    for valor in [-r["meta"]["limiar_principal_kw"], r["meta"]["limiar_principal_kw"]]:
        axes[1, 1].axvline(valor, ls="--", color="gray", lw=.8)
    axes[1, 1].axhline(0, color="black", lw=.8)
    axes[1, 1].set(xlabel="Variação observada em relação a ontem (kW)", ylabel="Erro previsto − real (kW)", title="Erro × mudança: ambos compartilham o alvo")
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out/"meses_e_mudancas_bruscas.png", dpi=150)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for modelo in foco:
        g = e[e.modelo.eq(modelo)]
        for ax, x in [(axes[0, 0], "fracao_leituras_potencia_pct"), (axes[0, 1], "max_diferenca_inversor_kwh"), (axes[1, 0], "variacao_ghi_wm2")]:
            y = g.erro_kw if x=="variacao_ghi_wm2" else g.erro_absoluto_kw
            ax.scatter(g[x], y, s=25, alpha=.6, color=cores[modelo], label=rotulo(modelo))
    axes[0, 0].set(xlabel="% de leituras inversor-horário de potência (2304 possíveis)", ylabel="Erro absoluto (kW)", title="Telemetria de potência; não é cobertura simultânea")
    axes[0, 1].set(xlabel="Maior diferença entre contadores de um inversor (kWh)", ylabel="Erro absoluto (kW)", title="Consistência dos contadores nos dias aprovados")
    axes[1, 0].axhline(0, color="black", lw=.8)
    axes[1, 0].set(xlabel="GHI do dia alvo − GHI de ontem (W/m²)", ylabel="Erro assinado (kW)", title="Meteorologia do alvo: somente explicação retrospectiva")
    sens = tab["sensibilidade_referencia"].set_index("modelo").loc[foco, ["RMSE_referencia_diario_kw", "RMSE_referencia_acumulado_kw"]]
    sens.columns = ["Contador diário", "Diferença do acumulado"]
    sens.index = [rotulo(n) for n in sens.index]
    sens.plot.bar(ax=axes[1, 1], rot=15, color=["#377fb1", "#d49a37"])
    axes[1, 1].set(xlabel="", ylabel="RMSE (kW)", title="Mesmas previsões; troca apenas da referência")
    axes[0, 0].legend(fontsize=8)
    for ax in axes.flat:
        ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out/"qualidade_e_meteorologia.png", dpi=150)
    plt.close(fig)


def relatorio(r):
    tab, meta, foco = r["tabelas"], r["meta"], r["foco"]
    dist = tab["resumo_distribuicao"].set_index("modelo")
    reg = tab["metricas_por_regime"]
    linhas = ["# Diagnóstico dos 44 erros diários", "",
              "Erro = previsto − referência. Positivo indica superestimação; energia diária tem erro 24 vezes o erro em potência média.",
              f"Analisados 44 dias e {meta['n_modelos']} métodos ({meta['n_erros']} resíduos), sem alterar previsões, hiperparâmetros ou decisões.",
              "Modelos em foco: persistência, Chronos escolhido pela validação, MLP Brasil e LSTM Brasil (semente 42).", "",
              "## Distribuição e concentração", "", "| Modelo | MAE kW | RMSE kW | Viés kW | P90 absoluto kW | Top 5: % do erro quadrático |", "|---|---:|---:|---:|---:|---:|"]
    for modelo in foco:
        v = dist.loc[modelo]
        linhas.append(f"| {ROTULOS.get(modelo, modelo)} | {v.MAE_kw:.2f} | {v.RMSE_kw:.2f} | {v.BIAS_kw:.2f} | {v.P90_absoluto_kw:.2f} | {v.top5_SSE_pct:.1f} |")
    linhas += ["", "Se todos os erros tivessem a mesma magnitude, cinco dos 44 dias responderiam por 11,36% da soma de erros quadráticos. A curva de concentração é descritiva, sem teste de uniformidade ou normalidade.",
               "", "## Dias com maiores desvios", "", "| Modelo | Dia | Variação real kW | Erro kW | Regime |", "|---|---|---:|---:|---|"]
    for modelo in foco:
        for v in tab["maiores_desvios"].query("modelo == @modelo").itertuples():
            linhas.append(f"| {ROTULOS.get(modelo, modelo)} | {v.timestamp:%d/%m/%Y} | {v.variacao_real_kw:.2f} | {v.erro_kw:.2f} | {v.regime} |")
    linhas += ["", "## Quedas e subidas bruscas", "",
               f"Limiar principal = Q75 das mudanças absolutas de {meta['n_pares_treino']} pares consecutivos válidos no treino: {meta['limiar_principal_kw']:.2f} kW. Sensibilidade Q90: {meta['limiar_sensibilidade_kw']:.2f} kW. Não escolhemos limiares pelos erros de teste.",
               "", "| Modelo | Regime | Dias | % dos dias | MAE kW | % do erro quadrático | Razão concentração |", "|---|---|---:|---:|---:|---:|---:|"]
    for modelo in foco:
        for v in reg.query("modelo == @modelo and quantil_treino == 75").itertuples():
            linhas.append(f"| {ROTULOS.get(modelo, modelo)} | {v.regime} | {v.n} | {v.fracao_dias_pct:.1f} | {v.MAE_kw:.2f} | {v.fracao_SSE_pct:.1f} | {v.concentracao_SSE_por_fracao_dias:.2f} |")
    linhas += ["", "Razão acima de 1 indica mais erro quadrático do que a fração de dias daquele regime. Os resíduos e a variação real compartilham o alvo: a associação é em parte mecânica, especialmente para persistência (erro = −variação). Não demonstra causa nem ausência de informação por si só.",
               "", "## Novembro e dezembro", "", "| Modelo | Mês | N | MAE kW | RMSE kW | Viés kW |", "|---|---|---:|---:|---:|---:|"]
    for modelo in foco:
        for v in tab["metricas_mensais"].query("modelo == @modelo").itertuples():
            linhas.append(f"| {ROTULOS.get(modelo, modelo)} | {v.mes} | {v.n} | {v.MAE_kw:.2f} | {v.RMSE_kw:.2f} | {v.BIAS_kw:.2f} |")
    linhas += ["", "São 44 alvos selecionados entre 61 dias do bimestre. A comparação mensal descreve esses alvos, não o desempenho nos dias reprovados nem sazonalidade geral. Veja também mudanças de geração, GHI e composição de regimes em contexto_mensal.csv.",
               "", "## Qualidade dos alvos e informações ausentes", "",
               f"Todos os 44 dias têm oito inversores aprovados. O maior desvio entre a referência pela soma dos contadores diários e a soma das diferenças acumuladas é {meta['max_diferenca_referencias_kw']:.4f} kW ({24*meta['max_diferenca_referencias_kw']:.2f} kWh/dia).",
               "A análise de sensibilidade mantém todas as previsões, inclusive a persistência original, e troca apenas a referência. Esses contadores são dos mesmos equipamentos: a concordância não exclui erro de calibração ou outro erro comum.",
               "A fração de leituras usa 8×288 registros inversor-horário possíveis, não horários com a planta completa. Telemetria esparsa de potência não implica perda do total diário registrado pelo contador.",
               "GHI, umidade e temperatura do próprio dia alvo aparecem somente neste diagnóstico retrospectivo. Os modelos receberam meteorologia passada e calendário; não receberam a meteorologia futura observada. Correlações de postos são descritivas, com 44 dias, possíveis fatores comuns e seleção por qualidade; não estabelecem causalidade.",
               "", "## Leitura conjunta", ""]
    for modelo in foco:
        top = tab["maiores_desvios"].query("modelo == @modelo").iloc[0]
        mm = tab["metricas_mensais"].query("modelo == @modelo").set_index("mes")
        rg = reg.query("modelo == @modelo and quantil_treino == 75").set_index("regime")
        queda = rg.loc["queda_brusca"] if "queda_brusca" in rg.index else None
        linhas.append(f"- **{ROTULOS.get(modelo, modelo)}:** maior desvio em {top.timestamp:%d/%m}: {top.erro_kw:+.2f} kW; os cinco maiores dias somam {dist.loc[modelo, 'top5_SSE_pct']:.1f}% do erro quadrático. RMSE novembro/dezembro: {mm.loc['2025-11', 'RMSE_kw']:.2f}/{mm.loc['2025-12', 'RMSE_kw']:.2f} kW.")
        if queda is not None:
            linhas.append(f"  Quedas bruscas: {int(queda.n)} dias ({queda.fracao_dias_pct:.1f}%) respondem por {queda.fracao_SSE_pct:.1f}% do erro quadrático; viés geral {dist.loc[modelo, 'BIAS_kw']:+.2f} kW.")
    rr = reg[reg.modelo.eq(meta["chronos_escolhido_validacao"]) & reg.quantil_treino.eq(75)]
    bruscos = rr[rr.regime.ne("variacao_moderada")]
    linhas += ["", f"No Chronos escolhido em outubro, os {int(bruscos.n.sum())} dias de mudanças bruscas ({bruscos.fracao_dias_pct.sum():.1f}% dos dias) concentram {bruscos.fracao_SSE_pct.sum():.1f}% do erro quadrático. Há concentração tanto nas quedas quanto nas subidas: a dificuldade não se restringe às quedas."]
    for modelo in ["mlp_brasil", "lstm_brasil"]:
        moderado = reg.query("modelo == @modelo and quantil_treino == 75 and regime == 'variacao_moderada'").iloc[0]
        mm = tab["metricas_mensais"].query("modelo == @modelo").set_index("mes")
        linhas.append(f"{ROTULOS[modelo]} também superestima fora das grandes mudanças: viés {moderado.BIAS_kw:+.2f} kW nos {int(moderado.n)} dias moderados. O viés passa de {mm.loc['2025-11', 'BIAS_kw']:+.2f} kW em novembro para {mm.loc['2025-12', 'BIAS_kw']:+.2f} kW em dezembro. Isso sugere uma limitação adicional de generalização, sem identificar seu mecanismo.")
    contexto = tab["contexto_mensal"].set_index("mes")
    correlacoes = tab["correlacoes_descritivas"]
    rho_clima = correlacoes[correlacoes.modelo.eq(meta["chronos_escolhido_validacao"]) & correlacoes.tipo_erro.eq("assinado")].iloc[0].rho_spearman_descritivo
    linhas += [f"Nos alvos avaliados, a geração média passa de {contexto.loc['2025-11', 'media_real_kw']:.2f} kW para {contexto.loc['2025-12', 'media_real_kw']:.2f} kW; o GHI médio passa de {contexto.loc['2025-11', 'media_ghi_alvos_wm2']:.2f} para {contexto.loc['2025-12', 'media_ghi_alvos_wm2']:.2f} W/m². Essa mudança de composição deve ser considerada ao comparar os meses.",
               f"A magnitude do erro tem associação pequena com a magnitude da mudança do GHI, mas a direção contém outro sinal: no Chronos, a correlação de postos entre erro assinado e mudança assinada de GHI é {rho_clima:.2f}. Isso é compatível com superestimar em reduções da radiação e subestimar em aumentos. É evidência descritiva, não prova da causa dominante nem estimativa do ganho de acrescentar previsões meteorológicas.",
               "Previsões meteorológicas operacionais poderiam testar essa hipótese em outro período; a reanálise observada no alvo não deve ser fornecida retroativamente como se fosse uma previsão disponível.",
               "Não podemos atribuir os desvios a uma única causa com este teste pequeno.",
               "A concordância interna dos contadores torna improvável que a diferença entre esses dois totais explique erros de dezenas de kW; não substitui uma referência independente. Investigar eventos operacionais ou qualidade comum dos medidores exige registros externos.",
               "", "Este diagnóstico não autoriza excluir os piores dias do benchmark nem reajustar o modelo pelo teste. Uma alteração motivada por estes resultados exige uma nova avaliação temporal independente."]
    (r["out"]/"analise_erros.md").write_text("\n".join(linhas)+"\n", encoding="utf-8")
