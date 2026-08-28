# video-use editor (visual UI)

A local, CapCut-style visual editor for video-use: a media bin, a real-time
player, and a multi-track timeline (video / text / overlay / audio) with
drag-to-trim, split, transitions, per-clip color grade, speed, Ken Burns
zoom/pan, stickers, background music, file upload, and export — all in the
browser. It also exposes the same AI-driven automation the chat flow uses:
one-click ElevenLabs transcription per clip, and a real Claude-powered
auto-edit that proposes a cut list from a brief for you to review before
anything touches the timeline.

It is **not a replacement** for the chat-driven flow — it's a second way to
drive the same project. Both read and write the same `<videos_dir>/edit/`
directory and the same `edl.json` the skill's helpers already use:

- The **backend** (`backend/`) is a small FastAPI app. It doesn't reimplement
  rendering — it shells out to `helpers/render.py`, the same pipeline
  `SKILL.md` documents, in a background job and streams its log to the UI.
- The UI's richer `timeline.json` (multi-track, per-clip grade/transition/text)
  is bridged to/from `edl.json` on every load/save (`backend/bridge.py`), so
  opening the editor on a project Claude already cut (via chat) shows the same
  cuts, grades, and overlays — and saving from the UI keeps `edl.json` in a
  shape the chat flow can keep editing.

## Quick start (Windows, installed like an app)

From the repo root, in File Explorer:

1. Double-click **`Video-Use-Setup.bat`** once — installs everything,
   builds the frontend, and adds a **video-use** shortcut (with its own
   icon) to your Desktop and Start Menu. Leave the window open until it
   says "Pronto!".
2. From then on, open it the same way as any other app — the Desktop icon,
   or search "video-use" in the Start Menu. It starts the backend hidden
   (no console window) and opens in its own app window (no browser address
   bar/tabs, via Edge's app mode — falls back to your default browser if
   Edge isn't found). Your footage goes in `%USERPROFILE%\Videos\video-use`
   (created for you the first time).
3. To close it, close the app window, or double-click **`Video-Use-Stop.vbs`**
   if you want to make sure the background server stops too.

**To update** — Setup also adds a **"video-use (atualizar)"** entry to the
Start Menu, pointing at `Video-Use-Update.bat`. Running it downloads the
latest version of this branch, copies it over the existing install (leaving
`.env` and your footage untouched), then re-runs Setup automatically to pick
up any new dependencies and rebuild the frontend — no manual zip download,
no re-pasting `.env`.

## Quick start (manual / macOS / Linux)

From the repo root:

```bash
# 1. Backend deps
pip install -e ".[webapp]"      # or: pip install fastapi "uvicorn[standard]"

# 2. Build the frontend once
cd webapp/frontend
npm install
npm run build

# 3. Run, pointed at a folder of raw footage
cd ../..
python webapp/backend/main.py --videos-dir /path/to/your/videos --port 8756
```

Open `http://127.0.0.1:8756`. Drop more footage into the folder and refresh —
it shows up in the media bin, same as the chat flow.

After a `git pull` that changes the frontend, rebuild it once
(`npm run build` in `webapp/frontend`, or just re-run `Video-Use-Setup.bat`
on Windows) before the new UI shows up — the backend serves whatever was
last built, not the source files directly.

### AI features (optional)

Transcription and AI auto-edit both read their key from a `.env` file at the
repo root (same convention as the chat flow — see `install.md`), or from the
environment. Nothing in the UI works without the matching key; everything
else in the editor works fine without either:

```
ELEVENLABS_API_KEY=...   # for one-click transcription
OPENAI_API_KEY=...       # preferred: AI auto-edit + caption translation
OPENAI_MODEL=gpt-5.4-mini
ANTHROPIC_API_KEY=...    # optional fallback
```

- **Transcription** — a **Transcribe** button per clip (or **Transcribe all**)
  in the Media panel calls ElevenLabs Scribe and caches the result under
  `edit/transcripts/`, same as `helpers/transcribe.py`. Needed for both
  auto-subtitles on export and the AI auto-edit below.
- **AI auto-edit** (toolbar, **✨ AI Edit**) — write a brief ("60s highlight,
  upbeat, cut the small talk"), optionally a target duration, and it sends
  your transcribed footage to OpenAI (`gpt-5.4-mini` by default), with
  Anthropic as a fallback when only its key is configured. The model proposes a list of cuts
  (source, in/out, a short label, and why); you review, uncheck anything you
  don't want, and only then click **Apply** to write them to the video track.
  Nothing is ever applied automatically.
- **Cleanup / silence + filler-word removal** (Inspector, selected video
  clip → **✂ Limpar**) — no LLM call, purely from the transcript's word
  timestamps: flags silences above a threshold you set and unambiguous
  filler interjections ("um", "uh", "erm"...). Deliberately conservative —
  context-dependent words like "like"/"so"/"actually" are never auto-removed
  since they're too often not filler. Review the list, then **Aplicar**
  splits that one clip into the surviving sub-ranges in place.
- **Transcript editing** (Inspector, selected video clip → **Editar pela
  transcrição**) — click individual words to mark them for removal, preview
  the exact selection, then apply the resulting non-destructive cuts. The
  operation uses the same undo/redo history and autosave as timeline edits.

## Frontend dev mode (hot reload)

```bash
# terminal 1
python webapp/backend/main.py --videos-dir /path/to/your/videos

# terminal 2
cd webapp/frontend && npm run dev   # http://localhost:5173, proxies /api and /media to :8756
```

## Editor basics

- **Media bin** (left) — drag a clip onto the video track, or double-click to append. Drag files in from your OS file browser (or click **+ Import**) to add new footage/audio to the project without leaving the browser. Below it: a small **sticker** library (drag onto the Overlays track) and a **Music** list (drag onto the Audio track) for any audio files sitting in the videos folder. Footage recorded as HEVC/h265 (common on Android and iPhone cameras) plays audio-only in a browser's native `<video>` tag, so those clips are automatically routed through a lazily-transcoded h264 preview copy for playback — export quality is unaffected either way, since rendering always re-encodes from the original file. Removing media also removes its timeline clips after confirmation, but moves the original into the project's recoverable `edit/trash/` folder.
- Imported PNG, JPG, and WebP images appear with the stickers and can be
  placed on the overlay track. Removing source media moves it to
  `edit/trash/` rather than permanently deleting it.
- **Player** (center top) — space to play/pause, scrub the transport bar or the timeline ruler. Reflects per-clip speed (`playbackRate`) and shows the active sticker/text overlay live.
- **Timeline** (bottom) — drag clip edges to trim, drag a clip to reorder, `S` to split at the playhead, `Delete` to remove the selected clip, `+ Text at playhead` to drop a title card. The Audio track's clips trim/move the same way, adjusting `trimIn` on the left edge.
- **Aspect ratio** (Toolbar) — reframe the whole project for a different platform: 16:9 Landscape, 9:16 Vertical (Reels/Shorts), 1:1 Square, or 4:5 Portrait. Every clip is scaled and center-cropped to fill the chosen frame (same "fill" behavior as CapCut/Reels/TikTok when footage doesn't match); use the per-clip **Transform** panel afterward to reposition anything the auto-crop cuts off. Leaving it on **Original** renders each clip at its own native orientation, exactly like before this existed — nothing changes for existing projects unless you actively pick a ratio.
- **Inspector** (right), per clip type:
  - **Video** — grade preset (10 presets, see `helpers/grade.py`), transition-out type/duration, **speed** (0.25x–4x), **Ken Burns zoom/pan** (in/out, adjustable amount), and a **Transform** panel (scale, X/Y position, rotation, opacity, flip H/V) — a static per-clip transform, not keyframed over time; live-previewed in the player via CSS and rendered for real via ffmpeg `crop`/`pad`/`rotate`/`colorchannelmixer`.
  - **Text** — content, position, font size/color, background chip, **animation** (fade or slide-up entrance).
  - **Sticker** — position (x/y) and size, as fractions of the frame.
  - **Audio** — start/duration, volume, fade in/out.
- **Export** — preview (fast, 720p) or final (1080p, loudness-normalized), with a live render log and a download link when done. The same Export dialog also has **Export EDL**, a CMX3600 Edit Decision List for handing the cut off to DaVinci Resolve, Premiere Pro, or Final Cut Pro — importable by all three. It carries clip order and exact source in/out points only (cuts); grades, transitions, text/overlays, Ken Burns, speed changes and music don't survive the format and aren't meant to — redo those with the target NLE's own (better) tools. The exported file notes anything dropped per clip as `* NOTE:` comments, and includes `* FROM CLIP NAME:` comments so the NLE can auto-relink source media by filename.
  - **Subtitle style + language** — when "Burn subtitles" is checked, a panel opens for size, color, position (bottom/middle/top — bottom respects the platform safe-zone margin Reels/Shorts/TikTok UI needs), a background box, and an UPPERCASE toggle. **Subtitle language** translates the burned-in captions with the same configured OpenAI/Anthropic provider, cached per source so translating once doesn't re-spend API calls on the next export — timing follows sentence boundaries rather than exact per-word sync, since translation changes word count and order. Leaving it on "Original" behaves exactly as before.

## What's intentionally out of scope (v1)

- Generating new overlay animations (HyperFrames/Remotion/Manim/PIL) — those
  are still built by the chat flow's sub-agents per `SKILL.md`; the overlay
  track here lets you retime/trim clips they already produced.
- A full keyframe/property-curve animation system — Ken Burns (one zoom/pan
  motion per clip) is the practical stand-in for an ffmpeg-filter-graph
  renderer; it is not arbitrary keyframing of position/scale/opacity.
- True pixel-accurate overlay/transition compositing in the live preview —
  the preview is a fast approximation; `helpers/render.py` (via ffmpeg) is
  always the source of truth for the actual output.
