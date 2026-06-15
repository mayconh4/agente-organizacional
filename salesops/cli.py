"""Interface de linha de comando do SalesOps AI.

Comandos:
  run                Gera o relatório executivo do dia (padrão).
  log-action TEXTO   Registra uma ação tomada (alimenta a memória do agente).
  history            Lista os dias com snapshot salvo.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

from .config import get_settings
from .engine.memory import Memory
from .models import Channel


def _cmd_run(args: argparse.Namespace) -> int:
    from .brain import run_daily

    settings = get_settings()
    if args.client:
        settings.client_name = args.client
    if args.channels:
        settings.channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    print(f"▶ SalesOps AI — analisando '{settings.client_name}' "
          f"({', '.join(Channel.label(c) for c in settings.channels)})…\n",
          file=sys.stderr)

    result = run_daily(settings, day=args.date)

    print(result.report_markdown)
    print()

    # Rodapé operacional (stderr para não poluir o markdown se for redirecionado).
    motor = "Claude" if result.engine == "claude" else "regras (offline)"
    print(f"\n— Motor de diagnóstico: {motor} | Saúde: {result.health}% | "
          f"Relatório salvo em: {result.report_path}", file=sys.stderr)
    if result.failed_channels:
        labels = ", ".join(Channel.label(c) for c in result.failed_channels)
        print(f"— ⚠️ Falha na API real (usando exemplo): {labels}", file=sys.stderr)
    if result.sample_channels:
        labels = ", ".join(Channel.label(c) for c in result.sample_channels)
        print(f"— ℹ️ Canais com dados de exemplo (sem credenciais): {labels}",
              file=sys.stderr)
    return 0


def _cmd_log_action(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.client:
        settings.client_name = args.client
    memory = Memory(settings.data_dir, settings.client_name)
    memory.log_action(args.description, channel=args.channel, day=args.date)
    print(f"✔ Ação registrada para '{settings.client_name}'.", file=sys.stderr)
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.client:
        settings.client_name = args.client
    memory = Memory(settings.data_dir, settings.client_name)
    dates = memory.stored_dates()
    if not dates:
        print("Nenhum snapshot salvo ainda.", file=sys.stderr)
        return 0
    print(f"Snapshots de '{settings.client_name}':")
    for d in dates:
        print(f"  {d}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="salesops",
        description="Agente executivo de operações comerciais multicanal.",
    )
    parser.add_argument("--client", help="Sobrescreve o nome do cliente.")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Gera o relatório executivo do dia.")
    run.add_argument("--date", default=date.today().isoformat(),
                     help="Data a analisar (YYYY-MM-DD). Padrão: hoje.")
    run.add_argument("--channels", help="Canais (csv). Padrão: do .env.")
    run.set_defaults(func=_cmd_run)

    log = sub.add_parser("log-action", help="Registra uma ação tomada.")
    log.add_argument("description", help="Descrição da ação.")
    log.add_argument("--channel", default="geral",
                     help="Canal relacionado (shopee/mercado_livre/amazon/geral).")
    log.add_argument("--date", default=date.today().isoformat(), help="Data da ação.")
    log.set_defaults(func=_cmd_log_action)

    hist = sub.add_parser("history", help="Lista os dias com snapshot salvo.")
    hist.set_defaults(func=_cmd_history)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # Sem subcomando → roda o relatório do dia.
        args.command = "run"
        args.date = date.today().isoformat()
        args.channels = None
        return _cmd_run(args)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
