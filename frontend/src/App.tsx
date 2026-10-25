import { useCallback, useEffect, useRef, useState } from "react";
import { createJob, getHealth, getJob } from "./api";
import { clipsFromJob, EXPECTED_CLIPS } from "./clips";
import { STAGE_LABELS, STAGE_ORDER, stageIndex } from "./stages";
import type { Job } from "./types";

const POLL_INTERVAL_MS = 2000;

function classNames(...parts: Array<string | false | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

function isValidYouTubeUrl(url: string): boolean {
  try {
    const u = new URL(url.trim());
    if (!["http:", "https:"].includes(u.protocol)) return false;
    const host = u.hostname.replace(/^www\./, "");
    return (
      (host === "youtube.com" && (u.pathname === "/watch" || u.pathname.startsWith("/shorts/"))) ||
      host === "youtu.be" ||
      host === "youtube-nocookie.com"
    );
  } catch {
    return false;
  }
}

export default function App() {
  const [url, setUrl] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    getHealth().then((ok) => {
      if (active) setBackendOnline(ok);
    });
    return () => {
      active = false;
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();
      pollRef.current = window.setInterval(async () => {
        try {
          const updated = await getJob(jobId);
          setJob(updated);
          if (updated.status === "failed" || updated.status === "published") {
            stopPolling();
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Lost contact with the backend.");
          stopPolling();
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!isValidYouTubeUrl(url)) {
      setError("Please paste a valid YouTube video URL (youtube.com/watch or youtu.be).");
      return;
    }
    setSubmitting(true);
    setJob(null);
    try {
      const created = await createJob(url, { target_clips: [20, 30, 35] });
      setJob(created);
      startPolling(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the job.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    stopPolling();
    setJob(null);
    setUrl("");
    setError(null);
  };

  const clips = job ? clipsFromJob(job.payload) : [];
  const isFailed = job?.status === "failed";
  const isReady = job?.status === "review" || job?.status === "approved";
  const isProcessing = job ? !isFailed && !isReady && job.status !== "published" : false;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">
          <span className="brand-mark" aria-hidden>▶</span>
          <div>
            <h1>Content Engine</h1>
            <p className="tagline">AI short clips from your long-form videos</p>
          </div>
        </div>
        <BackendStatus online={backendOnline} />
      </header>

      <main className="app-main">
        <section className="card submit-card">
          <h2>Generate Clips</h2>
          <p className="hint">
            Paste a YouTube URL. We&apos;ll transcribe it, find the strongest moments, and produce
            three ready-to-post vertical clips: <strong>20s</strong>, <strong>30s</strong>, and{" "}
            <strong>35s</strong>.
          </p>
          <form onSubmit={handleSubmit} className="submit-form">
            <input
              type="url"
              inputMode="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              disabled={submitting || isProcessing}
              aria-label="YouTube video URL"
              className="url-input"
            />
            <button
              type="submit"
              disabled={submitting || isProcessing || !url.trim()}
              className="primary-btn"
            >
              {submitting ? "Starting…" : isProcessing ? "Processing…" : "Generate Clips"}
            </button>
          </form>
          {error && <div className="error-banner" role="alert">{error}</div>}
        </section>

        {job && (
          <section className="card job-card">
            <div className="job-header">
              <div>
                <h2>{STAGE_LABELS[job.status]}</h2>
                <p className="job-id">Job {job.id.slice(0, 8)}</p>
              </div>
              <div className="progress-ring" aria-label={`${job.progress}% complete`}>
                <ProgressRing value={job.progress} />
              </div>
            </div>

            <StageTracker currentStatus={job.status} />

            {isFailed && (
              <div className="error-banner" role="alert">
                <strong>Processing failed.</strong>{" "}
                {job.error_message ?? "An unexpected error occurred."}
                <button onClick={handleReset} className="text-btn">Try another video</button>
              </div>
            )}

            {isReady && clips.length > 0 && (
              <ClipsGrid clips={clips} />
            )}

            {isReady && clips.length === 0 && (
              <div className="notice">
                Clips were processed but no download links are available yet. The backend still needs
                the rendering pipeline to be enabled to produce final MP4 files.
              </div>
            )}

            {(isReady || isFailed) && (
              <button onClick={handleReset} className="secondary-btn">Start a new job</button>
            )}
          </section>
        )}

        {!job && (
          <section className="card expectation-card">
            <h3>What you&apos;ll get</h3>
            <div className="expectations">
              {EXPECTED_CLIPS.map((clip) => (
                <div key={clip.index} className="expectation">
                  <div className="expectation-dur">{clip.target_duration}s</div>
                  <div className="expectation-label">{clip.label}</div>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <p>
          You remain responsible for content rights and platform monetization eligibility. No income
          is guaranteed.
        </p>
      </footer>
    </div>
  );
}

function BackendStatus({ online }: { online: boolean | null }) {
  const label = online === null ? "Checking…" : online ? "Backend online" : "Backend offline";
  return (
    <span
      className={classNames("status-chip", online === false && "offline", online === true && "online")}
    >
      <span className="status-dot" aria-hidden />
      {label}
    </span>
  );
}

function ProgressRing({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(100, value));
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;
  return (
    <svg width="64" height="64" viewBox="0 0 64 64">
      <circle cx="32" cy="32" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={radius}
        fill="none"
        stroke="#38bdf8"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform="rotate(-90 32 32)"
        style={{ transition: "stroke-dashoffset 0.6s ease" }}
      />
      <text x="32" y="36" textAnchor="middle" fontSize="14" fill="#e2e8f0" fontWeight="600">
        {clamped}%
      </text>
    </svg>
  );
}

function StageTracker({ currentStatus }: { currentStatus: Job["status"] }) {
  const currentIdx = stageIndex(currentStatus);
  return (
    <ol className="stage-tracker">
      {STAGE_ORDER.map((status, index) => {
        const state = index < currentIdx ? "done" : index === currentIdx ? "active" : "pending";
        return (
          <li key={status} className={classNames("stage", state)}>
            <span className="stage-dot" aria-hidden />
            <span className="stage-label">{STAGE_LABELS[status]}</span>
          </li>
        );
      })}
    </ol>
  );
}

function ClipsGrid({ clips }: { clips: NonNullable<Job["payload"]["clips"]> }) {
  return (
    <div className="clips-grid">
      {clips.map((clip) => (
        <article key={clip.index} className="clip-card">
          <div className="clip-preview">
            {clip.download_url ? (
              <video
                src={clip.download_url}
                controls
                playsInline
                preload="metadata"
                aria-label={`Preview of ${clip.label} clip`}
              />
            ) : (
              <div className="clip-placeholder">
                <span>{clip.target_duration}s</span>
              </div>
            )}
          </div>
          <div className="clip-meta">
            <div className="clip-title">
              <span className="clip-badge">{clip.target_duration}s</span>
              <span>{clip.label}</span>
            </div>
            <p className="clip-reason">{clip.reason}</p>
            <p className="clip-range">
              {formatDuration(clip.start)} – {formatDuration(clip.end)}
            </p>
            {clip.download_url ? (
              <a
                href={clip.download_url}
                download
                className="primary-btn small"
              >
                Download MP4
              </a>
            ) : (
              <span className="muted">Download available once rendering completes</span>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
