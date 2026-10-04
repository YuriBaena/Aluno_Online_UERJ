"""Consulta e parsing do detalhe de cada disciplina (requisitos, turmas e vagas)."""

import re
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from ..core.autenticacao import SessaoAutenticada
from ..core.cliente_http import post_html
from ..core.config import REQUISICAO_URL
from ..core.parsing import separar_codigo_nome

PAUSA_PADRAO_SEGUNDOS = 0.5

_RE_TURMA = re.compile(r"TURMA:\s*(\S+)")
_RE_PREFERENCIAL = re.compile(r"Preferencial:\s*(\S+)", re.IGNORECASE)
_RE_ID_EMENTA = re.compile(r"ementaDisciplina\((\d+)\)")
_RE_SEM_REQUISITO = re.compile(r"n[ãa]o possui requisito", re.IGNORECASE)
# o site usa singular quando há uma única turma ("Turma da Disciplina")
_RE_BLOCO_TURMAS = re.compile(r"Turmas?\s+da\s+Disciplina", re.IGNORECASE)
_RE_BLOCO_REQUISITOS = re.compile(r"Requisitos?\s+da\s+Disciplina", re.IGNORECASE)


class DetalheDisciplinaError(Exception):
    """Falha ao consultar ou interpretar o detalhe de uma disciplina."""


# --------------------------------------------------------------------------- #
# Modelos
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class FormularioConsulta:
    """Campos hidden do formulário 'output' da página de disciplinas do currículo."""
    token: str
    requisicao: str
    matricula: str


@dataclass(frozen=True)
class Horario:
    dia: str
    tempos: tuple[str, ...]


@dataclass(frozen=True)
class VagaTurma:
    """Vagas atualizadas da turma (oferecidas x ocupadas)."""
    tipo: str
    oferecidas: int
    ocupadas: int


@dataclass(frozen=True)
class VagaSolicitacao:
    """Vagas para solicitação de inscrição."""
    tipo: str
    oferecidas: int
    solicitadas: int
    solicitadas_preferenciais: int


@dataclass(frozen=True)
class Turma:
    numero: str
    preferencial: bool
    horarios: tuple[Horario, ...]
    local: str
    docente: str
    vagas: tuple[VagaTurma, ...]
    solicitacoes: tuple[VagaSolicitacao, ...]


@dataclass(frozen=True)
class Requisito:
    """Requisito de inscrição. Ex.: tipo='Trava', descricao='69 créditos na ramificação ...'."""
    tipo: str
    descricao: str


@dataclass(frozen=True)
class DetalheDisciplina:
    id: str | None
    codigo: str
    nome: str
    creditos: int
    carga_horaria_total: int
    carga_horaria_semanal: int
    universal: bool
    permite_conflito_horario: bool
    permite_situacao_em_preparo: bool
    tipo_aprovacao: str
    duracao: str
    requisitos: tuple[Requisito, ...]
    turmas: tuple[Turma, ...]


# --------------------------------------------------------------------------- #
# Busca
# --------------------------------------------------------------------------- #

def buscar_detalhe(
    autenticado: SessaoAutenticada,
    html_curriculo: str,
    id_disciplina: str,
) -> DetalheDisciplina:
    """Busca o detalhe de uma disciplina a partir do id interno (ex.: '4827')."""
    formulario = extrair_formulario_consulta(html_curriculo)
    return _consultar(autenticado, formulario, id_disciplina)


def buscar_detalhes(
    autenticado: SessaoAutenticada,
    html_curriculo: str,
    ids_disciplinas: Iterable[str],
    pausa_segundos: float = PAUSA_PADRAO_SEGUNDOS,
) -> list[DetalheDisciplina]:
    """Busca o detalhe de várias disciplinas (falha na primeira que der erro)."""
    return list(iterar_detalhes(autenticado, html_curriculo, ids_disciplinas, pausa_segundos))


def iterar_detalhes(
    autenticado: SessaoAutenticada,
    html_curriculo: str,
    ids_disciplinas: Iterable[str],
    pausa_segundos: float = PAUSA_PADRAO_SEGUNDOS,
) -> Iterator[DetalheDisciplina]:
    """Versão em gerador: permite mostrar progresso ou tratar erros a cada disciplina."""
    formulario = extrair_formulario_consulta(html_curriculo)

    for posicao, id_disciplina in enumerate(ids_disciplinas):
        if posicao and pausa_segundos > 0:
            time.sleep(pausa_segundos)  # evita rajada de requisições no portal
        yield _consultar(autenticado, formulario, id_disciplina)


def extrair_formulario_consulta(html_curriculo: str) -> FormularioConsulta:
    """Lê _token, requisicao e matricula do formulário da página de disciplinas."""
    soup = BeautifulSoup(html_curriculo, "html.parser")
    formulario = soup.find("form", attrs={"name": "output"})
    if formulario is None:
        raise DetalheDisciplinaError(
            "Formulário 'output' não encontrado na página de disciplinas do currículo."
        )

    return FormularioConsulta(
        token=_valor_hidden(formulario, "_token"),
        requisicao=_valor_hidden(formulario, "requisicao"),
        matricula=_valor_hidden(formulario, "matricula"),
    )


def buscar_html_detalhe(
    autenticado: SessaoAutenticada,
    formulario: FormularioConsulta,
    id_disciplina: str,
) -> str:
    payload = {
        "_token": formulario.token,
        "requisicao": formulario.requisicao,
        "matricula": formulario.matricula,
        "disciplinas[0]": id_disciplina,  # notação de array do PHP
    }
    return post_html(autenticado.sessao, REQUISICAO_URL, payload)


def _consultar(
    autenticado: SessaoAutenticada,
    formulario: FormularioConsulta,
    id_disciplina: str,
) -> DetalheDisciplina:
    html = buscar_html_detalhe(autenticado, formulario, id_disciplina)
    return parse_detalhe(html, id_disciplina)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

def parse_detalhe(html: str, id_disciplina: str | None = None) -> DetalheDisciplina:
    soup = BeautifulSoup(html, "html.parser")

    codigo, nome = _parse_titulo(soup)
    campos = _textos_folha(soup)

    return DetalheDisciplina(
        id=id_disciplina or _extrair_id_ementa(html),
        codigo=codigo,
        nome=nome,
        creditos=_para_int(_valor_campo(campos, "Número de créditos:")),
        carga_horaria_total=_para_int(_valor_campo(campos, "Carga Horária Total:")),
        carga_horaria_semanal=_para_int(_valor_campo(campos, "Carga Horária Semanal:")),
        universal=_para_bool(_valor_campo(campos, "Oferecida como Universal?")),
        permite_conflito_horario=_para_bool(_valor_campo(campos, "Permite Conflito de Horário?")),
        permite_situacao_em_preparo=_para_bool(_valor_campo(campos, "Permite Situação em Preparo?")),
        tipo_aprovacao=_valor_campo(campos, "Tipo de Aprovação:"),
        duracao=_valor_campo(campos, "Tempo de Duração:"),
        requisitos=_parse_requisitos(soup),
        turmas=_parse_turmas(soup),
    )


def _parse_titulo(soup: BeautifulSoup) -> tuple[str, str]:
    rotulo = soup.find("b", string=re.compile(r"^\s*Disciplina:"))
    if rotulo is None:
        raise DetalheDisciplinaError(
            "Página de detalhe não reconhecida (sessão expirada ou layout alterado)."
        )
    titulo = " ".join(str(rotulo.next_sibling or "").split())
    return separar_codigo_nome(titulo)


def _extrair_id_ementa(html: str) -> str | None:
    correspondencia = _RE_ID_EMENTA.search(html)
    return correspondencia.group(1) if correspondencia else None


def _parse_requisitos(soup: BeautifulSoup) -> tuple[Requisito, ...]:
    bloco = _localizar_bloco(soup, _RE_BLOCO_REQUISITOS)
    corpo = bloco.find("div", class_="divContentBlockBody") if bloco else None
    if corpo is None:
        return ()

    if _RE_SEM_REQUISITO.search(corpo.get_text(" ", strip=True)):
        return ()

    # formato conhecido: <div><b>Trava:</b></div><div>descrição</div> por requisito
    requisitos = tuple(
        requisito
        for rotulo in corpo.find_all("b")
        if (requisito := _parse_requisito(rotulo)) is not None
    )
    if requisitos:
        return requisitos

    # formato desconhecido: preserva o texto cru em vez de perder a informação
    return tuple(Requisito(tipo="", descricao=linha) for linha in _linhas_de_texto(corpo))


def _parse_requisito(rotulo: Tag) -> Requisito | None:
    tipo = rotulo.get_text(strip=True).rstrip(":").strip()
    valor = rotulo.parent.find_next_sibling("div") if rotulo.parent else None
    descricao = valor.get_text(" ", strip=True) if valor else ""
    return Requisito(tipo=tipo, descricao=descricao) if descricao else None


def _parse_turmas(soup: BeautifulSoup) -> tuple[Turma, ...]:
    bloco = _localizar_bloco(soup, _RE_BLOCO_TURMAS)
    tabela = bloco.find("table") if bloco else None
    if tabela is None:
        return ()

    return tuple(
        _parse_turma(linha)
        for linha in _linhas_proprias(tabela)
        if _RE_TURMA.search(linha.get_text(" ", strip=True))
    )


def _parse_turma(linha: Tag) -> Turma:
    texto = linha.get_text(" ", strip=True)
    vagas, solicitacoes = _parse_vagas(linha)

    return Turma(
        numero=_buscar(_RE_TURMA, texto),
        preferencial=_para_bool(_buscar(_RE_PREFERENCIAL, texto)),
        horarios=_parse_horarios(linha),
        local=_texto_ao_lado(linha, "Local das Aulas"),
        docente=_texto_ao_lado(linha, "Docente"),
        vagas=vagas,
        solicitacoes=solicitacoes,
    )


def _parse_horarios(linha: Tag) -> tuple[Horario, ...]:
    container = _valor_ao_lado(linha, "Tempos")
    if container is None:
        return ()

    # estrutura: <div>DIA</div><div>&nbsp;M5&nbsp;M6</div><br> repetida por dia
    filhos = container.find_all("div", recursive=False)
    return tuple(
        Horario(
            dia=dia.get_text(strip=True),
            tempos=tuple(tempos.get_text(" ").split()),
        )
        for dia, tempos in zip(filhos[0::2], filhos[1::2])
    )


def _parse_vagas(linha: Tag) -> tuple[tuple[VagaTurma, ...], tuple[VagaSolicitacao, ...]]:
    vagas: tuple[VagaTurma, ...] = ()
    solicitacoes: tuple[VagaSolicitacao, ...] = ()

    for tabela in linha.find_all("table"):
        texto = tabela.get_text(" ", strip=True)
        if "Solicitadas" in texto:
            solicitacoes = tuple(
                VagaSolicitacao(c[0], int(c[1]), int(c[2]), int(c[3]))
                for c in _linhas_numericas(tabela, colunas=4)
            )
        elif "Ocupadas" in texto:
            vagas = tuple(
                VagaTurma(c[0], int(c[1]), int(c[2]))
                for c in _linhas_numericas(tabela, colunas=3)
            )
    return vagas, solicitacoes


# --------------------------------------------------------------------------- #
# Utilitários de HTML
# --------------------------------------------------------------------------- #

def _valor_hidden(formulario: Tag, nome: str) -> str:
    tag = formulario.find("input", attrs={"name": nome})
    if tag is None or not tag.get("value"):
        raise DetalheDisciplinaError(f"Campo '{nome}' não encontrado no formulário.")
    return tag["value"]


def _localizar_bloco(soup: BeautifulSoup, titulo: re.Pattern) -> Tag | None:
    for cabecalho in soup.find_all("div", class_="divContentBlockHeader"):
        if titulo.search(cabecalho.get_text(" ", strip=True)):
            return cabecalho.find_parent("div", class_="divContentBlock")
    return None


def _linhas_de_texto(corpo: Tag) -> tuple[str, ...]:
    elementos = (
        corpo.find_all("tr")
        or [d for d in corpo.find_all("div") if not d.find("div")]
        or [corpo]
    )
    textos = (e.get_text(" ", strip=True) for e in elementos)
    return tuple(t for t in textos if t)


def _linhas_proprias(tabela: Tag) -> list[Tag]:
    """<tr> que pertencem diretamente à tabela (ignora tabelas aninhadas)."""
    return [tr for tr in tabela.find_all("tr") if tr.find_parent("table") is tabela]


def _linhas_numericas(tabela: Tag, colunas: int) -> Iterator[list[str]]:
    """Linhas com `colunas` células, sendo todas numéricas exceto a primeira."""
    for linha in _linhas_proprias(tabela):
        celulas = [td.get_text(" ", strip=True) for td in linha.find_all("td", recursive=False)]
        if len(celulas) == colunas and all(c.isdigit() for c in celulas[1:]):
            yield celulas


def _textos_folha(soup: BeautifulSoup) -> list[str]:
    """Texto de todos os <div> que não contêm outros <div>."""
    return [d.get_text(" ", strip=True) for d in soup.find_all("div") if not d.find("div")]


def _valor_campo(textos: list[str], rotulo: str) -> str:
    padrao = re.compile(rf"^{re.escape(rotulo)}\s*(.*)$", re.IGNORECASE)
    for texto in textos:
        correspondencia = padrao.match(texto)
        if correspondencia:
            return correspondencia.group(1).strip()
    return ""


def _valor_ao_lado(escopo: Tag, rotulo: str) -> Tag | None:
    """Acha <b>rotulo</b> e devolve o <div> irmão que vem logo depois do pai."""
    negrito = escopo.find("b", string=re.compile(re.escape(rotulo)))
    if negrito is None or negrito.parent is None:
        return None
    return negrito.parent.find_next_sibling("div")


def _texto_ao_lado(escopo: Tag, rotulo: str) -> str:
    valor = _valor_ao_lado(escopo, rotulo)
    return valor.get_text(" ", strip=True) if valor else ""


def _buscar(padrao: re.Pattern, texto: str) -> str:
    correspondencia = padrao.search(texto)
    return correspondencia.group(1) if correspondencia else ""


def _para_int(texto: str) -> int:
    correspondencia = re.search(r"\d+", texto)
    return int(correspondencia.group()) if correspondencia else 0


def _para_bool(texto: str) -> bool:
    """'Sim'/'SIM' -> True; 'Não'/'NÃO'/vazio -> False."""
    return texto.strip().lower().startswith("s")