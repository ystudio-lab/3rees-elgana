# Audio files (optional)

The game makes all of its music and sound effects in code. Nothing in this folder is needed for it to run.

Use this folder only for files you own or have a written licence for. Do not add songs ripped from YouTube, downloaded MP3s or streaming links.

## Radio songs: `assets/audio/radio/`
1. Copy the file here. Supported formats: MP3, M4A (AAC), OGG, Opus and WAV. The game checks whether the browser can play the format before using the file.
2. Add an entry to `RADIO_FILES` in `index.html`:
   ```js
   { id: 'track-id', file: 'assets/audio/radio/track-id.mp3', titleAr: 'اسم الأغنية', titleEn: 'Song title', artist: 'Artist', licence: 'Who granted the licence' }
   ```
3. Real songs play before the four built-in placeholder tracks. If a file fails to load, the radio skips it and shows a message.

## Character voices: `assets/audio/voice/<characterId>/`
Each line ID is `<characterId>_<line number>`, for example `noga_1` or `faheem_2`. The number is the line's position in `NPC_TALK` (counting from 1). Player-character lines use `sayed_start`, `sayed_hit`, `sayed_win` and `sayed_lose`.

Add an entry to `VOICE_FILES` in `index.html`:
```js
'noga_1': 'assets/audio/voice/noga/noga_1.ogg'
```
A line that has a file plays the recording. A line without one shows only the written subtitle, plus a short babble sound effect if "Character babble" is turned on. The babble is not speech.
