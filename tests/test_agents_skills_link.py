"""`sh install.sh` links `.agents/skills` to `.claude/skills` for agents that only look there.

The rule under test is the second half: the installer never replaces or deletes a `.agents/skills`
that is already there. A step that "fixes" someone else's folder is the failure this test exists for.
"""
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _clone(tmp_path):
    dest = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(dest)], check=True)
    # the working tree under test may be ahead of HEAD: take the installer as it is on disk
    shutil.copy(ROOT / "install.sh", dest / "install.sh")
    return dest


def _install(dest):
    return subprocess.run(["sh", "install.sh"], cwd=dest, capture_output=True, text=True)


OK_LINE = "Skills for other agents: .agents/skills is linked to .claude/skills"


def _hook_is_active(dest):
    r = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=dest, capture_output=True, text=True)
    return r.stdout.strip() == ".githooks"


def _points_at_the_skills(dest):
    link = dest / ".agents" / "skills"
    return link.is_symlink() and link.resolve() == (dest / ".claude" / "skills").resolve()


def test_install_creates_the_link_and_git_does_not_see_it(tmp_path):
    dest = _clone(tmp_path)
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert _points_at_the_skills(dest) and (dest / ".agents" / "skills" / "cf-onboard" / "SKILL.md").is_file()
    assert OK_LINE in r.stdout and "NOTE:" not in r.stdout
    status = subprocess.run(["git", "status", "--porcelain", "--", ".agents"], cwd=dest, capture_output=True, text=True)
    assert status.stdout == "", status.stdout


def test_running_it_twice_keeps_the_link_and_says_the_same(tmp_path):
    dest = _clone(tmp_path)
    first = _install(dest)
    second = _install(dest)
    assert second.returncode == 0, second.stderr
    assert _points_at_the_skills(dest)
    assert OK_LINE in second.stdout and "NOTE:" not in second.stdout
    assert [l for l in first.stdout.splitlines() if "agents" in l] == [l for l in second.stdout.splitlines() if "agents" in l]
    excl = (dest / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert excl.count("/.agents/skills") == 1, excl


def test_install_leaves_an_existing_agents_skills_folder_alone_and_git_still_sees_it(tmp_path):
    dest = _clone(tmp_path)
    mine = dest / ".agents" / "skills" / "someone-elses"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("not ours\n", encoding="utf-8")
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert not (dest / ".agents" / "skills").is_symlink()
    assert (mine / "SKILL.md").read_text(encoding="utf-8") == "not ours\n"
    assert "left alone" in r.stdout and OK_LINE not in r.stdout
    status = subprocess.run(["git", "status", "--porcelain", "--", ".agents"], cwd=dest, capture_output=True, text=True)
    assert ".agents" in status.stdout, "the user's own folder must not be hidden from git"


def test_install_leaves_a_plain_file_at_agents_skills_alone(tmp_path):
    dest = _clone(tmp_path)
    (dest / ".agents").mkdir()
    (dest / ".agents" / "skills").write_text("mine\n", encoding="utf-8")
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    f = dest / ".agents" / "skills"
    assert f.is_file() and not f.is_symlink() and f.read_text(encoding="utf-8") == "mine\n"
    assert "left alone" in r.stdout and OK_LINE not in r.stdout


def test_install_leaves_a_link_that_points_elsewhere_alone(tmp_path):
    dest = _clone(tmp_path)
    (dest / ".agents").mkdir()
    (dest / ".agents" / "skills").symlink_to("../somewhere-else")
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert (dest / ".agents" / "skills").readlink() == Path("../somewhere-else")
    assert "left alone" in r.stdout and OK_LINE not in r.stdout


def test_a_link_to_the_same_folder_written_another_way_counts_as_ours(tmp_path):
    dest = _clone(tmp_path)
    (dest / ".agents").mkdir()
    (dest / ".agents" / "skills").symlink_to(dest / ".claude" / "skills")  # absolute, not ../.claude/skills
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert OK_LINE in r.stdout and "NOTE:" not in r.stdout


def test_install_does_not_write_through_an_agents_folder_that_is_a_link(tmp_path):
    dest = _clone(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (dest / ".agents").symlink_to(outside)
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert list(outside.iterdir()) == [], "the installer wrote outside the repo"
    assert "left alone" in r.stdout and OK_LINE not in r.stdout


def test_a_failure_in_this_step_does_not_undo_the_installation(tmp_path):
    dest = _clone(tmp_path)
    (dest / ".agents").write_text("a file where the folder would go\n", encoding="utf-8")
    r = _install(dest)
    assert r.returncode == 0, r.stderr
    assert _hook_is_active(dest)
    assert "was not created" in r.stdout and OK_LINE not in r.stdout
    assert "hook active" in r.stdout


def test_a_failed_team_setup_leaves_no_link_behind(tmp_path):
    dest = _clone(tmp_path)
    (dest / "vault" / "roles.txt").write_text("someone admin a@b.c\n", encoding="utf-8")
    subprocess.run(["git", "config", "user.email", "x@example.com"], cwd=dest, check=True)
    r = subprocess.run(["sh", "install.sh", "--team", "ana"], cwd=dest, capture_output=True, text=True)
    assert r.returncode != 0
    assert not (dest / ".agents").exists()
