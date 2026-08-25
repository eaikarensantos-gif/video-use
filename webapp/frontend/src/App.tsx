import { useEffect, useState } from "react";
import { useEditor } from "./store";
import Toolbar from "./components/Toolbar";
import MediaBin from "./components/MediaBin";
import Player from "./components/Player";
import Timeline from "./components/Timeline";
import Inspector from "./components/Inspector";
import ExportModal from "./components/ExportModal";

export default function App() {
  const load = useEditor((s) => s.load);
  const loading = useEditor((s) => s.loading);
  const timeline = useEditor((s) => s.timeline);
  const playing = useEditor((s) => s.playing);
  const setPlaying = useEditor((s) => s.setPlaying);
  const playhead = useEditor((s) => s.playhead);
  const splitVideoClipAt = useEditor((s) => s.splitVideoClipAt);
  const selection = useEditor((s) => s.selection);
  const removeClip = useEditor((s) => s.removeClip);
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.code === "Space") {
        e.preventDefault();
        setPlaying(!playing);
      } else if (e.key === "s" || e.key === "S") {
        splitVideoClipAt(playhead);
      } else if ((e.key === "Delete" || e.key === "Backspace") && selection) {
        removeClip(selection.trackId, selection.clipId);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playing, playhead, selection, setPlaying, splitVideoClipAt, removeClip]);

  useEffect(() => {
    function beforeUnload(e: BeforeUnloadEvent) {
      if (useEditor.getState().dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, []);

  if (loading || !timeline) {
    return <div className="loading-screen">Loading project…</div>;
  }

  return (
    <div className="app">
      <Toolbar onExport={() => setExportOpen(true)} />
      <MediaBin />
      <Player />
      <Inspector />
      <Timeline />
      {exportOpen && <ExportModal onClose={() => setExportOpen(false)} />}
    </div>
  );
}
