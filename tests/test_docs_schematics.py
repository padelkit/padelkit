from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_schematics.py"
SCHEMATICS_DIR = REPO_ROOT / "docs" / "images" / "schematics"


def _load_generator_module():
    spec = importlib.util.spec_from_file_location("generate_schematics", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["generate_schematics"] = module
    spec.loader.exec_module(module)
    return module


def test_all_schematics_up_to_date() -> None:
    gen = _load_generator_module()
    exit_code = gen.main(["--check"])
    assert exit_code == 0


def test_schematics_xml_well_formed_and_bounded() -> None:
    gen = _load_generator_module()
    expected_count = len(gen.SCHEMATIC_GENERATORS) * 2
    svg_files = sorted(SCHEMATICS_DIR.glob("*.svg"))
    assert len(svg_files) == expected_count

    for svg_path in svg_files:
        raw = svg_path.read_text(encoding="utf-8")
        raw_bytes = svg_path.read_bytes()
        assert len(raw_bytes) <= gen.MAX_SVG_BYTES, f"{svg_path.name} exceeds 30 KB"
        assert "NaN" not in raw
        assert "inf" not in raw.lower() or "info" in raw.lower()

        root = ET.fromstring(raw)
        assert root.attrib.get("viewBox") is not None
        assert root.attrib.get("role") == "img"
        ns_free_tags = {el.tag.split("}")[-1] for el in root}
        assert "title" in ns_free_tags
        assert "desc" in ns_free_tags


def test_clip_segment_and_rdp_helpers() -> None:
    gen = _load_generator_module()

    # Segment completely behind near plane is discarded
    assert (
        gen.clip_segment_near_plane(
            np.array([0.0, 0.0, -2.0]),
            np.array([1.0, 1.0, 0.05]),
            z_near=0.10,
        )
        is None
    )

    # Segment crossing z_near is clipped to z = 0.10
    clipped = gen.clip_segment_near_plane(
        np.array([0.0, 0.0, -0.90]),
        np.array([0.0, 0.0, 1.10]),
        z_near=0.10,
    )
    assert clipped is not None
    assert np.isclose(clipped[0][2], 0.10)
    assert np.isclose(clipped[1][2], 1.10)

    # Collinear points simplify to endpoints, while bounce cusp index is preserved
    line_pts = np.column_stack([np.linspace(0.0, 100.0, 21), np.zeros(21)])
    simplified = gen.rdp_simplify_2d(line_pts, epsilon=0.5)
    assert simplified.shape == (2, 2)

    with_cusp = gen.simplify_trajectory_preserve_cusps(
        line_pts, bounce_indices=[10], epsilon=0.5
    )
    assert with_cusp.shape == (3, 2)
    assert np.allclose(with_cusp[1], line_pts[10])
