"""Analisa o teste congelado sem executar treinamento ou alterar o benchmark."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ/"src"))
from energia_transfer.diagnostico_erros_diarios import analisar_erros

if __name__ == "__main__":
    analisar_erros(RAIZ)
