"""Sayed Felfel (سيد فلفل) — SDF sculpt. Game coords: metres, +Y up, +Z forward (faces +Z), +X = character's left.
Layers are smooth-unioned inside a layer and hard-min'd between layers, so clothes read as separate fabric shells."""
import numpy as np
L = dict(skin=0, hair=1, tee=2, shirt=3, jeans=4, shoe=5, sole=6, mouth=7, brow=8, lip=9, nose=10)
NL = len(L)
def _n(v): return np.linalg.norm(v, axis=-1)
def smin(a, b, k):
    h = np.maximum(k - np.abs(a - b), 0) / k; return np.minimum(a, b) - h * h * k * 0.25
def ell(P, c, r):
    q = (P - c) / r; k0 = _n(q); k1 = _n(q / r); return k0 * (k0 - 1) / np.maximum(k1, 1e-6)
def cap(P, a, b, ra, rb=None):
    rb = ra if rb is None else rb; a = np.array(a, float); b = np.array(b, float); d = b - a
    t = np.clip(((P - a) @ d) / (d @ d), 0, 1); return _n(P - (a + t[:, None] * d)) - (ra + (rb - ra) * t)
def sph(P, c, r): return _n(P - np.array(c)) - r
def rbox(P, c, h, r):
    q = np.abs(P - np.array(c)) - np.array(h) + r; return _n(np.maximum(q, 0)) + np.minimum(q.max(-1), 0) - r
def torus(P, c, ax, R, r):
    ax = np.array(ax, float); ax /= np.linalg.norm(ax); q = P - np.array(c); h = q @ ax; pr = q - h[:, None] * ax
    return np.hypot(_n(pr) - R, h) - r
def smax(a, b, k): return -smin(-a, -b, k)
def mouth_arc(x): t = np.clip(x / 0.125, -1, 1); return 1.468 + 0.05 * t * t
def mouth_h(x): t = np.clip(x / 0.125, -1, 1); return 0.031 - 0.010 * np.abs(t)
EYE = (0.080, 1.618, 0.170)
S_LIP_Y = 1.468 - 0.046
def sm(lst, k):
    d = lst[0]
    for x in lst[1:]: d = smin(d, x, k)
    return d

def curl_positions(seed=7):
    rng = np.random.default_rng(seed); pts = []
    c = np.array([0, 1.655, -0.012])
    for _ in range(4000):
        v = rng.normal(size=3); v /= np.linalg.norm(v)
        s = 1.0 + rng.uniform(0.0, 0.1)
        p = c + v * np.array([0.215, 0.215, 0.225]) * s
        y, z = p[1], p[2]
        if y < 1.515 + 0.58 * (z + 0.2): continue            # hairline: high at the forehead, low at the nape
        if y < 1.60 and abs(p[0]) < 0.14 and z > 0.0: continue
        if any(np.linalg.norm(p - q) < 0.034 for q, _ in pts): continue
        ax = rng.normal(size=3); ax /= np.linalg.norm(ax); pts.append((p, ax))
        if len(pts) >= 300: break
    return pts
CURLS = curl_positions()

def gr(u, w, A): return A * np.exp(-(u / w) ** 2)                      # gaussian crease profile (positive = groove)
def sstep(a, b, v):
    t = np.clip((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)
def rr2(x, y, cx, cy, hx, hy, r):                                       # 2D rounded rectangle distance
    qx = np.abs(x - cx) - hx + r; qy = np.abs(y - cy) - hy + r
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
WRIST = 0.76

def hand(P, s):
    """relaxed open hand, palm facing the thigh (-x for the left hand), fingers lightly curled, thumb forward. s=+1 left (+x)."""
    cx = s * 0.362
    palm = rbox(P, [cx, 0.708, 0.004], [0.017, 0.048, 0.044], 0.014)
    parts = [palm]
    # fingers: (z offset, length scale, splay)
    for zo, ls, sp in ((0.036, 0.93, 0.07), (0.012, 1.0, 0.02), (-0.012, 0.95, -0.02), (-0.034, 0.76, -0.08)):
        b0 = np.array([cx, 0.668, zo]); l1, l2, l3 = 0.040 * ls, 0.030 * ls, 0.024 * ls
        b1 = b0 + np.array([-s * 0.004, -l1, sp * l1]); b2 = b1 + np.array([-s * 0.010, -l2, sp * l2]); b3 = b2 + np.array([-s * 0.016, -l3 * 0.9, sp * l3 * 0.6])
        parts += [cap(P, b0, b1, 0.0098, 0.0092), cap(P, b1, b2, 0.0092, 0.0086), cap(P, b2, b3, 0.0086, 0.0075)]
    t0 = np.array([cx - s * 0.002, 0.738, 0.040]); t1 = t0 + np.array([-s * 0.004, -0.030, 0.030]); t2 = t1 + np.array([-s * 0.006, -0.026, 0.020])
    parts += [cap(P, t0, t1, 0.0125, 0.0105), cap(P, t1, t2, 0.0105, 0.0088)]
    return sm(parts, 0.008)

def build(P):
    """P: (N,3) points -> (N, NL) per-layer signed distances."""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; ax = np.abs(x); out = np.full((len(P), NL), 9.0)
    def mir(f):
        return [f(1.0), f(-1.0)]
    # ---------- skin ----------
    head = sm([ell(P, [0, 1.57, 0.035], [0.198, 0.205, 0.19]), ell(P, [0, 1.505, 0.06], [0.196, 0.152, 0.178]), ell(P, [0, 1.425, 0.112], [0.092, 0.072, 0.08])]
              + mir(lambda s: ell(P, [s * 0.108, 1.512, 0.108], [0.085, 0.074, 0.07])) + mir(lambda s: ell(P, [s * 0.197, 1.56, 0.0], [0.028, 0.05, 0.034]))
              + [ell(P, [0, S_LIP_Y, 0.212], [0.072, 0.020, 0.022])], 0.05)
    neck = cap(P, [0, 1.34, 0.0], [0, 1.50, 0.02], 0.103)
    arms = []
    for s in (1, -1):
        arms += [cap(P, [s * 0.262, 1.26, 0.0], [s * 0.325, 1.03, 0.0], 0.060, 0.058), cap(P, [s * 0.325, 1.03, 0.0], [s * 0.355, WRIST, 0.004], 0.060, 0.043), hand(P, s)]
    skin = sm([head, neck] + arms, 0.04)
    arc = mouth_arc(x)
    cav = np.maximum(np.abs(x) - 0.130, np.maximum(np.abs(y - arc) - mouth_h(x), 0.10 - z))
    eyes = [sph(P, [s * EYE[0], EYE[1], EYE[2]], 0.049) for s in (1, -1)]
    skin = np.maximum(skin, -sm([cav] + eyes, 0.01))
    nose = ell(P, [0, 1.545, 0.216], [0.058, 0.070, 0.064]); nose = smin(nose, ell(P, [0, 1.585, 0.188], [0.042, 0.052, 0.044]), 0.03)
    brow = sm([sm([cap(P, [s * 0.036, 1.696, 0.205], [s * 0.104, 1.720, 0.189], 0.0142, 0.0150), cap(P, [s * 0.104, 1.720, 0.189], [s * 0.172, 1.686, 0.152], 0.0150, 0.0120)], 0.01) for s in (1, -1)], 0.02)
    skin_all = smin(smin(skin, nose, 0.04), brow, 0.035)
    # ---------- hair ----------
    cap_d = ell(P, [0, 1.655, -0.012], [0.222, 0.222, 0.232])
    plane = (1.515 + 0.58 * (z + 0.2)) - y
    hair_base = np.maximum(cap_d, plane)
    hair_base = np.maximum(hair_base, -ell(P, [0, 1.55, 0.06], [0.185, 0.17, 0.185]) + 0.0)
    curls = []
    lo, hi = P.min(0) - 0.07, P.max(0) + 0.07
    for (p, a) in CURLS:
        if np.any(p < lo) or np.any(p > hi): continue
        m = (np.abs(x - p[0]) < 0.06) & (np.abs(y - p[1]) < 0.06) & (np.abs(z - p[2]) < 0.06)
        d = np.full(len(P), 1.0)
        if m.any(): d[m] = torus(P[m], p, a, 0.021, 0.0165)
        curls.append(d)
    hair = smin(hair_base, np.min(curls, 0), 0.02) if curls else hair_base
    hair = np.maximum(hair, -ell(P, [0, 1.52, 0.10], [0.17, 0.17, 0.15]))
    # ---------- tee (green) ----------
    tee = sm([ell(P, [0, 1.09, -0.005], [0.24, 0.30, 0.205]), ell(P, [0, 0.97, 0.04], [0.225, 0.215, 0.2]), ell(P, [0, 1.25, 0.0], [0.25, 0.14, 0.19])], 0.06)
    tee = np.maximum(tee, y - 1.385)
    tee = smin(tee, torus(P, [0, 1.384, 0.0], [0, 1, 0.1], 0.098, 0.013), 0.01)                  # ribbed crew neck
    # ---------- open overshirt (khaki), rolled sleeves ----------
    skirt = np.maximum((np.hypot(x / 0.286, (z - 0.02) / 0.262) - 1.0) * 0.26, np.abs(y - 0.84) - 0.14)                    # straight hanging hem so the shirt bottom is a clean edge
    sh_core = sm([ell(P, [0, 1.12, -0.01], [0.262, 0.31, 0.222]), ell(P, [0, 0.95, 0.035], [0.268, 0.25, 0.222]), ell(P, [0, 1.27, 0.0], [0.262, 0.14, 0.2]), skirt], 0.07)
    sleeves = []
    for s in (1, -1):
        sleeves += [cap(P, [s * 0.225, 1.315, 0.0], [s * 0.322, 1.075, 0.0], 0.094, 0.079),
                    torus(P, [s * 0.322, 1.045, 0.0], [0.03 * s, 1, 0], 0.077, 0.029), torus(P, [s * 0.324, 1.094, 0.0], [0.03 * s, 1, 0], 0.081, 0.023)]
    shb = sm([smax(sh_core, y - (1.405 - 0.55 * np.maximum(ax - 0.07, 0)), 0.035)] + sleeves, 0.04)          # sloping shoulder line
    shb = smax(shb, 0.700 - y, 0.014)                                                              # hem
    wedge_w = 0.052 + 0.075 * np.clip((1.36 - y) / 0.52, 0, 1)
    cutd = np.maximum(ax - wedge_w, -(z - 0.02))
    shirt = smax(shb, -cutd, 0.02)
    # placket band (button strip) along the open edge, collar, pockets with flaps and buttons
    band = np.maximum(shb - 0.004, np.maximum(ax - (wedge_w + 0.040), -(ax - wedge_w + 0.012)))
    band = np.maximum(band, np.maximum(-(z - 0.02), y - 1.38))
    collar = np.maximum(torus(P, [0, 1.405, -0.008], [0, 1, 0.12], 0.108, 0.026), -np.maximum(ax - 0.062, -(z - 0.02)))
    pk = []
    for s in (1, -1):
        cx = s * 0.135
        fz = 0.06 - z                                                                  # front only
        body = np.maximum(np.maximum(shb - 0.0042, rr2(x, y, cx, 1.150, 0.044, 0.050, 0.006)), fz)
        flap = np.maximum(np.maximum(shb - 0.0078, np.maximum(rr2(x, y, cx, 1.178, 0.046, 0.020, 0.008), -(y - 1.09))), fz)
        btn = np.maximum(np.maximum(shb - 0.0105, _n(np.stack([x - cx, y - 1.160], -1)) - 0.0075), fz)
        pk += [body, flap, btn]
    shirt = sm([shirt, collar, band] + pk, 0.0035)
    # fabric creases (geometry; baked into the normal map)
    cr = np.zeros(len(P)); front = sstep(-0.02, 0.10, z); back = sstep(0.0, -0.10, z); side = lambda s: (x * s > 0)
    for s in (1, -1):
        for k, (c0, wd) in enumerate(((0.0, 0.0065), (0.045, 0.006), (0.09, 0.0055))):                                   # belly drag folds, fanning down-outwards from the buttoned centre
            u = (np.array([s * 0.62, 0.78, 0.0]) @ np.stack([x - s * 0.13, y - 0.98, z], 0).reshape(3, -1)) + c0 * 1.0
            m = front * sstep(0.06, 0.12, ax) * sstep(0.27, 0.20, ax) * sstep(0.68, 0.76, y) * sstep(1.06, 0.96, y)
            cr += gr(u, wd, 0.0028) * m
        for yi, am in ((1.125, 0.0028), (1.175, 0.0024)):                                                     # sleeve bunching above the rolled cuff
            cr += gr(y - yi - 0.012 * (ax - 0.3), 0.0065, am) * sstep(0.215, 0.28, ax) * sstep(1.26, 1.20, y)
    for yi in (0.94, 0.84, 0.76): cr += gr(y - yi, 0.008, 0.0045) * back * sstep(1.08, 1.0, y)
    shirt = shirt + cr
    # ---------- jeans ----------
    jl = [ell(P, [0, 0.84, -0.01], [0.262, 0.15, 0.215]), ell(P, [0, 0.89, 0.03], [0.25, 0.12, 0.2])]
    for s in (1, -1):
        jl += [cap(P, [s * 0.128, 0.82, 0.0], [s * 0.124, 0.46, 0.012], 0.137, 0.103), cap(P, [s * 0.124, 0.46, 0.012], [s * 0.122, 0.12, 0.014], 0.103, 0.078)]
    jeans = sm(jl, 0.05)
    jr = np.zeros(len(P)); cuffs = []
    for s in (1, -1):
        lx = s * 0.122; cuffs += [torus(P, [lx, 0.150, 0.014], [0, 1, 0], 0.083, 0.027), torus(P, [lx, 0.186, 0.014], [0, 1, 0], 0.086, 0.019)]
        for yi, am in ((0.50, 0.0030), (0.465, 0.0034), (0.43, 0.0028)): jr += gr(y - yi + 0.01 * np.sin((x - lx) * 30), 0.007, am) * sstep(-0.01, 0.09, z) * (np.abs(x - lx) < 0.14)           # knee front creases
        for yi, am in ((0.485, 0.004), (0.445, 0.0036)): jr += gr(y - yi, 0.007, am) * sstep(0.0, -0.09, z) * (np.abs(x - lx) < 0.14)                                                            # back-of-knee folds
        for yi, am in ((0.26, 0.0016), (0.30, 0.0014)): jr += gr(y - yi, 0.0075, am)                                                                                           # stacked fabric above the cuff
        for k, (nx, ny, nz_) in enumerate(((0.5, 0.7, 0.5), (0.7, 0.55, 0.45), (0.35, 0.85, 0.4))):
            u = np.array([s * nx, ny, nz_]) @ np.stack([x - s * 0.04, y - 0.78 - 0.02 * k, z - 0.12], 0).reshape(3, -1); jr += gr(u, 0.006, 0.0012) * sstep(0.04, 0.12, z) * sstep(0.88, 0.8, y) * sstep(0.62, 0.7, y)    # crotch whiskers
    jeans = sm([jeans] + cuffs, 0.012); jeans = jeans + jr
    jeans = np.maximum(jeans, 0.098 - y)
    # ---------- sneakers ----------
    sl, so = [], []
    for s in (1, -1):
        sx = s * 0.124
        sl += [ell(P, [sx, 0.072, 0.075], [0.058, 0.050, 0.150]), ell(P, [sx, 0.070, 0.195], [0.056, 0.044, 0.085]), ell(P, [sx, 0.112, -0.012], [0.060, 0.056, 0.075])]
        so += [rbox(P, [sx, 0.018, 0.090], [0.062, 0.018, 0.158], 0.014)]
    shoe = np.maximum(sm(sl, 0.03), 0.040 - y)
    sole = sm(so, 0.01)
    out[:, L['skin']] = skin_all; out[:, L['hair']] = hair; out[:, L['tee']] = tee; out[:, L['shirt']] = shirt
    out[:, L['jeans']] = jeans; out[:, L['shoe']] = shoe; out[:, L['sole']] = sole
    out[:, L['brow']] = brow; out[:, L['mouth']] = cav; out[:, L['lip']] = cav; out[:, L['nose']] = nose
    return out

def surface(P):
    """total SDF + owning layer id"""
    D = build(P); d = D[:, [L[k] for k in ('skin', 'hair', 'tee', 'shirt', 'jeans', 'shoe', 'sole')]]
    ids = [L[k] for k in ('skin', 'hair', 'tee', 'shirt', 'jeans', 'shoe', 'sole')]
    a = d.argmin(1); return d.min(1), np.array(ids)[a], D
