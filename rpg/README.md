# Niemandsland – Mittelalter-Fantasy-RPG (Arbeitstitel)

Klassenloses Open-World-RPG: Du startest als Niemand und verdienst dir Ruhm –
oder Furcht. Die komplette Vision steht im [Game Design Document](docs/GDD.md).

## Was es schon gibt

| System | Datei | Inhalt |
|--------|-------|--------|
| Skill-Fusion | `core/skills.py` | 14 Grund-Skills, Elementreaktionen, verschmelzende Formen, Rezepte, **emergente neue Skills** und seltene **Mutationen** mit Bausteinen, die es sonst nirgends gibt. Weltweite Entdecker-Registry. |
| Wirtschaft | `core/economy.py` | 4 Städte, echte Geldmenge (Prägen/Verschleiß), Steuern, Löhne, Angebot & Nachfrage, Wohlstand, NPC-Karawanen, Überfälle, Spielerhandel. |

## Ausprobieren

Aus dem Repo-Hauptordner (nur Python 3.10+, keine Abhängigkeiten):

```bash
python -m rpg.demo                                   # Demo beider Systeme
python -m unittest discover -s rpg/tests -t .        # Tests
```
