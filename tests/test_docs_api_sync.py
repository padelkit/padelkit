from __future__ import annotations

import ast
import dataclasses
import inspect
import json
import re
import textwrap
from enum import Enum
from pathlib import Path
from typing import Any

import padelkit

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src" / "padelkit"
DOCS_DIR = REPO_ROOT / "docs"
DOCS_CONFIG_PATH = DOCS_DIR / "docs.config.json"

ALLOWED_HEADING_TAGS = {
    "class",
    "dataclass",
    "enum",
    "constant",
    "constructor",
    "fields",
    "property",
    "classmethod",
    "method",
    "guide",
    "schema",
    "cli",
}

GUIDE_ROUTES = {
    "/quickstart",
    "/court-geometry",
    "/camera-system",
    "/ball-physics",
    "/visualization-3d",
    "/stroke-library",
    "/scoring-system",
    "/match-format",
}

CLASS_API_ROUTES: dict[str, str] = {
    # padelkit.court
    "/court": "Court",
    "/court-dimensions": "CourtDimensions",
    "/court-location": "CourtLocation",
    "/side-access": "SideAccess",
    "/safety-zone": "SafetyZone",
    "/side-enclosure-panel": "SideEnclosurePanel",
    "/side-enclosure-segment": "SideEnclosureSegment",
    # padelkit.camera
    "/camera": "Camera",
    "/camera-intrinsics": "CameraIntrinsics",
    "/camera-extrinsics": "CameraExtrinsics",
    "/camera-distortion": "CameraDistortion",
    # padelkit.physics
    "/ball-physics-engine": "BallPhysicsEngine",
    "/ball-state": "BallState",
    "/ball-trajectory": "BallTrajectory",
    "/bounce-event": "BounceEvent",
    "/ball-properties": "BallProperties",
    "/environment-conditions": "EnvironmentConditions",
    "/surface-materials": "SurfaceMaterials",
    # padelkit.scoring
    "/match": "Match",
    "/match-configuration": "MatchConfiguration",
    "/match-score": "MatchScore",
    "/match-score-history": "MatchScoreHistory",
    "/team": "Team",
    "/player": "Player",
    "/serving-state": "ServingState",
    "/serving-engine": "ServingEngine",
    # padelkit.viz
    "/padel-visualizer": "PadelVisualizer",
    "/match-timeline": "MatchTimeline",
    "/frame-state": "FrameState",
    "/player-pose": "PlayerPose",
}

ENUM_CONSTANT_ROUTES: dict[str, str] = {
    "CourtLandmark": "/court-landmark",
    "CoordinateSystem": "/court-enums",
    "EnclosureType": "/court-enums",
    "EnclosureVariant": "/court-enums",
    "SideWallProfile": "/court-enums",
    "CourtSurfaceColor": "/court-enums",
    "CourtOrientation": "/court-enums",
    "DoorState": "/court-enums",
    "CourtSetting": "/court-enums",
    "CameraPreset": "/camera-enums",
    "DistortionModel": "/camera-enums",
    "BallColor": "/physics-enums",
    "SurfaceType": "/physics-enums",
    "ContactRegime": "/physics-enums",
    "TeamId": "/scoring-enums",
    "H36M_JOINT_NAMES": "/viz-constants",
}


def _route_to_mdx_path(route: str) -> Path:
    return (
        DOCS_DIR / "page.mdx"
        if route == "/"
        else DOCS_DIR / route.lstrip("/") / "page.mdx"
    )


def _strip_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _decamelize_and_slugify(title: str) -> str:
    """Approximates `@sindresorhus/slugify` for MDX H2 heading anchor validation."""
    clean = re.sub(r"\s*\{\{[^}]*\}\}\s*$", "", title).replace("`", "").strip()
    clean = clean.replace("&", " and ")
    clean = re.sub(r"([a-z\d])([A-Z])", r"\1-\2", clean)
    clean = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", clean)
    clean = clean.lower()
    clean = re.sub(r"[^a-z0-9]+", "-", clean).strip("-")
    return clean


def _collect_h2_anchors(content: str) -> set[str]:
    no_code = _strip_fenced_code(content)
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in no_code.splitlines():
        m = re.match(r"^##\s+(.+)$", line)
        if not m:
            continue
        base = _decamelize_and_slugify(m.group(1))
        idx = counts.get(base, 0)
        counts[base] = idx + 1
        anchors.add(base if idx == 0 else f"{base}-{idx}")
    return anchors


def _split_h2_sections(content: str) -> list[tuple[str, str | None, str]]:
    """Splits an MDX document into `(heading_title, tag, body)` for each H2 block."""
    no_code = _strip_fenced_code(content)
    lines = no_code.splitlines()
    sections: list[tuple[str, str | None, list[str]]] = []
    cur_title: str | None = None
    cur_tag: str | None = None
    cur_lines: list[str] = []

    for line in lines:
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if cur_title is not None:
                sections.append((cur_title, cur_tag, cur_lines))
            raw = m.group(1)
            tag_m = re.search(r"tag:\s*['\"]([a-zA-Z0-9_-]+)['\"]", raw)
            cur_tag = tag_m.group(1) if tag_m else None
            cur_title = re.sub(r"\s*\{\{[^}]*\}\}\s*$", "", raw).strip()
            cur_lines = []
        elif cur_title is not None:
            cur_lines.append(line)

    if cur_title is not None:
        sections.append((cur_title, cur_tag, cur_lines))

    return [(t, tag, "\n".join(body)) for t, tag, body in sections]


def _init_assigned_attributes(cls: type[Any]) -> set[str]:
    """Collects attributes assigned to `self.<attr>` inside `cls.__init__`."""
    assigned: set[str] = set()
    init_fn = cls.__dict__.get("__init__")
    if init_fn is None:
        return assigned
    try:
        src = inspect.getsource(init_fn)
    except OSError:
        return assigned
    dedented = textwrap.dedent(src)
    tree = ast.parse(dedented)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    assigned.add(target.attr)
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "self"
            ):
                assigned.add(target.attr)
    return assigned


def test_all_public_symbols_documented() -> None:
    """Every symbol exported in `padelkit.__all__` must have dedicated docs."""
    public_symbols = {name for name in padelkit.__all__ if name != "__version__"}
    mapped_classes = set(CLASS_API_ROUTES.values())
    mapped_enums = set(ENUM_CONSTANT_ROUTES.keys())

    assert len(CLASS_API_ROUTES) == len(mapped_classes), (
        "Each class page must map 1:1 to a distinct symbol."
    )
    assert mapped_classes.isdisjoint(mapped_enums)
    assert (mapped_classes | mapped_enums) == public_symbols, (
        "padelkit.__all__ and docs API mapping drifted! "
        f"Undocumented: {sorted(public_symbols - mapped_classes - mapped_enums)}; "
        f"Extra in test map: {sorted((mapped_classes | mapped_enums) - public_symbols)}"
    )

    docs_config = json.loads(DOCS_CONFIG_PATH.read_text(encoding="utf-8"))
    registered_pages = docs_config.get("pages", {})

    for route, sym_name in CLASS_API_ROUTES.items():
        assert route in registered_pages, f"Missing '{route}' in docs.config.json"
        mdx = _route_to_mdx_path(route)
        assert mdx.is_file(), f"Missing MDX file for {sym_name}: {mdx}"
        first_h1 = next(
            (ln for ln in mdx.read_text(encoding="utf-8").splitlines() if ln.strip()),
            "",
        )
        assert first_h1 == f"# {sym_name}", (
            f"{mdx.name} must start with '# {sym_name}' (found {first_h1!r})"
        )

    for sym_name, route in ENUM_CONSTANT_ROUTES.items():
        assert route in registered_pages, f"Missing '{route}' in docs.config.json"
        content = _route_to_mdx_path(route).read_text(encoding="utf-8")
        obj = getattr(padelkit, sym_name)
        if sym_name == "CourtLandmark":
            assert "# CourtLandmark" in content
        else:
            assert re.search(
                rf"^##\s+`?{re.escape(sym_name)}`?\s*(?:\{{\{{|\Z|$)",
                content,
                re.MULTILINE,
            ), f"Expected H2 section for '{sym_name}' in {route}/page.mdx"

        if inspect.isclass(obj) and issubclass(obj, Enum):
            for member_name in obj.__members__:
                assert f"{sym_name}.{member_name}" in content, (
                    f"Enum member '{sym_name}.{member_name}' is not documented "
                    f"in {route}/page.mdx"
                )
        elif sym_name == "H36M_JOINT_NAMES":
            for joint_name in obj:
                assert f'"{joint_name}"' in content, (
                    f"Joint '{joint_name}' from H36M_JOINT_NAMES missing in {route}"
                )


def test_api_pages_match_python_runtime() -> None:
    """Verify Nivel 1 introspection parity for documented fields, props & methods."""
    for route, sym_name in CLASS_API_ROUTES.items():
        cls = getattr(padelkit, sym_name)
        content = _route_to_mdx_path(route).read_text(encoding="utf-8")
        sections = _split_h2_sections(content)

        is_dc = dataclasses.is_dataclass(cls)
        dc_field_names = {f.name for f in dataclasses.fields(cls)} if is_dc else set()
        init_params = {
            p
            for p in inspect.signature(cls.__init__).parameters
            if p not in ("self", "args", "kwargs")
        }
        init_attrs = _init_assigned_attributes(cls)
        cls_props = {
            name for name, val in inspect.getmembers(cls) if isinstance(val, property)
        }

        documented_dc_fields: set[str] = set()

        for title, tag, body in sections:
            # Strip subsections like ### Arguments / ### Returns from field checks
            top_body = re.split(r"^###\s+", body, maxsplit=1, flags=re.MULTILINE)[0]
            prop_names = re.findall(r'<Property\s+name="([^"]+)"', top_body)

            if tag in ("dataclass", "constructor", "fields", "property"):
                for raw_name in prop_names:
                    attr = raw_name.split("(", 1)[0].strip()
                    if tag == "dataclass":
                        assert attr in dc_field_names, (
                            f"{sym_name}: documented dataclass field '{attr}' "
                            f"not in {sorted(dc_field_names)}"
                        )
                        documented_dc_fields.add(attr)
                    elif tag == "constructor":
                        assert attr in init_params, (
                            f"{sym_name}: constructor arg '{attr}' not in "
                            f"__init__ signature {sorted(init_params)}"
                        )
                    elif tag == "fields":
                        valid = init_attrs | dc_field_names | set(cls.__dict__)
                        assert attr in valid, (
                            f"{sym_name}: attribute '{attr}' not found on class"
                        )
                    elif tag == "property":
                        assert attr in cls_props, (
                            f"{sym_name}: documented property '{attr}' "
                            f"is not a @property on {sym_name}"
                        )

            if tag in ("method", "classmethod"):
                # Verify backticked method names in H2 titles and any <Property> calls
                for token in re.findall(r"`([A-Za-z_][A-Za-z0-9_]*)(?:\(\))?`", title):
                    assert hasattr(cls, token), (
                        f"{sym_name}: H2 mentions '{token}' on {route}, "
                        f"but {sym_name}.{token} does not exist"
                    )
                for raw_name in prop_names:
                    if "(" in raw_name:
                        m_name = raw_name.split("(", 1)[0].strip()
                        assert hasattr(cls, m_name), (
                            f"{sym_name}: method '{m_name}' listed in {route} "
                            f"does not exist on {sym_name}"
                        )

        if is_dc and any(tag == "dataclass" for _, tag, _ in sections):
            assert documented_dc_fields == dc_field_names, (
                f"{sym_name}: incomplete dataclass docs! "
                f"Missing: {sorted(dc_field_names - documented_dc_fields)}"
            )


def test_diataxis_and_editorial_contract() -> None:
    """Enforce Guide vs API separation, closed tag palette, and IDE hygiene."""
    assert (SRC_DIR / "py.typed").is_file(), (
        "PEP 561 marker src/padelkit/py.typed must exist for downstream IDE/LSP hints."
    )

    for py_path in sorted(SRC_DIR.rglob("*.py")):
        src_text = py_path.read_text(encoding="utf-8")
        assert not re.search(
            r":(?:class|attr|meth|func|mod):`|\.\. code-block::", src_text
        ), f"Sphinx directive leaked into {py_path.relative_to(REPO_ROOT)}"

    for mdx_path in sorted(DOCS_DIR.rglob("page.mdx")):
        rel_dir = mdx_path.parent.relative_to(DOCS_DIR)
        route = "/" if str(rel_dir) == "." else f"/{rel_dir.as_posix()}"
        content = mdx_path.read_text(encoding="utf-8")
        no_code = _strip_fenced_code(content)

        if route in GUIDE_ROUTES:
            assert "<Properties" not in no_code and "<Property " not in no_code, (
                f"Diataxis violation in Guide '{route}': Guides must explain "
                "concepts and link to API Reference rather than embedding "
                "<Properties>/<Property> blocks."
            )

        for tag_match in re.finditer(
            r"^##\s+.+?\btag:\s*['\"]([^'\"]+)['\"]", no_code, re.MULTILINE
        ):
            tag = tag_match.group(1)
            assert tag in ALLOWED_HEADING_TAGS, (
                f"{mdx_path.relative_to(REPO_ROOT)} uses unsupported tag '{tag}'. "
                f"Allowed tags: {sorted(ALLOWED_HEADING_TAGS)}"
            )


def test_mdx_links_anchors_and_jsx() -> None:
    """Verify internal route/anchor links, intro_cards uniqueness, and balanced JSX."""
    docs_config = json.loads(DOCS_CONFIG_PATH.read_text(encoding="utf-8"))
    pages = docs_config.get("pages", {})
    intro = docs_config.get("intro_cards", {})
    guide_cards = intro.get("guides", [])
    resource_cards = intro.get("resources", [])

    assert len(guide_cards) == len(set(guide_cards)), "Duplicate routes in guides cards"
    assert len(resource_cards) == len(set(resource_cards)), (
        "Duplicate routes in resources cards"
    )
    assert set(guide_cards).isdisjoint(set(resource_cards)), (
        f"Routes duplicated across intro_cards.guides and resources: "
        f"{sorted(set(guide_cards) & set(resource_cards))}"
    )

    for group in docs_config.get("navigation", []):
        links = group.get("links", [])
        assert len(links) == len(set(links)), (
            f"Duplicate link in navigation group '{group['title']}'"
        )

    anchors_by_route: dict[str, set[str]] = {}
    for route in pages:
        content = _route_to_mdx_path(route).read_text(encoding="utf-8")
        anchors_by_route[route] = _collect_h2_anchors(content)

    container_tags = ("Row", "Col", "Properties", "CodeGroup")

    for route in pages:
        mdx_path = _route_to_mdx_path(route)
        content = mdx_path.read_text(encoding="utf-8")
        no_code = _strip_fenced_code(content)

        # Balanced JSX container check
        for tag in container_tags:
            opens = len(re.findall(rf"<{tag}(?:\s|>)", no_code))
            closes = len(re.findall(rf"</{tag}>", no_code))
            assert opens == closes, (
                f"Unbalanced <{tag}> tags in {mdx_path.relative_to(REPO_ROOT)}: "
                f"{opens} opens vs {closes} closes"
            )

        # Internal link & anchor check
        for m in re.finditer(r"\]\((/[^)\s]+)\)", no_code):
            target = m.group(1)
            if target.startswith("/images/"):
                asset_path = DOCS_DIR / target.lstrip("/")
                assert asset_path.is_file(), (
                    f"Missing static asset '{target}' referenced in {route}"
                )
                continue
            target_route, _, anchor = target.partition("#")
            assert target_route in anchors_by_route, (
                f"Broken link '{target}' in {mdx_path.relative_to(REPO_ROOT)}"
            )
            if anchor:
                assert anchor in anchors_by_route[target_route], (
                    f"Broken anchor '{target}' in {mdx_path.relative_to(REPO_ROOT)}; "
                    f"valid anchors on {target_route}: "
                    f"{sorted(anchors_by_route[target_route])}"
                )
