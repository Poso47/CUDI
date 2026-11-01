"""Reddit-Storys holen: offizielle API (mit kostenlosem Zugang), öffentliches Reddit oder das Archiv
Arctic Shift (ohne Schlüssel, Upvotes nach ca. 36 Stunden aktuell). Dazu Link-Import und eigener Text."""

from __future__ import annotations

import html
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, fields

from .. import config, net
from .moods import MOODS, seconds_per_word

log = logging.getLogger(__name__)

ARCTIC = "https://arctic-shift.photon-reddit.com/api"
ARCTIC_FIELDS = "id,title,selftext,score,num_comments,over_18,created_utc,author,subreddit"
REMOVED = {"", "[removed]", "[deleted]", "[ Removed by Reddit ]"}

# Länge -> Ziel-Sekunden je Video; der Wortbereich ergibt sich aus dem Sprechtempo der Stimmung
LENGTHS = {
    "kurz": {"label": "Kurz (bis 1 Minute)", "seconds": 60},
    "3min": {"label": "Bis 3 Minuten", "seconds": config.STORY_MAX_SECONDS},
    "teile": {"label": "Lang, in Teilen", "seconds": config.STORY_MAX_SECONDS, "parts": 6},
}
OVERHEAD_SECONDS = 9            # Titel + Abspann


def word_range(length: str, mood: str, lang: str) -> tuple[int, int]:
    """Wie viele Wörter passen? Kurz: 40–100 %, 3 Minuten: 45–100 %, Teile: 1–6 Videos."""
    spec = LENGTHS[length]
    per_video = int((spec["seconds"] - OVERHEAD_SECONDS) / seconds_per_word(mood, lang))
    if length == "teile":
        return int(per_video * 0.9), per_video * spec["parts"]
    return int(per_video * (0.4 if length == "kurz" else 0.45)), per_video


@dataclass
class Post:
    id: str
    subreddit: str
    author: str
    title: str
    text: str
    score: int = 0
    num_comments: int = 0
    over_18: bool = False
    created_utc: float = 0.0
    source: str = "reddit"            # reddit | archiv | eigener Text

    @property
    def url(self) -> str:
        return f"https://www.reddit.com/r/{self.subreddit}/comments/{self.id}/" if self.id and self.subreddit else ""

    @property
    def words(self) -> int:
        return len(self.text.split())

    def to_dict(self) -> dict:
        return {**asdict(self), "url": self.url, "words": self.words}

    @classmethod
    def from_dict(cls, data: dict) -> "Post":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


def _post(data: dict, source: str) -> Post | None:
    text = html.unescape((data.get("selftext") or "").strip())
    if text in REMOVED or data.get("removed_by_category"):
        return None
    return Post(
        id=str(data.get("id", "")), subreddit=data.get("subreddit") or "", author=data.get("author") or "",
        title=html.unescape(data.get("title") or "").strip(), text=text, score=int(data.get("score") or 0),
        num_comments=int(data.get("num_comments") or 0), over_18=bool(data.get("over_18")),
        created_utc=float(data.get("created_utc") or 0), source=source,
    )


# --------------------------------------------------------------------------- Reddit

_token = {"value": "", "expires": 0.0}
_public_blocked = False      # öffentliches Reddit hat in diesem Lauf abgelehnt (z. B. Cloud-IP) -> Archiv


def _reddit_headers() -> dict | None:
    if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET):
        return None
    if time.time() > _token["expires"] - 60:
        data = net.post("https://www.reddit.com/api/v1/access_token", data={"grant_type": "client_credentials"},
                        auth=(config.REDDIT_CLIENT_ID, config.REDDIT_CLIENT_SECRET)).json()
        _token.update(value=data["access_token"], expires=time.time() + float(data.get("expires_in", 3600)))
    return {"Authorization": f"bearer {_token['value']}"}


def _reddit(path: str, params: dict) -> dict | list:
    """Reddit mit Zugang (oauth.reddit.com) oder öffentlich (www.reddit.com/....json)."""
    global _public_blocked
    headers = _reddit_headers()
    if headers is None and _public_blocked:
        raise net.FetchError("öffentliches Reddit nicht erreichbar")
    url = ("https://oauth.reddit.com" + path) if headers else ("https://www.reddit.com" + path + ".json")
    try:
        return net.get_json(url, params={**params, "raw_json": 1}, headers=headers, cache_hours=6,
                            retries=1, max_wait=10)
    except net.FetchError:
        if headers is None:
            _public_blocked = True
        raise


def _reddit_candidates(subreddit: str, keywords: list[str]) -> list[Post]:
    if keywords:
        data = _reddit(f"/r/{subreddit}/search", {"q": " OR ".join(keywords), "restrict_sr": 1, "sort": "top",
                                                  "t": "all", "limit": 100})
    else:
        data = _reddit(f"/r/{subreddit}/top", {"t": "year", "limit": 100})
    posts = [_post(child["data"], "reddit") for child in data["data"]["children"]]
    return [p for p in posts if p]


# --------------------------------------------------------------------------- Archiv (Arctic Shift)

def _arctic_window(subreddit: str, end: float, span_hours: int) -> list[Post]:
    params = {"subreddit": subreddit, "after": int(end - span_hours * 3600), "before": int(end),
              "limit": 100, "sort": "desc", "fields": ARCTIC_FIELDS}
    try:
        data = net.get_json(f"{ARCTIC}/posts/search", params=params, cache_hours=24 * 7, retries=3, max_wait=30)
    except net.FetchError as exc:
        log.warning("Archiv für r/%s nicht erreichbar: %s", subreddit, exc)
        return []
    return [p for p in (_post(d, "archiv") for d in data.get("data") or []) if p]


def _arctic_candidates(subreddit: str, rnd: random.Random, windows: int = 6, span_hours: int = 72) -> list[Post]:
    """Zufällige Zeitfenster der letzten 12 Monate (ohne die letzten 3 Tage: Upvotes noch nicht aktuell)."""
    now = time.time()
    ends = []
    for _ in range(windows):
        end = now - rnd.uniform(3, 365) * 86400
        ends.append(end - end % 3600)                       # volle Stunden -> Cache greift wieder
    with ThreadPoolExecutor(max_workers=3) as pool:         # das Archiv verträgt ein paar Anfragen pro Sekunde
        return [p for batch in pool.map(lambda e: _arctic_window(subreddit, e, span_hours), ends) for p in batch]


# --------------------------------------------------------------------------- Suche

def relevance(post: Post, keywords: list[str]) -> int:
    title, text = post.title.lower(), post.text.lower()
    return sum(3 * title.count(k) + min(text.count(k), 5) for k in (k.lower() for k in keywords))


def find_stories(plan: dict, length: str = "3min", limit: int = 6, allow_nsfw: bool = False,
                 seed: int | None = None, lang: str = "en") -> tuple[list[Post], list[str]]:
    """Passende Storys zum Suchplan (aus moods.plan_from_description). Gibt (Storys, Hinweise) zurück."""
    lo, hi = word_range(length, plan["mood"], lang)
    keywords = plan.get("keywords", [])
    rnd = random.Random(seed if seed is not None else int(time.time() // 86400))
    notes: list[str] = []
    pool: dict[str, Post] = {}
    for sub in plan["subreddits"]:
        try:
            found = _reddit_candidates(sub, keywords)
        except (net.FetchError, KeyError, TypeError) as exc:
            log.info("Reddit für r/%s nicht verfügbar (%s) – nutze das Archiv", sub, exc)
            found = _arctic_candidates(sub, rnd)
        for p in found:
            pool.setdefault(p.id, p)
    def usable(p: Post, lo: int, hi: int) -> bool:
        return lo <= p.words <= hi and (allow_nsfw or not p.over_18) and len(p.title) >= 8

    candidates = [p for p in pool.values() if usable(p, lo, hi)]
    if not candidates and length != "teile":
        lo, hi = word_range("teile", plan["mood"], lang)
        candidates = [p for p in pool.values() if usable(p, lo, hi)]
        if candidates:
            notes.append("Keine Story in der gewünschten Länge gefunden – längere Storys werden in Teile "
                         "mit Cliffhanger geschnitten.")
    if not candidates:
        notes.append("Keine passende Story gefunden – andere Stimmung oder Beschreibung probieren.")
        return [], notes
    if keywords:
        matching = [p for p in candidates if relevance(p, keywords) > 0]
        if matching:
            candidates = matching
        else:
            notes.append(f"Keine Story mit „{', '.join(keywords)}“ gefunden – zeige die beliebtesten passenden Storys.")
    candidates.sort(key=lambda p: (relevance(p, keywords) > 0, p.score), reverse=True)
    if any(p.source == "archiv" for p in candidates[:limit]):
        notes.append("Quelle: Reddit-Archiv (Arctic Shift). Mit Reddit-Zugang (CUDI_REDDIT_CLIENT_ID/SECRET) "
                     "werden die Upvotes live abgefragt.")
    return candidates[:limit], notes


# --------------------------------------------------------------------------- einzelne Story

def post_id(ref: str) -> str:
    """ID aus Link (reddit.com/r/x/comments/<id>/…, redd.it/<id>) oder der ID selbst."""
    ref = ref.strip()
    match = re.search(r"/comments/([a-z0-9]{4,10})", ref) or re.search(r"redd\.it/([a-z0-9]{4,10})", ref)
    if match:
        return match.group(1)
    if re.fullmatch(r"(t3_)?[a-z0-9]{4,10}", ref):
        return ref.removeprefix("t3_")
    raise ValueError("Das sieht nicht nach einem Reddit-Link aus.")


def fetch_post(ref: str) -> Post:
    pid = post_id(ref)
    try:
        data = _reddit(f"/comments/{pid}", {"limit": 1})
        post = _post(data[0]["data"]["children"][0]["data"], "reddit")
    except (net.FetchError, KeyError, IndexError, TypeError):
        data = net.get_json(f"{ARCTIC}/posts/ids", params={"ids": pid, "fields": ARCTIC_FIELDS}, cache_hours=24,
                            retries=3, max_wait=30)
        items = data.get("data") or []
        post = _post(items[0], "archiv") if items else None
    if post is None:
        raise ValueError("Die Story wurde gelöscht oder hat keinen Text (nur Bild/Link).")
    return post


def post_from_text(title: str, text: str, author: str = "", subreddit: str = "") -> Post:
    """Eigener oder kopierter Text – z. B. wenn Reddit nicht erreichbar ist."""
    if len(text.split()) < 40:
        raise ValueError("Der Text ist zu kurz für ein Story-Video (mindestens etwa 40 Wörter).")
    return Post(id="", subreddit=subreddit.removeprefix("r/"), author=author.removeprefix("u/"),
                title=title.strip() or text.split(".")[0][:120], text=text.strip(), source="eigener Text")


def rights_note(post: Post) -> list[str]:
    """Hinweise zu Urheberrecht und Quellenangabe für den Prüfbericht."""
    notes = []
    who = f"u/{post.author}" if post.author else "dem Autor"
    if post.subreddit.lower() == "nosleep":
        notes.append(f"r/nosleep: Vertonungen nur mit Erlaubnis von {who} – vor dem Hochladen anfragen "
                     "(Nachricht auf Reddit).")
    if post.author:
        notes.append(f"Die Story stammt von {who} auf r/{post.subreddit} – Name und Link stehen im Video und "
                     "in der Beschreibung. Für monetarisierte Videos am besten die Erlaubnis einholen.")
    if post.over_18:
        notes.append("Als NSFW markiert – für TikTok/YouTube Shorts meist ungeeignet.")
    return notes


def mood_subreddits(mood: str) -> list[str]:
    return list(MOODS[mood]["subreddits"])
