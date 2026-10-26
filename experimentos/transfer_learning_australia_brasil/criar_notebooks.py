"""Atualiza somente notebooks existentes para cinco minutos."""
from pathlib import Path
import runpy
if __name__=='__main__':
 runpy.run_path(str(Path(__file__).resolve().parents[2]/'scripts/atualizar_notebooks_5min.py'),run_name='__main__')
