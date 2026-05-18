BOTTLENECK_THRESH = 0.05  


def klasifikasi_arus_3level(
    v_norm: float,
    tau:    float = 0.2249,
    bottleneck_thresh: float = BOTTLENECK_THRESH,
) -> str:

    if v_norm < bottleneck_thresh:
        return "BOTTLENECK"
    elif v_norm < tau:
        return "LAMBAT"
    else:
        return "LANCAR"


def klasifikasi_keramaian(rerata_jumlah, rasio_lambat, X=60, Y=90, SH=0.5):
    """
    Menentukan label tingkat keramaian berdasarkan jumlah orang dan rasio lambat.

    Parameter:
        rerata_jumlah : rata-rata jumlah orang per window
        rasio_lambat  : proporsi pejalan kaki yang bergerak lambat (0.0–1.0)
        X             : ambang bawah keramaian sedang (default 60)
        Y             : ambang bawah keramaian tinggi (default 90)
        SH            : ambang rasio lambat (default 0.5)

    Return:
        str - "TINGGI", "SEDANG", atau "RENDAH"
    """
    if rerata_jumlah >= Y:
        return "TINGGI"

    elif X <= rerata_jumlah < Y:
        if rasio_lambat >= SH:
            return "TINGGI"
        else:
            return "SEDANG"

    else:  # rerata_jumlah < X
        if rasio_lambat >= SH:
            return "SEDANG"
        else:
            return "RENDAH"


def klasifikasi_pergerakan(rasio_lambat, rerata_jumlah, X, SH=0.5):
    """
    Menentukan label kondisi pergerakan jamaah.

    Parameter:
        rasio_lambat  : proporsi pejalan kaki lambat (0.0–1.0)
        rerata_jumlah : rata-rata jumlah orang per window
        X             : ambang bawah keramaian (untuk filter kepadatan)
        SH            : ambang rasio lambat (default 0.5)

    Return:
        str — "TERSENDAT" atau "LANCAR"
    """
    if rerata_jumlah < X:
        return "LANCAR"
    return "TERSENDAT" if rasio_lambat >= SH else "LANCAR"


def klasifikasi_pergerakan_3level(
    rasio_bottleneck: float,
    rasio_lambat:     float,
    rerata_jumlah:    float,
    X:                float,
    SH:               float = 0.5,
    SB:               float = 0.3,
) -> str:
    """
    Label output:
        BOTTLENECK : proporsi track bottleneck ≥ SB DAN jumlah ≥ X
        TERSENDAT  : proporsi lambat ≥ SH DAN jumlah ≥ X
        LANCAR     : kondisi normal

    Parameter

    rasio_bottleneck : n_bottleneck / n_terdefinisi dalam window
    rasio_lambat     : n_lambat / n_terdefinisi dalam window
    rerata_jumlah    : rata-rata count per window
    X                : ambang bawah jumlah (sama dengan X_COUNT)
    SH               : ambang rasio lambat (default 0.5)
    SB               : ambang rasio bottleneck (default 0.3)

    """
    if rerata_jumlah < X:
        return "LANCAR"

    if rasio_bottleneck >= SB:
        return "BOTTLENECK"

    if rasio_lambat >= SH:
        return "TERSENDAT"

    return "LANCAR"