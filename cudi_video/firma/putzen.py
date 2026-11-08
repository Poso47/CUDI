"""Putzmann: räumt GitHub und firma_daten/ auf -> firma_daten/putzen.json (Bericht, was wann entfernt wurde).

Entfernt werden nur: Workflow-Artefakte > 7 Tage, abgeschlossene Workflow-Läufe > 30 Tage, ausgedünnte Altdaten in
firma_daten/. Geschlossene, erledigte Notbetrieb-Issues (Marker-Label cudi-auftrag) > 14 Tage werden gesperrt.
NIE: Code, Releases, offene Issues, Issues mit Fehlern (nicht „completed“ geschlossen)."""

from __future__ import annotations

import os
import time
from datetime import timedelta

from . import common
from .common import fetch, iso, now

API = "https://api.github.com"
ARTIFACT_DAYS, RUN_DAYS, ISSUE_DAYS, TREND_DAYS, IDEA_DAYS = 7, 30, 14, 2, 7
ISSUE_MARKER = "cudi-auftrag"
MAX_DELETES = 300                       # je Lauf, damit der Job kurz bleibt (Rest folgt am nächsten Tag)
LOG_KEEP = 60


class GitHub:
    def __init__(self, repo: str, token: str, dry: bool = False):
        self.repo, self.dry = repo, dry
        self.headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    def pages(self, path: str, key: str | None, params: dict | None = None, limit: int = 5):
        for page in range(1, limit + 1):
            data = fetch(f"{API}/repos/{self.repo}{path}", params={"per_page": 100, "page": page, **(params or {})},
                         headers=self.headers, timeout=20).json()
            items = data.get(key, []) if key else data
            yield from items
            if len(items) < 100:
                return

    def delete(self, path: str) -> None:
        if not self.dry:
            fetch(f"{API}/repos/{self.repo}{path}", method="DELETE", headers=self.headers, timeout=20, retries=1)

    def lock(self, number: int) -> None:
        if not self.dry:
            fetch(f"{API}/repos/{self.repo}/issues/{number}/lock", method="PUT", headers=self.headers, timeout=20,
                  json={"lock_reason": "resolved"}, retries=1)


def clean_artifacts(gh: GitHub) -> int:
    limit, n = now() - timedelta(days=ARTIFACT_DAYS), 0
    for art in list(gh.pages("/actions/artifacts", "artifacts")):
        created = common.parse_time(art.get("created_at", ""))
        if created and created < limit and n < MAX_DELETES:
            gh.delete(f"/actions/artifacts/{art['id']}")
            n += 1
    return n


def clean_runs(gh: GitHub) -> int:
    day = (now() - timedelta(days=RUN_DAYS)).strftime("%Y-%m-%d")
    n = 0
    for run in list(gh.pages("/actions/runs", "workflow_runs", {"status": "completed", "created": f"<{day}"})):
        if run.get("status") == "completed" and n < MAX_DELETES:        # nie laufende Läufe
            gh.delete(f"/actions/runs/{run['id']}")
            n += 1
    return n


def lock_issues(gh: GitHub) -> int:
    limit, n = now() - timedelta(days=ISSUE_DAYS), 0
    for issue in list(gh.pages("/issues", None, {"state": "closed", "labels": ISSUE_MARKER})):
        closed = common.parse_time(issue.get("closed_at") or "")
        done = issue.get("state") == "closed" and issue.get("state_reason") == "completed"
        if ("pull_request" not in issue and done and not issue.get("locked") and closed and closed < limit
                and ISSUE_MARKER in [lb.get("name") for lb in issue.get("labels", [])]):
            gh.lock(issue["number"])
            n += 1
    return n


def thin_data(dry: bool = False) -> dict:
    """firma_daten/ ausdünnen: alte Ideen und lange nicht gesehene Trends."""
    removed = {}
    ideen = common.read_json("ideen.json")
    if ideen and ideen.get("ideen"):
        kept = common.thin_by_age(ideen["ideen"], "erstellt", IDEA_DAYS)
        if len(kept) != len(ideen["ideen"]):
            removed["ideen"] = len(ideen["ideen"]) - len(kept)
            if not dry:
                common.write_json("ideen.json", {**ideen, "ideen": kept, "anzahl": len(kept)})
    trends = common.read_json("trends.json")
    if trends and trends.get("themen"):
        kept = common.thin_by_age(trends["themen"], "zuletzt", TREND_DAYS)
        if len(kept) != len(trends["themen"]):
            removed["trends"] = len(trends["themen"]) - len(kept)
            if not dry:
                common.write_json("trends.json", {**trends, "themen": kept, "anzahl": len(kept)})
    return removed


def run(dry: bool | None = None) -> dict:
    started = time.monotonic()
    dry = bool(os.environ.get("CUDI_PUTZEN_TROCKEN")) if dry is None else dry
    notes: list[str] = []
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    done = {"artefakte": 0, "laeufe": 0, "issues_gesperrt": 0}
    if repo and token:
        gh = GitHub(repo, token, dry)
        for key, name, func in (("artefakte", "Artefakte", clean_artifacts), ("laeufe", "Workflow-Läufe", clean_runs),
                                ("issues_gesperrt", "Notbetrieb-Issues", lock_issues)):
            try:
                done[key] = func(gh)
            except Exception as exc:                      # noqa: BLE001 – ein Bereich fällt aus, der Rest läuft weiter
                notes.append(f"{name}: nicht möglich ({common.short_error(exc)})")
    else:
        notes.append("GITHUB_TOKEN/GITHUB_REPOSITORY fehlen – nur firma_daten/ wird ausgedünnt")
    return finish(started, done, notes, dry)


def finish(started: float, done: dict, notes: list[str], dry: bool) -> dict:
    done["daten"] = thin_data(dry)
    report = common.read_json("putzen.json", {}) or {}
    log = report.get("protokoll", [])
    total = sum(v for k, v in done.items() if k != "daten") + sum(done["daten"].values())
    if total:
        log.insert(0, {"zeit": iso(), "entfernt": {k: v for k, v in done.items() if v}, "trocken": dry})
    data = {"erzeugt": iso(), "regeln": {"artefakte_tage": ARTIFACT_DAYS, "laeufe_tage": RUN_DAYS,
                                         "issues_tage": ISSUE_DAYS, "ideen_tage": IDEA_DAYS},
            "letzter_lauf": {"zeit": iso(), "entfernt": done, "hinweise": notes[:10]},
            "protokoll": log[:LOG_KEEP]}
    changed = common.write_json("putzen.json", data)
    common.record_status("putzen", started, True, f"{total} entfernt" + (" (Probelauf)" if dry else "")
                         + ("" if changed else " (unverändert)"), notes)
    return data
