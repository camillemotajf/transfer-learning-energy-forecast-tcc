"""Prepara e audita bases reais de cinco minutos, sem medias diarias."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from energia_transfer.intradiario import gerar_bases,auditar_bases
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('etapa',choices=['australia','auditoria','base-observada','meteorologia','base-final','todas'])
 etapa=p.parse_args().etapa
 print(auditar_bases() if etapa=='auditoria' else gerar_bases())
if __name__=='__main__':main()
