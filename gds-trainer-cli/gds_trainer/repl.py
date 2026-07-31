"""REPL entry point, replacing script.js's inputEl keydown handler.

prompt_toolkit's PromptSession gives arrow-key history recall natively, so
unlike script.js there's no hand-rolled cmdHistory/cmdHistoryIdx.
"""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory

from . import commands as c
from .dispatcher import process_command
from .printer import print_err, print_line


def main() -> None:
    c.boot()
    session: PromptSession[str] = PromptSession(history=InMemoryHistory())
    while True:
        try:
            raw = session.prompt("GDS> ")
        except KeyboardInterrupt:
            continue
        except EOFError:
            break

        print_line("> " + raw.upper(), "echo")
        try:
            process_command(raw)
        except Exception as err:  # mirrors script.js's try/catch around processCommand()
            print_err(f"SYSTEM ERROR - {err}")


if __name__ == "__main__":
    main()
