"""Executa o piloto diario com cinco adaptadores e sem comprimir o calendario."""
import argparse
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
from energia_transfer.chronos_diario import preparar, treinar, avaliar, graficos

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("etapa", choices=["preparar", "treinar", "avaliar", "todas"])
    a = p.parse_args()
    dados = preparar(RAIZ)
    if a.etapa in ["treinar", "todas"]:
        treinar(dados)
    if a.etapa in ["avaliar", "todas"]:
        avaliar(dados)
        graficos(dados)
