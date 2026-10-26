"""Treina MLP/LSTM somente no Brasil e reúne o benchmark diário com o Chronos."""
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ/"src"))
from energia_transfer.benchmark_diario_brasil import carregar_brasil, executar_benchmark

if __name__ == "__main__":
    executar_benchmark(carregar_brasil(RAIZ))
