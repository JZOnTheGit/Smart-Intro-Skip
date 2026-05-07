# skip intro button windowxml — background thread closes when playhead passes intro end
import os
import threading
import time
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from typing import Optional, Callable

ADDON = xbmcaddon.Addon()
ADDON_PATH: str = ADDON.getAddonInfo('path')
# Must match the last argument to SkipOverlay / WindowXMLDialog (folder under resources/skins/default/).
_OVERLAY_RES = '1080i'
_BG_IMAGE_SHADOW = 3003
_BG_IMAGE_FILL = 3004

# String IDs for localization
STR_SKIP_INTRO = 32001
STR_SKIP_RECAP = 32003
STR_SKIP_CREDITS = 32004
STR_SKIP_PREVIEW = 32005
STR_NEXT_EPISODE = 32012

# must match overlay.xml window id
OVERLAY_WINDOW_ID = 14000

ACTION_SELECT = 7
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
BUTTON_ID = 3001

_POLL_INTERVAL = 0.5
_DISPLAY_DURATION = 5.0


def _rounded_rect_texture_path() -> str:
    joined = os.path.join(
        ADDON_PATH, 'resources', 'skins', 'default', _OVERLAY_RES, 'rounded_rect.png')
    return xbmcvfs.translatePath(joined)


class SkipOverlay(xbmcgui.WindowXMLDialog):

    def __new__(cls, xml_file: str, addon_path: str, skin: str, res: str,
                callback: Optional[Callable[[], None]] = None, intro_end: Optional[float] = None,
                player: Optional[xbmc.Player] = None, monitor: Optional[xbmc.Monitor] = None,
                segment_type: str = 'intro', segment_index: int = 0) -> 'SkipOverlay':
        return super(SkipOverlay, cls).__new__(cls)

    def __init__(self, xml_file: str, addon_path: str, skin: str, res: str,
                 callback: Optional[Callable[[], None]] = None, intro_end: Optional[float] = None,
                 player: Optional[xbmc.Player] = None, monitor: Optional[xbmc.Monitor] = None,
                 segment_type: str = 'intro', segment_index: int = 0) -> None:
        super(SkipOverlay, self).__init__(xml_file, addon_path, skin, res)
        self._skip_pressed: bool = False
        self._callback: Optional[Callable[[], None]] = callback
        self._intro_end: Optional[float] = intro_end
        self._player: Optional[xbmc.Player] = player
        self._monitor: Optional[xbmc.Monitor] = monitor
        self._poll_thread: Optional[threading.Thread] = None
        self._closed: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._segment_type: str = segment_type
        self._segment_index: int = segment_index
        self._display_deadline: Optional[float] = None

    @property
    def skip_pressed(self) -> bool:
        return self._skip_pressed

    def _get_segment_button_text(self, segment_type: str) -> str:
        """Get the appropriate button text for the segment type."""
        segment_texts = {
            'intro': ADDON.getLocalizedString(STR_SKIP_INTRO),
            'recap': ADDON.getLocalizedString(STR_SKIP_RECAP),
            'credits': ADDON.getLocalizedString(STR_SKIP_CREDITS),
            'preview': ADDON.getLocalizedString(STR_SKIP_PREVIEW),
            'next_episode': ADDON.getLocalizedString(STR_NEXT_EPISODE)
        }
        base_text = segment_texts.get(segment_type, ADDON.getLocalizedString(STR_SKIP_INTRO))
        
        return base_text

    def onInit(self) -> None:
        mon = self._monitor if self._monitor is not None else xbmc.Monitor()
        if mon.abortRequested():
            self._dismiss_main_thread()
            return
        
        # Reload pill textures by absolute path (relative paths sometimes fail for addon WindowXML on some platforms).
        try:
            tex = _rounded_rect_texture_path()
            self.getControl(_BG_IMAGE_SHADOW).setImage(tex)
            self.getControl(_BG_IMAGE_FILL).setImage(tex)
        except Exception as e:
            xbmc.log('[TheIntroDB] Overlay background textures: {}'.format(e), xbmc.LOGWARNING)
        
        # Set dynamic button text based on segment type
        try:
            button_text = self._get_segment_button_text(self._segment_type)
            button_control = self.getControl(BUTTON_ID)
            if isinstance(button_control, xbmcgui.ControlButton):
                button_control.setLabel(button_text)
        except Exception as e:
            xbmc.log('[TheIntroDB] Failed to set button text: {}'.format(e), xbmc.LOGWARNING)
        
        try:
            self.setFocusId(BUTTON_ID)
        except Exception:
            pass
        if self._intro_end is not None and self._player is not None:
            self._display_deadline = time.time() + _DISPLAY_DURATION
            self._poll_thread = threading.Thread(target=self._poll_loop)
            self._poll_thread.daemon = True
            self._poll_thread.start()

    def onClick(self, controlId: int) -> None:
        if controlId == BUTTON_ID:
            self._do_skip()

    def onAction(self, action: xbmcgui.Action) -> None:
        aid = action.getId()
        if aid == ACTION_SELECT:
            try:
                if self.getFocusId() == BUTTON_ID:
                    self._do_skip()
            except Exception:
                pass
            return
        if aid in (ACTION_PREVIOUS_MENU, ACTION_BACK):
            self._dismiss_main_thread()

    def _do_skip(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._skip_pressed = True
        self._stop_poll_thread()
        if self._callback:
            try:
                self._callback()
            except Exception:
                pass
        self._dismiss_main_thread()

    def _poll_loop(self) -> None:
        # close from worker thread using dialog.close builtin — kodi does not like gui from random threads otherwise
        mon = self._monitor if self._monitor is not None else xbmc.Monitor()
        # No immediate getTime check: playback advances while WindowXML loads; that race closed the dialog instantly.
        while True:
            with self._lock:
                if self._closed:
                    return
            if mon.abortRequested():
                self._close_from_bg_thread()
                return
            if mon.waitForAbort(_POLL_INTERVAL):
                self._close_from_bg_thread()
                return
            try:
                pl = self._player
                if self._display_deadline is not None and time.time() >= self._display_deadline:
                    self._close_from_bg_thread()
                    return
                if pl and pl.isPlaying() and self._intro_end is not None:
                    current_time = pl.getTime()
                    if current_time >= self._intro_end:
                        self._close_from_bg_thread()
                        return
                elif pl and not pl.isPlaying():
                    self._close_from_bg_thread()
                    return
            except Exception:
                pass

    def _close_from_bg_thread(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        try:
            self.close()
        except Exception as e:
            xbmc.log('[TheIntroDB] Overlay close failed: {}'.format(e), xbmc.LOGWARNING)

    def _stop_poll_thread(self) -> None:
        with self._lock:
            self._closed = True

    def _dismiss_main_thread(self) -> None:
        self._stop_poll_thread()
        try:
            self.close()
        except Exception:
            pass


def show_skip_overlay(callback: Optional[Callable[[], None]] = None, intro_end: Optional[float] = None,
                      player: Optional[xbmc.Player] = None, monitor: Optional[xbmc.Monitor] = None,
                      segment_type: str = 'intro', segment_index: int = 0) -> bool:
    # blocks until window closes; true if user hit skip
    mon = monitor if monitor is not None else xbmc.Monitor()
    if mon.abortRequested():
        return False
    try:
        wnd = SkipOverlay(
            'overlay.xml',
            ADDON_PATH,
            'default',
            _OVERLAY_RES,
            callback=callback,
            intro_end=intro_end,
            player=player,
            monitor=monitor,
            segment_type=segment_type,
            segment_index=segment_index,
        )
        wnd.doModal()
        pressed = wnd.skip_pressed
        del wnd
        return pressed
    except Exception as e:
        xbmc.log('[TheIntroDB] Overlay error: {}'.format(e), xbmc.LOGERROR)
        return False
