"""Persists learned intro ranges in the addon profile (used by skipper when learning's enabled)."""
import json
import os
import re
import xbmc
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_DATA = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
DATA_FILE = os.path.join(ADDON_DATA, 'data.json')


def _ensure_data_dir():
    if not os.path.exists(ADDON_DATA):
        os.makedirs(ADDON_DATA)


def _load():
    _ensure_data_dir()
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except (ValueError, IOError):
            return {}
    return {}


def _save(data):
    _ensure_data_dir()
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except IOError:
        xbmc.log('[IntroSkip] Failed to write data file', xbmc.LOGERROR)


def _normalise_filename(filename):
    # mess of release tags stripped so two files from different groups can still match
    name = os.path.basename(filename)
    name = os.path.splitext(name)[0]
    name = re.sub(r'[\[\(].*?[\]\)]', '', name)
    name = re.sub(r'\b(720p|1080p|2160p|4k|x264|x265|hevc|aac|bluray|webrip|web-dl|hdtv)\b',
                  '', name, flags=re.IGNORECASE)
    name = re.sub(r'[._\-]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip().lower()
    return name


def _extract_show_key(filename):
    # returns (show, SxxExx) if the filename looks like TV, else the whole normalised string
    normalised = _normalise_filename(filename)
    match = re.search(r'(.+?)\s*s(\d+)\s*e(\d+)', normalised, re.IGNORECASE)
    if match:
        show = match.group(1).strip()
        season = int(match.group(2))
        episode = int(match.group(3))
        return show, 'S{:02d}E{:02d}'.format(season, episode)
    return normalised, None


def store_intro(filename, intro_start, intro_end):
    # append/update data.json
    data = _load()
    show, episode = _extract_show_key(filename)

    if show not in data:
        data[show] = {'episodes': {}, 'avg_start': intro_start, 'avg_end': intro_end}

    show_data = data[show]
    key = episode if episode else _normalise_filename(filename)
    show_data['episodes'][key] = {
        'start': intro_start,
        'end': intro_end,
    }

    episodes = show_data['episodes']
    starts = [ep['start'] for ep in episodes.values()]
    ends = [ep['end'] for ep in episodes.values()]
    show_data['avg_start'] = sum(starts) / len(starts)
    show_data['avg_end'] = sum(ends) / len(ends)

    data[show] = show_data
    _save(data)
    xbmc.log('[IntroSkip] Stored intro for {}: {:.1f}s -> {:.1f}s'.format(
        key or show, intro_start, intro_end), xbmc.LOGINFO)


def lookup_intro(filename):
    # (start, end, boost) or zeros if nothing saved
    data = _load()
    show, episode = _extract_show_key(filename)

    if show not in data:
        return None, None, 0.0

    show_data = data[show]

    if episode and episode in show_data.get('episodes', {}):
        ep = show_data['episodes'][episode]
        return ep['start'], ep['end'], 1.0

    if len(show_data.get('episodes', {})) >= 2:
        return show_data['avg_start'], show_data['avg_end'], 0.8

    return None, None, 0.0


def reset_all():
    # wipe data.json — wired from settings action
    _ensure_data_dir()
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    xbmc.log('[IntroSkip] All learned data reset', xbmc.LOGINFO)
