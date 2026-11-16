# PadelKit Documentation Guide

Welcome to the **PadelKit** documentation source! The official documentation website (**[https://padelkit.dev](https://padelkit.dev)**) is generated automatically from this directory whenever changes in `docs/**` are pushed to `develop` or `main`.

This public repository is **100% self-contained** for documentation contributors: you do not need access to any private website repository to write guides, document new classes, add SVG icons/schematics, or run full CI verification before opening a Pull Request.

---

## 1. Editorial Architecture (Diátaxis)

PadelKit separates **conceptual Guides** from **formal API Reference** so concepts are intuitive without cluttering specifications, and specifications are complete without duplicating tutorials:

| Document Role | Location & Sidebar Group | What Belongs Here | What Is Forbidden |
| :--- | :--- | :--- | :--- |
| **Guides & Formats** | `Getting Started`, `Guides` (`/quickstart`, `/court-geometry`, `/camera-system`, `/ball-physics`, `/visualization-3d`, `/stroke-library`, `/scoring-system`, `/match-format`) | Intuitive explanations assuming zero prior context, coordinate/unit conventions, regulatory rationale, SVG `<Schematic>` diagrams, end-to-end `<CodeGroup>` examples, and links to API pages. | Never embed `<Properties>` / `<Property>` class parameter specs or duplicate constructor tables inside guides. |
| **Class / Dataclass API** | `API: Court`, `API: Camera`, `API: Physics`, `API: Scoring`, `API: Visualization` | **Strict `1 class = 1 page` rule.** Exact fields/constructor, read-only `@property` attributes, `@classmethod` factories, methods (`### Arguments` / `### Returns`), and self-contained Python examples. | Never bundle multiple public classes onto a single page (e.g. `FrameState` and `PlayerPose` live on separate pages). |
| **Enums & Constants** | `<module>-enums/page.mdx` or `<module>-constants/page.mdx` (plus `/court-landmark` for spatial landmarks) | One `## \`EnumName\` {{ tag: 'enum' }}` section per exported enum/constant containing a full member-value table matching Python source and a short usage example. | Never omit exported enum members or mix unrelated classes onto the same page. |

### Clarity & Intuitiveness Standard

PadelKit bridges **3D geometry, computer vision, physics simulation, and padel rules**. Do not treat domain conventions as "obvious":
- Always state **units** explicitly (`m`, `m/s`, `rad/s`, `RPM`, `PSI`, `kg·m²`, `pixels`, `degrees`).
- Remind readers of the **spatial frame** when coordinates appear (`CENTERED` `(0,0,0)` at net center, `+X` right, `+Y` far, `+Z` up from the NEAR-side view).
- Keep all **Python docstrings** in `src/padelkit/` clean Markdown Google-style (no `:class:` / `:attr:` Sphinx directives that render poorly in IDE tooltips), include inline `"""..."""` attribute docstrings underneath dataclass fields, and preserve [src/padelkit/py.typed](../src/padelkit/py.typed).

---

## 2. Writing MDX Pages & Canonical API Template

Documentation pages live under `docs/<route-slug>/page.mdx` (or `docs/page.mdx` for `/`).

**Strict MDX rules:**
- Start directly with `# Title` — **never** add `export const metadata = { ... }` (metadata is injected automatically from [docs.config.json](./docs.config.json)).
- Only **`##` (`H2`)** headings appear in the secondary sidebar outline and full-text search index, and only **`##`** headings accept `{{ tag: '...', label: '...' }}` eyebrow annotations. Use `###` for sub-sections inside methods (`### Arguments`, `### Returns`).
- `<Property name="..." type="...">` only accepts **`name`** and **`type`** props—state defaults and constraints inside the body (e.g. `Defaults to \`0.058\`.`).
- Use only the canonical tag vocabulary in `{{ tag: '...' }}`:
  - **API Reference:** `class`, `dataclass`, `enum`, `constant`, `constructor`, `fields`, `property`, `classmethod`, `method`
  - **Guides & Workflows:** `guide`, `schema`, `cli`

### Canonical API Page Skeleton

1. **Lead + Import:** `# ClassName`, brief intuitive summary, `from padelkit import ClassName`, optional `<Note>` or `<Schematic />`.
2. **`## Parameters & Fields {{ tag: 'dataclass', label: 'ClassName' }}`** *(for dataclasses whose fields match `__init__` 1:1)* — **or** separate **`## Constructor {{ tag: 'constructor' }}`** and **`## Attributes {{ tag: 'fields' }}`** when `__init__` differs from stored state, paired with `<Col sticky><CodeGroup title="Initialization">...</CodeGroup></Col>`.
3. **`## Properties {{ tag: 'property' }}`** *(optional: computed `@property` attributes only)*.
4. **Factories / Methods:** Each factory (`{{ tag: 'classmethod' }}`) or public method (`{{ tag: 'method' }}`) gets a dedicated `## \`method_name()\`` heading with `### Arguments` / `### Returns` on the left and a runnable `<CodeGroup>` on the right.

---

## 3. Registering Pages, Schematics & Icons (`docs.config.json`)

Every page must be registered in [`docs/docs.config.json`](./docs.config.json):

1. **`"pages"`**: Add `"/your-route"` with `"title"`, `"description"`, optional `"min"` / `"max"` version bounds (matching `"versions"`), and `"icon"` (required if featured in `intro_cards.resources`).
2. **`"navigation"`**: Add `"/your-route"` under the appropriate sidebar group (`Getting Started`, `Guides`, or `API: <Module>`).
3. **`"intro_cards"`**: Avoid duplicating a route across both `guides` and `resources`.
4. **Icons (`docs/icons/`):** Pre-existing SVG React components live in [`./icons/`](./icons/) (e.g., `BoltIcon`, `ShapesIcon`, `ViewfinderCircleIcon`, `CogIcon`, `MapPinIcon`, `TrophyIcon`, `UsersIcon`, `UserIcon`, `DocumentIcon`). To add a custom icon, place `MyIcon.tsx` inside `./icons/` and reference `"icon": "MyIcon"` in `docs.config.json`.
5. **Vector Schematics (`docs/images/schematics/`):** Light and dark SVGs are generated deterministically by [`scripts/generate_schematics.py`](../scripts/generate_schematics.py). Embed them with:
   ```mdx
   <Schematic
     name="court-dimensions"
     alt="Official FIP CourtDimensions Blueprint"
     caption="..."
   />
   ```
   After editing a schematic generator, regenerate both themes via:
   ```bash
   .venv/bin/python scripts/generate_schematics.py
   ```

---

## 4. Multi-Version Annotations

- **Whole-page availability:** Use `"min"` / `"max"` (and optional `"supersededBy"`) in [`docs/docs.config.json`](./docs.config.json) rather than wrapping an entire MDX page in `<Version>`.
- **Granular inline notices:** Within a valid page, use `<AddedIn version="X.Y.Z">...</AddedIn>`, `<DeprecatedIn version="X.Y.Z">...</DeprecatedIn>`, or `<Version min="X.Y.Z" max="A.B.C">...</Version>`. Note that `"X.Y.Z"` must be declared in `docs.config.json`'s `"versions"` array once released.

---

## 5. Local Validation & Deployment

Pull requests target **`develop`** (which triggers the staging preview when `docs/**` merges to `develop`), and merging `develop` into **`main`** deploys live to **[https://padelkit.dev](https://padelkit.dev)**.

Before opening a PR, run the full documentation, API-sync, lint, and test checks locally:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python scripts/generate_schematics.py --check
.venv/bin/pytest
```

Our CI suite ([`tests/test_version_and_docs.py`](../tests/test_version_and_docs.py), [`tests/test_docs_schematics.py`](../tests/test_docs_schematics.py), and [`tests/test_docs_api_sync.py`](../tests/test_docs_api_sync.py)) enforces:
- 100% coverage of every symbol exported in `padelkit.__all__`.
- Runtime introspection parity between documented fields/methods/enum values and real Python signatures (`inspect.signature`, `dataclasses.fields`, `hasattr`).
- Diátaxis separation (no API `<Properties>` blocks inside Guide pages), valid `<Heading tag="...">` names, valid internal `/slug` and `/slug#anchor` links, balanced JSX containers, SVG parity, and package version alignment.
