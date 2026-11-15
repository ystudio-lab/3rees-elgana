"""Numpy texture baker: rasterises a UV-unwrapped mesh and evaluates the Sayed SDF scene per texel
-> baseColor (sRGB), tangent-space normal (OpenGL), ORM (R=AO G=roughness B=metallic)."""
import numpy as np, sys
from scipy import ndimage
sys.path.insert(0, '.')
import sdf_sayed as S
_rng = np.random.default_rng(11); _G = _rng.random((48, 48, 48)).astype(np.float32)
def noise(P, f):
    q = (P * f) % 48.0; return ndimage.map_coordinates(_G, [q[:, 0], q[:, 1], q[:, 2]], order=1, mode='wrap')
def fbm(P, f, o=3):
    a, s, t = 0.0, 0.5, 0.0
    for i in range(o): a = a + s * noise(P, f * 2 ** i); t += s; s *= 0.5
    return a / t
def hexc(h): h = h.lstrip('#'); return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0
def srgb2lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
C = dict(skin=hexc('#e2a389'), cheek=hexc('#e0968a'), nose=hexc('#dc7f78'), lip=hexc('#c9757a'), mouth=hexc('#2e0e13'), hair=hexc('#17151b'), brow=hexc('#1a1719'),
         tee=hexc('#1f9d6b'), shirt=hexc('#b3a37c'), shirt2=hexc('#9a8a66'), jeans=hexc('#3a4a6c'), jeansW=hexc('#566a8e'), cuff=hexc('#8a98b4'), shoe=hexc('#9a9fb2'),
         shoeD=hexc('#3a4466'), sole=hexc('#ececec'), stub=hexc('#8f7a72'))

def raster(V, F, UV, Nrm, size):
    """returns per-texel arrays for covered texels"""
    pix = []; tri = []; bar = []
    for fi in range(len(F)):
        uv = UV[fi] * size; mn = np.floor(uv.min(0) - 1).astype(int); mx = np.ceil(uv.max(0) + 1).astype(int); mn = np.clip(mn, 0, size - 1); mx = np.clip(mx, 0, size - 1)
        xs, ys = np.meshgrid(np.arange(mn[0], mx[0] + 1), np.arange(mn[1], mx[1] + 1)); p = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
        a, b, c = uv; d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-9: continue
        l1 = ((b[1] - c[1]) * (p[:, 0] - c[0]) + (c[0] - b[0]) * (p[:, 1] - c[1])) / d; l2 = ((c[1] - a[1]) * (p[:, 0] - c[0]) + (a[0] - c[0]) * (p[:, 1] - c[1])) / d; l3 = 1 - l1 - l2
        ok = (l1 >= -0.02) & (l2 >= -0.02) & (l3 >= -0.02)
        if ok.any(): pix.append(p[ok].astype(int)); tri.append(np.full(ok.sum(), fi)); bar.append(np.stack([l1[ok], l2[ok], l3[ok]], 1))
    return np.concatenate(pix), np.concatenate(tri), np.concatenate(bar)

def shade(P, N, T, B):
    n = len(P); d, ids, D = S.surface(P)
    col = np.zeros((n, 3), np.float32); rough = np.full(n, 0.8, np.float32); h = np.zeros(n, np.float32)
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    nz = fbm(P, 38, 3); nz2 = fbm(P, 130, 2)
    m = ids == S.L['skin']
    if m.any():
        c = np.tile(C['skin'], (n, 1)); ch = np.exp(-(((np.abs(x) - 0.115) / 0.05) ** 2 + ((y - 1.515) / 0.045) ** 2 + ((z - 0.12) / 0.1) ** 2)); c = c + (C['cheek'] - C['skin']) * (0.75 * ch)[:, None]
        k = np.clip(1 - (D[:, S.L['nose']] + 0.003) / 0.01, 0, 1) * (z > 0.12); c = c + (C['nose'] - c) * k[:, None]                    # bulb nose
        ear = (np.abs(x) > 0.185) & (y > 1.50) & (y < 1.63); c = c + (C['cheek'] - c) * (0.5 * ear)[:, None]
        jaw = np.clip((1.50 - y) / 0.05, 0, 1) * (z > 0.02) * (y > 1.40) * (np.abs(x) < 0.17); sd = (nz2 > 0.6) * jaw; c = c + (C['stub'] - c) * (0.22 * sd + 0.05 * jaw)[:, None]   # stubble
        b = np.clip(1 - (D[:, S.L['brow']] + 0.002) / 0.004, 0, 1) * (y > 1.62); c = c + (C['brow'] - c) * b[:, None]
        cv = D[:, S.L['mouth']]; lip = np.clip(1 - np.abs(cv - 0.004) / 0.012, 0, 1) * (z > 0.05); c = c + (C['lip'] - c) * (0.9 * lip)[:, None]
        ins = np.clip(1 - (cv + 0.0) / 0.006, 0, 1); c = c + (C['mouth'] - c) * ins[:, None]
        sub = 0.96 + 0.08 * nz; c = c * sub[:, None]
        col[m] = c[m]; rough[m] = 0.62 + 0.15 * ins[m] - 0.1 * (k[m] > 0.3); h[m] = 0.0002 * (nz2[m] - 0.5) + 0.0001 * (fbm(P[m], 260, 1) - 0.5)
    m = ids == S.L['hair']
    if m.any():
        v = 0.8 + 0.5 * fbm(P, 90, 2); sh = np.clip((y - 1.6) / 0.3, 0, 1); col[m] = (C['hair'][None] * v[:, None] + np.array([0.02, 0.025, 0.05]) * sh[:, None])[m]; rough[m] = 0.5; h[m] = (0.0015 * np.sin(fbm(P, 150, 2) * 40))[m]
    m = ids == S.L['tee']
    if m.any():
        knit = 0.5 + 0.5 * np.sin(y * 1100) * np.sin(x * 900 + z * 300); v = 0.93 + 0.1 * knit + 0.05 * nz; col[m] = (C['tee'][None] * v[:, None])[m]; rough[m] = 0.88; h[m] = (0.0002 * knit)[m]
    m = ids == S.L['shirt']
    if m.any():
        wv = 0.5 + 0.5 * np.sin(y * 1500) * np.sin((x + z) * 1500); fold = fbm(P, 22, 3); v = 0.93 + 0.12 * wv + 0.05 * (fold - 0.5); cc = C['shirt'][None] * v[:, None]
        col[m] = cc[m]; rough[m] = 0.93; h[m] = (0.0002 * wv + 0.0012 * (fold - 0.5))[m]
    m = ids == S.L['jeans']
    if m.any():
        tw = 0.5 + 0.5 * np.sin((y * 1300 + x * 1300 + z * 1300)); wh = np.clip(fbm(P * np.array([1, 3, 1]), 18, 3) * 1.8 - 0.55, 0, 1); cc = C['jeans'][None] + (C['jeansW'] - C['jeans'])[None] * (0.7 * wh)[:, None]; cc = cc * (0.92 + 0.12 * tw)[:, None]
        cu = (y < 0.172) & (y > 0.098); cc = np.where(cu[:, None], C['cuff'][None] * (0.9 + 0.2 * nz[:, None]), cc)                  # rolled cuff lining
        col[m] = cc[m]; rough[m] = 0.92; h[m] = (0.0002 * tw + 0.0012 * (fbm(P, 24, 3) - 0.5))[m]
    m = ids == S.L['shoe']
    if m.any():
        mesh = 0.5 + 0.5 * np.sin(x * 1400) * np.sin(z * 1400); cc = np.tile(C['shoe'], (n, 1)) * (0.92 + 0.1 * mesh)[:, None]
        acc = ((np.abs(x) > 0.08) & (np.abs(x) < 0.115) & (y > 0.085) & (z > -0.02) & (z < 0.2)) | (z < -0.07) | ((np.abs(z - 0.17) < 0.02) & (y > 0.09)); cc = np.where(acc[:, None], C['shoeD'][None] * (0.95 + 0.1 * nz[:, None]), cc)
        col[m] = cc[m]; rough[m] = 0.8; h[m] = (0.0002 * mesh)[m]
    m = ids == S.L['sole']
    if m.any(): col[m] = (C['sole'][None] * (0.96 + 0.06 * nz[:, None]))[m]; rough[m] = 0.55; h[m] = (0.0003 * (nz2 - 0.5))[m]
    # ambient occlusion from the SDF (self + garments)
    ao = np.ones(n, np.float32); acc = np.zeros(n, np.float32)
    for dist, w in ((0.012, 0.45), (0.035, 0.35), (0.08, 0.2)):
        dd = S.surface(P + N * dist)[0]; acc += w * np.clip((dist - np.maximum(dd, 0)) / dist, 0, 1)
    ao = np.clip(1 - 0.95 * acc, 0.15, 1)
    return col, rough, ao, h, ids, d

def height_at(P, ids):
    """cheap re-evaluation of just the bump height (for finite differences)"""
    x, y, z = P[:, 0], P[:, 1], P[:, 2]; h = np.zeros(len(P), np.float32)
    nz2 = fbm(P, 130, 2)
    for name in ('skin',): m = ids == S.L[name]; h[m] = (0.0002 * (nz2 - 0.5) + 0.0001 * (fbm(P, 260, 1) - 0.5))[m]
    m = ids == S.L['hair']; h[m] = (0.0015 * np.sin(fbm(P, 150, 2) * 40))[m]
    m = ids == S.L['tee']; h[m] = (0.0002 * (0.5 + 0.5 * np.sin(y * 1100) * np.sin(x * 900 + z * 300)))[m]
    m = ids == S.L['shirt']; h[m] = (0.0002 * (0.5 + 0.5 * np.sin(y * 1500) * np.sin((x + z) * 1500)) + 0.0012 * (fbm(P, 22, 3) - 0.5))[m]
    m = ids == S.L['jeans']; h[m] = (0.0002 * (0.5 + 0.5 * np.sin(y * 1300 + x * 1300 + z * 1300)) + 0.0012 * (fbm(P, 24, 3) - 0.5))[m]
    m = ids == S.L['shoe']; h[m] = (0.0002 * (0.5 + 0.5 * np.sin(x * 1400) * np.sin(z * 1400)))[m]
    m = ids == S.L['sole']; h[m] = (0.0003 * (nz2 - 0.5))[m]
    return h

def bake(V, F, UV, VN, size, outprefix, swatch_band=0):
    """V (n,3) F (m,3) UV (m,3,2) in 0..1 (v up) VN per-vertex normals"""
    UVp = UV.copy(); UVp[..., 1] = 1 - UVp[..., 1]                                          # image rows go downward
    pix, tri, bar = raster(V, F, UVp, VN, size)
    P = np.einsum('ij,ijk->ik', bar, V[F[tri]]); Nn = np.einsum('ij,ijk->ik', bar, VN[F[tri]]); Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-9
    # per-triangle tangent frame from the UV layout
    e1 = V[F[:, 1]] - V[F[:, 0]]; e2 = V[F[:, 2]] - V[F[:, 0]]; du1 = UV[:, 1, 0] - UV[:, 0, 0]; dv1 = UV[:, 1, 1] - UV[:, 0, 1]; du2 = UV[:, 2, 0] - UV[:, 0, 0]; dv2 = UV[:, 2, 1] - UV[:, 0, 1]
    det = du1 * dv2 - du2 * dv1; det = np.where(np.abs(det) < 1e-12, 1e-12, det)
    Tt = (e1 * dv2[:, None] - e2 * dv1[:, None]) / det[:, None]; Bt = (e2 * du1[:, None] - e1 * du2[:, None]) / det[:, None]
    T = Tt[tri]; Bv = Bt[tri]; T = T - Nn * (T * Nn).sum(1, keepdims=True); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    Bv = Bv - Nn * (Bv * Nn).sum(1, keepdims=True); Bv /= np.linalg.norm(Bv, axis=1, keepdims=True) + 1e-9
    # glTF: tangent-space bitangent follows +V (image-up). Our UV v is up already.
    out = np.zeros((len(P), 3)); rough = np.zeros(len(P)); ao = np.zeros(len(P)); nrm = np.zeros((len(P), 3)); CH = 120000
    for i in range(0, len(P), CH):
        s = slice(i, i + CH); c, r, a, h0, ids, d0 = shade(P[s], Nn[s], T[s], Bv[s]); eps = 0.0015
        hT = height_at(P[s] + T[s] * eps, ids); hB = height_at(P[s] + Bv[s] * eps, ids); gx = (hT - h0) / eps; gy = (hB - h0) / eps; k = 1.0
        e2 = 0.0022; Ps = P[s]; ns = np.stack([S.surface(Ps + np.array(ax_) * e2)[0] - d0 for ax_ in ((1, 0, 0), (0, 1, 0), (0, 0, 1))], 1); ns /= np.linalg.norm(ns, axis=1, keepdims=True) + 1e-9   # sculpt normal (folds, fingers, curls)
        sx = (ns * T[s]).sum(1); sy = (ns * Bv[s]).sum(1); sz = np.maximum((ns * Nn[s]).sum(1), 0.35); sx = np.clip(sx / sz, -1.3, 1.3); sy = np.clip(sy / sz, -1.3, 1.3)
        nn = np.stack([sx - gx * k, sy - gy * k, np.ones_like(gx)], 1); nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        out[s] = c; rough[s] = r; ao[s] = a; nrm[s] = nn; print('  baked', min(i + CH, len(P)), '/', len(P), flush=True)
    img = np.zeros((size, size, 3), np.float32); orm = np.zeros((size, size, 3), np.float32); nm = np.zeros((size, size, 3), np.float32); nm[..., 2] = 1; cov = np.zeros((size, size), bool)
    x, yy = pix[:, 0], pix[:, 1]; img[yy, x] = out; orm[yy, x, 0] = ao; orm[yy, x, 1] = rough; orm[yy, x, 2] = 0.0; nm[yy, x] = nrm; cov[yy, x] = True
    idx = ndimage.distance_transform_edt(~cov, return_distances=False, return_indices=True)                  # bleed into the padding
    for a in (img, orm, nm): a[:] = a[idx[0], idx[1]]
    def u8(a): return (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    return u8(img), u8(orm), u8(nm * 0.5 + 0.5)
