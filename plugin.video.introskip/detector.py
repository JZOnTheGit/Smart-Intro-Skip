"""Old heuristic detector — time window + rough audio + learned JSON. Service doesn't use this right now but I kept the file."""
import json
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()

SENSITIVITY_MAP = {
    '0': {'time_weight': 0.60, 'audio_weight': 0.15},
    '1': {'time_weight': 0.75, 'audio_weight': 0.15},
    '2': {'time_weight': 0.85, 'audio_weight': 0.10},
}

RAMP_SECONDS = 3.0


class IntroDetector(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self._audio_history = []
        self._confidence_history = []
        self._spike_sustained_count = 0
        self._intro_start = None
        self._intro_end = None
        self._peak_confidence = 0.0
        self._learned_start = None
        self._learned_end = None
        self._learned_boost = 0.0
        self._detection_complete = False
        self._prev_db = None

    def set_learned_data(self, start, end, boost):
        self._learned_start = start
        self._learned_end = end
        self._learned_boost = boost

    def _get_settings(self):
        sensitivity = ADDON.getSetting('detection_sensitivity') or '1'
        params = SENSITIVITY_MAP.get(sensitivity, SENSITIVITY_MAP['1'])
        try:
            window_start = int(ADDON.getSetting('intro_window_start') or 0)
        except (ValueError, TypeError):
            window_start = 0
        try:
            window_end = int(ADDON.getSetting('intro_window_end') or 180)
        except (ValueError, TypeError):
            window_end = 180
        try:
            intro_dur = int(ADDON.getSetting('default_intro_duration') or 60)
        except (ValueError, TypeError):
            intro_dur = 60
        return params, window_start, window_end, intro_dur

    def _time_score(self, current_time, window_start, window_end):
        # ramps up/down at the edges of the window so confidence isn't a brick wall
        if current_time < window_start or current_time > window_end:
            return 0.0
        elapsed = current_time - window_start
        remaining = window_end - current_time
        if elapsed < RAMP_SECONDS:
            return elapsed / RAMP_SECONDS
        if remaining < RAMP_SECONDS:
            return remaining / RAMP_SECONDS
        return 1.0

    def _collect_audio_energy(self):
        # Player.Volume infolabel if I can parse it, else Application volume — hacky but cheap
        try:
            db_str = xbmc.getInfoLabel('Player.Volume')
            if db_str:
                db_val = float(db_str.replace(' dB', '').replace(',', '.'))
                self._prev_db = db_val
                normalised = max(0.0, min(1.0, (db_val + 60.0) / 60.0))
                return normalised
        except (ValueError, TypeError):
            pass

        try:
            query = json.dumps({
                'jsonrpc': '2.0',
                'method': 'Application.GetProperties',
                'params': {'properties': ['volume', 'muted']},
                'id': 1
            })
            response = json.loads(xbmc.executeJSONRPC(query))
            volume = response.get('result', {}).get('volume', 50)
            muted = response.get('result', {}).get('muted', False)
            if muted:
                return 0.0
            return volume / 100.0
        except Exception:
            return 0.5

    def _audio_spike_score(self):
        if len(self._audio_history) < 5:
            return 0.0

        recent = self._audio_history[-5:]
        older = self._audio_history[:-5] if len(self._audio_history) > 5 else [0.3]

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older) if older else 0.3
        delta = avg_recent - avg_older

        if delta > 0.10 and avg_recent > 0.4:
            self._spike_sustained_count += 1
        else:
            self._spike_sustained_count = max(0, self._spike_sustained_count - 1)

        if self._spike_sustained_count >= 3:
            return min(1.0, 0.5 + delta)
        if delta > 0.08:
            return min(0.6, delta * 3)
        return 0.0

    def _silence_score(self):
        if len(self._audio_history) < 8:
            return 0.0

        first_half = self._audio_history[-8:-4]
        second_half = self._audio_history[-4:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        if avg_first < 0.3 and avg_second > 0.5:
            return 0.8
        if avg_first < 0.4 and avg_second - avg_first > 0.15:
            return 0.4
        return 0.0

    def update(self, current_time):
        # one service loop iteration worth of state
        if self._detection_complete:
            return {
                'confidence': self._peak_confidence,
                'intro_start': self._intro_start,
                'intro_end': self._intro_end,
                'detection_complete': True,
                'from_learned': self._learned_boost > 0,
            }

        if self._learned_boost >= 1.0 and self._learned_start is not None:
            return {
                'confidence': 1.0,
                'intro_start': self._learned_start,
                'intro_end': self._learned_end,
                'detection_complete': True,
                'from_learned': True,
            }

        params, window_start, window_end, intro_dur = self._get_settings()

        if current_time < window_start or current_time > window_end + 10:
            if current_time > window_end + 10 and self._peak_confidence > 0.5:
                self._detection_complete = True
            return {
                'confidence': 0.0,
                'intro_start': self._intro_start,
                'intro_end': self._intro_end,
                'detection_complete': self._detection_complete,
                'from_learned': False,
            }

        use_audio = ADDON.getSetting('audio_detection') != 'false'
        if use_audio:
            energy = self._collect_audio_energy()
            self._audio_history.append(energy)
            if len(self._audio_history) > 60:
                self._audio_history = self._audio_history[-60:]

        t_score = self._time_score(current_time, window_start, window_end)

        a_spike = 0.0
        s_score = 0.0
        if use_audio and len(self._audio_history) >= 5:
            a_spike = self._audio_spike_score()
            s_score = self._silence_score()

        audio_combined = max(a_spike, s_score)
        confidence = t_score * params['time_weight'] + audio_combined * params['audio_weight']

        if self._learned_boost > 0 and self._learned_start is not None:
            learned_proximity = 1.0 - min(1.0, abs(current_time - self._learned_start) / 30.0)
            confidence += self._learned_boost * 0.3 * max(0.0, learned_proximity)

        confidence = min(1.0, confidence)

        if confidence > self._peak_confidence:
            self._peak_confidence = confidence

        if confidence > 0.4 and self._intro_start is None:
            self._intro_start = current_time

        if self._intro_start is not None and confidence < 0.2 and current_time > self._intro_start + 10:
            if self._intro_end is None:
                self._intro_end = current_time

        if self._intro_start and not self._intro_end:
            if self._learned_end:
                self._intro_end = self._learned_end
            else:
                self._intro_end = self._intro_start + intro_dur

        self._confidence_history.append(confidence)
        if len(self._confidence_history) > 30:
            self._confidence_history = self._confidence_history[-30:]

        debug = ADDON.getSetting('debug_logging') == 'true'
        if debug:
            xbmc.log('[IntroSkip] t={:.0f}s conf={:.2f} (time={:.2f} audio={:.2f} silence={:.2f} start={} end={})'.format(
                current_time, confidence, t_score, a_spike, s_score,
                self._intro_start, self._intro_end), xbmc.LOGINFO)

        return {
            'confidence': confidence,
            'intro_start': self._intro_start,
            'intro_end': self._intro_end,
            'detection_complete': self._detection_complete,
            'from_learned': self._learned_boost > 0,
        }
