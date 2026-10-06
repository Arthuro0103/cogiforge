"""Exact count per check over demo/ — the fixture's meta-assertion.

If the fixture stops exercising a check (someone deletes the planted note, or the check dies and
the note passes), the number changes and the CI fails. Runnable on its own: `python3 tests/counts.py`.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"

# check -> the ONLY file that fails it (the file name says which failure it carries)
EXPECTED = {
    "orphan": "notes/learning/orphan.md",
    "dead-link": "notes/learning/dead-link.md",
    "broken-link": "notes/learning/broken-link.md",
    "dead-target": "notes/learning/dead-target.md",
    "area": "notes/technology/wrong-area.md",
    "frontmatter": "notes/technology/broken-frontmatter.md",
    "leak": "notes/life/leaked.md",
}
TOTAL_NOTES = 15
RING_EXEMPT = ["inbox/loose-capture.md"]


def _run(script, *args):
    env = {**os.environ, "LEAK_BLOCKLIST": str(ROOT / "absent-on-purpose.txt"), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, str(ROOT / "core" / script), *args],
                          capture_output=True, text=True, cwd=ROOT, env=env)


def count():
    """{check: [files that fail it]} plus the keys '_total' and '_exempt'."""
    found = {c: [] for c in EXPECTED}
    p = _run("gate.py", "--vault", "demo", "--json")
    data = json.loads(p.stdout)
    for f in data["failures"]:
        found.setdefault(f["check"], []).append(f["file"])
    a = json.loads(_run("ring.py", "--vault", "demo", "--json").stdout)
    found["orphan"] = a["orphans"]
    v = _run("leak.py", "--no-ignore", "demo")
    for line in v.stdout.splitlines():
        if line.startswith("demo") and ": " in line:
            found["leak"].append(line.split(":")[0].removeprefix("demo/"))
    found["_total"] = data["files"]
    found["_exempt"] = a["exempt"]
    return found


def main():
    try:
        found = count()
    except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
        print(f"FAILED: could not measure demo/ ({type(e).__name__}: {e})")
        return 1
    bad = 0
    print(f"{'check':<14}{'expected':>9}{'found':>8}  file")
    for check, file in EXPECTED.items():
        got = sorted(found[check])
        ok = got == [file]
        bad += not ok
        print(f"{check:<14}{1:>9}{len(got):>8}  {'ok' if ok else 'DIFFERENT: ' + str(got)}  {file}")
    extras = sorted(set(found) - set(EXPECTED) - {"_total", "_exempt"})
    for c in extras:  # a check that fails and the fixture does not plant: the score changed
        print(f"{c:<14}{0:>9}{len(found[c]):>8}  UNEXPECTED")
        bad += 1
    print(f"notes scanned: {found['_total']} (expected {TOTAL_NOTES}); exempt from the ring: {found['_exempt']}")
    bad += found["_total"] != TOTAL_NOTES or found["_exempt"] != RING_EXEMPT
    print("FAILED" if bad else "OK: exact count on every check")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
