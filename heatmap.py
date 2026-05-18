import cv2
import numpy as np

_DECAY     = 0.96
_SIGMA_PX  = 15      
_ALPHA     = 0.45
_GRID_COLS = 8
_GRID_ROWS = 6


class HeatmapEngine:
    
    def __init__(
        self,
        frame_width:  int   = 1280,
        frame_height: int   = 720,
        decay:        float = _DECAY,
        alpha:        float = _ALPHA,
        grid_cols:    int   = _GRID_COLS,
        grid_rows:    int   = _GRID_ROWS,
        crowd_top_y:  int   = 200,
    ):
        self.W           = frame_width
        self.H           = frame_height
        self.decay       = decay
        self.alpha       = alpha
        self.grid_cols   = grid_cols
        self.grid_rows   = grid_rows
        self.crowd_top_y = crowd_top_y

        sigma = _SIGMA_PX | 1
        self._ksize = (sigma * 6 + 1, sigma * 6 + 1)
        self._sigma = sigma

        self._heat = np.zeros((frame_height, frame_width), dtype=np.float32)

        self._grid_density = np.zeros((grid_rows, grid_cols), dtype=np.float32)

    def update(self, jalur_terkonfirmasi: list) -> None:
       
        self._heat *= self.decay

        stamp = np.zeros((self.H, self.W), dtype=np.float32)
        for t in jalur_terkonfirmasi:
            cx = int(np.clip(t["cx"], 0, self.W - 1))
            cy = int(np.clip(t["cy"], 0, self.H - 1))
            stamp[cy, cx] += 2000.0

        if stamp.max() > 0:
            stamp = cv2.GaussianBlur(stamp, self._ksize, self._sigma)

        self._heat = np.clip(self._heat + stamp, 0, 255)
        self._update_grid(jalur_terkonfirmasi)

    def _update_grid(self, tracks: list) -> None:
        
        cell_h = self.H / self.grid_rows
        cell_w = self.W / self.grid_cols

        current_density = np.zeros((self.grid_rows, self.grid_cols), dtype=np.float32)

        for t in tracks:
            cx, cy = t["cx"], t["cy"]
            if cy < self.crowd_top_y:
                continue
            r = int(np.clip(cy / cell_h, 0, self.grid_rows - 1))
            c = int(np.clip(cx / cell_w, 0, self.grid_cols - 1))
            current_density[r, c] += 1

        self._grid_density = current_density

    def overlay(self, frame: np.ndarray) -> np.ndarray:

        if frame is None:
            return frame

        h_max = float(self._heat.max())
        if h_max < 1e-3:
            return frame

        heat_norm  = (self._heat / h_max * 255).astype(np.uint8)
        heat_color = cv2.applyColorMap(heat_norm, cv2.COLORMAP_JET)

        nonzero = self._heat[self._heat > 0]
        if len(nonzero) == 0:
            return frame

        thresh_raw  = float(np.percentile(nonzero, 70))
        thresh_norm = int(thresh_raw / h_max * 255)
        mask        = (heat_norm > thresh_norm).astype(np.float32)
        mask_3ch    = np.stack([mask, mask, mask], axis=-1)

        alpha_eff = min(self.alpha, 0.35)
        blended = (
            frame.astype(np.float32) * (1 - alpha_eff * mask_3ch)
            + heat_color.astype(np.float32) * (alpha_eff * mask_3ch)
        )
        frame[:] = np.clip(blended, 0, 255).astype(np.uint8)
        return frame

    def draw_grid(self, frame: np.ndarray) -> np.ndarray:
        cell_h = self.H / self.grid_rows
        cell_w = self.W / self.grid_cols
        color  = (60, 60, 60)
        for r in range(1, self.grid_rows):
            cv2.line(frame, (0, int(r * cell_h)), (self.W, int(r * cell_h)), color, 1)
        for c in range(1, self.grid_cols):
            cv2.line(frame, (int(c * cell_w), 0), (int(c * cell_w), self.H), color, 1)
        return frame

    @property
    def grid_density(self) -> np.ndarray:
        """Grid density saat ini (rows x cols). Read-only."""
        return self._grid_density.copy()

    def reset(self) -> None:
        """Reset semua state (panggil saat video baru)."""
        self._heat[:] = 0
        self._grid_density[:] = 0