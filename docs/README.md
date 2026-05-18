# PadelKit Documentation Guide

Welcome to the PadelKit documentation source! The official documentation website (https://padelkit.dev) is automatically generated from this folder. 

We use a decoupled architecture: this public repository holds the content (Markdown) and configuration (JSON), while a separate private Next.js repository handles the rendering, styling, and deployment via Vercel.

## 📝 Writing Content

Documentation pages are written using standard Markdown (`.mdx`). 
You should place your files inside this folder (e.g., `my-feature/page.mdx`).

**Important Rules:**
- Do **not** use Next.js `export const metadata = { ... }` blocks at the top of your markdown files.
- Write pure markdown (e.g., start directly with `# My Feature Title`).
- Code blocks can be wrapped in `<CodeGroup>` components for tabbed interfaces if needed.

### 🏷️ Multi-Version Documentation

PadelKit uses a single-source-of-truth differential engine for its documentation, combining global page constraints with granular MDX components.

#### 1. Full-Page Versioning (docs.config.json)
If a page (like a class or concept) was introduced in a specific version or deprecated in another, define this in `docs.config.json` inside the `"pages"` object. 
The system will **automatically** intercept requests to out-of-bounds pages, hide them from the sidebar and search results, and display a standardized warning.

```json
"pages": {
  "/my-feature": {
    "title": "My Feature",
    "description": "API Reference.",
    "min": "2.0.0", // Only available in 2.0.0 or higher
    "max": "2.5.0", // Deprecated after 2.5.0
    "supersededBy": { // Optional: suggest an alternative when deprecated
      "title": "NewFeature",
      "href": "/new-feature"
    }
  }
}
```
*Note: Do NOT wrap the entire MDX file content in `<Version>` tags if the entire page is restricted. Let `docs.config.json` handle it globally!*

#### 2. Granular Versioning (MDX)
If you only need to show/hide specific paragraphs, properties, or methods *within* a valid page, use MDX components:

- `<Version min="1.0.0" max="1.5.0">...</Version>`: Shows inner content only if the selected version is within the specified range.
- `<AddedIn version="1.2.0">...</AddedIn>`: Shows a styled block indicating that a granular feature was added.
- `<DeprecatedIn version="1.6.0">...</DeprecatedIn>`: Shows a styled block indicating that a granular feature was deprecated.

**Example usage:**
```mdx
<Version min="1.0.0" max="1.5.0">
  This property had the old behavior.
</Version>

<AddedIn version="1.6.0">
  This is the new behavior.
</AddedIn>
```

## ⚙️ Configuring the Website

The entire structure of the website is controlled by **`docs.config.json`**. This is the Single Source of Truth for all metadata, URLs, and navigation menus.

If you create a new page, you **must** register it in `docs.config.json`.

### 1. Register the Page Metadata
Add your page to the `"pages"` object. The key should be the URL path (which corresponds to the folder name):

```json
"pages": {
  "/my-feature": {
    "title": "My Awesome Feature",
    "description": "Learn how to use my awesome feature in PadelKit.",
    "icon": "UserIcon" // Optional: Only needed if it's a resource card on the homepage
  }
}
```

### 2. Add it to the Sidebar Navigation
To make the page accessible from the sidebar menu, add its URL to the `"navigation"` array:

```json
"navigation": [
  {
    "title": "Guides",
    "links": ["/", "/quickstart", "/my-feature"]
  }
]
```

### 3. Add it to the Homepage Cards (Optional)
If you want the page to appear as a large visual card on the homepage, add its URL to the `"intro_cards"` object under `guides` or `resources`. 

If you place it under `resources`, you must specify a valid `"icon"` string in the page's object inside `"pages"`.

#### 🎨 Synced Icons System
Icons are defined directly within PadelKit in [docs/icons/](file:///home/fidelechevarria/repos/padelkit/docs/icons/). The build pipeline automatically copies these icons, registers them, and exposes them dynamically on the documentation website.

*   **Using an Existing Icon:** 
    You can use any of the pre-configured icons by setting `"icon"` to the icon's component name (without the `.tsx` extension). Some of the available built-in options include:
    *   `UserIcon` / `UserNoCircleIcon` (for single user/player metrics)
    *   `UsersIcon` (for teams/groups)
    *   `TrophyIcon` (for matches/tournaments)
    *   `ChatBubbleIcon` (for chat, scoring history, or feedback)
    *   `ViewfinderCircleIcon` (for landmarks/vision system)
    *   `BookIcon`, `CalendarIcon`, `CartIcon`, `ClipboardIcon`, `CogIcon`, `FolderIcon`, `LinkIcon`, `MapPinIcon`, `PackageIcon`, `TagIcon` (and many more in [docs/icons/](file:///home/fidelechevarria/repos/padelkit/docs/icons/)).

*   **Adding a Custom Icon:**
    If you need a new icon that is not in the list, simply create a new React component file inside [docs/icons/](file:///home/fidelechevarria/repos/padelkit/docs/icons/) (e.g., `NewFeatureIcon.tsx`). It must be a standard React SVG component accepting SVG properties:
    
    ```tsx
    export function NewFeatureIcon(props: React.ComponentPropsWithoutRef<'svg'>) {
      return (
        <svg viewBox="0 0 20 20" aria-hidden="true" {...props}>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="..."
          />
        </svg>
      )
    }
    ```
    
    Once the file is saved, reference it in `docs.config.json` as `"icon": "NewFeatureIcon"`. During the next automated sync, the build process will automatically copy, register, and render your custom icon.

## 🚀 Deployment

You do not need to do anything to deploy the documentation. 
Whenever changes to this folder are merged into the `main` branch, a Vercel webhook will automatically trigger the private frontend repository to fetch your changes, inject the necessary metadata, build the site, and deploy the updates.
