"""Camada de acesso HTTP: único lugar que conhece requests, timeout e encoding."""

import requests

from config import ENCODING_SITE, HEADERS, TIMEOUT_SEGUNDOS


def criar_sessao() -> requests.Session:
    sessao = requests.Session()
    sessao.headers.update(HEADERS)
    return sessao


def get_html(sessao: requests.Session, url: str) -> str:
    resposta = sessao.get(url, timeout=TIMEOUT_SEGUNDOS)
    return _decodificar(resposta)


def post_html(sessao: requests.Session, url: str, dados: dict) -> str:
    resposta = sessao.post(url, data=dados, timeout=TIMEOUT_SEGUNDOS)
    return _decodificar(resposta)


def _decodificar(resposta: requests.Response) -> str:
    resposta.raise_for_status()
    resposta.encoding = ENCODING_SITE
    return resposta.text