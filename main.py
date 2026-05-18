import csv
import json
import time
from datetime import datetime

import cv2

from classifier          import (
    klasifikasi_keramaian,
    klasifikasi_pergerakan,
    klasifikasi_pergerakan_3level,
)
from detector            import Detektor
from heatmap             import HeatmapEngine
from bottleneck_detector import BottleneckDetector
from stationary_detector import StationaryDetector, LoiteringGridDetector
from metrics             import KalkulatorMetrik
from rolling_window      import RollingCrowdWindow
from tracker             import Tracker
from video_writer        import AnnotatedVideoWriter

VIDEO_PATH  = "videos/video1.mp4"
MODEL_PATH  = "best.pt"
VIDEO_NAME  = "video1"
LOCATION    = {
    "nama": "Titik A - Pelataran Masjid",
    "lat":  21.4225,
    "lon":  39.8262,
}

CONF_THRESH        = 0.40
IOU_THRESH         = 0.50
IMGSZ              = 1280
TAU                = 0.225     
BOTTLENECK_THRESH  = 0.05      
SB                 = 0.15     
X_COUNT            = 60
Y_COUNT            = 90
SH                 = 0.200     
WINDOW_S           = 10.0
INTERVAL_S         = 1.0
WARMUP_FRAMES      = 10
CROWD_TOP_Y        = 0         

# Kolom output CSV
FRAME_FIELDS = ["timestamp", "count", "n_terdefinisi", "n_lambat", "n_bottleneck", "sf", "sb"]

FRAME_TRACK_FIELDS = [
    "timestamp",
    "frame_idx",
    "track_id",
    "cx",
    "cy",
    "bbox_h",
    "v_norm",         
    "v_norm_smooth",  
    "is_lambat",
    "is_bottleneck",
    "arus",
]

WINDOW_FIELDS = [
    "window_k", "window_start", "window_end",
    "count_avg",
    "n_terdefinisi_total", "n_lambat_total", "n_bottleneck_total",
    "slow_ratio", "bottleneck_ratio",
    "label_crowd",
    "label_movement",       
    "label_movement_3",     
    "lat", "lon", "lokasi",
]

BD_ALERT_FIELDS = [
    "frame_idx", "alert_type",
    "grid_row", "grid_col",
    "density", "avg_vnorm", "baseline_vnorm",
    "n_slow", "slow_ratio",
    "cx_pixel", "cy_pixel",
    "duration_frames",
]

SD_ALERT_FIELDS = [
    "timestamp", "alert_type",
    "track_ids", "cx", "cy",
    "n_tracks", "dwell_s", "n_nearby",
    "cells", "frame_w",
]


def get_timestamp(cap, indeks_frame, fps, is_live, waktu_awal):
    if is_live:
        return time.time() - waktu_awal
    ms = cap.get(cv2.CAP_PROP_POS_MSEC)
    return float(ms) / 1000.0 if ms > 0 else indeks_frame / fps


def save_metadata(path, video_name, fps, location, thresholds):
    meta = {
        "video_name":    video_name,
        "run_timestamp": datetime.now().isoformat(),
        "fps_source":    fps,
        "location":      location,
        "thresholds":    thresholds,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"Metadata : {path}")


def _hitung_track_mentah(tracker_obj) -> int:
    try:
        tracks = tracker_obj.tracker.tracks
        return sum(1 for t in tracks if t.is_confirmed())
    except Exception:
        return 0


def jalankan_pipeline(
    video_path,
    model_path,
    video_name,
    location,
    output_dir         = "outputs",
    conf_thresh        = CONF_THRESH,
    iou_thresh         = IOU_THRESH,
    imgsz              = IMGSZ,
    tau                = TAU,
    bottleneck_thresh  = BOTTLENECK_THRESH,
    sb                 = SB,
    x_count            = X_COUNT,
    y_count            = Y_COUNT,
    sh                 = SH,
    window_s           = WINDOW_S,
    interval_s         = INTERVAL_S,
    warmup_frames      = WARMUP_FRAMES,
    crowd_top_y        = CROWD_TOP_Y,
    save_video         = True,
    video_out_path     = None,
    on_log             = None,
    on_progress        = None,
    on_window          = None,
    stop_flag          = None,
):
    import os
    os.makedirs(output_dir, exist_ok=True)

    def _log(msg):
        print(msg)
        if on_log:
            on_log(msg)

    is_live = isinstance(video_path, int)
    _log(f"▶ Membuka video: {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Tidak bisa membuka video: {video_path}")

    fps          = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_est = total_frames / fps if fps > 0 else 0
    vid_w        = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h        = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    _log(
        f"   FPS: {fps:.1f} │ Frame: {total_frames} │ "
        f"Durasi: {duration_est:.1f}s │ Resolusi: {vid_w}x{vid_h}"
    )
    _log(
        f"   Conf: {conf_thresh} │ IoU: {iou_thresh} │ imgsz: {imgsz} │ "
        f"TAU: {tau} │ BN_THRESH: {bottleneck_thresh} │ crowd_top_y: {crowd_top_y}px"
    )

    detektor   = Detektor(
        model_path,
        conf         = conf_thresh,
        iou          = iou_thresh,
        imgsz        = imgsz,
        zona_latar_y = crowd_top_y,
    )

    tracker    = Tracker(
        crowd_top_y  = crowd_top_y,
        frame_width  = vid_w,
        frame_height = vid_h,
    )

    calculator = KalkulatorMetrik(
        tau               = tau,
        bottleneck_thresh = bottleneck_thresh,
    )

    win = RollingCrowdWindow(
        window_s=window_s,
        output_interval_s=interval_s,
    )

    hm_engine = HeatmapEngine(
        frame_width  = vid_w,
        frame_height = vid_h,
        crowd_top_y  = crowd_top_y,
    )

    bd = BottleneckDetector(
        frame_width  = vid_w,
        frame_height = vid_h,
        crowd_top_y  = crowd_top_y,
    )

    sd  = StationaryDetector()
    lgd = LoiteringGridDetector(frame_w=vid_w, frame_h=vid_h)

    vwriter_detail  = None
    vwriter_monitor = None
    out_video_detail  = None
    out_video_monitor = None

    SAVE_DETAIL  = True
    SAVE_MONITOR = True

    if save_video:
        _out_detail = (
            video_out_path
            if video_out_path is not None
            else os.path.join(output_dir, f"annotated_{video_name}.mp4")
        )

        if not SAVE_DETAIL:
            _log("Video detail di-skip (SAVE_DETAIL=False) — aktifkan untuk render bbox+ID")

        if SAVE_DETAIL:
            vwriter_detail = AnnotatedVideoWriter(
                _out_detail, fps, vid_w, vid_h,
                crowd_top_y     = crowd_top_y,
                show_heatmap    = True,
                show_legend     = True,
                monitoring_mode = False,
                heatmap_engine  = hm_engine,
            )
            if vwriter_detail.is_open:
                out_video_detail = vwriter_detail.out_path
                _log(f"Video output (detail)     : {out_video_detail}")
            else:
                _log("VideoWriter detail gagal dibuka.")
                vwriter_detail = None

        if not SAVE_MONITOR:
            _log("Video monitoring di-skip (SAVE_MONITOR=False)")

        if SAVE_MONITOR:
            _out_monitor = os.path.join(output_dir, f"monitoring_{video_name}.mp4")

            from heatmap import HeatmapEngine as _HM
            hm_engine_mon = _HM(
                frame_width  = vid_w,
                frame_height = vid_h,
                crowd_top_y  = crowd_top_y,
            )

            vwriter_monitor = AnnotatedVideoWriter(
                _out_monitor, fps, vid_w, vid_h,
                crowd_top_y     = crowd_top_y,
                show_heatmap    = True,
                show_legend     = True,
                monitoring_mode = True,
                heatmap_engine  = hm_engine_mon,
            )

            if vwriter_monitor.is_open:
                out_video_monitor = vwriter_monitor.out_path
                _log(f"Video output (monitoring) : {out_video_monitor}")
            else:
                _log("VideoWriter monitoring gagal dibuka.")
                vwriter_monitor = None

    _log("✓ Model YOLOv8 + DeepSORT + HeatmapEngine siap")
    if warmup_frames > 0:
        _log(f"⏳ Warmup {warmup_frames} frame pertama...")
    _log("Pipeline dimulai...")

    waktu_awal          = time.time()
    indeks_frame        = 0
    jumlah_diproses     = 0
    baris_frame         = []
    frame_track_rows    = []
    baris_window        = []
    baris_bd_alerts     = []
    baris_sd_alerts     = []
    dihentikan_pengguna = False

    while cap.isOpened():
        if stop_flag and stop_flag():
            _log("⛔ Pipeline dihentikan oleh pengguna.")
            dihentikan_pengguna = True
            break

        ret, frame = cap.read()
        if not ret:
            break

        ts = get_timestamp(cap, indeks_frame, fps, is_live, waktu_awal)

        if indeks_frame < warmup_frames:
            hasil_deteksi = detektor.deteksi(frame)
            tracker.perbarui(hasil_deteksi, frame)
            indeks_frame += 1
            if on_progress and total_frames > 0:
                on_progress(min(int(indeks_frame / total_frames * 100), 5))
            continue

        hasil_deteksi = detektor.deteksi(frame)

        raw_confirmed_before  = _hitung_track_mentah(tracker)
        jalur_terkonfirmasi   = tracker.perbarui(hasil_deteksi, frame)
        n_ghost = max(0, raw_confirmed_before - len(jalur_terkonfirmasi))

        (count, n_def, n_slow, n_bottle,
         sf, sb_val,
         ids_lambat, ids_bottleneck,
         kecepatan_track) = calculator.perbarui(jalur_terkonfirmasi, ts)

        bd_alerts, active_zones = bd.update(kecepatan_track)

        for alert in bd_alerts:
            baris_bd_alerts.append(alert)
            label = alert["alert_type"].replace("_", " ")
            icons = {"BOTTLENECK": "🔴"}
            if on_log:
                on_log(
                    f"{icons.get(alert['alert_type'], '⚠')} {label}  "
                    f"Zone({alert['grid_row']},{alert['grid_col']})  "
                    f"Density={alert['density']}  "
                    f"SlowRatio={alert['slow_ratio']:.0%}"
                )

        sd_alerts  = sd.update(jalur_terkonfirmasi, kecepatan_track, ts)
        lgd_alerts = lgd.update(kecepatan_track, ts)
        sd_alerts  = sd_alerts + lgd_alerts

        for alert in sd_alerts:
            alert_csv = dict(alert)
            alert_csv["track_ids"] = str(alert["track_ids"])
            alert_csv["cells"]   = str(alert.get("cells", ""))
            alert_csv["frame_w"] = str(alert.get("frame_w", ""))
            baris_sd_alerts.append(alert_csv)
            icons_sd = {
                "STATIONARY_IN_CROWD":   "🔴",
                "STATIONARY_GROUP":      "🟠",
                "LOITERING_GROUP":       "🟠",
            }
            label_sd = alert["alert_type"].replace("_", " ")
            if on_log:
                on_log(
                    f"{icons_sd.get(alert['alert_type'], '⚠')} {label_sd}  "
                    f"IDs={alert['track_ids']}  "
                    f"Diam={alert['dwell_s']:.1f}s  "
                    f"Sekitar={alert['n_nearby']} orang"
                )

        if vwriter_detail is None and vwriter_monitor is None:
            hm_engine.update(jalur_terkonfirmasi)

        abnormal_alert = bd_alerts[0] if bd_alerts else None

        if jumlah_diproses % 30 == 0:
            _log(
                f"[Frame {indeks_frame}] raw_det={len(hasil_deteksi)} │ "
                f"confirmed={count} │ slow={n_slow} │ bottle={n_bottle} │ "
                f"ghost={n_ghost} │ ts={ts:.1f}s"
            )

        baris_frame.append({
            "timestamp":     round(ts, 4),
            "count":         count,
            "n_terdefinisi": n_def,
            "n_lambat":      n_slow,
            "n_bottleneck":  n_bottle,
            "sf":            round(sf, 4),
            "sb":            round(sb_val, 4),
        })

        for spd in kecepatan_track:
            frame_track_rows.append({
                "timestamp":      round(ts, 4),
                "frame_idx":      indeks_frame,
                "track_id":       spd["track_id"],
                "cx":             spd["cx"],
                "cy":             spd["cy"],
                "bbox_h":         spd["bbox_h"],
                "v_norm":         spd["v_norm"],
                "v_norm_smooth":  spd.get("v_norm_smooth", spd["v_norm"]),  
                "is_lambat":      spd["is_lambat"],
                "is_bottleneck":  spd["is_bottleneck"],
                "arus":           spd["arus"],
            })

        win.push(ts, count, n_def, n_slow, n_bottle)
        while win.should_output(ts):
            feats = win.get_features(ts)
            if feats is None:
                break

            label_crowd      = klasifikasi_keramaian(
                feats["count_avg"], feats["slow_ratio"],
                X=x_count, Y=y_count, SH=sh,
            )
            label_movement   = klasifikasi_pergerakan(
                feats["slow_ratio"], feats["count_avg"], x_count, SH=sh
            )
            label_movement_3 = klasifikasi_pergerakan_3level(
                feats["bottleneck_ratio"], feats["slow_ratio"],
                feats["count_avg"], x_count, SH=sh, SB=sb,
            )

            row = {
                "window_k":              feats["window_k"],
                "window_start":          feats["window_start"],
                "window_end":            feats["window_end"],
                "count_avg":             feats["count_avg"],
                "n_terdefinisi_total":   feats["n_terdefinisi_total"],
                "n_lambat_total":        feats["n_lambat_total"],
                "n_bottleneck_total":    feats["n_bottleneck_total"],
                "slow_ratio":            feats["slow_ratio"],
                "bottleneck_ratio":      feats["bottleneck_ratio"],
                "label_crowd":           label_crowd,
                "label_movement":        label_movement,
                "label_movement_3":      label_movement_3,
                "lat":                   location["lat"],
                "lon":                   location["lon"],
                "lokasi":                location["nama"],
            }
            baris_window.append(row)
            if on_window:
                on_window(row)

            _log(
                f"[W{feats['window_k']:03d}] "
                f"{feats['window_start']:.1f}-{feats['window_end']:.1f}s │ "
                f"count={feats['count_avg']:.1f} │ "
                f"slow={feats['slow_ratio']:.3f} │ "
                f"bottle={feats['bottleneck_ratio']:.3f} │ "
                f"{label_crowd} / {label_movement_3}"
            )

        _write_kwargs_detail = dict(
            jalur_terkonfirmasi = jalur_terkonfirmasi,
            frame_idx           = indeks_frame,
            timestamp           = ts,
            ids_lambat          = ids_lambat,
            ids_bottleneck      = ids_bottleneck,
            n_ghost             = n_ghost,
            abnormal_alert      = abnormal_alert,
            bd_alerts           = bd_alerts,
            active_zones        = active_zones,
            sd_alerts           = sd_alerts,
            kecepatan_track     = kecepatan_track,  \
        )

        _write_kwargs_monitor = dict(
            jalur_terkonfirmasi = jalur_terkonfirmasi,
            frame_idx           = indeks_frame,
            timestamp           = ts,
            ids_lambat          = ids_lambat,
            ids_bottleneck      = ids_bottleneck,
            n_ghost             = n_ghost,
            abnormal_alert      = abnormal_alert,
            bd_alerts           = bd_alerts,
            active_zones        = active_zones,
            sd_alerts           = sd_alerts,
            kecepatan_track     = kecepatan_track,  
        )

        if vwriter_detail is not None:
            vwriter_detail.write_frame(frame, **_write_kwargs_detail)
        if vwriter_monitor is not None:
            vwriter_monitor.write_frame(frame, **_write_kwargs_monitor)

        indeks_frame    += 1
        jumlah_diproses += 1

        if on_progress and total_frames > 0:
            on_progress(min(int(indeks_frame / total_frames * 100), 99))

    cap.release()

    if vwriter_detail is not None:
        vwriter_detail.release()
        _log(f"✅ Video detail tersimpan    : {out_video_detail}")
    if vwriter_monitor is not None:
        vwriter_monitor.release()
        _log(f"✅ Video monitoring tersimpan: {out_video_monitor}")

    _log(
        f"\n✓ Selesai — {jumlah_diproses} frame diproses "
        f"(+{warmup_frames} warmup, total {indeks_frame})"
    )

    out_frame       = os.path.join(output_dir, f"frame_{video_name}.csv")
    out_frame_track = os.path.join(output_dir, f"frame_track_{video_name}.csv")
    out_window      = os.path.join(output_dir, f"window_{video_name}.csv")
    out_meta        = os.path.join(output_dir, f"meta_{video_name}.json")

    if baris_frame:
        with open(out_frame, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FRAME_FIELDS)
            writer.writeheader()
            writer.writerows(baris_frame)
        _log(f"💾 Frame CSV          → {out_frame}")

    if frame_track_rows:
        with open(out_frame_track, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FRAME_TRACK_FIELDS)
            writer.writeheader()
            writer.writerows(frame_track_rows)
        _log(f"💾 Frame Track CSV    → {out_frame_track}  ({len(frame_track_rows):,} baris)")
    else:
        _log("⚠  frame_track CSV kosong — tidak ada track dengan v_norm terdefinisi.")

    if baris_window:
        with open(out_window, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=WINDOW_FIELDS)
            writer.writeheader()
            writer.writerows(baris_window)
        _log(f"💾 Window CSV         → {out_window}")

    out_bd_alerts = os.path.join(output_dir, f"bd_alerts_{video_name}.csv")
    if baris_bd_alerts:
        with open(out_bd_alerts, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=BD_ALERT_FIELDS)
            writer.writeheader()
            writer.writerows(baris_bd_alerts)
        _log(f"💾 BD Alerts CSV      → {out_bd_alerts}  ({len(baris_bd_alerts)} event)")
    else:
        _log("ℹ  Tidak ada event bottleneck/sudden-stop/suspicious-crowd terdeteksi.")
        out_bd_alerts = None

    out_sd_alerts = os.path.join(output_dir, f"sd_alerts_{video_name}.csv")
    if baris_sd_alerts:
        with open(out_sd_alerts, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SD_ALERT_FIELDS)
            writer.writeheader()
            writer.writerows(baris_sd_alerts)
        _log(
            f"💾 SD Alerts CSV      → {out_sd_alerts}  ({len(baris_sd_alerts)} event: "
            f"{sum(1 for a in baris_sd_alerts if 'IN_CROWD' in a['alert_type'])} in-crowd, "
            f"{sum(1 for a in baris_sd_alerts if 'GROUP' in a['alert_type'])} group)"
        )
    else:
        _log("ℹ  Tidak ada event stationary terdeteksi.")
        out_sd_alerts = None

    thresholds = {
        "CONF_THRESH":       conf_thresh,
        "IOU_THRESH":        iou_thresh,
        "IMGSZ":             imgsz,
        "TAU":               tau,
        "BOTTLENECK_THRESH": bottleneck_thresh,
        "SB":                sb,
        "X_COUNT":           x_count,
        "Y_COUNT":           y_count,
        "SH":                sh,
        "WINDOW_S":          window_s,
        "INTERVAL_S":        interval_s,
        "WARMUP_FRAMES":     warmup_frames,
    }

    save_metadata(
        path       = out_meta,
        video_name = video_name,
        fps        = fps,
        location   = location,
        thresholds = thresholds,
    )

    if on_progress:
        on_progress(100)

    return {
        "out_frame":           out_frame,
        "out_frame_track":     out_frame_track,
        "out_window":          out_window,
        "out_bd_alerts":       out_bd_alerts,
        "out_sd_alerts":       out_sd_alerts,
        "out_meta":            out_meta,
        "out_video":           out_video_detail,
        "out_video_monitor":   out_video_monitor,
        "window_rows":         baris_window,
        "bd_alert_count":      len(baris_bd_alerts),
        "sd_alert_count":      len(baris_sd_alerts),
        "frame_count":         jumlah_diproses,
        "dihentikan_pengguna": dihentikan_pengguna,
    }


def main():
    jalankan_pipeline(
        video_path        = VIDEO_PATH,
        model_path        = MODEL_PATH,
        video_name        = VIDEO_NAME,
        location          = LOCATION,
        output_dir        = "outputs",
        conf_thresh       = CONF_THRESH,
        iou_thresh        = IOU_THRESH,
        imgsz             = IMGSZ,
        tau               = TAU,
        bottleneck_thresh = BOTTLENECK_THRESH,
        sb                = SB,
        x_count           = X_COUNT,
        y_count           = Y_COUNT,
        sh                = SH,
        window_s          = WINDOW_S,
        interval_s        = INTERVAL_S,
        warmup_frames     = WARMUP_FRAMES,
        crowd_top_y       = CROWD_TOP_Y,
        save_video        = True,
    )


if __name__ == "__main__":
    main()