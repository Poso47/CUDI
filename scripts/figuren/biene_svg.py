"""Erzeugt die Bienen-Figur (Honigbiene, Blick nach rechts) als SVG-Ebenen – Quelle für cudi_video/data/figuren/biene/.

Ebenen wie beim Huhn: „koerper“ (Hinterleib, atmet, wird mit "durchsichtig" halb durchsichtig – darin Honigblase/Magen),
„brust“, „kopf“ (nickt), „fluegel“ (schlagen bei „flattere“), „lid“ (blinzeln). Aufruf:
  python scripts/figuren/biene_svg.py <svg-ordner>  &&  node scripts/figuren/svg_zu_png.js <svg-ordner> <png-ordner> 1024
"""
import json, math, random, sys
random.seed(11)
out = sys.argv[1]
VB = 400

DEFS = """<defs>
<radialGradient id="hinterleib" cx="0.6" cy="0.35" r="0.8"><stop offset="0" stop-color="#ffd35c"/><stop offset="0.55" stop-color="#f0a423"/><stop offset="1" stop-color="#a8600c"/></radialGradient>
<radialGradient id="brust" cx="0.45" cy="0.35" r="0.75"><stop offset="0" stop-color="#d9a24c"/><stop offset="0.6" stop-color="#9a5f1f"/><stop offset="1" stop-color="#4f2d0d"/></radialGradient>
<radialGradient id="kopf" cx="0.4" cy="0.35" r="0.8"><stop offset="0" stop-color="#7a4a22"/><stop offset="0.7" stop-color="#3d230e"/><stop offset="1" stop-color="#1f1206"/></radialGradient>
<radialGradient id="auge" cx="0.35" cy="0.3" r="0.8"><stop offset="0" stop-color="#5a5f70"/><stop offset="0.5" stop-color="#20232d"/><stop offset="1" stop-color="#0a0b10"/></radialGradient>
<linearGradient id="fluegel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffffff" stop-opacity="0.75"/><stop offset="1" stop-color="#bfe3ff" stop-opacity="0.35"/></linearGradient>
<radialGradient id="pollen" cx="0.4" cy="0.35" r="0.8"><stop offset="0" stop-color="#fff07a"/><stop offset="1" stop-color="#e0a000"/></radialGradient>
<radialGradient id="schatten"><stop offset="0" stop-color="#000" stop-opacity="0.4"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<radialGradient id="glanz" cx="0.4" cy="0.3" r="0.6"><stop offset="0" stop-color="#fff" stop-opacity="0.6"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
</defs>"""

HINTERLEIB = "M232,206 C226,168 186,150 146,156 C104,162 74,190 66,224 C60,252 84,276 122,282 C168,290 214,272 228,244 C232,232 233,218 232,206 Z"


def haare(cx, cy, r, n, farbe, laenge=7, op=0.5):
    s = []
    for _ in range(n):
        a = random.uniform(0, 2 * math.pi)
        rr = r * random.uniform(0.75, 1.02)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        l = laenge * random.uniform(0.6, 1.2)
        s.append(f'<path d="M{x:.1f},{y:.1f} l{l * math.cos(a):.1f},{l * math.sin(a):.1f}" stroke="{farbe}" stroke-opacity="{op}" '
                 f'stroke-width="1.3" stroke-linecap="round"/>')
    return "".join(s)


def koerper():                                    # Hinterleib mit Streifen, Fell, Stachel
    s = [f'<path d="{HINTERLEIB}" fill="url(#hinterleib)"/>', f'<clipPath id="hc"><path d="{HINTERLEIB}"/></clipPath>',
         '<g clip-path="url(#hc)">']
    for x0, w in ((92, 16), (130, 18), (170, 18)):   # dunkle Querstreifen, leicht gebogen
        s.append(f'<path d="M{x0},140 C{x0 - 10},190 {x0 - 10},240 {x0},300 L{x0 + w},300 C{x0 + w - 10},240 {x0 + w - 10},190 {x0 + w},140 Z" '
                 f'fill="#2b1a08" fill-opacity="0.88"/>')
    s.append('<ellipse cx="170" cy="190" rx="55" ry="26" fill="url(#glanz)"/></g>')
    s.append(haare(150, 218, 74, 70, "#7a4a12", 6, 0.35))
    s.append(f'<path d="{HINTERLEIB}" fill="none" stroke="#5a3207" stroke-opacity="0.6" stroke-width="2"/>')
    s.append('<path d="M70,232 L44,246 L70,244 Z" fill="#2b1a08"/>')           # Stachel
    return "".join(s)


def brust():                                      # Brust (Thorax), dicht behaart
    return ('<ellipse cx="248" cy="196" rx="46" ry="42" fill="url(#brust)"/>' + haare(248, 196, 44, 120, "#e8b866", 8, 0.55)
            + haare(248, 196, 34, 60, "#5a3510", 6, 0.4) + '<ellipse cx="238" cy="178" rx="22" ry="14" fill="url(#glanz)"/>')


def kopf():                                       # Kopf mit Facettenauge, Fühlern, Rüssel
    s = ['<path d="M300,152 C332,150 346,176 342,204 C338,228 318,240 300,236 C280,232 272,208 274,186 C276,166 286,154 300,152 Z" fill="url(#kopf)"/>',
         haare(306, 194, 34, 40, "#c08a40", 5, 0.4),
         '<ellipse cx="318" cy="186" rx="13" ry="20" fill="url(#auge)" stroke="#000" stroke-opacity="0.4"/>',
         '<ellipse cx="314" cy="178" rx="4" ry="6" fill="#fff" fill-opacity="0.55"/>']
    for x, y in ((312, 196), (320, 192), (316, 202), (323, 182)):   # Facetten-Andeutung
        s.append(f'<circle cx="{x}" cy="{y}" r="1.6" fill="#8890a8" fill-opacity="0.35"/>')
    s.append('<path d="M314,156 C322,128 340,112 360,104" stroke="#1f1206" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
             '<path d="M304,156 C306,128 318,108 336,96" stroke="#1f1206" stroke-width="3.4" fill="none" stroke-linecap="round"/>'
             '<circle cx="360" cy="104" r="3.5" fill="#1f1206"/><circle cx="336" cy="96" r="3.5" fill="#1f1206"/>')
    s.append('<path d="M326,226 C332,240 336,252 344,262" stroke="#3d230e" stroke-width="3" fill="none" stroke-linecap="round"/>')  # Rüssel
    return "".join(s)


def lid():
    return '<ellipse cx="318" cy="186" rx="13.5" ry="20.5" fill="#5a3518"/>'


def fluegel():                                    # zwei durchscheinende Flügelpaare mit Adern
    s = []
    for cx, cy, rx, ry, rot in ((205, 120, 78, 30, -28), (190, 150, 56, 22, -12)):
        s.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" transform="rotate({rot} {cx} {cy})" fill="url(#fluegel)" '
                 f'stroke="#7d9bb5" stroke-opacity="0.7" stroke-width="1.4"/>')
        r = math.radians(rot)
        for k in (-0.5, 0, 0.45):
            x1, y1 = cx + math.cos(r) * rx * 0.85, cy + math.sin(r) * rx * 0.85 + k * ry * 0.8
            s.append(f'<path d="M242,166 Q{cx:.0f},{cy + k * ry:.0f} {x1:.0f},{y1:.0f}" stroke="#7d9bb5" stroke-opacity="0.45" '
                     f'stroke-width="1" fill="none"/>')
    s.append('<ellipse cx="190" cy="108" rx="30" ry="9" transform="rotate(-28 190 108)" fill="#fff" fill-opacity="0.35"/>')
    return "".join(s)


def beine():                                      # drei sichtbare Beine, Hinterbein mit Pollenhöschen
    s = []
    for (x0, y0), (x1, y1), (x2, y2) in (((232, 226), (214, 262), (200, 300)), ((250, 232), (258, 270), (250, 304)),
                                         ((266, 228), (290, 258), (304, 292))):
        s.append(f'<path d="M{x0},{y0} L{x1},{y1} L{x2},{y2}" stroke="#2b1a08" stroke-width="5" fill="none" stroke-linecap="round" '
                 f'stroke-linejoin="round"/>')
    s.append('<ellipse cx="210" cy="280" rx="12" ry="15" fill="url(#pollen)" stroke="#b07800" stroke-opacity="0.6"/>')
    return "".join(s)


def schatten():
    return '<ellipse cx="200" cy="350" rx="120" ry="13" fill="url(#schatten)"/>'


EBENEN = {"schatten": schatten(), "beine": beine(), "koerper": koerper(), "brust": brust(), "kopf": kopf(), "fluegel": fluegel(),
          "lid": lid()}
for name, body in EBENEN.items():
    open(f"{out}/{name}.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}{body}</svg>')
open(f"{out}/ganz.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}'
                                   + "".join(v for k, v in EBENEN.items() if k != "lid") + "</svg>")
json.dump({"name": "Biene", "ebenen": list(EBENEN), "groesse": VB, "versteckt": ["lid"], "mit_kopf": ["lid"],
           "drehpunkte": {"kopf": [290, 200], "fluegel": [242, 166], "lid": [318, 186], "koerper": [150, 220]},
           "anker": {"kopf": [306, 194], "auge": [318, 186], "fuehler": [358, 104], "ruessel": [344, 262], "brust": [248, 196],
                     "hinterleib": [140, 222], "honigblase": [200, 214], "magen": [160, 220], "darm": [110, 228], "herz": [150, 184],
                     "stachel": [46, 245], "fluegel": [205, 118], "beine": [252, 290], "pollen": [210, 280],
                     "wachsdruesen": [150, 270], "futtersaftdruese": [298, 208]}},
          open(f"{out}/figur.json", "w"), ensure_ascii=False, indent=1)
print("ok")
