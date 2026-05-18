import os
import sys
import traceback
from PyQt6.QtCore import QThread, pyqtSignal


class PipelineWorker(QThread):
    log_message       = pyqtSignal(str)
    progress          = pyqtSignal(int)
    window_result     = pyqtSignal(dict)
    pipeline_finished = pyqtSignal(dict)
    error             = pyqtSignal(str)

    def __init__(self, params: dict, parent=None):
        super().__init__(parent)
        self.params = params
        self._stop_requested = False

    def minta_berhenti(self):
        self._stop_requested = True

    def run(self):
        try:
            self._panggil_inti()
        except Exception as e:
            self.error.emit(f"{e}\n\n{traceback.format_exc()}")

    def _panggil_inti(self):
        p    = self.params
        root = p["project_root"]
        if root not in sys.path:
            sys.path.insert(0, root)

        from main import jalankan_pipeline

        result = jalankan_pipeline(
            video_path        = p["video_path"],
            model_path        = p["model_path"],
            video_name        = p["video_name"],
            location          = {"nama": p["location_name"],
                                 "lat":  p["lat"],
                                 "lon":  p["lon"]},
            output_dir        = p["output_dir"],
            conf_thresh       = p["CONF_THRESH"],
            iou_thresh        = p["IOU_THRESH"],
            imgsz             = p["IMGSZ"],
            warmup_frames     = p["WARMUP_FRAMES"],
            tau               = p["TAU"],
            bottleneck_thresh = p.get("BOTTLENECK_THRESH", 0.05),  
            sb                = p.get("SB", 0.15),                  
            x_count           = p["X_COUNT"],
            y_count           = p["Y_COUNT"],
            sh                = p["SH"],
            window_s          = p["WINDOW_S"],
            interval_s        = p["INTERVAL_S"],
            crowd_top_y       = p.get("CROWD_TOP_Y", 0),
            on_log            = self.log_message.emit,
            on_progress       = self.progress.emit,
            on_window         = self.window_result.emit,
            stop_flag         = lambda: self._stop_requested,
        )
        self.pipeline_finished.emit(result)