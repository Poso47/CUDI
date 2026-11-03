"""Konsolen-Chat mit CUDI (z. B. im Terminal von VS Code): python main.py --cli"""

from __future__ import annotations

from .core.application import get_app
from .core.results import CONFIRM


def run() -> None:
    app = get_app()
    name = app.settings.assistant_name
    print(f"{name} ist bereit. Beenden mit /ende. Befehle: /hilfe")
    print(app.orchestrator.models_text().splitlines()[0])
    for status_name, ok, info in app.models.status():
        print(f"  {'✅' if ok else '➖'} {status_name}: {info}")
    while True:
        try:
            text = input("\nDu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if text.lower() in ("/ende", "/exit", "/quit"):
            break
        if not text:
            continue
        result = app.handle(text)
        while True:
            label = f" [{result.model}]" if result.model else ""
            print(f"\n{name}{label}: {result.render()}")
            if result.details:
                print(f"  (Details: {result.details})")
            if result.kind != CONFIRM or not result.pending_id:
                break
            answer = input("Freigeben? (j/n): ").strip().lower()
            result = app.resolve(result.pending_id, answer in ("j", "ja", "y", "yes"))
    app.close()
    print("Bis bald!")
