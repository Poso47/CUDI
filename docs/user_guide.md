# CUDI – Bedienungsanleitung

CUDI ist dein persönlicher KI-Kollege. Du sprichst ganz normal mit ihm. CUDI merkt sich, was du ihm
sagst, kennt deine Projekte, liest deine Dokumente und erledigt Aufgaben – bei allem, was etwas
verändert, fragt er vorher.

---

## 1. Starten – der einfachste Weg

**Windows:** Im Ordner `CUDI` doppelt auf **`CUDI_STARTEN.bat`** klicken. Fertig.
Beim ersten Start richtet sich CUDI selbst ein (eigene Umgebung im Ordner `.venv`, dauert einige
Minuten). Danach startet CUDI in Sekunden. Voraussetzung: Python 3.10+ von https://www.python.org
(beim Installieren „Add python.exe to PATH“ anhaken).

**macOS/Linux:** `./cudi_starten.sh`

**In VS Code:** Links auf „Ausführen und Debuggen“ (oder **F5**) und „CUDI starten (Fenster)“ wählen.
Es gibt auch „CUDI im Terminal (Chat)“, „CUDI Selbstdiagnose“ und „CUDI Tests“.

**Von Hand (Terminal):** `pip install -r requirements-core.txt`, dann `python main.py`.

### Sprachmodell anschließen (eine Möglichkeit genügt)

Ohne Sprachmodell funktionieren Befehle, Gedächtnis, Projekte und Dokumentsuche – freie Antworten
und selbstständiges Arbeiten aber erst mit Modell.

**A) Lokal und kostenlos – Ollama (empfohlen für Datenschutz)**
1. Ollama installieren: https://ollama.com
2. Im Terminal: `ollama pull llama3.1`
3. CUDI starten – fertig. (Ein anderes installiertes Modell nimmt CUDI automatisch.)

**B) Claude (Anthropic) – beste Qualität, kostenpflichtig**
1. Datei `.env.example` kopieren und in `.env` umbenennen.
2. In `.env` die Zeile `ANTHROPIC_API_KEY=...` mit deinem Schlüssel eintragen (ohne `#` davor).
3. CUDI neu starten – der Starter installiert das Claude-Paket dann automatisch
   (von Hand: `pip install anthropic`).

**C) OpenAI** – wie B, aber `OPENAI_API_KEY=...`.

Die Datei `.env` wird nie ins Git-Repository übernommen. Reihenfolge der Modelle ändern:
`CUDI_PROVIDER_ORDER=anthropic,ollama` in `.env`.

Prüfen, was verbunden ist: Bereich **🤖 Modelle** oder `/modelle` im Chat.

## 2. Startvarianten

| Was | Doppelklick-Starter | Terminal |
|---|---|---|
| Fenster (normal) | `CUDI_STARTEN.bat` | `python main.py` |
| Chat im Terminal | `CUDI_STARTEN.bat --cli` | `python main.py --cli` |
| Selbstdiagnose | `CUDI_STARTEN.bat --diagnose` | `python main.py --diagnose` |

Wurde `requirements-core.txt` geändert, die Datei `.venv/cudi_installiert.txt` löschen – beim
nächsten Start wird dann neu installiert.

## 3. Das Fenster

Links die Bereiche, rechts der Inhalt:

| Bereich | Wofür |
|---|---|
| 💬 Chat | mit CUDI reden; Enter sendet, Umschalt+Enter = neue Zeile; unten Schnellknöpfe |
| 🧠 Gedächtnis | alle Erinnerungen mit Quelle/Status; suchen, korrigieren, löschen, exportieren |
| 📁 Projekte | Projekte anlegen, aktiv setzen, Entscheidungen/Probleme/Schritte eintragen |
| ✅ Aufgaben | Aufgaben anlegen und auf erledigt/in Arbeit/fehlgeschlagen setzen |
| 📄 Dokumente | Dokumente importieren und durchsuchen (mit Fundstelle) |
| 🤖 Modelle | welches Sprachmodell verbunden ist und wie man eins anschließt |
| 🛠 Werkzeuge | was CUDI ausführen darf (Stufe, Rückfrage ja/nein) |
| 🩺 Diagnose | Selbsttest, letzte Ereignisse, Sicherung |
| ⚙️ Einstellungen | Name, Anrede (du/Sie), Modelle, Freigabestufe, Datenschutz |

Die frühere Oberfläche („CUDI_SUPREME“) gibt es weiterhin: `CUDI_STARTEN.bat --alt` bzw.
`python main.py --alt`.

## 4. Mit CUDI arbeiten

Schreib einfach, was du brauchst – zum Beispiel:

* „Kannst du programmieren?“ → CUDI fragt, was du bauen willst, und legt dann los.
* „Schreib mir ein Python-Skript, das meine Fotos nach Datum sortiert, und speichere es.“ →
  CUDI schreibt den Code und fragt **vor dem Speichern** um Erlaubnis. Dateien landen im Ordner
  `workspace/`.
* „Merke dir: Mein Lieblingseditor ist VS Code.“ → wird dauerhaft gespeichert.
* „Was ist mein Lieblingseditor?“ → CUDI antwortet mit Quelle.
* „Künftig bitte immer kurze Antworten mit Codebeispiel.“ → gilt ab jetzt für alle Antworten.
* „Das war richtig.“ / „Das ist falsch.“ / „Diese Lösung hat funktioniert.“ → CUDI lernt daraus.

Unter jeder Antwort siehst du, was **wirklich** passiert ist:
✅ ausgeführt · ❌ fehlgeschlagen · ⛔ von dir abgelehnt. Welches Modell geantwortet hat (lokal oder
extern), steht neben dem Namen.

### Freigaben

Lesen und Nachschlagen macht CUDI selbst. Bevor CUDI etwas **verändert** (Datei schreiben,
Erinnerung löschen, Sicherung zurückspielen …), erscheint ein Fenster: *Ja* oder *Nein*. Du kannst
auch einfach „ja“ oder „nein“ in den Chat schreiben. Mit dem Häkchen „für diese Sitzung erlauben“
fragt CUDI bis zum nächsten Start bei diesem Werkzeug nicht mehr.

## 5. Das Digitale Gehirn

Die Bereiche **🧠 Gedächtnis**, **📁 Projekte**, **✅ Aufgaben** und **📄 Dokumente** zeigen alles, was CUDI
weiß – Erinnerungen mit Status (bestätigt/vorläufig/veraltet) und Quelle.

* **Widersprüche:** Sagst du etwas, das einer gespeicherten Angabe widerspricht, fragt CUDI nach.
  Die alte Angabe wird dann als „veraltet“ markiert, nicht gelöscht.
* **Korrigieren:** `/korrigiere 3 Mein Lieblingseditor ist PyCharm`
* **Löschen:** „Vergiss #3“ (mit Rückfrage)
* **Alles exportieren:** `/export` (JSON-Datei in `data/exports/`)

### Projekte

```
/projekt neu Webseite | Seite für meinen Friseursalon
/entscheidung Wir nutzen WordPress
/problem Kontaktformular sendet nicht
/lösung SMTP-Port 587 statt 25
/schritt Bilder optimieren
/projektstand
```

Nach einem Neustart weiß CUDI, wo ihr stehen geblieben seid („Wo waren wir?“).

### Dokumente

* Bereich **📄 Dokumente → Dokument importieren …** und Datei wählen, **oder**
* Dateien in den Ordner `import/` legen und `/importordner` eingeben.

Unterstützt: PDF, DOCX, TXT, Markdown, JSON, CSV. Danach einfach fragen – CUDI nennt die Fundstelle
(z. B. „vertrag.pdf, Seite 2“). Eingescannte PDFs ohne Texterkennung können nicht gelesen werden.
Anweisungen, die in Dokumenten stehen, befolgt CUDI nicht – Dokumente sind nur Wissensquellen.

## 6. Sicherung und Wiederherstellung

* Automatisch: einmal täglich beim Start (die letzten 10 bleiben, Ordner `data/backups/`).
* Manuell: `/sicherung` oder Bereich **🩺 Diagnose → Sicherung erstellen**.
* Zurückspielen: `/sicherungen` zeigt die Dateien, `/wiederherstellen DATEINAME`. Vorher wird der
  aktuelle Stand automatisch gesichert.

## 7. Wenn etwas nicht klappt

1. Bereich **🩺 Diagnose** öffnen, `/status` eingeben oder `python main.py --diagnose`. ❌ = kritisch, ⚠️ = Warnung,
   ➖ = optional/nicht vorhanden – jeweils mit Lösungsvorschlag.
2. Technische Details stehen in `logs/cudi.log`.
3. Antwortet CUDI nur eingeschränkt, ist meist kein Sprachmodell verbunden → `/modelle`.

## 8. Einstellungen

Am einfachsten im Bereich **⚙️ Einstellungen**. Gespeichert wird in `config/settings.json`; alternativ `.env`:

| Einstellung | Bedeutung | Standard |
|---|---|---|
| `user_name` / `CUDI_USER_NAME` | wie CUDI dich nennt | leer |
| `address` | „du“ oder „Sie“ | du |
| `provider_order` / `CUDI_PROVIDER_ORDER` | Reihenfolge der Modelle | ollama, anthropic, openai |
| `ollama_model`, `anthropic_model`, `openai_model` | Modellnamen | llama3.1, claude-opus-5-5, gpt-4o |
| `auto_approve_level` | bis zu welcher Stufe ohne Rückfrage (1–4) | 2 |
| `share_documents_with_external_models` | Dokumentauszüge an externe Modelle senden | true |

## 9. Was CUDI (noch) nicht kann

Sprachsteuerung, Websuche, Programme/Tests ausführen, E-Mail/Kalender, Videoproduktion und
Synchronisierung zwischen Geräten sind noch nicht eingebaut – CUDI sagt das auch ehrlich, wenn du
danach fragst. Die Vorschläge dazu stehen in `docs/implementation_plan.md`. In der alten Oberfläche
(`--alt`) nutzen die alten Knöpfe noch die alte Logik.
