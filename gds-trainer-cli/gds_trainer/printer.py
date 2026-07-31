"""Terminal output, replacing script.js's DOM-based print()/printErr()/printBlank().

Approximates the green-phosphor CRT theme from style.css by mapping its
'hd'/'dim'/'err'/'echo' line classes to rich styles instead of CSS classes.
"""

from __future__ import annotations

from rich.console import Console

console = Console(markup=False, highlight=False)

_STYLES = {
    None: "green",
    "hd": "bold green",
    "dim": "grey62",
    "err": "bold red",
    "echo": "bold cyan",
}


def print_line(text: object = "", cls: str | None = None) -> None:
    style = _STYLES.get(cls, "green")
    for line in str(text).split("\n"):
        console.print(line if line else " ", style=style)


def print_err(text: object) -> None:
    print_line(text, "err")


def print_blank() -> None:
    print_line("")
