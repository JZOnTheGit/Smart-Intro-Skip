# Smart Intro Skip (Kodi)

Skips TV intros using timestamps from **[TheIntroDB](https://theintrodb.org)**. Shows a skip button until the intro ends or you press it.

## Credits

Database and API: **[TheIntroDB](https://theintrodb.org)** — community-submitted timings.

**Creator / maintainer of the API:** [Pasithea0](https://github.com/Pasithea0) · org: [github.com/TheIntroDB](https://github.com/TheIntroDB)

This addon is just a Kodi client; it’s not run by them.

## Compatibility (Seren, Umbrella, etc.)

Nothing here is tied to one streaming addon. The service reads **whatever Kodi’s player has for the current file** — usually via `VideoInfoTag` and JSON-RPC (`uniqueid`, season, episode).

So it works with **Seren, Fen, Umbrella, or your local library** as long as the playing item actually has a **TMDB id** (and season + episode for TV). Some addons only set IMDB or leave IDs empty; then TheIntroDB can’t match. That’s a metadata problem.

## Features

- Pulls intro in/out from TheIntroDB
- Skip button stays up for the whole intro (or auto-skip if you turn that on)
- One HTTP request per episode when you have IDs

## Installation

### Install from my Kodi repository (updates show up in Kodi)

1. Download **`repository.smartintro.jz-1.0.0.zip`** (the small “repo installer” zip), from either:
   - **Raw link:**  
     `https://raw.githubusercontent.com/JZOnTheGit/Smart-Intro-Skip/main/repo/repository.smartintro.jz-1.0.0.zip`  
   - Or open the repo on GitHub → folder **`repo/`** → download the file.
2. In Kodi: **Settings → Add-ons → Install from zip file** → select that zip (you may need to enable unknown sources once).
3. **Settings → Add-ons → Install from repository** → **Smart Intro Skip repo** → **Services** → **Smart Intro Skip** → **Install**.

After that, new versions appear under **My add-ons** when you bump the version in `addon.xml` and refresh the repo (Kodi checks `repo/addons.xml` on the `main` branch).

### Zip install (addon only, no repo)

1. Download **`plugin.video.introskip-1.0.1.zip`**:  
   `https://raw.githubusercontent.com/JZOnTheGit/Smart-Intro-Skip/main/repo/plugin.video.introskip-1.0.1.zip`
2. **Settings → Add-ons → Install from zip file**
3. **My add-ons → Services → Smart Intro Skip** — enable it  

### Releasing a new version (for you)

1. Edit **`plugin.video.introskip/addon.xml`** → bump `version`.
2. Rebuild the addon zip from the repo root (folder must be **inside** the zip):  
   `zip -r repo/plugin.video.introskip-X.Y.Z.zip plugin.video.introskip`
3. Update **`repo/addons.xml`** to match the new version (copy the addon block from `addon.xml` if needed).
4. Regenerate checksum: `md5 -q repo/addons.xml > repo/addons.xml.md5`
5. Commit and push **`main`**.  
   (Keep the repo **public** so `raw.githubusercontent.com` URLs work for everyone.)

## Settings

| | |
|--|--|
| **General** | Auto-skip; extra seconds after intro end |
| **TheIntroDB** | On/off; optional API key from the site |
| **Coming soon** | Greyed placeholders for later stuff |
| **Debug** | Log spam; on-screen debug lines |

## Requirements

- Kodi 19+  
- TMDB id on the item (and S/E for episodes) or nothing lines up  

## License

GPL-2.0-or-later
