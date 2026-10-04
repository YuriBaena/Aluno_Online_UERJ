"""Constantes de configuração do Aluno Online."""

BASE_URL = "https://www.alunoonline.uerj.br/"
REQUISICAO_URL = BASE_URL + "requisicaoaluno/"

TIMEOUT_SEGUNDOS = 15
ENCODING_SITE = "iso-8859-1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Referer": BASE_URL,
}