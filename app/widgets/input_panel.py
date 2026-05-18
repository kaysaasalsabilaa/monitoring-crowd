import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QDoubleSpinBox, QSpinBox,
    QFileDialog, QScrollArea, QFrame, QSizePolicy,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from app.widgets.map_picker import MapPickerDialog


def _step_header(num: str, title: str, done: bool = False) -> QWidget:
    w   = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(9)
    badge = QLabel("✓" if done else num)
    badge.setObjectName("step_badge_done" if done else "step_badge")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(22, 22)
    lbl = QLabel(title)
    lbl.setObjectName("step_title")
    lay.addWidget(badge)
    lay.addWidget(lbl)
    lay.addStretch()
    return w


def _label_sidebar(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sidebar_label")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setObjectName("step_divider")
    line.setFrameShape(QFrame.Shape.HLine)
    return line


class AdvancedSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        self._collapsed = True
        self._toggle_btn = QPushButton("⚙   Pengaturan Lanjutan  ▾")
        self._toggle_btn.setObjectName("adv_toggle")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self._toggle_btn)

        self._content = QWidget()
        self._content.setObjectName("adv_content")
        self._content.setVisible(False)
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(14, 14, 14, 14)
        cl.setSpacing(12)

        hint_lbl = QLabel(
            "Parameter ini digunakan oleh algoritma deteksi & klasifikasi.\n"
            "Untuk penggunaan normal, nilai default sudah optimal."
        )
        hint_lbl.setStyleSheet(
            "color: #3A6070; font-size: 10px; "
            "background: rgba(42,79,101,0.3); border-radius: 6px; "
            "padding: 8px 10px; line-height: 1.5;"
        )
        hint_lbl.setWordWrap(True)
        cl.addWidget(hint_lbl)

        def _param(label: str, hint: str, widget: QWidget) -> QWidget:
            row = QWidget()
            rl  = QVBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(3)
            top = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setObjectName("adv_param_label")
            top.addWidget(lbl)
            top.addStretch()
            top.addWidget(widget)
            rl.addLayout(top)
            hint_lbl = QLabel(hint)
            hint_lbl.setObjectName("adv_param_hint")
            hint_lbl.setWordWrap(True)
            rl.addWidget(hint_lbl)
            return row

        def _dspin(val, lo, hi, step, dec, suffix=""):
            s = QDoubleSpinBox()
            s.setRange(lo, hi)
            s.setSingleStep(step)
            s.setDecimals(dec)
            s.setValue(val)
            if suffix:
                s.setSuffix(suffix)
            s.setFixedWidth(100)
            return s

        def _ispin(val, lo, hi):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setFixedWidth(100)
            return s

        # deteksi
        self.conf_spin   = _dspin(0.40, 0.01, 1.0, 0.05, 2)
        self.iou_spin    = _dspin(0.50, 0.01, 1.0, 0.05, 2)
        self.imgsz_combo = QComboBox()
        self.imgsz_combo.addItems(["640", "960", "1280"])
        self.imgsz_combo.setCurrentText("1280")
        self.imgsz_combo.setFixedWidth(100)
        self.imgsz_combo.setStyleSheet(
            "background-color: #1E3A4E; color: #E8EFF4; "
            "border: 1.5px solid #2A4F65; border-radius: 8px; padding: 4px 8px;"
        )
        self.warmup_spin = _ispin(10, 0, 120)

        self.tau_spin      = _dspin(0.2249, 0.001, 5.0, 0.01, 3)
        self.x_spin        = _ispin(60,  1, 9999)
        self.y_spin        = _ispin(90, 1, 9999)
        self.sh_spin       = _dspin(0.200, 0.0, 1.0,  0.05, 2)
        self.window_spin   = _dspin(10.0, 1.0, 300.0, 1.0, 1, " s")
        self.interval_spin = _dspin(1.0,  0.1,  60.0, 0.5, 1, " s")

        sec_det = QLabel("── DETEKSI ──")
        sec_det.setStyleSheet(
            "color:#5A8090;font-size:9px;font-weight:700;letter-spacing:1.5px;")
        cl.addWidget(sec_det)

        cl.addWidget(_param(
            "CONF_THRESH",
            "Confidence minimum deteksi YOLO (0.45 disarankan untuk crowd)",
            self.conf_spin
        ))
        cl.addWidget(_param(
            "IOU_THRESH",
            "IoU NMS — 0.50 optimal: suppress double-box tanpa buang orang berdekatan",
            self.iou_spin
        ))
        cl.addWidget(_param(
            "IMGSZ",
            "Resolusi inferensi — 1280 lebih akurat, 640 lebih cepat di CPU",
            self.imgsz_combo
        ))
        cl.addWidget(_param(
            "WARMUP_FRAMES",
            "Frame awal yang di-skip agar tracker stabil sebelum pencatatan",
            self.warmup_spin
        ))

        sec_met = QLabel("── METRIK & KLASIFIKASI ──")
        sec_met.setStyleSheet(
            "color:#5A8090;font-size:9px;font-weight:700;"
            "letter-spacing:1.5px;margin-top:6px;")
        cl.addWidget(sec_met)

        self.bottleneck_spin = _dspin(0.05, 0.001, 1.0, 0.01, 3)
        self.sb_spin         = _dspin(0.15, 0.0,   1.0, 0.05, 2)

        cl.addWidget(_param(
            "TAU (τ)",
            "Batas Lancar/Lambat — v_norm ≥ TAU → LANCAR (default 0.225 dari Q1 data)",
            self.tau_spin,
        ))
        cl.addWidget(_param(
            "BOTTLENECK_THRESH",
            "Batas Lambat/Bottleneck — v_norm < nilai ini → nyaris diam (default 0.05)",
            self.bottleneck_spin,
        ))
        cl.addWidget(_param(
            "SB",
            "Ambang rasio bottleneck per window untuk label BOTTLENECK (default 0.30)",
            self.sb_spin,
        ))
        cl.addWidget(_param("X_COUNT",    "Batas bawah jumlah → keramaian sedang", self.x_spin))
        cl.addWidget(_param("Y_COUNT",    "Batas bawah jumlah → keramaian tinggi", self.y_spin))
        cl.addWidget(_param("SH",         "Ambang proporsi lambat",                self.sh_spin))
        cl.addWidget(_param("WINDOW_S",   "Durasi rolling window temporal",        self.window_spin))
        cl.addWidget(_param("INTERVAL_S", "Interval output per window",            self.interval_spin))

        layout.addWidget(self._content)

    def _toggle(self):
        self._collapsed = not self._collapsed
        self._content.setVisible(not self._collapsed)
        arrow = "▴" if not self._collapsed else "▾"
        self._toggle_btn.setText(f"⚙   Pengaturan Lanjutan  {arrow}")

    def ambil_params(self) -> dict:
        return {
            "CONF_THRESH":       self.conf_spin.value(),
            "IOU_THRESH":        self.iou_spin.value(),
            "IMGSZ":             int(self.imgsz_combo.currentText()),
            "WARMUP_FRAMES":     self.warmup_spin.value(),
            "TAU":               self.tau_spin.value(),
            "BOTTLENECK_THRESH": self.bottleneck_spin.value(),
            "SB":                self.sb_spin.value(),
            "X_COUNT":           self.x_spin.value(),
            "Y_COUNT":           self.y_spin.value(),
            "SH":                self.sh_spin.value(),
            "WINDOW_S":          self.window_spin.value(),
            "INTERVAL_S":        self.interval_spin.value(),
        }


class InputPanel(QWidget):
    """
    Sinyal:
        run_requested(dict)  — emit saat Run diklik
        stop_requested()     — emit saat Stop diklik
    """
    run_requested  = pyqtSignal(dict)
    stop_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._video_path = ""
        self._lat = 21.4225
        self._lon = 39.8262
        self._bangun_ui()

    def _bangun_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        brand  = QWidget()
        brand.setObjectName("sidebar_brand")
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(18, 16, 18, 16)
        bl.setSpacing(12)
        icon_lbl = QLabel("🕋")
        icon_lbl.setStyleSheet("font-size: 28px;")
        icon_lbl.setFixedSize(36, 36)
        bl.addWidget(icon_lbl)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_col.setContentsMargins(0, 0, 0, 0)
        t = QLabel("HAJJ CROWD MONITOR")
        t.setObjectName("brand_title")
        s = QLabel("YOLOv8 · DeepSORT · UNAIR 2026")
        s.setObjectName("brand_sub")
        title_col.addWidget(t)
        title_col.addWidget(s)
        bl.addLayout(title_col, 1)
        ver = QLabel("v6")
        ver.setObjectName("brand_version_badge")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bl.addWidget(ver, alignment=Qt.AlignmentFlag.AlignTop)
        outer.addWidget(brand)

        # scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(0)
        form  = QWidget()
        fl    = QVBoxLayout(form)
        fl.setContentsMargins(16, 18, 16, 16)
        fl.setSpacing(14)

        # langkah 1 - video
        fl.addWidget(_step_header("1", "PILIH VIDEO"))
        browse_row = QHBoxLayout()
        browse_row.setSpacing(8)
        self._video_display = QLineEdit()
        self._video_display.setPlaceholderText("Belum ada video dipilih...")
        self._video_display.setReadOnly(True)
        browse_btn = QPushButton("📂  Browse")
        browse_btn.setObjectName("btn_browse")
        browse_btn.setFixedWidth(90)
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._pilih_video)
        browse_row.addWidget(self._video_display)
        browse_row.addWidget(browse_btn)
        fl.addLayout(browse_row)

        self._video_card = QWidget()
        self._video_card.setObjectName("video_preview_card")
        self._video_card.setVisible(False)
        vc_lay = QHBoxLayout(self._video_card)
        vc_lay.setContentsMargins(12, 10, 12, 10)
        vc_lay.setSpacing(10)
        vid_icon = QLabel("🎬")
        vid_icon.setStyleSheet("font-size: 22px;")
        vc_text = QVBoxLayout()
        vc_text.setSpacing(2)
        self._vid_name_lbl = QLabel("")
        self._vid_name_lbl.setObjectName("video_preview_name")
        self._vid_meta_lbl = QLabel("")
        self._vid_meta_lbl.setObjectName("video_preview_meta")
        vc_text.addWidget(self._vid_name_lbl)
        vc_text.addWidget(self._vid_meta_lbl)
        vc_lay.addWidget(vid_icon)
        vc_lay.addLayout(vc_text, 1)
        fl.addWidget(self._video_card)
        fl.addWidget(_divider())

        # langkah 2 - lokasi
        fl.addWidget(_step_header("2", "LOKASI PENGAMATAN"))
        fl.addWidget(_label_sidebar("Nama / Deskripsi Lokasi"))
        self._loc_name = QLineEdit()
        self._loc_name.setPlaceholderText("Contoh: Pelataran Masjidil Haram")
        self._loc_name.textChanged.connect(self._update_loc_preview)
        fl.addWidget(self._loc_name)

        map_btn = QPushButton("🗺️   Pilih Lokasi dari Peta")
        map_btn.setObjectName("btn_map")
        map_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        map_btn.setMinimumHeight(36)
        map_btn.clicked.connect(self._buka_pemilih_peta)
        fl.addWidget(map_btn)

        coord_row = QHBoxLayout()
        coord_row.setSpacing(8)
        lat_col = QVBoxLayout()
        lat_col.setSpacing(4)
        lat_col.addWidget(_label_sidebar("Latitude"))
        self._lat_spin = QDoubleSpinBox()
        self._lat_spin.setRange(-90.0, 90.0)
        self._lat_spin.setDecimals(6)
        self._lat_spin.setValue(self._lat)
        self._lat_spin.setSuffix("°")
        self._lat_spin.valueChanged.connect(self._on_coords_changed)
        lat_col.addWidget(self._lat_spin)
        lon_col = QVBoxLayout()
        lon_col.setSpacing(4)
        lon_col.addWidget(_label_sidebar("Longitude"))
        self._lon_spin = QDoubleSpinBox()
        self._lon_spin.setRange(-180.0, 180.0)
        self._lon_spin.setDecimals(6)
        self._lon_spin.setValue(self._lon)
        self._lon_spin.setSuffix("°")
        self._lon_spin.valueChanged.connect(self._on_coords_changed)
        lon_col.addWidget(self._lon_spin)
        coord_row.addLayout(lat_col)
        coord_row.addLayout(lon_col)
        fl.addLayout(coord_row)

        self._loc_card = QWidget()
        self._loc_card.setObjectName("loc_preview_card")
        lc_lay = QHBoxLayout(self._loc_card)
        lc_lay.setContentsMargins(12, 10, 12, 10)
        lc_lay.setSpacing(10)
        pin_icon = QLabel("📍")
        pin_icon.setObjectName("loc_preview_icon")
        lc_text = QVBoxLayout()
        lc_text.setSpacing(2)
        self._loc_name_preview   = QLabel("Makkah al-Mukarramah")
        self._loc_name_preview.setObjectName("loc_preview_name")
        self._loc_coords_preview = QLabel(f"{self._lat:.6f}, {self._lon:.6f}")
        self._loc_coords_preview.setObjectName("loc_preview_coords")
        lc_text.addWidget(self._loc_name_preview)
        lc_text.addWidget(self._loc_coords_preview)
        lc_lay.addWidget(pin_icon)
        lc_lay.addLayout(lc_text, 1)
        fl.addWidget(self._loc_card)
        fl.addWidget(_divider())

        # langkah 3 - pengaturan 
        self._adv = AdvancedSettings()
        fl.addWidget(self._adv)
        fl.addStretch(1)

        scroll.setWidget(form)
        outer.addWidget(scroll, 1)

        action_area = QWidget()
        action_area.setStyleSheet(
            "background-color: #0F1F2E; border-top: 1px solid #1E3A4E;")
        al = QVBoxLayout(action_area)
        al.setContentsMargins(16, 14, 16, 18)
        al.setSpacing(8)

        self._val_hint = QLabel("")
        self._val_hint.setStyleSheet(
            "color: #E07878; font-size: 11px; "
            "background: rgba(217,64,64,0.1); border-radius: 6px; "
            "padding: 6px 10px;"
        )
        self._val_hint.setWordWrap(True)
        self._val_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val_hint.setVisible(False)
        al.addWidget(self._val_hint)

        self._run_btn = QPushButton("▶   Mulai Analisis")
        self._run_btn.setObjectName("btn_run")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setMinimumHeight(38)
        self._run_btn.clicked.connect(self._on_jalankan)
        self._run_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #D9B65C, stop:1 #B89030);
                color: #0F1F2E;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: 800;
                padding: 8px 0;
            }
            QPushButton:hover { background-color: #EAC464; }
            QPushButton:disabled { background: #243F54; color: #3A6070; }
        """)

        self._stop_btn = QPushButton("■   Hentikan Analisis")
        self._stop_btn.setObjectName("btn_stop")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stop_btn.setMinimumHeight(32)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._stop_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(217, 64, 64, 0.15);
                color: #FF9090;
                border: 2px solid #FF6060;
                border-radius: 10px;
                font-size: 12px;
                font-weight: 800;
                padding: 6px 0;
            }
            QPushButton:hover { background-color: #D94040; color: #FFFFFF; }
            QPushButton:disabled { color: #4A7A90; border-color: #3A6070; background-color: transparent; }
        """)

        al.addWidget(self._run_btn)
        al.addWidget(self._stop_btn)
        outer.addWidget(action_area)

        self._update_loc_preview()

    def _pilih_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Pilih File Video", "",
            "Video (*.mp4 *.avi *.mov *.mkv *.wmv *.m4v);;Semua File (*)"
        )
        if path:
            self._video_path = path
            fname = os.path.basename(path)
            self._video_display.setText(fname)
            self._video_display.setToolTip(path)
            size_mb = os.path.getsize(path) / (1024 * 1024)
            self._vid_name_lbl.setText(fname)
            self._vid_meta_lbl.setText(
                f"{size_mb:.1f} MB  ·  {os.path.splitext(fname)[1].upper()}"
            )
            self._video_card.setVisible(True)
            self._val_hint.setVisible(False)

    def _buka_pemilih_peta(self):
        dlg = MapPickerDialog(
            initial_lat=self._lat_spin.value(),
            initial_lon=self._lon_spin.value(),
            parent=self
        )
        if dlg.exec():
            lat, lon = dlg.ambil_hasil()
            if lat is not None:
                self._lat_spin.setValue(lat)
                self._lon_spin.setValue(lon)

    def _on_coords_changed(self):
        self._lat = self._lat_spin.value()
        self._lon = self._lon_spin.value()
        self._update_loc_preview()

    def _update_loc_preview(self):
        name = self._loc_name.text().strip() or "Makkah al-Mukarramah"
        self._loc_name_preview.setText(name)
        self._loc_coords_preview.setText(
            f"{self._lat_spin.value():.6f}°,  {self._lon_spin.value():.6f}°"
        )

    def _on_jalankan(self):
        if not self._video_path or not os.path.exists(self._video_path):
            self._val_hint.setText("⚠  Pilih file video yang valid terlebih dahulu.")
            self._val_hint.setVisible(True)
            return

        adv = self._adv.ambil_params()

        if adv["X_COUNT"] > adv["Y_COUNT"]:
            self._val_hint.setText("⚠  X_COUNT tidak boleh lebih besar dari Y_COUNT.")
            self._val_hint.setVisible(True)
            return

        if adv["INTERVAL_S"] > adv["WINDOW_S"]:
            self._val_hint.setText("⚠  INTERVAL_S tidak boleh lebih besar dari WINDOW_S.")
            self._val_hint.setVisible(True)
            return

        self._val_hint.setVisible(False)
        self._update_loc_preview()

        video_name = os.path.splitext(os.path.basename(self._video_path))[0]
        params = {
            "video_path":    self._video_path,
            "video_name":    video_name,
            "location_name": self._loc_name.text().strip() or "Titik Pengamatan",
            "lat":           self._lat_spin.value(),
            "lon":           self._lon_spin.value(),
            **adv,
        }
        self.run_requested.emit(params)

    def set_running(self, running: bool):
        self._run_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._run_btn.setText(
            "Sedang Berjalan..." if running else "Mulai Analisis"
        )