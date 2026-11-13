"""Erzeugt die Huhn-Figur als SVG, aufgeteilt in Ebenen (je Ebene eine Datei) – Quelle für cudi_video/data/figuren/huhn/."""
import json, math, random, sys
random.seed(7)
out = sys.argv[1]
VB = 400

DEFS = """<defs>
<radialGradient id="koerper" cx="0.55" cy="0.38" r="0.75"><stop offset="0" stop-color="#f2b46a"/><stop offset="0.55" stop-color="#cf7f36"/><stop offset="1" stop-color="#7f3f17"/></radialGradient>
<radialGradient id="kopf" cx="0.45" cy="0.3" r="0.8"><stop offset="0" stop-color="#f6c27d"/><stop offset="0.6" stop-color="#d58b40"/><stop offset="1" stop-color="#94501f"/></radialGradient>
<linearGradient id="fluegel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c06d2b"/><stop offset="1" stop-color="#6e3412"/></linearGradient>
<linearGradient id="schwanz" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3b2a1d"/><stop offset="0.6" stop-color="#5a3a20"/><stop offset="1" stop-color="#8a5326"/></linearGradient>
<radialGradient id="kamm" cx="0.4" cy="0.3" r="0.9"><stop offset="0" stop-color="#ff6a5a"/><stop offset="0.6" stop-color="#e0262b"/><stop offset="1" stop-color="#8f0f17"/></radialGradient>
<linearGradient id="schnabel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd36b"/><stop offset="1" stop-color="#d98a1a"/></linearGradient>
<linearGradient id="bein" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f3b33a"/><stop offset="0.5" stop-color="#ffd56a"/><stop offset="1" stop-color="#c9871d"/></linearGradient>
<radialGradient id="schatten"><stop offset="0" stop-color="#000" stop-opacity="0.45"/><stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>
<radialGradient id="glanz" cx="0.4" cy="0.3" r="0.6"><stop offset="0" stop-color="#fff" stop-opacity="0.55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<filter id="weich" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="0.6"/></filter>
</defs>"""

KOERPER = "M104,176 C126,192 176,172 232,170 C266,168 286,180 300,204 C320,236 314,280 284,302 C250,328 168,332 130,304 C102,282 90,238 98,206 C100,194 98,184 104,176 Z"
FLUEGEL = "M150,198 C192,176 252,186 274,218 C256,256 196,268 146,248 C134,232 136,212 150,198 Z"
HALS = "M238,196 C244,154 262,116 294,102 C324,92 342,124 328,150 C318,170 312,196 308,222 C286,222 260,212 238,196 Z"

def feder(cx, cy, w, h, fill, rot=0, op=1.0, stroke="#6a3010"):
    return (f'<path d="M{cx-w/2:.1f},{cy:.1f} Q{cx:.1f},{cy+h*1.35:.1f} {cx+w/2:.1f},{cy:.1f}" fill="{fill}" fill-opacity="{op}" '
            f'stroke="{stroke}" stroke-opacity="0.35" stroke-width="0.8" transform="rotate({rot} {cx:.1f} {cy:.1f})"/>')

def koerper():
    s = [f'<path d="{KOERPER}" fill="url(#koerper)"/>', '<clipPath id="kc"><path d="%s"/></clipPath>' % KOERPER, '<g clip-path="url(#kc)">']
    for row in range(15):                                     # Federreihen wie Schuppen, vorn kleiner, hinten größer
        y = 160 + row * 12
        for col in range(18):
            x = 92 + col * 12 + (6 if row % 2 else 0) + random.uniform(-1.5, 1.5)
            t = (x - 100) / 230
            w = 14 - 4 * t
            hell = 0.82 + 0.25 * random.random() - 0.15 * (row / 14)
            c = tuple(int(min(255, v * hell)) for v in (214, 132, 58))
            s.append(feder(x, y, w, 8, "rgb(%d,%d,%d)" % c, rot=-12 + 8 * t, op=0.55))
    s.append('<ellipse cx="240" cy="200" rx="70" ry="45" fill="url(#glanz)"/></g>')
    s.append(f'<path d="{KOERPER}" fill="none" stroke="#5c2a0c" stroke-opacity="0.5" stroke-width="2"/>')
    return "".join(s)

def fluegel():
    s = [f'<path d="{FLUEGEL}" fill="url(#fluegel)" stroke="#4e230a" stroke-opacity="0.5" stroke-width="1.6"/>',
         '<clipPath id="fc"><path d="%s"/></clipPath>' % FLUEGEL, '<g clip-path="url(#fc)">']
    for row in range(3):                                       # Deckfedern
        for col in range(9):
            x, y = 160 + col * 13 + row * 6, 200 + row * 11
            s.append(feder(x, y, 15, 9, "#b8642a" if row < 2 else "#8e461c", rot=-8, op=0.85))
    for i in range(7):                                         # Schwungfedern hinten, lang
        x = 150 + i * 4
        s.append(f'<path d="M{200+i*9},{232+i} C{180+i*6},{246+i*2} {160+i*3},{250+i} {140+i*2},{244+i}" stroke="#3e1b07" stroke-opacity="0.45" stroke-width="1.4" fill="none"/>')
    s.append('</g>')
    return "".join(s)

def schwanz():
    s = []
    blaetter = [(-172, 92, 22), (-158, 112, 24), (-144, 124, 26), (-130, 126, 26), (-117, 116, 24), (-105, 98, 20), (-95, 76, 16)]
    for i, (a, l, w) in enumerate(blaetter):                  # Sichelfedern: breite, gebogene Klingen mit Bronzeglanz
        r = math.radians(a)
        x0, y0 = 118, 196
        x1, y1 = x0 + math.cos(r) * l, y0 + math.sin(r) * l
        bx, by = x0 + math.cos(r + 0.42) * l * 0.62, y0 + math.sin(r + 0.42) * l * 0.62
        nx, ny = -math.sin(r) * w / 2, math.cos(r) * w / 2
        s.append(f'<path d="M{x0-nx*.4:.1f},{y0-ny*.4:.1f} Q{bx-nx:.1f},{by-ny:.1f} {x1:.1f},{y1:.1f} Q{bx+nx*.6:.1f},{by+ny*.6:.1f} {x0+nx*.4:.1f},{y0+ny*.4:.1f} Z" '
                 f'fill="url(#schwanz)" stroke="#1a110a" stroke-opacity="0.55" stroke-width="1.2"/>')
        s.append(f'<path d="M{x0:.1f},{y0:.1f} Q{bx:.1f},{by:.1f} {x1:.1f},{y1:.1f}" stroke="#e0b06a" stroke-opacity="0.4" stroke-width="1.1" fill="none"/>')
        s.append(f'<path d="M{x0-nx*.2:.1f},{y0-ny*.2:.1f} Q{bx-nx*.6:.1f},{by-ny*.6:.1f} {x1:.1f},{y1:.1f}" stroke="#7fae8a" stroke-opacity="0.25" stroke-width="2.5" fill="none"/>')
    return "".join(s)

def kopf():
    s = [f'<path d="{HALS}" fill="url(#kopf)"/>', '<clipPath id="hc"><path d="%s"/></clipPath>' % HALS, '<g clip-path="url(#hc)">']
    for row in range(8):                                       # Halsfedern, lang und spitz nach unten
        for col in range(5):
            x, y = 258 + col * 14 + row * 3, 130 + row * 10
            s.append(feder(x, y, 13, 10, "#e3a050" if row < 4 else "#c97a36", rot=20, op=0.5))
    s.append('<ellipse cx="300" cy="118" rx="26" ry="20" fill="url(#glanz)"/></g>')
    s.append(f'<path d="{HALS}" fill="none" stroke="#6a3410" stroke-opacity="0.45" stroke-width="1.8"/>')
    kamm = "M282,102 C278,88 288,80 292,92 C292,76 304,72 305,88 C308,72 320,72 317,90 C324,80 334,86 326,100 C318,106 290,108 282,102 Z"
    s.append(f'<path d="{kamm}" fill="url(#kamm)" stroke="#7a0b12" stroke-opacity="0.6" stroke-width="1.2"/>')
    s.append('<path d="M322,132 C334,134 338,150 330,160 C322,166 314,156 316,146 C317,140 318,134 322,132 Z" fill="url(#kamm)" stroke="#7a0b12" stroke-opacity="0.55"/>')
    s.append('<path d="M326,112 L354,120 L327,124 Z" fill="url(#schnabel)" stroke="#9a5b0e" stroke-width="1"/>')
    s.append('<path d="M327,124 L350,122 L328,131 Z" fill="#d48a1e" stroke="#9a5b0e" stroke-width="1"/>')
    s.append('<ellipse cx="302" cy="132" rx="5" ry="6.5" fill="#f3e6dc" stroke="#c9b1a0" stroke-width="0.8"/>')
    s.append('<circle cx="313" cy="112" r="6.4" fill="#2b1608"/><circle cx="313" cy="112" r="5.2" fill="#e88a1c"/>'
             '<circle cx="314" cy="112" r="2.7" fill="#120804"/><circle cx="315.6" cy="110.2" r="1.3" fill="#fff"/>')
    return "".join(s)

def lid():
    return '<circle cx="313" cy="112" r="6.8" fill="#d99347" stroke="#8b4a1c" stroke-width="0.8"/>'

def beine():
    s = []
    for bx, by in ((188, 300), (226, 304)):
        s.append(f'<path d="M{bx-6},{by} L{bx+6},{by} L{bx+4},{by+62} L{bx-3},{by+62} Z" fill="url(#bein)" stroke="#9a6110" stroke-width="1"/>')
        for k in range(6):
            s.append(f'<path d="M{bx-4},{by+14+k*8} L{bx+4},{by+12+k*8}" stroke="#a86a14" stroke-opacity="0.55" stroke-width="1"/>')
        y = by + 62
        for dx, dy in ((26, 4), (14, 9), (-18, 5)):
            s.append(f'<path d="M{bx},{y} L{bx+dx},{y+dy}" stroke="url(#bein)" stroke-width="5" stroke-linecap="round"/>'
                     f'<path d="M{bx},{y} L{bx+dx},{y+dy}" stroke="#9a6110" stroke-opacity="0.4" stroke-width="5.5" stroke-linecap="round" fill="none"/>')
    return "".join(s)

def schatten():
    return '<ellipse cx="210" cy="372" rx="110" ry="14" fill="url(#schatten)"/>'

EBENEN = {"schatten": schatten(), "beine": beine(), "schwanz": schwanz(), "kopf": kopf(), "koerper": koerper(), "fluegel": fluegel(), "lid": lid()}
for name, body in EBENEN.items():
    open(f"{out}/{name}.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}{body}</svg>')
open(f"{out}/ganz.svg", "w").write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {VB} {VB}" width="{VB}" height="{VB}">{DEFS}' + "".join(v for k, v in EBENEN.items() if k != "lid") + "</svg>")
json.dump({"name": "Huhn", "ebenen": list(EBENEN), "groesse": VB,
           "versteckt": ["lid"], "mit_kopf": ["lid"], "drehpunkte": {"kopf": [268, 200], "fluegel": [160, 205], "schwanz": [122, 200], "lid": [313, 112], "koerper": [205, 300]},
           "anker": {"kopf": [305, 115], "auge": [313, 112], "schnabel": [345, 121], "kamm": [304, 88], "hals": [278, 160], "brust": [282, 230],
                     "bauch": [210, 268], "ruecken": [190, 150], "fluegel": [212, 222], "schwanz": [80, 130], "beine": [207, 335],
                     "fuesse": [207, 368], "kloake": [124, 262], "eierstock": [222, 214], "eileiter": [178, 246], "herz": [262, 218],
                     "magen": [236, 252], "lunge": [232, 184]}}, open(f"{out}/figur.json", "w"), ensure_ascii=False, indent=1)
print("ok")
