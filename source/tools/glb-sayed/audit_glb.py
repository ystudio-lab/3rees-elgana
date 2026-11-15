"""Static audit of sayed.glb against SAYED-GLB-SPEC (no rendering). python audit_glb.py [path]"""
import json, struct, sys, numpy as np
p = sys.argv[1] if len(sys.argv) > 1 else '../../assets/characters/sayed/sayed.glb'
b = open(p, 'rb').read(); n = struct.unpack('<I', b[12:16])[0]; j = json.loads(b[20:20 + n]); bin_ = b[20 + n + 8:]
def acc(i):
    a = j['accessors'][i]; v = j['bufferViews'][a['bufferView']]; ct = {5126: 'f4', 5123: 'u2', 5125: 'u4', 5121: 'u1', 5120: 'i1', 5122: 'i2'}[a['componentType']]; nc = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}[a['type']]
    off = v.get('byteOffset', 0) + a.get('byteOffset', 0); arr = np.frombuffer(bin_, dtype=ct, count=a['count'] * nc, offset=off).reshape(a['count'], nc)
    if 'byteStride' in v and v['byteStride'] != nc * np.dtype(ct).itemsize:
        st = v['byteStride']; arr = np.stack([np.frombuffer(bin_, dtype=ct, count=nc, offset=off + k * st) for k in range(a['count'])])
    return arr
R = {}; R['file_MB'] = round(len(b) / 1048576, 3); R['file_bytes'] = len(b)
tris = 0; names = []
for m, nd in [(j['meshes'][nd['mesh']], nd) for nd in j['nodes'] if 'mesh' in nd]:
    for pr in m['primitives']: tris += j['accessors'][pr['indices']]['count'] // 3
    names.append((nd['name'], len(m['primitives']), len(m['primitives'][0].get('targets', []))))
R['triangles'] = tris; R['meshes'] = names; R['materials'] = [m['name'] for m in j['materials']]; R['draw_calls'] = sum(x[1] for x in names)
R['images'] = [(im['mimeType']) for im in j['images']]
# bones / hierarchy
nodes = j['nodes']; par = {}
for i, nd in enumerate(nodes):
    for c in nd.get('children', []): par[c] = i
def world(i):
    t = np.zeros(3); k = i
    while k is not None:
        nd = nodes[k]; t = t + np.array(nd.get('translation', [0, 0, 0])) if 'rotation' not in nd or True else t; k = par.get(k)
    return t
bones = [nd['name'] for nd in nodes if 'mesh' not in nd and nd['name'] not in ('Sayed',) and 'camera' not in nd]
R['bones'] = bones; R['bone_count'] = len(bones)
need = 'root hips torso head armL foreL armR foreR legL shinL legR shinR'.split(); R['required_bones_ok'] = all(n in bones for n in need)
R['joint_world_y'] = {nd['name']: round(float(world(i)[1]), 3) for i, nd in enumerate(nodes) if nd['name'] in ('hips', 'torso', 'head', 'head_top', 'legL', 'shinL', 'armL', 'foreL')}
R['root_nodes'] = [nodes[i]['name'] for i in j['scenes'][0]['nodes']]
# geometry extents (skinned bind pose == rest)
allp = np.concatenate([acc(pr['attributes']['POSITION']) for m in j['meshes'] for pr in m['primitives']]); R['bbox_min'] = allp.min(0).round(3).tolist(); R['bbox_max'] = allp.max(0).round(3).tolist(); R['height_m'] = round(float(allp[:, 1].max() - allp[:, 1].min()), 3)
# influences
mx = 0; wsum = []
for m in j['meshes']:
    for pr in m['primitives']:
        w = acc(pr['attributes']['WEIGHTS_0']); mx = max(mx, int((w > 1e-4).sum(1).max())); wsum.append(float(np.abs(w.sum(1) - 1).max()))
R['max_influences'] = mx; R['max_weight_sum_error'] = round(max(wsum), 5)
# morphs
for m in j['meshes']:
    if m.get('extras', {}).get('targetNames'): R['morph_count'] = len(m['extras']['targetNames']); R['morphs'] = m['extras']['targetNames']; R['morph_has_normals'] = all('NORMAL' in t for t in m['primitives'][0]['targets'])
# clips
R['clips'] = {a['name']: dict(channels=len(a['channels']), paths=sorted({c['target']['path'] for c in a['channels']}), duration=round(max(float(acc(s['input']).max()) for s in a['samplers']), 3)) for a in j['animations']}
R['animation_scale_tracks'] = sum(1 for a in j['animations'] for c in a['channels'] if c['target']['path'] == 'scale')
R['viseme_or_mouth_keyed_in_clips'] = any(c['target']['path'] == 'weights' for a in j['animations'] for c in a['channels'])
# UV sanity: overlap = fraction of texels covered by >1 triangle (rasterised at 512)
def uv_overlap(prim_idx):
    pr = j['meshes'][prim_idx]['primitives'][0]; uv = acc(pr['attributes']['TEXCOORD_0']).astype(float); f = acc(pr['indices']).reshape(-1, 3).astype(int); S = 512; cnt = np.zeros((S, S), np.int16)
    for t in f:
        q = uv[t] * S; mn = np.floor(q.min(0)).astype(int); mxx = np.ceil(q.max(0)).astype(int)
        if (mxx - mn).max() > 80: continue
        xs, ys = np.meshgrid(np.arange(mn[0], mxx[0] + 1), np.arange(mn[1], mxx[1] + 1)); pt = np.stack([xs.ravel() + .5, ys.ravel() + .5], 1)
        a, b2, c = q; d = (b2[1] - c[1]) * (a[0] - c[0]) + (c[0] - b2[0]) * (a[1] - c[1])
        if abs(d) < 1e-9: continue
        l1 = ((b2[1] - c[1]) * (pt[:, 0] - c[0]) + (c[0] - b2[0]) * (pt[:, 1] - c[1])) / d; l2 = ((c[1] - a[1]) * (pt[:, 0] - c[0]) + (a[0] - c[0]) * (pt[:, 1] - c[1])) / d; ok = (l1 > 0.05) & (l2 > 0.05) & (1 - l1 - l2 > 0.05)
        xx, yy = np.clip(pt[ok, 0].astype(int), 0, S - 1), np.clip(pt[ok, 1].astype(int), 0, S - 1); cnt[yy, xx] += 1
    cov = cnt > 0; return dict(coverage=round(float(cov.mean()), 3), overlap_fraction=round(float((cnt > 1).sum() / max(cov.sum(), 1)), 4))
R['uv_body'] = uv_overlap(0); R['uv_head_primitive0'] = uv_overlap(1)
print(json.dumps(R, indent=1))
