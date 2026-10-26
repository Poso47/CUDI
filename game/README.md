# Niemandsland – spielbare Testwelt (Godot 4)

Low-Poly-Formen wie in RuneScape, Toon-Licht wie in Zelda, direkte Steuerung
mit Verfolgerkamera. Alle Modelle werden per Code erzeugt – keine externen
Assets nötig.

## Starten

1. Godot **4.4** (oder neuer, Standard-Version, nicht .NET) öffnen
2. **Importieren** → den Ordner `game/` wählen → `project.godot` → *Importieren & Bearbeiten*
3. **F5** drücken (oder ▶ oben rechts)

Beim ersten Öffnen scannt Godot die Skripte einmal – das dauert ein paar Sekunden.

## Steuerung

| Aktion | Tastatur/Maus | Controller |
|--------|---------------|------------|
| Laufen | WASD | linker Stick |
| Kamera | Maus | rechter Stick |
| Sprinten | Shift | Stick drücken |
| Springen | Leertaste | A |
| Angreifen | Linksklick | X |
| Blocken | Rechtsklick (halten) | LB |
| Ausweichrolle | C | B |
| Interagieren / Handeln | E | Y |
| Heiltrank | R | RB |
| Zoom | Mausrad | – |
| Maus freigeben | Esc | Start |

## Was du ausprobieren kannst

- **Insel** mit Bergen, Strand, Wald, Wasser (man kann schwimmen) und Tag/Nacht-Wechsel
- **Dorf Grünau** mit Händlerin Berta: Preise kommen aus dem Wirtschaftssystem –
  verkaufst du viel von einer Ware, sinkt ihr Preis; die Bürger zahlen aus ihrem
  echten Geldvorrat
- **Goblin-Lager** im Nordwesten (vom Dorf aus Richtung Lagerfeuer-Schein):
  Goblins lassen Zähne und Felle fallen, die du verkaufen kannst
- **Sichtbare Ausrüstung**: Eisenhelm, Lederrüstung, Streitaxt und Eisenschild
  kaufen – sie erscheinen sofort an deiner Figur und verbessern Schaden/Rüstung

## Aufbau

| Datei | Inhalt |
|-------|--------|
| `scripts/main.gd` | baut die Welt zusammen |
| `scripts/core/low_poly.gd` | Low-Poly-Mesh-Baukasten + Toon-Material |
| `scripts/core/market.gd` | Markt (Übertragung von `rpg/core/economy.py`) |
| `scripts/core/controls.gd` | Tastenbelegung |
| `scripts/world/terrain.gd` | prozedurale Insel |
| `scripts/world/props.gd` | Bäume, Felsen, Häuser, Lager |
| `scripts/world/day_night.gd` | Tag/Nacht, Himmel, Licht |
| `scripts/actors/character_model.gd` | Figur mit Ausrüstungsplätzen und Animationen |
| `scripts/actors/player.gd` | Spielersteuerung, Kampf, Inventar |
| `scripts/actors/goblin.gd` | Gegner-KI |
| `scripts/actors/merchant.gd` | Händlerin |
| `scripts/ui/hud.gd` | Anzeige und Handelsfenster |
