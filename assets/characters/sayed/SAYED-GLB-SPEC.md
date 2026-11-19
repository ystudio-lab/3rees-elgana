# SAYED FELFEL (سيد فلفل) — GLB Production Specification v1.0

**Deliverable:** `assets/characters/sayed/sayed.glb` (single binary glTF 2.0, textures embedded)
**Source of truth for the look:** `assets/references/3d-production/sayed/sayed-front.png`, `sayed-side.png`, `sayed-back.png` (approved character sheet). Do NOT redesign. Match the sheet; where the sheet and this spec disagree on appearance, the sheet wins; where they disagree on rig/scale/names, this spec wins.
**Status:** no GLB exists yet. The game runs the procedural Sayed until this file is delivered AND enabled (see §11).

---
## 1. Units, scale, orientation (hard requirements)
| Item | Requirement |
|---|---|
| Units | 1 unit = 1 metre (glTF native). Apply all transforms (scale 1, rotation 0) before export. |
| Up axis | +Y up (glTF). In Blender: export with "+Y Up". |
| Facing | Character faces **+Z** (glTF forward). Game turns him with `rotation.y` (0 = faces camera, π = runs away). |
| Origin | World origin at the **soles of the feet**, centred between the feet (x=0, z=0). Feet flat on y=0. |
| Height | **1.90 m ± 0.03** top of curls (current procedural: 1.911). Head-centre joint at y = 1.57. |
| Footprint | Fits in x ∈ [−0.45, 0.45], z ∈ [−0.30, 0.40] in the Idle pose, arms relaxed. |
| Proportions | Stocky, big head, short legs, per the sheet. Rest-pose joint heights (m): hips 0.86, knee 0.48, shoulder 1.30–1.36, head joint 1.57. Shoulder joints x = ±0.28, hip joints x = ±0.118. |
| Pose | Bind/rest pose = **A-pose**, arms ~35° below horizontal, palms in, facing +Z, neutral face. |
| Handedness | `armL/legL/foreL/shinL` are the character's **left = +X** (as in the current rig). `…R` = −X. |
| Hitbox | The game's capsule is fixed (radius 0.3, centre y 0.9). Do not model it; do not scale the character to "fit". |

## 2. Scene structure (node names are case-sensitive)
```
Sayed                      (Scene root Empty/Group; the only root node)
├─ root                    (Bone, at origin, y=0)
│  └─ hips                 (Bone, y=0.86)
│     ├─ torso             (Bone, y≈0.86)      ← spine chain collapsed to ONE joint named torso (extra spine bones allowed: torso_1, torso_2 as children BEFORE head/arms)
│     │  ├─ head           (Bone, y=1.57)
│     │  │  └─ head_top    (Empty/Bone, at crown of hair; used for helmet placement)
│     │  ├─ armL → foreL → handL
│     │  └─ armR → foreR → handR
│     ├─ legL → shinL → footL
│     └─ legR → shinR → footR
├─ Sayed_Body              (SkinnedMesh: skin, clothes, hair, accessories — see §4)
└─ Sayed_Head              (SkinnedMesh: face, with morph targets — see §6)
```
- Required bone names (exact): `root hips torso head armL foreL armR foreR legL shinL legR shinR`. Optional extras: `handL handR footL footR head_top neck jaw eyeL eyeR` (extras are ignored by the game but allowed).
- Max **32 bones** total, max **4 influences per vertex**, weights normalised, bind pose = rest pose.
- Single armature, single skin per SkinnedMesh; both meshes share the same skeleton.
- No cameras, lights, empties other than listed, no IK/constraints/drivers in the exported file (bake them).

## 3. Budget (Android mid-range target)
| Item | Limit |
|---|---|
| Triangles (whole character, LOD0) | **≤ 12,000** (current procedural: 15,579 — the GLB should be *lower* and look better via normal maps) |
| Draw calls | **≤ 3** (Body, Head, optional Eyes) → ≤ 3 materials total |
| Materials | 3 max: `MAT_Sayed_Body`, `MAT_Sayed_Head`, `MAT_Sayed_Eyes` (eyes may be merged into Head) |
| Texture sets | Body 1024², Head 1024². **No 2K+.** |
| Texture memory | ≤ 6 MB GPU total |
| File size | **≤ 4 MB** (Draco/meshopt allowed — see §9 for loader support) |
| Animation | ≤ 30 fps keyframes, ≤ 2.5 MB of clip data; no per-frame vertex animation |

## 4. Sculpt / content (match the sheet)
High-poly sculpt baked down to the game mesh. The sculpt must capture: curly dark hair mass (dense, individually readable curls — current procedural hair is too thin, this is a known gap), stocky torso with pronounced belly, rounded bulb nose, wide grin with visible teeth, stubble shadow on jaw, thick brows, chubby cheeks, short strong forearms, work-worn hands. Clothes (shirt, jeans, belt, shoes), the necklace (silver chain + pendant per the sheet), and any accessories drawn on the sheet are **modelled as geometry** (not painted flat) with fabric folds at elbows, belly, knees and cuffs. Colours come from the sheet, not from the procedural build (jeans = mid denim, not near-black; chain = silver). Hair, clothes and accessories are skinned to the same skeleton; no separate rigid props except through `head_top`.

## 5. Materials & textures (glTF 2.0 PBR metallic-roughness only)
- Material model: `pbrMetallicRoughness`. No KHR extensions except `KHR_materials_emissive_strength` (optional) and `KHR_texture_transform`. **No** transmission, clearcoat, sheen, volume, iridescence (too slow on Android).
- Per material, textures are:
  | Slot | Format | Colour space | Notes |
  |---|---|---|---|
  | baseColorTexture | PNG/JPEG, RGB (+A only where needed) | sRGB | Albedo, **no baked lighting / AO / shadows**. Skin must stay warm (`#dba58c` average). |
  | normalTexture | PNG, tangent space, +Y (OpenGL) | Linear | Fabric weave, skin pores, hair strands, stitches. |
  | metallicRoughnessTexture (ORM) | PNG/JPEG | Linear | **R = ambient occlusion**, **G = roughness**, **B = metallic** (glTF ORM packing; reference occlusionTexture and metallicRoughnessTexture to the same image). |
  | emissiveTexture | optional | sRGB | Only for the pendant if needed. |
- Roughness guide: skin 0.55–0.7, cotton 0.85–0.95, denim 0.9, hair 0.6, metal chain/pendant 0.3 with metallic 1.0, shoe rubber 0.8, eyes 0.1 (glossy).
- Texture sizes powers of two, ≤1024². Mip-friendly (no hairline detail below 2 px). No alpha-blend; hair cards (if any) use `alphaMode: MASK` with cutoff 0.5. All materials `doubleSided: false` except hair cards.
- UV0 only (non-overlapping, 2–4 px padding). No UV animation. Vertex colours not required and are ignored.
- Embed textures in the .glb. No external URIs.

## 6. Facial animation: morph targets (on mesh `Sayed_Head`)
All targets are **relative** (delta) morphs, influence range 0–1, rest = 0. Normals must be included on every target. ≤ 20 targets. Names exact, case-sensitive:

**Mouth / dialogue (driven by the game's Talk mode and, later, by audio):**
`viseme_aa` (open "aah"), `viseme_oo` (round "ooh/o"), `viseme_ee` (wide "ee"), `viseme_mbp` (lips closed "m/b/p"), `viseme_fv` (lower lip to teeth), `mouthOpen` (jaw drop, generic), `mouthSmile` (grin wider), `mouthFrown`

**Eyes:** `blinkL`, `blinkR`, `eyesWide`, `eyesNarrow`, `lookUp`, `lookDown`

**Brows / expression packs (full-face, from the character sheet's expression row):**
`browUp`, `browAngry`, `exp_happy`, `exp_angry`, `exp_scared`, `exp_surprised`, `exp_smug` (overconfident), `exp_fall` (the "falling" shout)

Notes: the neutral face = the sheet's neutral grin. Mouth shapes must not push the nose. `mouthOpen=1` + `viseme_aa=1` must stay inside the head silhouette (no clipping through the chin).

## 7. Animation clips (exact names, in the glTF `animations[]`)
All clips: bones only (translation on `hips` allowed; rotation on all others; **no scale tracks**), sampled at 30 fps, no root motion (character stays at x=0, z=0 — the game moves the capsule). Feet-on-ground y=0 at rest. Names exact, case-sensitive:

| Clip | Loop | Length | Spec |
|---|---|---|---|
| `Idle` | loop | 2.0 s | Breathing, weight shift, head micro-look. Neutral facing +Z. |
| `Run` | loop | **0.60 s** (one full stride = left+right; matches the game's ~10 Hz cadence at 3 steps/s) | Chunky, bouncy, arms pumping, slight forward lean (~8° at `torso`). Passing-pose contact at 0 / 0.30 s. |
| `Jump` | hold/once | 0.7 s | Pose pair: take-off crouch → air (arms up, knees tucked) → ends in the airborne hold pose (last frame is held while the player is not grounded). |
| `Slide` | hold/once | 0.35 s | Drop to a low slide (hips ≈ 0.45 m, torso leaning back ~35°, legs forward), last frame held while sliding. NOTE: the game squashes the *hitbox* to 50% and cancels it visually, so author at **normal scale 1.0**. |
| `Wave` | loop | 1.6 s | Menu greeting: right arm raised, waving, big grin. |
| `Cheer` | loop | 1.2 s | Victory / character-picked: both arms up, bounce. |
| `Talk` | loop | 2.0 s | Conversational idle with hand gestures (face is driven by morphs, not baked). |
| `Defeat` | once | 1.0 s | Hit-flinch / game-over: recoil then slump. The game also uses this as the short "ouch" on collision. |

- The first four (`Idle Run Jump Slide`) are **mandatory for acceptance**. `Wave Cheer Talk Defeat` are required before the GLB replaces the procedural Sayed (the game uses them in menus, victory and game-over). If any is missing the loader falls back to `Idle` and logs a warning.
- Mouth/face morph keyframes in clips are **allowed only for expression poses** (e.g. `Defeat` may key `exp_fall`); lip-sync is runtime-driven, so clips must not key `viseme_*` or `mouthOpen`.
- Export clips as separate NLA/Action entries; do not leave a stashed "Action" or "Take 001".

## 8. Rig/deform quality rules
- Weight-paint for ±90° shoulder, 120° knee/elbow without volume collapse. Belly must jiggle-free (no physics).
- Hair is skinned to `head`; it must not intersect the torso in `Defeat`/`Slide`.
- No bone is scaled in any clip. No negative scale. Quaternion rotation tracks.
- `head_top` must sit on the highest point of the curl mass when the character is in the bind pose (the game parents the Mahshi helmet there).

## 9. Export settings
- **Blender 4.x glTF Exporter:** Format = glTF Binary (.glb); Include: Selected Objects (Sayed collection only); Transform: +Y Up; Mesh: Apply Modifiers ON, Normals ON, Tangents OFF, Vertex Colors OFF; Compression: **Off** for v1 (Draco/meshopt only if size > 4 MB, and then tell the integrator so the decoder can be wired); Animation: Mode = **NLA Tracks**, FPS 30, Always Sample ON, Optimize Animation Size ON; Skinning ON, **Include All Bone Influences OFF**; Shape Keys ON with Shape Key Normals ON; Materials = Export; Images = **Automatic (PNG/JPEG)**, ≤1024².
- Validate with the Khronos glTF Validator (0 errors; warnings reviewed) and open in a glTF viewer before delivery.

## 10. Acceptance checklist (the integration pass runs these)
1. Loads with GLTFLoader without errors; single root `Sayed`; `sayed.glb` ≤ 4 MB.
2. Bone names exactly as §2; ≤ 32 bones; ≤ 4 influences.
3. Height 1.90 ± 0.03 m, feet at y=0, faces +Z, origin between the feet.
4. Triangles ≤ 12,000; ≤ 3 materials; ≤ 3 draw calls.
5. Clips `Idle Run Jump Slide` present and correctly named (plus `Wave Cheer Talk Defeat` before go-live); `Run` is 0.60 s and loops seamlessly.
6. Morph targets on `Sayed_Head` with every name in §6.
7. PBR slots populated per §5; no external image URIs; sRGB/linear flags correct.
8. Screenshot comparison to the character sheet (front / side / back) passes art-director review.
9. In-game: no collision/slide/jump behaviour change; thumbnails, helmet (Mahshi), voice-talk animation and flinch all work; FPS on the Android reference device ≥ the procedural build.

## 11. Integration contract (how the game consumes it)
- Path: `assets/characters/sayed/sayed.glb` (relative to `index.html`).
- Loader: `loadSayedGLB()` in `index.html` (opt-in). It is **inert unless** the URL has `?glb=sayed` (or `localStorage.areesGLB = 'sayed'`). On any error (404, parse error, missing bone/clip) it logs to `window.__arees.GLB.errs` and the procedural Sayed stays.
- The loader builds a Group with the same `userData.joints` shape (`head, hips, torso, armL, armR, foreL, foreR, legL, legR, shinL, shinR`), plus `userData.glb = { mixer, actions, morph }`. `AreesCast.animate()` is wrapped so GLB characters are driven by an `AnimationMixer` cross-fading between the clip named for the requested mode (`idle→Idle`, `run→Run`, `jump→Jump`, `slide→Slide`, `wave→Wave`, `cheer→Cheer`, `talk→Talk`, `defeat→Defeat`); procedural characters are untouched.
- `talk` mode additionally drives `mouthOpen`/`viseme_aa`/`viseme_oo` from a smooth envelope until audio-driven visemes are added later.
- The hitbox capsule, slide squash cancel (`sayed.scale.y = 1 / player.scale.y`), lane lean (`rotation.z`) and yaw (`rotation.y`) are applied to the **returned root Group**, exactly as for the procedural model, so gameplay is unchanged.

---
## AS-BUILT (M20) — revision results (supersedes M19)

Status: OPT-IN ONLY (`?glb=sayed` or `localStorage.areesGLB='sayed'`). Procedural Sayed remains the default and the silent fallback. Awaiting user approval.

- File: sayed.glb ~3.94 MB (cap 4 MB), 11,647 tris, 3 materials / 3 draw calls, 17 bones, max 4 influences, height 1.912 m.
- Rig (spec-correct): root, hips y0.86, torso y0.90, head joint y1.57, head_top child of head (1.908), arm joints at shoulder (+-0.28,1.32), legs +-0.118. Armpit weights Laplacian-smoothed; garment arm weights fall off by distance to arm segment.
- Morphs: 22 shipped. NOTE spec section 6 says "<=20" but lists 22 names; the list governs, text should read "22".
- Clips (8): Idle, Run, Jump, Slide, Wave, Cheer, Talk, Defeat. Exact lengths (time shifted -1/30 s, scale channels stripped). Slide = 0.333 s vs 0.35 s spec (frame-quantized).
- UVs: xatlas, 1024 px, 0 overlap, hair band + face charts + swatch band (teeth/tongue/lids).
- Textures: base/ORM JPEG, normal PNG 5-bit-quantized (size cap). Normal map = sculpt SDF gradient (folds, fingers, curls) + procedural bump.
- Geometry fixes: stockier build, 5-finger hands with thumb, eyelids, larger grin/teeth, flapped front-only pockets, straight shirt hem, rolled sleeves.

### Known limitations (exact)
- Procedural clay-like sculpt, not Pixar-grade; hair is tight curls, not the sheet's loose curls; brows are stiff bars; fingers mitten-ish.
- Eye sockets/lids low-poly; faint copper strip on mouth-interior floor; ee viseme weakly triggered.
- GPU texture memory ~32 MB vs spec <=6 MB (needs KTX2/Basis, loader does not support it).
- Normals 5-bit quantized.
- Real-device (Android) performance untested; software-render numbers only.

### Tests (Playwright, swiftshader, serial)
glbfull (load/skeleton/morphs/clips), view (turnaround/details), glbgame (run/jump/slide), glbhit (collision -> Defeat), procedural baseline, 4 fallback variants (missing file / bad file / flag off / load error). Results in previews/test_*.json.
