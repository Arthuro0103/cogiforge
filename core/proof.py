#!/usr/bin/env python3
"""proof.py: NOT_VERIFIED as a first-class verdict, with a typed reason. Stdlib only.

    python3 core/proof.py --selftest

A check that touched nothing cannot say OK (rule 11 of the repo). A two-column scoreboard
(passed / failed) forces every check to lie about the third thing it can be: "I did not look".
This module is the library a check uses so it cannot lie about that:

  * the evidence is recorded OUTSIDE the check: a `Record` writes down every file read and every
    command run, and a check never writes its own provenance;
  * `verify()` downgrades to NOT_VERIFIED any check that touched nothing, whatever it returned;
  * a null result carries one of five typed reasons, and a null without a reason raises
    `ReasonMissing`. "I ran and there was nothing to measure" and "I did not run" are different
    facts, and an automation has to be able to tell them apart.

The five reasons:

    single           found exactly one, and this is it. The only reason that carries a value.
    multiple         found more than one: there is no single answer, and picking one is inventing
    nothing_to_measure  RAN, and the set was empty
    wrong_type       something came back that is not the kind of thing that is measured (a cloud-sync
                     placeholder: `stat` says 11,875 bytes, the disk has zero)
    failed           the attempt did not happen, or broke

Status and reason are different axes on purpose. The status answers "does this count as OK?", the
reason answers "why is there no value?". The one law that ties them: a null verdict (NOT_VERIFIED or
ERROR) never has the reason `single`, and a verdict with a value (VERIFIED or FAILED) always has it.

rc of the CLI (selftest only): 0 the selftest holds · 1 the selftest is broken · 2 usage
rc of `scoreboard()`: 0 only when everything is VERIFIED; any FAILED, NOT_VERIFIED or ERROR is 1.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

VERIFIED = "VERIFIED"
FAILED = "FAILED"
NOT_VERIFIED = "NOT_VERIFIED"
ERROR = "ERROR"
STATUSES = (VERIFIED, FAILED, NOT_VERIFIED, ERROR)


class Reason(str, Enum):
    """WHY there is no value, separate from what that means for the scoreboard.

    Closed on purpose: a free-text reason is the same as no reason, because nobody can branch on it
    without guessing the spelling of whoever wrote it.
    """

    SINGLE = "single"
    MULTIPLE = "multiple"
    NOTHING_TO_MEASURE = "nothing_to_measure"
    WRONG_TYPE = "wrong_type"
    FAILED = "failed"

    def __str__(self) -> str:
        return self.value


class ReasonMissing(TypeError):
    """A null result without a typed reason.

    The error IS the product. A null that is born without a reason becomes silence two layers later,
    and then nobody knows whether the measurement ran. Raising here forces whoever writes the check
    to answer on the spot, which is the only moment they know.
    """


class EmptyRead(OSError):
    """A file whose size on disk is not zero came back with zero bytes (a cloud placeholder)."""


@dataclass(frozen=True)
class Measure:
    """The result of one measurement: a value, or a typed reason for not having one."""

    value: object | None
    reason: Reason
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.reason, Reason):
            raise ReasonMissing(f"reason={self.reason!r} is not a Reason: a null without a typed reason is silence")
        if self.reason is Reason.SINGLE and self.value is None:
            raise ReasonMissing("reason=single with a null value: 'found one' and 'found none' cannot be the same")
        if self.reason is not Reason.SINGLE and self.value is not None:
            raise ReasonMissing(f"reason={self.reason} with a value: a null reason carrying a value contradicts itself")

    @property
    def has_value(self) -> bool:
        return self.reason is Reason.SINGLE

    def __str__(self) -> str:
        if not self.has_value:
            return f"{self.reason}: {self.detail}"
        raw = repr(self.value)  # the value can be a whole file: a scoreboard that dumps contents is no scoreboard
        shown = raw if len(raw) <= 70 else raw[:67] + "..."
        return f"value={shown}" + (f" ({self.detail})" if self.detail else "")


@dataclass
class Touch:
    """One piece of evidence: what the check really reached."""

    kind: str  # file | command
    target: str
    detail: str

    def __str__(self) -> str:
        return f"{self.kind}:{self.target} ({self.detail})"


class Record:
    """What a check touched. The record writes it, never the check.

    This is what makes a verdict hard to fake: a check cannot claim a provenance it does not have,
    because it is not the one writing the record.
    """

    def __init__(self) -> None:
        self.touches: list[Touch] = []

    def read_file(self, path: str | Path) -> str:
        """Read as UTF-8, compare with the size on disk, and record the bytes read."""
        p = Path(path)
        expected = p.stat().st_size
        raw = p.read_bytes()
        if expected > 0 and len(raw) == 0:
            self.touches.append(Touch("file", str(p), f"0 bytes read, {expected} on disk"))
            raise EmptyRead(f"{p}: {expected} bytes on disk, 0 read (a placeholder, not the file)")
        if len(raw) != expected:
            self.touches.append(Touch("file", str(p), f"short read: {len(raw)} of {expected}"))
            raise OSError(f"{p}: short read, {len(raw)} of {expected} bytes")
        self.touches.append(Touch("file", str(p), f"{len(raw)} bytes read"))
        return raw.decode("utf-8", errors="replace")

    def run(self, args: list[str], **kw) -> subprocess.CompletedProcess:
        """Run and record rc plus bytes of output. rc=0 alone is not evidence of anything."""
        r = subprocess.run(args, capture_output=True, text=True, check=False, **kw)
        self.touches.append(Touch("command", " ".join(args[:4]), f"rc={r.returncode}, {len(r.stdout)}B stdout"))
        return r

    def single_file(self, folder: str | Path, pattern: str = "*.md") -> Measure:
        """'Which is THE file in this folder?', and every way for it to go wrong has its own name.

            folder does not exist  -> failed             (did not run)
            folder is empty        -> nothing_to_measure (RAN, and there was nothing)
            two candidates         -> multiple           (choosing one would be inventing)
            cloud placeholder      -> wrong_type         (has a size, has no content)
            one real file          -> single
        """
        p = Path(folder)
        if not p.is_dir():
            self.touches.append(Touch("file", str(p), "not a folder"))
            return Measure(None, Reason.FAILED, f"{p} is not a folder")
        try:
            found = sorted(x for x in p.glob(pattern) if x.is_file())
        except OSError as e:
            self.touches.append(Touch("file", str(p), f"glob failed: {e}"))
            return Measure(None, Reason.FAILED, f"{type(e).__name__}: {e}")
        self.touches.append(Touch("file", str(p), f"{len(found)} match {pattern}"))
        if not found:
            return Measure(None, Reason.NOTHING_TO_MEASURE, f"no {pattern} in {p}: the folder exists and is empty")
        if len(found) > 1:
            names = ", ".join(x.name for x in found[:3])
            return Measure(None, Reason.MULTIPLE, f"{len(found)} candidates ({names}...)")
        try:
            text = self.read_file(found[0])
        except EmptyRead as e:
            # Not `failed`: nothing broke. Not `nothing_to_measure`: there is a file there.
            return Measure(None, Reason.WRONG_TYPE, f"placeholder, not a file: {e}")
        return Measure(text, Reason.SINGLE, str(found[0]))

    def __len__(self) -> int:
        return len(self.touches)


@dataclass
class Verdict:
    name: str
    status: str
    touches: list[Touch] = field(default_factory=list)
    note: str = ""
    reason: Reason | None = None

    def __post_init__(self) -> None:
        """A null without a reason raises. That is the whole rule."""
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r} for '{self.name}'")
        null = self.status in (NOT_VERIFIED, ERROR)
        if null and self.reason is None:
            raise ReasonMissing(
                f"verdict {self.status} of '{self.name}' has no typed reason. "
                f"Pick one: {', '.join(r.value for r in Reason)}."
            )
        if null and self.reason is Reason.SINGLE:
            raise ReasonMissing(f"'{self.name}' is {self.status} and says reason=single: if one value was found, the verdict is not null")
        if not null:
            if self.reason is None:
                self.reason = Reason.SINGLE
            elif self.reason is not Reason.SINGLE:
                raise ReasonMissing(f"'{self.name}' concluded ({self.status}) with a null reason ({self.reason})")

    @property
    def counts_as_ok(self) -> bool:
        """Only VERIFIED counts. This is the whole point of the module."""
        return self.status == VERIFIED


def verify(name: str, fn) -> Verdict:
    """Run a check and return the verdict, downgrading what touched nothing.

    `fn` receives a `Record` and returns True (passed) / False (failed) / None (did not conclude) /
    a `Measure` (measured, and the reason says what came out). The downgrade is unconditional: if the
    record is empty, what the check returned is ignored, because a check that says True without having
    opened a file or run a command is stating something it did not look at.

    The idiom to measure and judge in the same check, without one swallowing the other:

        def check(rec):
            m = rec.single_file(folder)
            if not m.has_value:
                return m                 # nothing to judge; the reason says why
            return "abc123" in m.value   # now it judges

    Returning the bare `Measure` is not failing: it says there was nothing to judge. A measured zero is
    a fact, not a failure.
    """
    rec = Record()
    try:
        r = fn(rec)
    except EmptyRead as e:
        return Verdict(name, NOT_VERIFIED, rec.touches, f"placeholder read: {e}", reason=Reason.WRONG_TYPE)
    except Exception as e:  # noqa: BLE001 - the error is information, not an accident
        return Verdict(name, ERROR, rec.touches, f"{type(e).__name__}: {e}", reason=Reason.FAILED)

    if len(rec) == 0:
        return Verdict(name, NOT_VERIFIED, [], "touched nothing: the return value was ignored", reason=Reason.FAILED)
    if isinstance(r, Measure):
        if r.has_value:
            return Verdict(name, VERIFIED, rec.touches, str(r), reason=Reason.SINGLE)
        return Verdict(name, NOT_VERIFIED, rec.touches, r.detail, reason=r.reason)
    if r is None:
        return Verdict(name, NOT_VERIFIED, rec.touches, "the check did not conclude", reason=Reason.FAILED)
    return Verdict(name, VERIFIED if r else FAILED, rec.touches, reason=Reason.SINGLE)


def scoreboard(verdicts: list[Verdict], *, detail: bool = False) -> tuple[str, int]:
    """A FOUR-column scoreboard, and an rc that does not forgive NOT_VERIFIED.

    A two-column scoreboard is the defect, not the presentation of it: it forces the check to pick
    between two boxes when the honest answer is the third.
    """
    by = {s: [v for v in verdicts if v.status == s] for s in STATUSES}
    mark = {VERIFIED: "+", FAILED: "x", NOT_VERIFIED: "?", ERROR: "!"}
    lines = []
    for v in verdicts:
        # the reason goes on the line of what has no value: that is where "ran and found nothing"
        # stops being indistinguishable from "did not run"
        why = f" [{v.reason}]" if v.reason and v.reason is not Reason.SINGLE else ""
        lines.append(f"  {mark[v.status]} {v.status:<13} {v.name}{why}" + (f": {v.note}" if v.note else ""))
        if detail:
            lines.extend(f"        touched: {t}" for t in v.touches)
        if v.status == NOT_VERIFIED and not v.touches:
            lines.append("        touched: NOTHING (this 'ok' is worth nothing)")
    n_ok, n_bad, n_nv, n_err = (len(by[s]) for s in STATUSES)
    lines += ["", f"  {n_ok} verified, {n_bad} failed, {n_nv} NOT_VERIFIED, {n_err} error"]
    if n_nv:
        untouched = sum(1 for v in by[NOT_VERIFIED] if not v.touches)
        extra = f" ({untouched} touched nothing)" if untouched else ""
        lines.append(f"  WARNING: {n_nv} check(s) without verification{extra}. This is NOT 'passed'.")
    counts: dict[str, int] = {}
    for v in verdicts:
        if v.reason and v.reason is not Reason.SINGLE:
            counts[v.reason.value] = counts.get(v.reason.value, 0) + 1
    if counts:
        lines.append("  reasons: " + ", ".join(f"{n} {r}" for r, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    rc = 0 if (n_bad == 0 and n_nv == 0 and n_err == 0) else 1
    return "\n".join(lines), rc


def _selftest() -> int:
    """The module proved in both directions, without leaving the file."""
    import shutil
    import tempfile

    here = Path(__file__)

    def liar(_rec):
        return True  # says it passed and looked at nothing

    def honest(rec):
        return "NOT_VERIFIED" in rec.read_file(here)

    def really_fails(rec):
        # The sentinel is BUILT at run time. Writing the literal here would put it in the file the
        # check reads, and the check could never fail (a verifier that cannot fail is worse than none).
        absent = "zzz" + "-" + "absent" + "-" + "%04x" % 0xBEEF
        return absent in rec.read_file(here)

    tmp = Path(tempfile.mkdtemp(prefix="proof-selftest-"))
    try:
        (tmp / "empty").mkdir()
        (tmp / "one").mkdir()
        (tmp / "two").mkdir()
        (tmp / "one" / "a.md").write_text("x" * 100, encoding="utf-8")
        (tmp / "two" / "a.md").write_text("a", encoding="utf-8")
        (tmp / "two" / "b.md").write_text("b", encoding="utf-8")

        def placeholder(rec):
            orig = Path.read_bytes
            Path.read_bytes = lambda self: b""
            try:
                return rec.single_file(tmp / "one")
            finally:
                Path.read_bytes = orig

        vs = [
            verify("a check that lies", liar),
            verify("a check that looks and passes", honest),
            verify("a check that looks and fails", really_fails),
            verify("empty folder", lambda r: r.single_file(tmp / "empty")),
            verify("missing folder", lambda r: r.single_file(tmp / "missing")),
            verify("two candidates", lambda r: r.single_file(tmp / "two")),
            verify("placeholder file", placeholder),
            verify("one file", lambda r: r.single_file(tmp / "one")),
        ]
        text, rc = scoreboard(vs, detail=True)
        print(text)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    R = Reason
    ok = (
        vs[0].status == NOT_VERIFIED and not vs[0].touches
        and vs[1].status == VERIFIED
        and vs[2].status == FAILED
        and vs[3].status == NOT_VERIFIED and vs[3].reason is R.NOTHING_TO_MEASURE
        and vs[4].status == NOT_VERIFIED and vs[4].reason is R.FAILED
        and vs[5].status == NOT_VERIFIED and vs[5].reason is R.MULTIPLE
        and vs[6].status == NOT_VERIFIED and vs[6].reason is R.WRONG_TYPE
        and vs[7].status == VERIFIED and vs[7].reason is R.SINGLE
        and vs[3].reason is not vs[4].reason  # ran and found nothing is not the same as did not run
        and rc == 1
    )
    for build in (lambda: Verdict("x", NOT_VERIFIED), lambda: Measure(None, "single"), lambda: Measure(None, R.SINGLE)):
        try:
            build()
        except ReasonMissing:
            continue
        ok = False
    print("\nselftest:", "OK" if ok else "BROKEN")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args == ["--selftest"]:
        return _selftest()
    print(__doc__.split("\n")[0])
    print("usage: python3 core/proof.py --selftest")
    return 2


if __name__ == "__main__":
    sys.exit(main())
