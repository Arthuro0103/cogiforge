# WHY

Every rule in this repo was born from a real mistake, with a date. The mistake is told without project
names, and the **test that catches it lives here**: you can run it and see red without the rule, green
with it.

This is not what the workbench does (that is in the [README](README.md)). This is the foundation under
it: what keeps the workbench from rotting without anyone noticing.

The tests and scripts named below use their English names. If you are reading a translated copy or an
older clone, see [docs/TRANSLATING.md](docs/TRANSLATING.md).

## How a rule gets in

1. **A mistake with a date and a number**, the kind that already happened, not the kind that could happen.
2. **A paired test**: an input that is known to fail **and** a plausible one that must pass.
3. **A mutation**: `tests/mutate.py` breaks each check on purpose and requires the suite to go red. A test that stays green with the check broken tests nothing.

A rule with no mistake to justify it, or with no test that fails without it, does not get in. When you
find a mistake of your own, record it here with the date, write the test that fails, and only then write
the rule. (A skill that automates this does not exist yet.)

## The mistakes

### 1. The link with an old path that the checker approved (Aug 25)

**What broke.** A set of notes was moved to another folder. 58 wikilinks in 38 files kept pointing to the
old path. The checker said "all good" because, when the path did not exist, it fell back to the **file
name** and found the note. Obsidian does not do that when the link carries a path: the 58 were broken on
screen, with the checker saying everything was fine.

**The rule.** A link **with** a path is only valid by its path. Only a link **without** a slash resolves by name.

**Who catches it.** `core/gate.py`, check `dead-link`.
**The test.** `tests/test_gate.py::test_dead_link_fails` (the case `[[other/folder/b]]`, where `b`
exists in another folder) and
`test_target_that_only_matches_by_basename_with_a_declared_path_fails`.

### 2. Seven of the eight checks could be deleted and the tests stayed green (Sep 5)

**What broke.** Someone broke one check at a time on purpose to see whether the suite noticed. The suite
of the time had a test for only 1 of the 8 checks: the other 7 could be deleted and nothing went red.

**The rule.** Every check must have a test that fails when the check is broken.

**Who catches it.** `tests/mutate.py`, which runs in CI as a gate: a surviving mutant fails the build.
**The test.** `mutate.py` itself. Result on Oct 7: **236 of 236 mutants killed, 0 alive**. On Oct 9, after a large merge, the first full run was **361 of 371 killed, 10 alive**: the new pieces came with tests that stayed green with the check broken. Ten tests were added, the eight affected pieces were rerun (**138 of 138 killed**), and the gate went green again. That is the gate doing its job, on the author's own merge.

### 3. A checker that touched nothing and said OK (Sep 11)

**What broke.** A deploy check printed "9 · 0 failed" **without ever talking to the server**.
Zero failures, because nothing was tried.

**The rule.** A check that touched nothing **cannot say OK**. It says `NOT_VERIFIED`.

**Who catches it.** `core/leak.py`: without the private list of terms, it runs only the generic patterns
and says `NOT_VERIFIED`; `--require-list` turns that into rc 3.
**The test.** `tests/test_hook_e2e.py::test_without_a_private_list_warns_not_verified_and_does_not_block`.

### 4. 389 orphan notes became 1, and five new ones were born in the same session (Sep 13 and 14)

**What broke.** One session stitched 254 links **by hand** and took the orphans from 389 down to 1. In
the same session, 5 new orphans were born. Fixing the collection does not close the tap. The hook that
closes it was only written the next day.

**The rule.** A note with no incoming and no outgoing link is blocked **at commit time**, not afterwards.

**Who catches it.** `core/ring.py` through the hook `.githooks/pre-commit`.
**The tests.** `tests/test_ring.py::test_gate_fails_an_orphan_and_teaches_the_fix` and
`tests/test_hook_e2e.py::test_orphan_blocks_the_commit_and_teaches`.

### 5. The hook that existed on disk and never ran (Sep 14)

**What broke.** `core.hooksPath` is **local** git configuration. In a fresh clone the hook arrives on
disk and **does not fire**: the protection exists and does not protect.

**The rule.** The install step activates the hook and **proves** it is active; a test fails when it is not.

**Who catches it.** `install.sh` (fails loudly, rc ≠ 0) and `tests/test_hook_active.py`. CI also checks
that the clone **starts without** `hooksPath` and that it has it after `install.sh`.
**The tests.** `tests/test_hook_active.py::test_hookspath_points_to_githooks` and
`tests/test_hook_e2e.py::test_without_hookspath_the_hook_does_not_fire`.

### 6. A checker that could not read the file and called it debt (Sep 13 and 14)

**What broke.** A file without read permission came out as a "YAML error" and went into the count as
formatting debt. "I could not read it" and "I read it and it is wrong" are different things.

**The rule.** An unreadable file has its own verdict: rc 3, `UNREADABLE`, never clean.

**Who catches it.** `core/gate.py`.
**The tests.** `tests/test_gate.py::test_cli_unreadable_file_exits_3_never_clean` and
`test_unreadable_is_a_non_utf8_file_never_clean`.

### 7. The checker that said OK to what it had not checked, again (Sep 5, and today)

**What broke, in the original.** 3 of the 8 checks aborted on the first line outside the notes folder.
Running the gate on a draft that was not there yet checked only 5 of the 8, **in silence**.

**And the same mistake showed up here, today (Oct 3).** While writing this file, I tested the gate on a
draft **outside** the vault. With a vault given as an absolute path it came out **clean (rc 0)** without
having checked anything; with a relative vault, it crashed with a traceback. The test was written before
the fix, failed, and only then was the gate fixed.

**The rule.** The gate only checks what is **inside** the vault; a file outside it exits with rc 2 and a
message, never as OK.

**Who catches it.** `core/gate.py`.
**The test.** `tests/test_gate.py::test_file_outside_the_vault_exits_2_never_clean_and_no_traceback`.
There is also a dedicated mutant in `tests/mutate.py`.

### 8. The gate that blocks what you did not do becomes the gate you skip (Sep 20 and 24)

**What broke.** A gate that failed the commit because of a note that **was not yours**, or a draft that
was not even in the commit, was bypassed: 3 commits, then 6, with `--no-verify`.

**The rule.** The hook only looks at what **this** commit carries. The rest becomes a warning. And quick
capture (`inbox/`) is never blocked.

**Who catches it.** `core/ring.py --gate --stage`.
**The tests.** `tests/test_hook_e2e.py::test_orphan_outside_the_commit_only_warns`,
`test_inbox_is_never_blocked` and `test_no_verify_is_the_deliberate_bypass`.

### 9. The `;` in the loop that let the commit through (Sep 25)

**What broke.** A shell loop ran the checker and `git commit` separated by `;`. Two commits went out with
the checker failing, because the commit ran anyway.

**The rule.** The block lives **in the git hook**, which every `git commit` goes through, and not in the
discipline of whoever writes the loop.

**Who catches it.** `.githooks/pre-commit`.
**The test.** `tests/test_hook_e2e.py::test_orphan_blocks_the_commit_and_teaches` (the commit exits with
an error and HEAD does not move). CI repeats this in a clean clone.

### 10. The plugin that writes what the checker does not understand, and the task that is born without a link (Oct 3)

**What broke.** When integrating the task plugin, we measured two tasks in its format. One identical to
the example in its documentation passed. The other, with **logged time** (`timeEntries`, a list of maps:
valid YAML), **failed the gate** as "yaml outside the subset". And a task **with no project**, the kind the
interface creates without asking for a link, was an **orphan**: the hook would block the commit.
**Caveat:** the format of these two was built from the plugin's documentation, not from real output from it
(Obsidian was not run here).

**The rule.** What the plugin writes in `tasks/` belongs to the plugin: the gate does not judge the YAML
there, and the folder is exempt from the orphan rule (like `inbox/`). A dead link inside the task still fails.

**Who catches it.** `core/gate.py` (the `tasks/` folder) and `core/ring.py` (`DEPOSITS`).
**The tests.** `tests/test_gate.py::test_plugin_task_frontmatter_is_not_judged_by_the_subset`,
`test_the_same_yaml_outside_tasks_still_fails` and `test_dead_link_inside_the_task_still_fails`;
`tests/test_ring.py::test_plugin_task_without_a_project_is_exempt_but_links_what_it_points_to` and
`test_only_tasks_at_the_root_is_exempt_not_a_similar_name`. There are three dedicated mutants in
`tests/mutate.py`. The tests were written before the fix and failed.

### 11. Notes were kept and never used (Oct 8)

**What broke.** The author's own vault holds 3,795 notes. Measured by `type:`, the share of notes that ever
reached a project file was 4 of 4 for notes born in a conversation, 19 of 165 for videos, 11 of 199 for books and
**0 of 43** for loose archive files. The notes were kept, linked (the orphan gate saw to that) and never used: a
link between two notes proves they were filed, not that anything came out of them.

**The rule.** A note under `notes/` is **used** when something that leaves the notes points at it or answered
from it: a project file (anything under `projects/`) or a note of `type:` article, brief or routine links to it, or
a `/cf-ask` answer that passed `ask.py cite --log` cited it. Everything else is unused; unused and `--days` old
(default 90) is **stale**, unused and younger is **idle**, and a note with no readable `date:` is **undated**,
counted and never guessed. `tools/usage.py` reports it by area. With no note it says `NOT_VERIFIED`, never "0% stale".
`/cf-open-session` and `/cf-close-session` bring back up to 3 unused notes of the project of the day.

**What it does not say.** A link from a project file is evidence that the note was **put to use**, not that it
helped. The third signal one would want, "the target the note declared changed", is not measured: it needs the
history of the target file, and an honest zero is better than a guess. And the only vault it has been measured on is
the author's: nobody else has used it yet.

**Who catches it.** `tools/usage.py`; the log is written by `tools/ask.py cite --log`.
**The tests.** `tools/test_usage.py` (a project file, an output type and an answer count; a plain note, a self link,
a link in code and a link out do not; the stale limit is inclusive at exactly 90 days; no notes is rc 3) and
`tools/test_ask.py::test_a_failed_citation_logs_nothing`. 19 mutants in `tests/mutate.py` (`usage`).

### 12. A commit gate that reads the whole vault gets slower with every note (Oct 8)

**What broke.** Nobody had measured a big vault. On a synthetic one with the shape of the author's (6 areas, links
by full path, a heavy tail of links, @@N10K@@ notes), committing ONE note took @@PRE_BEFORE@@ in the hook, almost all of
it in `core/ring.py`, which read and parsed every note to decide whether the one in the commit was an orphan. A
gate that costs seconds is a gate people skip (see 8).

**The rule.** The commit of one note takes under 2 seconds at 10,000 notes. The ring keeps the links it read from
each note in `<git dir>/cogiforge-edges.json` (never in the vault, never committed), keyed by the file's size and
modification time, and re-reads only what changed. The answer must be **identical** to the one without the
cache, so: a file changed in the last 2 seconds is never cached (size and time could not tell two edits apart), a
corrupt, old or unwritable cache is ignored and rebuilt, and what the cache keeps is the raw link text, not where it
pointed, so a note created later still resolves.

**Who catches it.** `core/ring.py` (`--gate --stage` is the only path that uses the cache).
**The tests.** `tests/test_ring_cache.py` (22 cases, among them `test_a_stale_cache_never_hides_an_orphan_in_the_commit`
and `test_a_corrupt_cache_is_ignored_and_rewritten`, which went red on the first draft: a cache whose `notes` was not a
map crashed the gate). 16 mutants in `tests/mutate.py` (`ring`). `tools/bench.py` measures it again whenever you want.

### 13. A project root that grows with the project (Oct 8)

**What broke.** Each project root carries a generated list of every file of the project, so that none is an
orphan. `/cf-open-session` reads the root. At 10,000 synthetic notes, with a few projects holding most of the files
(as in a real vault), the biggest root was **26 KB**: opening that project cost more than the whole fixed context.

**The rule.** A root lists at most 40 files itself. Past that it keeps one link, `[[projects/<name>/_files|all N files of
this project]]`, and the full list moves to a generated `_files.md` in the same folder. Every file still has an edge
(root, then `_files`, then file), so nothing becomes an orphan; `_files.md` goes away when the project shrinks back, and
a `_files.md` the user wrote is never deleted.

**Who catches it.** `tools/hub.py` (and `hub.py --check` for the list).
**The tests.** `tools/test_hub.py` (the boundary at exactly 40 and 41 files, the root under 600 bytes at 500 files, no
orphan after the move). 10 mutants in `tests/mutate.py` (`hub`).

### 14. The context a session loads is cut in silence (Sep 22, and measured Oct 8)

**What broke.** On Sep 22, in the author's vault, an index that loaded in every session grew past the point where it
is cut, and the cut was silent: a new session answered "I do not know" to 3 of 3 questions whose hook had been
cut off the end. On Oct 8 the same question was asked of this repo. The empty skeleton already loads **24.5 KB**
before any work, and 11.6 KB of that is the `description` of the 14 skills; the three memory files are what grows
with use, and nothing watched them.

**The rule.** The bytes a session loads have a ceiling, and the commit that crosses it says so. `core/budget.py` counts
both `CLAUDE.md` files, the three memory files and every skill description (ceiling 32,000 bytes, about 8k tokens:
the skeleton plus about 7 KB of what you say), and, for opening a project, its root, the 3 newest diary entries and 5
open tasks (ceiling 48,000). The hook blocks a commit only when it makes one of those files **bigger** while the total is
over: a commit that shrinks, or touches something else, always passes, so the way out is never blocked. The fix is
`tools/cool.py`: the older dated lines of a memory file move, word for word, to `memory/archive/`, one link stays
behind, and it writes only with `--apply` and the user's yes (rule 2 of the repo: nothing about the user is rewritten).

**What it does not do.** It does not shorten the skill descriptions, which are the biggest piece (a decision for the
skill author, since each one is what lets Claude know when to use it).

**Who catches it.** `core/budget.py` through `.githooks/pre-commit`.
**The tests.** `tests/test_budget.py` (the ceiling is inclusive and 1 byte over fails; a shrinking commit passes while over;
a skill that grows counts), `tests/test_hook_e2e.py::test_growing_a_loaded_file_over_the_ceiling_blocks_the_commit`,
`tools/test_cool.py` (the whole text is conserved, the archive is never an orphan). 19 mutants (`budget`), 15 (`cool`).

### 15. A new note that says nothing about what it is for (Oct 8)

**What broke.** "The target comes first" lived only in the manual (`vault/CLAUDE.md`): an item is only processed when a file
that already existed changed. Nothing checked it, so the notes born from loose files reached a project 0 times in 43.

**The rule.** A **new** note under `notes/` declares `target:` (a path that exists, or `none`). Without it the commit
only gets a warning: quick capture is never blocked. Whether to block is the user's choice, and it is one line:
`target: block` in `vault/gate.txt`. `target: none` is a real answer, not a way around the check: it says out loud that
the note changes nothing yet.

**Who catches it.** `core/target.py` through `.githooks/pre-commit`; the path itself is judged by `gate.py` (`dead-target`).
**The tests.** `tests/test_target.py` (a note that is only edited, and `inbox/`, `tasks/`, `projects/`, are never asked; the
two modes; a bad mode is rc 2) and the end-to-end cases in `tests/test_hook_e2e.py`. 13 mutants (`target`).

## What is not covered yet

### A regex that cut the extension and fabricated 18 "dead" paths (Sep 6)

The author's checker had a check that verified paths cited in the text, and its regex read `.tsx` as
`.ts`: 18 "dead" paths were that cut. **This template does not have that check** (there are five checks,
and none verifies paths in running text), so there is no rule or test here. It is recorded so it does not
look forgotten: when the check is ported, it comes in with its test.
