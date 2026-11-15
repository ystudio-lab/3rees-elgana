"""Sayed GLB production build. Run:  python build_glb.py   (needs: bpy numpy scipy scikit-image pillow trimesh)
SDF sculpt (sdf_sayed.py) -> marching cubes -> Blender decimate/UV -> numpy PBR bake (bake.py) -> rig/morphs/clips -> sayed.glb"""
import sys, os, math, time, json, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import bpy, bmesh, mathutils, trimesh
from PIL import Image
import sdf_sayed as S, bake as BK
OUT = os.path.abspath(os.path.join(HERE, '../../assets/characters/sayed/sayed.glb')); WORK = '/tmp/sayed_build'; os.makedirs(WORK, exist_ok=True)
TARGET = dict(body=6300, head=3500)
def g2b(a): a = np.asarray(a, float); return np.stack([a[..., 0], -a[..., 2], a[..., 1]], -1)       # game (y up, +z fwd) -> blender (z up, -y fwd)
def b2g(a): a = np.asarray(a, float); return np.stack([a[..., 0], a[..., 2], -a[..., 1]], -1)
def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)
def mk_obj(name, V, F, collection=True):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in g2b(V)], [], [tuple(f) for f in F]); me.update()
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob); return ob
def decimate_unwrap(name, V, F, tris, hair_cells=False):
    ob = mk_obj(name, V, F); bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    md = ob.modifiers.new('d', 'DECIMATE'); md.ratio = min(1.0, tris / len(F)); md.use_collapse_triangulate = True
    bpy.ops.object.modifier_apply(modifier='d')
    me = ob.data
    for p in me.polygons: p.use_smooth = True
    me.calc_loop_triangles(); Vn = b2g(np.array([v.co[:] for v in me.vertices])); Fn = np.array([t.vertices[:] for t in me.loop_triangles])
    hair = np.zeros(len(me.polygons), bool)
    if hair_cells:
        cen = Vn[Fn].mean(1); hair = S.surface(cen)[1] == S.L['hair']
    me = ob.data; me.calc_loop_triangles(); N2 = b2g(np.array([v.normal[:] for v in me.vertices]))
    nf = len(Fn); UV = np.zeros((nf, 3, 2))
    sel = np.where(~hair)[0]; UVs = xatlas_uv(Vn, Fn[sel]); UV[sel] = UVs
    if hair_cells:
        UV[~hair, :, 1] = 0.32 + UV[~hair, :, 1] * 0.68                      # unwrapped skin/face charts occupy the upper 68 %
        idx = np.where(hair)[0]; ncell = (len(idx) + 1) // 2; H0, H1 = 0.0, 0.31; W = 1024; Hpx = (H1 - H0) * 1024
        s = int(math.floor(math.sqrt(W * Hpx / ncell))); cols = W // s; m = 1.5
        for k, fi in enumerate(idx):
            c = k // 2; x0 = (c % cols) * s; y0 = H0 * 1024 + (c // cols) * s
            if k % 2 == 0: q = [(x0 + m, y0 + m), (x0 + s - m, y0 + m), (x0 + m, y0 + s - m)]
            else: q = [(x0 + s - m, y0 + s - m), (x0 + m, y0 + s - m), (x0 + s - m, y0 + m)]
            for j in range(3): UV[fi, j] = (q[j][0] / 1024.0, q[j][1] / 1024.0)
    return Vn, np.array([t.vertices[:] for t in me.loop_triangles]), UV, N2


def xatlas_uv(V, F, cost=6.0):
    """few, large, low-distortion charts packed at uniform texel density (xatlas). Returns per-face-corner UV (nf,3,2), v up, 0..1."""
    import xatlas
    used = np.unique(F); remap = -np.ones(len(V), int); remap[used] = np.arange(len(used)); sub = remap[F]
    at = xatlas.Atlas(); at.add_mesh(V[used].astype(np.float32), sub.astype(np.uint32))
    co = xatlas.ChartOptions(); co.max_cost = cost; co.normal_deviation_weight = 2.0; co.roundness_weight = 0.01; co.straightness_weight = 6.0; co.texture_seam_weight = 0.5
    po = xatlas.PackOptions(); po.resolution = 1024; po.padding = 3; po.bilinear = True; po.rotate_charts = True; po.blockAlign = False
    at.generate(co, po); vm, idx, uv = at[0]
    uv = np.asarray(uv, float); idx = np.asarray(idx).reshape(-1, 3)
    if uv.max() > 1.5: uv = uv / np.array([at.width, at.height])
    assert len(idx) == len(F) and (np.sort(remap[F], 1) == np.sort(np.asarray(vm)[idx], 1)).all(), 'xatlas changed the face order'
    print('  xatlas charts', at.chart_count, 'utilisation %.2f' % at.utilization, flush=True)
    U = uv[idx]; U[..., 1] = 1 - U[..., 1]; return U

def load_mesh(name, ymin, ymax):
    d = np.load(f'/tmp/sayed_{name}.npz'); v, f = d['v'], d['f']; cy = v[f][:, :, 1].mean(1); keep = (cy >= ymin) & (cy <= ymax); f = f[keep]
    used = np.unique(f); remap = -np.ones(len(v), int); remap[used] = np.arange(len(used)); return v[used], remap[f]

def sphere_uv(c, r, nlon=22, nlat=14, lat0=0.0, lat1=math.pi, rot=None):
    """lat-long sphere centred c; returns V,F,UV (per-vertex UV), pole axis = +Z game (front)."""
    V = []; UV = []
    for i in range(nlat + 1):
        th = lat0 + (lat1 - lat0) * i / nlat
        for j in range(nlon + 1):
            ph = 2 * math.pi * j / nlon; V.append([r * math.sin(th) * math.cos(ph), r * math.sin(th) * math.sin(ph), r * math.cos(th)]); UV.append([j / nlon, 1 - i / nlat])
    F = []
    for i in range(nlat):
        for j in range(nlon):
            a = i * (nlon + 1) + j; b = a + 1; c2 = a + nlon + 1; d = c2 + 1; F += [[a, c2, b], [b, c2, d]]
    return np.array(V), np.array(F), np.array(UV)

def build_all():
    t0 = time.time()
    # ---------------- sculpt meshes (marching cubes, game coords) ----------------
    import mesh_stage as MS
    MS.run((-0.5, 0.0, -0.32), (0.5, 1.44, 0.42), 0.005, 'body'); MS.run((-0.3, 1.38, -0.3), (0.3, 1.98, 0.33), 0.0052, 'head')
    bv, bf = load_mesh('body', 0, 1.43); hv, hf = load_mesh('head', 1.385, 9)
    BV, BF, BUV, BN = decimate_unwrap('body', bv, bf, TARGET['body']); HV, HF, HUV, HN = decimate_unwrap('head', hv, hf, TARGET['head'], hair_cells=True)
    HUV = HUV.copy(); HUV[..., 1] = 0.085 + HUV[..., 1] * 0.915                                   # keep a swatch band (v<0.085) for teeth/tongue/lids
    print('decimated body', len(BF), 'head', len(HF), 'sec %.0f' % (time.time() - t0), flush=True)
    return dict(BV=BV, BF=BF, BUV=BUV, BN=BN, HV=HV, HF=HF, HUV=HUV, HN=HN)

def bake_textures(G, size=1024):
    res = {}
    for k, (V, F, UV, N) in {'body': (G['BV'], G['BF'], G['BUV'], G['BN']), 'head': (G['HV'], G['HF'], G['HUV'], G['HN'])}.items():
        print('baking', k, flush=True); a, o, n = BK.bake(V, F, UV, N, size, k); res[k] = (a, o, n)
    # swatch band on the head atlas: teeth | gum/tongue | skin(lid) | dark
    alb, orm, nrm = res['head']; H = alb.shape[0]; band = int(0.085 * H); sw = [(244, 238, 222), (205, 96, 104), (219, 165, 140), (60, 20, 26)]
    for i, c in enumerate(sw):
        x0, x1 = i * H // 4, (i + 1) * H // 4; alb[H - band:, x0:x1] = c; orm[H - band:, x0:x1] = (255, 140 if i != 0 else 110, 0); nrm[H - band:, x0:x1] = (128, 128, 255)
    for k in ('body', 'head'):
        a, o, n = res[k]; Image.fromarray(a).save(f'{WORK}/{k}_basecolor.jpg', quality=88); Image.fromarray(o).save(f'{WORK}/{k}_orm.jpg', quality=86); n = np.clip(np.round((n.astype(np.int32) - 128) / 8.0) * 8 + 128, 0, 255).astype(np.uint8); Image.fromarray(n).save(f'{WORK}/{k}_normal.png', optimize=True)   # 5-bit levels keep the PNG small; flat (128,128,255) is preserved
    eye = np.zeros((128, 256, 3), np.uint8); vv = (np.arange(128)[:, None] / 127.0) * np.ones((1, 256))                       # eye atlas: v=1 (top rows) is the front pole
    pol = np.clip(vv, 0, 1)
    eye[:] = (246, 244, 240); iris = pol < 0.165; pup = pol < 0.075; ring = (pol >= 0.14) & (pol < 0.165)
    eye[iris] = (96, 58, 30); eye[ring] = (52, 30, 16); eye[pup] = (8, 6, 8); shade = np.clip(1 - np.abs(pol - 0.5) * 0.0, 0, 1)
    eye[pol > 0.72] = (232, 214, 210); Image.fromarray(eye).save(f'{WORK}/eyes_basecolor.jpg', quality=92)
    return res


# ======================================================================== assembly: head extras, rig, morphs, clips, export
BONES = {  # name: (parent, head, tail)   game coords (spec section 2: hips .86, knee .48, shoulder 1.30-1.36, head joint 1.57)
 'root': (None, (0, 0, 0), (0, 0.08, 0)), 'hips': ('root', (0, 0.86, 0), (0, 0.90, 0)), 'torso': ('hips', (0, 0.90, 0), (0, 1.40, 0)),
 'head': ('torso', (0, 1.57, 0.0), (0, 1.90, 0.0)), 'head_top': ('head', (0, 1.90, 0.0), (0, 1.95, 0.0)),
 'armL': ('torso', (0.28, 1.32, 0), (0.325, 1.03, 0)), 'foreL': ('armL', (0.325, 1.03, 0), (0.355, 0.76, 0.004)), 'handL': ('foreL', (0.355, 0.76, 0.004), (0.372, 0.57, 0.02)),
 'armR': ('torso', (-0.28, 1.32, 0), (-0.325, 1.03, 0)), 'foreR': ('armR', (-0.325, 1.03, 0), (-0.355, 0.76, 0.004)), 'handR': ('foreR', (-0.355, 0.76, 0.004), (-0.372, 0.57, 0.02)),
 'legL': ('hips', (0.118, 0.86, 0), (0.118, 0.48, 0.01)), 'shinL': ('legL', (0.118, 0.48, 0.01), (0.118, 0.11, 0.012)), 'footL': ('shinL', (0.118, 0.11, 0.012), (0.118, 0.06, 0.26)),
 'legR': ('hips', (-0.118, 0.86, 0), (-0.118, 0.48, 0.01)), 'shinR': ('legR', (-0.118, 0.48, 0.01), (-0.118, 0.11, 0.012)), 'footR': ('shinR', (-0.118, 0.11, 0.012), (-0.118, 0.06, 0.26)),
}
SEG = {k: v for k, v in BONES.items() if k not in ('root', 'head_top')}
SEG['hips'] = (None, (0, 0.80, 0), (0, 0.98, 0))
LEG_ONLY = ('hips', 'legL', 'legR', 'shinL', 'shinR', 'footL', 'footR')
def _smooth(w, F, region, it=10, lam=0.65):
    import scipy.sparse as sp
    n = len(w); e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]); A = sp.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)); A = ((A + A.T) > 0).astype(float).tocsr()
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1); wn = w / np.maximum(w.sum(1, keepdims=True), 1e-12)
    for _ in range(it): nb = (A @ wn) / deg[:, None]; wn[region] = (1 - lam) * wn[region] + lam * nb[region]
    return wn
def skin_weights(V, F, headmesh=False, ids=None):
    names = list(SEG); d = np.zeros((len(V), len(names)))
    for j, n in enumerate(names):
        a = np.array(SEG[n][1], float); b = np.array(SEG[n][2], float); ab = b - a; t = np.clip(((V - a) @ ab) / (ab @ ab), 0, 1); d[:, j] = np.linalg.norm(V - (a + t[:, None] * ab), axis=1)
    w = 1.0 / (d + 0.012) ** 4; x, y, z = V[:, 0], V[:, 1], V[:, 2]; col = {n: i for i, n in enumerate(names)}; ax = np.abs(x)
    def kill_rules(w):
        def kill(mask, bones):
            for bn in bones: w[mask, col[bn]] = 0
        if ids is not None and not headmesh:
            low = np.isin(ids, (S.L['jeans'], S.L['shoe'], S.L['sole']))
            kill(low, [n for n in names if n not in LEG_ONLY and n != 'torso'])
            tee = ids == S.L['tee']; kill(tee, ['foreL', 'foreR', 'handL', 'handR', 'legL', 'legR', 'shinL', 'shinR', 'footL', 'footR'])
            sh = ids == S.L['shirt']; kill(sh, ['legL', 'legR', 'shinL', 'shinR', 'footL', 'footR', 'handL', 'handR'])
            sk = ids == S.L['skin']; kill(sk, ['legL', 'legR', 'shinL', 'shinR', 'footL', 'footR'])
            kill((ax < 0.17) & (y > 0.9), ['armL', 'armR', 'foreL', 'foreR', 'handL', 'handR'])                         # chest/belly never follows the arms
            kill(~low & (y < 1.2) & (ax < 0.235), ['armL', 'armR', 'foreL', 'foreR', 'handL', 'handR'])
            kill(sh & (y < 0.98) & (ax > 0.17) & (ax < 0.24), ['foreL', 'foreR'])
            for sd, bl in (('L', ['armL', 'foreL', 'handL']), ('R', ['armR', 'foreR', 'handR'])):                      # garments follow an arm only inside the sleeve; the side seam / hem stays on the torso
                far = np.minimum(d[:, col['arm' + sd]], d[:, col['fore' + sd]]); fall = 1 - np.clip((far - 0.06) / 0.07, 0, 1); fall = fall * fall * (3 - 2 * fall)
                for bn in bl: w[(sh | tee), col[bn]] *= fall[(sh | tee)]
        kill(x < -0.05, ['armL', 'foreL', 'handL', 'legL', 'shinL', 'footL']); kill(x > 0.05, ['armR', 'foreR', 'handR', 'legR', 'shinR', 'footR'])
        kill(y > 1.30, ['legL', 'legR', 'shinL', 'shinR', 'footL', 'footR'])
        return w
    w = kill_rules(w)
    if not headmesh:
        pit = (y > 0.8) & (y < 1.43) & (ax > 0.08)
        w = _smooth(w, F, pit, it=28, lam=0.7); w = kill_rules(w)                                                         # blend skinning through the armpit / shoulder so the webbing doesn't stretch
    rad = np.hypot(x, z - 0.01); tj = 1 - np.clip((y - 1.36) / 0.11, 0, 1); tj = tj * tj * (3 - 2 * tj)       # neck: torso->head blend (head joint sits at 1.57)
    neck = (rad < 0.125) & (y > 1.30) & (y < 1.48) & (headmesh | (ids == S.L['skin']))
    if headmesh:
        top = y > 1.47; w[top] = 0; w[top, names.index('head')] = 1
        face = (~neck) & (y <= 1.47); w[face] = 0; w[face, names.index('head')] = 1                                 # jaw / chin ride with the head
    w[neck] = 0; w[neck, names.index('torso')] = tj[neck]; w[neck, names.index('head')] = 1 - tj[neck]
    idx = np.argsort(-w, 1)[:, :4]; out = []
    for i in range(len(V)):
        ws = w[i, idx[i]]
        if ws.sum() <= 1e-12: out.append([('torso', 1.0)]); continue
        ws = ws / ws.sum(); keep = ws > 0.03; ws = ws[keep] / ws[keep].sum(); out.append([(names[idx[i][k]], float(ws[k])) for k in np.where(keep)[0]])
    return out

def tooth(c, size, rot=0.0, sub=1):
    m = trimesh.creation.icosphere(subdivisions=sub); v = m.vertices * (np.array(size) / 2.0); ca, sa = math.cos(rot), math.sin(rot); v = v @ np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1]]).T + np.array(c); return v, m.faces
def lid_shell(c, r, rest_deg):
    V, F, _ = sphere_uv(c, r, 14, 7, 0.0, math.radians(112)); V = V[:, [0, 2, 1]]; F = F[:, ::-1]                    # pole -> +Y (reflection => flip winding)
    a = math.radians(-rest_deg); R = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]); return V @ R.T + np.array(c), F
def rotx(P, c, ang):
    ca, sa = math.cos(ang), math.sin(ang); R = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]]); return (P - c) @ R.T + c

def assemble_head(G):
    HV, HF, HUV, HN = G['HV'], G['HF'], G['HUV'], G['HN']; n0 = len(HV)
    V = [HV]; Fs = [HF]; UVs = [HUV]; mats = [np.zeros(len(HF), int)]; tag = [np.zeros(len(HV), int)]       # tags: 0 face/hair, 1 upper teeth, 2 lower teeth, 3 tongue, 4 lidL, 5 lidR, 6 eyeL, 7 eyeR
    def add(v, f, uv, mat, tg):
        off = sum(len(x) for x in V); V.append(v); Fs.append(f + off); UVs.append(uv); mats.append(np.full(len(f), mat)); tag.append(np.full(len(v), tg))
    H = 1024; band = 0.085; sw = lambda i: np.array([(i + 0.5) / 4.0, band * 0.5])
    def flatuv(f, i): return np.tile(sw(i), (len(f), 3, 1))
    arc = S.mouth_arc; hh = S.mouth_h
    rng = np.random.default_rng(3)
    zt = lambda x, k: 0.206 - k * (abs(x) / 0.12) ** 2
    ux = np.linspace(-0.097, 0.097, 8)
    for i, x in enumerate(ux):
        cen = 1.0 - abs(x) / 0.12; w_ = 0.029 + 0.004 * cen; h = 0.027 + 0.008 * cen; ytop = arc(x) + hh(x) + 0.004
        v, f = tooth([x, ytop - h / 2, zt(x, 0.05)], [w_, h, 0.017], rng.uniform(-0.07, 0.07) - 0.15 * x / 0.1, 1); add(v, f, flatuv(f, 0), 0, 1)
    for x in np.linspace(-0.066, 0.066, 6):
        h = 0.016; v, f = tooth([x, arc(x) - hh(x) + h / 2 - 0.002, zt(x, 0.08) - 0.006], [0.021, h, 0.012], rng.uniform(-0.04, 0.04), 0); add(v, f, flatuv(f, 0), 0, 2)
    v, f = tooth([0, arc(0) - hh(0) * 0.55, 0.14], [0.10, 0.02, 0.10], 0, 1); add(v, f, flatuv(f, 1), 0, 3)
    for s, tg, tg2 in ((1, 4, 6), (-1, 5, 7)):
        c = np.array([s * S.EYE[0], S.EYE[1], S.EYE[2]]); lv, lf = lid_shell(c, 0.0535, 60); add(lv, lf, flatuv(lf, 2), 0, tg)
        ev, ef, euv = sphere_uv(c, 0.0505, 16, 10); th = s * 0.11; ev = np.stack([ev[:, 0] * math.cos(th) + ev[:, 2] * math.sin(th), ev[:, 1], -ev[:, 0] * math.sin(th) + ev[:, 2] * math.cos(th)], 1) + c; add(ev, ef, euv[ef], 1, tg2)
    V = np.concatenate(V); F = np.concatenate(Fs); UV = np.concatenate(UVs); M = np.concatenate(mats); T = np.concatenate(tag)
    return V, F, UV, M, T, n0

def morph_deltas(V, T, n0, ids):
    """returns dict name -> (n,3) deltas (game coords). ids: layer id per head-mesh vertex (valid for T==0)"""
    x, y, z = V[:, 0], V[:, 1], V[:, 2]; n = len(V); face = (T == 0) & (ids != S.L['hair'])
    ss = lambda a, b, v: np.clip((v - a) / (b - a), 0, 1) ** 2 * (3 - 2 * np.clip((v - a) / (b - a), 0, 1)) if False else (lambda t: t * t * (3 - 2 * t))(np.clip((v - a) / (b - a), 0, 1))
    arc = S.mouth_arc(x)
    jw = ss(arc + 0.014, arc - 0.016, y) * ss(-0.03, 0.06, z) * (1 - ss(0.13, 0.19, np.abs(x))) * (y > 1.38) * face
    jw = np.where((T == 2) | (T == 3), 1.0 if True else 0, jw); jw = np.where(T == 3, 0.8, jw)
    mouthzone = face & (np.abs(x) < 0.17) & (np.abs(y - 1.48) < 0.09) & (z > 0.03); corner = ss(0.05, 0.12, np.abs(x)) * mouthzone * ss(1.40, 1.47, y) * (1 - ss(1.50, 1.56, y)) + 0 * x
    cmz = np.where((T == 1) | (T == 2) | (T == 3), ss(0.05, 0.1, np.abs(x)) * 0.0, 0.0)
    def D(): return np.zeros((n, 3))
    def jaw(a): d = D(); d[:, 1] = -0.042 * a * jw; d[:, 2] = -0.007 * a * jw; return d
    def smile(a, side=None):
        d = D(); w = corner * (1.0 if side is None else (x * side > 0)); d[:, 1] = 0.014 * a * w; d[:, 0] = np.sign(x) * 0.008 * a * w; return d
    def narrow(a):                                                                                          # purse: pull mouth region towards the centre + push forward
        d = D(); mz = (mouthzone | np.isin(T, (1, 2, 3))); w = mz * (1 - ss(0.10, 0.17, np.abs(x))); d[:, 0] = -x * 0.35 * a * w; d[:, 2] = 0.012 * a * w; return d
    def wide(a): d = D(); mz = (mouthzone | np.isin(T, (1, 2, 3))); w = mz * (1 - ss(0.10, 0.17, np.abs(x))); d[:, 0] = x * 0.14 * a * w; return d
    def lidrot(tg, deg):
        d = D(); sel = T == tg; c = np.array([S.EYE[0] * (1 if tg == 4 else -1), S.EYE[1], S.EYE[2]]); d[sel] = rotx(V[sel], c, math.radians(deg)) - V[sel]; return d
    def eyerot(deg):
        d = D()
        for tg, s in ((6, 1), (7, -1)): sel = T == tg; c = np.array([s * S.EYE[0], S.EYE[1], S.EYE[2]]); d[sel] = rotx(V[sel], c, math.radians(deg)) - V[sel]
        return d
    brow_zone = face & (z > 0.10) & (y > 1.625) & (y < 1.71) & (np.abs(x) < 0.19)
    def browUp(a, side=None): d = D(); w = brow_zone * (1.0 if side is None else (x * side > 0)); d[:, 1] = 0.014 * a * w; return d
    def browAng(a): d = D(); w = brow_zone; inner = 1 - ss(0.0, 0.16, np.abs(x)); d[:, 1] = (-0.016 * inner + 0.010 * (1 - inner)) * a * w; d[:, 0] = -x * 0.05 * a * w; return d
    def cheeks(a): d = D(); w = face * np.exp(-(((np.abs(x) - 0.11) / 0.05) ** 2 + ((y - 1.52) / 0.04) ** 2 + ((z - 0.12) / 0.08) ** 2)); d[:, 1] = 0.01 * a * w; return d
    open_ = lambda a: jaw(a); m = {}
    m['mouthOpen'] = jaw(0.9); m['mouthSmile'] = smile(1.0) + cheeks(0.6) + wide(0.4); m['mouthFrown'] = smile(-1.0) + jaw(-0.1)
    m['viseme_aa'] = jaw(1.0) + wide(0.1); m['viseme_oo'] = narrow(1.0) + jaw(0.4); m['viseme_ee'] = wide(0.9) + smile(0.5) + jaw(0.15)
    m['viseme_mbp'] = jaw(-1.25) + narrow(0.25); m['viseme_fv'] = jaw(-0.55) + wide(0.1)
    m['blinkL'] = lidrot(4, 80); m['blinkR'] = lidrot(5, 80); m['eyesWide'] = lidrot(4, -14) + lidrot(5, -14); m['eyesNarrow'] = lidrot(4, 38) + lidrot(5, 38)
    m['lookUp'] = eyerot(-14); m['lookDown'] = eyerot(14); m['browUp'] = browUp(1.0); m['browAngry'] = browAng(1.0)
    m['exp_happy'] = smile(0.9) + cheeks(1.0) + browUp(0.3) + lidrot(4, 18) + lidrot(5, 18) + jaw(0.1)
    m['exp_angry'] = browAng(1.0) + smile(-0.5) + jaw(0.15) + lidrot(4, 22) + lidrot(5, 22)
    m['exp_scared'] = browUp(1.0) + lidrot(4, -14) + lidrot(5, -14) + jaw(0.55) + wide(0.5) + smile(-0.3)
    m['exp_surprised'] = browUp(1.0) + lidrot(4, -14) + lidrot(5, -14) + jaw(0.75) + narrow(0.5)
    m['exp_smug'] = smile(0.9, 1) + smile(0.2, -1) + browUp(0.7, 1) + lidrot(4, 26) + lidrot(5, 26) + cheeks(0.4)
    m['exp_fall'] = jaw(1.0) + wide(0.35) + browUp(1.0) + lidrot(4, -14) + lidrot(5, -14)
    return m

# ------------------------------------------------------------------ animation clips (game-space Euler, mirrors the procedural rig's mappings)
J = ['torso', 'head', 'armR', 'armL', 'foreR', 'foreL', 'legR', 'legL', 'shinR', 'shinL']
def P0(): return dict(torso=(0, 0, 0), head=(0, 0, 0), armR=(0, 0, 0), armL=(0, 0, 0), foreR=(0, 0, 0), foreL=(0, 0, 0), legR=(0, 0, 0), legL=(0, 0, 0), shinR=(0, 0, 0), shinL=(0, 0, 0), hipDY=0.0, poseRX=0.0, poseDY=0.0)
def PS(**kw):
    p = P0()
    for k, v in kw.items(): p[k] = v if k in ('hipDY', 'poseRX', 'poseDY') else (tuple(v) if hasattr(v, '__len__') else (v, 0, 0))
    return p
def lerp(a, b, t):
    o = {}
    for k in a: o[k] = a[k] + (b[k] - a[k]) * t if isinstance(a[k], float) else tuple(a[k][i] + (b[k][i] - a[k][i]) * t for i in range(3))
    return o
ease = lambda t: t * t * (3 - 2 * min(max(t, 0), 1) * 0 - 2 * t) if False else (lambda u: u * u * (3 - 2 * u))(min(max(t, 0), 1))
TAU = 2 * math.pi
def pose_idle(t):
    b = math.sin(TAU * t / 2.0); return PS(torso=(b * 0.015, math.sin(TAU * t / 2.0 + 0.6) * 0.05, 0), head=(b * 0.03, math.sin(TAU * t / 2.0 + 1.2) * 0.15, 0), armR=(b * 0.03, 0, -0.1 - b * 0.02), armL=(-b * 0.03, 0, 0.1 + b * 0.02), foreR=-0.12, foreL=-0.12, hipDY=-0.004 * b)
def pose_run(t):
    w = TAU * t / 0.6; s, c = math.sin(w), math.cos(w)
    return PS(legR=-s * 0.75, legL=s * 0.75, shinR=max(0, c) * 1.2 + 0.15, shinL=max(0, -c) * 1.2 + 0.15, armR=(s * 0.7, 0, -0.12), armL=(-s * 0.7, 0, 0.12), foreR=-1.2, foreL=-1.2, torso=(0.16, s * 0.08, 0), head=-0.1, hipDY=abs(math.sin(w)) * 0.045 - 0.02)
AIR = PS(legR=-0.9, legL=-0.5, shinR=1.4, shinL=1.0, armR=(-0.4, 0, -1.1), armL=(-0.4, 0, 1.1), foreR=-0.6, foreL=-0.6, torso=0.05, head=-0.15, hipDY=0.03)
CROUCH = PS(legR=-0.85, legL=-0.85, shinR=1.5, shinL=1.5, torso=0.42, head=-0.25, armR=(0.55, 0, -0.15), armL=(0.55, 0, 0.15), foreR=-0.5, foreL=-0.5, hipDY=-0.2)
STAND = pose_run(0.0)
def pose_jump(t):
    if t < 0.18: return lerp(pose_idle(0), CROUCH, ease(t / 0.18))
    if t < 0.32: return lerp(CROUCH, AIR, ease((t - 0.18) / 0.14))
    return lerp(AIR, PS(legR=-0.8, legL=-0.45, shinR=1.3, shinL=0.95, armR=(-0.5, 0, -1.0), armL=(-0.5, 0, 1.0), foreR=-0.6, foreL=-0.6, torso=0.05, head=-0.15, hipDY=0.03), ease((t - 0.32) / 0.38))
SLIDE = PS(poseRX=-1.2, poseDY=0.12, legR=-0.35, legL=0.2, shinR=0.2, shinL=0.9, armR=(-1.0, 0, -0.45), armL=(-1.0, 0, 0.45), foreR=-0.5, foreL=-0.5, torso=0.25, head=0.55)
def pose_slide(t): return lerp(pose_run(0.15), SLIDE, ease(t / 0.2))
def pose_wave(t):
    return PS(armR=(0, 0, -2.6 + math.sin(TAU * 4 * t / 1.6) * 0.25), foreR=-0.4, torso=(0, 0, math.sin(TAU * t / 1.6) * 0.03), head=(0, math.sin(TAU * t / 1.6) * 0.2, 0.08), armL=(0.05, 0, 0.12))
def pose_cheer(t):
    b = abs(math.sin(math.pi * t / 0.4)); return PS(armR=(0, 0, -2.7 - b * 0.2), armL=(0, 0, 2.7 + b * 0.2), foreR=-0.3, foreL=-0.3, head=-0.2, legR=-0.1 * b, shinR=0.2 * b, hipDY=b * 0.07)
def pose_talk(t):
    return PS(armR=(-0.5, 0, -0.35 + math.sin(TAU * t / 2.0) * 0.15), foreR=-1.1 + math.sin(TAU * 2 * t / 2.0) * 0.25, armL=(0, 0, 0.15), head=(math.sin(TAU * 3 * t / 2.0) * 0.06, math.sin(TAU * t / 2.0) * 0.2, 0), torso=(0, math.sin(TAU * t / 2.0) * 0.08, 0))
DEF = PS(torso=0.45, head=0.55, armR=(-0.25, 0, -0.05), armL=(-0.25, 0, 0.05), foreR=-0.2, foreL=-0.2, legR=-0.2, shinR=0.4, hipDY=-0.06)
def pose_defeat(t):
    if t < 0.3: return lerp(pose_idle(0), lerp(DEF, PS(torso=0.6, head=0.7, hipDY=-0.09, armR=(-0.3, 0, -0.05), armL=(-0.3, 0, 0.05), foreR=-0.2, foreL=-0.2, legR=-0.2, shinR=0.4), 1.0), ease(t / 0.3))
    return lerp(lerp(DEF, PS(torso=0.6, head=0.7, hipDY=-0.09, armR=(-0.3, 0, -0.05), armL=(-0.3, 0, 0.05), foreR=-0.2, foreL=-0.2, legR=-0.2, shinR=0.4), 1.0), DEF, ease((t - 0.3) / 0.5))
CLIPS = {'Idle': (2.0, True, pose_idle), 'Run': (0.6, True, pose_run), 'Jump': (0.7, False, pose_jump), 'Slide': (0.35, False, pose_slide), 'Wave': (1.6, True, pose_wave), 'Cheer': (1.2, True, pose_cheer), 'Talk': (2.0, True, pose_talk), 'Defeat': (1.0, False, pose_defeat)}

def strip_scale_tracks(path):
    """spec: bones carry rotation/translation only - drop the exporter's constant scale channels"""
    import struct
    b = open(path, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + n]); rest = b[20 + n:]
    for a in j.get('animations', []): a['channels'] = [c for c in a['channels'] if c['target']['path'] != 'scale']
    # the exporter starts every clip one frame late (first key at 1/30 s); shift to t=0 so Run is exactly 0.60 s and the loop closes without a held frame
    ins = sorted({s['input'] for a in j.get('animations', []) for s in a['samplers']}); binb = bytearray(rest)
    for i in ins:
        ac = j['accessors'][i]; bvw = j['bufferViews'][ac['bufferView']]; off = 8 + bvw.get('byteOffset', 0) + ac.get('byteOffset', 0)
        import numpy as _np
        arr = _np.frombuffer(bytes(binb[off:off + 4 * ac['count']]), '<f4').copy() - _np.float32(1 / 30); arr = _np.maximum(arr, 0).astype('<f4'); binb[off:off + 4 * ac['count']] = arr.tobytes(); ac['min'] = [float(arr.min())]; ac['max'] = [float(arr.max())]
    rest = bytes(binb)
    js = json.dumps(j, separators=(',', ':')).encode(); js += b' ' * ((4 - len(js) % 4) % 4)
    out = struct.pack('<4sII', b'glTF', 2, 12 + 8 + len(js) + len(rest)) + struct.pack('<I4s', len(js), b'JSON') + js + rest; open(path, 'wb').write(out)

def finalize(G, res):
    clear(); scn = bpy.context.scene; scn.render.fps = 30
    # ---- armature
    arm_d = bpy.data.armatures.new('SayedArmature'); arm = bpy.data.objects.new('Sayed', arm_d); scn.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm; arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); eb = {}
    HV0 = G['HV']; top_y = float(HV0[:, 1].max()); BONES['head_top'] = ('head', (0, top_y - 0.004, 0.0), (0, top_y + 0.04, 0.0)); BONES['head'] = ('torso', (0, 1.57, 0.0), (0, top_y - 0.004, 0.0))
    for n, (par, h, t) in BONES.items():
        b = arm_d.edit_bones.new(n); b.head = g2b(h); b.tail = g2b(t); eb[n] = b
        if par: b.parent = eb[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    # ---- materials
    def mat(name, base, orm=None, nrm=None, rough=0.8):
        m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes['Principled BSDF']; bs.inputs['Roughness'].default_value = rough
        t = nt.nodes.new('ShaderNodeTexImage'); t.image = bpy.data.images.load(base); nt.links.new(t.outputs['Color'], bs.inputs['Base Color'])
        if orm:
            t2 = nt.nodes.new('ShaderNodeTexImage'); t2.image = bpy.data.images.load(orm); t2.image.colorspace_settings.name = 'Non-Color'; sep = nt.nodes.new('ShaderNodeSeparateColor')
            nt.links.new(t2.outputs['Color'], sep.inputs['Color']); nt.links.new(sep.outputs['Green'], bs.inputs['Roughness']); nt.links.new(sep.outputs['Blue'], bs.inputs['Metallic'])
            grp = bpy.data.node_groups.new('glTF Material Output', 'ShaderNodeTree'); grp.interface.new_socket('Occlusion', in_out='INPUT', socket_type='NodeSocketFloat')
            gn = nt.nodes.new('ShaderNodeGroup'); gn.node_tree = grp; nt.links.new(sep.outputs['Red'], gn.inputs['Occlusion'])
        if nrm:
            t3 = nt.nodes.new('ShaderNodeTexImage'); t3.image = bpy.data.images.load(nrm); t3.image.colorspace_settings.name = 'Non-Color'; nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 1.0
            nt.links.new(t3.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
        m.use_backface_culling = True
        return m
    mb = mat('MAT_Sayed_Body', f'{WORK}/body_basecolor.jpg', f'{WORK}/body_orm.jpg', f'{WORK}/body_normal.png'); mh = mat('MAT_Sayed_Head', f'{WORK}/head_basecolor.jpg', f'{WORK}/head_orm.jpg', f'{WORK}/head_normal.png')
    me_ = mat('MAT_Sayed_Eyes', f'{WORK}/eyes_basecolor.jpg', None, None, 0.12)
    def make(name, V, F, UV, mats_idx, matlist, weights, shapes=None):
        F = np.asarray(F); key = np.sort(F, 1); _, first = np.unique(key, axis=0, return_index=True); ok = np.zeros(len(F), bool); ok[first] = True; ok &= (key[:, 0] != key[:, 1]) & (key[:, 1] != key[:, 2])
        F, UV, mats_idx = F[ok], np.asarray(UV)[ok], np.asarray(mats_idx)[ok]
        if (~ok).any(): print(name, 'dropped', int((~ok).sum()), 'duplicate/degenerate faces')
        me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in g2b(V)], [], [tuple(f) for f in F]); me.update()
        uvl = me.uv_layers.new(name='UVMap')
        for pi, p in enumerate(me.polygons):
            for k, l in enumerate(p.loop_indices): uvl.data[l].uv = (float(UV[pi, k, 0]), float(UV[pi, k, 1]))
        for m in matlist: me.materials.append(m)
        me.polygons.foreach_set('material_index', np.asarray(mats_idx, np.int32)); me.polygons.foreach_set('use_smooth', np.ones(len(F), bool))
        ob = bpy.data.objects.new(name, me); scn.collection.objects.link(ob); ob.parent = arm
        for bn in SEG: ob.vertex_groups.new(name=bn)
        for i, ws in enumerate(weights):
            for bn, w in ws: ob.vertex_groups[bn].add([i], w, 'REPLACE')
        md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
        if shapes:
            ob.shape_key_add(name='Basis', from_mix=False); base = g2b(V)
            for nm, d in shapes.items():
                k = ob.shape_key_add(name=nm, from_mix=False); k.data.foreach_set('co', (base + g2b(d)).astype(np.float32).ravel()); k.value = 0.0
        return ob
    # ---- body
    wB = skin_weights(G['BV'], G['BF'], ids=S.surface(G['BV'])[1]); make('Sayed_Body', G['BV'], G['BF'], G['BUV'], np.zeros(len(G['BF']), int), [mb], wB)
    # ---- head (+ teeth, tongue, lids, eyes, morph targets)
    V, F, UV, M, T, n0 = assemble_head(G); ids = np.zeros(len(V), int); ids[:n0] = S.surface(V[:n0])[1]
    wH = skin_weights(V, F, headmesh=True)
    for i in range(n0, len(V)): wH[i] = [('head', 1.0)]
    morphs = morph_deltas(V, T, n0, ids); make('Sayed_Head', V, F, UV, M, [mh, me_], wH, morphs)
    print('head tris', len(F), 'verts', len(V), 'morphs', len(morphs), 'body tris', len(G['BF']))
    # ---- pose + clips
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='POSE')
    rest = {b.name: b.matrix_local.to_3x3() for b in arm_d.bones}; M_ = mathutils.Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
    for pb in arm.pose.bones: pb.rotation_mode = 'QUATERNION'
    ad = arm.animation_data_create()
    def qof(joint, e):
        R = mathutils.Euler(e, 'ZYX').to_matrix(); Rb = M_ @ R @ M_.transposed(); rr = rest[joint]; return (rr.inverted() @ Rb @ rr).to_quaternion()
    for name, (dur, loop, fn) in CLIPS.items():
        act = bpy.data.actions.new(name); ad.action = act; nf = int(round(dur * 30))
        for f in range(nf + 1):
            t = (f / 30.0) if (loop is False or f < nf) else 0.0
            if loop and f == nf: t = 0.0
            if not loop: t = min(f / 30.0, dur)
            p = fn(t)
            for jn in J:
                pb = arm.pose.bones[jn]; pb.rotation_quaternion = qof(jn, p[jn]); pb.keyframe_insert('rotation_quaternion', frame=f + 1)
            pb = arm.pose.bones['hips']; v = mathutils.Vector((0, 0, p['hipDY'])); pb.location = rest['hips'].inverted() @ v; pb.keyframe_insert('location', frame=f + 1)
            pr = arm.pose.bones['root']; pr.rotation_quaternion = qof('root', (p['poseRX'], 0, 0)); pr.keyframe_insert('rotation_quaternion', frame=f + 1)
            pr.location = rest['root'].inverted() @ mathutils.Vector((0, 0, p['poseDY'])); pr.keyframe_insert('location', frame=f + 1)
        tr = ad.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, 1, act); ad.action = None
    for pb in arm.pose.bones: pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    bpy.ops.object.mode_set(mode='OBJECT')
    # ---- export
    for o in bpy.data.objects: o.select_set(True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', use_selection=True, export_yup=True, export_apply=False, export_animations=True, export_animation_mode='NLA_TRACKS',
        export_optimize_animation_size=True, export_skins=True, export_morph=True, export_morph_normal=True, export_image_format='AUTO', export_cameras=False, export_lights=False, export_extras=False)
    strip_scale_tracks(OUT); print('exported', OUT, os.path.getsize(OUT))

if __name__ == '__main__':
    import sys as _s
    if '--reuse' in _s.argv and os.path.exists(f'{WORK}/geo.npz') and os.path.exists(f'{WORK}/head_normal.png'):
        G = dict(np.load(f'{WORK}/geo.npz')); res = None
    else:
        clear(); G = build_all(); np.savez(f'{WORK}/geo.npz', **G); res = bake_textures(G)
    finalize(G, res)
