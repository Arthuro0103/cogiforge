"""The cf-help skill: it only reads, it knows the person only from what they said, and it never carries a list of skills."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude/skills/cf-help/SKILL.md"
NAME = re.compile(r"cf-[a-z]+(?:-[a-z]+)*")


def skill():
    return SKILL.read_text(encoding="utf-8")


def fixed_names(text):
    """Distinct cf-* names the text carries, not counting cf-help itself."""
    return {n for n in NAME.findall(text)} - {"cf-help"}


def test_frontmatter_has_name_triggers_and_do_not_trigger():
    fm = skill().split("---")[1]
    assert re.search(r"^name: cf-help$", fm, re.M)
    assert "TRIGGERS" in fm and "Do NOT trigger" in fm
    for en, pt in (("how do I use", "como uso"), ("which skill", "qual skill")):
        assert en in fm and pt in fm
    assert "Writes nothing" in fm


def test_it_only_reads_and_has_no_instruction_to_write():
    t = skill()
    assert "1. **Read only.** Writes no file and makes no commit" in t
    assert "- Write, edit or commit anything." in t
    code = "\n".join(re.findall(r"```bash\n(.*?)```", t, re.S))
    assert code, "no shell block found: NOT_VERIFIED, not OK"
    # No shell write in the commands: no redirect into a file (2>/dev/null is fine), no tee, no git add/commit, no rm/mv/cp.
    assert not re.search(r">>?\s*(?!/dev/null)[\w./~$]", code)
    assert not re.search(r"\b(tee|git add|git commit|rm|mv|cp)\b ", code)


def test_the_person_comes_only_from_the_profile_and_the_answers():
    t = skill()
    assert "vault/memory/profile.md" in t and "vault/_questions_about_me.md" in t
    assert "Quote the phrase when you use it." in t


def test_it_never_deduces_anything_about_the_person():
    t = skill()
    assert "3. **Never deduce anything about the person**" in t
    assert "If it was not said, it is not used." in t
    assert "- Say something about the person that they did not say." in t


def test_what_exists_is_counted_not_guessed():
    t = skill()
    assert "4. **What exists is counted, not guessed**" in t
    for needle in ("vault/projects/", "vault/tasks/", "vault/notes", "vault/roles.txt", "vault/memory/diary/",
                   "ask-log.jsonl", "study-plan.md"):
        assert needle in t, needle


def test_the_skill_list_comes_from_the_disk_not_from_the_file():
    t = skill()
    assert "ls .claude/skills/*/SKILL.md" in t
    assert "This file holds no list of skills." in t
    assert "Never describe a skill from memory." in t
    assert len(fixed_names(t)) < 5, sorted(fixed_names(t))


def test_the_fixed_names_guard_catches_a_planted_list():
    planted = skill() + "\ncf-study cf-ask cf-brand cf-adopt cf-new-rule\n"
    assert len(fixed_names(planted)) >= 5


def test_it_has_the_detail_mode():
    t = skill()
    assert "`/cf-help <skill>`: **detail mode**" in t
    assert "### 5. Detail mode" in t
    assert "the closest names" in t
    assert "when NOT to use it" in t


def test_an_empty_profile_sends_to_onboard_with_one_question():
    t = skill()
    assert "### 3. Empty profile" in t
    assert "recommend `/cf-onboard` first" in t
    assert "What do you want to do here first?" in t
    assert "6. **At most one question before answering**" in t


def test_the_tables_say_it_writes_nothing_and_the_plugin_notes_say_17():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    row = next(l for l in readme.splitlines() if l.startswith("| `/cf-help"))
    assert row.rstrip().endswith("| Nothing (read only). |")          # tied to rule 1 of the skill ("Read only.")
    leia = next(l for l in (ROOT / "LEIA-ME.md").read_text(encoding="utf-8").splitlines() if l.startswith("| `/cf-help"))
    assert leia.rstrip().endswith("| Nada (só lê). |")
    assert re.search(r"^\| `cf-help` \|.*Writes nothing", (ROOT / "AGENTS.md").read_text(encoding="utf-8"), re.M)
    assert "The 17 skills live inside each workbench" in readme       # the plugin's version (0.1.1) has 17
    assert "does not have `/cf-help` yet" in readme
