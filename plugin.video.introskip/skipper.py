"""Seek past the intro. Writes to storage.py only when learning_enabled is on."""
import xbmc
import xbmcaddon
import storage

ADDON = xbmcaddon.Addon()


def execute_skip(player, intro_start, intro_end, filename=None):
    if not player.isPlaying():
        return False

    offset = int(ADDON.getSetting('skip_offset') or 2)
    target = intro_end + offset

    total_time = player.getTotalTime()
    if target >= total_time:
        target = total_time - 10

    xbmc.log('[IntroSkip] Skipping intro: {:.1f}s -> {:.1f}s (target {:.1f}s)'.format(
        intro_start, intro_end, target), xbmc.LOGINFO)

    player.seekTime(target)

    if filename and ADDON.getSetting('learning_enabled') == 'true':
        try:
            storage.store_intro(filename, intro_start, intro_end)
        except Exception as e:
            xbmc.log('[IntroSkip] Failed to store intro data: {}'.format(e), xbmc.LOGERROR)

    return True
