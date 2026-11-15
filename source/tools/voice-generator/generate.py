#!/usr/bin/env python3
"""Generate real Egyptian-Arabic WAV dialogue for AREES EL GANNAH with VoiceTut-TTS (free, local).

Setup (once, on a machine with a GPU or a free Colab T4):
    pip install voicetut-tts
    pip install git+https://github.com/k2-fsa/OmniVoice.git
Run from the project root:
    python tools/voice-generator/generate.py --list-speakers
    python tools/voice-generator/generate.py            # writes assets/audio/voices/**.wav + manifest.json
    python tools/voice-generator/generate.py --only noga --force

The game reads assets/audio/voices/manifest.json at startup; missing clips silently fall back to
browser speech / babble, so a partial run is safe.
"""
import argparse, json, os, sys, wave

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "audio", "voices")
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-speakers", action="store_true")
    ap.add_argument("--only", help="character id, e.g. sayed")
    ap.add_argument("--force", action="store_true", help="regenerate existing files")
    ap.add_argument("--model", default="mohammedaly22/VoiceTut-TTS")
    ap.add_argument("--voices", default=os.path.join(HERE, "speakers.json"))
    a = ap.parse_args()
    try:
        from voicetut_tts import VoiceTutTTS
    except ImportError:
        sys.exit("voicetut-tts is not installed. See the header of this file / README.md.")
    tts = VoiceTutTTS.from_pretrained(a.model)
    if a.list_speakers:
        for s in tts.list_speakers(): print(s)
        return
    speakers = json.load(open(a.voices, encoding="utf-8"))
    lines = json.load(open(os.path.join(HERE, "lines.json"), encoding="utf-8"))
    manifest, made, skipped = {}, 0, 0
    for ln in lines:
        c, key = ln["char"], ln["key"]
        if a.only and c != a.only: continue
        path = os.path.join(OUT, c, key + ".wav")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and not a.force: skipped += 1
        else:
            tts.synthesize(ln["text"], speaker=speakers[c], output=path); made += 1
            print("made", os.path.relpath(path, ROOT))
        manifest.setdefault(c, {})[key] = "assets/audio/voices/%s/%s.wav" % (c, key)
    # validate every listed file is a readable WAV before publishing the manifest
    for c, d in list(manifest.items()):
        for k, p in list(d.items()):
            try:
                try:
                    import soundfile as sf; i = sf.info(os.path.join(ROOT, p)); assert i.frames > 0
                except ImportError:
                    wave.open(os.path.join(ROOT, p)).close()
            except Exception as e: print("BAD", p, e); del d[k]
    mp = os.path.join(OUT, "manifest.json")
    if a.only and os.path.exists(mp):                      # merge partial runs
        old = json.load(open(mp, encoding="utf-8")); old.update(manifest); manifest = old
    json.dump(manifest, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("done: %d new, %d kept; manifest -> %s" % (made, skipped, os.path.relpath(mp, ROOT)))

if __name__ == "__main__":
    main()
