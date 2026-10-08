#!/usr/bin/env python3
"""synth.py: a deterministic synthetic vault with the shape of a big real one. Stdlib only.

    python3 tools/synth.py OUT_DIR --notes 5000 [--seed 7] [--force]

Same seed and same N give the same bytes, on any machine. The vault is made of invented words: no
real note, name or path is in it, so it is safe to generate anywhere and to commit nothing of it.

Shape (measured on a private vault of 3795 .md files and 25069 wikilinks, about 6.6 links per file):
  - 6 areas, one project per ~100 notes (a few projects hold most of the files), a root `projects/<name>/instructions.md` per project;
  - ~70% notes/<area>/, ~14% project files, ~10% inbox/ (never linked), ~6% tasks/;
  - links go by full path from the vault and sit in the middle of the text;
  - in-degree has a heavy tail (preferential attachment): a few notes are linked by very many;
  - about 15% of the notes are cited by a project file (the "used" ones), the rest sit still;
  - the three memory files hold ~N/100 dated lines each (an assumption, not a measurement: a vault that is
    used for months says more); tasks are 2/3 open or in progress.
`--notes N` is the number of .md files under notes/, projects/, inbox/ and tasks/ together.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hub  # noqa: E402  (the project roots carry the generated file list, like a real vault)

REFERENCE_DAY = date(2026, 10, 1)  # fixed on purpose: today's date would make the output change
HISTORY_DAYS = 180
AREAS = ["learning", "technology", "life", "work", "health", "money"]
PROJECT_RATIO = 100            # one project per this many notes
USED_SHARE = 0.15              # share of notes that some project file cites
MEAN_LINKS = 9                 # outbound wikilinks per note (tuned so that [[ per file lands near the measured 6.6)

ADJ = ("small", "slow", "honest", "plain", "careful", "early", "late", "shared", "narrow", "steady",
       "loose", "fresh", "quiet", "sharp", "open", "blunt", "tidy", "rough", "daily", "weekly")
NOUN = ("habit", "draft", "budget", "route", "script", "chapter", "plan", "lesson", "ritual", "backlog",
        "garden", "ledger", "sketch", "protocol", "recipe", "playlist", "checklist", "journal", "model",
        "map", "story", "tool", "meeting", "workout", "contract", "report", "review", "pattern", "rule")
VERB = ("beats", "shapes", "replaces", "explains", "delays", "feeds", "tests", "trims", "guards", "reveals",
        "slows", "frames", "limits", "unlocks", "repeats", "splits")
FILL = ("because", "while", "after", "unless", "before", "once", "whenever", "although")
TYPES = (("note", 0.55), ("video", 0.2), ("book", 0.15), ("archive", 0.1))


def words(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(ADJ + NOUN + VERB) for _ in range(n))


def title(rng: random.Random) -> str:
    return f"A {rng.choice(ADJ)} {rng.choice(NOUN)} {rng.choice(VERB)} the {rng.choice(ADJ)} {rng.choice(NOUN)}"


def slug(text: str, i: int) -> str:
    return "-".join(text.lower().split()[:6]) + f"-{i}"


def pick_type(rng: random.Random) -> str:
    x, acc = rng.random(), 0.0
    for name, p in TYPES:
        acc += p
        if x < acc:
            return name
    return "note"


class Plan:
    """What each file is, decided before any text is written so a link can point forward or back."""

    def __init__(self, n: int, rng: random.Random):
        self.n_inbox = n * 10 // 100
        self.n_tasks = n * 6 // 100
        self.n_projects = max(2, n // PROJECT_RATIO)
        self.n_pfiles = n * 14 // 100
        self.n_notes = max(1, n - self.n_inbox - self.n_tasks - self.n_pfiles - self.n_projects)
        self.projects = [f"project-{p:03d}-{rng.choice(ADJ)}-{rng.choice(NOUN)}" for p in range(self.n_projects)]
        # a few projects hold most of the files, like a real vault (Zipf-like weights)
        self.weights = [1 / (k + 1) ** 0.9 for k in range(self.n_projects)]
        self.notes: list[dict] = []
        for i in range(self.n_notes):
            t = title(rng)
            area = rng.choice(AREAS)
            self.notes.append({"i": i, "title": t, "area": area, "rel": f"notes/{area}/{slug(t, i)}",
                               "project": rng.choices(self.projects, self.weights)[0],
                               "type": pick_type(rng),
                               "date": REFERENCE_DAY - timedelta(days=rng.randrange(HISTORY_DAYS))})
        self.pfiles: list[dict] = []
        for i in range(self.n_pfiles):
            t = title(rng)
            p = rng.choices(self.projects, self.weights)[0]
            self.pfiles.append({"i": i, "title": t, "project": p, "rel": f"projects/{p}/{slug(t, i)}"})


def preferential_targets(rng: random.Random, plan: Plan) -> list[list[int]]:
    """For each note, the indexes of the earlier notes it links to. Preferential attachment: a note that
    was linked before is more likely to be linked again (the endpoints list is the urn)."""
    urn: list[int] = []
    out: list[list[int]] = []
    for i in range(plan.n_notes):
        picks: list[int] = []
        k = 0 if i == 0 else min(i, max(1, int(rng.expovariate(1 / MEAN_LINKS)) + 1))
        for _ in range(k):
            j = rng.choice(urn) if urn and rng.random() < 0.6 else rng.randrange(i)
            if j != i and j not in picks:
                picks.append(j)
        out.append(picks)
        urn.extend(picks)
        urn.append(i)
    return out


def sentence(rng: random.Random, link: str | None) -> str:
    base = f"The {rng.choice(NOUN)} {rng.choice(VERB)} the {rng.choice(ADJ)} {rng.choice(NOUN)} {rng.choice(FILL)} the {rng.choice(NOUN)} {rng.choice(VERB)} it"
    return f"{base}, see {link}." if link else f"{base}."


def paragraph(rng: random.Random, links: list[str]) -> str:
    parts = [sentence(rng, links.pop() if links else None) for _ in range(rng.randrange(3, 6))]
    return " ".join(parts)


def note_text(rng: random.Random, plan: Plan, n: dict, targets: list[int]) -> str:
    links = [f"[[{plan.notes[j]['rel']}|{plan.notes[j]['title'][:40]}]]" for j in targets]
    if not links or rng.random() < 0.3:
        links.append(f"[[projects/{n['project']}/instructions|{n['project']}]]")
    head = (f"---\ntype: {n['type']}\narea: {n['area']}\nproject: {n['project']}\ndate: {n['date'].isoformat()}\n"
            f"target: projects/{n['project']}/instructions.md\n---\n# {n['title']}\n\n")
    body = []
    while links or len(body) < 2:
        body.append(paragraph(rng, links))
    return head + "\n\n".join(body) + "\n"


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def generate(out: Path, n: int, seed: int) -> dict:
    rng = random.Random(seed)
    plan = Plan(n, rng)
    targets = preferential_targets(rng, plan)
    v = out / "vault"
    write(v, "areas.txt", "\n".join(AREAS) + "\n")
    write(v, "home.md", "# Home\n\n" + "\n".join(f"- [[projects/{p}/instructions|{p}]]" for p in plan.projects[:20])
          + "\n\n" + "\n".join(f"- [[memory/{m}]]" for m in ("profile", "patterns", "decisions")) + "\n")
    for name in ("profile", "patterns", "decisions"):  # a long-used vault has said more: ~1 dated line per 100 notes per file
        said = [f"- {(REFERENCE_DAY - timedelta(days=rng.randrange(HISTORY_DAYS))).isoformat()}: \"{words(rng, 14)}\""
                for _ in range(n // 100)]
        write(v, f"memory/{name}.md", f"# {name.title()}\n\n" + ("\n".join(said) if said else "_(empty)_") + "\n")
    write(v, "projects/_index.md", "# Projects\n\n" + "\n".join(f"- [[projects/{p}/instructions|{p}]]" for p in plan.projects) + "\n")
    for p in plan.projects:
        write(v, f"projects/{p}/instructions.md",
              f"---\ntype: project\nstatus: active\ndeclared_target: something that exists when this works\n---\n"
              f"# {p}\n\n{words(rng, 18)}.\n\n<!-- hub:start -->\n<!-- hub:end -->\n")
    # which notes some project file cites: a share of the notes, chosen once
    used = rng.sample(range(plan.n_notes), int(plan.n_notes * USED_SHARE))
    cited_by: dict[int, list[int]] = {}
    for j, note_i in enumerate(used):
        cited_by.setdefault(j % max(1, plan.n_pfiles), []).append(note_i)
    for i, nt in enumerate(plan.notes):
        write(v, nt["rel"] + ".md", note_text(rng, plan, nt, targets[i]))
    for pf in plan.pfiles:
        links = [f"[[{plan.notes[j]['rel']}|{plan.notes[j]['title'][:40]}]]" for j in cited_by.get(pf["i"], [])]
        links.append(f"[[projects/{pf['project']}/instructions|{pf['project']}]]")
        body = []
        while links or len(body) < 2:
            body.append(paragraph(rng, links))
        write(v, pf["rel"] + ".md", f"---\ntype: brief\n---\n# {pf['title']}\n\n" + "\n\n".join(body) + "\n")
    for i in range(plan.n_inbox):
        write(v, f"inbox/capture-{i:05d}.md", f"# capture {i}\n\n{words(rng, 25)}\n")
    for i in range(plan.n_tasks):
        p = rng.choices(plan.projects, plan.weights)[0]
        status = rng.choice(("open", "open", "in-progress", "done", "done", "done"))
        write(v, f"tasks/task-{i:05d}.md",
              f"---\ntags:\n  - task\ntitle: {rng.choice(VERB)} the {rng.choice(NOUN)}\nstatus: {status}\npriority: normal\n"
              f"projects:\n  - \"[[projects/{p}/instructions|{p}]]\"\n---\n\n{words(rng, 8)}\n")
    with contextlib.redirect_stdout(io.StringIO()):  # hub prints one line per project
        hub.run(v, check=False, dry=False)
    return {"notes": plan.n_notes, "pfiles": plan.n_pfiles, "projects": plan.n_projects,
            "inbox": plan.n_inbox, "tasks": plan.n_tasks, "path": str(v)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("out")
    ap.add_argument("--notes", type=int, required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--force", action="store_true", help="write into a folder that already has files")
    a = ap.parse_args(argv)
    if a.notes < 20:
        ap.error("--notes must be at least 20")
    out = Path(a.out)
    if out.exists() and any(out.iterdir()) and not a.force:
        print(f"ERROR: {out} is not empty (use --force). Nothing was written.", file=sys.stderr)
        return 2
    info = generate(out, a.notes, a.seed)
    print(f"synthetic vault at {info['path']}: {info['notes']} notes, {info['pfiles']} project files, "
          f"{info['projects']} projects, {info['inbox']} inbox, {info['tasks']} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
