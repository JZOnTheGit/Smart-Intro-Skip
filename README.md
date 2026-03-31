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

### Why are there two zip files on GitHub?

They are **not** two copies of the same thing. Kodi treats them as **two different add-ons**:

| Zip | Kodi add-on id | Role |
|-----|----------------|------|
| **`repository.smartintro.jz-1.0.0.zip`** | `repository.smartintro.jz` | **Repository only** — a tiny package that says “here is `addons.xml` and where to download zips.” No skip logic inside. |
| **`plugin.video.introskip-1.0.1.zip`** | `plugin.video.introskip` | **Your actual addon** (service, UI, TheIntroDB client). |

You **cannot** merge those into a single zip and still use **Install from repository** the normal way — Kodi’s repo system expects a separate repository add-on that points at the index (`addons.xml`) and the addon zip(s).

**What people actually download by hand:**

- **Repo route:** they only need **one** file — **`repository.smartintro.jz-1.0.0.zip`**. After that, **Install from repository** pulls **`plugin.video.introskip-*.zip`** for them; they don’t download it from GitHub manually.
- **Direct route:** they only download **`plugin.video.introskip-1.0.1.zip`** and skip the repository entirely.

So: two zips on the server, but each user only grabs **one** of them, depending on the path they choose.

### Repo route (recommended — updates in Kodi)

1. Download **`repository.smartintro.jz-1.0.0.zip`** from the **root of this GitHub repo** (short link: [project root on `main`](https://github.com/JZOnTheGit/Smart-Intro-Skip)).
2. **Settings → Add-ons → Install from zip file** → select that zip (use USB / phone / share — same as any zip).
3. **Settings → Add-ons → Install from repository** → **Smart Intro Skip repo** → **Services** → **Smart Intro Skip** → **Install**.

*(Optional)* **File manager → Add source** can point at a folder or URL where you put the zip; GitHub’s web UI is usually easier than typing a long URL in Kodi.

### Direct zip (no repository)

1. Download **`plugin.video.introskip-1.0.1.zip`** from the same [repo root](https://github.com/JZOnTheGit/Smart-Intro-Skip).
2. **Settings → Add-ons → Install from zip file**

### Releasing a new version (for you)

1. Bump **`version`** in **`plugin.video.introskip/addon.xml`**.
2. Rebuild **`plugin.video.introskip-X.Y.Z.zip`** from the project root (folder must be inside the zip):  
   `zip -r plugin.video.introskip-X.Y.Z.zip plugin.video.introskip`
3. Update **`addons.xml`** in the project root to match (copy the `<addon>...</addon>` block from `addon.xml` if needed).
4. `md5 -q addons.xml > addons.xml.md5`
5. Rebuild **`repository.smartintro.jz-1.0.0.zip`** only if you changed **`repository.smartintro.jz/addon.xml`**:  
   `zip -r repository.smartintro.jz-1.0.0.zip repository.smartintro.jz`
6. Commit and push **`main`** (repo must stay **public** for `raw.githubusercontent.com` URLs).

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
