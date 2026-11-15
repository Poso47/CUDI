# Fremde Bibliotheken der 3D-Bühne (alle kostenlos, MIT-Lizenz)

| Datei | Projekt | Version | Wofür |
|---|---|---|---|
| `three.min.js` | https://github.com/mrdoob/three.js | r128 | 3D-Darstellung |
| `camera-controls.js` | https://github.com/yomotsu/camera-controls | 3.1.2 | gedämpfte Kamerafahrten und Zooms (`regie` in `szene3d.html`) |
| `GLTFLoader.js` | https://github.com/mrdoob/three.js (examples/js/loaders) | r128 | lädt fertige freie 3D-Modelle (GLB) des Modell-Scouts |
| `tween.umd.js` | https://github.com/tweenjs/tween.js | 25.0.0 | Bewegungskurven (Easing) für Ein-/Ausflug der Kamera |

`camera-controls.js` ist die Original-Datei `dist/camera-controls.cjs`, nur in eine Funktion verpackt, die `window.CameraControls` setzt
(Chromium lädt Module nicht von `file://`). Lizenztext: `LICENSE-camera-controls`.
