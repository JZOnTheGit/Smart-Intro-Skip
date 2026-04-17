# http client for theintrodb v2 /media — url from tmdb or imdb plus season/episode when needed
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
_ADDON_ID = ADDON.getAddonInfo('id')

API_BASE = 'https://api.theintrodb.org/v2'
MIN_REQUEST_GAP = 0.4  # small gap between requests
_last_request_time = 0.0
_rate_limit_until = 0.0


def _debug_logging():
    return ADDON.getSetting('debug_logging') == 'true'


def _log_resp(body):
    if not _debug_logging():
        return
    snippet = body[:500] if len(body) > 500 else body
    xbmc.log('[TheIntroDB] TheIntroDB response: {}'.format(snippet), xbmc.LOGINFO)


def _get_api_key():
    return (ADDON.getSetting('introdb_api_key') or '').strip()


def _is_enabled():
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting('introdb_enabled') == 'true'
    except Exception:
        return ADDON.getSetting('introdb_enabled') == 'true'


def _wait_rate_limit():
    global _last_request_time
    now = time.time()
    if now < _rate_limit_until:
        xbmc.log('[TheIntroDB] TheIntroDB rate-limited until {:.0f}'.format(
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
    req.add_header('User-Agent', 'TheIntroDB Kodi Addon/1.0')
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
            xbmc.log('[TheIntroDB] TheIntroDB 429 rate limited for {}s'.format(retry),
                     xbmc.LOGWARNING)
        elif e.code == 404:
            xbmc.log('[TheIntroDB] TheIntroDB 404: not in database', xbmc.LOGINFO)
        else:
            xbmc.log('[TheIntroDB] TheIntroDB HTTP {}'.format(e.code), xbmc.LOGWARNING)
        return None
    except URLError as e:
        xbmc.log('[TheIntroDB] TheIntroDB network error: {}'.format(e.reason),
                 xbmc.LOGWARNING)
        return None
    except Exception as e:
        xbmc.log('[TheIntroDB] TheIntroDB request failed: {}'.format(e),
                 xbmc.LOGERROR)
        return None


def _pick_best_segment(segments):
    # intro array may have multiple rows — take best score
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


def _pick_best_segments_all_types(segments, segment_type):
    """Pick the best segment(s) for a given type, handling multiple segments."""
    if not segments:
        return []

    valid_segments = []
    for seg_idx, seg in enumerate(segments):
        if not isinstance(seg, dict):
            xbmc.log('[TheIntroDB] Skipping {} segment {}: not a dict'.format(segment_type, seg_idx), xbmc.LOGINFO)
            continue
        
        start = seg.get('start_ms')
        end = seg.get('end_ms')
        
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[TheIntroDB] Processing {} segment {}: start_ms={}, end_ms={}'.format(segment_type, seg_idx, start, end), xbmc.LOGINFO)
        
        # Handle different segment type requirements
        if segment_type == 'intro' or segment_type == 'recap':
            # Intro/Recap: start optional (can be null), end required
            if end is None:
                if ADDON.getSetting('debug_logging') == 'true':
                    xbmc.log('[TheIntroDB] Skipping {} segment {}: end is None'.format(segment_type, seg_idx), xbmc.LOGINFO)
                continue
            if start is None:
                start = 0
        elif segment_type == 'credits' or segment_type == 'preview':
            # Credits/Preview: start required, end optional (null = end of media)
            if start is None:
                if ADDON.getSetting('debug_logging') == 'true':
                    xbmc.log('[TheIntroDB] Skipping {} segment {}: start is None'.format(segment_type, seg_idx), xbmc.LOGINFO)
                continue
            # end can be null (means end of media)
        
        if end is not None and end <= start:
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[TheIntroDB] Skipping {} segment {}: end <= start ({} <= {})'.format(segment_type, seg_idx, end, start), xbmc.LOGINFO)
            continue
            
        conf = seg.get('confidence') if seg.get('confidence') is not None else 0.5
        count = seg.get('submission_count', 1)
        score = float(conf) + count * 0.001
        
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[TheIntroDB] Valid {} segment {}: start={}, end={}, score={:.3f}'.format(segment_type, seg_idx, start, end, score), xbmc.LOGINFO)
        
        valid_segments.append({
            'start_ms': start,
            'end_ms': end,
            'score': score,
            'confidence': conf,
            'submission_count': count
        })
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[TheIntroDB] {} valid {} segments found'.format(len(valid_segments), segment_type), xbmc.LOGINFO)
    
    # Sort by score (highest first) and return top segments
    valid_segments.sort(key=lambda x: x['score'], reverse=True)
    
    # Convert to seconds and return
    result_segments = []
    for seg in valid_segments:
        start_sec = seg['start_ms'] / 1000.0 if seg['start_ms'] is not None else None
        end_sec = seg['end_ms'] / 1000.0 if seg['end_ms'] is not None else None
        result_segments.append({
            'start': start_sec,
            'end': end_sec,
            'score': seg['score'],
            'type': segment_type
        })
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[TheIntroDB] Returning {} processed {} segments'.format(len(result_segments), segment_type), xbmc.LOGINFO)
    return result_segments


def _normalize_imdb(imdb_id):
    if not imdb_id:
        return None
    s = str(imdb_id).strip()
    if not s.startswith('tt'):
        return None
    return s


def _valid_tmdb(tmdb_id):
    try:
        return int(str(tmdb_id)) > 0
    except (ValueError, TypeError):
        return False


def _episode_nums(season, episode):
    try:
        s = int(season)
        e = int(episode)
        return s, e
    except (TypeError, ValueError):
        return None, None


def _build_url(tmdb_id, imdb_id, season, episode, is_movie):
    # prefer tmdb; if missing use imdb (api matches show/episode)
    if tmdb_id and _valid_tmdb(tmdb_id):
        tid = str(tmdb_id).strip()
        if is_movie:
            return '{}/media?tmdb_id={}'.format(API_BASE, tid), 'tmdb'
        s, e = _episode_nums(season, episode)
        if s is None or e is None or s <= 0 or e <= 0:
            return None, None
        return (
            '{}/media?tmdb_id={}&season={}&episode={}'.format(API_BASE, tid, s, e),
            'tmdb',
        )

    imdb = _normalize_imdb(imdb_id)
    if not imdb:
        return None, None

    if is_movie:
        return '{}/media?imdb_id={}'.format(API_BASE, imdb), 'imdb'

    s, e = _episode_nums(season, episode)
    if s is None or e is None or s <= 0 or e <= 0:
        return None, None
    return '{}/media?imdb_id={}&season={}&episode={}'.format(
        API_BASE, imdb, s, e), 'imdb'


def query_intro(tmdb_id=None, imdb_id=None, season=None, episode=None, is_movie=False):
    # returns intro start/end in seconds, or none
    if not _is_enabled():
        return None, None

    url, mode = _build_url(tmdb_id, imdb_id, season, episode, is_movie)
    if not url:
        if tmdb_id or imdb_id:
            xbmc.log(
                '[TheIntroDB] TheIntroDB: need TMDB id, or IMDb tt… id with season/episode for TV',
                xbmc.LOGINFO,
            )
        else:
            xbmc.log('[TheIntroDB] TheIntroDB: no TMDB or IMDb id', xbmc.LOGINFO)
        return None, None

    xbmc.log('[TheIntroDB] TheIntroDB query ({}): {}'.format(mode, url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return None, None

    api_key = _get_api_key()
    data = _do_request(url, api_key)
    if not data:
        return None, None

    if 'error' in data:
        xbmc.log('[TheIntroDB] TheIntroDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return None, None

    intro_start, intro_end = _pick_best_segment(data.get('intro', []))
    if intro_start is not None:
        xbmc.log('[TheIntroDB] TheIntroDB intro: {:.1f}s -> {:.1f}s'.format(
            intro_start, intro_end), xbmc.LOGINFO)
    else:
        xbmc.log('[TheIntroDB] TheIntroDB: no usable intro segment', xbmc.LOGINFO)

    return intro_start, intro_end


def query_all_segments(tmdb_id=None, imdb_id=None, season=None, episode=None, is_movie=False):
    # returns dict with all segment types and their segments
    if not _is_enabled():
        return {}

    url, mode = _build_url(tmdb_id, imdb_id, season, episode, is_movie)
    if not url:
        if tmdb_id or imdb_id:
            xbmc.log(
                '[TheIntroDB] TheIntroDB: need TMDB id, or IMDb tt… id with season/episode for TV',
                xbmc.LOGINFO,
            )
        else:
            xbmc.log('[TheIntroDB] TheIntroDB: no TMDB or IMDb id', xbmc.LOGINFO)
        return {}

    xbmc.log('[TheIntroDB] TheIntroDB query all segments ({}): {}'.format(mode, url), xbmc.LOGINFO)

    if not _wait_rate_limit():
        return {}

    api_key = _get_api_key()
    data = _do_request(url, api_key)
    if not data:
        return {}

    if 'error' in data:
        xbmc.log('[TheIntroDB] TheIntroDB error: {}'.format(data['error']), xbmc.LOGINFO)
        return {}

    # Process all segment types
    all_segments = {}
    
    # Debug: Log what the API actually returned (only if debug logging is enabled)
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[TheIntroDB] API response keys: {}'.format(list(data.keys())), xbmc.LOGINFO)
        xbmc.log('[TheIntroDB] Full API response (first 500 chars): {}'.format(str(data)[:500]), xbmc.LOGINFO)
        for key in data.keys():
            if key in ['intro', 'recap', 'credits', 'preview']:
                xbmc.log('[TheIntroDB] API {} raw data: {}'.format(key, len(data.get(key, []))), xbmc.LOGINFO)
    
    segment_types = ['intro', 'recap', 'credits', 'preview']
    for seg_type in segment_types:
        raw_segments = data.get(seg_type, [])
        if ADDON.getSetting('debug_logging') == 'true':
            xbmc.log('[TheIntroDB] Processing {}: {} raw segments'.format(seg_type, len(raw_segments)), xbmc.LOGINFO)
        segments = _pick_best_segments_all_types(raw_segments, seg_type)
        if segments:
            all_segments[seg_type] = segments
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[TheIntroDB] TheIntroDB {}: {} valid segments'.format(seg_type, len(segments)), xbmc.LOGINFO)
        else:
            if ADDON.getSetting('debug_logging') == 'true':
                xbmc.log('[TheIntroDB] TheIntroDB {}: no valid segments'.format(seg_type), xbmc.LOGINFO)
    
    if ADDON.getSetting('debug_logging') == 'true':
        xbmc.log('[TheIntroDB] Final segments dict: {}'.format(list(all_segments.keys())), xbmc.LOGINFO)
    return all_segments
