# Game Design Document – Arbeitstitel „Niemandsland“

> Mittelalter-Fantasy-Open-World-RPG ohne Klassen. Du startest als Niemand –
> nicht als Auserwählter. Ruhm, Furcht und Macht musst du dir selbst verdienen.

Status: **Grundvision v0.1** – wird Schritt für Schritt erweitert.

---

## 1. Design-Säulen (an diesen Regeln wird jede Entscheidung gemessen)

| # | Säule | Bedeutung |
|---|-------|-----------|
| 1 | **Totale Freiheit** | Keine festen Klassen. Dieb, Magier, Krieger – oder alles zugleich. Was du *tust*, macht dich zu dem, was du *bist*. |
| 2 | **Emergenz** | Systeme greifen ineinander und erzeugen Dinge, die niemand vorgeschrieben hat – vor allem neue Skills durch Fusion. |
| 3 | **Lebendige Welt** | Städte, Wirtschaft, NPCs und Drachen existieren auch ohne den Spieler weiter. |
| 4 | **Verdienter Aufstieg** | Herausfordernd. Vom Niemand zum König (oder gefürchteten Tyrannen) – jeder Schritt ist erarbeitet. |
| 5 | **Sichtbare Identität** | Alles, was du trägst und erreichst, sieht man – an deinem Charakter, deinem Ruf, deinem Reich. |

---

## 2. Charakter & Fortschritt

### 2.1 Klassenlos
- Kein Klassen-Auswahlbildschirm. Fortschritt entsteht **durch Nutzung** („Learning by Doing“).
- Wer viel mit der Axt kämpft, wird besser mit Äxten. Wer schleicht, wird besser im Schleichen.
- Titel entstehen automatisch aus der Spielweise (z. B. „Klingentänzer“, „Schattenmagier“, „Drachenreiter“).

### 2.2 Attribute (Stats)
| Attribut | Wirkung |
|----------|---------|
| Stärke | Schaden schwerer Waffen, Traglast, Schmieden |
| Geschick | Präzision, leichte Waffen, Schlösser knacken, Bogen |
| Ausdauer | Leben, Stamina, schwere Rüstung |
| Intelligenz | Magiekraft, Fusions-Erfolg, Handwerks-Rezepte |
| Willenskraft | Mana, Widerstand, Zähmen |
| Charisma | Handel, Überzeugen, Gefolgsleute, Herrschaft |

### 2.3 Waffen-Disziplinen
Schwert · Großschwert · Axt · Streitaxt · Kriegshammer · Streitkolben · Speer · Hellebarde ·
Dolch · Schild · Bogen · Armbrust · Stab · Faustkampf – jeweils mit eigener Meisterschaft.

### 2.4 Skill-Fusion (Kernfeature ⭐)
- Jeder Skill besteht aus **Bausteinen**: *Element*, *Form*, *Effekte*, *Waffenbindung*.
- Zwei gemeisterte Skills können **fusioniert** werden.
- Gibt es ein bekanntes Rezept → bekannter Fusions-Skill.
- Gibt es **keins** → das System ist **gezwungen, einen neuen Skill zu erschaffen**:
  - Elemente reagieren miteinander (Feuer + Eis = **Dampf**, Licht + Schatten = **Zwielicht** …).
  - Formen verschmelzen (Hieb + Geschoss = **Wellenhieb**).
  - Effekte werden kombiniert, Stärke und Kosten neu berechnet.
  - Mit Glück (Intelligenz + Meisterschaft) entsteht eine **Mutation** – ein völlig neuer Baustein.
  - Der Skill bekommt einen generierten Namen und wird **weltweit registriert**:
    *„Du bist der Erste, der ‚Zwielicht-Wellenhieb‘ entdeckt hat.“*
- Fusionen können weiter fusioniert werden → theoretisch unendlich viele Skills.
- Prototyp vorhanden: `rpg/core/skills.py`

---

## 3. Ausrüstung, Schmieden & Handwerk
- **Sichtbare Ausrüstung:** jede Rüstung, jeder Helm, jede Waffe ist am Modell sichtbar (modulares Charaktermodell: Kopf, Torso, Arme, Hände, Beine, Füße, Umhang, Waffen).
- **Schmieden:** alles ist schmiedbar, sobald das Rezept erlernt ist.
- **Zerlegen (Reverse Engineering):** fertige Waffen/Rüstungen auseinanderbauen → Materialien zurück + Chance, das **Rezept zu lernen**. Höhere Schmiedekunst = höhere Chance.
- Materialqualität (Eisen → Stahl → Mithril → Drachenstahl …) bestimmt Werte.
- Weitere Handwerke (später): Alchemie, Lederverarbeitung, Verzauberung, Kochen, Zimmerei.

---

## 4. Welt
- **Open World** mit mehreren Ländern und Regionen, jede mit eigener Kultur, Wirtschaft und Gefahr.
- **Lebendige Welt:** Tag/Nacht, Wetter, NPC-Tagesabläufe, Karawanen, Kriege zwischen Fraktionen, Drachen-Angriffe auf Dörfer.
- **Boss-Hierarchie:**
  | Stufe | Beispiel |
  |-------|----------|
  | Elite-Gegner | Banditenhauptmann |
  | Regions-Boss | Sumpfhexe von Morrgrund |
  | Land-Boss | Uralter Frostdrache des Nordreichs |
  | Welt-Boss | Wird mit der Story enthüllt |
- Unterirdische Welten (Höhlen, Zwergenminen, Unterreich) und Unterwasser-Gebiete.

---

## 5. Drachen 🐉
Viele, verschiedene, beeindruckende Drachen – jeder mit eigenem Verhalten, Revier und Hort.

| Art | Lebensraum | Besonderheit |
|-----|-----------|--------------|
| Feuerdrache | Vulkane | Flammenatem, verbrennt Wälder |
| Frostdrache | Gletscher | Eisatem, friert Flüsse ein |
| Sturmdrache | Bergspitzen | Blitze, fliegt nur bei Gewitter |
| Seedrache | Ozean | Schwimmt statt fliegt, versenkt Schiffe |
| Erddrache / Lindwurm | Unterwelt | Gräbt Tunnel, flugunfähig |
| Schattendrache | Ruinen | Unsichtbar bei Nacht |
| Giftdrache | Sümpfe | Säureatem, vergiftet Land |
| Kristalldrache | Kristallhöhlen | Reflektiert Magie |
| Knochendrache | Alte Schlachtfelder | Untot, beschwört Skelette |
| Uralter (Ancient) | einzigartig | Land-/Welt-Bosse, sprechen, haben eigene Ziele |

Drachen sind **zähmbar** (extrem schwer) – z. B. durch Aufzucht aus einem Ei.

---

## 6. Zähmen & Tiere
- **Jedes Tier ist zähmbar** – Schwierigkeit hängt von Art, Stärke und deiner Willenskraft/Erfahrung ab.
- Kategorien:
  - **Nutztiere:** Kühe, Schafe, Hühner, Ochsen (Ressourcen, Felder pflügen, Karren ziehen)
  - **Reittiere Land:** Pferd, Kriegsross, Wolf, Bär, Echse
  - **Reittiere Luft:** Greif, Wyvern, Riesenadler, Drache
  - **Reittiere Wasser:** Seepferd, Riesenschildkröte, Seeschlange
  - **Reittiere Untergrund:** Riesenwurm, Höhlenspinne, Maulwurfsbestie
  - **Begleiter:** kämpfen mit, leveln mit, haben eigene Skills

---

## 7. Wirtschaft, Handel & Währung 💰
- **Echte Geldmenge:** Münzen werden nur geprägt (Minen + Münzstätten) und verschwinden nur durch echte Senken (Steuern ans Reich, Verschleiß, Verluste). Kein Gold aus dem Nichts.
- **Cashflow zwischen Städten:** Geld fließt durch Handel, Löhne, Steuern und Karawanen. Reiche Städte haben mehr Geld im Umlauf – höhere Preise, bessere Waren, mehr Aufträge.
- **Angebot & Nachfrage:** Preise ändern sich dynamisch je nach Vorrat, Bedarf und Wohlstand.
- **Wohlstand:** steigt/fällt durch Handel, Kriege, Drachenangriffe, Bandenplage und Spieler-Aktionen.
- **Spieler-Handel:** Waren kaufen/verkaufen, eigene Karawanen, Läden, Handelsrouten.
- Prototyp vorhanden: `rpg/core/economy.py`

---

## 8. Bauen & Königreich 🏰
- **Building-System:** vom Lagerfeuer → Hütte → Hof → Dorf → Burg → Stadt.
- Gebäude produzieren, kosten Unterhalt, ziehen NPC-Siedler an.
- **Eigenes Königreich gründen:** Land beanspruchen, Steuern erheben, Gesetze, Armee aufstellen.
- **Erobern:** Belagerungen, Schlachten, Diplomatie, Bündnisse, Verrat.

---

## 9. Ruf & Moral
- Kein Gut/Böse-Schalter, sondern mehrere Achsen:
  - **Ruhm** (wie bekannt du bist)
  - **Ehre** ↔ **Furcht** (wie man dich wahrnimmt)
  - **Fraktionsansehen** pro Fraktion
- NPCs reagieren: Wachen grüßen oder fliehen, Händler geben Rabatt oder verlangen Schutzgeld, Bänkelsänger singen Lieder über dich.

---

## 10. Story
- Du bist **niemand**. Kein Auserwählter, keine Prophezeiung über dich.
- Eine große Haupthandlung läuft im Hintergrund (Erwachen der uralten Drachen?) – du entscheidest, ob und wie du eingreifst.
- *Wird in einem eigenen Schritt ausgearbeitet (Welt-Lore, Fraktionen, Hauptfiguren).*

---

## 11. Technische Richtung & Stil
- **Engine: Godot 4** (Projekt in `game/`).
- **Grafikstil:** Low-Poly-Formen wie RuneScape + Toon-/Cel-Licht wie Zelda. Kräftige Farben, flach schattierte Flächen.
- **Steuerung:** direkt (WASD/Controller) mit freier Verfolgerkamera, Kampf mit Angriff, Block und Ausweichrolle.
- **Balancing** der Systeme weiterhin in den Python-Prototypen (`rpg/core/`), übertragen nach GDScript.

## 12. Roadmap (Schritt für Schritt)
| Phase | Inhalt | Status |
|-------|--------|--------|
| 0 | Vision & GDD | ✅ |
| 1 | Prototyp Skill-Fusion | ✅ |
| 1 | Prototyp Wirtschaft & Währung | ✅ |
| 2 | Engine-Wahl + spielbare Testwelt (Bewegung, Kamera, Kampf) | ✅ |
| 3 | Stats & Learning-by-Doing | ⏳ |
| 4 | Schmieden & Zerlegen | ⏳ |
| 5 | Zähmen, Reittiere | ⏳ |
| 6 | Drachen-KI | ⏳ |
| 7 | Bauen & Königreich | ⏳ |
| 8 | Story, Fraktionen, Quests | ⏳ |
