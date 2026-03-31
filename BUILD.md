# Maintainer notes (releases & GitHub Pages)

## Turn on github.io (one-time)

The short download URL **`https://jzonethegit.github.io/Smart-Intro-Skip/`** is served from this repo’s **`docs/`** folder via **GitHub Pages**.

1. GitHub repo → **Settings** → **Pages**
2. **Build and deployment** → **Source**: *Deploy from a branch*
3. **Branch**: `main` → **Folder**: `/docs` → **Save**
4. After a minute, the site should load. If you see 404, wait for the Pages build to finish (check the **Actions** tab).

Published files live in **`docs/`**: `addons.xml`, `addons.xml.md5`, both zips, `index.html`, `.nojekyll`.

The repository addon (`repository.smartintro.jz`) points Kodi at the **github.io** URLs in `repository.smartintro.jz/addon.xml`.

## Release checklist

1. Bump **`version`** in **`plugin.video.introskip/addon.xml`**
2. Copy the `<addon>...</addon>` block into **`docs/addons.xml`**
3. `cd` to project root, then:
   ```bash
   rm -f docs/plugin.video.introskip-*.zip
   zip -r docs/plugin.video.introskip-X.Y.Z.zip plugin.video.introskip
   md5 -q docs/addons.xml > docs/addons.xml.md5
   ```
4. If **`repository.smartintro.jz/addon.xml`** changed, rebuild **`docs/repository.smartintro.jz-1.0.0.zip`**:
   ```bash
   rm -f docs/repository.smartintro.jz-*.zip
   zip -r docs/repository.smartintro.jz-1.0.0.zip repository.smartintro.jz
   ```
5. Update **`docs/index.html`** zip names/versions if needed
6. Commit and push **`main`**

Repo must stay **public** for Pages and for Kodi clients to fetch files.
