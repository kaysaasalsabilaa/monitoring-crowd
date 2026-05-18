from collections import deque


class RollingCrowdWindow:

    def __init__(self, window_s: float = 10.0, output_interval_s: float = 1.0):

        if output_interval_s > window_s:
            raise ValueError(
                f"output_interval_s ({output_interval_s}s) tidak boleh "
                f"lebih besar dari window_s ({window_s}s). "
                f"Pastikan INTERVAL_S <= WINDOW_S di pengaturan."
            )

        self.window_s          = window_s
        self.output_interval_s = output_interval_s
        self.buffer            = deque()
        self.next_output_ts    = None
        self.window_k          = 0

    def push(
        self,
        ts:            float,
        count:         int,
        n_terdefinisi: int,
        n_lambat:      int,
        n_bottleneck:  int = 0,  
    ) -> None:

        self.buffer.append((ts, count, n_terdefinisi, n_lambat, n_bottleneck))

        while self.buffer and (ts - self.buffer[0][0]) > self.window_s:
            self.buffer.popleft()

        if self.next_output_ts is None:
            self.next_output_ts = ts + self.output_interval_s

    def should_output(self, ts: float) -> bool:
        return self.next_output_ts is not None and ts >= self.next_output_ts

    def get_features(self, ts: float) -> dict | None:

        if not self.buffer:
            self.next_output_ts += self.output_interval_s
            return None

        counts                = [s[1] for s in self.buffer]
        n_terdefinisi_total   = sum(s[2] for s in self.buffer)
        n_lambat_total        = sum(s[3] for s in self.buffer)
        n_bottleneck_total    = sum(s[4] for s in self.buffer)   # ← baru

        rerata_jumlah  = sum(counts) / len(counts)

        rasio_lambat = (
            n_lambat_total / n_terdefinisi_total
            if n_terdefinisi_total > 0 else 0.0
        )
        rasio_bottleneck = (
            n_bottleneck_total / n_terdefinisi_total
            if n_terdefinisi_total > 0 else 0.0
        )

        self.window_k       += 1
        self.next_output_ts += self.output_interval_s

        return {
            "window_k":              self.window_k,
            "window_start":          round(self.buffer[0][0], 3),
            "window_end":            round(self.buffer[-1][0], 3),
            "count_avg":             round(rerata_jumlah, 2),
            "n_terdefinisi_total":   n_terdefinisi_total,
            "n_lambat_total":        n_lambat_total,
            "n_bottleneck_total":    n_bottleneck_total,            # ← baru
            "slow_ratio":            round(rasio_lambat, 4),
            "bottleneck_ratio":      round(rasio_bottleneck, 4),    # ← baru
        }