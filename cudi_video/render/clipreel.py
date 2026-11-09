"""Mehrere kurze Videoclips hintereinander geschnitten – als bewegte Bildkarte eines Ranking-Platzes.

Ein einziger ffmpeg-Aufruf schneidet aus jedem Clip ein Stück (nicht den oft ruhigen Anfang), bringt alles
auf Kartengröße und liefert die Bilder als Rohdaten. Die Szene liest sie der Reihe nach mit; fehlt etwas,
bleibt das letzte Bild stehen – und ohne ein einziges Bild fällt die Karte aufs Foto zurück.
"""

from __future__ import annotations

import subprocess

from PIL import Image


class ClipReel:
    def __init__(self, clips: list[dict], size: tuple[int, int], duration: float, fps: int):
        self.size, self.fps = size, fps
        self.frame_bytes = size[0] * size[1] * 3
        self.pos, self.last = -1, None
        self.cuts: list[tuple[float, str]] = []          # (Startzeit, Bildnachweis) je Ausschnitt
        n = max(1, len(clips))
        seg = duration / n + 0.2
        cmd, filters, t = ["ffmpeg", "-loglevel", "error"], [], 0.0
        w, h = size
        for i, clip in enumerate(clips):
            if clip.get("kind") == "image":
                # Standbild: etwas größer skalieren und langsam seitlich schwenken (Ken Burns), abwechselnd links/rechts
                take = seg
                cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{take:.2f}", "-i", clip["path"]]
                bw, bh = int(w * 1.12) // 2 * 2, int(h * 1.12) // 2 * 2
                x = f"(iw-ow)*t/{take:.2f}" if i % 2 == 0 else f"(iw-ow)*(1-t/{take:.2f})"
                y = f"(ih-oh)*(0.65-0.3*t/{take:.2f})" if i % 3 else f"(ih-oh)*(0.35+0.3*t/{take:.2f})"    # zusätzlich leicht auf/ab
                filters.append(f"[{i}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                               f"crop={w}:{h}:x='{x}':y='{y}',fps={fps},setsar=1,format=rgb24,"
                               f"setpts=PTS-STARTPTS[v{i}]")
                self.cuts.append((t, clip.get("credit", "")))
                t += take
                continue
            length = float(clip.get("duration") or 0) or seg
            start = max(0.0, min(length * 0.2, length - seg))
            take = min(seg, max(1.0, length - start))
            cmd += ["-ss", f"{start:.2f}", "-t", f"{take:.2f}", "-i", clip["path"]]
            filters.append(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
                           f"crop={w}:{h},fps={fps},setsar=1,format=rgb24,setpts=PTS-STARTPTS[v{i}]")
            self.cuts.append((t, clip.get("credit", "")))
            t += take
        graph = ";".join(filters) + ";" + "".join(f"[v{i}]" for i in range(len(clips))) + \
            f"concat=n={len(clips)}:v=1:a=0[out]"
        cmd += ["-filter_complex", graph, "-map", "[out]", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def frame_at(self, t: float) -> Image.Image | None:
        want = int(t * self.fps)
        while self.pos < want and self.proc is not None:
            data = self.proc.stdout.read(self.frame_bytes)
            if len(data) < self.frame_bytes:
                self.close()
                break
            self.last = Image.frombytes("RGB", self.size, data)
            self.pos += 1
        return self.last

    def credit_at(self, t: float) -> str:
        current = ""
        for start, credit in self.cuts:
            if t >= start:
                current = credit
        return current

    def close(self) -> None:
        if self.proc is not None:
            try:
                self.proc.stdout.close()
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:
                pass
            self.proc = None

    def __del__(self):
        self.close()
