"""Navegação pelo menu pós-login: descobre a `requisicao` de cada tela e a consulta."""

import re
import unicodedata

from bs4 import BeautifulSoup

from .autenticacao import SessaoAutenticada, extrair_token
from .cliente_http import post_html
from .config import REQUISICAO_URL

_RE_HASH = re.compile(r"""['"]([0-9a-f]{32})['"]""")


class NavegacaoError(Exception):
    """Falha ao localizar ou abrir uma tela do menu."""


def buscar_tela(autenticado: SessaoAutenticada, texto_link: str) -> str:
    """Abre a tela cujo link do menu contém `texto_link` e devolve o HTML dela."""
    html_menu = autenticado.html_pos_login
    payload = {
        "flg_logado": "@FLG_LOGADO@",  # literal, igual ao navegador
        "_token": extrair_token(html_menu),
        "target": "0",
        "hRef": "",
        "requisicao": extrair_requisicao(html_menu, texto_link),
    }
    return post_html(autenticado.sessao, REQUISICAO_URL, payload)


def extrair_requisicao(html: str, texto_link: str) -> str:
    """Acha o hash de `requisicao` do link cujo texto contém `texto_link`."""
    alvo = _normalizar(texto_link)
    opcoes = listar_requisicoes(html)

    for texto, hash_requisicao in opcoes:
        if alvo in _normalizar(texto):
            return hash_requisicao

    detalhe = "\n".join(f"  {h} -> {t[:60]!r}" for t, h in opcoes) or "  (nenhuma)"
    raise NavegacaoError(
        f"Link '{texto_link}' não encontrado no menu. Opções disponíveis:\n{detalhe}"
    )


def listar_requisicoes(html: str) -> list[tuple[str, str]]:
    """Retorna [(texto, hash)] de todo elemento clicável com hash de 32 hex."""
    soup = BeautifulSoup(html, "html.parser")
    achados = []

    for elemento in soup.find_all(True):
        codigo_js = elemento.get("onclick") or elemento.get("href") or ""
        correspondencia = _RE_HASH.search(codigo_js)
        if not correspondencia:
            continue

        texto = elemento.get_text(" ", strip=True)
        if not texto and elemento.parent:  # link só com imagem
            texto = elemento.parent.get_text(" ", strip=True)

        achados.append((texto, correspondencia.group(1)))
    return achados


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acento e sem espaços repetidos."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip().lower()