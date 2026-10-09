#!/usr/bin/env python3
"""brand_preview.py: turns a tokens.json into one self-contained HTML preview and checks contrast.

    python3 tools/brand_preview.py <tokens.json> [--out preview.html] [--selftest]

tokens.json:
    {"name": str,
     "colors": {"<token>": "#rrggbb"},
     "type": {"heading": str, "body": str},
     "space": [numbers],
     "radius": number,
     "pairs": [["fg-token", "bg-token"], ...]}

There is NO default color: with no `colors` declared nothing is generated (NOT_VERIFIED).
The HTML has no script and no external resource; declared font names become font-family with a
`system-ui` fallback. Every value from the JSON is HTML-escaped. For each pair it prints the WCAG
contrast ratio and a label for normal text: AAA (>= 7), AA (>= 4.5) or fail.

rc: 0 every pair passes AA (or none declared) · 1 a pair fails AA (the file is still written) ·
2 invalid input, names the field · 3 NOT_VERIFIED: no colors declared, no file written
"""
import argparse
import contextlib
import html
import io
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
FONT_RE = re.compile(r"^[A-Za-z0-9 ,_.-]+$")
AA, AAA = 4.5, 7.0


class Invalid(Exception):
    """Invalid input; the message names the field."""


def channel(value):
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(fg, bg):
    a, b = luminance(fg), luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def label(ratio):
    if ratio >= AAA:
        return "AAA"
    if ratio >= AA:
        return "AA"
    return "fail"


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def validate(data):
    """Returns the normalized spec, or raises Invalid. Empty colors are NOT an error here: see main()."""
    if not isinstance(data, dict):
        raise Invalid("root: expected a JSON object")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise Invalid("name: expected a non-empty string")
    colors = data.get("colors", {})
    if not isinstance(colors, dict):
        raise Invalid("colors: expected an object of token -> #rrggbb")
    for token, value in colors.items():
        if not isinstance(value, str) or not HEX_RE.match(value):
            raise Invalid(f"colors.{token}: expected a 6-digit hex like #1a2b3c")
    fonts = data.get("type", {})
    if not isinstance(fonts, dict):
        raise Invalid("type: expected an object with heading and body")
    for key in ("heading", "body"):
        if key in fonts and (not isinstance(fonts[key], str) or not FONT_RE.match(fonts[key])):
            raise Invalid(f"type.{key}: expected a font name (letters, digits, space, comma, dot, dash)")
    space = data.get("space", [])
    if not isinstance(space, list) or not all(is_number(v) and v >= 0 for v in space):
        raise Invalid("space: expected a list of non-negative numbers")
    radius = data.get("radius", 0)
    if not is_number(radius) or radius < 0:
        raise Invalid("radius: expected a non-negative number")
    pairs = data.get("pairs", [])
    if not isinstance(pairs, list):
        raise Invalid("pairs: expected a list of [fg-token, bg-token]")
    for i, p in enumerate(pairs):
        if not (isinstance(p, list) and len(p) == 2 and all(isinstance(t, str) for t in p)):
            raise Invalid(f"pairs[{i}]: expected [fg-token, bg-token] as two strings")
    return dict(name=name, colors=colors, type=fonts, space=space, radius=radius, pairs=pairs)


def check_pairs(spec):
    out = []
    for i, (fg, bg) in enumerate(spec["pairs"]):
        for t in (fg, bg):
            if t not in spec["colors"]:
                raise Invalid(f"pairs[{i}]: token '{t}' is not in colors")
        ratio = contrast(spec["colors"][fg], spec["colors"][bg])
        out.append((fg, bg, ratio, label(ratio)))
    return out


def num(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def font_css(names):
    families = [f"'{n.strip()}'" for n in names.split(",") if n.strip()]
    return ", ".join(families + ["system-ui"])


def render(spec, results):
    e = html.escape
    colors = spec["colors"]
    heading_font = font_css(spec["type"].get("heading", ""))
    body_font = font_css(spec["type"].get("body", ""))
    parts = [
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">",
        f"<title>{e(spec['name'])} brand preview</title>",
        "<style>",
        f"body{{font-family:{body_font};margin:2rem;color:#111;background:#fff}}",
        f"h1,h2{{font-family:{heading_font}}}",
        ".sw{display:inline-block;width:9rem;margin:0 .75rem .75rem 0;border:1px solid #888;"
        f"border-radius:{num(spec['radius'])}px;overflow:hidden;font-size:.8rem}}",
        ".sw div{height:4rem}.sw p{margin:.4rem}",
        ".bar{height:1rem;background:#555;margin:.25rem 0}",
        ".pair{padding:.75rem 1rem;margin:.5rem 0}",
        "</style></head><body>",
        f"<h1>{e(spec['name'])}</h1>",
        "<h2>Palette</h2>",
    ]
    for token, value in colors.items():
        parts.append(f"<div class=\"sw\"><div style=\"background:{value}\"></div>"
                     f"<p>{e(token)}<br>{e(value)}</p></div>")
    parts.append("<h2>Type</h2>")
    parts.append(f"<p style=\"font-family:{heading_font};font-size:2rem\">Heading sample: {e(spec['type'].get('heading', 'system-ui'))}</p>")
    parts.append(f"<p style=\"font-family:{body_font}\">Body sample: {e(spec['type'].get('body', 'system-ui'))}. "
                 "The quick brown fox jumps over the lazy dog.</p>")
    parts.append("<h2>Space</h2>")
    for v in spec["space"]:
        parts.append(f"<div class=\"bar\" style=\"width:{num(min(v, 600))}px\"></div><small>{e(num(v))}</small>")
    parts.append(f"<h2>Radius</h2><p>{e(num(spec['radius']))}px</p>")
    parts.append("<h2>Contrast (normal text)</h2>")
    if not results:
        parts.append("<p>No pairs declared: contrast was not checked.</p>")
    for fg, bg, ratio, lab in results:
        parts.append(f"<div class=\"pair\" style=\"color:{colors[fg]};background:{colors[bg]}\">"
                     f"{e(fg)} on {e(bg)}: {ratio:.2f}:1 {e(lab)}</div>")
    parts.append("</body></html>\n")
    return "\n".join(parts)


def generate(data, out):
    """Returns (rc, [lines])."""
    try:
        spec = validate(data)
        if not spec["colors"]:
            return 3, ["NOT_VERIFIED: no colors declared; there is no default palette, no file was written."]
        results = check_pairs(spec)
    except Invalid as e:
        return 2, [f"ERROR: {e}"]
    lines = [f"{fg} on {bg}: {ratio:.2f}:1 {lab}" for fg, bg, ratio, lab in results]
    if not results:
        lines.append("NOT_VERIFIED: no pairs declared; contrast was not checked.")
    try:
        Path(out).write_text(render(spec, results), encoding="utf-8")
    except OSError as e:
        return 2, [f"ERROR: cannot write {out}: {type(e).__name__}"]
    failed = [r for r in results if r[3] == "fail"]
    lines.append(f"wrote {out}: {len(spec['colors'])} color(s), {len(results)} pair(s), {len(failed)} failing AA")
    # A contrast check that checked nothing is NOT_VERIFIED (rc 3), never a quiet OK; the file is still written.
    return (1 if failed else (0 if results else 3)), lines


def selftest():
    failed = []

    def check(name, cond):
        print(f"  {'ok  ' if cond else 'FAILED'}  {name}")
        if not cond:
            failed.append(name)

    check("black on white is 21:1", abs(contrast("#000000", "#ffffff") - 21.0) < 1e-9)
    check("same color is 1:1", abs(contrast("#336699", "#336699") - 1.0) < 1e-9)
    check("labels: 21 AAA, 4.54 AA, 3 fail", [label(21), label(4.54), label(3)] == ["AAA", "AA", "fail"])
    base = {"name": "Demo", "colors": {"ink": "#000000", "paper": "#ffffff", "mist": "#cccccc"},
            "type": {"heading": "Inter", "body": "Georgia"}, "space": [4, 8], "radius": 6,
            "pairs": [["ink", "paper"]]}
    tmp = Path(tempfile.mkdtemp(prefix="brand-preview-selftest-"))
    try:
        out = tmp / "p.html"
        rc, _ = generate(base, out)
        check("good pair is rc 0 and writes the file", rc == 0 and out.is_file())
        text = out.read_text(encoding="utf-8")
        check("no script and no external resource", "<script" not in text and "http" not in text)
        bad = {**base, "pairs": [["mist", "paper"]]}
        rc, lines = generate(bad, tmp / "q.html")
        check("low contrast pair fails (rc 1)", rc == 1 and any(l.endswith("fail") for l in lines))
        inj = {**base, "name": "<script>alert(1)</script>"}
        generate(inj, out)
        text = out.read_text(encoding="utf-8")
        check("injection in name comes out escaped", "<script>alert" not in text and "&lt;script&gt;" in text)
        check("invalid hex is rc 2", generate({**base, "colors": {"ink": "#12345"}}, out)[0] == 2)
        check("unknown token in pairs is rc 2", generate({**base, "pairs": [["ink", "nope"]]}, out)[0] == 2)
        gone = tmp / "none.html"
        rc, lines = generate({"name": "Demo"}, gone)
        check("no colors is rc 3 and no file", rc == 3 and not gone.exists() and lines[0].startswith("NOT_VERIFIED"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\nSELFTEST FAILED: " + "; ".join(failed) if failed else "\nSELFTEST OK: brand_preview")
    return 1 if failed else 0


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tokens", nargs="?")
    ap.add_argument("--out", default="preview.html")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.tokens:
        ap.error("a tokens.json file is required")
    try:
        data = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        print(f"ERROR: cannot read {args.tokens}: {type(e).__name__}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: {args.tokens} is not valid JSON: {e.msg} (line {e.lineno})", file=sys.stderr)
        return 2
    rc, lines = generate(data, args.out)
    for line in lines:
        print(line, file=sys.stderr if rc == 2 else sys.stdout)
    return rc


if __name__ == "__main__":
    sys.exit(main())
