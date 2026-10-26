"""Localização única dos arquivos, independente do diretório do notebook."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaminhosProjeto:
    raiz: Path = Path(__file__).resolve().parents[2]

    def __post_init__(self):
        object.__setattr__(self, "raiz", Path(self.raiz).resolve())

    @property
    def brutos_brasil(self): return self.raiz / "data/raw/brasil"

    @property
    def brutos_australia(self): return self.raiz / "data/raw/australia"

    @property
    def cache_era5(self): return self.raiz / "data/external/era5"

    @property
    def configuracao_usina(self): return self.raiz / "config/usina_leopoldo.json"

    @property
    def intermediarios_brasil(self): return self.raiz / "data/interim/brasil"

    @property
    def intermediarios_meteo(self): return self.raiz / "data/interim/meteorologia"

    @property
    def exploratorios(self): return self.raiz / "data/interim/exploratorio"

    @property
    def processados_brasil(self): return self.raiz / "data/processed/brasil"

    @property
    def processados_australia(self): return self.raiz / "data/processed/australia"

    @property
    def auditoria(self): return self.raiz / "reports/auditoria"

    @property
    def base_final(self): return self.raiz / "reports/base_final"

    @property
    def meteo(self): return self.raiz / "reports/meteorologia"

    @property
    def metadados(self): return self.raiz / "reports/metadados"

    @property
    def exploratorio_imputacao(self): return self.raiz / "reports/exploratorio/imputacao"

    @property
    def exploratorio_meteo(self): return self.raiz / "reports/exploratorio/meteorologia"

    @property
    def figuras(self): return self.raiz / "reports/figures"

    @property
    def documentacao(self): return self.raiz / "docs"

    def preparar_saidas(self):
        for pasta in [self.intermediarios_brasil, self.intermediarios_meteo,
                      self.exploratorios, self.processados_brasil, self.processados_australia,
                      self.auditoria, self.base_final, self.meteo, self.metadados, self.exploratorio_imputacao,
                      self.exploratorio_meteo, self.figuras, self.documentacao]:
            pasta.mkdir(parents=True, exist_ok=True)


def localizar_raiz(inicio=None):
    """Útil em scripts interativos; não depende de caminhos da máquina do autor."""
    atual = Path(inicio or Path.cwd()).resolve()
    for pasta in [atual, *atual.parents]:
        if (pasta / "src/energia_transfer").is_dir():
            return pasta
    raise FileNotFoundError("Execute dentro da pasta do projeto que contém src/energia_transfer.")
