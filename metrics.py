import math
from collections import deque
from classifier import klasifikasi_arus_3level, BOTTLENECK_THRESH

MAKS_DT_KECEPATAN    = 1.0   # batas selisih waktu antar frame (detik)
MAKS_FRAME_ABSEN     = 10    # toleransi frame tanpa deteksi sebelum track dihapus
PANJANG_RIWAYAT_H    = 5     # jumlah sampel tinggi bbox yang disimpan per track
MIN_CROWD_BOTTLENECK = 5     # minimal n_terdefinisi sebelum bottleneck dianggap valid
PANJANG_POS_HISTORY  = 15    

MIN_BBOX_H           = 20         

V_NORM_CAP           = 3.0   # batas atas v_norm yang masuk akal                            

PANJANG_VNORM_SMOOTH = 5     
                             
class KalkulatorMetrik:

    def __init__(
        self,
        tau               = 0.2249,   
        bottleneck_thresh = BOTTLENECK_THRESH,
        maks_dt           = MAKS_DT_KECEPATAN,
        maks_absen        = MAKS_FRAME_ABSEN,
        panjang_hist      = PANJANG_RIWAYAT_H,
        min_crowd_bottleneck = MIN_CROWD_BOTTLENECK,
        panjang_pos_history  = PANJANG_POS_HISTORY,
        min_bbox_h        = MIN_BBOX_H,
        v_norm_cap        = V_NORM_CAP,
        panjang_smooth    = PANJANG_VNORM_SMOOTH,
    ):
        self.tau                  = tau
        self.bottleneck_thresh    = bottleneck_thresh
        self.maks_dt              = maks_dt
        self.maks_absen           = maks_absen
        self.panjang_hist         = panjang_hist
        self.min_crowd_bottleneck = min_crowd_bottleneck
        self.panjang_pos_history  = panjang_pos_history
        self.min_bbox_h           = min_bbox_h
        self.v_norm_cap           = v_norm_cap
        self.panjang_smooth       = panjang_smooth

        self.riwayat_track = {}

    @staticmethod
    def _median(nilai_list):
        terurut = sorted(nilai_list)
        n       = len(terurut)
        tengah  = n // 2
        return terurut[tengah] if n % 2 else (terurut[tengah - 1] + terurut[tengah]) / 2.0

    def perbarui(self, jalur_terkonfirmasi, timestamp):
        
        jumlah          = len(jalur_terkonfirmasi)
        n_terdefinisi   = 0
        n_lambat        = 0
        n_bottleneck    = 0
        ids_lambat      = set()
        ids_bottleneck  = set()
        kecepatan_track = []

        id_aktif = {t["id"] for t in jalur_terkonfirmasi}

        for t in jalur_terkonfirmasi:
            tid       = t["id"]
            cx, cy, h = t["cx"], t["cy"], t["h"]

            if tid in self.riwayat_track:
                sebelumnya = self.riwayat_track[tid]
                dt         = timestamp - sebelumnya["ts"]
                sebelumnya["pos_history"].append((cx, cy))

                if 0 < dt <= self.maks_dt:
                    h_robust = self._median(list(sebelumnya["riwayat_h"]))
                    if h_robust < self.min_bbox_h:
                        sebelumnya["riwayat_h"].append(h)
                        sebelumnya["cx"]    = cx
                        sebelumnya["cy"]    = cy
                        sebelumnya["ts"]    = timestamp
                        sebelumnya["absen"] = 0
                        continue

                    if h_robust > 0:
                        raw_dx   = cx - sebelumnya["cx"]
                        raw_dy   = cy - sebelumnya["cy"]
                        jarak    = math.sqrt(raw_dx ** 2 + raw_dy ** 2)
                        v_piksel = jarak / dt
                        v_norm_raw = v_piksel / h_robust
                        v_norm_capped = min(v_norm_raw, self.v_norm_cap)

                        sebelumnya["vnorm_buffer"].append(v_norm_capped)
                        v_norm_smooth = sum(sebelumnya["vnorm_buffer"]) / len(sebelumnya["vnorm_buffer"])
                        if jarak > 0.5:
                            dx_norm = raw_dx / jarak
                            dy_norm = raw_dy / jarak
                        else:
                            dx_norm = 0.0
                            dy_norm = 0.0

                        n_terdefinisi += 1

                        
                        arus = klasifikasi_arus_3level(
                            v_norm_smooth,
                            tau=self.tau,
                            bottleneck_thresh=self.bottleneck_thresh,
                        )

                        lambat    = int(arus == "LAMBAT")
                        is_bottle = int(arus == "BOTTLENECK")

                        if lambat:
                            n_lambat += 1
                            ids_lambat.add(tid)

                        if is_bottle:
                            n_bottleneck += 1
                            ids_bottleneck.add(tid)

                        kecepatan_track.append({
                            "track_id":      tid,
                            "cx":            round(cx, 2),
                            "cy":            round(cy, 2),
                            "bbox_h":        round(h_robust, 2),
                            
                            "v_norm":        round(v_norm_capped, 6),
                            
                            "v_norm_smooth": round(v_norm_smooth, 6),
                            "is_lambat":     lambat,
                            "is_bottleneck": is_bottle,
                            "arus":          arus,
                            "dx_norm":       round(dx_norm, 4),
                            "dy_norm":       round(dy_norm, 4),
                            "pos_history":   list(sebelumnya["pos_history"]),
                        })

                sebelumnya["riwayat_h"].append(h)
                sebelumnya["cx"]    = cx
                sebelumnya["cy"]    = cy
                sebelumnya["ts"]    = timestamp
                sebelumnya["absen"] = 0

            else:
               
                self.riwayat_track[tid] = {
                    "cx":           cx,
                    "cy":           cy,
                    "riwayat_h":    deque([h], maxlen=self.panjang_hist),
                    "ts":           timestamp,
                    "absen":        0,
                    "pos_history":  deque([(cx, cy)], maxlen=self.panjang_pos_history),
                    
                    "vnorm_buffer": deque(maxlen=self.panjang_smooth),
                }

        akan_dihapus = []
        for tid, data in self.riwayat_track.items():
            if tid not in id_aktif:
                data["absen"] += 1
                if data["absen"] > self.maks_absen:
                    akan_dihapus.append(tid)
        for tid in akan_dihapus:
            del self.riwayat_track[tid]

        sf = n_lambat     / n_terdefinisi if n_terdefinisi > 0 else 0.0
        sb = n_bottleneck / n_terdefinisi if n_terdefinisi > 0 else 0.0

        if n_terdefinisi < self.min_crowd_bottleneck:
            n_bottleneck   = 0
            sb             = 0.0
            ids_lambat     = ids_lambat | ids_bottleneck
            ids_bottleneck = set()

        return (
            jumlah, n_terdefinisi, n_lambat, n_bottleneck,
            sf, sb,
            ids_lambat, ids_bottleneck,
            kecepatan_track,
        )