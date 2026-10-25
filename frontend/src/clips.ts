import type { ClipCandidate } from "./types";

const TARGET_DURATIONS = [20, 30, 35] as const;
const CLIP_LABELS = ["Hook", "Story", "Payoff"] as const;

export const EXPECTED_CLIPS = TARGET_DURATIONS.map((duration, index) => ({
  index,
  label: CLIP_LABELS[index] ?? `Clip ${index + 1}`,
  target_duration: duration,
}));

export function clipsFromJob(payload: { clips?: ClipCandidate[] } | undefined): ClipCandidate[] {
  return payload?.clips ?? [];
}
