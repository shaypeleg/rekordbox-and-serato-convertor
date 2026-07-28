import { useMemo, useState } from "react";
import type { ConvertPlaylistPreview, ConvertTrackPreview } from "./api";

function fileName(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

/** Last 2 path segments for a shorter mapped view. */
function shortTail(path: string, segments = 2): string {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  if (parts.length <= segments) return parts.join("/");
  return parts.slice(-segments).join("/");
}

interface Props {
  playlists: ConvertPlaylistPreview[];
  includedIds: Set<string>;
  musicRootSet: boolean;
  busy: boolean;
  onToggleInclude: (id: string) => void;
  onHeal: () => void;
}

export function PreviewList({
  playlists,
  includedIds,
  musicRootSet,
  busy,
  onToggleInclude,
  onHeal,
}: Props) {
  const [openIds, setOpenIds] = useState<Set<string>>(() => new Set());

  const totals = useMemo(() => {
    return playlists.reduce(
      (acc, pl) => {
        const included = includedIds.has(pl.source_id);
        if (included) {
          acc.included += 1;
          acc.tracks += pl.track_count;
          acc.missing += pl.missing_count;
          acc.healed += pl.healed_count ?? 0;
        } else {
          acc.skipped += 1;
        }
        return acc;
      },
      { included: 0, skipped: 0, tracks: 0, missing: 0, healed: 0 },
    );
  }, [playlists, includedIds]);

  function toggleOpen(id: string) {
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="preview-list">
      <div className="preview-summary">
        <span>
          {totals.included} of {playlists.length} will import · {totals.tracks}{" "}
          tracks
        </span>
        {totals.skipped > 0 && (
          <span className="muted-inline"> · {totals.skipped} skipped</span>
        )}
        {totals.missing > 0 ? (
          <span className="missing"> · {totals.missing} missing</span>
        ) : totals.included > 0 ? (
          <span className="ok-text"> · all found</span>
        ) : null}
        {totals.healed > 0 && (
          <span className="healed-text"> · {totals.healed} healed</span>
        )}
      </div>

      <ul className="preview-rows">
        {playlists.map((pl) => {
          const open = openIds.has(pl.source_id);
          const included = includedIds.has(pl.source_id);
          const label = pl.source_path.join(" / ") || pl.source_name;
          const checkId = `include-${pl.source_id}`;
          return (
            <li
              key={pl.source_id}
              className={`preview-row${included ? "" : " preview-row-skipped"}`}
            >
              <div className="preview-row-main">
                <label className="preview-include" htmlFor={checkId}>
                  <input
                    id={checkId}
                    type="checkbox"
                    className="tree-check"
                    checked={included}
                    disabled={busy}
                    onChange={() => onToggleInclude(pl.source_id)}
                  />
                  <span className="sr-only">Include in import</span>
                </label>
                <button
                  type="button"
                  className="preview-row-toggle"
                  aria-expanded={open}
                  onClick={() => toggleOpen(pl.source_id)}
                >
                  <span className="chevron" aria-hidden="true">
                    {open ? "▾" : "▸"}
                  </span>
                  <span className="preview-row-name">{label}</span>
                  <span className="preview-row-meta">
                    {!included ? (
                      <span className="muted-inline">skipped</span>
                    ) : (
                      <>
                        {pl.track_count}
                        {pl.missing_count > 0 ? (
                          <span className="missing">
                            {" "}
                            · {pl.missing_count} missing
                          </span>
                        ) : (
                          <span className="ok-text"> · ok</span>
                        )}
                        {(pl.healed_count ?? 0) > 0 && (
                          <span className="healed-text">
                            {" "}
                            · {pl.healed_count} healed
                          </span>
                        )}
                      </>
                    )}
                  </span>
                </button>
                {included && pl.missing_count > 0 && (
                  <button
                    type="button"
                    className="ghost preview-row-heal"
                    disabled={busy || !musicRootSet}
                    onClick={onHeal}
                  >
                    Heal
                  </button>
                )}
              </div>

              {open && (
                <div className="preview-detail">
                  <p className="hint preview-dest">
                    → {pl.destination_name}
                    {pl.written_path ? ` · wrote ${fileName(pl.written_path)}` : ""}
                  </p>
                  <TrackList tracks={pl.tracks} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function TrackRow({ track, index }: { track: ConvertTrackPreview; index: number }) {
  const name = fileName(track.source_path);
  const mapped = track.destination_path
    ? shortTail(track.destination_path, 3)
    : null;
  const className = track.missing
    ? "track-item missing"
    : track.healed
      ? "track-item healed-text"
      : "track-item";

  return (
    <li
      key={`${track.source_path}-${index}`}
      className={className}
      title={
        track.destination_path
          ? `${track.source_path}\n→ ${track.destination_path}`
          : track.source_path
      }
    >
      <span className="track-name">{name}</span>
      {track.healed && <span className="track-tag">healed</span>}
      {track.missing && <span className="track-tag">missing</span>}
      {mapped && !track.missing && (
        <span className="track-mapped">→ {mapped}</span>
      )}
    </li>
  );
}

function TrackList({ tracks }: { tracks: ConvertTrackPreview[] }) {
  if (tracks.length === 0) {
    return <p className="hint">No track details in this preview sample.</p>;
  }

  const missing = tracks.filter((t) => t.missing);
  const primary = missing.length > 0 ? missing : tracks;

  return (
    <div className="track-list">
      {missing.length > 0 ? (
        <p className="hint">
          {missing.length} missing
          {missing.length < tracks.length
            ? ` · ${tracks.length} tracks listed`
            : ""}
        </p>
      ) : (
        <p className="hint">Filename · mapped folder (hover for full path)</p>
      )}
      <ul>
        {primary.map((t, i) => (
          <TrackRow key={`p-${t.source_path}-${i}`} track={t} index={i} />
        ))}
      </ul>
      {missing.length > 0 && missing.length < tracks.length && (
        <details className="track-all">
          <summary>Show all {tracks.length} listed tracks</summary>
          <ul>
            {tracks.map((t, i) => (
              <TrackRow key={`a-${t.source_path}-${i}`} track={t} index={i} />
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
