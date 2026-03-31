"""Thin wrapper around theintrodb.org's /v2/media API (TMDB + S/E for TV)."""
import json
import time
import xbmc
import xbmcaddon

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

ADDON = xbmcaddon.Addon()

API_BASE = 'https://api.theintrodb.org/v2'
MIN_REQUEST_GAP = 0.4  # seconds between calls
_last_request_time = 0.0
_rate_limit_until = 0.0


def _debug_logging():
    return ADDON.getSetting('debug_logging') == 'true'


def _log_resp(body):
    if not _debug_logging():
        return
    snippet = body[:500] if len(body) > 500 else body
    xbmc.log('[IntroSkip] TheIntroDB response: {}'.format(snippet), xbmc.LOGINFO)


def _get_api_key():
    return (ADDON.getSetting('introdb_api_key') or '').strip()


def _is_enabled():
    return ADDON.getSetting('introdb_enabled') != 'false'


def _wait_rate_limit():
    global _last_request_time
    now = time.time()
    if now < _rate_limit_until:
        xbmc.log('[IntroSkip] TheIntroDB rate-limited until {:.0f}'.format(
            _rate_limit_until), xbmc.LOGINFO)
        return False
    gap = now - _last_request_time
    if gap < MIN_REQUEST_GAP:
        time.sleep(MIN_REQUEST_GAP - gap)
    _last_request_time = time.time()
    return True


def _do_request(url, api_key):
    global _rate_limit_until
    req = Request(url)
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', 'KodiSmartIntroSkip/1.0')  # CF blocks default Python UA
    if api_key:
        req.add_header('Authorization', 'Bearer {}'.format(api_key))

    try:
        resp = urlopen(req, timeout=8)
        body = resp.read().decode('utf-8')
        data = json.loads(body)
        _log_resp(body)
        return data
    except HTTPError as e:
        if e.code == 429:
            retry = 300
            for header in ('X-UsageLimit-Reset', 'X-RateLimit-Reset', 'Retry-After'):
                val = e.headers.get(header)
                if val:
                    try:
                        retry = int(val)
                    except ValueError:
                        pass
                    break
            _rate_limit_until = time.time() + retry
            xbmc.log('[IntroSkip] TheIntroDB 429 rate limited for {}s'.format(retry),
                     xbmc.LOGWARNING)
        elif e.code == 404:
            xbmc.log('[IntroSkip] TheIntroDB 404: show/episode not in database', xbmc.LOGINFO)
        else:
            xbmc.log('[IntroSkip] TheIntroDB HTTP {}'.format(e.code), xbmc.LOGWARNING)
        return None
    except URLError as e:
        xbmc.log('[IntroSkip] TheIntroDB network error: {}'.format(e.reason),
                 xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log('[IntroSkip] TheIntroDB request failed: {}'.format(e),
                 xbmc.LOGERROR)
        return None


def _pick_best_segment(segments):
    # start_ms null = 0; skip rows with no end_ms
    if not segments:
        return None, None

    best = None
    best_score = -1.0
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        start = seg.get('start_ms')
        end = seg.get('end_ms')
        if start is None:
            start = 0
        if end is None:
            continue
        if end <= start:
            continue
        conf = seg.get('confidence') if seg.get('confidence') is not None else 0.5
        count = seg.get('submission_count', 1)
        score = float(conf) + count * 0.001
        if score > best_score:
            best_score = score
            best = (start, end)

    if best:
        return best[0] / 1000.0, best[1] / 1000.0
    return None, None


def query_intro(tmdb_id=None, season=None, episode=None, is_movie=False, **kwargs):
    # Returns (start_sec, end_sec) or (None, None)
    if not _is_enabled():
        return None, None

    if not tmdb_id:
        xbmc.log('[IntroSkip] TheIntroDB: no TMDB ID available, cannot query', xbmc.LOGINFO)
        return None, None

    try:
        if int(tmdb_id) <= 0:
            return None, None
    except (ValueError, TypeError):
        return None, None

    api_key = _get_api_key()

    if is_movie:
        url = '{}/media?tmdb_id={}'.format(API_BASE, tmdb_id)
    else:
        url = '{}/media?tmdb_id={}&season={}&episode={}'.format(
            API_BASE, tmdb_id, season, episode)

    xbmc.log('[IntroSkip] TheIntroDB query: {}'.format(url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return None, None

    data = _do_request(url, api_key)
    if not data:
        return None, None

    if 'error' in data:
        xbmc.log('[IntroSkip] TheIntroDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return None, None

    intro_start, intro_end = _pick_best_segment(data.get('intro', []))
    if intro_start is not None:
        xbmc.log('[IntroSkip] TheIntroDB intro: {:.1f}s -> {:.1f}s'.format(
            intro_start, intro_end), xbmc.LOGINFO)
    else:
        xbmc.log('[IntroSkip] TheIntroDB: response had no usable intro segment', xbmc.LOGINFO)

    return intro_start, intro_end


def query_all_segments(tmdb_id=None, season=None, episode=None, is_movie=False, **kwargs):
    # same fetch as query_intro but returns all segment types — might use for recaps later
    if not _is_enabled():
        return {}

    if not tmdb_id:
        return {}

    try:
        if int(tmdb_id) <= 0:
            return {}
    except (ValueError, TypeError):
        return {}

    api_key = _get_api_key()

    if is_movie:
        url = '{}/media?tmdb_id={}'.format(API_BASE, tmdb_id)
    else:
        url = '{}/media?tmdb_id={}&season={}&episode={}'.format(
            API_BASE, tmdb_id, season, episode)

    xbmc.log('[IntroSkip] TheIntroDB query (all segments): {}'.format(url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return {}

    data = _do_request(url, api_key)
    if not data or 'error' in data:
        return {}

    result = {}
    for seg_type in ('intro', 'recap', 'credits', 'preview'):
        start, end = _pick_best_segment(data.get(seg_type, []))
        if start is not None:
            result[seg_type] = (start, end)

    if result:
        xbmc.log('[IntroSkip] TheIntroDB segments: {}'.format(
            ', '.join('{} {:.1f}s->{:.1f}s'.format(k, v[0], v[1])
                      for k, v in result.items())), xbmc.LOGINFO)

    return result
