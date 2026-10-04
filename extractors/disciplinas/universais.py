"""Consulta e parsing das disciplinas universais com turma no período atual."""

from dataclasses import dataclass

from bs4 import BeautifulSoup

from ..core.autenticacao import SessaoAutenticada
from ..core.navegacao import buscar_tela
from ..core.parsing import (
    extrair_id_consulta,
    limpar_texto,
    para_int,
    separar_codigo_nome,
)

TEXTO_LINK_UNIVERSAIS = "Disciplinas Universais"
COLUNAS_ESPERADAS = 4  # Disciplina | Cred. | CH Total | Turma Período?


class DisciplinasUniversaisError(Exception):
    """Falha ao consultar ou interpretar as disciplinas universais."""


@dataclass(frozen=True)
class DisciplinaUniversal:
    id: str | None
    codigo: str
    nome: str
    creditos: int
    carga_horaria: int
    turma_no_periodo: str


def buscar_disciplinas_universais(autenticado: SessaoAutenticada) -> list[DisciplinaUniversal]:
    """Fluxo completo: abre a tela e interpreta a resposta."""
    return parse_disciplinas_universais(buscar_html_universais(autenticado))


def buscar_html_universais(autenticado: SessaoAutenticada) -> str:
    return buscar_tela(autenticado, TEXTO_LINK_UNIVERSAIS)


def parse_disciplinas_universais(html: str) -> list[DisciplinaUniversal]:
    tabela = BeautifulSoup(html, "html.parser").find("table", class_="reportTable")
    if tabela is None:
        raise DisciplinasUniversaisError("Tabela de disciplinas universais não encontrada.")

    universais = []
    for linha in tabela.find_all("tr"):
        celulas = linha.find_all("td", recursive=False)
        if len(celulas) != COLUNAS_ESPERADAS:  # ignora o cabeçalho (<th>)
            continue

        colunas = [limpar_texto(c.get_text(" ")) for c in celulas]
        codigo, nome = separar_codigo_nome(colunas[0])
        universais.append(
            DisciplinaUniversal(
                id=extrair_id_consulta(celulas[0]),
                codigo=codigo,
                nome=nome,
                creditos=para_int(colunas[1]),
                carga_horaria=para_int(colunas[2]),
                turma_no_periodo=colunas[3],
            )
        )
    return universais