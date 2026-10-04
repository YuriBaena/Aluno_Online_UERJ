"""Funções puras de interpretação de texto/HTML compartilhadas entre os módulos."""

import re

from bs4 import Tag

_RE_CODIGO_NOME = re.compile(r"^([A-Z]+\d+-\d+)\s+(.+)$")
_RE_ID_CONSULTA = re.compile(r"consultarDisciplina\(\w+,\s*(\d+)\)")


def limpar_texto(texto: str) -> str:
    """Colapsa espaços (inclusive &nbsp;) e remove as pontas."""
    return " ".join(texto.split())


def separar_codigo_nome(texto: str) -> tuple[str, str]:
    """'IME01-04827  Cálculo I' -> ('IME01-04827', 'Cálculo I')."""
    texto = limpar_texto(texto)
    correspondencia = _RE_CODIGO_NOME.match(texto)
    return (correspondencia.group(1), correspondencia.group(2)) if correspondencia else ("", texto)


def extrair_id_consulta(celula: Tag) -> str | None:
    """Lê o id interno em onclick='consultarDisciplina(output, 4827)'."""
    link = celula.find("a", onclick=True)
    if link is None:
        return None
    correspondencia = _RE_ID_CONSULTA.search(link["onclick"])
    return correspondencia.group(1) if correspondencia else None


def para_int(texto: str, padrao: int = 0) -> int:
    correspondencia = re.search(r"\d+", texto)
    return int(correspondencia.group()) if correspondencia else padrao


def para_decimal(texto: str) -> float | None:
    """'10,00' -> 10.0 | '100%' -> 100.0 | '' -> None."""
    limpo = limpar_texto(texto).replace("%", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return None