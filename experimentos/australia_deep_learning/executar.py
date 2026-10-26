"""Estudo australiano de cinco minutos; motor compartilhado."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src'))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('etapa',choices=['preparar','mlp','lstm','comparar','correcao','todas'])
 etapa=p.parse_args().etapa
 if etapa in ['preparar','todas']:
  from energia_transfer.transfer_learning.dados import preparar
  print(preparar()['particoes'].to_string(index=False))
 if etapa in ['mlp','lstm','todas']:
  from energia_transfer.transfer_learning.treinamento import pretreinar
  print(pretreinar().to_string(index=False))
 if etapa in ['comparar','correcao','todas']:
  from energia_transfer.intradiario import avaliar_australia
  print(avaliar_australia().to_string(index=False))
if __name__=='__main__':main()
