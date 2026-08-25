# video-use editor (visual UI)

A local, CapCut-style visual editor for video-use: a media bin, a real-time
player, and a multi-track timeline (video / text / overlay) with drag-to-trim,
split, transitions, per-clip color grade, and export — all in the browser.

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

## Quick start

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

## Frontend dev mode (hot reload)

```bash
# terminal 1
python webapp/backend/main.py --videos-dir /path/to/your/videos

# terminal 2
cd webapp/frontend && npm run dev   # http://localhost:5173, proxies /api and /media to :8756
```

## Editor basics

- **Media bin** (left) — drag a clip onto the video track, or double-click to append.
- **Player** (center top) — space to play/pause, scrub the transport bar or the timeline ruler.
- **Timeline** (bottom) — drag clip edges to trim, drag a clip to reorder, `S` to split at the playhead, `Delete` to remove the selected clip, `+ Text at playhead` to drop a title card.
- **Inspector** (right) — per-clip grade preset, transition-out type/duration, and text card styling.
- **Export** — preview (fast, 720p) or final (1080p, loudness-normalized), with a live render log and a download link when done.

## What's intentionally out of scope (v1)

- Generating new overlay animations (HyperFrames/Remotion/Manim/PIL) — those
  are still built by the chat flow's sub-agents per `SKILL.md`; the overlay
  track here lets you retime/trim clips they already produced.
- Uploading media through the browser — drop files into the videos folder
  directly, same as today.
- True pixel-accurate overlay/transition compositing in the live preview —
  the preview is a fast approximation; `helpers/render.py` (via ffmpeg) is
  always the source of truth for the actual output.
