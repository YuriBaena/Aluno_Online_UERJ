"""Consulta e parsing das disciplinas em curso (lista de turmas + grade de horários)."""

import re
from collections import defaultdict
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from autenticacao import SessaoAutenticada
from navegacao import buscar_tela
from parsing import limpar_texto, separar_codigo_nome

TEXTO_LINK_EM_CURSO = "Disciplinas em Curso"
COLUNAS_ESPERADAS = 5

_RE_ORDEM = re.compile(r"^\d+\.$")  # '1.', '2.' ...
_RE_CODIGO = re.compile(r"[A-Z]+\d+-\d+")
_RE_TEMPO = re.compile(r"^([A-Z]\d+)\s*\((\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\)")


class DisciplinasEmCursoError(Exception):
    """Falha ao consultar ou interpretar as disciplinas em curso."""


@dataclass(frozen=True)
class HorarioAula:
    dia: str  # ex.: 'Quarta'
    tempo: str  # ex.: 'M3'
    inicio: str  # ex.: '08:50'
    fim: str  # ex.: '09:40'


@dataclass(frozen=True)
class DisciplinaEmCurso:
    codigo: str
    nome: str
    turma: str
    local_ava: str
    local_aula: str
    horarios: tuple[HorarioAula, ...]


def buscar_disciplinas_em_curso(autenticado: SessaoAutenticada) -> list[DisciplinaEmCurso]:
    """Fluxo completo: abre a tela e interpreta a resposta."""
    return parse_disciplinas_em_curso(buscar_html_em_curso(autenticado))


def buscar_html_em_curso(autenticado: SessaoAutenticada) -> str:
    return buscar_tela(autenticado, TEXTO_LINK_EM_CURSO)


def parse_disciplinas_em_curso(html: str) -> list[DisciplinaEmCurso]:
    soup = BeautifulSoup(html, "html.parser")

    tabela = soup.find("table", class_="reportTable")
    if tabela is None:
        raise DisciplinasEmCursoError("Tabela de disciplinas em curso não encontrada.")

    horarios_por_codigo = _parse_grade_horaria(soup)

    disciplinas = []
    for linha in tabela.find_all("tr"):
        celulas = linha.find_all("td", recursive=False)
        if len(celulas) == COLUNAS_ESPERADAS and _RE_ORDEM.match(limpar_texto(celulas[0].get_text())):
            disciplinas.append(_linha_para_disciplina(celulas, horarios_por_codigo))
    return disciplinas


def _linha_para_disciplina(
    celulas: list[Tag],
    horarios_por_codigo: dict[str, tuple[HorarioAula, ...]],
) -> DisciplinaEmCurso:
    colunas = [limpar_texto(c.get_text(" ")) for c in celulas]
    codigo, nome = separar_codigo_nome(colunas[1])

    return DisciplinaEmCurso(
        codigo=codigo,
        nome=nome,
        turma=colunas[2],
        local_ava=colunas[3],
        local_aula=colunas[4],
        horarios=horarios_por_codigo.get(codigo, ()),
    )


def _parse_grade_horaria(soup: BeautifulSoup) -> dict[str, tuple[HorarioAula, ...]]:
    """Converte a grade (tempos x dias) em {codigo: horários}.

    O HTML da grade tem <TR> mal fechados, então não dá para confiar nas linhas:
    cada <th> de tempo ('M1 (07:00 - 07:50)') é seguido por um <td> por dia.
    """
    grade = soup.find("table", class_="table")
    if grade is None:
        return {}

    cabecalho = grade.find("tr")
    if cabecalho is None:
        return {}
    dias = [th.get_text(strip=True) for th in cabecalho.find_all("th")][1:]  # 1º é 'Tempo'
    ordem_dia = {dia: posicao for posicao, dia in enumerate(dias)}

    coletados: dict[str, list[HorarioAula]] = defaultdict(list)
    for th in grade.find_all("th"):
        correspondencia = _RE_TEMPO.match(th.get_text(" ", strip=True))
        if not correspondencia:  # cabeçalhos 'Tempo', 'Segunda', ...
            continue

        tempo, inicio, fim = correspondencia.groups()
        celulas = th.find_next_siblings("td", limit=len(dias))
        for dia, celula in zip(dias, celulas):
            for codigo in _RE_CODIGO.findall(celula.get_text(" ", strip=True)):
                coletados[codigo].append(HorarioAula(dia, tempo, inicio, fim))

    return {
        codigo: tuple(sorted(horarios, key=lambda h: (ordem_dia[h.dia], h.inicio)))
        for codigo, horarios in coletados.items()
    }