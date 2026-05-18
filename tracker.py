from deep_sort_realtime.deepsort_tracker import DeepSort


class Tracker:
    def __init__(
        self,
        max_age             = 20,
        n_init              = 3,
        max_iou_distance    = 0.60,
        max_cosine_distance = 0.65,
        nn_budget           = 150,
        crowd_top_y         = 270,
        frame_width         = 1280,
        frame_height        = 720,
    ):
        self.tracker = DeepSort(
            max_age             = max_age,
            n_init              = n_init,
            max_iou_distance    = max_iou_distance,
            max_cosine_distance = max_cosine_distance,
            nn_budget           = nn_budget,
        )
        self._last_det_bboxes: list = []
        self.crowd_top_y   = crowd_top_y
        self.frame_width   = frame_width
        self.frame_height  = frame_height

    def perbarui(self, hasil_deteksi, frame):
        if frame is not None:
            self.frame_height, self.frame_width = frame.shape[:2]

        self._last_det_bboxes = [d[0] for d in hasil_deteksi]
        tracks_mentah = self.tracker.update_tracks(hasil_deteksi, frame=frame)
        tracks_confirmed = []
        for t in tracks_mentah:
            if not t.is_confirmed():
                continue

            bbox_yolo = self._get_yolo_bbox(t)
            if bbox_yolo is not None:
                x1, y1, w, h = bbox_yolo
                x2 = x1 + w
                y2 = y1 + h
            else:
                try:
                    x1, y1, x2, y2 = t.to_ltrb()
                except Exception:
                    continue
                w = float(x2 - x1)
                h = float(y2 - y1)

            if w <= 0 or h <= 0:
                continue
            x1 = max(0.0, float(x1))
            y1 = max(0.0, float(y1))
            x2 = min(float(self.frame_width),  float(x2))
            y2 = min(float(self.frame_height), float(y2))
            w  = x2 - x1
            h  = y2 - y1

            if w <= 0 or h <= 0:
                continue

            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0
            if cy < self.crowd_top_y:
                continue

            tracks_confirmed.append({
                "id": t.track_id,
                "cx": cx,
                "cy": cy,
                "h" : float(h),
                "w" : float(w),
            })

        return tracks_confirmed

    def _get_yolo_bbox(self, track):
        try:
            ldet = track.last_detection
            if ldet is not None:
                for attr in ('ltwh', 'tlwh'):
                    if hasattr(ldet, attr):
                        val = getattr(ldet, attr)
                        if val is not None:
                            x1, y1, w, h = (float(val[0]), float(val[1]),
                                            float(val[2]), float(val[3]))
                            if w > 0 and h > 0:
                                return [x1, y1, w, h]
                if hasattr(ldet, 'to_tlwh'):
                    tlwh = ldet.to_tlwh()
                    if tlwh is not None:
                        x1, y1, w, h = (float(tlwh[0]), float(tlwh[1]),
                                        float(tlwh[2]), float(tlwh[3]))
                        if w > 0 and h > 0:
                            return [x1, y1, w, h]
        except (AttributeError, TypeError, IndexError):
            pass
        try:
            idx_deteksi = None
            for attr in ('det_id', '_det_id', 'origin_id', '_origin_id'):
                if hasattr(track, attr):
                    val = getattr(track, attr)
                    if val is not None and isinstance(val, int):
                        idx_deteksi = val
                        break
            if idx_deteksi is not None and 0 <= idx_deteksi < len(self._last_det_bboxes):
                bbox = self._last_det_bboxes[idx_deteksi]
                x1, y1, w, h = (float(bbox[0]), float(bbox[1]),
                                float(bbox[2]), float(bbox[3]))
                if w > 0 and h > 0:
                    return [x1, y1, w, h]
        except (AttributeError, TypeError, IndexError):
            pass

        return None