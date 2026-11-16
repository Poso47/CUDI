# Discord-Lese-Bot für den Clip-Scout

Viele Streamer und YouTuber suchen Clipper in ihrem Discord-Server. Diese Aufrufe sind nur für Mitglieder sichtbar.
Automatisch mitlesen mit deinem eigenen Konto verbietet Discord. Deshalb liest ein **eigener Bot**, und zwar nur in Servern,
deren Admin ihn eingeladen hat. Der Bot kann nichts schreiben, nichts löschen und niemanden anschreiben. Er liest nur
Kanäle, deren Name nach Clips, Ankündigungen, News, Infos oder Regeln klingt.

## Einmal einrichten (ca. 10 Minuten, kostenlos)

1. https://discord.com/developers/applications öffnen und mit deinem Discord-Konto anmelden.
2. Auf **New Application** gehen und als Namen z. B. „CUDI Clip-Scout“ eintragen.
3. Links auf **Bot** gehen und dort **Reset Token** wählen. Den Token kopierst du und gibst ihn **nirgends im Chat** ein.
4. Ebenfalls unter **Bot** **MESSAGE CONTENT INTENT** einschalten. Ohne diese Einstellung sieht der Bot keine Texte.
5. Im GitHub-Repo unter Settings → Secrets and variables → Actions → **New repository secret** anlegen:
   Name `CUDI_DISCORD_BOT_TOKEN`, Wert = der Token.
6. Unter **OAuth2** steht die **Client ID**. Daraus wird der Einladungslink (nur Lese-Rechte:
   „Kanäle ansehen“ + „Nachrichtenverlauf lesen“):
   `https://discord.com/oauth2/authorize?client_id=<CLIENT_ID>&scope=bot&permissions=66560`

## Streamer fragen (Vorlage)

> Hi! Ich clippe deine Streams für TikTok/YouTube Shorts (mit Credit). Damit ich deine Clipper-Aufrufe und Regeln nie verpasse,
> würde ich gern meinen Lese-Bot in euren Clipper-/Ankündigungs-Kanal holen. Er kann nur lesen, nichts schreiben:
> <Einladungslink>. Danke!

Bei Flying Uwe gilt: Das erste Wort der Nachricht muss „Clipper“ sein (Twitch, Discord oder Instagram).

## Was der Scout damit macht

- Alle 6 Stunden liest er die passenden Kanäle aller Server, in denen der Bot ist. Je Kanal sind das die letzten
  50 Nachrichten.
- Ein eindeutiger Clipper-Aufruf wird zum Beleg: Link zur Nachricht, wörtliches Zitat, Datum. Damit gilt der Creator als
  „erlaubt“, und der Clip-Autopilot arbeitet für ihn.
- Ein ausdrückliches Verbot („keine Clips“, „no reuploads“ …) sperrt den Creator sofort.
- Zugeordnet wird über den Einladungslink in `firma_daten/clip_creators.json` (`"discord": ["https://discord.gg/…"]`) oder
  über den Servernamen.
- Ohne Bot liest der Scout nur, was eine Einladung öffentlich zeigt: Servername und Beschreibung.
