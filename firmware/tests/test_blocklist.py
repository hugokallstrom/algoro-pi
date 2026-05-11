from pathlib import Path
from slopstop.blocklist import (
    add_domain,
    remove_domain,
    list_domains,
    export_to_file,
)


def test_add_and_list_domain(db_path: Path) -> None:
    add_domain("instagram.com", db_path)
    domains = list_domains(db_path)
    assert len(domains) == 1
    assert domains[0]["domain"] == "instagram.com"


def test_add_domain_normalises_whitespace_and_case(db_path: Path) -> None:
    add_domain("  Instagram.COM  ", db_path)
    domains = list_domains(db_path)
    assert domains[0]["domain"] == "instagram.com"


def test_add_domain_strips_trailing_dot(db_path: Path) -> None:
    add_domain("reddit.com.", db_path)
    assert list_domains(db_path)[0]["domain"] == "reddit.com"


def test_add_domain_is_idempotent(db_path: Path) -> None:
    add_domain("twitter.com", db_path)
    add_domain("twitter.com", db_path)
    assert len(list_domains(db_path)) == 1


def test_remove_domain(db_path: Path) -> None:
    add_domain("tiktok.com", db_path)
    remove_domain("tiktok.com", db_path)
    assert list_domains(db_path) == []


def test_remove_nonexistent_domain_does_not_raise(db_path: Path) -> None:
    remove_domain("nothere.com", db_path)  # must not raise


def test_export_writes_enabled_domains(db_path: Path, tmp_path: Path) -> None:
    add_domain("instagram.com", db_path)
    add_domain("tiktok.com", db_path)
    out = tmp_path / "blocklist.txt"
    export_to_file(db_path, out)
    lines = out.read_text().splitlines()
    assert "instagram.com" in lines
    assert "tiktok.com" in lines


def test_export_empty_blocklist_writes_empty_file(db_path: Path, tmp_path: Path) -> None:
    out = tmp_path / "blocklist.txt"
    export_to_file(db_path, out)
    assert out.read_text() == ""


def test_add_domain_stores_preset(db_path: Path) -> None:
    add_domain("facebook.com", db_path, preset="social_only")
    domains = list_domains(db_path)
    assert domains[0]["preset"] == "social_only"
