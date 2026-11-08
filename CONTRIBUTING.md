# Contributing to PadelKit 🎾

Thank you for your interest in contributing to **PadelKit**! Whether you are fixing a bug, adding a new physics or computer vision feature, or improving the documentation at [padelkit.dev](https://padelkit.dev), your contributions are welcome.

---

## 🌿 Branching Strategy & Pull Request Workflow

PadelKit uses a two-branch integration model (`develop` and `main`) connected to automated testing and documentation deployment:

| Branch | Purpose | Documentation Environment | PyPI Release |
| :--- | :--- | :--- | :--- |
| **`develop`** | **Integration branch (Target your PRs here!)** | Automatically deploys to the **Preview / Staging** docs environment when `docs/**` changes are merged. | No |
| **`main`** | **Stable production branch** | Automatically deploys to **[https://padelkit.dev](https://padelkit.dev)** (Production) when merged. | Triggered on GitHub Release (`vX.Y.Z`) |

### Step-by-Step Contribution Flow

1. **Fork** the repository on GitHub and clone your fork locally.
2. **Checkout a new branch from `develop`**:
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feat/my-awesome-feature
   ```
3. **Make your changes** (code, unit tests, and documentation if applicable).
4. **Run the quality checks locally** (see [Local Development Setup](#-local-development-setup) below).
5. **Update `CHANGELOG.md`** under the `## [X.Y.Z] - Unreleased` section and credit yourself at the end of the line (e.g., `- Add altitude air density helper (#12 by @your-github-username).`).
6. **Open a Pull Request targeting the `develop` branch** of `padelkit/padelkit`.

---

## 🛠️ Local Development Setup

We recommend using [**uv**](https://docs.astral.sh/uv/) for fast environment management, though standard `pip` works as well.

### 1. Install Dependencies

**Using `uv` (Recommended):**
```bash
uv sync --extra dev
```

**Using standard `venv` + `pip`:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run Tests, Linter, and Formatter

Before submitting a Pull Request, ensure all checks pass:

```bash
# 1. Run the test suite (includes code, version sync, and docs integrity checks)
.venv/bin/pytest

# 2. Check linting rules
.venv/bin/ruff check .

# 3. Verify (or apply) code formatting
.venv/bin/ruff format --check .
# To auto-format: .venv/bin/ruff format .
```

---

## 📚 Contributing to the Website & Documentation (`docs/`)

The official documentation website (**[https://padelkit.dev](https://padelkit.dev)**) is generated directly from the [`docs/`](./docs/) folder in this repository!

You do **not** need access to the Next.js frontend repository to add pages, edit guides, add icons, or update diagrams. Everything is controlled via Markdown (`.mdx`) and [`docs/docs.config.json`](./docs/docs.config.json).

### How to Edit or Add Documentation

1. **Edit an existing page:** Open any `docs/<page-slug>/page.mdx` file and edit the Markdown directly.
2. **Create a new page:**
   - Create `docs/<my-feature>/page.mdx` (start directly with `# Title` — **never** include `export const metadata = ...` as the build pipeline injects it automatically).
   - Register the route in [`docs/docs.config.json`](./docs/docs.config.json) under `"pages"` and `"navigation"` (and optionally `"intro_cards"`).
3. **Version Tags in Docs:**
   - If your new page belongs to the upcoming version (e.g. `0.1.0`), add `"min": "0.1.0"` to its entry in `docs/docs.config.json`.
   - If you are adding a new method or parameter to an existing page, wrap it in `<AddedIn version="0.1.0">...</AddedIn>` or `<Version min="0.1.0">...</Version>`.
4. **Technical Schematics (SVG):**
   - Light/dark vector diagrams in `docs/images/schematics/` are generated deterministically by [`scripts/generate_schematics.py`](./scripts/generate_schematics.py).
   - If you modify a schematic generator, regenerate the SVGs with:
     ```bash
     .venv/bin/python scripts/generate_schematics.py
     ```
5. **Validate your documentation changes:**
   - Run `.venv/bin/pytest tests/test_docs_schematics.py tests/test_version_and_docs.py` — our test suite automatically verifies that `docs.config.json` has no broken routes, missing `.mdx` files, invalid icons, or forbidden `export const metadata` blocks!

👉 For full details on MDX components (`<Row>`, `<Col>`, `<Properties>`, `<CodeGroup>`, `<Schematic>`) and custom SVG icons, read the **[Documentation Guide (`docs/README.md`)](./docs/README.md)**.

---

## 🏷️ Commit Convention & Versioning

### Conventional Commits
Please follow [Conventional Commits](https://www.conventionalcommits.org/) for clear history:
- `feat(physics): add altitude air density helper`
- `fix(camera): handle zero distortion coefficients in fisheye model`
- `docs(court): clarify corner-based coordinate origin`
- `test(scoring): add golden point tie-break edge cases`
- `ci: add Python 3.13 to test matrix`

### Semantic Versioning & Releases (Maintainers)
PadelKit follows [Semantic Versioning (`SemVer`)](https://semver.org/):
- `pyproject.toml` is the **single source of truth** for the package version (`src/padelkit/__init__.py` reads it dynamically via `importlib.metadata`, and CI verifies alignment with `CHANGELOG.md` and `docs/docs.config.json`).
- **Release checklist for maintainers:**
  1. Ensure `pyproject.toml` has the target version (e.g. `version = "0.1.0"`), `docs/docs.config.json` lists `"0.1.0"` in `"versions"`, and `CHANGELOG.md` replaces `## [0.1.0] - Unreleased` with `## [0.1.0] - YYYY-MM-DD`.
  2. Merge `develop` into `main` via Pull Request (this deploys production docs to `padelkit.dev`).
  3. Create a GitHub Release with tag `v0.1.0` targeting `main` and click **"Generate release notes"** (configured via [`.github/release.yml`](./.github/release.yml) to automatically group PRs by category and credit every contributor with `@username` and "New Contributors" callouts) — the [`.github/workflows/release.yml`](./.github/workflows/release.yml) workflow will automatically verify the tag matches `pyproject.toml`, run tests, build the wheel/sdist, and publish to PyPI.

---

## 📜 License

By contributing to PadelKit, you agree that your contributions will be licensed under the [Apache 2.0 License](./LICENSE).
