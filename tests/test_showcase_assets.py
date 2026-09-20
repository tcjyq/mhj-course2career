from pathlib import Path

SHOWCASE_ROOT = Path("showcase")


def test_showcase_has_required_public_links_and_real_screenshot() -> None:
    page = (SHOWCASE_ROOT / "public" / "index.html").read_text(encoding="utf-8")

    assert "https://mhj-course2career.streamlit.app" in page
    assert "https://github.com/tcjyq/mhj-course2career" in page
    assert "https://god97.tcjyq.cc" in page
    assert "/course2career-home.png" in page
    assert (SHOWCASE_ROOT / "public" / "course2career-home.png").read_bytes() == Path(
        "screenshots/home.png"
    ).read_bytes()


def test_showcase_worker_is_static_and_binds_the_custom_domain() -> None:
    config = (SHOWCASE_ROOT / "wrangler.jsonc").read_text(encoding="utf-8")
    worker = (SHOWCASE_ROOT / "src" / "worker.js").read_text(encoding="utf-8")

    assert '"pattern": "course2career.tcjyq.cc"' in config
    assert '"custom_domain": true' in config
    assert '"directory": "./public"' in config
    assert '"run_worker_first": true' in config
    assert "env.ASSETS.fetch(request)" in worker
    assert "script-src 'self' https://static.cloudflareinsights.com" in worker
    assert "connect-src 'self' https://cloudflareinsights.com" in worker


def test_showcase_has_crawler_entry_points() -> None:
    robots = (SHOWCASE_ROOT / "public" / "robots.txt").read_text(encoding="utf-8")
    sitemap = (SHOWCASE_ROOT / "public" / "sitemap.xml").read_text(encoding="utf-8")

    assert "https://course2career.tcjyq.cc/sitemap.xml" in robots
    assert "https://course2career.tcjyq.cc/" in sitemap
