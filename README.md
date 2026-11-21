# pesce mignon

A static recipe site built from the markdown notes in `content/`.

```
content/*.md  +  build.py  ── build ──▶  user-test124.github.io/recipes
                 (deploy.yml)
```

- `content/` is filled automatically by a sync, so don't edit it here: changes would be overwritten.
- `content/.dates.json` records when each note was first written. That date drives "Recently written down"; without it the build uses git history or file dates.
- A push to `main` builds the site and publishes it with GitHub Pages (Settings → Pages → Source: **GitHub Actions**).

## Preview on your computer

```sh
pip install -r requirements.txt
python build.py --content path/to/notes --serve
# open http://localhost:8000
```

The build prints the notes it skipped (still empty) and any photos it couldn't find.

## How notes are read

No special format is needed. The site understands the template the notes already use:

| In the note | On the site |
| --- | --- |
| File name `Cake aux Olives - Marraine Odile.md` | Title "Cake aux Olives", "From Marraine Odile" |
| `# Title` on the first line | Title (overrides the file name) |
| `> [source](https://…)` | Source link under the title |
| Other `> quoted text` at the top | Intro paragraph |
| The `Portions / Preparation / Dont cuisson` table | Makes / Preparation / Cooking |
| First `![[photo.jpg]]` before the sections | Main photo and card photo (found anywhere in the folder) |
| `### Ingredients`, `### Steps`, `### Tricks`, `### History` (any heading level, FR/IT/EN) | Ingredient checklist, numbered method, tips box, story |
| A short line like `Pâte:` or `**Cuisson :**` above a list | Sub-heading inside ingredients or method |
| `### Modo 1` … `### Modo 2`, each with its own sections | Separate variants of the recipe |
| `#alsace` or `[[lebanese]]` on its own line | Tag |
| `[[Bechamel]]` (another recipe) | Link to that recipe |
| Folders `savoury/pasta/` | Category tab "Savoury", chip "Pasta" (tabs are ordered by number of recipes) |

Notes whose sections are all empty are left out until they have content.

### Optional front matter

To override anything, add YAML at the very top of a note. Obsidian shows it as properties. All fields are optional:

```yaml
---
title: Kougelhopf
credit: Bernard
servings: 2 moules de 20 cm
prep: 2h30
cook: 50 min
image: kougelhopf.jpg
tags: [alsace, brioche]
draft: true        # keep it off the site
---
```

## Settings

At the top of `build.py`: site title, tagline, public address, and optional display names for folders (for example `vegi` → "Vegetables").
