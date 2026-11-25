// The shape of what `python -m core.status` prints.

export type StageStatus = "done" | "ready" | "blocked" | "waiting";

export type Who = "you" | "agent" | "code";

export type Stage = {
  id: string;
  who: Who;
  who_label: string;
  what: string;
  your_part: string;
  name: string;
  status: StageStatus;
  current: boolean;
  built: boolean;
  done: boolean;
  detail: string;
  problems: string[];
  command: string | null;
  // How the stage's outside calls went. Null for a stage that makes none.
  calls: { log_name: string; attempts: number; ok: number; failed: number; seconds: number; models: string[] } | null;
};

export type Source = {
  source_id: string;
  title: string | null;
  url: string;
  licence: string | null;
  words: number;
};

export type Fact = { id: string; source_id: string; text: string; quote: string };

export type Shot = {
  id: string;
  duration_s: number;
  size: string;
  image_prompt: string;
  use_reference: boolean;
  motion_prompt: string;
  reason: string;
  narration: Record<string, string>;
  subtitle_en: string;
  fact_ids: string[];
  seed: number;
};

export type Run = {
  ts: string;
  stage: string;
  item: string | null;
  model: string;
  attempt: number;
  status: string;
  latency_s: number;
  error: string;
};

// A generated file under the film's outputs folder. `v` changes whenever the file does.
export type MediaFile = { path: string; v: number; bytes: number };

export type Outputs = {
  reference: MediaFile | null;
  contact_sheet: MediaFile | null;
  shots: Record<
    string,
    {
      picture: MediaFile | null;
      narration: Record<
        string,
        MediaFile & { spoken_s: number | null; fits: boolean | null; model: string | null; heard: string | null; matches_line: boolean | null }
      >;
      clips: Record<string, MediaFile | null>;
      move: string | null;
    }
  >;
  // The same lines spoken by different providers: provider name, then shot id.
  voice_compare: Record<string, Record<string, MediaFile & { spoken_s: number | null; model: string | null }>>;
  radio_cut: { audio: MediaFile | null; video: MediaFile | null };
  music: {
    candidates: (MediaFile & { seed: number; seconds_to_make: number | null; audition: MediaFile | null })[];
    chosen_seed: number | null;
    gpu: string | null;
    gpu_seconds: number | null;
  };
  film: {
    shapes: Record<string, MediaFile & { duration_s: number; loudness_lufs: number; true_peak_db: number; subtitle_cards: number }>;
    placeholder_music: boolean | null;
    music: string | null;
  };
};

export type FilmState = {
  slug: string;
  brief: { title?: string; audience?: string; feeling?: string; languages?: string[] } | null;
  stages: Stage[];
  research: {
    subject: { description?: string; likeness_policy?: string; policy_reason?: string } | null;
    sources: Source[];
    facts: Fact[];
    facts_model: string | null;
  };
  storyboard: {
    languages: string[];
    voice: { name: string; style: string };
    style_block: string;
    world_block: string;
    reference_sheet: { prompt: string; seed: number };
    music: { caption: string; bpm: number; key: string; seeds: number[]; chosen_seed?: number };
    shots: Shot[];
    end_card: { text: string; duration_s: number };
  } | null;
  outputs: Outputs;
  runs: {
    attempts: number;
    ok: number;
    failed: number;
    model_calls: number;
    cost_usd: number;
    models: { model: string; ok: number; failed: number; median_latency_s: number | null }[];
    recent: Run[];
  };
};

export type FilmSummary = {
  slug: string;
  title: string;
  languages: string[];
  poster: MediaFile | null;
  has_film: boolean;
  description: string | null;
  stages: { id: string; name: string; status: StageStatus; who: Who }[];
  done: number;
  total: number;
  current: { name: string; status: StageStatus; detail: string; who: Who } | null;
  attempts: number;
  failed: number;
};

export type RepoState = {
  films: FilmSummary[];
  docs: { name: string; purpose: string; exists: boolean }[];
  experiments: { titles: string[]; target: number };
  failures: { titles: string[] };
};
