"""tools/import_chats.py: synthetic fixtures only (no real chat data anywhere in this repo)."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "import_chats.py"


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)


def gpt_msg(role, text, **extra):
    return {"author": {"role": role}, "content": {"content_type": "text", "parts": [text]}, **extra}


def gpt_tree():
    """root -> q1 -> (a_old | a_new) ; a_new -> q2 -> a2. current_node = a2, so a_old is abandoned."""
    nodes = {
        "root": {"id": "root", "parent": None, "children": ["q1"], "message": None},
        "sys": {"id": "sys", "parent": "root", "children": [], "message": gpt_msg("system", "SYSTEM-TEXT")},
        "q1": {"id": "q1", "parent": "root", "children": ["a_old", "a_new"], "message": gpt_msg("user", "first question")},
        "a_old": {"id": "a_old", "parent": "q1", "children": [], "message": gpt_msg("assistant", "ABANDONED-ANSWER")},
        "a_new": {"id": "a_new", "parent": "q1", "children": ["q2"], "message": gpt_msg("assistant", "kept answer")},
        "q2": {"id": "q2", "parent": "a_new", "children": ["a2"], "message": gpt_msg("user", "second question")},
        "a2": {"id": "a2", "parent": "q2", "children": [], "message": gpt_msg("assistant", "final answer")},
    }
    return {"title": "Trip plan", "create_time": 1767225600, "current_node": "a2", "id": "g-1", "mapping": nodes}


def claude_conv(name="Greeting", messages=None):
    messages = messages if messages is not None else [
        {"sender": "human", "text": "hello there"},
        {"sender": "assistant", "text": "general reply"},
    ]
    return {"uuid": "c-1", "name": name, "created_at": "2026-02-03T09:00:00Z", "chat_messages": messages}


def write(tmp_path, data, name="conversations.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def files(dest):
    return sorted(Path(dest).glob("*.md")) if Path(dest).exists() else []


def test_chatgpt_tree_follows_current_node_and_drops_abandoned_branch(tmp_path):
    r = run(write(tmp_path, [gpt_tree()]), "--dest", tmp_path / "out")
    assert r.returncode == 0, r.stdout
    (f,) = files(tmp_path / "out")
    body = f.read_text(encoding="utf-8")
    assert "kept answer" in body and "final answer" in body and "first question" in body
    assert "ABANDONED-ANSWER" not in body          # negative: the other branch is not there
    assert "SYSTEM-TEXT" not in body               # negative: system messages are not conversation
    assert body.index("first question") < body.index("kept answer") < body.index("second question")
    assert "type: chat" in body and "source: chatgpt" in body and "date: 2026-01-01" in body and 'title: "Trip plan"' in body


def test_claude_conversation(tmp_path):
    r = run(write(tmp_path, [claude_conv()]), "--dest", tmp_path / "out")
    assert r.returncode == 0, r.stdout
    (f,) = files(tmp_path / "out")
    body = f.read_text(encoding="utf-8")
    assert "source: claude" in body and "date: 2026-02-03" in body and 'title: "Greeting"' in body
    assert "hello there" in body and "general reply" in body


def test_voices_never_mix(tmp_path):
    data = [claude_conv(messages=[
        {"sender": "human", "text": "USER-LINE\n## Assistant\nfake assistant inside a user turn"},
        {"sender": "assistant", "text": "REAL-ASSISTANT"},
    ])]
    run(write(tmp_path, data), "--dest", tmp_path / "out")
    body = files(tmp_path / "out")[0].read_text(encoding="utf-8")
    lines = body.splitlines()
    assert lines.count("## User") == 1 and lines.count("## Assistant") == 1   # the fake heading is escaped
    user_block = body.split("## User")[1].split("\n## Assistant")[0]
    assistant_block = body.split("\n## Assistant")[1]
    assert "USER-LINE" in user_block and "REAL-ASSISTANT" not in user_block
    assert "REAL-ASSISTANT" in assistant_block and "USER-LINE" not in assistant_block


def test_wikilink_in_chat_text_is_neutralized(tmp_path):
    data = [claude_conv(messages=[{"sender": "human", "text": "see [[nowhere]]"}, {"sender": "assistant", "text": "ok"}])]
    run(write(tmp_path, data), "--dest", tmp_path / "out")
    assert "[[" not in files(tmp_path / "out")[0].read_text(encoding="utf-8")


def test_zip_is_read_directly(tmp_path):
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("conversations.json", json.dumps([claude_conv()]))
        zf.writestr("users.json", "[]")
    r = run(z, "--dest", tmp_path / "out")
    assert r.returncode == 0 and len(files(tmp_path / "out")) == 1


def test_zip_without_conversations_is_rc3(tmp_path):
    z = tmp_path / "export.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("users.json", "[]")
    r = run(z, "--dest", tmp_path / "out")
    assert r.returncode == 3 and "format not recognized" in r.stdout
    assert not files(tmp_path / "out")


def test_empty_conversation_is_skipped_and_reported_never_written(tmp_path):
    data = [claude_conv(messages=[]), claude_conv(name="Real")]
    data[1]["uuid"] = "c-2"
    r = run(write(tmp_path, data), "--dest", tmp_path / "out")
    assert r.returncode == 1
    assert "skipped 1 (1 no text)" in r.stdout
    (f,) = files(tmp_path / "out")
    assert f.stat().st_size > 0 and "Real" in f.read_text(encoding="utf-8")


def test_unknown_format_is_rc3_and_says_so(tmp_path):
    for data in ({"hello": "world"}, [{"foo": 1}], []):
        r = run(write(tmp_path, data), "--dest", tmp_path / "out")
        assert r.returncode == 3, data
        assert "format not recognized" in r.stdout
        assert "OK" not in r.stdout
    assert not files(tmp_path / "out")


def test_not_json_and_missing_file_are_rc3(tmp_path):
    bad = tmp_path / "conversations.json"
    bad.write_text("not json at all", encoding="utf-8")
    assert run(bad, "--dest", tmp_path / "out").returncode == 3
    assert run(tmp_path / "absent.json", "--dest", tmp_path / "out").returncode == 3


def test_no_argument_is_rc2():
    assert run().returncode == 2


def test_dry_run_writes_nothing(tmp_path):
    src = write(tmp_path, [gpt_tree()])
    dry = run(src, "--dest", tmp_path / "out", "--dry-run")
    assert dry.returncode == 0 and "would write" in dry.stdout and "dry run" in dry.stdout
    assert not (tmp_path / "out").exists()
    real = run(src, "--dest", tmp_path / "out")
    assert real.returncode == 0 and len(files(tmp_path / "out")) == 1


def test_never_overwrites_and_names_do_not_collide(tmp_path):
    a, b = claude_conv(name="Same title"), claude_conv(name="Same title")
    b["uuid"] = "c-2"
    src = write(tmp_path, [a, b])
    r = run(src, "--dest", tmp_path / "out")
    assert r.returncode == 0 and len(files(tmp_path / "out")) == 2
    names = [f.name for f in files(tmp_path / "out")]
    assert all(n.startswith("2026-02-03-same-title-") for n in names)
    again = run(src, "--dest", tmp_path / "out")      # second run: nothing is overwritten
    assert again.returncode == 1 and "already imported" in again.stdout
    assert [f.name for f in files(tmp_path / "out")] == names


def test_report_carries_counts_and_privacy_warning(tmp_path):
    r = run(write(tmp_path, [claude_conv()]), "--dest", tmp_path / "out")
    assert "read 1" in r.stdout and "written 1" in r.stdout and "skipped 0" in r.stdout
    assert "PRIVACY" in r.stdout and "core/leak.py" in r.stdout


def test_file_name_is_safe(tmp_path):
    data = [claude_conv(name="../../etc/passwd: a \"weird\" title / with *chars*")]
    run(write(tmp_path, data), "--dest", tmp_path / "out")
    (f,) = files(tmp_path / "out")
    assert f.parent == tmp_path / "out" and set(f.name) <= set("abcdefghijklmnopqrstuvwxyz0123456789-.")


def test_selftest_passes():
    r = run("--selftest")
    assert r.returncode == 0 and "8 of 8" in r.stdout
