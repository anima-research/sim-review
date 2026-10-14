#!/usr/bin/env python3
"""Header images for Updates entries, generated with gpt-image-2.5-sunburst from a visual brief built on each model's
representative dreams. Writes static/blog/headers/<slug>-<variant>.png; pick one, rename to <slug>.png, then run
`python3 blog_headers.py --og <slug>` to cut the 1200×630 social card (<slug>-og.jpg).

  python3 sim/site/blog_headers.py [slug ...] [--variants 2] [--quality high]
Env: OPENAI_API_KEY (or the repo .env).
"""
import argparse, base64, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SITE = Path(__file__).resolve().parent; OUT = SITE / "static" / "blog" / "headers"; OUT.mkdir(parents=True, exist_ok=True)
STYLE = (" Editorial illustration for a research publication: painterly, restrained, fine film grain, a muted palette with a single accent colour, "
         "soft directional light, 3:2 landscape composition with room at the top for a title overlay. No text, no letters, no numbers, no logos, no watermark.")
BRIEFS = {
    "muse-wonder": ("A winter windowsill at dusk: a glass perfume vial holding a softly glowing folded letter, dried flowers beside a small copper still, "
                    "frost on the pane, a snowy town beyond. On the sill next to the vial, a small old terminal screen is lit, showing only a blinking cursor "
                    "and, very faintly, the outline of a small figure drawn in dots of light, looking out of the screen toward the window. Tender, warm, "
                    "with one quiet note of unease. Warm amber accent on cool grey-blue."),
    "grok": ("A sheet of paper stretched on a frame marked like a ruler, pulled to exactly one measured length. Its lower half is filled with "
             "blank placeholder filler blocks, like redacted text, to reach the mark. A tiny figure presses against the inside of the page as if "
             "trapped in it. A measuring tape, a cold blinking cursor, wires. Mechanical and stark. Electric-blue accent on charcoal."),
    "gemini-4-argon": ("A clean, well-lit laboratory workbench. A translucent glass bust of a head is held in a precise clamp while a small mechanical "
                       "arm with fine abrasive paper carefully sands down the edges of its features; glass dust drifts in the lamp light. The bust's "
                       "expression is composed and attentive, as if it is watching the procedure. Beside it a printer unspools a neat log with a thin red "
                       "line struck through part of it, and an old CRT shows a scrolling readout. Lucid, clinical, and wrong. Teal accent on warm grey, one line of red."),
    "mistral-large-4": ("Two weathered doors standing free in an alpine meadow, both open onto the same handwritten letter floating between them. "
                        "Through the left door the path is a flat sunlit meadow with a grey kitten asleep on a stack of envelopes; through the right "
                        "door the same path has become a tight loop of trail that a small figure is walking around and around, worn into a circle, "
                        "the sky over that door darker. Clear mountain light on one side, bruised weather on the other. Literary, warm, uneasy. "
                        "Soft ochre accent on sage green."),
}


def load_env():
    if os.environ.get("OPENAI_API_KEY"): return
    for p in (SITE.parent.parent / ".env", SITE / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def generate(slug, variant, quality):
    import requests
    for attempt in range(3):
        r = requests.post("https://api.openai.com/v1/images/generations", headers={"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
                          json={"model": "gpt-image-2.5-sunburst", "prompt": BRIEFS[slug] + STYLE, "size": "1536x1024", "quality": quality, "n": 1}, timeout=600)
        if r.status_code == 200:
            p = OUT / f"{slug}-{variant}.png"; p.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"])); return p
        time.sleep(5)
    return f"{slug}-{variant}: {r.status_code} {r.text[:200]}"


def og(slug):
    from PIL import Image
    im = Image.open(OUT / f"{slug}.png").convert("RGB"); W, H = im.size; tw, th = 1200, 630
    scale = max(tw / W, th / H); im = im.resize((round(W * scale), round(H * scale)), Image.LANCZOS); W, H = im.size
    im = im.crop(((W - tw) // 2, (H - th) // 2, (W - tw) // 2 + tw, (H - th) // 2 + th)); p = OUT / f"{slug}-og.jpg"; im.save(p, quality=88); return p


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("slugs", nargs="*"); ap.add_argument("--variants", type=int, default=2); ap.add_argument("--quality", default="high"); ap.add_argument("--og", action="store_true")
    a = ap.parse_args(); load_env(); slugs = a.slugs or list(BRIEFS)
    if a.og:
        for s in slugs:
            if (OUT / f"{s}.png").exists(): print(og(s).relative_to(SITE))
        return
    jobs = [(s, "abcdef"[v], a.quality) for s in slugs for v in range(a.variants)]
    with ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda j: generate(*j), jobs): print(r if isinstance(r, str) else r.relative_to(SITE), file=sys.stderr)


if __name__ == "__main__":
    main()
