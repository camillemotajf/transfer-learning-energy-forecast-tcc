"""Executa cada notebook em um processo Python/IPython limpo e salva as saídas.

Não abre portas de kernel nem exige servidor Jupyter. Os arquivos continuam
no formato Jupyter padrão, compatível com VS Code/Jupyter e o kernel ipykernel.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

RAIZ = Path(__file__).resolve().parents[1]


def executar(arquivo):
    from IPython.core.interactiveshell import InteractiveShell
    from IPython.utils.capture import capture_output

    arquivo = Path(arquivo).resolve()
    notebook = json.loads(arquivo.read_text(encoding="utf-8"))
    if notebook.get("nbformat") != 4:
        raise ValueError("Esperado um notebook Jupyter de formato 4.")
    shell = InteractiveShell.instance()
    shell.execution_count = 1
    for celula in notebook["cells"]:
        if celula["cell_type"] != "code":
            continue
        celula["outputs"] = []
        celula["execution_count"] = shell.execution_count
        with capture_output() as cap:
            resultado = shell.run_cell("".join(celula["source"]), store_history=True)
        if resultado.error_before_exec or resultado.error_in_exec:
            raise RuntimeError(f"{arquivo.name}, célula {celula['id']}:\n{cap.stdout}\n{cap.stderr}")
        if cap.stdout:
            celula["outputs"].append({"output_type": "stream", "name": "stdout", "text": cap.stdout.splitlines(keepends=True)})
        if cap.stderr:
            celula["outputs"].append({"output_type": "stream", "name": "stderr", "text": cap.stderr.splitlines(keepends=True)})
        for saida in cap.outputs:
            celula["outputs"].append({"output_type": "display_data", "data": saida.data, "metadata": saida.metadata})
    notebook["metadata"]["execucao"] = {"isolada": True, "python": sys.version.split()[0], "executor": "scripts/executar_notebooks.py"}
    arquivo.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK: {arquivo.relative_to(RAIZ)}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, help="Executar um notebook específico.")
    parser.add_argument("--pasta", type=Path, help="Pasta dos notebooks numerados; padrão: notebooks/.")
    parser.add_argument("--incluir-exploratorios", action="store_true")
    args = parser.parse_args()
    if args.arquivo:
        executar(args.arquivo)
        return
    pasta = args.pasta.resolve() if args.pasta else RAIZ / "notebooks"
    arquivos = sorted(pasta.glob("[0-9][0-9]_*.ipynb"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum notebook numerado encontrado em {pasta}.")
    if args.incluir_exploratorios:
        arquivos += sorted((pasta / "exploratorio").glob("*.ipynb"))
    ambiente = dict(os.environ, MPLBACKEND="Agg", PYTHONIOENCODING="utf-8")
    for arquivo in arquivos:
        print(f"Executando em processo limpo: {arquivo.name}", flush=True)
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--arquivo", str(arquivo)],
                       cwd=RAIZ, env=ambiente, check=True)


if __name__ == "__main__":
    main()
