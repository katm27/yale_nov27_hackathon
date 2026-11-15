# Publishing and collaborating

There are two copies of the app:

| Copy | Where | Updates when |
|---|---|---|
| **Source** | this repository (`docs/` = the app, `scripts/` = pipelines, `data/` = inputs) | someone pushes a commit |
| **Hosted artifact** | https://claude.ai/artifact/PnwAgQdQYrjkgmqK7TEH7o | someone republishes it from a Claude session. It does **not** update from GitHub on its own |

## Changing the app (any collaborator)

1. Work on a branch, edit `docs/app.js`, `docs/index.html`, `docs/style.css` or a pipeline in `scripts/`.
2. If data or variables changed: `python scripts/build_web_data.py` (and `python scripts/trend_stats.py` if a source's series changed).
3. Preview locally: `python -m http.server -d docs 8000`.
4. Commit and push. Pull first (`git pull --ff-only`), because several people and Claude sessions push to the same branch.

## Republishing the hosted artifact

1. The artifact's owner opens it on claude.ai → **Share** → gives the collaborator **edit** access.
2. In the collaborator's Claude session (with this repo attached), ask Claude to:
   - `git pull`, then `python scripts/pack_for_artifact.py site` (packs only what `docs/data/curated.json` lists);
   - read the artifact URL above, then publish `site/index.html` with `root` = `site` **to that same URL**,
     in batches of < 55 MB and < 255 files (rasters first, page last).
3. Without edit access, publishing creates a separate new artifact with a new link.

## A link that updates automatically

Turn on **GitHub Pages** (Settings → Pages → branch `main`, folder `/docs`). Every push to `main` then updates the
site, with no packing needed. Private repositories need a paid GitHub plan for Pages.
