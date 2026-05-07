# kodi service entry: poll playback, query theintrodb, show skip ui or auto-seek
import xbmc
import xbmcaddon
import xbmcgui
from typing import List, Dict, Optional, Any, Tuple

from player import TIDBPlayer
import skipper
import overlay as overlay_mod
import submit_overlay
import introdb

ADDON = xbmcaddon.Addon()
_ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')

# String IDs for localization
STR_SKIP_INTRO = 32001
STR_SKIP_RECAP = 32003
STR_SKIP_CREDITS = 32004
STR_SKIP_PREVIEW = 32005
STR_MARK_START = 32020
STR_MARK_END = 32021
STR_SUBMIT_SUCCESS = 32022
STR_SUBMIT_FAILED = 32023

SUBMIT_WINDOW_SECS = 300.0  # first 5 minutes


class TIDBMonitor(xbmc.Monitor):
    pass


def _debug_osd(message: str) -> None:
    # optional toast spam for debugging
    if ADDON.getSetting('debug_osd') == 'true':
        xbmc.executebuiltin('Notification(TIDB, {}, 1500)'.format(message))


def _fresh_bool(key: str) -> bool:
    # read setting again from disk so gui changes apply without restart
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting(key) == 'true'
    except Exception:
        return ADDON.getSetting(key) == 'true'


def _debug_logging() -> bool:
    return ADDON.getSetting('debug_logging') == 'true'


# ── Playback session state ────────────────────────────────────────────────

class PlaybackSession:
    """Holds all mutable state for one file's playback."""
    current_file: Optional[str]
    media_ids: Optional[Dict[str, Any]]
    all_segments: Optional[Dict[str, Any]]
    processed_segments: Dict[str, Dict[str, Any]]
    next_episode_info: Optional[Dict[str, Any]]
    next_episode_checked: bool
    submit_start_sec: Optional[float]
    submit_prompted_this_pause: bool
    submit_done_for_file: bool
    was_paused_last_tick: bool

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.current_file = None
        self.media_ids = None
        self.all_segments = None
        self.processed_segments = {}
        self.next_episode_info = None
        self.next_episode_checked = False
        # Submission state
        self.submit_start_sec = None
        self.submit_prompted_this_pause = False
        self.submit_done_for_file = False
        self.was_paused_last_tick = False


# ── Segment collection ────────────────────────────────────────────────────

def _collect_enabled_segments(all_segments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gather all enabled segments from the API response, sorted chronologically."""
    result = []
    for segment_type in ('intro', 'recap', 'preview', 'credits'):
        if not _fresh_bool('enable_{}'.format(segment_type)):
            continue
        segments = all_segments.get(segment_type, [])
        for idx, seg in enumerate(segments):
            entry = seg.copy()
            entry['type'] = segment_type
            entry['index'] = idx
            result.append(entry)

    result.sort(key=lambda x: x['start'] if x['start'] is not None else 0)
    return result


# ── Skip / next-episode handling ──────────────────────────────────────────

def _resolve_segment_bounds(segment: Dict[str, Any], player: TIDBPlayer) -> Optional[Tuple[float, float, bool]]:
    """Normalise start/end; returns (start, end, is_next_episode_candidate) or None."""
    api_start = segment['start']
    api_end = segment['end']

    if api_start is None and api_end is None:
        return None

    if api_start is None:
        api_start = 0

    is_next_ep = segment['type'] in ('credits', 'preview') and api_end is None

    if api_end is None:
        try:
            api_end = player.getTotalTime() - 10
        except Exception:
            return None

    return api_start, api_end, is_next_ep


def _show_skip_overlay(player: TIDBPlayer, monitor: xbmc.Monitor, api_end: float, segment_type: str, segment_idx: int) -> Optional[bool]:
    """Show the standard skip pill and return whether it was pressed."""
    if monitor.abortRequested():
        return None  # signal to break the outer loop
    return overlay_mod.show_skip_overlay(
        intro_end=api_end,
        player=player,
        monitor=monitor,
        segment_type=segment_type,
        segment_index=segment_idx,
    )


def _handle_segment(segment: Dict[str, Any], segment_idx: int, player: TIDBPlayer, monitor: xbmc.Monitor, session: PlaybackSession, filename: str, auto_skip: bool) -> Optional[str]:
    """Process a single segment: auto-skip, next-episode, or show skip button.

    Returns 'break' if the service loop should exit, else None.
    """
    bounds = _resolve_segment_bounds(segment, player)
    if bounds is None:
        return None
    api_start, api_end, is_next_ep = bounds

    segment_type = segment['type']
    segment_key = '{}_{}'.format(segment_type, segment_idx)

    if _debug_logging():
        xbmc.log('[TheIntroDB] Processing {} segment {}: start={}, end={}'.format(
            segment_type, segment_idx, api_start, api_end), xbmc.LOGINFO)

    current_time = player.getTime() if player.isPlaying() else 0

    if not _should_show_segment_button(session.processed_segments, segment_key,
                                       current_time, api_start, api_end):
        return None

    if not player.isPlaying():
        return None

    # Resolve display name
    segment_names = {
        'intro': ADDON.getLocalizedString(STR_SKIP_INTRO),
        'recap': ADDON.getLocalizedString(STR_SKIP_RECAP),
        'credits': ADDON.getLocalizedString(STR_SKIP_CREDITS),
        'preview': ADDON.getLocalizedString(STR_SKIP_PREVIEW),
    }
    segment_name = segment_names.get(segment_type, segment_type.title())
    overlay_type = segment_type

    # Check for next-episode promotion
    if is_next_ep:
        if not session.next_episode_checked:
            session.next_episode_info = player.get_next_episode()
            session.next_episode_checked = True
        if session.next_episode_info:
            return _handle_next_episode(
                player, monitor, session, api_end, segment_type, segment_idx)

    # Auto-skip intro segments only
    if auto_skip and segment_type == 'intro':
        skipper.execute_skip(player, api_start, api_end, filename, segment_type)
        _debug_osd('Auto-skipped {}'.format(segment_name))
        xbmc.log('[TheIntroDB] Auto-skipped {} to {:.1f}s'.format(segment_name, api_end), xbmc.LOGINFO)
        return None

    # Show skip button (for non-intro when auto_skip, or always when not auto_skip)
    xbmc.log('[TheIntroDB] Showing skip overlay for {}'.format(segment_name), xbmc.LOGINFO)
    pressed = _show_skip_overlay(player, monitor, api_end, overlay_type, segment_idx)
    if pressed is None:
        return 'break'
    if pressed:
        xbmc.log('[TheIntroDB] User pressed Skip {}'.format(segment_name), xbmc.LOGINFO)
        skipper.execute_skip(player, api_start, api_end, filename, segment_type)
        _debug_osd('Skipped {} to {:.1f}s'.format(segment_name, api_end))
    else:
        xbmc.log('[TheIntroDB] User did NOT skip {}'.format(segment_name), xbmc.LOGINFO)
    return None


def _handle_next_episode(player: TIDBPlayer, monitor: xbmc.Monitor, session: PlaybackSession, api_end: float, segment_type: str, segment_idx: int) -> Optional[str]:
    """Show 'Next Episode' overlay and act on the result."""
    if monitor.abortRequested():
        return 'break'

    overlay_mod.ADDON.getLocalizedString(overlay_mod.STR_NEXT_EPISODE)
    xbmc.log('[TheIntroDB] Showing Next Episode for end-of-media {} segment'.format(segment_type),
             xbmc.LOGINFO)

    pressed = overlay_mod.show_skip_overlay(
        intro_end=api_end,
        player=player,
        monitor=monitor,
        segment_type='next_episode',
        segment_index=segment_idx,
    )
    if pressed:
        xbmc.log('[TheIntroDB] User pressed Next Episode', xbmc.LOGINFO)
        was_opened = player.play_next_episode(session.next_episode_info)
        if was_opened:
            _debug_osd('Next Episode')
        else:
            xbmc.log('[TheIntroDB] Next episode was no longer available to open', xbmc.LOGWARNING)
    else:
        xbmc.log('[TheIntroDB] User did NOT press Next Episode', xbmc.LOGINFO)
    return None


# ── Pause-detection submission ────────────────────────────────────────────

def _handle_submit_tick(session: PlaybackSession, player: TIDBPlayer, monitor: xbmc.Monitor, all_segments: Dict[str, Any], media_ids: Dict[str, Any]) -> bool:
    """Check for a pause event and run the mark-start / mark-end / submit flow.

    Mutates session in place. Returns True if the segment cache should be invalidated.
    """
    is_paused = xbmc.getCondVisibility('Player.Paused')

    # Detect fresh pause edge
    if is_paused and not session.was_paused_last_tick:
        session.submit_prompted_this_pause = False
    session.was_paused_last_tick = is_paused

    if not _should_offer_submit(session, is_paused, all_segments):
        return False

    try:
        current_time = player.getTime()
    except Exception:
        return False

    if current_time > SUBMIT_WINDOW_SECS:
        return False

    session.submit_prompted_this_pause = True

    if session.submit_start_sec is None:
        _mark_start(session, player, monitor, current_time)
        return False

    if current_time <= session.submit_start_sec:
        return False

    return _mark_end_and_submit(session, player, monitor, current_time, media_ids)


def _should_offer_submit(session: PlaybackSession, is_paused: bool, all_segments: Dict[str, Any]) -> bool:
    """Guard: all preconditions for showing the submit prompt."""
    if not _fresh_bool('enable_submissions'):
        return False
    if not bool((ADDON.getSetting('introdb_api_key') or '').strip()):
        return False
    if bool(all_segments.get('intro')):
        return False
    if session.submit_done_for_file:
        return False
    if not is_paused:
        return False
    if session.submit_prompted_this_pause:
        return False
    return True


def _mark_start(session: PlaybackSession, player: TIDBPlayer, monitor: xbmc.Monitor, current_time: float) -> None:
    """Phase 1: show the 'Mark Intro Start' pill."""
    label = ADDON.getLocalizedString(STR_MARK_START)
    xbmc.log('[TheIntroDB] Showing Mark Start at {:.1f}s'.format(current_time), xbmc.LOGINFO)

    pressed = submit_overlay.show_submit_mark_overlay(
        label_text=label, player=player, monitor=monitor)
    if pressed:
        session.submit_start_sec = current_time
        xbmc.log('[TheIntroDB] Marked intro start: {:.1f}s'.format(current_time), xbmc.LOGINFO)
        xbmc.executebuiltin(
            'Notification(TheIntroDB, Start marked at {:.0f}s — pause at end of intro, 2000)'.format(
                current_time))


def _mark_end_and_submit(session: PlaybackSession, player: TIDBPlayer, monitor: xbmc.Monitor, current_time: float, media_ids: Dict[str, Any]) -> bool:
    """Phase 2: show the 'Mark Intro End' pill, validate, confirm, and submit.

    Returns True if the segment cache should be invalidated.
    """
    label = ADDON.getLocalizedString(STR_MARK_END)
    xbmc.log('[TheIntroDB] Showing Mark End at {:.1f}s'.format(current_time), xbmc.LOGINFO)

    pressed = submit_overlay.show_submit_mark_overlay(
        label_text=label, player=player, monitor=monitor)
    if not pressed:
        return False

    start = session.submit_start_sec
    end = current_time
    duration = end - start
    xbmc.log('[TheIntroDB] Marked intro end: {:.1f}s (duration {:.1f}s)'.format(end, duration),
             xbmc.LOGINFO)

    # Validate duration (API: intro must be 5–200s)
    if duration < 5.0:
        xbmc.executebuiltin(
            'Notification(TheIntroDB, Too short — must be at least 5 seconds, 3000)')
        session.submit_start_sec = None
        return False
    if duration > 200.0:
        xbmc.executebuiltin(
            'Notification(TheIntroDB, Too long — intro max is 200 seconds, 3000)')
        session.submit_start_sec = None
        return False

    # Confirm
    confirm = xbmcgui.Dialog().yesno(
        'TheIntroDB',
        'Submit intro: {:.0f}s \u2192 {:.0f}s ({:.0f}s)?'.format(start, end, duration),
    )
    if not confirm:
        session.submit_start_sec = None
        xbmc.log('[TheIntroDB] User cancelled submission', xbmc.LOGINFO)
        return False

    # Submit
    success, msg = introdb.submit_segment(
        tmdb_id=media_ids.get('tmdb_id'),
        imdb_id=media_ids.get('imdb_id'),
        season=media_ids.get('season'),
        episode=media_ids.get('episode'),
        is_movie=media_ids.get('is_movie', False),
        segment='intro',
        start_sec=start,
        end_sec=end,
    )
    if success:
        xbmc.executebuiltin('Notification(TheIntroDB, {}, 3000)'.format(msg))
        session.submit_done_for_file = True
        return True  # invalidate cache
    else:
        xbmc.executebuiltin('Notification(TheIntroDB, {}, 4000)'.format(msg))
        session.submit_start_sec = None
        return False


# ── Main service loop ─────────────────────────────────────────────────────

def _run_service() -> None:
    monitor = TIDBMonitor()
    player = TIDBPlayer()
    session = PlaybackSession()

    xbmc.log('[TheIntroDB] Service started', xbmc.LOGINFO)

    while not monitor.abortRequested():
        if monitor.waitForAbort(1.0):
            break

        if not player.playback_started:
            session.reset()
            continue

        # skip movies that do not look like tv; player decides
        if not player.is_tv_content:
            continue

        filename = player.filename
        if not filename:
            continue

        # New file — reset everything
        if filename != session.current_file:
            session.reset()
            session.current_file = filename
            xbmc.log('[TheIntroDB] Reset segment tracking for file: {}'.format(filename),
                     xbmc.LOGINFO)

        _debug_osd('Monitoring: {}'.format(filename[-40:]))

        # ── Fetch media IDs (cached) ──
        if session.media_ids is None:
            session.media_ids = player.get_media_ids()
        media_ids = session.media_ids
        tmdb = media_ids.get('tmdb_id')
        imdb = media_ids.get('imdb_id')
        m_season = media_ids.get('season')
        m_episode = media_ids.get('episode')
        m_movie = media_ids.get('is_movie', False)

        xbmc.log('[TheIntroDB] Media IDs: tmdb={} imdb={} S{}E{} movie={}'.format(
            tmdb, imdb, m_season, m_episode, m_movie), xbmc.LOGINFO)
        _debug_osd('tmdb={} imdb={} S{}E{}'.format(
            tmdb or '-', imdb or '-', m_season or '?', m_episode or '?'))

        introdb_on = _fresh_bool('introdb_enabled')
        auto_skip = _fresh_bool('auto_skip')

        if _debug_logging():
            _raw = xbmcaddon.Addon(_ADDON_ID).getSetting('introdb_enabled')
            xbmc.log('[TheIntroDB] introdb_enabled raw={!r} lookups_on={}'.format(
                _raw, introdb_on), xbmc.LOGINFO)

        # ── Fetch segments (cached) ──
        all_segments = {}
        if introdb_on and (tmdb or imdb):
            if session.all_segments is None:
                session.all_segments = introdb.query_all_segments(
                    tmdb_id=tmdb, imdb_id=imdb,
                    season=m_season, episode=m_episode, is_movie=m_movie,
                )
            all_segments = session.all_segments or {}

        if all_segments and _debug_logging():
            xbmc.log('[TheIntroDB] API returned segments: {}'.format(
                list(all_segments.keys())), xbmc.LOGINFO)
            for seg_type, segs in all_segments.items():
                xbmc.log('[TheIntroDB] {} segments: {}'.format(seg_type, len(segs)),
                         xbmc.LOGINFO)

        # ── Process skip buttons ──
        enabled_segments = _collect_enabled_segments(all_segments)
        if _debug_logging():
            xbmc.log('[TheIntroDB] Total enabled segments to process: {}'.format(
                len(enabled_segments)), xbmc.LOGINFO)

        for seg_idx, segment in enumerate(enabled_segments):
            result = _handle_segment(
                segment, seg_idx, player, monitor, session, filename, auto_skip)
            if result == 'break':
                break

        # ── Pause-to-submit ──
        cache_dirty = _handle_submit_tick(
            session, player, monitor, all_segments, media_ids)
        if cache_dirty:
            session.all_segments = None

    xbmc.log('[TheIntroDB] Service stopped', xbmc.LOGINFO)


# ── Segment button timing ────────────────────────────────────────────────

def _should_show_segment_button(processed_segments: Dict[str, Dict[str, Any]], segment_key: str, current_time: float,
                                segment_start: float, segment_end: float, margin: float = 0.25) -> bool:
    """
    Show the skip button once per segment entry.

    If playback exits a segment and later re-enters it, including by seeking into
    the middle of the segment, the next entry gets a fresh 5 second overlay.
    """
    state = processed_segments.setdefault(segment_key, {
        'inside': False,
        'shown_for_entry': False,
        'last_time': None,
    })

    inside_segment = segment_start <= current_time < (segment_end - margin)
    previous_time = state.get('last_time')

    if not inside_segment:
        state['inside'] = False
        state['shown_for_entry'] = False
        state['last_time'] = current_time
        return False

    reentered = (not state['inside'])
    if previous_time is not None and current_time + margin < previous_time:
        reentered = True

    if reentered:
        if _debug_logging():
            xbmc.log('[TheIntroDB] Entry detected for {} at {:.1f}s'.format(
                segment_key, current_time), xbmc.LOGINFO)
        state['shown_for_entry'] = False

    state['inside'] = True
    state['last_time'] = current_time

    if state['shown_for_entry']:
        return False

    state['shown_for_entry'] = True
    return True

if __name__ == '__main__':
    _run_service()
