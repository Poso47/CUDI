"""Minimaler Markdown-zu-HTML-Wandler für den Prüfbericht (Überschriften, Listen, Tabellen, Links)."""

from __future__ import annotations

import html
import re


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', text)
    return text


def to_html(markdown: str) -> str:
    out: list[str] = []
    in_list = False
    table: list[list[str]] = []

    def flush_table():
        nonlocal table
        if not table:
            return
        head, *rows = table
        out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
        for row in rows:
            out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>")
        out.append("</tbody></table>")
        table = []

    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                table.append(cells)
            continue
        flush_table()
        if stripped.startswith("- "):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,3})\s+(.*)", stripped)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
        elif stripped:
            out.append(f"<p>{_inline(stripped)}</p>")
    flush_table()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


PAGE = """<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Prüfbericht</title>
<style>
body{{margin:0;background:#090c1e;color:#f1f5ff;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
main{{max-width:820px;margin:0 auto;padding:18px 16px 60px}}
h1{{font-size:22px}} h2{{font-size:18px;margin-top:28px;color:#22d3ee}} a{{color:#a5b4fc}}
table{{width:100%;border-collapse:collapse;font-size:13px;display:block;overflow-x:auto}}
th,td{{border-bottom:1px solid #2a3060;padding:6px 8px;text-align:left;white-space:nowrap}}
li{{margin:4px 0}} p strong{{color:#fbbf24}}
</style></head><body><main>{body}</main></body></html>"""


def page(markdown: str) -> str:
    return PAGE.format(body=to_html(markdown))
