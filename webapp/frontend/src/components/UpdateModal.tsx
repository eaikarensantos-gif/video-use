import { useEffect, useState } from "react";
import { api } from "../api";
import type { JobStatus, UpdateInfo } from "../types";

export default function UpdateModal({ info, onClose }: { info: UpdateInfo; onClose: () => void }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    const timer = window.setInterval(async () => {
      try {
        const status = await api.jobStatus<{ percent?: number; ready?: boolean }>(jobId);
        setProgress(status.result?.percent || 0);
        if (status.status === "done") {
          window.clearInterval(timer);
          setReady(true);
          setProgress(100);
        } else if (status.status === "error") {
          window.clearInterval(timer);
          setError(status.error || "Falha ao baixar a atualização.");
        }
      } catch (e) {
        window.clearInterval(timer);
        setError(e instanceof Error ? e.message : String(e));
      }
    }, 600);
    return () => window.clearInterval(timer);
  }, [jobId]);

  async function download() {
    if (!info.download_url) return;
    setError(null);
    try {
      const result = await api.downloadUpdate(info.download_url, info.digest);
      setJobId(result.job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function install() {
    setInstalling(true);
    setError(null);
    try {
      await api.installUpdate();
    } catch (e) {
      setInstalling(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="modal-backdrop">
      <div className="modal update-modal">
        <h2>Atualização disponível</h2>
        <p className="update-version">video-use {info.current_version} → {info.latest_version}</p>
        {info.notes && <div className="update-notes">{info.notes}</div>}
        {jobId && !ready && !error && (
          <div className="update-progress">
            <div className="update-progress-bar" style={{ width: `${progress}%` }} />
            <span>{progress}%</span>
          </div>
        )}
        {ready && <p className="update-ready">Download concluído. O app fechará e abrirá novamente.</p>}
        {error && <p className="update-error">{error}</p>}
        <div className="actions">
          <button onClick={onClose} disabled={installing}>Depois</button>
          {!jobId && <button className="primary" onClick={download}>Baixar atualização</button>}
          {ready && <button className="primary" onClick={install} disabled={installing}>{installing ? "Atualizando…" : "Atualizar e reiniciar"}</button>}
        </div>
      </div>
    </div>
  );
}
