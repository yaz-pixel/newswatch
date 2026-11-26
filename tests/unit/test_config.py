from pathlib import Path

import pytest

from newswatch.config import load_sources

SOURCES = Path(__file__).parent.parent.parent / "config" / "sources.yaml"


def test_sources_registry_is_valid() -> None:
    sources = load_sources(SOURCES)
    assert 30 <= len(sources) <= 60
    assert len({s.source_id for s in sources}) == len(sources)
    assert all(s.rss_url.startswith(("http://", "https://")) for s in sources)


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "sources.yaml"
    bad.write_text(
        "sources:\n"
        "  - {source_id: a, name: A, rss_url: 'https://a.com/rss'}\n"
        "  - {source_id: a, name: B, rss_url: 'https://b.com/rss'}\n"
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_sources(bad)
