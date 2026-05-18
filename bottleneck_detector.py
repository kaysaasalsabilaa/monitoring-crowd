import math
import numpy as np
from collections import deque
_GRID_COLS       = 8
_GRID_ROWS       = 6
_WINDOW_BASELINE = 90     
_MIN_DENSITY     = 4
_SLOW_V_THRESH   = 0.15 
_BOTTLE_RATIO    = 0.60 
_MIN_DURATION_BN = 60
_COOLDOWN_FRAMES = 45


class BottleneckDetector:

    ALERT_TYPES = ("BOTTLENECK",)

    def __init__(
        self,
        frame_width:      int   = 1280,
        frame_height:     int   = 720,
        grid_cols:        int   = _GRID_COLS,
        grid_rows:        int   = _GRID_ROWS,
        min_density:      int   = _MIN_DENSITY,
        slow_v_thresh:    float = _SLOW_V_THRESH,
        bottle_ratio:     float = _BOTTLE_RATIO,
        min_duration_bn:  int   = _MIN_DURATION_BN,
        cooldown_frames:  int   = _COOLDOWN_FRAMES,
        crowd_top_y:      int   = 0,
    ):
        self.W             = frame_width
        self.H             = frame_height
        self.grid_cols     = grid_cols
        self.grid_rows     = grid_rows
        self.min_density   = min_density
        self.slow_v_thresh = slow_v_thresh
        self.bottle_ratio  = bottle_ratio
        self.min_dur_bn    = max(1, min_duration_bn)
        self.cooldown_frames = cooldown_frames
        self.crowd_top_y   = crowd_top_y

        self._cell_h = frame_height / grid_rows
        self._cell_w = frame_width  / grid_cols

        self._density_baseline: dict[tuple, deque] = {}
        self._vnorm_baseline:   dict[tuple, deque] = {}

        for r in range(grid_rows):
            for c in range(grid_cols):
                key = (r, c)
                self._density_baseline[key] = deque(maxlen=_WINDOW_BASELINE)
                self._vnorm_baseline[key]   = deque(maxlen=_WINDOW_BASELINE)

        self._streak: dict[tuple, dict] = {}

        self._cooldown: dict[tuple, int] = {}

        self._active_zones: dict[tuple, str] = {}

        self.alert_history: list[dict] = []
        self._frame_idx = 0


    def update(self, kecepatan_track: list) -> tuple[list[dict], dict]:
        
        self._frame_idx += 1

        self._active_zones = {}

    
        cell_tracks: dict[tuple, list] = {}
        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                cell_tracks[(r, c)] = []

        for t in kecepatan_track:
            cx, cy = t["cx"], t["cy"]
            if cy < self.crowd_top_y:
                continue
            r = int(np.clip(cy / self._cell_h, 0, self.grid_rows - 1))
            c = int(np.clip(cx / self._cell_w, 0, self.grid_cols - 1))
            cell_tracks[(r, c)].append(t)

        
        for key in list(self._cooldown.keys()):
            self._cooldown[key] = max(0, self._cooldown[key] - 1)

        frame_alerts = []

        for r in range(self.grid_rows):
            for c in range(self.grid_cols):
                key     = (r, c)
                tracks  = cell_tracks[key]
                density = len(tracks)

                self._density_baseline[key].append(float(density))
                avg_v = float(np.mean([t["v_norm"] for t in tracks])) if density > 0 else 0.0
                self._vnorm_baseline[key].append(avg_v)

                # Skip jika density terlalu rendah, reset streak & tidak ada di active
                if density < self.min_density:
                    self._reset_streak(key)
                    continue

                # Butuh minimal 10 frame baseline sebelum bisa evaluasi apapun
                d_hist = list(self._density_baseline[key])
                v_hist = list(self._vnorm_baseline[key])
                if len(d_hist) < 10:
                    self._reset_streak(key)
                    continue

                density_avg_baseline = float(np.mean(d_hist[:-1])) if len(d_hist) > 1 else 0.0
                vnorm_avg_baseline   = float(np.mean(v_hist[:-1]))  if len(v_hist) > 1 else avg_v

                n_slow     = sum(1 for t in tracks if t["v_norm"] < self.slow_v_thresh)
                slow_ratio = n_slow / density if density > 0 else 0.0

                if key not in self._streak:
                    self._streak[key] = {k: 0 for k in self.ALERT_TYPES}

                is_bn = (
                    avg_v < self.slow_v_thresh
                    and slow_ratio >= self.bottle_ratio
                )
                self._streak[key]["BOTTLENECK"] = (
                    self._streak[key]["BOTTLENECK"] + 1 if is_bn else 0
                )

                min_durations = {
                    "BOTTLENECK": self.min_dur_bn,
                }

                active_type = None
                for alert_type in self.ALERT_TYPES:
                    if self._streak[key][alert_type] >= min_durations[alert_type]:
                        active_type = alert_type
                        break

                if active_type is not None:
                    self._active_zones[key] = active_type

                if active_type is not None and self._cooldown.get(key, 0) == 0:
                    alert = {
                        "frame_idx":       self._frame_idx,
                        "alert_type":      active_type,
                        "grid_row":        r,
                        "grid_col":        c,
                        "density":         density,
                        "avg_vnorm":       round(avg_v, 4),
                        "baseline_vnorm":  round(vnorm_avg_baseline, 4),
                        "n_slow":          n_slow,
                        "slow_ratio":      round(slow_ratio, 3),
                        "cx_pixel":        int((c + 0.5) * self._cell_w),
                        "cy_pixel":        int((r + 0.5) * self._cell_h),
                        "duration_frames": self._streak[key][active_type],
                    }
                    frame_alerts.append(alert)
                    self.alert_history.append(alert)
                    self._cooldown[key] = self.cooldown_frames

        return frame_alerts, self._active_zones.copy()

    def _reset_streak(self, key: tuple) -> None:
        if key in self._streak:
            for k in self.ALERT_TYPES:
                self._streak[key][k] = 0

    def reset(self) -> None:
        """Reset semua state (panggil saat video baru)."""
        self._frame_idx = 0
        self._streak.clear()
        self._cooldown.clear()
        self._active_zones.clear()
        self.alert_history.clear()
        for key in self._density_baseline:
            self._density_baseline[key].clear()
        for key in self._vnorm_baseline:
            self._vnorm_baseline[key].clear()