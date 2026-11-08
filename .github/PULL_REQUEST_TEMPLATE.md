## Summary

<!-- Briefly describe what this Pull Request does and why. -->

Fixes #<!-- issue number if applicable -->

## Type of Change

- [ ] 🚀 **Feature (`feat`)** — New functionality or API addition
- [ ] 🐛 **Bug Fix (`fix`)** — Fixes an issue without breaking existing APIs
- [ ] 📚 **Documentation (`docs`)** — Adds or updates `.mdx` pages, `docs.config.json`, or SVG schematics
- [ ] 🧪 **Tests / Refactor (`test` / `refactor`)** — Code quality or test coverage improvements

## Contributor Checklist

Please make sure your Pull Request targets the **`develop`** branch (unless it is a release merge into `main`) and satisfies the following checks:

- [ ] My branch is up to date with `develop` and targets `develop`.
- [ ] I have added or updated unit tests in `tests/` and `.venv/bin/pytest` passes locally.
- [ ] Code linting (`.venv/bin/ruff check .`) and formatting (`.venv/bin/ruff format --check .`) pass without errors.
- [ ] I have added an entry under `## [X.Y.Z] - Unreleased` in `CHANGELOG.md` (feel free to credit yourself: `(#PR by @your-username)`).
- [ ] **Documentation (`docs/`):**
  - [ ] If I added/modified public classes or methods, I updated the corresponding `.mdx` files in `docs/` and registered any new routes in `docs/docs.config.json`.
  - [ ] I did **not** include manual `export const metadata = ...` blocks in `.mdx` files.
  - [ ] If I modified [`scripts/generate_schematics.py`](../../scripts/generate_schematics.py), I regenerated the vector diagrams with `.venv/bin/python scripts/generate_schematics.py`.
