#!/usr/bin/env python3
"""Render the Updates blog: sim/site/blog/*.md (YAML-ish front matter + markdown) → static/blog/<slug>.html and
static/blog/index.html, in the site's shell. Also writes static/blog/entries.json for the API.

  python3 sim/site/blog_charts.py && python3 sim/site/build_blog.py     # run before `railway up`; entries sort by date (newest first), then title
Front matter keys: title, date (YYYY-MM-DD), arms (YAML list or comma string), summary.
"""
import html, json, re
from pathlib import Path

SITE = Path(__file__).resolve().parent
SRC = SITE / "blog"; OUT = SITE / "static" / "blog"; OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://sim-review-production.up.railway.app"
HEAD = """<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Troubled Dreams updates</title><meta name="description" content="{desc}">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/static/style.css"><link rel="stylesheet" href="/static/presentation.css">
<style>
.blog{{max-width:var(--measure,760px);margin:0 auto;padding:24px 16px 64px;font-family:"Source Serif 4",Georgia,serif;line-height:1.55}}
.blog h1{{font-size:1.8rem;margin:.2em 0 .3em}} .blog h2{{font-size:1.25rem;margin:1.6em 0 .5em;font-family:"IBM Plex Sans",sans-serif}} .blog h3{{font-size:1.05rem;margin:1.3em 0 .4em;font-family:"IBM Plex Sans",sans-serif}}
.blog .meta{{font-family:"IBM Plex Sans",sans-serif;color:var(--muted,#667);font-size:.9rem;margin-bottom:1.2em}}
.blog blockquote{{margin:.8em 0 .3em;padding:.6em 1em;border-left:3px solid var(--s1,#205bd8);background:var(--card,#f6f8fb);white-space:pre-wrap;font-size:.95rem}}
.blog blockquote p{{margin:0}} .blog p>em:only-child{{display:block;font-family:"IBM Plex Sans",sans-serif;font-size:.85rem;color:var(--muted,#667);margin:0 0 1.2em}}
.blog table{{border-collapse:collapse;font-family:"IBM Plex Sans",sans-serif;font-size:.88rem;margin:1em 0;width:100%;display:block;overflow-x:auto}} .blog th,.blog td{{border-bottom:1px solid #dde3ea;padding:5px 8px;text-align:left;vertical-align:top}} .blog th{{font-weight:600}}
.blog img{{display:block;height:auto;width:min(100vw - 32px,1180px);margin:1.2em 0 .4em calc((100% - min(100vw - 32px,1180px))/2);border:1px solid #dde3ea;border-radius:4px;background:#fff}}
.blog img{{max-width:100%;height:auto;display:block;margin:.6em 0 .2em;border:1px solid #e5e7eb;border-radius:4px}} .blog code{{font-family:"IBM Plex Mono",monospace;font-size:.88em}} .blog .entries li{{margin:.7em 0}} .blog .entries .d{{color:var(--muted,#667);font-family:"IBM Plex Sans",sans-serif;font-size:.85rem;margin-right:.6em}}
.blog nav.crumbs{{font-family:"IBM Plex Sans",sans-serif;font-size:.9rem;margin-bottom:1.4em}} .blog nav.crumbs a{{margin-right:1em}}
</style></head><body><header class="top"><h1>Troubled Dreams / Updates</h1><span class="sub">research notes as new models are collected</span></header><main class="blog">
<nav class="crumbs"><a href="/">← The study</a><a href="/blog">All updates</a><a href="/#explorer">Read samples</a><a href="/agents.md">API guide</a></nav>
"""
FOOT = "</main></body></html>\n"


def front_matter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m: return {}, text
    meta = {}; key = None
    for line in m.group(1).splitlines():
        if line.lstrip().startswith("- ") and key:   # YAML block list under the previous key
            meta[key] = (meta[key] if isinstance(meta[key], list) else []) + [line.lstrip()[2:].strip().strip("'\"")]; continue
        if ":" not in line: continue
        k, v = line.split(":", 1); v = v.strip(); key = k.strip()
        if v.startswith("[") and v.endswith("]"): v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else: v = v.strip("'\"")
        meta[key] = v
    return meta, text[m.end():]


def render(md):
    try:
        import markdown
        return markdown.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    except ImportError:
        import subprocess
        return subprocess.run(["pandoc", "-f", "gfm", "-t", "html"], input=md, capture_output=True, text=True, check=True).stdout


def main():
    entries = []
    for p in sorted(SRC.glob("*.md")):
        meta, body = front_matter(p.read_text())
        slug = p.stem; title = meta.get("title") or slug; date = meta.get("date", "")
        arms = meta.get("arms") or []; arms = arms if isinstance(arms, list) else [a.strip() for a in str(arms).split(",") if a.strip()]
        body_html = render(body)
        body_html = re.sub(r"^<h1>.*?</h1>\n?", "", body_html, count=1, flags=re.S)  # the shell prints the title
        page = HEAD.format(title=html.escape(title), desc=html.escape(meta.get("summary", ""))) + f"<h1>{html.escape(title)}</h1><p class=\"meta\">{html.escape(date)}" + (f" · arms: {', '.join(f'<code>{html.escape(a)}</code>' for a in arms)}" if arms else "") + f" · <a href=\"/blog/{slug}.md\">markdown</a></p>\n" + body_html + FOOT
        (OUT / f"{slug}.html").write_text(page)
        (OUT / f"{slug}.md").write_text(p.read_text())
        entries.append({"slug": slug, "title": title, "date": date, "arms": arms, "summary": meta.get("summary", ""), "url": f"{BASE}/blog/{slug}", "markdown": f"{BASE}/blog/{slug}.md"})
    entries.sort(key=lambda e: (e["date"], e["title"]), reverse=True)
    items = "".join(f"<li><span class=\"d\">{html.escape(e['date'])}</span><a href=\"/blog/{e['slug']}\">{html.escape(e['title'])}</a>" + (f"<br><span class=\"sum\">{html.escape(e['summary'])}</span>" if e["summary"] else "") + "</li>" for e in entries)
    index = HEAD.format(title="All updates", desc="Research notes as new models are collected") + "<h1>Updates</h1><p class=\"meta\">Notes written as new models and collections enter the study. Each entry has verified numbers and verbatim excerpts with links to the full texts.</p><ul class=\"entries\">" + items + "</ul>" + FOOT
    (OUT / "index.html").write_text(index)
    (OUT / "entries.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1))
    print(f"blog: {len(entries)} entries → {OUT.relative_to(SITE)}")


if __name__ == "__main__":
    main()
