"""Atualiza somente notebooks já existentes. Não cria nenhum .ipynb novo."""
import json
from pathlib import Path

RAIZ=Path(__file__).resolve().parents[1]


def md(s,i): return {"cell_type":"markdown","id":i,"metadata":{},"source":s.splitlines(keepends=True)}
def code(s,i): return {"cell_type":"code","id":i,"metadata":{},"execution_count":None,"outputs":[],"source":s.splitlines(keepends=True)}


BOOT='''from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from IPython.display import display,Image,Markdown
RAIZ=next(p for p in [Path.cwd(),*Path.cwd().parents] if (p/'src/energia_transfer').is_dir())
if str(RAIZ/'src') not in sys.path: sys.path.insert(0,str(RAIZ/'src'))
PASTA=RAIZ/'experimentos/transfer_learning_australia_brasil'
AU=RAIZ/'experimentos/australia_deep_learning'
REPORT=RAIZ/'reports/intradiario'
from energia_transfer.transfer_learning.dados import carregar,particao
_,CONFIG,CONTRATO=carregar(PASTA)
def exibir(t): display(t.round(5))
'''

PROTOCOLO='''Resolução real de **cinco minutos**, horizonte **t+5 minutos**. Os nomes dos arquivos foram mantidos por solicitação do usuário; o conteúdo foi migrado de diário para intradiário.

O alvo e a persistência (t−5 min) precisam ser originalmente medidos. Cada etapa de preenchimento causal usa até 15 minutos; no Brasil a combinação proxy + ffill pode atingir 30 minutos somente no histórico: nunca se interpola usando ponto posterior. Não se concatenam blocos interrompidos. A avaliação principal é diurna (elevação solar > 0); a avaliação 24h é complementar. Zero noturno não deve inflar a precisão.

As entradas principais são potência AC em p.u., hora local e dia do ano em seno/cosseno. O vento continua excluído. ERA5 nativa horária é auxiliar e não entra nos modelos principais. Estatísticas de normalização vêm apenas do treino australiano; alvos de validação/teste não ajustam escalas.
'''


def notebook(titulo,conteudo):
    return [md('# '+titulo+'\n\n'+PROTOCOLO,'contexto'),code(BOOT,'caminhos'),*conteudo]


TABELAS=code("""exibir(pd.read_csv(PASTA/'resultados/particoes.csv'))
print('Inputs:',CONTRATO['variaveis_por_passo'])
print('Históricos:',[l*5 for l in CONFIG['lags']],'minutos; horizonte: 5 minutos')
print(CONTRATO['normalizacao'])
""",'contrato')

AUDITORIA=code("""for dominio in ['australia','brasil']:
    print(dominio.upper())
    exibir(pd.read_csv(REPORT/f'faltantes_{dominio}_resumo.csv'))
    exibir(pd.read_csv(REPORT/f'faltantes_{dominio}_por_dia.csv').head(12))
    display(Image(filename=str(REPORT/f'faltantes_{dominio}_5min.png')))
    if dominio=='australia':
        exibir(pd.read_csv(REPORT/'invalidos_australia_por_dia.csv').groupby('variavel')[['campos_vazios','invalidos_operacionais']].sum())
""",'faltantes')

ESTUDO=code("""resumo=json.loads((REPORT/'resumo.json').read_text(encoding='utf-8'))
print(json.dumps(resumo,ensure_ascii=False,indent=2))
""",'resumo')

FONTE=code("""metricas=pd.read_csv(PASTA/'resultados/pretreino_metricas.csv')
exibir(metricas.groupby(['arquitetura','lag','particao']).agg(RMSE_pu=('RMSE_pu','mean'),DP=('RMSE_pu','std'),MAE_pu=('MAE_pu','mean'),n=('n','first')))
exibir(pd.read_csv(PASTA/'resultados/pretreino_execucoes.csv').head(15))
""",'pretreino')

ADAPTACAO=code("""from energia_transfer.deep_learning.dados import sha256
decisao=json.loads((PASTA/'resultados/decisao_validacao.json').read_text(encoding='utf-8'))
assert decisao['contrato_sha256']==sha256(PASTA/'dados/contrato.json')
ranking=pd.read_csv(PASTA/'resultados/brasil_ranking_validacao.csv').sort_values('RMSE_medio')
exibir(ranking)
print('Escolha pela validação:',decisao['melhor_rede_validacao'])
print('Incluindo persistência:',decisao['melhor_incluindo_persistencia'])
execucoes=pd.read_csv(PASTA/'resultados/brasil_execucoes.csv')
assert execucoes.query("metodo in ['cabeca','sem_ajuste']").encoder_igual_fonte.all()
exibir(execucoes.groupby(['arquitetura','metodo']).parametros_treinaveis.first().reset_index())
""",'adaptacao')

TESTE=code("""from energia_transfer.transfer_learning.avaliacao import avaliar
resultado=avaliar(PASTA)
exibir(resultado['resumo'])
print(resultado['relatorio']['qualidade_alvos'])
print('Avaliação 24h complementar:',resultado['relatorio'].get('avaliacao_24h_complementar'))
display(Image(filename=str(PASTA/'figuras/comparacao_transferencia.png')))
display(Image(filename=str(PASTA/'figuras/previsoes_brasil.png')))
display(Markdown((PASTA/'resultados/relatorio.md').read_text(encoding='utf-8')))
""",'avaliacao')

RUN=md('''## Reexecutar cálculos

Use o terminal para evitar treinos longos ocultos em uma célula:

```powershell
.venv\\Scripts\\python.exe experimentos\\transfer_learning_australia_brasil\\executar.py preparar
.venv\\Scripts\\python.exe experimentos\\transfer_learning_australia_brasil\\executar.py pretreinar
.venv\\Scripts\\python.exe experimentos\\transfer_learning_australia_brasil\\executar.py adaptar
.venv\\Scripts\\python.exe experimentos\\transfer_learning_australia_brasil\\executar.py avaliar
```

Históricos de 30 e 60 minutos (6/12 passos). São cinco sementes, MLP direta, MLP residual e LSTM direta. Treino fonte: uma de cada 12 janelas diurnas válidas, por custo de CPU, mantendo 2013–2022; validação 2023 e teste 2024–2025 em todos os instantes elegíveis. Treino brasileiro até setembro, validação outubro, teste novembro–dezembro de 2025. Os dados são autocorrelacionados: número de instantes não equivale a observações independentes. A configuração fixa máximos de 25 épocas fonte e 40 na adaptação; são experimentos iniciais, sem busca no teste.
''','execucao')


def main():
    arquivos={}
    arquivos['notebooks/00_guia_do_projeto.ipynb']=notebook('Guia do projeto — cinco minutos',[ESTUDO,TABELAS,RUN])
    arquivos['notebooks/01_australia_base_diaria.ipynb']=notebook('Austrália — medições originais de cinco minutos',[ESTUDO,AUDITORIA,
      code("""df=pd.read_pickle(RAIZ/'data/processed/australia/base_5min_australia.pkl')
exibir(df.head(12))
exibir(pd.read_csv(REPORT/'lacunas_australia_5min.csv').sort_values('duracao_min',ascending=False).head(15))
""",'base'),RUN])
    arquivos['notebooks/02_brasil_auditoria_original.ipynb']=notebook('Brasil — auditoria original em cinco minutos',[AUDITORIA,
      code("""exibir(pd.read_csv(REPORT/'lacunas_brasil_5min.csv').sort_values('duracao_min',ascending=False).head(20))
exibir(pd.read_csv(REPORT/'blocos_brasil_5min.csv').sort_values('pontos',ascending=False).head(15))
""",'lacunas')])
    BASEBR=code("""df=pd.read_pickle(RAIZ/'data/processed/brasil/base_5min_brasil.pkl')
exibir(df.head(15))
print('Alvos medidos:',df.Active_Power_original.notna().sum())
print('Históricos reconstruídos:',df.potencia_estimada.sum())
print('Grade:',df.index.to_series().diff().dropna().value_counts().to_dict())
""",'base-brasil')
    arquivos['notebooks/03_brasil_base_observada.ipynb']=notebook('Brasil — soma dos oito inversores por instante',[BASEBR,ESTUDO])
    arquivos['notebooks/04_brasil_meteorologia_publica.ipynb']=notebook('Meteorologia — distinguir resolução nativa e grade',[BASEBR,
      md('''## ERA5 não vira medição de cinco minutos

Temperatura/umidade/GHI ERA5 são horários e são mantidos para frente por no máximo 55 minutos, sem deslocar a radiação média da hora anterior para o início da hora (isso revelaria o futuro). A latência real de publicação não foi simulada. Estes dados são auxiliares, não entradas dos modelos principais.

A estação original tem longas interrupções, GHI com escala ainda não validada e não oferece a umidade necessária ao contrato meteorológico anterior. Não multiplicamos automaticamente GHI para fazê-lo coincidir com ERA5 e não interpolamos meses sem medições. Os faltantes da estação e da reanálise são relatados separadamente.
''','resolucao-meteo'),code("""exibir(df[['Weather_Temperature_Celsius','Weather_Relative_Humidity','Global_Horizontal_Radiation','meteo_resolucao_nativa_min','meteo_idade_min','temperatura_estacao_original','ghi_estacao_original_escala_nao_validada']].head(24))
exibir(pd.read_csv(REPORT/'faltantes_brasil_resumo.csv'))
""",'meteo')])
    arquivos['notebooks/05_brasil_base_final.ipynb']=notebook('Base brasileira — grade de cinco minutos e origem',[BASEBR,TABELAS,
      md('''## Reconstrução causal dos inputs

Para um inversor ausente, o proxy usa os outros sete medidos no instante e a mediana da razão dos últimos 30 dias, excluindo o instante atual e exigindo 100 doadores. Só até três ausências consecutivas já conhecidas. Não consulta o fim futuro da lacuna. Zeros físicos são restritos à escuridão solar e conferidos contra as medições. Ffill usa no máximo três passos e não encadeia estimativas indefinidamente.

`Active_Power_original` é a verdade supervisionada; `Active_Power` pode conter reconstrução apenas para contexto. Na avaliação exigimos também a persistência originalmente medida no instante anterior. Falhas mais longas interrompem as janelas. Não eliminamos um dia inteiro por uma única leitura ausente.
''','tratamento')])
    arquivos['notebooks/06_planejamento_transfer_learning.ipynb']=notebook('Janelas, histórico e horizonte em minutos',[TABELAS,
      code("""for lag in CONFIG['lags']:
    d=particao(PASTA,'brasil',lag,'teste')
    t=pd.to_datetime(d['datas'])
    print(f'Histórico {lag*5} minutos: {len(t)} alvos; último input sempre t-5 min; alvo original.')
    exibir(pd.DataFrame({'alvo':t[:8],'entrada_inicio':t[:8]-pd.Timedelta(minutes=lag*5),'entrada_fim':t[:8]-pd.Timedelta(minutes=5)}))
""",'janelas'),RUN])
    arquivos['experimentos/australia_deep_learning/notebooks/01_inputs_lags_e_faltantes.ipynb']=notebook('Inputs, lags e faltantes — Austrália em cinco minutos',[AUDITORIA,TABELAS,
      code("exibir(pd.read_csv(PASTA/'resultados/inputs_lags_validacao.csv'))",'selecao'),RUN])
    for nome,arq,fig in [('02_treino_mlp.ipynb','mlp_direta','treino_mlp.png'),('03_treino_lstm.ipynb','lstm_direta','treino_lstm.png')]:
        arquivos['experimentos/australia_deep_learning/notebooks/'+nome]=notebook(arq+' — previsão de cinco minutos',[FONTE,
          code(f"exibir(pd.read_csv(AU/'resultados/metricas_teste_5min.csv').query(\"arquitetura == '{arq}'\"))\ndisplay(Image(filename=str(AU/'figuras/{fig}')))",'metricas'),RUN])
    arquivos['experimentos/australia_deep_learning/notebooks/04_comparacao_modelos.ipynb']=notebook('Comparação MLP/LSTM/persistência — cinco minutos',[
       code("""exibir(pd.read_csv(AU/'resultados/comparacao_modelos_5min.csv'))
display(Image(filename=str(AU/'figuras/comparacao_modelos.png')))
print('Lags selecionados somente na validação australiana. Teste não muda a escolha.')
""",'comparacao')])
    arquivos['experimentos/australia_deep_learning/notebooks/05_mlp_correcao_persistencia.ipynb']=notebook('MLP residual — correção da persistência de cinco minutos',[
       code("""exibir(pd.read_csv(AU/'resultados/correcao_persistencia_5min.csv'))
display(Image(filename=str(AU/'figuras/treino_mlp_residual.png')))
print('Positivo: residual com menor RMSE que a direta no mesmo lag e semente. Sem escolher semente pelo teste.')
""",'correcao')])
    arquivos['experimentos/transfer_learning_australia_brasil/notebooks/01_dados_contrato_e_blocos.ipynb']=notebook('Contrato compartilhado Austrália–Brasil em cinco minutos',[AUDITORIA,TABELAS,ESTUDO,RUN])
    arquivos['experimentos/transfer_learning_australia_brasil/notebooks/02_pre_treino_australia.ipynb']=notebook('Pré-treino australiano — cinco minutos',[FONTE,RUN])
    arquivos['experimentos/transfer_learning_australia_brasil/notebooks/03_adaptacao_brasil.ipynb']=notebook('Adaptação brasileira — horizonte cinco minutos',[ADAPTACAO,RUN])
    arquivos['experimentos/transfer_learning_australia_brasil/notebooks/04_teste_comparacao_e_conclusao.ipynb']=notebook('Teste brasileiro — cinco minutos',[TESTE,
       md('''As métricas principais usam apenas alvos diurnos originalmente medidos. O ganho contra persistência deve ser verificado; em cinco minutos esse benchmark costuma ser forte. Transferência pode ser negativa. As estatísticas de todo o teste, incluindo noite, são complementares e não substituem o resultado diurno. Capacidades e mudanças de configuração DKA estão documentadas em `fontes_e_hipoteses.json`.
''','limites')])
    # Esta asserção impede criar qualquer notebook novo.
    for relativo in arquivos:
        if not (RAIZ/relativo).is_file(): raise FileNotFoundError(relativo)
    for relativo,celulas in arquivos.items():
        arquivo=RAIZ/relativo
        n=json.loads(arquivo.read_text(encoding='utf-8'))
        n['cells']=celulas
        n.get('metadata',{}).pop('execucao',None)
        arquivo.write_text(json.dumps(n,ensure_ascii=False,indent=1)+'\n',encoding='utf-8')
    print('Notebooks existentes atualizados:',len(arquivos))


if __name__=='__main__': main()
