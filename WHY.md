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
**The test.** `mutate.py` itself. Result today: **105 of 105 mutants killed, 0 alive** (Oct 3).

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

## What is not covered yet

### A regex that cut the extension and fabricated 18 "dead" paths (Sep 6)

The author's checker had a check that verified paths cited in the text, and its regex read `.tsx` as
`.ts`: 18 "dead" paths were that cut. **This template does not have that check** (there are five checks,
and none verifies paths in running text), so there is no rule or test here. It is recorded so it does not
look forgotten: when the check is ported, it comes in with its test.
