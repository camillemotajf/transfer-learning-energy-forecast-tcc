"""Executar etapas do experimento de transferência em cinco minutos."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("etapa", choices=["preparar", "pretreinar", "adaptar", "avaliar", "todas"])
    etapa = p.parse_args().etapa
    if etapa in ["preparar", "todas"]:
        from energia_transfer.transfer_learning.dados import preparar
        print(preparar()["particoes"].to_string(index=False), flush=True)
    if etapa in ["pretreinar", "todas"]:
        from energia_transfer.transfer_learning.treinamento import pretreinar
        print(pretreinar().groupby(["arquitetura", "lag", "particao"]).RMSE_pu.mean().to_string(), flush=True)
    if etapa in ["adaptar", "todas"]:
        from energia_transfer.transfer_learning.treinamento import adaptar
        print(adaptar()["validacao"].to_string(index=False), flush=True)
    if etapa in ["avaliar", "todas"]:
        from energia_transfer.transfer_learning.avaliacao import avaliar
        print(avaliar()["resumo"].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
