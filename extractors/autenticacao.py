"""Obtenção dos dados de autenticação e login no Aluno Online."""

from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from cliente_http import criar_sessao, get_html, post_html
from config import BASE_URL, REQUISICAO_URL

ID_BLOCO_LOGIN = "caixa_bloco_login"


class AutenticacaoError(Exception):
    """Falha ao obter os dados necessários para autenticar."""


class LoginError(AutenticacaoError):
    """Credenciais recusadas ou resposta inesperada no login."""


@dataclass(frozen=True)
class DadosAutenticacao:
    sessao: requests.Session
    phpsessid: str | None
    token: str
    requisicao: str


@dataclass(frozen=True)
class SessaoAutenticada:
    sessao: requests.Session
    html_pos_login: str


def extrair_token(html: str) -> str:
    """Lê o valor do input hidden `_token` de qualquer página."""
    return _extrair_input(BeautifulSoup(html, "html.parser"), "_token")


def obter_dados_autenticacao(sessao: requests.Session | None = None) -> DadosAutenticacao:
    """Abre a página de login e coleta PHPSESSID, _token e requisicao."""
    sessao = sessao or criar_sessao()

    get_html(sessao, BASE_URL)  # inicializa a sessão
    html = get_html(sessao, REQUISICAO_URL)

    soup = BeautifulSoup(html, "html.parser")
    formulario = soup.find("form", attrs={"name": "form"})
    if formulario is None:
        raise AutenticacaoError("Formulário de login não encontrado.")

    return DadosAutenticacao(
        sessao=sessao,
        phpsessid=sessao.cookies.get("PHPSESSID"),
        token=_extrair_input(formulario, "_token"),
        requisicao=_extrair_input(formulario, "requisicao"),
    )


def fazer_login(
    matricula: str,
    senha: str,
    sessao: requests.Session | None = None,
) -> SessaoAutenticada:
    """Realiza o login e devolve a sessão autenticada com o HTML pós-login."""
    dados = obter_dados_autenticacao(sessao)

    html = post_html(
        dados.sessao,
        REQUISICAO_URL,
        {
            "requisicao": dados.requisicao,
            "_token": dados.token,
            "matricula": matricula,
            "senha": senha,
        },
    )

    if BeautifulSoup(html, "html.parser").find(id=ID_BLOCO_LOGIN):
        raise LoginError("Login falhou: a tela de login foi exibida novamente.")

    return SessaoAutenticada(sessao=dados.sessao, html_pos_login=html)


def _extrair_input(escopo, nome: str) -> str:
    tag = escopo.find("input", attrs={"name": nome})
    if tag is None or not tag.get("value"):
        raise AutenticacaoError(f"Campo '{nome}' não encontrado na página.")
    return tag["value"]