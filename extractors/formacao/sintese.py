"""Consulta e parsing da tela 'Síntese da Formação'."""

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from ..core.autenticacao import SessaoAutenticada
from ..core.navegacao import buscar_tela
from ..core.parsing import limpar_texto, para_decimal

TEXTO_LINK_SINTESE = "Síntese da Formação"

_RE_NUMERO = re.compile(r"\d+")


class SinteseFormacaoError(Exception):
    """Falha ao consultar ou interpretar a síntese da formação."""


@dataclass(frozen=True)
class RequisitoTitulacao:
    descricao: str
    cumprido: int | None
    a_cumprir: int | None
    situacao: str


@dataclass(frozen=True)
class RequisitoCurriculo:
    descricao: str
    nivel: int  # 0 = ramificação; 1 = grupos dentro dela
    cumprido: int | None
    exigido: int | None
    situacao: str


@dataclass(frozen=True)
class PeriodoLetivo:
    periodo: str  # ex.: '2025/2'
    situacao: str  # ex.: 'Cursado', 'Inscrito'


@dataclass(frozen=True)
class SinteseFormacao:
    ingresso: str
    situacao_aluno: str
    centro: str
    unidade: str
    curso: str
    versao_curricular: str
    regime: str
    coeficiente_rendimento: float | None
    titulacao: str
    situacao_titulacao: str
    conclusao: str  # vazio quando ainda não concluído
    periodo_conclusao: str
    colacao_grau: str
    requisitos_titulacao: tuple[RequisitoTitulacao, ...]
    requisitos_curriculo: tuple[RequisitoCurriculo, ...]
    minimo_periodos: int | None
    periodos_utilizados: int | None
    maximo_periodos: int | None
    periodos_restantes: int | None
    periodos: tuple[PeriodoLetivo, ...]


def buscar_sintese(autenticado: SessaoAutenticada) -> SinteseFormacao:
    """Fluxo completo: abre a tela e interpreta a resposta."""
    return parse_sintese(buscar_html_sintese(autenticado))


def buscar_html_sintese(autenticado: SessaoAutenticada) -> str:
    return buscar_tela(autenticado, TEXTO_LINK_SINTESE)


def parse_sintese(html: str) -> SinteseFormacao:
    soup = BeautifulSoup(html, "html.parser")

    if soup.find("b", string=re.compile(r"^\s*Curso:")) is None:
        raise SinteseFormacaoError(
            "Síntese da formação não reconhecida (sessão expirada ou layout alterado)."
        )

    return SinteseFormacao(
        ingresso=_valor(soup, "Ingresso:"),
        situacao_aluno=_valor(soup, "Situação:", 0),
        centro=_valor(soup, "Centro:"),
        unidade=_valor(soup, "Unidade:"),
        curso=_valor(soup, "Curso:"),
        versao_curricular=_valor(soup, "Versão Curricular"),
        regime=_valor(soup, "Regime:"),
        coeficiente_rendimento=para_decimal(_valor(soup, "Coeficiente de Rendimento:")),
        titulacao=_valor(soup, "Titulação:"),
        situacao_titulacao=_valor(soup, "Situação:", 1),
        conclusao=_sem_placeholder(_valor(soup, "Conclusão (mês/ano):")),
        periodo_conclusao=_sem_placeholder(_valor(soup, "Período:")),
        colacao_grau=_sem_placeholder(_valor(soup, "Colação de Grau:")),
        requisitos_titulacao=_parse_requisitos_titulacao(soup),
        requisitos_curriculo=_parse_requisitos_curriculo(soup),
        minimo_periodos=_int(_valor(soup, "Mínimo de Períodos")),
        periodos_utilizados=_int(_valor(soup, "Períodos Utilizados")),
        maximo_periodos=_int(_valor(soup, "Máximo de Períodos")),
        periodos_restantes=_int(_valor(soup, "Períodos Restantes")),
        periodos=_parse_periodos(soup),
    )


# --------------------------------------------------------------------------- #
# Tabelas
# --------------------------------------------------------------------------- #

def _parse_requisitos_titulacao(soup: BeautifulSoup) -> tuple[RequisitoTitulacao, ...]:
    return tuple(
        RequisitoTitulacao(
            descricao=_descricao(c[0]),
            cumprido=_int(c[1].get_text()),
            a_cumprir=_int(c[2].get_text()),
            situacao=limpar_texto(c[3].get_text(" ")),
        )
        for c in _linhas_de_celulas(soup, "Requisitos Curriculares da Titulação", 4)
    )


def _parse_requisitos_curriculo(soup: BeautifulSoup) -> tuple[RequisitoCurriculo, ...]:
    return tuple(
        RequisitoCurriculo(
            descricao=_descricao(c[0]),
            nivel=_nivel(c[0]),
            cumprido=_int(c[1].get_text()),
            exigido=_int(c[2].get_text()),
            situacao=limpar_texto(c[3].get_text(" ")),
        )
        for c in _linhas_de_celulas(soup, "Requisitos do Currículo", 4)
    )


def _parse_periodos(soup: BeautifulSoup) -> tuple[PeriodoLetivo, ...]:
    """A tabela tem dois blocos lado a lado: (período, situação) | espaço | (período, situação)."""
    periodos = []
    for c in _linhas_de_celulas(soup, "Período", 5):
        for posicao in (0, 3):
            periodo = limpar_texto(c[posicao].get_text(" "))
            if periodo:
                periodos.append(PeriodoLetivo(periodo, limpar_texto(c[posicao + 1].get_text(" "))))
    return tuple(sorted(periodos, key=lambda p: p.periodo))


# --------------------------------------------------------------------------- #
# Utilitários de HTML
# --------------------------------------------------------------------------- #

def _linhas_de_celulas(soup: BeautifulSoup, titulo_coluna: str, colunas: int) -> list[list[Tag]]:
    """Células (<td>) das linhas da tabela cujo <th> é `titulo_coluna`."""
    tabela = _tabela_com_cabecalho(soup, titulo_coluna)
    if tabela is None:
        return []

    linhas = []
    for tr in tabela.find_all("tr"):
        if tr.find_parent("table") is not tabela:  # ignora tabelas aninhadas
            continue
        celulas = tr.find_all("td", recursive=False)
        if len(celulas) == colunas:
            linhas.append(celulas)
    return linhas


def _tabela_com_cabecalho(soup: BeautifulSoup, titulo: str) -> Tag | None:
    for tabela in soup.find_all("table"):
        for th in tabela.find_all("th"):
            if th.find_parent("table") is tabela and limpar_texto(th.get_text()) == titulo:
                return tabela
    return None


def _valor(soup: BeautifulSoup, rotulo: str, indice: int = 0) -> str:
    """Texto que vem logo após <b>rotulo</b>. `indice` desambigua rótulos repetidos."""
    achados = soup.find_all("b", string=re.compile(rf"^\s*{re.escape(rotulo)}"))
    if indice >= len(achados):
        return ""
    return limpar_texto(str(achados[indice].next_sibling or ""))


def _descricao(celula: Tag) -> str:
    return limpar_texto(celula.get_text().replace("\u2022", " "))


def _nivel(celula: Tag) -> int:
    """Nível de indentação: cada nível usa 3 &nbsp; antes do marcador '•'."""
    prefixo = celula.get_text().split("\u2022")[0]
    return prefixo.count("\xa0") // 3


def _int(texto: str) -> int | None:
    correspondencia = _RE_NUMERO.search(texto)
    return int(correspondencia.group()) if correspondencia else None


def _sem_placeholder(valor: str) -> str:
    """'--/----' e similares (campo ainda não preenchido) viram ''."""
    return valor if any(c.isalnum() for c in valor) else ""