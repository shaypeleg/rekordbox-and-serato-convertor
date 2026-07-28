import { useEffect, useRef, useState } from "react";
import { api, type ConvertPlaylistPreview, type Direction } from "./api";

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
  const [copied, setCopied] = useState(false);
  const [revealError, setRevealError] = useState<string | null>(null);
  const written = playlists.filter((pl) => pl.written_path);
  const count = written.length || playlists.length;
  const tracks = playlists.reduce((sum, pl) => sum + pl.track_count, 0);
  const toSerato = direction === "rekordbox_to_serato";
  const xmlPath =
    !toSerato && written[0]?.written_path ? written[0].written_path : null;

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  async function copyPath() {
    if (!xmlPath) return;
    try {
      await navigator.clipboard.writeText(xmlPath);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setRevealError("Could not copy path — select it manually.");
    }
  }

  async function revealInFinder() {
    if (!xmlPath) return;
    setRevealError(null);
    try {
      await api.reveal(xmlPath);
    } catch (e) {
      setRevealError(String((e as Error).message || e));
    }
  }

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
        {toSerato ? "Migration complete" : "XML export ready"}
      </h2>
      <p className="apply-confirm-lead">
        {count} playlist{count === 1 ? "" : "s"} · {tracks} tracks
        {toSerato ? " written." : " exported."}
      </p>

      {toSerato ? (
        <p className="apply-confirm-next">
          Close and re-open Serato so the new crates appear in your library.
        </p>
      ) : (
        <div className="apply-confirm-steps">
          <p className="apply-confirm-next">
            Rekordbox does <strong>not</strong> pick this up automatically. Point
            it at the XML file, then drag playlists into your library:
          </p>
          <ol>
            <li>
              Rekordbox → <strong>Preferences → Advanced → Database</strong>
            </li>
            <li>
              Under <strong>rekordbox xml → Imported Library</strong>, Browse to:
            </li>
          </ol>
          {xmlPath && (
            <p className="apply-confirm-path" title={xmlPath}>
              <code>{xmlPath}</code>
            </p>
          )}
          <ol start={3}>
            <li>
              Preferences → <strong>View → Layout</strong> → enable{" "}
              <strong>rekordbox xml</strong>
            </li>
            <li>
              In the browser tree open <strong>rekordbox xml → Playlists</strong>,
              then drag your playlist into <strong>Playlists</strong>
            </li>
          </ol>
          <div className="apply-confirm-actions path-actions">
            <button type="button" className="primary" onClick={revealInFinder}>
              Show XML in Finder
            </button>
            <button type="button" className="ghost" onClick={copyPath}>
              {copied ? "Copied" : "Copy path"}
            </button>
          </div>
          {revealError && (
            <p className="error" role="alert">
              {revealError}
            </p>
          )}
        </div>
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
