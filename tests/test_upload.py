"""Upload zu YouTube/TikTok – ohne Netz (HTTP per Monkeypatch), mit Prüfung, dass keine Geheimnisse auslaufen."""

import json
from argparse import Namespace

import pytest

from cudi_video import upload
from cudi_video.upload import cli, tiktok, youtube

SECRET = "geheim-zugang-4711"


class Resp:
    def __init__(self, status=200, body=None, headers=None):
        self.status_code, self.headers, self._body = status, headers or {}, body if body is not None else {}

    def json(self):
        return self._body

    @property
    def text(self):
        return json.dumps(self._body)


class Net:
    """Drehbuch: Antworten der Reihe nach (Funktion oder Resp); merkt sich alle Aufrufe."""

    def __init__(self, monkeypatch, script):
        self.script, self.calls = list(script), []
        monkeypatch.setattr(upload, "http", self)
        monkeypatch.setattr(upload, "PAUSE", 0)

    def __call__(self, method, url, **kw):
        self.calls.append((method, url, kw))
        item = self.script.pop(0)
        return item(method, url, **kw) if callable(item) else item


@pytest.fixture
def env(monkeypatch, tmp_path):
    for k in upload.SECRET_VARS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("CUDI_YT_CLIENT_ID", "client-id-" + SECRET)
    monkeypatch.setenv("CUDI_YT_CLIENT_SECRET", "client-secret-" + SECRET)
    monkeypatch.setenv("CUDI_YT_REFRESH_TOKEN", "refresh-" + SECRET)
    monkeypatch.setenv("CUDI_TIKTOK_ACCESS_TOKEN", "tt-access-" + SECRET)
    monkeypatch.setattr(youtube.config, "OUTPUT_DIR", tmp_path / "out")


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "top5_de.mp4"
    path.write_bytes(b"x" * 1000)
    (tmp_path / "top5_de_beschreibung.txt").write_text(
        "Die 5 höchsten Berge 🏆\n\n5. Berg\n4. Gipfel\n\n#shorts #fakten #berge\n", "utf-8")
    (tmp_path / "top5_de_tiktok.txt").write_text("Berge! #berge\n", "utf-8")
    return path


def test_material_reads_texts_next_to_video(video):
    m = upload.materials(str(video))[0]
    assert m.title == "Die 5 höchsten Berge 🏆" and m.tags == ["shorts", "fakten", "berge"]
    assert m.caption == "Berge! #berge" and m.lang == "de"
    with pytest.raises(upload.UploadError):
        upload.materials(str(video.with_name("fehlt.mp4")))


def test_snippet_shorts_hint_visibility_and_limits(video):
    m = upload.materials(str(video))[0]
    body = youtube.snippet(m)
    assert body["status"]["privacyStatus"] == "private"                         # Standard: privat
    assert "#shorts" in body["snippet"]["description"]
    long = upload.Material(video, "T" * 300, "Text", [f"tag{i}" * 3 for i in range(200)])
    s = youtube.snippet(long, "oeffentlich")
    assert len(s["snippet"]["title"]) == 100 and s["status"]["privacyStatus"] == "public"
    assert s["snippet"]["description"].endswith("#shorts") and sum(len(t) + 3 for t in s["snippet"]["tags"]) <= 500
    assert youtube.snippet(m, "ungelistet")["status"]["privacyStatus"] == "unlisted"
    with pytest.raises(upload.UploadError):
        youtube.snippet(m, "geheim")


def test_youtube_init_chunking_and_resume_after_error(env, video, monkeypatch):
    monkeypatch.setattr(youtube, "CHUNK", 400)                                   # 1000 Bytes = 3 Stücke
    seen = []

    def chunk(status, headers=None, body=None):
        return lambda m, u, **kw: seen.append((kw["headers"]["Content-Range"], len(kw["data"]))) or Resp(status, body, headers)

    net = Net(monkeypatch, [
        Resp(200, {"access_token": "at-" + SECRET}),                              # Token
        Resp(200, headers={"Location": "https://upload.example/session"}),        # Start
        chunk(308, {"Range": "bytes=0-399"}),
        chunk(503),                                                              # Störung beim 2. Stück
        Resp(308, headers={"Range": "bytes=0-399"}),                              # Status: 400 Bytes angekommen
        chunk(308, {"Range": "bytes=0-799"}),
        chunk(201, body={"id": "abc123"}),
    ])
    result = youtube.upload(upload.materials(str(video))[0], "privat")
    assert result["id"] == "abc123" and result["url"].endswith("abc123")
    assert seen == [("bytes 0-399/1000", 400), ("bytes 400-799/1000", 400), ("bytes 400-799/1000", 400),
                    ("bytes 800-999/1000", 200)]
    method, url, kw = net.calls[1]
    assert kw["params"] == {"uploadType": "resumable", "part": "snippet,status"}
    assert kw["headers"]["X-Upload-Content-Length"] == "1000" and kw["headers"]["Authorization"] == "Bearer at-" + SECRET
    sent = json.loads(kw["data"].decode("utf-8"))
    assert sent["status"]["privacyStatus"] == "private" and "#shorts" in sent["snippet"]["description"]
    assert net.calls[0][2]["data"]["grant_type"] == "refresh_token"


def test_youtube_gives_up_after_retries_without_leaking_secrets(env, video, monkeypatch):
    Net(monkeypatch, [Resp(200, {"access_token": "at-" + SECRET}), Resp(200, headers={"Location": "https://u/x"})]
        + [Resp(500, {"error": "kaputt at-" + SECRET})] * 4 + [Resp(308, headers={}), Resp(500)] * 0
        + [Resp(500, {"error": "kaputt at-" + SECRET})] * 8)
    with pytest.raises(upload.UploadError) as err:
        youtube.upload(upload.materials(str(video))[0])
    assert SECRET not in str(err.value) and "abgebrochen" in str(err.value)


def test_youtube_start_error_and_missing_credentials(env, video, monkeypatch):
    Net(monkeypatch, [Resp(200, {"access_token": "t"}), Resp(403, {"error": "quota"})])
    with pytest.raises(upload.UploadError, match="403"):
        youtube.upload(upload.materials(str(video))[0])
    monkeypatch.delenv("CUDI_YT_CLIENT_SECRET")
    with pytest.raises(upload.UploadError, match="CUDI_YT_CLIENT_SECRET") as err:
        youtube.access_token()
    assert SECRET not in str(err.value)
    Net(monkeypatch, [Resp(400, {"error": "invalid_grant refresh-" + SECRET})])
    monkeypatch.setenv("CUDI_YT_CLIENT_SECRET", "x" * 8)
    with pytest.raises(upload.UploadError) as err:
        youtube.access_token()
    assert SECRET not in str(err.value)


def test_tiktok_chunking_rules():
    assert tiktok.chunking(3_000_000) == (3_000_000, 1)
    assert tiktok.chunking(64 * 1024 * 1024) == (64 * 1024 * 1024, 1)
    size = 100 * 1024 * 1024
    chunk, count = tiktok.chunking(size)
    assert (chunk, count) == (32 * 1024 * 1024, 3) and size - (count - 1) * chunk < 64 * 1024 * 1024 + 1


def test_tiktok_inbox_upload_single_and_chunked(env, video, monkeypatch):
    net = Net(monkeypatch, [Resp(200, {"data": {"upload_url": "https://tt.example/up", "publish_id": "p1"}}),
                            Resp(201), Resp(200, {"data": {"status": "SEND_TO_USER_INBOX"}})])
    result = cli.run_one(upload.materials(str(video))[0], "tiktok", "privat")
    assert result["publish_id"] == "p1" and result["status"] == "SEND_TO_USER_INBOX"
    init = net.calls[0]
    assert init[1] == tiktok.INBOX_INIT and init[2]["json"] == {
        "source_info": {"source": "FILE_UPLOAD", "video_size": 1000, "chunk_size": 1000, "total_chunk_count": 1}}
    assert init[2]["headers"]["Authorization"] == "Bearer tt-access-" + SECRET
    assert net.calls[1][2]["headers"]["Content-Range"] == "bytes 0-999/1000"
    # mehrere Stücke: letztes nimmt den Rest auf
    monkeypatch.setattr(tiktok, "MAX_SINGLE", 400)
    monkeypatch.setattr(tiktok, "CHUNK", 300)
    ranges = []
    Net(monkeypatch, [Resp(200, {"data": {"upload_url": "u", "publish_id": "p2"}})]
        + [lambda m, u, **kw: ranges.append(kw["headers"]["Content-Range"]) or Resp(206)] * 2
        + [lambda m, u, **kw: ranges.append(kw["headers"]["Content-Range"]) or Resp(201)])
    tiktok.upload(upload.materials(str(video))[0])
    assert ranges == ["bytes 0-299/1000", "bytes 300-599/1000", "bytes 600-999/1000"]


def test_tiktok_direct_post_body_and_retry(env, video, monkeypatch):
    net = Net(monkeypatch, [Resp(500), Resp(200, {"data": {"upload_url": "u", "publish_id": "p"}}), Resp(201)])
    tiktok.upload(upload.materials(str(video))[0], "direkt", "privat")
    body = net.calls[1][2]["json"]
    assert net.calls[1][1] == tiktok.DIRECT_INIT and body["post_info"]["privacy_level"] == "SELF_ONLY"
    assert body["post_info"]["title"] == "Berge! #berge"
    with pytest.raises(upload.UploadError):
        tiktok.upload(upload.materials(str(video))[0], "egal")


def test_tiktok_refreshes_expired_token_once(env, video, monkeypatch):
    monkeypatch.setenv("CUDI_TIKTOK_CLIENT_KEY", "ck-" + SECRET)
    monkeypatch.setenv("CUDI_TIKTOK_CLIENT_SECRET", "cs-" + SECRET)
    monkeypatch.setenv("CUDI_TIKTOK_REFRESH_TOKEN", "rt-" + SECRET)
    net = Net(monkeypatch, [Resp(401, {"error": "expired"}), Resp(200, {"access_token": "neu-" + SECRET}),
                            Resp(200, {"data": {"upload_url": "u", "publish_id": "p"}}), Resp(201)])
    tiktok.upload(upload.materials(str(video))[0])
    assert net.calls[1][1] == tiktok.TOKEN_URL and net.calls[2][2]["headers"]["Authorization"].endswith("neu-" + SECRET)


def test_tiktok_without_any_token_names_what_is_missing(env, video, monkeypatch):
    monkeypatch.delenv("CUDI_TIKTOK_ACCESS_TOKEN")
    with pytest.raises(upload.UploadError, match="CUDI_TIKTOK_CLIENT_KEY"):
        tiktok.upload(upload.materials(str(video))[0])


def test_probe_makes_no_requests_and_prints_no_secrets(env, video, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError("Trockenlauf darf kein Netz benutzen")

    monkeypatch.setattr(upload, "http", boom)
    args = Namespace(quelle=str(video), ziel="beide", sichtbarkeit="privat", sprache="", tiktok_modus="inbox", probe=True)
    assert cli.hochladen(args) == 0
    out = capsys.readouterr().out
    assert "Probe" in out and "private" in out and "INBOX" not in out and "inbox" in out and "gesetzt" in out
    assert SECRET not in out and "#shorts" in out


def test_cli_prints_no_secrets_on_failure(env, video, monkeypatch, capsys):
    Net(monkeypatch, [Resp(401, {"error": "bad client-secret-" + SECRET})])
    args = Namespace(quelle=str(video), ziel="youtube", sichtbarkeit="privat", sprache="", tiktok_modus="inbox", probe=False)
    assert cli.hochladen(args) == 1
    assert SECRET not in capsys.readouterr().out
    assert SECRET not in upload.redact(f"Authorization: Bearer {SECRET}")
    assert "***" in upload.redact("access_token=abc123xyz")


def test_order_field_and_upload_never_breaks_order(env, video, monkeypatch):
    from cudi_video import job

    assert job._upload_wish(None) is None and job._upload_wish("") is None
    assert job._upload_wish("tiktok") == {"ziel": "tiktok", "sichtbarkeit": "privat"}
    assert job._upload_wish({"ziel": "beide", "sichtbarkeit": "öffentlich"})["sichtbarkeit"] == "oeffentlich"
    with pytest.raises(job.OrderError):
        job._upload_wish("facebook")
    Net(monkeypatch, [Resp(500, {"error": "x"})] * 20)
    result = cli.upload_order({"ziel": "youtube", "sichtbarkeit": "privat"},
                              {"videos": [{"video": str(video), "key": "de"}]})
    assert result[0]["ok"] is False and SECRET not in json.dumps(result)


def test_tiktok_login_code_und_tausch(monkeypatch):
    from cudi_video.upload import UploadError, tiktok

    monkeypatch.setenv("CUDI_TIKTOK_CLIENT_KEY", "k1")
    monkeypatch.setenv("CUDI_TIKTOK_CLIENT_SECRET", "s1")
    monkeypatch.delenv("CUDI_TIKTOK_REDIRECT_URI", raising=False)
    url = tiktok.authorize_url("st")
    assert "client_key=k1" in url and "scope=video.upload" in url and "poso47.github.io%2FCUDI%2Ftiktok%2F" in url
    assert tiktok.code_from("https://poso47.github.io/CUDI/tiktok/?code=AB%2A1&state=st", "st") == "AB*1"
    assert tiktok.code_from("nurCode") == "nurCode"
    for bad in ("https://x/?error=access_denied", "https://x/?code=a&state=zz", "zwei worte", ""):
        with pytest.raises(UploadError):
            tiktok.code_from(bad, "st")

    class Resp:
        status_code = 200

        def json(self):
            return {"refresh_token": "rt"}

    seen = {}
    monkeypatch.setattr(tiktok, "http", lambda *a, **k: (seen.update(k), Resp())[1])
    assert tiktok.exchange_code("c") == "rt"
    assert seen["data"]["grant_type"] == "authorization_code" and seen["data"]["redirect_uri"] == tiktok.DEFAULT_REDIRECT
