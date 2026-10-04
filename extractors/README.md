# Aluno Online UERJ - Extrator de Disciplinas

Ferramenta de linha de comando em Python que faz login no [Aluno Online da UERJ](https://www.alunoonline.uerj.br/) e extrai as **disciplinas do currículo** do aluno, exibindo no terminal e, opcionalmente, salvando em JSON.

> **Aviso:** use apenas com a sua própria conta. O projeto não é oficial nem afiliado à UERJ. Como depende do HTML do site, uma mudança no portal pode quebrar a extração.

---

## Funcionalidades

- Login automático (obtém `PHPSESSID`, `_token` e `requisicao` dinamicamente).
- Descoberta automática da `requisicao` do link "Disciplinas do Currículo" no menu pós-login (nada fixo no código).
- Extração tipada das disciplinas: código, nome, período, tipo, créditos, carga horária etc.
- Consulta opcional das disciplinas cursadas e das disciplinas em curso, incluindo horários.
- Filtro de disciplinas **pendentes** (não atendidas).
- Exportação para **JSON**.
- Tratamento de erros separado por tipo (login, autenticação, parsing e rede).

---

## Estrutura do projeto

```
projeto/
└── extractors/
    ├── __init__.py
    ├── __main__.py
    ├── cli.py
    ├── core/
    │   ├── autenticacao.py
    │   ├── cliente_http.py
    │   ├── config.py
    │   ├── navegacao.py
    │   └── parsing.py
    ├── disciplinas/
    │   ├── curriculo.py
    │   ├── cursadas.py
    │   ├── em_curso.py
    │   └── detalhes.py
    └── requirements.txt
```

| Módulo | Responsabilidade |
|---|---|
| `core/config.py` | Único lugar com URLs e headers. Alterar o site ou o timeout exige mexer só aqui. |
| `core/cliente_http.py` | Único módulo que conhece `requests`. Cria a sessão, faz GET/POST, aplica timeout, `raise_for_status` e o encoding `iso-8859-1` do site. |
| `core/autenticacao.py` | Lê `_token` e `requisicao` do formulário, faz o POST de login e devolve a sessão autenticada. |
| `core/navegacao.py` | Descobre a `requisicao` de cada tela no menu e faz a navegação autenticada. |
| `core/parsing.py` | Reúne funções puras de parsing compartilhadas entre extratores. |
| `disciplinas/` | Contém os extratores de currículo, disciplinas cursadas, disciplinas em curso e detalhes. |
| `cli.py` | Lê credenciais, orquestra o fluxo, imprime e exporta. Não contém lógica de scraping. |
| `__main__.py` | Permite iniciar a CLI com `python -m extractors`. |

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

Execute os comandos a partir da raiz do repositório:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r extractors/requirements.txt
```

O ambiente virtual também evita o aviso `RequestsDependencyWarning` causado por conflito com pacotes do sistema.

---

## Uso

```bash
# Pergunta matrícula e senha no terminal
python -m extractors

# Apenas disciplinas ainda não atendidas
python -m extractors --pendentes

# Salva o resultado em JSON
python -m extractors --json disciplinas.json

# Combinando
python -m extractors --pendentes --json pendentes.json

# Também mostra o histórico de disciplinas cursadas
python -m extractors --cursadas

# Também mostra disciplinas em curso e seus horários
python -m extractors --em-curso

# Mostra as duas consultas adicionais
python -m extractors --cursadas --em-curso --sem-menu
```

| Opção | Descrição |
|---|---|
| `--pendentes` | Mostra só as disciplinas com "Atendida?" igual a "Não". |
| `--cursadas` | Também consulta e mostra disciplinas já cursadas, com período, frequência, nota e situação. |
| `--em-curso` | Também consulta e mostra disciplinas em curso, turma, locais e horários. |
| `--json ARQUIVO` | Salva a lista de disciplinas do currículo em um arquivo JSON (UTF-8). |
| `--sem-menu` | Omite o menu interativo de consulta de detalhes. |

As opções `--cursadas` e `--em-curso` podem ser combinadas. A listagem padrão e a exportação `--json` continuam referentes ao currículo.

### Credenciais com arquivo `.env`

Copie `extractors/.env.example` para `extractors/.env` e preencha os valores:

```bash
cp extractors/.env.example extractors/.env
```

No PowerShell, use:

```powershell
Copy-Item extractors/.env.example extractors/.env
```

Edite `extractors/.env`:

```dotenv
UERJ_MATRICULA=sua_matricula
UERJ_SENHA=sua_senha
```

O `.env` local é carregado automaticamente e está no `.gitignore`; nunca o envie ao repositório. O arquivo `.env.example` não contém credenciais e pode ser versionado. Variáveis já definidas no ambiente têm precedência sobre os valores do arquivo. Se uma ou ambas estiverem ausentes, a CLI solicita os dados no terminal, sem exibir a senha.

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
from extractors.core.autenticacao import fazer_login
from extractors.disciplinas.curriculo import buscar_disciplinas

autenticado = fazer_login("sua_matricula", "sua_senha")
for d in buscar_disciplinas(autenticado):
    print(d.codigo, d.nome, d.atendida)
```

Para testar o parsing sem acessar o site, use o HTML salvo de uma resposta:

```python
from extractors.disciplinas.curriculo import parse_disciplinas

with open("disciplinas.html", encoding="iso-8859-1") as f:
    print(len(parse_disciplinas(f.read())))
```

---

## Arquitetura e princípios (SOLID)

- **Responsabilidade única:** rede, autenticação, disciplinas e interface (CLI) ficam em módulos separados.
- **Aberto/fechado:** para extrair outra tela (histórico, notas), crie um novo módulo em `disciplinas/`, reaproveitando `SessaoAutenticada`, `buscar_tela` e as funções compartilhadas de `core/parsing.py`.
- **Inversão de dependência:** `fazer_login` aceita uma `sessao` opcional e `parse_disciplinas` recebe apenas texto HTML, o que facilita testes com dados falsos.
- **Dados tipados:** `Disciplina`, `DadosAutenticacao` e `SessaoAutenticada` são `dataclass(frozen=True)`.
- **Erros explícitos:** `AutenticacaoError`, `LoginError` e `DisciplinasError`.

---

## Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Página não encontrada!` no HTML | Requisição sem `User-Agent`/sessão inicializada | Use os headers de `config.py` e passe pela home antes (já implementado). |
| `Login falhou: a tela de login foi exibida novamente` | Matrícula/senha incorretos ou token inválido | Confira as credenciais. Evite tentar em loop: o sistema pode bloquear o acesso temporariamente. |
| `Link 'Disciplinas do Currículo' não encontrado` | O texto do link no menu é diferente | A mensagem lista os links encontrados; ajuste `TEXTO_LINK_CURRICULO` em `disciplinas/curriculo.py`. |
| `Tabela de disciplinas não encontrada` | Sessão expirada ou `requisicao` incorreta | Rode novamente; se persistir, o HTML do site pode ter mudado. |
| Acentos quebrados | Encoding incorreto | O site usa `iso-8859-1`, configurado em `config.py`. |
| Erro de rede / timeout | Instabilidade do portal ou da conexão | Tente novamente; ajuste `TIMEOUT_SEGUNDOS` se necessário. |

---

## Segurança

- **Nunca grave a senha no código** nem a envie em commits, prints ou conversas.
- Se uma senha for exposta, troque-a imediatamente no Aluno Online.
- O `.gitignore` na raiz do repositório exclui `.env`, ambientes virtuais, caches de Python e arquivos HTML/JSON gerados.

---

## Limitações conhecidas

- O parsing depende da estrutura atual do HTML (tabela `reportTable` com 9 colunas e o link "Disciplinas do Currículo" no menu pós-login).
- Apenas a tela de disciplinas do currículo está implementada.
- Não há renovação automática de sessão: se ela expirar, é preciso fazer login novamente.

## Próximos passos possíveis

- Novos extratores (histórico escolar, notas, horários) seguindo o padrão dos módulos em `disciplinas/`.
- Exportação para CSV/Excel.
- Testes automatizados com `pytest` usando HTML salvo.