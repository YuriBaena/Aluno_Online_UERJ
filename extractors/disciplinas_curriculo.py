"""Consulta e parsing das disciplinas do currículo."""

from dataclasses import dataclass

from bs4 import BeautifulSoup

from autenticacao import SessaoAutenticada
from navegacao import buscar_tela
from parsing import extrair_id_consulta, separar_codigo_nome

TEXTO_LINK_CURRICULO = "Disciplinas do Currículo"
COLUNAS_ESPERADAS = 9


class DisciplinasError(Exception):
    """Falha ao consultar ou interpretar as disciplinas."""


@dataclass(frozen=True)
class Disciplina:
    id: str | None
    codigo: str
    nome: str
    periodo: str
    atendida: str
    tipo: str
    ramificacao: str
    creditos: str
    carga_horaria: str
    trava_credito: str
    turma_no_periodo: str


def buscar_disciplinas(autenticado: SessaoAutenticada) -> list[Disciplina]:
    """Fluxo completo: abre a tela do currículo e interpreta a resposta."""
    return parse_disciplinas(buscar_html_disciplinas(autenticado))


def buscar_html_disciplinas(autenticado: SessaoAutenticada) -> str:
    return buscar_tela(autenticado, TEXTO_LINK_CURRICULO)


def parse_disciplinas(html: str) -> list[Disciplina]:
    tabela = BeautifulSoup(html, "html.parser").find("table", class_="reportTable")
    if tabela is None:
        raise DisciplinasError("Tabela de disciplinas não encontrada na resposta.")

    disciplinas = []
    for linha in tabela.find_all("tr"):
        celulas = linha.find_all("td", recursive=False)
        if len(celulas) >= COLUNAS_ESPERADAS:  # ignora o cabeçalho (<th>)
            disciplinas.append(_linha_para_disciplina(celulas))
    return disciplinas


def _linha_para_disciplina(celulas) -> Disciplina:
    colunas = [c.get_text(" ", strip=True) for c in celulas]
    codigo, nome = separar_codigo_nome(colunas[0])

    return Disciplina(
        id=extrair_id_consulta(celulas[0]),
        codigo=codigo,
        nome=nome,
        periodo=colunas[1],
        atendida=colunas[2],
        tipo=colunas[3],
        ramificacao=colunas[4],
        creditos=colunas[5],
        carga_horaria=colunas[6],
        trava_credito=colunas[7],
        turma_no_periodo=colunas[8],
    )