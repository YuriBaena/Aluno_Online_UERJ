# Aluno Online UERJ - Extrator de Disciplinas

Ferramenta de linha de comando em Python que faz login no [Aluno Online da UERJ](https://www.alunoonline.uerj.br/) e extrai as **disciplinas do currículo** do aluno, exibindo no terminal e, opcionalmente, salvando em JSON.

> **Aviso:** use apenas com a sua própria conta. O projeto não é oficial nem afiliado à UERJ. Como depende do HTML do site, uma mudança no portal pode quebrar a extração.

---

## Funcionalidades

- Login automático (obtém `PHPSESSID`, `_token` e `requisicao` dinamicamente).
- Descoberta automática da `requisicao` do link "Disciplinas do Currículo" no menu pós-login (nada fixo no código).
- Extração tipada das disciplinas: código, nome, período, tipo, créditos, carga horária etc.
- Filtro de disciplinas **pendentes** (não atendidas).
- Exportação para **JSON**.
- Tratamento de erros separado por tipo (login, autenticação, parsing e rede).

---

## Estrutura do projeto

```
projeto/
├── config.py          # constantes: URLs, headers, timeout, encoding
├── cliente_http.py    # camada HTTP (sessão, GET/POST, decodificação)
├── autenticacao.py    # dados de autenticação e login
├── disciplinas.py     # busca e parsing das disciplinas do currículo
├── main.py            # ponto de entrada (CLI)
└── requirements.txt
```

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Único lugar com URLs e headers. Alterar o site ou o timeout exige mexer só aqui. |
| `cliente_http.py` | Único módulo que conhece `requests`. Cria a sessão, faz GET/POST, aplica timeout, `raise_for_status` e o encoding `iso-8859-1` do site. |
| `autenticacao.py` | Lê `_token` e `requisicao` do formulário, faz o POST de login e devolve a sessão autenticada. |
| `disciplinas.py` | Monta o POST das disciplinas, localiza a `requisicao` no menu e converte a tabela HTML em objetos `Disciplina`. |
| `main.py` | Lê credenciais, orquestra o fluxo, imprime e exporta. Não contém lógica de scraping. |

---

## Como funciona

O Aluno Online é uma aplicação PHP que usa **um único endpoint** (`/requisicaoaluno/`) para todas as telas. O que muda entre uma tela e outra é o campo `requisicao`, um hash que identifica a ação.

```
1. GET  /                      -> inicializa a sessão (PHPSESSID)
2. GET  /requisicaoaluno/      -> página de login; lê _token e requisicao do <form>
3. POST /requisicaoaluno/      -> login (requisicao, _token, matricula, senha)
                                  resposta = página pós-login (menu)
4. Extrai do menu o hash da requisicao do link "Disciplinas do Currículo"
5. POST /requisicaoaluno/      -> flg_logado, _token, target, hRef, requisicao
                                  resposta = tabela de disciplinas
6. Parsing da tabela (class "reportTable") -> lista de Disciplina
```

Pontos importantes:

- **Mesma sessão do início ao fim.** O `_token` e a `requisicao` são amarrados ao `PHPSESSID`; por isso a `requests.Session` é reaproveitada em todas as etapas.
- **Detecção de falha no login:** se o elemento `#caixa_bloco_login` aparece de novo na resposta, o login é considerado recusado.
- **Campo `flg_logado`:** é enviado com o valor literal `@FLG_LOGADO@`, exatamente como o navegador faz.

---

## Requisitos

- Python **3.10 ou superior** (usa a sintaxe `str | None`).
- Dependências em `requirements.txt`:

```
requests>=2.31,<3
beautifulsoup4>=4.12,<5
```

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

O ambiente virtual também evita o aviso `RequestsDependencyWarning` causado por conflito com pacotes do sistema.

---

## Uso

```bash
# Pergunta matrícula e senha no terminal
python3 main.py

# Apenas disciplinas ainda não atendidas
python3 main.py --pendentes

# Salva o resultado em JSON
python3 main.py --json disciplinas.json

# Combinando
python3 main.py --pendentes --json pendentes.json
```

| Opção | Descrição |
|---|---|
| `--pendentes` | Mostra só as disciplinas com "Atendida?" igual a "Não". |
| `--json ARQUIVO` | Salva a lista exibida em um arquivo JSON (UTF-8). |

### Credenciais por variável de ambiente

Para não digitar toda vez (o `read -s` evita que a senha apareça na tela e no histórico):

```bash
export UERJ_MATRICULA="sua_matricula"
read -s UERJ_SENHA && export UERJ_SENHA
python3 main.py
```

Se as variáveis não existirem, o programa pergunta no terminal (a senha é lida com `getpass`, sem eco).

### Códigos de saída

| Código | Significado |
|---|---|
| `0` | Sucesso |
| `1` | Erro de login, autenticação, parsing ou rede |
| `130` | Cancelado pelo usuário (Ctrl+C) |

---

## Exemplo de saída

```
Per. Código       Disciplina                                             Atend. Tipo        Cred. Turma?
------------------------------------------------------------------------------------------------------
1    IME01-04827  Cálculo I                                              Sim    Obrigatória 6     Sim
1    IME03-10814  Geometria Analítica                                    Sim    Obrigatória 4     Sim
...

Total: 62 disciplinas
```

Formato de cada item no JSON:

```json
{
  "id": "4827",
  "codigo": "IME01-04827",
  "nome": "Cálculo I",
  "periodo": "1",
  "atendida": "Sim",
  "tipo": "Obrigatória",
  "ramificacao": "626",
  "creditos": "6",
  "carga_horaria": "90",
  "trava_credito": "0",
  "turma_no_periodo": "Sim"
}
```

Eletivas restritas aparecem com período `-`, pois não têm período fixo.

---

## Uso como biblioteca

Os módulos podem ser importados em outros scripts:

```python
from autenticacao import fazer_login
from disciplinas import buscar_disciplinas

autenticado = fazer_login("sua_matricula", "sua_senha")
for d in buscar_disciplinas(autenticado):
    print(d.codigo, d.nome, d.atendida)
```

Para testar o parsing sem acessar o site, use o HTML salvo de uma resposta:

```python
from disciplinas import parse_disciplinas

with open("disciplinas.html", encoding="iso-8859-1") as f:
    print(len(parse_disciplinas(f.read())))
```

---

## Arquitetura e princípios (SOLID)

- **Responsabilidade única:** rede, autenticação, disciplinas e interface (CLI) ficam em módulos separados.
- **Aberto/fechado:** para extrair outra tela (histórico, notas), crie um novo módulo no mesmo molde de `disciplinas.py`, reaproveitando `SessaoAutenticada`, `post_html` e `extrair_token`, sem alterar o código existente.
- **Inversão de dependência:** `fazer_login` aceita uma `sessao` opcional e `parse_disciplinas` recebe apenas texto HTML, o que facilita testes com dados falsos.
- **Dados tipados:** `Disciplina`, `DadosAutenticacao` e `SessaoAutenticada` são `dataclass(frozen=True)`.
- **Erros explícitos:** `AutenticacaoError`, `LoginError` e `DisciplinasError`.

---

## Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Página não encontrada!` no HTML | Requisição sem `User-Agent`/sessão inicializada | Use os headers de `config.py` e passe pela home antes (já implementado). |
| `Login falhou: a tela de login foi exibida novamente` | Matrícula/senha incorretos ou token inválido | Confira as credenciais. Evite tentar em loop: o sistema pode bloquear o acesso temporariamente. |
| `Link 'Disciplinas do Currículo' não encontrado` | O texto do link no menu é diferente | A mensagem lista os links encontrados; ajuste `TEXTO_LINK_CURRICULO` em `disciplinas.py`. |
| `Tabela de disciplinas não encontrada` | Sessão expirada ou `requisicao` incorreta | Rode novamente; se persistir, o HTML do site pode ter mudado. |
| Acentos quebrados | Encoding incorreto | O site usa `iso-8859-1`, configurado em `config.py`. |
| Erro de rede / timeout | Instabilidade do portal ou da conexão | Tente novamente; ajuste `TIMEOUT_SEGUNDOS` se necessário. |

---

## Segurança

- **Nunca grave a senha no código** nem a envie em commits, prints ou conversas.
- Se uma senha for exposta, troque-a imediatamente no Aluno Online.
- Ao versionar com git, crie um `.gitignore`:

```
.venv/
__pycache__/
*.json
*.html
```

---

## Limitações conhecidas

- O parsing depende da estrutura atual do HTML (tabela `reportTable` com 9 colunas e o link "Disciplinas do Currículo" no menu pós-login).
- Apenas a tela de disciplinas do currículo está implementada.
- Não há renovação automática de sessão: se ela expirar, é preciso fazer login novamente.

## Próximos passos possíveis

- Novos extratores (histórico escolar, notas, horários) seguindo o padrão de `disciplinas.py`.
- Exportação para CSV/Excel.
- Testes automatizados com `pytest` usando HTML salvo.