"""CUDI Video als Hugging Face Space bereitstellen (wird vom Workflow „CUDI Cloud-App“ aufgerufen).

Legt den Space bei Bedarf an, setzt Zugangscode und optionale Schlüssel als Secrets und lädt die App hoch.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

from huggingface_hub import HfApi

SPACE_README = """---
title: CUDI Video
emoji: 🎬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

CUDI Video – Ranking-Faktenvideos und Reddit-Storys für TikTok & YouTube Shorts.
"""
OPTIONAL_SECRETS = (
    "CUDI_PEXELS_API_KEY", "CUDI_PIXABAY_API_KEY", "CUDI_LLM_BASE_URL", "CUDI_LLM_API_KEY", "CUDI_LLM_MODEL",
    "CUDI_DEEPL_API_KEY", "CUDI_REDDIT_CLIENT_ID", "CUDI_REDDIT_CLIENT_SECRET", "CUDI_POLLINATIONS_TOKEN",
    "CUDI_CHANNEL", "CUDI_FACTCHECK_API_KEY",
)


def main() -> int:
    token = os.environ.get("HF_TOKEN", "")
    access_code = os.environ.get("CUDI_VIDEO_TOKEN", "")
    if not token:
        if os.environ.get("GITHUB_EVENT_NAME") == "push":     # automatischer Lauf: Hugging Face ist optional
            print("::notice::Hugging Face ist nicht eingerichtet (Secret HF_TOKEN fehlt) – Bereitstellung übersprungen.")
            return 0
        print("::error::Secret HF_TOKEN fehlt (Hugging Face → Settings → Access Tokens → Write).")
        return 1
    if not access_code:
        print("::error::Secret CUDI_VIDEO_TOKEN (dein Zugangscode für die App) fehlt – ohne ihn wäre die App offen.")
        return 1
    api = HfApi(token=token)
    user = api.whoami()["name"]
    name = os.environ.get("HF_SPACE_NAME") or "cudi-video"
    private = os.environ.get("HF_SPACE_PRIVATE", "true").lower() != "false"
    repo_id = f"{user}/{name}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", private=private, exist_ok=True)
    api.add_space_secret(repo_id, "CUDI_VIDEO_TOKEN", access_code)
    for secret in OPTIONAL_SECRETS:
        if os.environ.get(secret):
            api.add_space_secret(repo_id, secret, os.environ[secret])
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        for item in ("cudi_video", "presets", "video_assets"):
            if Path(item).is_dir():
                shutil.copytree(item, target / item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for item in ("Dockerfile", ".dockerignore"):
            shutil.copy(item, target / item)
        (target / "README.md").write_text(SPACE_README, "utf-8")
        api.upload_folder(folder_path=str(target), repo_id=repo_id, repo_type="space",
                          commit_message="CUDI Video aktualisiert", delete_patterns=["cudi_video/**", "presets/**"])
    host = f"{user}-{name}".lower().replace("_", "-").replace(".", "-")
    print(f"::notice::CUDI läuft gleich unter https://{host}.hf.space "
          f"(Space: https://huggingface.co/spaces/{repo_id}{', privat – am Handy bei Hugging Face anmelden' if private else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
