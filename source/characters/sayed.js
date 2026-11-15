/*
 * AREES EL GANNAH — Sayed Felfel, C1 blockout (procedural Three.js).
 * Classic script (works from file://). Exposes window.AreesCharacters.createSayed(THREE).
 *
 * Proportions are measured from the approved sheet crops in
 * assets/references/3d-production/sayed/ (front 325x525, side 205x525; feet at y=502 px,
 * hair top at y=15 px). Pixel -> world: 487 px = 1.8 units (the gameplay hitbox height).
 *   FX(px) front-view x, FY(py) height from the ground, FZ(pxSide) side-view depth.
 * The model faces +Z (glTF forward), feet at y=0.
 *
 * Parts are attached to a joint hierarchy (hips/spine/chest/neck/head, arms, legs) so they
 * can be rigged later. C1 = blockout: no skinning, textures or animation yet.
 */
(function () {
  'use strict';

  function createSayed(THREE, opts = {}) {
    const S = 1.8 / 487;                       // world units per reference pixel
    const FX = (px) => (px - 162) * S;
    const FY = (py) => (502 - py) * S;
    const FZ = (pz) => (pz - 96) * S;
    const V = (x, y, z) => new THREE.Vector3(FX(x), FY(y), FZ(z));
    const smooth = (e0, e1, x) => { const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t); };
    let seed = opts.seed || 7;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

    // ---------------- Materials (colours sampled from the sheet, lit for the game) ----------------
    const M = (color, extra = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.8, metalness: 0, ...extra });
    const mat = {
      skin: M(0xd9a088, { roughness: 0.6 }),
      skinFace: M(0xffffff, { roughness: 0.6, vertexColors: true }),
      nose: M(0xd27f70, { roughness: 0.5 }),
      tshirt: M(0x2e9a78, { roughness: 0.9 }),
      khaki: M(0xb3a68c, { roughness: 0.92, side: THREE.DoubleSide }),
      khakiEdge: M(0x958a72, { roughness: 0.95 }),
      denim: M(0x30364a, { roughness: 0.95 }),
      denimCuff: M(0x4a5168, { roughness: 0.95 }),
      shoe: M(0xffffff, { roughness: 0.75, vertexColors: true }),
      sole: M(0xe9e9ec, { roughness: 0.7 }),
      lace: M(0xf4f4f4, { roughness: 0.7 }),
      hair: M(0x1b1918, { roughness: 0.55 }),
      eyeWhite: M(0xf6f3ee, { roughness: 0.25 }),
      iris: M(0x4a3226, { roughness: 0.3 }),
      pupil: M(0x0d0b0b, { roughness: 0.2 }),
      mouth: M(0x3b1517, { roughness: 0.6, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 }),
      teeth: M(0xf3efe4, { roughness: 0.35 }),
      cord: M(0x2a2420, { roughness: 0.6 }),
      pendant: M(0xc7a35a, { roughness: 0.35, metalness: 0.6 })
    };

    // ---------------- Joint hierarchy (model-space positions in reference px) ----------------
    const root = new THREE.Group(); root.name = 'Sayed';
    function joint(name, parent, px) {
      const g = new THREE.Group(); g.name = name;
      g.userData.model = px ? V(...px) : new THREE.Vector3();
      const pm = parent ? parent.userData.model : new THREE.Vector3();
      g.position.copy(g.userData.model).sub(pm);
      (parent || root).add(g);
      return g;
    }
    root.userData.model = new THREE.Vector3();
    const J = {};
    J.hips = joint('hips', null, [162, 325, 96]);
    J.spine = joint('spine', J.hips, [162, 280, 98]);
    J.chest = joint('chest', J.spine, [162, 200, 98]);
    J.neck = joint('neck', J.chest, [162, 140, 92]);
    J.head = joint('head', J.neck, [162, 120, 92]);
    // Character's right side is screen-left in the front view.
    J.upperArm_R = joint('upperArm_R', J.chest, [95, 158, 96]);
    J.forearm_R = joint('forearm_R', J.upperArm_R, [60, 250, 108]);
    J.hand_R = joint('hand_R', J.forearm_R, [45, 318, 116]);
    J.upperArm_L = joint('upperArm_L', J.chest, [229, 158, 96]);
    J.forearm_L = joint('forearm_L', J.upperArm_L, [264, 250, 108]);
    J.hand_L = joint('hand_L', J.forearm_L, [279, 318, 116]);
    J.thigh_R = joint('thigh_R', J.hips, [130, 335, 98]);
    J.shin_R = joint('shin_R', J.thigh_R, [122, 400, 92]);
    J.foot_R = joint('foot_R', J.shin_R, [116, 462, 86]);
    J.thigh_L = joint('thigh_L', J.hips, [194, 335, 98]);
    J.shin_L = joint('shin_L', J.thigh_L, [202, 400, 92]);
    J.foot_L = joint('foot_L', J.shin_L, [208, 462, 86]);

    const parts = {};
    // Geometry is authored in model space; re-centre it on the joint it belongs to.
    function add(jointGroup, name, geometry, material) {
      const m = geometry.isObject3D ? geometry : new THREE.Mesh(geometry, material);
      m.name = name;
      if (!geometry.isObject3D) geometry.translate(-jointGroup.userData.model.x, -jointGroup.userData.model.y, -jointGroup.userData.model.z);
      else m.position.sub(jointGroup.userData.model);
      m.castShadow = true; m.receiveShadow = true;
      jointGroup.add(m);
      (parts[name.split('_')[0]] ||= []).push(m);
      return m;
    }

    // ---------------- Loft: smooth shells from measured rings ----------------
    // ctrl: [{p:[x,y,z] px, w: half-width px, d: half-depth px}], angle 0 = local front (+D).
    function catmull1D(vals, u) {
      const n = vals.length - 1, f = u * n, i = Math.min(n - 1, Math.floor(f)), t = f - i;
      const p0 = vals[Math.max(0, i - 1)], p1 = vals[i], p2 = vals[i + 1], p3 = vals[Math.min(n, i + 2)];
      return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
    }
    function loft(ctrl, o = {}) {
      const seg = o.seg || 24, sub = o.sub || 5, ex = o.exp || 2, gap = o.gap || null;
      const pts = ctrl.map(c => V(...c.p));
      const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
      const W = ctrl.map(c => c.w * S), D = ctrl.map(c => c.d * S);
      const nR = (ctrl.length - 1) * sub + 1;
      const full = !gap, nV = full ? seg : seg + 1;
      const pos = [], uv = [], idx = [], rings = [];
      const up = new THREE.Vector3(0, 1, 0), fwd = new THREE.Vector3(0, 0, 1);
      for (let i = 0; i < nR; i++) {
        const u = i / (nR - 1);
        const C = curve.getPoint(u), T = curve.getTangent(u);
        const ref = Math.abs(T.dot(fwd)) > 0.9 ? up : fwd;
        let Wd = new THREE.Vector3().crossVectors(T, ref).normalize();
        if (Wd.x < 0 && ref === fwd) Wd.negate();            // keep "width" axis pointing +X
        let Dd = new THREE.Vector3().crossVectors(Wd, T).normalize();
        if (ref === fwd && Dd.z < 0) Dd.negate();             // keep "depth" axis pointing forward
        if (ref === up && Dd.y < 0) Dd.negate();
        const w = catmull1D(W, u), d = catmull1D(D, u);
        const g = gap ? gap(u) : 0;
        rings.push({ C, Wd, Dd, w, d, g });
        for (let j = 0; j < nV; j++) {
          const a = full ? (j / seg) * Math.PI * 2 : g + (j / seg) * (Math.PI * 2 - 2 * g);
          const s = Math.sin(a), c = Math.cos(a);
          const sx = Math.sign(s) * Math.pow(Math.abs(s), 2 / ex), sz = Math.sign(c) * Math.pow(Math.abs(c), 2 / ex);
          const P = C.clone().addScaledVector(Wd, w * sx).addScaledVector(Dd, d * sz);
          pos.push(P.x, P.y, P.z); uv.push(j / seg, u);
        }
      }
      for (let i = 0; i < nR - 1; i++) for (let j = 0; j < (full ? seg : seg); j++) {
        const a = i * nV + j, b = i * nV + ((j + 1) % nV), c = (i + 1) * nV + j, d = (i + 1) * nV + ((j + 1) % nV);
        if (!full && j === seg) continue;
        idx.push(a, c, b, b, c, d);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
      geo.setIndex(idx); geo.computeVertexNormals();
      // Orientation check: normals must point away from the ring centre.
      const k = Math.floor(nR / 2) * nV + Math.floor(nV / 4), n = geo.attributes.normal, p = geo.attributes.position;
      const out = new THREE.Vector3(p.getX(k), p.getY(k), p.getZ(k)).sub(rings[Math.floor(nR / 2)].C);
      if (out.dot(new THREE.Vector3(n.getX(k), n.getY(k), n.getZ(k))) < 0) {
        for (let t = 0; t < idx.length; t += 3) { const tmp = idx[t + 1]; idx[t + 1] = idx[t + 2]; idx[t + 2] = tmp; }
        geo.setIndex(idx); geo.computeVertexNormals();
      }
      if (o.caps && full) {                                   // close both ends with a fan
        const P = geo.attributes.position.array, I = Array.from(geo.index.array), arr = Array.from(P);
        const cap = (ri, other) => {
          const c = arr.length / 3, C = rings[ri].C; arr.push(C.x, C.y, C.z);
          const out = C.clone().sub(rings[other].C), A = new THREE.Vector3(), B = new THREE.Vector3();
          for (let j = 0; j < nV; j++) {
            let a = ri * nV + j, b = ri * nV + ((j + 1) % nV);
            A.set(arr[a * 3], arr[a * 3 + 1], arr[a * 3 + 2]).sub(C); B.set(arr[b * 3], arr[b * 3 + 1], arr[b * 3 + 2]).sub(C);
            if (A.clone().cross(B).dot(out) < 0) [a, b] = [b, a];
            I.push(c, a, b);
          }
        };
        cap(0, 1); cap(nR - 1, nR - 2);
        uv.push(0.5, 0, 0.5, 1);
        geo.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3));
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
        geo.setIndex(I); geo.computeVertexNormals();
      }
      geo.userData.rings = rings;
      return geo;
    }
    // Point on a loft's front surface at world (x, y) — used to place details on clothing.
    function onLoft(geo, xw, yw, lift = 0) {
      const rings = geo.userData.rings;
      let best = rings[0]; for (const r of rings) if (Math.abs(r.C.y - yw) < Math.abs(best.C.y - yw)) best = r;
      const s = Math.max(-0.98, Math.min(0.98, (xw - best.C.x) / best.w)), a = Math.asin(s);
      const P = best.C.clone().addScaledVector(best.Wd, best.w * Math.sin(a)).addScaledVector(best.Dd, best.d * Math.cos(a));
      const N = best.Wd.clone().multiplyScalar(Math.sin(a) / best.w).addScaledVector(best.Dd, Math.cos(a) / best.d).normalize();
      P.y = yw; P.addScaledVector(N, lift);
      return { P, N };
    }
    function orientTo(mesh, P, N) { mesh.position.copy(P); mesh.lookAt(P.clone().add(N)); }

    // ---------------- Head (sculpted sphere: wide cheeks and jaw, rounded crown) ----------------
    const HEAD = { cx: 162, cy: 90, cz: 94, rx: 41, ry: 51, rz: 46 };
    const widthAt = (uy) => (0.9 + 0.2 * smooth(0.7, -0.35, uy)) * (1 - 0.32 * smooth(-0.68, -1.0, uy));
    const surfaceZ = (px, py) => {                       // front surface depth (side px) at front-view (px,py)
      const uy = (HEAD.cy - py) / HEAD.ry, ux = (px - HEAD.cx) / (HEAD.rx * widthAt(uy));
      const r = 1 - ux * ux - uy * uy; return r <= 0 ? HEAD.cz : HEAD.cz + HEAD.rz * Math.sqrt(r);
    };
    const onFace = (px, py, lift = 0) => V(px, py, surfaceZ(px, py) + lift);
    const faceNormal = (px, py) => onFace(px, py, 1).sub(V(HEAD.cx, HEAD.cy, HEAD.cz)).normalize();
    {
      const g = new THREE.SphereGeometry(1, 48, 36), p = g.attributes.position, col = [];
      const base = new THREE.Color(0xd9a088), blush = new THREE.Color(0xd07a6c), stubble = new THREE.Color(0x9f8378), c = new THREE.Color();
      for (let i = 0; i < p.count; i++) {
        const ux = p.getX(i), uy = p.getY(i), uz = p.getZ(i), w = widthAt(uy);
        p.setXYZ(i, FX(HEAD.cx) + ux * HEAD.rx * w * S, FY(HEAD.cy) + uy * HEAD.ry * S, FZ(HEAD.cz) + uz * HEAD.rz * S);
        c.copy(base);
        const ck = Math.exp(-(((Math.abs(ux) - 0.55) ** 2) / 0.03 + ((uy + 0.25) ** 2) / 0.03)) * smooth(0.2, 0.7, uz);
        c.lerp(blush, 0.45 * ck);
        c.lerp(stubble, 0.35 * smooth(-0.45, -0.8, uy) * smooth(-0.2, 0.4, uz));   // shaved jaw shadow
        col.push(c.r, c.g, c.b);
      }
      g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.computeVertexNormals();
      add(J.head, 'head', g, mat.skinFace);
    }
    // Nose: big round bulb + bridge (the character's signature).
    {
      const bulb = new THREE.SphereGeometry(15 * S, 28, 20); bulb.scale(1, 0.9, 1);
      const P = onFace(161, 98, 4); bulb.translate(P.x, P.y, P.z);
      add(J.head, 'nose_bulb', bulb, mat.nose);
      const bridge = new THREE.CapsuleGeometry(6 * S, 14 * S, 6, 12);
      const B = onFace(161, 82, 1); bridge.rotateX(-0.45); bridge.translate(B.x, B.y, B.z + 2 * S);
      add(J.head, 'nose_bridge', bridge, mat.nose);
    }
    // Ears.
    for (const [px, sgn, nm] of [[121, -1, 'ear_R'], [203, 1, 'ear_L']]) {
      const e = new THREE.SphereGeometry(1, 16, 12); e.scale(5 * S, 12 * S, 8 * S); e.rotateY(sgn * 0.35);
      const P = V(px, 97, 96); e.translate(P.x, P.y, P.z); add(J.head, nm, e, mat.skin);
    }
    // Eyes: bulging whites, iris, pupil, heavy upper lids.
    for (const [px, nm] of [[146, 'R'], [178, 'L']]) {
      const r = 9 * S, C = onFace(px, 80, -3);
      const ew = new THREE.SphereGeometry(r, 24, 16); ew.translate(C.x, C.y, C.z); add(J.head, 'eye_' + nm, ew, mat.eyeWhite);
      const ir = new THREE.SphereGeometry(r * 0.52, 18, 12); ir.scale(1, 1, 0.4); ir.translate(C.x, C.y, C.z + r * 0.86); add(J.head, 'iris_' + nm, ir, mat.iris);
      const pu = new THREE.SphereGeometry(r * 0.26, 12, 8); pu.scale(1, 1, 0.4); pu.translate(C.x, C.y, C.z + r * 0.97); add(J.head, 'pupil_' + nm, pu, mat.pupil);
      const lid = new THREE.SphereGeometry(r * 1.1, 24, 10, 0, Math.PI * 2, 0, Math.PI * 0.34); lid.rotateX(0.12); lid.translate(C.x, C.y, C.z);
      add(J.head, 'lid_' + nm, lid, mat.skin);
    }
    // Eyebrows: thick dark arcs following the forehead.
    for (const [nm, pts] of [['R', [[129, 71], [138, 63], [150, 61], [158, 65]]], ['L', [[166, 65], [175, 60], [187, 61], [196, 69]]]]) {
      const curve = new THREE.CatmullRomCurve3(pts.map(([x, y]) => onFace(x, y, 1.5)));
      add(J.head, 'brow_' + nm, new THREE.TubeGeometry(curve, 16, 3.6 * S, 8, false), mat.hair);
    }
    // Grin: crescent mouth conformed to the face, with gappy upper teeth.
    {
      const top = (t) => [131 + 64 * t, 104 + 8 * Math.sin(Math.PI * t)];
      const bot = (t) => [131 + 64 * t, 104 + 24 * Math.sin(Math.PI * t)];
      const cols = 28, rows = 4, pos = [], idx = [];
      for (let i = 0; i <= cols; i++) for (let j = 0; j <= rows; j++) {
        const t = i / cols, [x1, y1] = top(t), [, y2] = bot(t), y = y1 + (y2 - y1) * (j / rows);
        const P = onFace(x1, y, 0.4); pos.push(P.x, P.y, P.z);
      }
      for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
        const a = i * (rows + 1) + j, b = a + 1, c = a + rows + 1, d = c + 1; idx.push(a, b, c, b, d, c);
      }
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
      add(J.head, 'mouth', g, mat.mouth);
      const teeth = [0.2, 0.31, 0.43, 0.57, 0.69, 0.8];
      teeth.forEach((t, k) => {
        if (k === 2) return;                                    // gap tooth
        const [x, y] = top(t), tooth = new THREE.CapsuleGeometry(3.4 * S, 4 * S, 4, 8); tooth.scale(1, 1, 0.55);
        const m = new THREE.Mesh(tooth, mat.teeth); orientTo(m, onFace(x, y + 4.5, 0.6), faceNormal(x, y + 4.5));
        add(J.head, 'tooth_' + k, m);
      });
    }
    // Neck.
    {
      const n = new THREE.CylinderGeometry(25 * S, 28 * S, 34 * S, 20); const P = V(162, 136, 90); n.translate(P.x, P.y, P.z);
      add(J.neck, 'neck', n, mat.skin);
    }

    // ---------------- Hair: dense black curls over a shaped cap ----------------
    {
      // The cap follows the head shape, inflated with extra volume on top (sheet: hair top ~y15).
      const C = V(HEAD.cx, HEAD.cy, HEAD.cz);
      const capPoint = (ux, uy, uz, lift = 1) => {
        const w = widthAt(uy), puff = (1.03 + 0.3 * smooth(-0.2, 0.95, uy) + 0.05 * smooth(0.3, 0.9, Math.abs(ux)) * smooth(0, 0.5, uy)) * lift;
        return new THREE.Vector3(C.x + ux * HEAD.rx * w * S * puff, C.y + uy * HEAD.ry * S * puff, C.z + uz * HEAD.rz * S * puff * (uz < 0 ? 0.93 : 1));
      };
      // Hairline: forehead at the centre, lower at the temples, sideburns at the sides; nape at the back.
      const hairline = (ux) => 0.86 - 1.0 * ux * ux;
      const isFace = (ux, uy, uz) => uz > 0 && uy < hairline(ux);
      const isBelow = (ux, uy, uz) => uy < -0.42 || (uz > -0.3 && uy < 0.02);
      const cap = new THREE.SphereGeometry(1, 44, 34).toNonIndexed(), p = cap.attributes.position, keep = [];
      for (let i = 0; i < p.count; i += 3) {
        let cx = 0, cy = 0, cz = 0; for (let k = 0; k < 3; k++) { cx += p.getX(i + k) / 3; cy += p.getY(i + k) / 3; cz += p.getZ(i + k) / 3; }
        if (isFace(cx, cy, cz) || isBelow(cx, cy, cz)) continue;
        for (let k = 0; k < 3; k++) { const P = capPoint(p.getX(i + k), p.getY(i + k), p.getZ(i + k)); keep.push(P.x, P.y, P.z); }
      }
      const capG = new THREE.BufferGeometry(); capG.setAttribute('position', new THREE.Float32BufferAttribute(keep, 3)); capG.computeVertexNormals();
      add(J.head, 'hair_cap', capG, mat.hair);
      // One curl = 2.2-turn helix tube; instanced over the cap, plus a short fringe over the forehead.
      const helix = new THREE.Curve(); helix.getPoint = (t, out = new THREE.Vector3()) => out.set(Math.cos(t * 13.8) * 0.021, Math.sin(t * 13.8) * 0.021, t * 0.03 - 0.015);
      const curl = new THREE.TubeGeometry(helix, 14, 0.0072, 3, false);
      const N = opts.curls || 340, inst = new THREE.InstancedMesh(curl, mat.hair, N);
      const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler(), sc = new THREE.Vector3(), cc = new THREE.Color();
      let n = 0, k = 0;
      while (n < N && k < 20000) {
        k++;
        const uy = 2 * rnd() - 1, th = rnd() * Math.PI * 2, rr = Math.sqrt(1 - uy * uy), ux = rr * Math.cos(th), uz = rr * Math.sin(th);
        const fringe = uz > 0 && uy < hairline(ux) && uy > hairline(ux) - 0.06 && Math.abs(ux) < 0.7;
        if (isBelow(ux, uy, uz) || (isFace(ux, uy, uz) && !fringe)) continue;
        const P = capPoint(ux, uy, uz, fringe ? 1.0 : 0.99 + rnd() * 0.1);
        e.set(rnd() * 6.28, rnd() * 6.28, rnd() * 6.28); q.setFromEuler(e);
        const s = 0.95 + rnd() * 0.6; sc.set(s, s, s);
        m4.compose(P.sub(J.head.userData.model), q, sc); inst.setMatrixAt(n, m4);
        cc.setHSL(0.06, 0.08, 0.09 + rnd() * 0.12); inst.setColorAt(n, cc);
        n++;
      }
      inst.count = n; inst.castShadow = true; inst.name = 'hair_curls';
      J.head.add(inst); (parts.hair ||= []).push(inst);
    }

    // ---------------- Torso: T-shirt, open khaki overshirt, collar, pockets ----------------
    const torsoRings = [
      { p: [162, 132, 92], w: 28, d: 27 }, { p: [162, 140, 93], w: 44, d: 34 }, { p: [162, 151, 95], w: 63, d: 43 }, { p: [162, 166, 96], w: 70, d: 48 },
      { p: [162, 200, 98], w: 66, d: 52 }, { p: [162, 240, 101], w: 64, d: 57 }, { p: [162, 280, 104], w: 66, d: 61 },
      { p: [162, 304, 102], w: 66, d: 58 }, { p: [162, 318, 99], w: 64, d: 53 }
    ];
    const tshirt = loft(torsoRings, { seg: 28, sub: 5, exp: 2.3 });
    add(J.chest, 'tshirt', tshirt, mat.tshirt);
    const shirtRings = torsoRings.slice(1).map((r, i, a) => ({ p: [r.p[0], r.p[1] + (i === a.length - 1 ? 6 : 0), r.p[2] + 1], w: r.w * 1.07 + 2, d: r.d * 1.07 + 2 }));
    const gap = (u) => 0.3 + 0.16 * smooth(0, 0.6, u);            // open front, wider toward the hem
    const overshirt = loft(shirtRings, { seg: 30, sub: 5, exp: 2.3, gap });
    add(J.chest, 'overshirt', overshirt, mat.khaki);
    // Front placket edges give the open shirt visible thickness.
    for (const side of [1, -1]) {
      const pts = overshirt.userData.rings.map(r => { const a = side > 0 ? r.g : -r.g; return r.C.clone().addScaledVector(r.Wd, r.w * Math.sin(a)).addScaledVector(r.Dd, r.d * Math.cos(a)); });
      add(J.chest, 'placket_' + (side > 0 ? 'L' : 'R'), new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 40, 2.4 * S, 6, false), mat.khakiEdge);
    }
    // Collar band + points.
    add(J.chest, 'collar', loft([{ p: [162, 147, 93], w: 50, d: 40 }, { p: [162, 137, 92], w: 43, d: 36 }, { p: [162, 127, 90], w: 37, d: 33 }], { seg: 24, sub: 3, gap: () => 0.55 }), mat.khaki);
    for (const [px, sgn] of [[141, -1], [183, 1]]) {
      const pt = new THREE.ConeGeometry(9 * S, 20 * S, 3); pt.scale(1, 1, 0.3);
      const m = new THREE.Mesh(pt, mat.khaki); const { P, N } = onLoft(overshirt, FX(px), FY(152), 1.5 * S);
      orientTo(m, P, N); m.rotateZ(Math.PI + sgn * 0.5);
      add(J.chest, 'collarPoint_' + (sgn < 0 ? 'R' : 'L'), m);
    }
    // Chest pockets with flaps.
    for (const [px, nm] of [[115, 'R'], [213, 'L']]) {
      const pocket = new THREE.Mesh(new THREE.BoxGeometry(27 * S, 30 * S, 2.5 * S, 2, 2, 1), mat.khaki);
      const a = onLoft(overshirt, FX(px), FY(197), 1.2 * S); orientTo(pocket, a.P, a.N); add(J.chest, 'pocket_' + nm, pocket);
      const flap = new THREE.Mesh(new THREE.BoxGeometry(29 * S, 10 * S, 3.6 * S, 2, 1, 1), mat.khakiEdge);
      const b = onLoft(overshirt, FX(px), FY(181), 2 * S); orientTo(flap, b.P, b.N); add(J.chest, 'pocketFlap_' + nm, flap);
    }
    // Necklace: cord around the neck dropping to a pendant on the chest.
    {
      const pts = [];
      for (let i = 0; i < 24; i++) {
        const s = (i / 24) * Math.PI * 2, front = Math.max(0, Math.cos(s));
        const px = 162 + 30 * Math.sin(s), py = 140 + 24 * front ** 3;
        let z = 92 + 30 * Math.cos(s);
        if (front > 0.35) z = Math.max(z, (onLoft(tshirt, FX(px), FY(py)).P.z / S) + 96 + 2.2);
        pts.push(V(px, py, z));
      }
      add(J.chest, 'necklace', new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, true), 60, 1.3 * S, 6, true), mat.cord);
      const pend = new THREE.SphereGeometry(5 * S, 14, 10); pend.scale(0.8, 1.1, 0.45);
      const { P } = onLoft(tshirt, FX(162), FY(169), 3.5 * S); pend.translate(P.x, P.y, P.z);
      add(J.chest, 'pendant', pend, mat.pendant);
    }

    // ---------------- Jeans: waist, thighs, shins, rolled cuffs ----------------
    add(J.hips, 'jeans_hips', loft([{ p: [162, 308, 100], w: 64, d: 55 }, { p: [162, 326, 98], w: 66, d: 52 }, { p: [162, 344, 96], w: 60, d: 44 }], { seg: 28, sub: 4, exp: 2.3 }), mat.denim);
    for (const [sgn, nm] of [[-1, 'R'], [1, 'L']]) {
      const X = (px) => 162 + sgn * (162 - px);
      add(J['thigh_' + nm], 'jeans_thigh_' + nm, loft([{ p: [X(131), 326, 100], w: 31, d: 36 }, { p: [X(127), 365, 98], w: 28, d: 32 }, { p: [X(122), 404, 93], w: 24, d: 27 }], { sub: 6 }), mat.denim);
      add(J['shin_' + nm], 'jeans_shin_' + nm, loft([{ p: [X(122), 396, 93], w: 24, d: 27 }, { p: [X(119), 430, 89], w: 22, d: 25 }, { p: [X(116), 458, 86], w: 21, d: 23 }], { sub: 6 }), mat.denim);
      add(J['shin_' + nm], 'jeans_cuff_' + nm, loft([{ p: [X(116), 450, 86], w: 23, d: 25 }, { p: [X(116), 459, 86], w: 26, d: 27 }, { p: [X(115), 469, 86], w: 25, d: 26 }], { sub: 4 }), mat.denimCuff);
    }

    // ---------------- Shoes: grey sneakers with navy panels, white sole and laces ----------------
    for (const [sgn, nm] of [[-1, 'R'], [1, 'L']]) {
      const cx = 162 + sgn * (162 - 101), foot = J['foot_' + nm], yaw = sgn * 0.17;
      const zs = [-33, -22, 0, 24, 46, 64], ys = [488, 485, 486, 490, 493, 495], ws = [8, 23, 28, 29, 25, 8], hs = [9, 17, 15, 12, 9, 4];
      const upper = loft(zs.map((z, i) => ({ p: [cx, ys[i], 86 + z], w: ws[i], d: hs[i] })), { seg: 22, sub: 5, exp: 2.6, caps: true });
      const sole = loft(zs.map((z, i) => ({ p: [cx, 498, 86 + z + (i === 0 ? -2 : i === 5 ? 3 : 0)], w: ws[i] * 1.08 + 1, d: 4 })), { seg: 22, sub: 5, exp: 3, caps: true });
      // Navy heel counter and toe band via vertex colours.
      const pa = upper.attributes.position, col = [], grey = new THREE.Color(0xa6a7ab), navy = new THREE.Color(0x3d4152), c = new THREE.Color();
      const zMin = FZ(86 - 33), zMax = FZ(86 + 64);
      for (let i = 0; i < pa.count; i++) {
        const tz = (pa.getZ(i) - zMin) / (zMax - zMin), ty = pa.getY(i);
        c.copy(grey); if (tz < 0.28 || ty < FY(495) || (tz > 0.86 && ty < FY(490))) c.copy(navy);
        col.push(c.r, c.g, c.b);
      }
      upper.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
      const pivot = V(cx, 498, 86); const turn = (g) => { g.translate(-pivot.x, -pivot.y, -pivot.z); g.rotateY(yaw); g.translate(pivot.x, pivot.y, pivot.z); return g; };
      add(foot, 'shoe_' + nm, turn(upper), mat.shoe);
      add(foot, 'sole_' + nm, turn(sole), mat.sole);
      for (let l = 0; l < 3; l++) {
        const lace = new THREE.CapsuleGeometry(1.5 * S, 15 * S, 3, 6); lace.rotateZ(Math.PI / 2);
        lace.translate(FX(cx), FY(474 + l * 4), FZ(86 + 8 + l * 9)); add(foot, `lace_${nm}_${l}`, turn(lace), mat.lace);
      }
    }

    // ---------------- Arms: khaki sleeves with rolled cuffs, forearms, hands ----------------
    for (const [sgn, nm] of [[-1, 'R'], [1, 'L']]) {
      const X = (px) => 162 + sgn * (162 - px);
      add(J['upperArm_' + nm], 'sleeve_' + nm, loft([{ p: [X(100), 150, 96], w: 22, d: 24 }, { p: [X(84), 180, 99], w: 24, d: 24 }, { p: [X(70), 215, 103], w: 22, d: 22 }, { p: [X(62), 246, 107], w: 21, d: 20 }], { sub: 6 }), mat.khaki);
      add(J['forearm_' + nm], 'sleeveCuff_' + nm, loft([{ p: [X(64), 238, 106], w: 22, d: 21 }, { p: [X(60), 250, 108], w: 25, d: 24 }, { p: [X(57), 262, 109], w: 23, d: 22 }], { sub: 4 }), mat.khakiEdge);
      add(J['forearm_' + nm], 'forearm_' + nm, loft([{ p: [X(60), 252, 108], w: 14, d: 13 }, { p: [X(52), 285, 112], w: 12, d: 11 }, { p: [X(46), 316, 116], w: 9, d: 8 }], { sub: 6 }), mat.skin);
      // Hand: palm + four fingers + thumb, hanging relaxed with palms toward the body.
      const hand = new THREE.Group(); hand.name = 'hand_' + nm;
      const palm = new THREE.Mesh(new THREE.SphereGeometry(1, 18, 14), mat.skin); palm.scale.set(7.5 * S, 17 * S, 13 * S); palm.position.y = -13 * S; hand.add(palm);
      for (let f = 0; f < 4; f++) {
        const len = [15, 17, 16, 13][f], fg = new THREE.Mesh(new THREE.CapsuleGeometry(3.3 * S, len * S, 4, 8), mat.skin);
        fg.position.set(0, -(29 + len / 2) * S, (-8.5 + f * 5.6) * S); fg.rotation.x = (f - 1.5) * 0.06; fg.rotation.z = sgn * 0.12; hand.add(fg);
      }
      const th = new THREE.Mesh(new THREE.CapsuleGeometry(3 * S, 12 * S, 4, 8), mat.skin); th.position.set(-sgn * 3 * S, -16 * S, 12 * S); th.rotation.x = 0.6; hand.add(th);
      const wrist = V(X(46), 316, 116), elbow = V(X(60), 252, 108);
      hand.position.copy(wrist); hand.quaternion.setFromUnitVectors(new THREE.Vector3(0, -1, 0), wrist.clone().sub(elbow).normalize());
      hand.traverse(o => { o.castShadow = true; });
      add(J['hand_' + nm], 'hand_' + nm, hand);
    }

    root.userData.joints = J;
    root.userData.parts = parts;
    root.userData.version = 'C1-blockout';
    return root;
  }

  window.AreesCharacters = Object.assign(window.AreesCharacters || {}, { createSayed });
})();
