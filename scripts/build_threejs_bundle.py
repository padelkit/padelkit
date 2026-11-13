"""Rebuilds the vendored gzip-compressed Three.js runtime for offline HTML export.

Requires Node.js and npm on ``PATH`` with network access to install
``three@0.170.0`` and ``esbuild`` inside a temporary build directory.
"""

from __future__ import annotations

import gzip
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

THREEJS_VERSION = "0.170.0"
REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = REPO_ROOT / "src" / "padelkit" / "viz" / "vendor"

ENTRY_MJS = """import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import * as SkeletonUtils from "three/examples/jsm/utils/SkeletonUtils.js";

globalThis.__PADELKIT_THREE_BUNDLE__ = {
  THREE,
  OrbitControls,
  GLTFLoader,
  SkeletonUtils,
};
"""


def build_bundle() -> None:
    """Installs Three.js + esbuild in a temp dir and writes the vendor bundle."""
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="padelkit_three_") as tmp:
        tmp_path = Path(tmp)
        pkg_json = {
            "name": "padelkit-three-bundler",
            "private": True,
            "dependencies": {"three": THREEJS_VERSION},
            "devDependencies": {"esbuild": "^0.24.0"},
        }
        (tmp_path / "package.json").write_text(
            json.dumps(pkg_json, indent=2), encoding="utf-8"
        )
        (tmp_path / "entry.mjs").write_text(ENTRY_MJS, encoding="utf-8")

        subprocess.run(["npm", "install"], cwd=tmp_path, check=True)

        raw_out = tmp_path / "three.bundle.min.js"
        esbuild_bin = tmp_path / "node_modules" / ".bin" / "esbuild"
        banner = (
            f"/* three.js r{THREEJS_VERSION} | MIT License | "
            "Copyright (c) 2010-2024 three.js authors */"
        )
        subprocess.run(
            [
                str(esbuild_bin),
                str(tmp_path / "entry.mjs"),
                "--bundle",
                "--minify",
                "--format=iife",
                "--platform=browser",
                "--target=es2020",
                f"--banner:js={banner}",
                f"--outfile={raw_out}",
            ],
            cwd=tmp_path,
            check=True,
        )

        bundle_bytes = raw_out.read_bytes()
        gz_path = VENDOR_DIR / "three.bundle.min.js.gz"
        gz_path.write_bytes(gzip.compress(bundle_bytes, compresslevel=9))

        license_src = tmp_path / "node_modules" / "three" / "LICENSE"
        shutil.copyfile(license_src, VENDOR_DIR / "THREEJS_LICENSE.txt")

        print(
            f"Built {gz_path.relative_to(REPO_ROOT)} "
            f"({len(bundle_bytes) / 1024:.1f} KiB raw, "
            f"{gz_path.stat().st_size / 1024:.1f} KiB gzip)"
        )


if __name__ == "__main__":
    build_bundle()
