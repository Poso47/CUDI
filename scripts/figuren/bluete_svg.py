"""Erzeugt die Blüten-Figur (Blume mit Stiel) als SVG-Ebenen – Quelle für cudi_video/data/figuren/bluete/.

Ebenen: „beine“ (Stiel + Blätter), „koerper“ (Blütenblätter, atmen/wiegen, mit "durchsichtig" halb durchsichtig),
„kopf“ (Blütenmitte mit Stempel, Staubgefäßen, Pollen – nickt leicht). Aufruf:
  python scripts/figuren/bluete_svg.py <svg-ordner>  &&  node scripts/figuren/svg_zu_png.js <svg-ordner> <png-ordner> 1024
"""
import json, math, random, sys
random.seed(5)
out = sys.argv[1]
VB = 400
CX, CY = 200, 150

DEFS = """<defs>
<radialGradient id="blatt" cx="0.5" cy="0.15" r="1"><stop offset="0" stop-color="#ffd1e6"/><stop offset="0.55" stop-color="#f27aae"/><stop offset="1" stop-color="#b8326f"/></radialGradient>
<radialGradient id="blatt2" cx="0.5" cy="0.15" r="1"><stop offset="0" stop-color="#ffc0dc"/><stop offset="0.6" stop-color="#e05f98"/><stop offset="1" stop-color="#9a2559"/></radialGradient>
<radialGradient id="mitte" cx="0.42" cy="0.38" r="0.7"><stop offset="0" stop-color="#ffe680"/><stop offset="0.6" stop-color="#f0b21c"/><stop offset="1" stop-color="#b56f00"/></radialGradient>
<linearGradient id="stiel" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3f8a2e"/><stop offset="0.5" stop-color="#6fc04f"/><stop offset="1" stop-color="#2f6e22"/></linearGradient>
<linearGradient id="laub" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#8fd66a"/><stop offset="1" stop-color="#2f7a24"/></linearGradient>
<radialGradient id="nektar" cx="0.4" cy="0.35" r="0.7"><stop offset="0" stop-color="#fff7c4"/><stop offset="1" stop-color="#ffcf40" stop-opacity="0.9"/></radialGradient>
<radialGradient id="schatten"><stop offset="0" stop-color="#000" stop-opacity="0.35"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<radialGradient id="glanz" cx="0.4" cy="0.3" r="0.6"><stop offset="0" stop-color="#fff" stop-opacity="0.5"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
</defs>"""


def blatt_pfad(winkel: float, laenge: float, breite: float) -> str:
    r = math.radians(winkel)
    ux, uy, nx, ny = math.cos(r), math.sin(r), -math.sin(r), math.cos(r)
    sx, sy = CX + ux * 18, CY + uy * 18
    tx, ty = CX + ux * laenge, CY + uy * laenge
    c1 = (CX + ux * laenge * .45 + nx * breite, CY + uy * laenge * .45 + ny * breite)
    c2 = (CX + ux * laenge * .45 - nx * breite, CY + uy * laenge * .45 - ny * breite)
    k1 = (tx + nx * breite * .35, ty + ny * breite * .35)
    k2 = (tx - nx * breite * .35, ty - ny * breite * .35)
    return (f"M{sx:.1f},{sy:.1f} C{c1[0]:.1f},{c1[1]:.1f} {k1[0]:.1f},{k1[1]:.1f} {tx:.1f},{ty:.1f} "
            f"C{k2[0]:.1f},{k2[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {sx:.1f},{sy:.1f} Z")


def koerper():                                    # zwei Kränze Blütenblätter mit Adern
    s = []
    for i in range(8):
        w = -90 + 22.5 + i * 45
        s.append(f'<path d="{blatt_pfad(w, 92, 30)}" fill="url(#blatt2)" stroke="#8a1f4f" stroke-opacity="0.35" stroke-width="1.2"/>')
    for i in range(8):
        w = -90 + i * 45
        d = blatt_pfad(w, 100, 34)
        s.append(f'<path d="{d}" fill="url(#blatt)" stroke="#a02a60" stroke-opacity="0.4" stroke-width="1.4"/>')
        r = math.radians(w)
        for k in (-0.25, 0, 0.25):                     # Blattadern
            ex = CX + math.cos(r + k * .35) * 82
            ey = CY + math.sin(r + k * .35) * 82
            s.append(f'<path d="M{CX + math.cos(r) * 22:.1f},{CY + math.sin(r) * 22:.1f} L{ex:.1f},{ey:.1f}" stroke="#ffffff" '
                     f'stroke-opacity="0.35" stroke-width="1"/>')
    s.append(f'<ellipse cx="{CX - 30}" cy="{CY - 40}" rx="40" ry="22" fill="url(#glanz)"/>')
    return "".join(s)


def kopf():                                       # Blütenmitte: Nektar, Stempel, Staubgefäße mit Pollen
    s = [f'<circle cx="{CX}" cy="{CY}" r="30" fill="url(#mitte)" stroke="#9a5a00" stroke-opacity="0.5" stroke-width="1.5"/>',
         f'<circle cx="{CX}" cy="{CY + 4}" r="11" fill="url(#nektar)"/>']
    for i in range(12):                               # Staubgefäße
        a = math.radians(i * 30 + 8)
        x1, y1 = CX + math.cos(a) * 12, CY + math.sin(a) * 12
        x2, y2 = CX + math.cos(a) * 34, CY + math.sin(a) * 34 - 6
        s.append(f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" stroke="#7a4a00" stroke-width="1.6"/>'
                 f'<ellipse cx="{x2:.1f}" cy="{y2:.1f}" rx="3.6" ry="2.6" fill="#ffd21f" stroke="#a86b00" stroke-width="0.8"/>')
    for _ in range(26):                               # Pollenkörner
        a, r = random.uniform(0, 2 * math.pi), random.uniform(6, 28)
        s.append(f'<circle cx="{CX + math.cos(a) * r:.1f}" cy="{CY + math.sin(a) * r:.1f}" r="1.4" fill="#fff3a0" fill-opacity="0.9"/>')
    s.append(f'<path d="M{CX},{CY + 2} L{CX},{CY - 16}" stroke="#5e8a1e" stroke-width="3"/><circle cx="{CX}" cy="{CY - 18}" r="4.5" '
             f'fill="#9ccf3a" stroke="#4e7a12" stroke-width="1"/>')        # Stempel mit Narbe
    return "".join(s)


def beine():                                      # Stiel + zwei Blätter
    return (f'<path d="M{CX - 3},{CY + 20} C{CX - 14},{CY + 110} {CX + 14},{CY + 160} {CX - 4},{CY + 222} L{CX + 6},{CY + 222} '
            f'C{CX + 24},{CY + 160} {CX - 4},{CY + 110} {CX + 7},{CY + 20} Z" fill="url(#stiel)"/>'
            f'<path d="M{CX + 2},{CY + 150} C{CX + 40},{CY + 110} {CX + 92},{CY + 118} {CX + 112},{CY + 104} C{CX + 96},{CY + 146} '
            f'{CX + 46},{CY + 166} {CX + 2},{CY + 158} Z" fill="url(#laub)" stroke="#2a6a1c" stroke-opacity="0.5"/>'
            f'<path d="M{CX - 2},{CY + 176} C{CX - 40},{CY + 140} {CX - 90},{CY + 150} {CX - 110},{CY + 138} C{CX - 92},{CY + 178} '
            f'{CX - 44},{CY + 192} {CX - 2},{CY + 184} Z" fill="url(#laub)" stroke="#2a6a1c" stroke-opacity="0.5"/>'
            f'<path d="M{CX + 6},{CY + 154} Q{CX + 60},{CY + 134} {CX + 108},{CY + 106}" stroke="#d8f5c0" stroke-opacity="0.5" fill="none"/>'
            f'<path d="M{CX - 6},{CY + 180} Q{CX - 60},{CY + 162} {CX - 106},{CY + 140}" stroke="#d8f5c0" stroke-opacity="0.5" fill="none"/>')


def schatten():
    return f'<ellipse cx="{CX}" cy="{CY + 224}" rx="90" ry="10" fill="url(#schatten)"/>'


EBENEN = {"schatten": schatten(), "beine": beine(), "koerper": koerper(), "kopf": kopf()}
for name, body in EBENEN.items():
    open(f"{out}/{name}.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}{body}</svg>')
open(f"{out}/ganz.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}'
                                   + "".join(EBENEN.values()) + "</svg>")
json.dump({"name": "Blüte", "ebenen": list(EBENEN), "groesse": VB, "versteckt": [], "mit_kopf": [],
           "drehpunkte": {"kopf": [CX, CY + 40], "koerper": [CX, CY]},
           "anker": {"bluete": [CX, CY], "nektar": [CX, CY + 4], "nektarien": [CX, CY + 8], "stempel": [CX, CY - 18],
                     "narbe": [CX, CY - 18], "staubgefaesse": [CX + 30, CY - 20], "pollen": [CX - 24, CY - 14],
                     "bluetenblatt": [CX + 70, CY - 70], "stiel": [CX, CY + 120], "blatt": [CX + 80, CY + 120], "boden": [CX, CY + 224]}},
          open(f"{out}/figur.json", "w"), ensure_ascii=False, indent=1)
print("ok")
