#!/usr/bin/env python3
"""Atalho de execução: `python run.py [args]` equivale a `python -m salesops`."""
from salesops.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
