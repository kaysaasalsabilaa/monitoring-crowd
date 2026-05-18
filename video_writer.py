import cv2
import numpy as np

_C_LANCAR     = (80,  200,  72)
_C_LAMBAT     = (0,   200, 220)
_C_BOTTLENECK = (0,    60, 230)
_C_WHITE      = (255, 255, 255)
_C_PANEL      = (15,   15,  15)
_C_ZONE_LINE  = (0,    80, 200)

_BG_LANCAR     = (0,  100,  40)
_BG_LAMBAT     = (0,  120, 140)
_BG_BOTTLENECK = (0,   30, 160)

def _arus_style(track_id, ids_lambat, ids_bottleneck):
    if track_id in ids_bottleneck:
        return _C_BOTTLENECK, _BG_BOTTLENECK, "B"
    elif track_id in ids_lambat:
        return _C_LAMBAT, _BG_LAMBAT, "L"
    else:
        return _C_LANCAR, _BG_LANCAR, ""

def _put_text_bg(img, text, org, font_scale=0.42, thickness=1,
                 text_color=_C_WHITE, bg_color=_BG_LANCAR, pad=2):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = org
    cv2.rectangle(img,
                  (x - pad,      y - th - pad),
                  (x + tw + pad, y + baseline + pad),
                  bg_color, -1)
    cv2.putText(img, text, (x, y), font, font_scale,
                text_color, thickness, cv2.LINE_AA)

def _draw_background_zone_line(frame, crowd_top_y: int):
    h, w = frame.shape[:2]
    dash_len = 20
    gap_len  = 10
    x = 0
    while x < w:
        x_end = min(x + dash_len, w)
        cv2.line(frame, (x, crowd_top_y), (x_end, crowd_top_y), _C_ZONE_LINE, 1)
        x += dash_len + gap_len
    _put_text_bg(frame, f"CROWD ZONE > y={crowd_top_y}", (4, crowd_top_y - 4),
                 font_scale=0.32, bg_color=_C_ZONE_LINE)

def _draw_tracks(frame, jalur_terkonfirmasi,
                 ids_lambat=None, ids_bottleneck=None, crowd_top_y=270):
    ids_lambat     = ids_lambat     or set()
    ids_bottleneck = ids_bottleneck or set()
    n_border = 0
    h, w = frame.shape[:2]
    border_margin = 15

    for t in jalur_terkonfirmasi:
        cx, cy = t["cx"], t["cy"]
        th, tw = t["h"],  t["w"]
        x1 = int(cx - tw / 2)
        y1 = int(cy - th / 2)
        x2 = int(cx + tw / 2)
        y2 = int(cy + th / 2)

        box_color, id_bg, suffix = _arus_style(t["id"], ids_lambat, ids_bottleneck)
        di_tepi = (x2 >= w - border_margin or y2 >= h - border_margin
                   or x1 <= border_margin)
        thickness = 1 if di_tepi else 2
        if t["id"] in ids_bottleneck:
            thickness += 1

        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness)
        if di_tepi:
            n_border += 1

        label = f"ID:{t['id']}{suffix}"
        _put_text_bg(frame, label, (max(x1, 0), max(y1 - 2, 12)),
                     font_scale=0.38, bg_color=id_bg)

    return n_border

def _draw_info_panel(frame, frame_idx: int, timestamp: float,
                     count: int, n_slow: int = 0, n_bottleneck: int = 0,
                     n_ghost: int = 0, n_border: int = 0, crowd_top_y: int = 270):
    font   = cv2.FONT_HERSHEY_SIMPLEX
    fscale = 0.42
    thick  = 1
    pad_x  = 8
    pad_y  = 8
    line_h = 17

    lines = [
        (f"Frame     : {frame_idx}",               _C_WHITE),
        (f"Time      : {timestamp:7.2f} s",         _C_WHITE),
        (f"Count     : {count}",                    _C_WHITE),
        (f"Lambat    : {n_slow}",     (0, 200, 220) if n_slow > 0       else _C_WHITE),
        (f"Bottleneck: {n_bottleneck}", (0, 60, 230) if n_bottleneck > 0 else _C_WHITE),
        (f"Ghost     : {n_ghost}",    (0,  60, 220) if n_ghost > 0      else _C_WHITE),
        (f"Border    : {n_border}",   (180, 180, 0) if n_border > 0     else _C_WHITE),
    ]

    max_tw = max(cv2.getTextSize(l, font, fscale, thick)[0][0] for l, _ in lines)
    pw = max_tw + pad_x * 2
    ph = len(lines) * line_h + pad_y * 2

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (pw, ph), _C_PANEL, -1)
    cv2.addWeighted(overlay, 0.65, frame, 0.35, 0, frame)

    for i, (line, color) in enumerate(lines):
        y = pad_y + (i + 1) * line_h - 3
        cv2.putText(frame, line, (pad_x, y), font, fscale, color, thick, cv2.LINE_AA)

def _draw_abnormal_banner(frame, alert: dict):
    h, w = frame.shape[:2]
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 32), (0, 0, 180), -1)
    cv2.addWeighted(overlay, 0.80, frame, 0.20, 0, frame)
    msg = (f"!! BOTTLENECK  |  Zone ({alert['grid_row']},{alert['grid_col']})  |  "
           f"Density: {alert['density']} orang  |  SlowRatio: {alert['slow_ratio']:.0%}")
    cv2.putText(frame, msg, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)

_BD_STYLES = {
    "BOTTLENECK":       ((0,   30, 220), (0,  20, 160), "🔴 BOTTLENECK"),
}

_SD_STYLES = {
    "STATIONARY_INDIVIDUAL": ((0, 220, 220), (0, 120, 120), "DIAM"),
    "STATIONARY_IN_CROWD":   ((0,  40, 220), (0,  20, 140), "DIAM DI KERAMAIAN!"),
    "STATIONARY_GROUP":      ((0, 140, 220), (0,  80, 150), "KELOMPOK DIAM"),
    "LOITERING_GROUP":       ((0, 180,  80), (0, 100,  40), "KELOMPOK BERGEROMBOL"),
}

def _draw_sd_alerts(frame, sd_alerts: list):
    if not sd_alerts:
        return
    font = cv2.FONT_HERSHEY_SIMPLEX
    for alert in sd_alerts:
        cx    = int(alert["cx"])
        cy    = int(alert["cy"])
        atype = alert["alert_type"]
        circle_c, bg_c, label_text = _SD_STYLES.get(atype, ((200, 200, 0), (100, 100, 0), atype))

        if atype == "LOITERING_GROUP":
            radius = max(80, int(alert.get("frame_w", 1280) / 12 * 0.6))
        else:
            radius = max(20, 14 * alert.get("n_tracks", 1))
        cv2.circle(frame, (cx, cy), radius, circle_c, 3)
        overlay = frame.copy()
        cv2.circle(overlay, (cx, cy), radius, circle_c, -1)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        info = f"{label_text} {alert['dwell_s']:.0f}s"
        scale = 0.42
        thick = 1
        (tw, th), _ = cv2.getTextSize(info, font, scale, thick)
        tx = cx - tw // 2
        ty = max(cy - radius - 5, th + 4)
        cv2.rectangle(frame, (tx - 2, ty - th - 4), (tx + tw + 4, ty + 4), bg_c, -1)
        cv2.putText(frame, info, (tx, ty), font, scale, (255, 255, 255), thick, cv2.LINE_AA)

def _draw_trails(frame, kecepatan_track: list, active_zones: dict,
                 grid_rows: int, grid_cols: int):
    if not kecepatan_track:
        return

    overlay  = frame.copy()

    for t in kecepatan_track:
        history = t.get("pos_history", [])
        if len(history) < 2:
            continue

        trail_color = (180, 180, 180)

        n = len(history)
        for i in range(1, n):
            alpha = (i / n) ** 1.5
            x0, y0 = int(history[i - 1][0]), int(history[i - 1][1])
            x1, y1 = int(history[i][0]),     int(history[i][1])
            cv2.line(overlay, (x0, y0), (x1, y1), trail_color, max(1, int(alpha * 3)))

    cv2.addWeighted(overlay, 0.30, frame, 0.70, 0, frame)

def _draw_bd_alerts(frame, bd_alerts: list, active_zones: dict,
                    grid_rows: int, grid_cols: int):
    h, w   = frame.shape[:2]
    cell_h = h / grid_rows
    cell_w = w / grid_cols
    font   = cv2.FONT_HERSHEY_SIMPLEX

    new_alert_keys = {(a["grid_row"], a["grid_col"]) for a in bd_alerts}

    for (r, c), atype in active_zones.items():
        if (r, c) in new_alert_keys:
            continue
        x1 = int(c * cell_w);  y1 = int(r * cell_h)
        x2 = int((c+1) * cell_w); y2 = int((r+1) * cell_h)
        box_c, bg_c, label_text = _BD_STYLES.get(atype, ((0,0,200),(0,0,140),atype))
        cv2.rectangle(frame, (x1,y1), (x2,y2), box_c, 2)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1,y1), (x2,y2), box_c, -1)
        cv2.addWeighted(overlay, 0.06, frame, 0.94, 0, frame)
        cv2.putText(frame, label_text.split()[-1], (x1+4, y2-6),
                    font, 0.35, box_c, 1, cv2.LINE_AA)

    for alert in bd_alerts:
        r, c = alert["grid_row"], alert["grid_col"]
        x1 = int(c * cell_w);  y1 = int(r * cell_h)
        x2 = int((c+1) * cell_w); y2 = int((r+1) * cell_h)
        atype = alert["alert_type"]
        box_c, bg_c, label_text = _BD_STYLES.get(atype, ((0,0,200),(0,0,140),atype))
        cv2.rectangle(frame, (x1,y1), (x2,y2), box_c, 3)
        overlay = frame.copy()
        cv2.rectangle(overlay, (x1,y1), (x2,y2), box_c, -1)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)
        info = (f"{label_text}  d={alert['density']} "
                f"v={alert['avg_vnorm']:.2f} sl={alert['slow_ratio']:.0%}")
        scale = 0.45; thick = 1
        (tw, th), _ = cv2.getTextSize(info, font, scale, thick)
        tx = max(x1, 2); ty = max(y1 - 5, th + 4)
        cv2.rectangle(frame, (tx-2, ty-th-4), (tx+tw+4, ty+4), bg_c, -1)
        cv2.putText(frame, info, (tx, ty), font, scale, (255,255,255), thick, cv2.LINE_AA)

def _draw_legend(frame):
    h, w = frame.shape[:2]
    items = [(_C_LANCAR,"Lancar"), (_C_LAMBAT,"Lambat"), (_C_BOTTLENECK,"Bottleneck")]
    font=cv2.FONT_HERSHEY_SIMPLEX; fscale=0.38; thick=1; lh=16; pad=8
    box_w=130; box_h=len(items)*lh+pad*2
    x0=w-box_w-6; y0=h-box_h-6
    overlay=frame.copy()
    cv2.rectangle(overlay,(x0,y0),(w-6,h-6),(20,20,20),-1)
    cv2.addWeighted(overlay,0.70,frame,0.30,0,frame)
    for i,(color,label) in enumerate(items):
        y=y0+pad+(i+1)*lh-3
        cv2.rectangle(frame,(x0+pad,y-8),(x0+pad+12,y+2),color,-1)
        cv2.putText(frame,label,(x0+pad+16,y),font,fscale,_C_WHITE,thick,cv2.LINE_AA)

def _draw_bd_alerts_monitoring(frame, bd_alerts: list, active_zones: dict,
                               grid_rows: int, grid_cols: int):
    h, w   = frame.shape[:2]
    cell_h = h / grid_rows
    cell_w = w / grid_cols
    font   = cv2.FONT_HERSHEY_SIMPLEX

    _MON_STYLES = {
        "BOTTLENECK":       ((0,  30, 220), (0,  15, 160)),
    }
    _MON_LABELS = {
        "BOTTLENECK":       "!! BOTTLENECK",
    }

    new_alert_keys = {(a["grid_row"], a["grid_col"]) for a in bd_alerts}

    for (r, c), atype in active_zones.items():
        if (r, c) in new_alert_keys:
            continue
        x1=int(c*cell_w); y1=int(r*cell_h)
        x2=int((c+1)*cell_w); y2=int((r+1)*cell_h)
        box_c, _ = _MON_STYLES.get(atype, ((0,0,200),(0,0,120)))
        overlay=frame.copy()
        cv2.rectangle(overlay,(x1,y1),(x2,y2),box_c,-1)
        cv2.addWeighted(overlay,0.15,frame,0.85,0,frame)
        cv2.rectangle(frame,(x1,y1),(x2,y2),box_c,3)

    for alert in bd_alerts:
        r,c   = alert["grid_row"], alert["grid_col"]
        x1=int(c*cell_w); y1=int(r*cell_h)
        x2=int((c+1)*cell_w); y2=int((r+1)*cell_h)
        atype = alert["alert_type"]
        box_c, bg_c = _MON_STYLES.get(atype, ((0,0,200),(0,0,120)))
        label_text  = _MON_LABELS.get(atype, atype)
        overlay=frame.copy()
        cv2.rectangle(overlay,(x1,y1),(x2,y2),box_c,-1)
        cv2.addWeighted(overlay,0.35,frame,0.65,0,frame)
        cv2.rectangle(frame,(x1,y1),(x2,y2),box_c,5)
        scale=0.70; thick=2
        (tw,th),_ = cv2.getTextSize(label_text,font,scale,thick)
        tx=max(x1+(x2-x1-tw)//2,x1+4); ty=(y1+y2)//2+th//2
        cv2.rectangle(frame,(tx-6,ty-th-8),(tx+tw+6,ty+6),bg_c,-1)
        cv2.putText(frame,label_text,(tx,ty),font,scale,(255,255,255),thick,cv2.LINE_AA)
        d_info=f"d={alert['density']}  sl={alert['slow_ratio']:.0%}"
        ds=0.42
        (dw,dh),_=cv2.getTextSize(d_info,font,ds,1)
        dx=max(x1+(x2-x1-dw)//2,x1+4); dy=ty+dh+10
        if dy < y2-4:
            cv2.putText(frame,d_info,(dx,dy),font,ds,(220,220,220),1,cv2.LINE_AA)

def _draw_sd_alerts_monitoring(frame, sd_alerts: list):
    if not sd_alerts:
        return
    font = cv2.FONT_HERSHEY_SIMPLEX
    _MON_SD_LABELS = {
        "STATIONARY_INDIVIDUAL": "DIAM",
        "STATIONARY_IN_CROWD":   "!! DIAM DI KERAMAIAN",
        "STATIONARY_GROUP":      "!! KELOMPOK DIAM",
        "LOITERING_GROUP":       "!! KELOMPOK BERGEROMBOL",
    }
    for alert in sd_alerts:
        cx=int(alert["cx"]); cy=int(alert["cy"]); atype=alert["alert_type"]
        circle_c,bg_c,_ = _SD_STYLES.get(atype,((200,200,0),(100,100,0),""))
        label_text = _MON_SD_LABELS.get(atype,atype)

        if atype == "LOITERING_GROUP":
            radius = max(100, int(alert.get("frame_w", 1280) / 12 * 0.65))
        else:
            radius = max(30, 20 * alert.get("n_tracks", 1))
        overlay=frame.copy()
        cv2.circle(overlay,(cx,cy),radius,circle_c,-1)
        cv2.addWeighted(overlay,0.25,frame,0.75,0,frame)
        cv2.circle(frame,(cx,cy),radius,circle_c,4)
        scale=0.55; thick=2
        info=f"{label_text} {alert['dwell_s']:.0f}s"
        (tw,th),_=cv2.getTextSize(info,font,scale,thick)
        tx=cx-tw//2; ty=max(cy-radius-8,th+6)
        cv2.rectangle(frame,(tx-4,ty-th-6),(tx+tw+6,ty+6),bg_c,-1)
        cv2.putText(frame,info,(tx,ty),font,scale,(255,255,255),thick,cv2.LINE_AA)

def _draw_info_panel_monitoring(frame, frame_idx: int, timestamp: float,
                                count: int, n_slow: int = 0, n_bottleneck: int = 0):
    font=cv2.FONT_HERSHEY_SIMPLEX; pad_x=12; pad_y=10; line_h=22; fscale=0.55; thick=1
    lines = [
        (f"Frame     : {frame_idx}",               _C_WHITE),
        (f"Waktu     : {timestamp:7.2f} s",         _C_WHITE),
        (f"Terdeteksi: {count} orang",              _C_WHITE),
        (f"Lambat    : {n_slow}",   (0,200,220) if n_slow>0       else _C_WHITE),
        (f"Bottleneck: {n_bottleneck}", (0,60,230) if n_bottleneck>0 else _C_WHITE),
    ]
    max_tw=max(cv2.getTextSize(l,font,fscale,thick)[0][0] for l,_ in lines)
    pw=max_tw+pad_x*2; ph=len(lines)*line_h+pad_y*2
    overlay=frame.copy()
    cv2.rectangle(overlay,(0,0),(pw,ph),(10,10,10),-1)
    cv2.addWeighted(overlay,0.80,frame,0.20,0,frame)
    for i,(line,color) in enumerate(lines):
        y=pad_y+(i+1)*line_h-3
        cv2.putText(frame,line,(pad_x,y),font,fscale,color,thick,cv2.LINE_AA)

def _draw_legend_monitoring(frame):
    h,w=frame.shape[:2]
    items=[
        ((0, 30,220),"BOTTLENECK"),
        ((0,220,220),"DIAM / KELOMPOK DIAM"),
    ]
    font=cv2.FONT_HERSHEY_SIMPLEX; fscale=0.40; thick=1; lh=18; pad=10
    box_w=205; box_h=len(items)*lh+pad*2
    x0=w-box_w-8; y0=h-box_h-8
    overlay=frame.copy()
    cv2.rectangle(overlay,(x0,y0),(w-8,h-8),(15,15,15),-1)
    cv2.addWeighted(overlay,0.80,frame,0.20,0,frame)
    for i,(color,label) in enumerate(items):
        y=y0+pad+(i+1)*lh-3
        cv2.rectangle(frame,(x0+pad,y-9),(x0+pad+14,y+3),color,-1)
        cv2.putText(frame,label,(x0+pad+20,y),font,fscale,_C_WHITE,thick,cv2.LINE_AA)

class AnnotatedVideoWriter:

    def __init__(self, out_path: str, fps: float, width: int, height: int,
                 crowd_top_y: int = 270, show_zone_line: bool = False,
                 show_heatmap: bool = True, show_legend: bool = True,
                 monitoring_mode: bool = False, heatmap_engine=None):
        self.out_path        = out_path
        self._fps            = max(fps, 1.0)
        self._w              = int(width)
        self._h              = int(height)
        self.crowd_top_y     = crowd_top_y
        self.show_zone_line  = show_zone_line
        self.show_heatmap    = show_heatmap
        self.show_legend     = show_legend
        self.monitoring_mode = monitoring_mode

        if show_heatmap:
            if heatmap_engine is not None:
                self._hm = heatmap_engine
            else:
                from heatmap import HeatmapEngine
                self._hm = HeatmapEngine(frame_width=width, frame_height=height,
                                         crowd_top_y=crowd_top_y)
        else:
            self._hm = None

        self._hm_rows = self._hm.grid_rows if self._hm is not None else 6
        self._hm_cols = self._hm.grid_cols if self._hm is not None else 8

        cc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(out_path, cc, self._fps, (self._w, self._h))

        if not self._writer.isOpened():
            import os
            base, _ = os.path.splitext(out_path)
            self.out_path = base + ".avi"
            self._writer  = cv2.VideoWriter(
                self.out_path, cv2.VideoWriter_fourcc(*"XVID"),
                self._fps, (self._w, self._h))

        self._ok = self._writer.isOpened()

        self._active_sd: dict[int, dict] = {}

    @property
    def is_open(self) -> bool:
        return self._ok

    def _update_active_sd(
        self,
        sd_alerts:       list,
        kecepatan_track: list,
        v_slow_thresh:   float = 0.15,
    ) -> list[dict]:

        for alert in sd_alerts:
            tids = alert.get("track_ids", [])
            if tids:
                for tid in tids:
                    if tid is not None:
                        self._active_sd[tid] = alert
            else:

                key = f"lgd_{alert.get('cx', 0)}_{alert.get('cy', 0)}"
                self._active_sd[key] = alert

        v_by_id = {
            t["track_id"]: t.get("v_norm_smooth", t.get("v_norm", 999))
            for t in kecepatan_track
        }

        to_remove = [
            tid for tid, alert in self._active_sd.items()
            if isinstance(tid, int)
            and (tid not in v_by_id or v_by_id[tid] >= v_slow_thresh)
        ]
        for tid in to_remove:
            del self._active_sd[tid]

        seen = set()
        result = []
        for alert in self._active_sd.values():
            aid = id(alert)
            if aid not in seen:
                seen.add(aid)
                result.append(alert)
        return result

    def write_frame(
        self,
        frame,
        jalur_terkonfirmasi,
        frame_idx:       int,
        timestamp:       float,
        ids_lambat=None,
        ids_bottleneck=None,
        n_ghost:         int  = 0,
        abnormal_alert:  dict | None = None,
        bd_alerts:       list | None = None,
        active_zones:    dict | None = None,
        sd_alerts:       list | None = None,
        kecepatan_track: list | None = None,
    ):
        if not self._ok:
            return

        annotated       = frame.copy()
        count           = len(jalur_terkonfirmasi)
        ids_lambat      = ids_lambat      or set()
        ids_bottleneck  = ids_bottleneck  or set()
        n_slow          = len(ids_lambat)
        n_bottle        = len(ids_bottleneck)
        bd_alerts       = bd_alerts       or []
        active_zones    = active_zones    or {}
        sd_alerts       = sd_alerts       or []
        kecepatan_track = kecepatan_track or []

        if self._hm is not None:
            self._hm.update(jalur_terkonfirmasi)
            if self.monitoring_mode:
                before = annotated.copy()
                self._hm.overlay(annotated)
                cv2.addWeighted(annotated, 0.75, before, 0.25, 0, annotated)
            else:
                self._hm.overlay(annotated)

        if kecepatan_track:
            _draw_trails(annotated, kecepatan_track, active_zones,
                         self._hm_rows, self._hm_cols)

        if self.show_zone_line and not self.monitoring_mode:
            _draw_background_zone_line(annotated, self.crowd_top_y)

        persistent_sd = self._update_active_sd(sd_alerts, kecepatan_track)

        if self.monitoring_mode:
            if bd_alerts or active_zones:
                _draw_bd_alerts_monitoring(annotated, bd_alerts, active_zones,
                                           self._hm_rows, self._hm_cols)
            if persistent_sd:
                _draw_sd_alerts_monitoring(annotated, persistent_sd)
            _draw_info_panel_monitoring(annotated, frame_idx, timestamp,
                                        count, n_slow, n_bottle)
            if abnormal_alert is not None:
                _draw_abnormal_banner(annotated, abnormal_alert)
            if self.show_legend:
                _draw_legend_monitoring(annotated)
        else:
            n_border = _draw_tracks(annotated, jalur_terkonfirmasi,
                                    ids_lambat, ids_bottleneck, self.crowd_top_y)
            if bd_alerts or active_zones:
                _draw_bd_alerts(annotated, bd_alerts, active_zones,
                                self._hm_rows, self._hm_cols)
            if persistent_sd:
                _draw_sd_alerts(annotated, persistent_sd)
            _draw_info_panel(annotated, frame_idx, timestamp,
                             count, n_slow, n_bottle, n_ghost, n_border, self.crowd_top_y)
            if abnormal_alert is not None:
                _draw_abnormal_banner(annotated, abnormal_alert)
            if self.show_legend:
                _draw_legend(annotated)

        self._writer.write(annotated)

    def release(self):
        if self._ok:
            self._writer.release()
            self._ok = False