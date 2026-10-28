"""Exporta tabelas e figuras da seção 3.2, sem executar treinamento."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ/"src"))
from energia_transfer.caracterizacao_sistemas_tcc import preparar_caracterizacao_sistemas as preparar_caracterizacao, gerar_figuras_sistemas as gerar_figuras

if __name__ == "__main__":
    dados = preparar_caracterizacao(RAIZ)
    figuras = gerar_figuras(dados)
    print(f"{len(figuras)} figuras exportadas em PNG e PDF: {dados['figuras']}")
