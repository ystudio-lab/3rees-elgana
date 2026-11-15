# Voice generator (free, local)
Creates real Egyptian-Arabic WAVs for all 8 characters from `lines.json` (45 lines taken from the game) with
[VoiceTut-TTS](https://huggingface.co/mohammedaly22/VoiceTut-TTS) (language id `arz`).
Needs a CUDA GPU: a free Colab T4 works. It cannot run in the cloud sandbox used to build the game (no GPU, Hugging Face blocked).

1. `pip install voicetut-tts` and `pip install git+https://github.com/k2-fsa/OmniVoice.git`
2. `python tools/voice-generator/generate.py --list-speakers`, then put one name per character in `speakers.json`
3. `python tools/voice-generator/generate.py`  → `assets/audio/voices/<char>/<key>.wav` + `manifest.json`
4. Ship the `assets/audio/voices/` folder next to `index.html`. The game loads the manifest automatically.
Check the model licence before commercial release. Without recordings the game falls back to browser Arabic speech, then babble.
