from __future__ import annotations

import json
import re
from pathlib import Path

import padelkit

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_CONFIG_PATH = DOCS_DIR / "docs.config.json"
ICONS_DIR = DOCS_DIR / "icons"
SCHEMATICS_DIR = DOCS_DIR / "images" / "schematics"


def _extract_pyproject_version() -> str:
    raw = PYPROJECT_PATH.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', raw, re.MULTILINE)
    assert match is not None, "Could not find version in pyproject.toml"
    return match.group(1)


def test_version_consistency_across_repo() -> None:
    pyproject_version = _extract_pyproject_version()

    # 1. Runtime __version__ matches pyproject.toml
    assert padelkit.__version__ == pyproject_version

    # 2. CHANGELOG.md has an entry for the current version
    changelog = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert f"## [{pyproject_version}]" in changelog, (
        f"CHANGELOG.md must contain a section '## [{pyproject_version}]'"
    )

    # 3. docs/docs.config.json includes the current version in "versions"
    docs_config = json.loads(DOCS_CONFIG_PATH.read_text(encoding="utf-8"))
    versions = docs_config.get("versions", [])
    assert pyproject_version in versions, (
        f"docs/docs.config.json 'versions' ({versions}) must include "
        f"current version '{pyproject_version}'"
    )


def test_docs_config_routes_and_icons_integrity() -> None:
    docs_config = json.loads(DOCS_CONFIG_PATH.read_text(encoding="utf-8"))
    versions = set(docs_config.get("versions", []))
    pages = docs_config.get("pages", {})
    assert "/" in pages, "Root page '/' must be registered in docs.config.json"

    available_icons = {p.stem for p in ICONS_DIR.glob("*.tsx")}

    for route, meta in pages.items():
        assert route.startswith("/"), f"Page route '{route}' must start with '/'"
        assert meta.get("title"), f"Page '{route}' is missing a 'title'"
        assert meta.get("description"), f"Page '{route}' is missing a 'description'"

        # Verify corresponding MDX file exists
        mdx_path = (
            DOCS_DIR / "page.mdx"
            if route == "/"
            else DOCS_DIR / route.lstrip("/") / "page.mdx"
        )
        assert mdx_path.is_file(), (
            f"Page '{route}' registered in docs.config.json is missing "
            f"MDX file at {mdx_path.relative_to(REPO_ROOT)}"
        )

        # Verify version constraints reference declared versions
        if "min" in meta:
            assert meta["min"] in versions, (
                f"Page '{route}' has 'min': '{meta['min']}' which is not "
                f"in docs.config.json 'versions'"
            )
        if "max" in meta:
            assert meta["max"] in versions, (
                f"Page '{route}' has 'max': '{meta['max']}' which is not "
                f"in docs.config.json 'versions'"
            )

        # Verify custom icon exists if specified
        if "icon" in meta:
            icon_name = meta["icon"]
            assert icon_name in available_icons, (
                f"Page '{route}' references unknown icon '{icon_name}'. "
                f"Available icons in docs/icons/: {sorted(available_icons)}"
            )

    # Verify all navigation links point to registered pages
    for group in docs_config.get("navigation", []):
        assert group.get("title"), "Navigation group is missing a 'title'"
        for link in group.get("links", []):
            assert link in pages, (
                f"Navigation link '{link}' in group '{group['title']}' "
                f"is not registered in 'pages'"
            )

    # Verify all intro_cards links point to registered pages
    intro_cards = docs_config.get("intro_cards", {})
    for section in ("guides", "resources"):
        for link in intro_cards.get(section, []):
            assert link in pages, (
                f"intro_cards.{section} entry '{link}' is not registered in 'pages'"
            )


def test_mdx_files_conventions_and_schematics() -> None:
    docs_config = json.loads(DOCS_CONFIG_PATH.read_text(encoding="utf-8"))
    pages = docs_config.get("pages", {})
    mdx_files = sorted(DOCS_DIR.rglob("page.mdx"))
    assert len(mdx_files) > 0

    for mdx_path in mdx_files:
        rel_dir = mdx_path.parent.relative_to(DOCS_DIR)
        route = "/" if str(rel_dir) == "." else f"/{rel_dir.as_posix()}"
        assert route in pages, (
            f"Orphan MDX file '{mdx_path.relative_to(REPO_ROOT)}' is not "
            f"registered under 'pages' in docs/docs.config.json"
        )

        content = mdx_path.read_text(encoding="utf-8")
        # Rule 1: Never include manual Next.js metadata export
        assert not re.search(r"export\s+const\s+metadata\s*=", content), (
            f"{mdx_path.relative_to(REPO_ROOT)} contains 'export const metadata'. "
            f"Remove it: metadata is injected automatically from docs.config.json."
        )

        # Rule 2: Every <Schematic name="..." /> must have matching light & dark SVGs
        for match in re.finditer(r'<Schematic[^>]*\bname="([^"]+)"', content):
            name = match.group(1)
            light_svg = SCHEMATICS_DIR / f"{name}-light.svg"
            dark_svg = SCHEMATICS_DIR / f"{name}-dark.svg"
            assert light_svg.is_file() and dark_svg.is_file(), (
                f"{mdx_path.relative_to(REPO_ROOT)} references "
                f'<Schematic name="{name}" />, but {light_svg.name} or '
                f"{dark_svg.name} is missing in docs/images/schematics/"
            )
