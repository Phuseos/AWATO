import pytest

from awato.__main__ import main
from awato.loader import ContentError, load_content, parse_comparison, parse_time


def errors(content):
    return [str(p) for p in content.problems if p.level == "error"]


def test_shipped_content_has_no_errors(content):
    assert errors(content) == []


def test_original_texts_are_kept(content):
    assert content.tickets["not_working"].text == "It's not working! I've tried nothing and I'm all out of ideas!"
    assert len(content.quick_fix_texts) == 5
    assert content.t("name_too_short") == "Names that short are against office protocols!"
    assert content.title == "A Week At The Office"


def test_parse_helpers():
    assert parse_time("9:00") == 540
    assert parse_time("17:30") == 1050
    assert parse_comparison(">= 50") == (">=", 50)
    assert parse_comparison(3) == (">=", 3)
    with pytest.raises(ValueError):
        parse_time("25:00")
    with pytest.raises(ValueError):
        parse_comparison("about 5")


@pytest.mark.parametrize("rel, update, message", [
    ("events/monday.yaml", lambda d: d["monday_morning"].update(triger="day_start"), "unknown key 'triger'"),
    ("events/monday.yaml", lambda d: d["monday_lunch"]["effects"].update(event="nope"), "unknown event 'nope'"),
    ("events/monday.yaml", lambda d: d["monday_lunch"]["when"].update(after="noon"), "is not a time"),
    ("events/monday.yaml", lambda d: d["monday_morning"]["choices"][0]["effects"].update(stats={"trsut": 5}), "unknown key 'trsut'"),
    ("events/monday.yaml", lambda d: d["monday_morning"]["pages"][0].update(text="Hello {name"), "unbalanced"),
    ("endings.yaml", lambda d: d["survived"].update(when={"day": 5}), "the last 'final' ending must have no 'when'"),
    ("tickets.yaml", lambda d: d["tickets"]["haunted"].update(when={"stats": {"funds": "lots"}}), "is not a comparison"),
])
def test_validator_catches_mistakes(content_copy, rel, update, message):
    root, patch = content_copy
    patch(rel, update)
    content = load_content(root, strict=False)
    assert any(message in e for e in errors(content)), errors(content)
    with pytest.raises(ContentError):
        load_content(root)


def test_validator_warns_about_unset_flags_and_placeholders(content_copy):
    root, patch = content_copy
    patch("events/monday.yaml", lambda d: d["monday_lunch"].update(
        when={"day": 1, "flags": "never_set"}, pages=["Hi {nmae}"]))
    warnings = [str(p) for p in load_content(root, strict=False).problems if p.level == "warning"]
    assert any("'never_set' is checked but nothing ever sets it" in w for w in warnings)
    assert any("unknown placeholder {nmae}" in w for w in warnings)


def test_yaml_syntax_error_is_reported(content_copy):
    root, _ = content_copy
    (root / "shop.yaml").write_text("hire:\n  name: [unclosed\n")
    assert any("YAML syntax error" in e for e in errors(load_content(root, strict=False)))


def test_check_command(capsys):
    assert main(["--check"]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_missing_music_file_is_a_warning(content_copy):
    root, patch = content_copy
    patch("config.yaml", lambda d: d["music"].update(theme="music/nope.mp3"))
    content = load_content(root, strict=False)
    assert content.music_path is None
    assert any("nope.mp3" in str(p) and p.level == "warning" for p in content.problems)
