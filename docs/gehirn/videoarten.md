# Videoarten und Bausteine

Teil des Projekt-Gehirns (Übersicht: CLAUDE.md). Nur lesen, wenn die Aufgabe dieses Thema berührt.

Neben dem älteren Desktop-Assistenten (README.md, `main.py`, `ui/`) enthält das Repo **CUDI Video**
(`cudi_video/`, Doku: README_VIDEO.md): kostenlose Hochformat-Videos (1080×1920, ≤ 179 s, DE + EN)
für TikTok/YouTube Shorts.

- **Ranking-Faktenvideos**: Wikidata (neuester Wert je Objekt vor dem LIMIT) → Abgleich mit Weltbank,
  CIA Factbook, OSM, Wikipedia in 8 Sprachen, Webseiten aus den Einzelnachweisen (`ExternalSourcesChecker`,
  `n_extern`, Warnung „nur von Wikipedia/Wikidata bestätigt“) (`cudi_video/verify/`) → Skript nur aus geprüften Zahlen →
  Infografik-Render + edge-tts. Grundsatz: **nichts erfinden**, widersprochene Werte fliegen raus.
- **Reddit-Storys** (`cudi_video/story/`): Suche per Stimmung/Beschreibung/Link (Arctic-Shift-Archiv),
  Lektorat (heikle Stellen umschreiben statt weglassen), Skelett, Bilder/Clips, Stimme je Stimmung.
- Rankings mit echten Videoclips (`media.py`: Pexels/Pixabay mit Schlüssel, NASA, Commons; je Platz bis 3
  Ausschnitte, `render/clipreel.py`), Fotos sonst Commons → Openverse/NASA (Namensabgleich, nur kommerziell nutzbar).
- Fakten-Rankings (`facts.py`, `spec.kind == "facts"`): Claude plant `art: fakten` (Artikeltitel), schreibt Fakten mit
  wörtlichem Beleg; Prüfung je Fakt (Beleg in Quelle, Zahlen auch in zweiter Quelle, keine erfundenen Wörter –
  deutsche Alltagswörter per `textcheck.everyday_word`), abgelehnte Fakten einmal zur Korrektur (`fakten_korrektur`).
- Themen-Wissensstruktur (`themen.py`, `spec.focus`): Planer liefert Themenkern/Aspekte/nicht gemeint; alle Schreib-
  aufgaben erzählen Aufhänger → Kernaussage → Erklärung → Bedeutung für dich; Fakten brauchen Aspekt, Mindestlänge, `belege`.
- Formate (`render/formats.py`: karte, vollbild, kreis, magazin, polaroid, zahl, manuskript – eigener Bildaufbau, Übergang,
  Intro, Abschluss) je Video; Farben (`theme.STYLES`) nach Thema (`palette_options`: Titelwörter/Icon); `pick_style`
  fest je Video-ID, `apply_style` in `make_scene` (jeder Render-Prozess); Auftrag `format`.
- **Manuskript/Erklärvideo**: Format `manuskript` (Buchlook, eigenes Design, Schriften EB Garamond/Amiri/Inter in
  `video_assets/fonts`, Bausteine `render/manuskript.py`, Linien-Grafiken `render/linien.py`; bringt immer Design
  „manuskript“ mit, keine Maskottchen). Videoart `cudi_video/erklaer/` (Szenen-Skript JSON, `python -m cudi_video erklaer
  <skript.json>`, Beispiel `examples/erklaer_goldener_schnitt.json`, Szenentyp `erklaer` im Format).
- Spannungsbogen (`retention.py`): Hook mit Neugierlücke, Zwischen-Aufhänger aus geprüften Werten, Kommentarfrage
  je Thema; Regeln für Claude-Texte (`NARRATION_RULES`) und Storys je Stimmung (`story_rules`). Zahl im Wunsch = Anzahl.
- **Regie & Psychologie** (`regie.py`, nach dem Erzählen/vor `wahrheit`+Vertonung in `pipeline.run` und `story/editor.build_skeleton`): Basis-Checkliste (`firma/wissen.BASIS`) + gelernte Regeln mit Quelle (`firma_daten/wissen.json`, Wissens-Sammler `firma/wissen.py`, wöchentlich, Gemini, `firma-wissen.yml`) → Score je Kriterium vorher/nachher; EINE Schreibaufgabe `regie` (3 Hook-Kandidaten ohne Spoiler, natürlichere Abschnitte, Schluss); jede Änderung durch `pruefe_aenderung` + `wahrheit.Pruefer` (neuer Befund oder sinkender Score → alter Text bleibt); ohne Modell nur Bewertung; Ergebnis `regie.json`/`ergebnis.json["regie"]`/Prüfbericht „Regie & Psychologie“. `tts.naturalize`: Atempausen + leichte Tempo-/Tonhöhen-Variation je Video (aus: `CUDI_NATUERLICH=0`).
- Bildprüfung (`bildcheck.py`, CLIP ViT-B-32 CPU, Cache `video_output/_models`, 3 Bilder je Kandidat, ≥ 2/3 mit p ≥ 0.5; Ausfall → Tag-Abgleich;
  Ranking-Clips nur sortiert via `media.rank_by_image`; Tests setzen `CUDI_BILDPRUEFUNG=0`). Bildpassung (`facts.find_visuals`, `media.motif_matches`): Fakt-Feld `motiv` + `suche`-Liste; Treffer nur, wenn alle Kernwörter des
  Motivs in Beschreibung/Tags stehen (Clip → Foto → Commons → „Stimmungsbild“, im Prüfbericht vermerkt). Aha-Regel
  (`themen.AHA_RULES`, Fakt-Feld `aha_<sprache>`, geprüft in `facts.checked_aha`): Outro „Heute gelernt: …“ (Platz 1; Rankings: Spitzenwert).
- Verpackung (`render/cover.py`, `metadata.py`): Cover 1080×1920 (Titelwort, Spitzenwert, bestes Bild, Look des Formats, Safe-Zone) auch als erstes Frame (0,2 s; `CUDI_COVER_FRAME=0` aus); 3 Titelvarianten ≤ 60 Zeichen je Sprache (Aufgabe `titel` über `handoff`, geprüft: Zahl/Clickbait/Länge, sonst Regel-Varianten, beste per `title_score`) im Ergebnis (`titel_varianten`, Kopier-Knöpfe); 3–5 Hashtags je Plattform (#shorts YouTube, #fyp TikTok); Längenziel `LENGTH_GOALS` nur als Hinweis im Prüfbericht.
- **Experimente/Lernen** (`experimente.py`, `firma/lernen.py`, Doku `docs/lernen-einrichten.md`): je Video eine Variante je Stellschraube
  (Format, Design, Bewegung, Musik, Maskottchen; Hook/Länge vorbereitet, `KNOBS[..]["aktiv"]`), Bandit (Thompson, ≥ 20 % Erkundung) aus
  `firma_daten/lernen.json`; feste Wünsche im Auftrag gehen vor; ohne Daten = alte md5-Wahl. `varianten` in `ergebnis.json`/Ergebnis-Dokument;
  App-Bewertungen senden `vorlieben.varianten_gut/_schlecht` (zählen doppelt, Env `CUDI_VORLIEBEN_VARIANTEN`). Lern-Analyst (täglich, Workflow
  `firma-lernen.yml`) liest YouTube (`youtube.readonly` oder `CUDI_YT_API_KEY`) und TikTok (`video.list`; `youtube-login --lesen`, `tiktok-login --lesen`),
  Zuordnung über `firma_daten/uploads.json` (nur Notbetrieb-Job „liste“ schreibt; Claude-Läufe committen nie).
- **Satire** (`satire/`, Auftrag `art: "satire"` mit `thema`/`meldung`, `sprache`): echter bestätigter Kern (≥ 2 Betreiber, Beleg, `wahrheit.Pruefer`) → erkennbare Überspitzung → Pointe; „SATIRE“ in jedem Bild/Cover/Titel/Beschreibung, keine erfundenen Zitate/Zahlen/Namen, kein Spott gegen Gruppen, heikel → abgelehnt („nur als Reportage“); eigener Look in `satire/render.py` (kein Eingriff in `render/*`), Ideen-Bereich „satire“.
- **Reportage** (`reportage/`, Auftrag `art: "reportage"` mit `thema`, `links`, `sprache`; Tab „Reportage“ der App): sachlich, nur Aussagen mit wörtlichem Beleg
  aus ≥ 2 unabhängigen Betreibern (news.json, Wikipedia, Links), Aufgabe `reportage` (`handoff`) + Regelweg, Zahlen/Namen/Clickbait/Drama/Spekulation geprüft,
  Buchlook ohne Musik/Maskottchen, Quellen + Stand am Ende; zu wenig Quellen = ehrlicher Abbruch. Ideen mit `bereich: reportage` tragen einen Auftrag.
  Weitere Formate als Plan: `docs/content-formate.md`.
- **Recherche-Agent** (`cudi_video/recherche/`, Doku `docs/recherche.md`, Skill `recherche`): `suche` (Claude-Websuche nur im App-Lauf → Brave `CUDI_BRAVE_API_KEY` optional → DuckDuckGo-HTML → GDELT → Fachquellen Eurostat/Weltbank/Europe PMC; deutsch zuerst, Region DE), `lese(url)` (robots, Limits, Datum aus Meta/JSON-LD/Text, Betreiber/Eigentümer/Seitentyp), `recherchiere(frage, bereich)` (Aussagen mit wörtlichem Zitat+Datum, „bestätigt“ ≥ 2 unabhängige Gruppen, Widersprüche/ältere Stände ausgewiesen, Protokoll `schritte`, Prüfbericht-Abschnitt „Recherche“). Wikipedia nur in `fakten`/`geschichte`, nur mit Zweitquelle und ohne Manipulationszeichen (`recherche/wikipedia.py`), sonst Suchhinweis. Eingebaut in Reportage, Satire (Nachsuche), Wissens-Sammler, Ideen (`themenrecherche`), `verify.RechercheChecker` (freie Themen); Firma-Rolle „Rechercheur“ (`firma/recherche.py`, täglich, `recherche.json`, Export `recherche`). Aus: `CUDI_RECHERCHE=0`.
- Lange Videos bis 10 Min. (App-Fassung in Stücken ≤ 19 MB), Maskottchen „CUDI“ (`mascot.py`, lippensynchron
  zur Sprachspur, abschaltbar: Auftrag `maskottchen`, `CUDI_MASCOT`), Story-Bilder „cartoon“ (gleiche Hauptfigur
  `figur`, gleicher Seed).
