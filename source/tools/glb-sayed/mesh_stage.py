import numpy as np, sys, time
from skimage import measure
sys.path.insert(0, '.')
import sdf_sayed as S
def grid(lo, hi, res):
    ax = [np.arange(l, h + res, res) for l, h in zip(lo, hi)]; return ax
def run(lo, hi, res, name):
    ax = grid(lo, hi, res); nx, ny, nz = map(len, ax); vol = np.zeros((nx, ny, nz), np.float32); t0 = time.time()
    for i in range(nx):                                          # slab by slab (keeps curl culling tight)
        X, Y, Z = np.meshgrid(ax[0][i:i + 1], ax[1], ax[2], indexing='ij'); P = np.stack([X.ravel(), Y.ravel(), Z.ravel()], 1)
        vol[i] = S.surface(P)[0].reshape(ny, nz)
    v, f, n, _ = measure.marching_cubes(vol, 0.0, spacing=(res, res, res)); v += np.array([ax[0][0], ax[1][0], ax[2][0]])
    _, ids, D = S.surface(v)
    print(name, 'verts', len(v), 'tris', len(f), 'sec %.0f' % (time.time() - t0), flush=True)
    np.savez(f'/tmp/sayed_{name}.npz', v=v, f=f, ids=ids)
if __name__ == '__main__':
    which = sys.argv[1]
    if which == 'body': run((-0.5, 0.0, -0.32), (0.5, 1.44, 0.42), 0.005, 'body')
    else: run((-0.3, 1.38, -0.3), (0.3, 1.98, 0.33), 0.0055, 'head')
