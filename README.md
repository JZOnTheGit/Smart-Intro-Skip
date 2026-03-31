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

### Why are there two zip files in `repo/`?

| File | What it is |
|------|------------|
| **`repository.smartintro.jz-1.0.0.zip`** | Small “repo installer” only. It tells Kodi where to fetch **`addons.xml`** and the addon. Install **this one first** if you want *Install from repository* → updates. |
| **`plugin.video.introskip-1.0.1.zip`** | The **actual addon**. If you use the repo above, Kodi downloads this for you — you don’t need to grab it by hand. Only use this zip for a **direct install** (no repo). |

So: **repo path** = one small zip once, then pick the addon inside Kodi. **Direct path** = only the big addon zip.

### You don’t type long URLs into Kodi

Kodi’s **Install from zip** expects a **file** (USB, phone storage, SMB share, etc.). Nobody pastes `raw.githubusercontent.com/...` into the player.

**Easiest for users:** open the repo in a **browser**, go to the **`repo/`** folder, tap the zip → download → copy to the device running Kodi (or USB), then in Kodi: **Install from zip** → browse to that file.

**Folder link (share this):**  
[github.com/JZOnTheGit/Smart-Intro-Skip/tree/main/repo](https://github.com/JZOnTheGit/Smart-Intro-Skip/tree/main/repo)

### Install from my Kodi repository (updates in Kodi)

1. Download **`repository.smartintro.jz-1.0.0.zip`** from the link above (or the repo page → **`repo/`** → file → **Download**).
2. **Settings → Add-ons → Install from zip file** → pick that zip (enable unknown sources if asked).
3. **Settings → Add-ons → Install from repository** → **Smart Intro Skip repo** → **Services** → **Smart Intro Skip** → **Install**.

After you publish new versions (bump `addon.xml`, update `repo/`, push), users can **Check for updates** on the addon like any other repo.

### Direct zip install (no repository)

1. Download **`plugin.video.introskip-1.0.1.zip`** from the same **`repo/`** folder on GitHub.
2. **Settings → Add-ons → Install from zip file**
3. Enable under **My add-ons → Services** if needed.

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
