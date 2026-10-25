import type { JobStatus } from "./types";

export const STAGE_ORDER: JobStatus[] = [
  "queued",
  "downloading",
  "transcribing",
  "analyzing",
  "rendering",
  "captioning",
  "metadata",
  "review",
];

export const STAGE_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  downloading: "Downloading source",
  transcribing: "Transcribing audio",
  analyzing: "AI selecting moments",
  rendering: "Rendering vertical clips",
  captioning: "Burning in captions",
  metadata: "Generating metadata",
  review: "Ready for review",
  approved: "Approved",
  publishing: "Publishing",
  published: "Published",
  failed: "Failed",
};

export function stageIndex(status: JobStatus): number {
  const i = STAGE_ORDER.indexOf(status);
  return i === -1 ? STAGE_ORDER.length : i;
}

export function isTerminal(status: JobStatus): boolean {
  return status === "failed" || status === "published";
}

export function isProcessing(status: JobStatus): boolean {
  return !isTerminal(status) && status !== "review" && status !== "approved";
}
