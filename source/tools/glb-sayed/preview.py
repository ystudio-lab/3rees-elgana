import numpy as np, sys, trimesh
from PIL import Image
PAL = {0:(219,165,140),1:(22,20,26),2:(31,157,107),3:(176,160,122),4:(52,66,98),5:(150,155,170),6:(235,235,235)}
def load(name):
    d = np.load(f'/tmp/sayed_{name}.npz'); m = trimesh.Trimesh(d['v'], d['f'], process=False); return d['v'], m.vertex_normals, d['ids']
def render(parts, yaw, H=640, y0=0.0, y1=2.0, cx=0.0, out='/tmp/p.png', zoom_win=None):
    W = int(H * 0.8); img = np.full((H, W, 3), 205, np.uint8); zb = np.full((H, W), -1e9)
    c, s = np.cos(yaw), np.sin(yaw); L = np.array([0.4, 0.6, 0.7]); L /= np.linalg.norm(L)
    scale = H / (y1 - y0)
    for v, n, ids, splat in parts:
        x = v[:, 0] * c + v[:, 2] * s; z = -v[:, 0] * s + v[:, 2] * c; nx = n[:, 0] * c + n[:, 2] * s; nz = -n[:, 0] * s + n[:, 2] * c
        nn = np.stack([nx, n[:, 1], nz], 1); lit = np.clip(nn @ L, 0, 1) * 0.75 + 0.3
        px = ((x - cx) * scale + W / 2).astype(int); py = (H - (v[:, 1] - y0) * scale).astype(int)
        col = np.array([PAL[i] for i in ids]) * lit[:, None]
        for dx in range(-splat, splat + 1):
            for dy in range(-splat, splat + 1):
                X, Y = px + dx, py + dy; ok = (X >= 0) & (X < W) & (Y >= 0) & (Y < H)
                o = np.argsort(z[ok]); X, Y, Z, C = X[ok][o], Y[ok][o], z[ok][o], col[ok][o]
                m = Z > zb[Y, X]; 
                # last write wins in numpy fancy assign -> sorted ascending so nearest last
                sel = np.where(Z > zb[Y, X])[0]; zb[Y[sel], X[sel]] = Z[sel]; img[Y[sel], X[sel]] = C[sel].astype(np.uint8)
    Image.fromarray(img).save(out)
if __name__ == '__main__':
    import os
    parts = [(*load('body'), 2)]
    if os.path.exists('/tmp/sayed_head.npz'): parts.append((*load('head'), 1))
    imgs = []
    for k, yaw in enumerate([0, np.pi / 2, 0.6]): render(parts, yaw, out=f'/tmp/pv{k}.png'); imgs.append(Image.open(f'/tmp/pv{k}.png'))
    W = sum(i.width for i in imgs); sheet = Image.new('RGB', (W, imgs[0].height)); x = 0
    for i in imgs: sheet.paste(i, (x, 0)); x += i.width
    sheet.save('/tmp/preview_body.png')
