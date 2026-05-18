import math

_MIN_DWELL_S         = 10.0

_DRIFT_RATIO         = 1.5

_V_SLOW_THRESH       = 0.225

_GROUP_DIST_RATIO    = 1.5
_MIN_CROWD_NEARBY    = 4
_NEARBY_RADIUS_RATIO = 3.0
_COOLDOWN_S          = 5.0
_MAX_ABSENT_S        = 2.0

class StationaryDetector:
    ALERT_TYPES = ("STATIONARY_IN_CROWD", "STATIONARY_GROUP")

    def __init__(
        self,
        min_dwell_s:         float = _MIN_DWELL_S,
        drift_ratio:         float = _DRIFT_RATIO,
        v_slow_thresh:       float = _V_SLOW_THRESH,
        group_dist_ratio:    float = _GROUP_DIST_RATIO,
        min_crowd_nearby:    int   = _MIN_CROWD_NEARBY,
        nearby_radius_ratio: float = _NEARBY_RADIUS_RATIO,
        cooldown_s:          float = _COOLDOWN_S,
        max_absent_s:        float = _MAX_ABSENT_S,
    ):
        self.min_dwell_s         = min_dwell_s
        self.drift_ratio         = drift_ratio
        self.v_slow_thresh       = v_slow_thresh
        self.group_dist_ratio    = group_dist_ratio
        self.min_crowd_nearby    = min_crowd_nearby
        self.nearby_radius_ratio = nearby_radius_ratio
        self.cooldown_s          = cooldown_s
        self.max_absent_s        = max_absent_s

        self._state: dict[int, dict] = {}

        self.alert_history: list[dict] = []

    def update(
        self,
        jalur_terkonfirmasi: list,
        kecepatan_track:     list,
        timestamp:           float,
    ) -> list[dict]:

        v_by_id   = {t["track_id"]: t for t in kecepatan_track}
        pos_by_id = {t["id"]: t       for t in jalur_terkonfirmasi}
        active_ids = set(pos_by_id.keys())

        for tid, pos in pos_by_id.items():
            cx = pos["cx"]
            cy = pos["cy"]
            h  = max(pos["h"], 10.0)

            v_info   = v_by_id.get(tid)

            if v_info is not None:
                arus     = v_info.get("arus", None)
                v_smooth = v_info.get("v_norm_smooth", v_info.get("v_norm", 999))
                if arus is not None:
                    is_slow = arus in ("LAMBAT", "BOTTLENECK")
                else:
                    is_slow = v_smooth < self.v_slow_thresh
            else:
                is_slow = False

            if tid not in self._state:
                if is_slow:

                    self._state[tid] = {
                        "anchor_x":    cx,
                        "anchor_y":    cy,
                        "anchor_h":    h,
                        "since_ts":    timestamp,
                        "last_seen_ts":timestamp,
                        "alerted_ts":  -999.0,
                    }
                continue

            st = self._state[tid]
            st["last_seen_ts"] = timestamp

            if not is_slow:

                del self._state[tid]
                continue

            drift_limit = st["anchor_h"] * self.drift_ratio
            dist = math.sqrt((cx - st["anchor_x"])**2 + (cy - st["anchor_y"])**2)

            if dist > drift_limit:

                st["anchor_x"] = cx
                st["anchor_y"] = cy
                st["anchor_h"] = h
                st["since_ts"] = timestamp

        untuk_dihapus = [
            tid for tid, st in self._state.items()
            if tid not in active_ids
            and (timestamp - st["last_seen_ts"]) > self.max_absent_s
        ]
        for tid in untuk_dihapus:
            del self._state[tid]

        confirmed: list[dict] = []
        for tid, st in self._state.items():
            dwell = timestamp - st["since_ts"]
            if dwell < self.min_dwell_s:
                continue
            if (timestamp - st["alerted_ts"]) < self.cooldown_s:
                continue
            pos = pos_by_id.get(tid)
            if pos is None:
                continue
            confirmed.append({
                "tid":     tid,
                "cx":      pos["cx"],
                "cy":      pos["cy"],
                "h":       pos["h"],
                "dwell_s": round(dwell, 2),
            })

        if not confirmed:
            return []

        groups = self._cluster_nearby(confirmed)

        moving_positions = [
            (pos["cx"], pos["cy"])
            for tid, pos in pos_by_id.items()
            if tid not in self._state
        ]

        frame_alerts = []

        for group in groups:
            tids      = [g["tid"]     for g in group]
            cx_center = sum(g["cx"]   for g in group) / len(group)
            cy_center = sum(g["cy"]   for g in group) / len(group)
            avg_h     = sum(g["h"]    for g in group) / len(group)
            max_dwell = max(g["dwell_s"] for g in group)

            radius = avg_h * self.nearby_radius_ratio
            n_nearby = sum(
                1 for mx, my in moving_positions
                if math.sqrt((mx - cx_center)**2 + (my - cy_center)**2) < radius
            )

            if len(tids) >= 3:
                alert_type = "STATIONARY_GROUP"
            elif n_nearby >= self.min_crowd_nearby:
                alert_type = "STATIONARY_IN_CROWD"
            else:
                continue

            alert = {
                "timestamp":  round(timestamp, 3),
                "alert_type": alert_type,
                "track_ids":  tids,
                "cx":         round(cx_center, 1),
                "cy":         round(cy_center, 1),
                "n_tracks":   len(tids),
                "dwell_s":    max_dwell,
                "n_nearby":   n_nearby,
            }
            frame_alerts.append(alert)
            self.alert_history.append(alert)

            for g in group:
                if g["tid"] in self._state:
                    self._state[g["tid"]]["alerted_ts"] = timestamp

        return frame_alerts

    def _cluster_nearby(self, tracks: list) -> list[list]:
        if not tracks:
            return []

        n       = len(tracks)
        visited = [False] * n
        groups  = []

        for i in range(n):
            if visited[i]:
                continue
            group   = [tracks[i]]
            visited[i] = True
            queue   = [i]

            while queue:
                curr_idx = queue.pop()
                curr     = tracks[curr_idx]
                for j in range(n):
                    if visited[j]:
                        continue
                    other      = tracks[j]
                    avg_h      = (curr["h"] + other["h"]) / 2.0
                    dist_limit = avg_h * self.group_dist_ratio
                    dist = math.sqrt(
                        (curr["cx"] - other["cx"])**2 +
                        (curr["cy"] - other["cy"])**2
                    )
                    if dist < dist_limit:
                        visited[j] = True
                        group.append(other)
                        queue.append(j)

            groups.append(group)

        return groups

    def reset(self) -> None:
        self._state.clear()
        self.alert_history.clear()

_LGD_GRID_ROWS      = 4
_LGD_GRID_COLS      = 8
_LGD_MIN_PEOPLE     = 6
_LGD_MIN_DWELL_S    = 0.3
_LGD_COOLDOWN_S     = 5.0
_LGD_MERGE_ADJACENT = True

class LoiteringGridDetector:
    ALERT_TYPE = "LOITERING_GROUP"

    def __init__(
        self,
        frame_w:        int   = 1280,
        frame_h:        int   = 720,
        grid_rows:      int   = _LGD_GRID_ROWS,
        grid_cols:      int   = _LGD_GRID_COLS,
        min_people:     int   = _LGD_MIN_PEOPLE,
        min_dwell_s:    float = _LGD_MIN_DWELL_S,
        cooldown_s:     float = _LGD_COOLDOWN_S,
        merge_adjacent: bool  = _LGD_MERGE_ADJACENT,
    ):
        self.frame_w        = frame_w
        self.frame_h        = frame_h
        self.grid_rows      = grid_rows
        self.grid_cols      = grid_cols
        self.min_people     = min_people
        self.min_dwell_s    = min_dwell_s
        self.cooldown_s     = cooldown_s
        self.merge_adjacent = merge_adjacent

        self._cell_state: dict[tuple, dict] = {}

        self.alert_history: list[dict] = []

        self._last_ts: float = -1.0

    def _cell_of(self, cx: float, cy: float) -> tuple[int, int]:
        col = int(cx / self.frame_w * self.grid_cols)
        row = int(cy / self.frame_h * self.grid_rows)
        col = max(0, min(self.grid_cols - 1, col))
        row = max(0, min(self.grid_rows - 1, row))
        return (row, col)

    def _cell_center(self, row: int, col: int) -> tuple[float, float]:
        cx = (col + 0.5) / self.grid_cols * self.frame_w
        cy = (row + 0.5) / self.grid_rows * self.frame_h
        return (round(cx, 1), round(cy, 1))

    def update(
        self,
        kecepatan_track: list,
        timestamp:       float,
    ) -> list[dict]:
        dt = timestamp - self._last_ts if self._last_ts >= 0 else 0.0
        dt = min(dt, 1.0)
        self._last_ts = timestamp

        cell_count: dict[tuple, int] = {}
        for t in kecepatan_track:
            if t.get("arus") not in ("LAMBAT", "BOTTLENECK"):
                continue
            cell = self._cell_of(t["cx"], t["cy"])
            cell_count[cell] = cell_count.get(cell, 0) + 1

        semua_sel_aktif = set(cell_count.keys())

        for cell, n in cell_count.items():
            if n >= self.min_people:
                if cell not in self._cell_state:
                    self._cell_state[cell] = {
                        "streak_s":   0.0,
                        "alerted_ts": -999.0,
                        "n_people":   n,
                    }
                st = self._cell_state[cell]
                st["streak_s"] += dt
                st["n_people"]  = n
            else:

                if cell in self._cell_state:
                    del self._cell_state[cell]

        untuk_dihapus = [
            c for c in self._cell_state
            if c not in semua_sel_aktif
        ]
        for c in untuk_dihapus:
            del self._cell_state[c]

        triggered = []
        for cell, st in self._cell_state.items():
            if st["streak_s"] < self.min_dwell_s:
                continue
            if (timestamp - st["alerted_ts"]) < self.cooldown_s:
                continue
            triggered.append(cell)

        if not triggered:
            return []

        if self.merge_adjacent:
            groups = self._merge_cells(triggered)
        else:
            groups = [[c] for c in triggered]

        frame_alerts = []
        for group in groups:

            centers = [self._cell_center(r, c) for r, c in group]
            cx_avg  = sum(x for x, y in centers) / len(centers)
            cy_avg  = sum(y for x, y in centers) / len(centers)

            total_people = sum(self._cell_state[c]["n_people"] for c in group)
            max_streak   = max(self._cell_state[c]["streak_s"] for c in group)

            alert = {
                "timestamp":  round(timestamp, 3),
                "alert_type": self.ALERT_TYPE,
                "track_ids":  [],
                "cx":         round(cx_avg, 1),
                "cy":         round(cy_avg, 1),
                "n_tracks":   total_people,
                "dwell_s":    round(max_streak, 2),
                "n_nearby":   0,
                "cells":      group,
                "frame_w":    self.frame_w,
            }
            frame_alerts.append(alert)
            self.alert_history.append(alert)

            for cell in group:
                if cell in self._cell_state:
                    self._cell_state[cell]["alerted_ts"] = timestamp

        return frame_alerts

    def _merge_cells(self, cells: list[tuple]) -> list[list[tuple]]:
        cell_set = set(cells)
        visited  = set()
        groups   = []

        for cell in cells:
            if cell in visited:
                continue
            group = []
            queue = [cell]
            visited.add(cell)

            while queue:
                r, c = queue.pop()
                group.append((r, c))

                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if dr == 0 and dc == 0:
                            continue
                        neighbor = (r + dr, c + dc)
                        if neighbor in cell_set and neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)

            groups.append(group)

        return groups

    def reset(self) -> None:
        self._cell_state.clear()
        self.alert_history.clear()
        self._last_ts = -1.0