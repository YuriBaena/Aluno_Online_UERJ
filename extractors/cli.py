"""Ponto de entrada: login no Aluno Online, listagem do currículo e consulta de detalhes."""

import argparse
import getpass
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import requests
from dotenv import load_dotenv

from .core.autenticacao import AutenticacaoError, LoginError, SessaoAutenticada, fazer_login
from .core.navegacao import NavegacaoError
from .disciplinas.curriculo import (
    Disciplina,
    DisciplinasError,
    buscar_html_disciplinas,
    parse_disciplinas,
)
from .disciplinas.cursadas import (
    DisciplinaCursada,
    DisciplinasCursadasError,
    buscar_disciplinas_cursadas,
)
from .disciplinas.detalhes import DetalheDisciplina, DetalheDisciplinaError, buscar_detalhe
from .disciplinas.em_curso import (
    DisciplinaEmCurso,
    DisciplinasEmCursoError,
    buscar_disciplinas_em_curso,
)


# --------------------------------------------------------------------------- #
# Entrada
# --------------------------------------------------------------------------- #

def ler_credenciais() -> tuple[str, str]:
    """Carrega credenciais locais; usa o ambiente ou pergunta se estiverem ausentes."""
    load_dotenv(Path(__file__).resolve().parent / ".env")
    matricula = os.getenv("UERJ_MATRICULA") or input("Matrícula: ").strip()
    senha = os.getenv("UERJ_SENHA") or getpass.getpass("Senha: ")
    return matricula, senha


def escolher_disciplina(entrada: str, disciplinas: list[Disciplina]) -> Disciplina | None:
    """Aceita o número da lista (ex.: '3') ou o código (ex.: 'IME01-04827')."""
    if entrada.isdigit():
        posicao = int(entrada)
        return disciplinas[posicao - 1] if 1 <= posicao <= len(disciplinas) else None

    codigo = entrada.upper()
    return next((d for d in disciplinas if d.codigo.upper() == codigo), None)


# --------------------------------------------------------------------------- #
# Saída
# --------------------------------------------------------------------------- #

def imprimir_disciplinas(disciplinas: list[Disciplina]) -> None:
    cabecalho = (
        f"{'Nº':<4}{'Per.':<5}{'Código':<13}{'Disciplina':<55}"
        f"{'Atend.':<7}{'Tipo':<12}{'Cred.':<6}{'Turma?'}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for numero, d in enumerate(disciplinas, start=1):
        print(
            f"{numero:<4}{d.periodo:<5}{d.codigo:<13}{d.nome[:53]:<55}"
            f"{d.atendida:<7}{d.tipo:<12}{d.creditos:<6}{d.turma_no_periodo}"
        )
    print(f"\nTotal: {len(disciplinas)} disciplinas")


def imprimir_disciplinas_cursadas(disciplinas: list[DisciplinaCursada]) -> None:
    print("\nDisciplinas cursadas:")
    if not disciplinas:
        print("Nenhuma disciplina cursada encontrada.")
        return

    cabecalho = (
        f"{'Período':<9}{'Código':<14}{'Disciplina':<45}{'Cred.':<7}"
        f"{'CH':<6}{'Freq.':<9}{'Nota':<8}{'Situação'}"
    )
    print(cabecalho)
    print("-" * len(cabecalho))
    for d in disciplinas:
        frequencia = f"{d.frequencia:.2f}%".replace(".", ",") if d.frequencia is not None else "-"
        nota = f"{d.nota:.2f}".replace(".", ",") if d.nota is not None else "-"
        print(
            f"{d.periodo:<9}{d.codigo:<14}{d.nome[:43]:<45}{d.creditos:<7}"
            f"{d.carga_horaria:<6}{frequencia:<9}{nota:<8}{d.situacao}"
        )
    print(f"\nTotal: {len(disciplinas)} disciplinas cursadas")


def imprimir_disciplinas_em_curso(disciplinas: list[DisciplinaEmCurso]) -> None:
    print("\nDisciplinas em curso:")
    if not disciplinas:
        print("Nenhuma disciplina em curso encontrada.")
        return

    for d in disciplinas:
        horarios = "; ".join(
            f"{h.dia}: {h.tempo} ({h.inicio}-{h.fim})" for h in d.horarios
        ) or "-"
        print(f"\n{d.codigo} - {d.nome}")
        print(f"  Turma: {d.turma or '-'}")
        print(f"  Local AVA: {d.local_ava or '-'}")
        print(f"  Local de aula: {d.local_aula or '-'}")
        print(f"  Horários: {horarios}")
    print(f"\nTotal: {len(disciplinas)} disciplinas em curso")


def imprimir_detalhe(d: DetalheDisciplina) -> None:
    print("\n" + "=" * 72)
    print(f"{d.codigo} - {d.nome}")
    print("=" * 72)
    print(
        f"Créditos: {d.creditos} | CH total: {d.carga_horaria_total} "
        f"| CH semanal: {d.carga_horaria_semanal}"
    )
    print(
        f"Universal: {_sim_nao(d.universal)} "
        f"| Conflito de horário: {_sim_nao(d.permite_conflito_horario)} "
        f"| Situação em preparo: {_sim_nao(d.permite_situacao_em_preparo)}"
    )
    print(f"Aprovação: {d.tipo_aprovacao or '-'} | Duração: {d.duracao or '-'}")

    print("\nRequisitos:")
    if d.requisitos:
        for requisito in d.requisitos:
            rotulo = f"{requisito.tipo}: " if requisito.tipo else ""
            print(f"  - {rotulo}{requisito.descricao}")
    else:
        print("  Nenhum requisito para inscrição.")

    print(f"\nTurmas ({len(d.turmas)}):")
    if not d.turmas:
        print("  Nenhuma turma encontrada.")
    for turma in d.turmas:
        _imprimir_turma(turma)


def _imprimir_turma(turma) -> None:
    horarios = "; ".join(f"{h.dia} {' '.join(h.tempos)}" for h in turma.horarios) or "-"

    print(f"\n  Turma {turma.numero} (preferencial: {_sim_nao(turma.preferencial)})")
    print(f"    Docente:  {turma.docente or '-'}")
    print(f"    Local:    {turma.local or '-'}")
    print(f"    Horários: {horarios}")
    for vaga in turma.vagas:
        print(f"    Vagas {vaga.tipo}: {vaga.ocupadas}/{vaga.oferecidas} ocupadas")
    for sol in turma.solicitacoes:
        print(
            f"    Solicitações {sol.tipo}: {sol.solicitadas} solicitadas "
            f"({sol.solicitadas_preferenciais} preferenciais) para {sol.oferecidas} vagas"
        )


def _sim_nao(valor: bool) -> str:
    return "Sim" if valor else "Não"


def salvar_json(disciplinas: list[Disciplina], caminho: str) -> None:
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump([asdict(d) for d in disciplinas], arquivo, ensure_ascii=False, indent=2)
    print(f"Arquivo salvo em: {caminho}")


# --------------------------------------------------------------------------- #
# Menu interativo
# --------------------------------------------------------------------------- #

def menu_detalhes(
    autenticado: SessaoAutenticada,
    html_curriculo: str,
    disciplinas: list[Disciplina],
) -> None:
    """Loop: o usuário escolhe uma disciplina da lista e vê os detalhes."""
    print("\nDigite o número (ou o código) da disciplina para ver os detalhes.")
    print("Comandos: 'l' lista novamente | 'q' sai")

    while True:
        try:
            entrada = input("\nDisciplina> ").strip()
        except EOFError:
            return

        comando = entrada.lower()
        if not entrada:
            continue
        if comando in {"q", "sair"}:
            return
        if comando == "l":
            imprimir_disciplinas(disciplinas)
            continue

        disciplina = escolher_disciplina(entrada, disciplinas)
        if disciplina is None or not disciplina.id:
            print("Disciplina inválida. Use o número da lista ou o código (ex.: IME01-04827).")
            continue

        _consultar_e_imprimir(autenticado, html_curriculo, disciplina)


def _consultar_e_imprimir(
    autenticado: SessaoAutenticada,
    html_curriculo: str,
    disciplina: Disciplina,
) -> None:
    print(f"Buscando detalhes de {disciplina.codigo}...")
    try:
        detalhe = buscar_detalhe(autenticado, html_curriculo, disciplina.id)
    except (DetalheDisciplinaError, requests.RequestException) as erro:
        # um erro numa consulta não derruba o menu
        print(f"Não foi possível obter os detalhes: {erro}", file=sys.stderr)
        return
    imprimir_detalhe(detalhe)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Consultas de disciplinas - Aluno Online UERJ")
    parser.add_argument(
        "--json",
        metavar="ARQUIVO",
        help="salva a lista de disciplinas do currículo em JSON",
    )
    parser.add_argument(
        "--pendentes",
        action="store_true",
        help="mostra apenas as disciplinas ainda não atendidas",
    )
    parser.add_argument(
        "--cursadas",
        action="store_true",
        help="também mostra as disciplinas já cursadas",
    )
    parser.add_argument(
        "--em-curso",
        action="store_true",
        help="também mostra as disciplinas em curso e seus horários",
    )
    parser.add_argument(
        "--sem-menu",
        action="store_true",
        help="apenas lista as disciplinas, sem o menu de detalhes",
    )
    return parser


def main() -> int:
    args = criar_parser().parse_args()

    try:
        matricula, senha = ler_credenciais()

        print("Autenticando...")
        autenticado = fazer_login(matricula, senha)

        print("Buscando disciplinas...\n")
        html_curriculo = buscar_html_disciplinas(autenticado)
        disciplinas = parse_disciplinas(html_curriculo)

        if args.pendentes:
            disciplinas = [d for d in disciplinas if d.atendida.lower().startswith("n")]

        imprimir_disciplinas(disciplinas)

        if args.json:
            salvar_json(disciplinas, args.json)

        if args.cursadas:
            print("\nBuscando disciplinas cursadas...")
            imprimir_disciplinas_cursadas(buscar_disciplinas_cursadas(autenticado))

        if args.em_curso:
            print("\nBuscando disciplinas em curso...")
            imprimir_disciplinas_em_curso(buscar_disciplinas_em_curso(autenticado))

        if not args.sem_menu:
            menu_detalhes(autenticado, html_curriculo, disciplinas)

    except LoginError as erro:
        print(f"Erro de login: {erro}", file=sys.stderr)
        return 1
    except (
        AutenticacaoError,
        NavegacaoError,
        DisciplinasError,
        DisciplinasCursadasError,
        DisciplinasEmCursoError,
        DetalheDisciplinaError,
    ) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    except requests.RequestException as erro:
        print(f"Erro de rede: {erro}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nOperação cancelada.", file=sys.stderr)
        return 130

    return 0


if __name__ == "__main__":
    sys.exit(main())