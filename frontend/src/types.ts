export type JobStatus =
  | "queued"
  | "downloading"
  | "transcribing"
  | "analyzing"
  | "rendering"
  | "captioning"
  | "metadata"
  | "review"
  | "approved"
  | "publishing"
  | "published"
  | "failed";

export interface JobPayload {
  niche?: string;
  language?: string;
  attempts?: number;
  acquisition?: {
    asset_ref: string;
    filename: string;
    media_type: string;
    size_bytes: number;
    duration_seconds?: number;
    width?: number;
    height?: number;
    probed: boolean;
    title?: string;
    extractor?: string;
  };
  transcript?: { language?: string; segments: TranscriptSegment[] };
  clips?: ClipCandidate[];
  error?: string;
  recovery?: { reason: string; requeued_at: string };
}

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
}

export interface ClipCandidate {
  index: number;
  label: string;
  target_duration: number;
  start: number;
  end: number;
  reason: string;
  score: number;
  asset_ref?: string;
  download_url?: string;
}

export interface Job {
  id: string;
  source_url: string;
  status: JobStatus;
  progress: number;
  error_message: string | null;
  payload: JobPayload;
  created_at: string;
  updated_at: string;
}

export interface JobList {
  items: Job[];
  total: number;
}

export interface ApiError {
  error: { code: string; message: string; details?: unknown };
}
