import { useEffect, useRef } from "react";
import type { ConvertPlaylistPreview, Direction } from "./api";

function fileName(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

interface Props {
  direction: Direction;
  destLabel: string;
  playlists: ConvertPlaylistPreview[];
  message: string;
  onConvertMore: () => void;
  onStartOver: () => void;
}

/**
 * Confirmation shown after a successful write (not dry-run).
 */
export function ApplyConfirm({
  direction,
  destLabel,
  playlists,
  message,
  onConvertMore,
  onStartOver,
}: Props) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const written = playlists.filter((pl) => pl.written_path);
  const count = written.length || playlists.length;
  const tracks = playlists.reduce((sum, pl) => sum + pl.track_count, 0);
  const toSerato = direction === "rekordbox_to_serato";

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const nextStep = toSerato
    ? "Close and re-open Serato so the new crates appear in your library."
    : "In Rekordbox: File → Import → rekordbox xml, then import the playlist.";

  const xmlPath =
    !toSerato && written[0]?.written_path ? written[0].written_path : null;

  return (
    <div
      className="apply-confirm"
      role="status"
      aria-live="polite"
      aria-labelledby="apply-confirm-title"
    >
      <p className="apply-confirm-kicker">Applied to {destLabel}</p>
      <h2
        id="apply-confirm-title"
        ref={headingRef}
        className="apply-confirm-title"
        tabIndex={-1}
      >
        Migration complete
      </h2>
      <p className="apply-confirm-lead">
        {count} playlist{count === 1 ? "" : "s"} · {tracks} tracks written.
      </p>
      <p className="apply-confirm-next">{nextStep}</p>
      {xmlPath && (
        <p className="apply-confirm-path" title={xmlPath}>
          XML: <code>{xmlPath}</code>
        </p>
      )}
      {written.length > 0 && toSerato && (
        <ul className="apply-confirm-list">
          {written.map((pl) => (
            <li key={pl.source_id} title={pl.written_path || undefined}>
              {pl.destination_name || fileName(pl.written_path || "")}
            </li>
          ))}
        </ul>
      )}
      <p className="hint apply-confirm-msg">{message}</p>
      <div className="apply-confirm-actions">
        <button type="button" className="primary" onClick={onConvertMore}>
          Convert more
        </button>
        <button type="button" className="ghost" onClick={onStartOver}>
          Start over
        </button>
      </div>
    </div>
  );
}
