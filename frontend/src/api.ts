export type Side = "rekordbox" | "serato";
export type Direction = "rekordbox_to_serato" | "serato_to_rekordbox";

export interface PlaylistNode {
  id: string;
  name: string;
  kind: "folder" | "playlist";
  path: string[];
  track_count: number;
  children: PlaylistNode[];
  tracks?: TrackRef[] | null;
}

export interface TrackRef {
  path_absolute?: string | null;
  path_relative?: string | null;
  missing: boolean;
  title?: string | null;
  artist?: string | null;
}

export interface DetectedLibraries {
  rekordbox_candidates: string[];
  serato_candidates: string[];
  music_root_candidates: string[];
}

export interface LibraryPaths {
  rekordbox_path?: string | null;
  rekordbox_kind?: string | null;
  serato_path?: string | null;
  music_root?: string | null;
}

export interface ConvertTrackPreview {
  source_path: string;
  destination_path?: string | null;
  missing: boolean;
  healed?: boolean;
}

export interface ConvertPlaylistPreview {
  source_id: string;
  source_name: string;
  source_path: string[];
  destination_name: string;
  track_count: number;
  missing_count: number;
  healed_count?: number;
  tracks: ConvertTrackPreview[];
  backup_path?: string | null;
  written_path?: string | null;
}

export interface HealSummary {
  scanned_files: number;
  attempted: number;
  healed: number;
  still_missing: number;
  ambiguous: number;
  scan_roots: string[];
}

export interface ConvertResult {
  direction: Direction;
  dry_run: boolean;
  playlists: ConvertPlaylistPreview[];
  message: string;
  heal?: HealSummary | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  detect: () => request<DetectedLibraries>("/api/libraries/detect"),
  status: () => request<LibraryPaths>("/api/libraries/status"),
  connect: (body: Partial<LibraryPaths>) =>
    request<LibraryPaths>("/api/libraries/connect", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  tree: (side: Side) => request<PlaylistNode[]>(`/api/source/tree?side=${side}`),
  convert: (body: {
    direction: Direction;
    playlist_ids: string[];
    dry_run: boolean;
    output_xml_path?: string;
    heal_missing?: boolean;
  }) =>
    request<ConvertResult>("/api/convert", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
