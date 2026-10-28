"""Dicionário em português e cobertura de todas as colunas, sem dependências externas.

Executar da raiz: python scripts/tabelar_colunas_originais_tcc.py
Não modifica dados originais nem calcula alvos tratados.
"""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / 'reports/tcc/caracterizacao_dados_crus'
VAZIOS = {'', 'NA', 'N/A', 'NaN', 'nan', 'NULL', 'null', 'None', '<NA>', '#N/A'}
import sys
sys.path.insert(0, str(RAIZ / 'src'))
from energia_transfer.dicionario_colunas import significado


def construir():
    manifesto = json.loads((PASTA / 'manifesto.json').read_text(encoding='utf-8'))
    resultado = []
    resumo_alvos = []
    hashes = {}
    for chave, meta in manifesto['fontes'].items():
        nome = Path(meta['arquivo'].replace('\\', '/')).name
        caminho = RAIZ / 'data/raw' / ('australia' if chave == 'australia' else 'brasil') / nome
        inicio = datetime.fromisoformat(meta['inicio_calendario'])
        ndias = meta['dias_calendario']
        equipamentos = meta['equipamentos']
        nequip = len(equipamentos)
        mapa = {nome: i for i, nome in enumerate(equipamentos)}
        esperados = ndias * 288 * nequip
        with caminho.open(encoding='utf-8-sig', newline='') as arquivo:
            leitor = csv.DictReader(arquivo)
            colunas = leitor.fieldnames
            info = {c: significado(c) for c in colunas}
            texto = {c for c in colunas if info[c][1] in {'identificador', 'data/hora', 'código'}}
            presencas = {c: bytearray(esperados) for c in colunas}
            presentes = dict.fromkeys(colunas, 0)
            linhas = 0
            for linha in leitor:
                if chave != 'australia' and linha['usine_code'] != '07-07FX':
                    continue
                linhas += 1
                instante = datetime.fromisoformat(linha['timestamp' if chave == 'australia' else 'datetime'].replace('Z', '+00:00'))
                if chave != 'australia':
                    instante = instante.astimezone(timezone(timedelta(hours=-3))).replace(tzinfo=None)
                dia = (instante.date() - inicio.date()).days
                equip = 0 if chave == 'australia' else mapa.get(linha['equipment_name'])
                pos = ((dia * 288 + instante.hour * 12 + instante.minute // 5) * nequip + equip
                       if 0 <= dia < ndias and equip is not None else None)
                for coluna in colunas:
                    valor = linha[coluna]
                    if valor in VAZIOS:
                        continue
                    presentes[coluna] += 1
                    valido = True
                    if coluna not in texto:
                        try:
                            valido = math.isfinite(float(valor))
                        except ValueError:
                            valido = False
                    if valido and pos is not None:
                        presencas[coluna][pos] = 1
        fonte = meta['fonte'].replace(' — ', ': ')
        for coluna in colunas:
            papel = 'Variável auxiliar ou metadado'
            if coluna == 'Active_Power':
                papel = 'Alvo univariado australiano; média das leituras disponíveis no protocolo diário'
            elif coluna == 'total_active_power_w':
                papel = 'Origem do alvo de potência no protocolo de cinco minutos; requer os oito inversores'
            elif coluna in {'daily_power_yields_kwh', 'total_power_yields_kwh'}:
                papel = 'Construção/validação do alvo diário brasileiro; não é covariável do modelo univariado'
            n = sum(presencas[coluna])
            resultado.append(dict(fonte=fonte, coluna=coluna, significado_pt=info[coluna][0], unidade=info[coluna][1],
                                  papel=papel, linhas_selecionadas=linhas, campos_preenchidos=presentes[coluna],
                                  cobertura_nas_linhas_pct=100*presentes[coluna]/linhas,
                                  posicoes_esperadas=esperados, posicoes_disponiveis=n,
                                  cobertura_temporal_pct=100*n/esperados,
                                  criterio_temporal='Campo não vazio' if coluna in texto else 'Ao menos um valor numérico finito'))
        alvo = 'Active_Power' if chave == 'australia' else 'total_active_power_w'
        if alvo in presencas:
            grade = presencas[alvo]
            completos = sum(all(grade[p:p+nequip]) for p in range(0, esperados, nequip))
            resumo_alvos.append(dict(fonte=fonte, coluna=alvo, intervalos_esperados=ndias*288,
                                     intervalos_com_todos_inversores_ou_sistema=completos,
                                     cobertura_sistema_pct=100*completos/(ndias*288)))
        with caminho.open('rb') as arquivo:
            hashes[str(caminho.relative_to(RAIZ))] = hashlib.file_digest(arquivo, 'sha256').hexdigest()
        print(f'{chave}: {linhas} linhas; {len(colunas)} colunas', flush=True)
    tabdir = PASTA / 'tabelas'
    for nome, registros in [('dicionario_cobertura_colunas_originais.csv', resultado),
                             ('cobertura_alvos_originais.csv', resumo_alvos)]:
        with (tabdir / nome).open('w', encoding='utf-8-sig', newline='') as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=list(registros[0]))
            escritor.writeheader()
            escritor.writerows(registros)
    texto = '# Colunas e cobertura dos dados originais\n\n'
    texto += ('Significados interpretados a partir dos nomes dos campos e do protocolo local; '
              'unidades, códigos e canais marcados como pendentes exigem documentação do fornecedor. '
              'Não se corrigem valores nem se imputam registros.\n\n'
              'Cobertura nas linhas: campos não vazios / linhas selecionadas, incluindo duplicatas. '
              'Cobertura temporal: intervalos de cinco minutos por equipamento com valor numérico finito '
              '(ou campo não vazio para metadados), divididos por todos os intervalos esperados no calendário. '
              'Duplicatas contam uma vez por intervalo; zeros e valores negativos finitos são presentes, '
              'sem garantir validade física. Austrália: arquivo integral, de 25/07/2013 a 23/08/2025. '
              'Brasil: código 07-07FX, calendário local completo de 2025; denominador de linhas inclui '
              'todas as linhas desse código. Bordas também entram no denominador temporal.\n\n')
    for fonte in dict.fromkeys(r['fonte'] for r in resultado):
        texto += f'## {fonte}\n\n| Coluna original | Significado em português | Unidade | Campos preenchidos (%) | Cobertura temporal (%) |\n|---|---|---|---:|---:|\n'
        for r in resultado:
            if r['fonte'] == fonte:
                texto += f"| `{r['coluna']}` | {r['significado_pt']} | {r['unidade']} | {r['cobertura_nas_linhas_pct']:.2f} | {r['cobertura_temporal_pct']:.2f} |\n"
        texto += '\n'
    texto += '## Alvos univariados\n\n'
    for r in resumo_alvos:
        texto += (f"* {r['fonte']}, `{r['coluna']}`: {r['intervalos_com_todos_inversores_ou_sistema']:,} "
                  f"de {r['intervalos_esperados']:,} intervalos com o sistema completo observado "
                  f"({r['cobertura_sistema_pct']:.2f}%).\n")
    texto += ('\nNo Brasil, cobertura por inversor não equivale à cobertura da soma simultânea dos oito inversores. '
              'Para o protocolo diário, o alvo é derivado dos contadores e não é uma coluna original: '
              '284 de 365 dias foram aprovados (77,81%). Não confundir aprovação diária com presença de telemetria. '
              'No experimento australiano até 2023, 3778 de 3812 dias têm potência diária disponível (99,11%); '
              'isso não comprova cobertura intradiária integral. O modelo univariado usa somente o histórico do alvo, '
              'mesmo quando outras colunas servem à sua reconstrução ou validação.\n')
    (PASTA / 'tabela_colunas_originais.md').write_text(texto, encoding='utf-8')
    (PASTA / 'manifesto_colunas_originais.json').write_text(json.dumps(dict(fontes_sha256=hashes,
        script='scripts/tabelar_colunas_originais_tcc.py', n_colunas=len(resultado)), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    construir()
