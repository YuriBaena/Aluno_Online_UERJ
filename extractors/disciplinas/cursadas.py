"""Consulta e parsing das disciplinas já cursadas (tela 'Requisitos Realizados')."""

from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from ..core.autenticacao import SessaoAutenticada
from ..core.navegacao import buscar_tela
from ..core.parsing import (
    extrair_id_consulta,
    limpar_texto,
    para_decimal,
    para_int,
    separar_codigo_nome,
)

TEXTO_LINK_CURSADAS = "Requisitos Cursados"
COLUNAS_ESPERADAS = 8


class DisciplinasCursadasError(Exception):
    """Falha ao consultar ou interpretar as disciplinas cursadas."""


@dataclass(frozen=True)
class DisciplinaCursada:
    periodo: str  # ex.: '2024/1'
    id: str | None
    codigo: str
    nome: str
    creditos: int
    carga_horaria: int
    tipo: str
    frequencia: float | None  # percentual; None quando não informada
    nota: float | None  # None quando não informada (ex.: cancelada)
    situacao: str  # ex.: 'Aprov. Nota', 'Cancelado'


def buscar_disciplinas_cursadas(autenticado: SessaoAutenticada) -> list[DisciplinaCursada]:
    """Fluxo completo: abre a tela e interpreta a resposta."""
    return parse_disciplinas_cursadas(buscar_html_cursadas(autenticado))


def buscar_html_cursadas(autenticado: SessaoAutenticada) -> str:
    return buscar_tela(autenticado, TEXTO_LINK_CURSADAS)


def parse_disciplinas_cursadas(html: str) -> list[DisciplinaCursada]:
    tabelas = BeautifulSoup(html, "html.parser").find_all("table", class_="reportTable")
    if not tabelas:
        raise DisciplinasCursadasError("Tabela de disciplinas cursadas não encontrada.")

    cursadas = []
    periodo = ""
    for tabela in tabelas:
        for linha in tabela.find_all("tr"):
            celulas = linha.find_all("td", recursive=False)
            if len(celulas) != COLUNAS_ESPERADAS:  # ignora cabeçalho e linhas separadoras
                continue

            # o período só aparece na 1ª linha de cada semestre; as demais ficam em branco
            periodo = limpar_texto(celulas[0].get_text()) or periodo
            cursadas.append(_linha_para_cursada(periodo, celulas))
    return cursadas


def _linha_para_cursada(periodo: str, celulas: list[Tag]) -> DisciplinaCursada:
    colunas = [limpar_texto(c.get_text(" ")) for c in celulas]
    codigo, nome = separar_codigo_nome(colunas[1])

    return DisciplinaCursada(
        periodo=periodo,
        id=extrair_id_consulta(celulas[1]),
        codigo=codigo,
        nome=nome,
        creditos=para_int(colunas[2]),
        carga_horaria=para_int(colunas[3]),
        tipo=colunas[4],
        frequencia=para_decimal(colunas[5]),
        nota=para_decimal(colunas[6]),
        situacao=colunas[7],
    )