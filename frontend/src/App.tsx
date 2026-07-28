import { useEffect, useMemo, useState } from "react";
import {
  api,
  type ConvertResult,
  type DetectedLibraries,
  type Direction,
  type LibraryPaths,
  type PlaylistNode,
  type Side,
} from "./api";
import { ApplyConfirm } from "./ApplyConfirm";
import { PathField } from "./PathField";
import { PreviewList } from "./PreviewList";
import {
  TreeView,
  collectPlaylistIds,
  useSelectedSummary,
} from "./TreeView";

type Tab = "connect" | "select" | "convert";

export default function App() {
  const [tab, setTab] = useState<Tab>("connect");
  const [detected, setDetected] = useState<DetectedLibraries | null>(null);
  const [paths, setPaths] = useState<LibraryPaths>({});
  const [direction, setDirection] = useState<Direction>("rekordbox_to_serato");
  const [tree, setTree] = useState<PlaylistNode[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<ConvertResult | null>(null);
  const [xmlOut, setXmlOut] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [healOnApply, setHealOnApply] = useState(false);

  const sourceSide: Side =
    direction === "rekordbox_to_serato" ? "rekordbox" : "serato";
  const sourceLabel = sourceSide === "rekordbox" ? "Rekordbox" : "Serato";
  const destLabel = sourceSide === "rekordbox" ? "Serato" : "Rekordbox";
  const selection = useSelectedSummary(tree, selectedIds);

  useEffect(() => {
    api
      .detect()
      .then((d) => {
        setDetected(d);
        setPaths((prev) => ({
          rekordbox_path: prev.rekordbox_path || d.rekordbox_candidates[0] || "",
          serato_path: prev.serato_path || d.serato_candidates[0] || "",
          music_root: prev.music_root || d.music_root_candidates[0] || "",
        }));
      })
      .catch((e) => setError(String(e.message || e)));
    api
      .status()
      .then((s) => {
        setPaths((prev) => ({
          rekordbox_path: s.rekordbox_path || prev.rekordbox_path,
          serato_path: s.serato_path || prev.serato_path,
          music_root: s.music_root || prev.music_root,
        }));
      })
      .catch(() => undefined);
  }, []);

  const canBrowse = useMemo(() => {
    if (direction === "rekordbox_to_serato") {
      return Boolean(paths.rekordbox_path && paths.serato_path);
    }
    return Boolean(paths.serato_path);
  }, [direction, paths]);

  function toggleNode(node: PlaylistNode) {
    const ids = collectPlaylistIds(node);
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const allSelected = ids.every((id) => next.has(id));
      if (allSelected) {
        ids.forEach((id) => next.delete(id));
      } else {
        ids.forEach((id) => next.add(id));
      }
      return next;
    });
    setPreview(null);
    setHealOnApply(false);
  }

  async function connectAndLoad() {
    setBusy(true);
    setError(null);
    try {
      const next = await api.connect({
        rekordbox_path: paths.rekordbox_path || undefined,
        serato_path: paths.serato_path || undefined,
        music_root: paths.music_root || undefined,
      });
      setPaths(next);
      const nodes = await api.tree(sourceSide);
      setTree(nodes);
      setSelectedIds(new Set());
      setPreview(null);
      setHealOnApply(false);
      setTab("select");
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  function changeDirection(next: Direction) {
    setDirection(next);
    setTree([]);
    setSelectedIds(new Set());
    setPreview(null);
    setHealOnApply(false);
    setTab("connect");
  }

  const applyIds = useMemo(() => {
    if (!preview) return selectedIds;
    return new Set(
      preview.playlists
        .map((pl) => pl.source_id)
        .filter((id) => selectedIds.has(id)),
    );
  }, [preview, selectedIds]);

  const missingTotal = useMemo(() => {
    if (!preview) return 0;
    return preview.playlists.reduce(
      (sum, pl) => (applyIds.has(pl.source_id) ? sum + pl.missing_count : sum),
      0,
    );
  }, [preview, applyIds]);

  function toggleInclude(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function runConvert(dryRun: boolean, healMissing = false) {
    const ids = preview
      ? preview.playlists
          .map((pl) => pl.source_id)
          .filter((id) => selectedIds.has(id))
      : Array.from(selectedIds);
    if (ids.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.convert({
        direction,
        playlist_ids: ids,
        dry_run: dryRun,
        output_xml_path: xmlOut || undefined,
        heal_missing: healMissing || healOnApply,
      });
      // Reason: keep unchecked playlists visible so the user can re-include them.
      setPreview((prev) => {
        if (!prev) return result;
        const inResult = new Set(result.playlists.map((pl) => pl.source_id));
        const skipped = prev.playlists.filter((pl) => !inResult.has(pl.source_id));
        if (skipped.length === 0) return result;
        return { ...result, playlists: [...result.playlists, ...skipped] };
      });
      if (healMissing || (result.heal && result.heal.healed > 0)) {
        setHealOnApply(true);
      }
      setTab("convert");
      if (!dryRun) {
        // Reason: land the user on the confirmation after a real write.
        window.requestAnimationFrame(() => {
          document.getElementById("apply-confirm-title")?.focus();
          window.scrollTo({ top: 0, behavior: "smooth" });
        });
      }
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const applied = Boolean(preview && !preview.dry_run);

  function startOver() {
    setSelectedIds(new Set());
    setPreview(null);
    setHealOnApply(false);
    setTab("connect");
  }

  function convertMore() {
    setPreview(null);
    setHealOnApply(false);
    setTab("select");
  }

  const tabs: { id: Tab; label: string; enabled: boolean }[] = [
    { id: "connect", label: "Connect", enabled: true },
    { id: "select", label: "Select", enabled: tree.length > 0 },
    {
      id: "convert",
      label: "Convert",
      enabled: selectedIds.size > 0 || preview !== null,
    },
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <h1 className="brand">DJ Playlist Converter</h1>
          <p className="brand-sub">
            {sourceLabel} → {destLabel} · local only
          </p>
        </div>
        <div className="segmented" role="group" aria-label="Conversion direction">
          <button
            type="button"
            aria-pressed={direction === "rekordbox_to_serato"}
            onClick={() => changeDirection("rekordbox_to_serato")}
          >
            Rekordbox → Serato
          </button>
          <button
            type="button"
            aria-pressed={direction === "serato_to_rekordbox"}
            onClick={() => changeDirection("serato_to_rekordbox")}
          >
            Serato → Rekordbox
          </button>
        </div>
      </header>

      <nav className="tabs" aria-label="Steps">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`tab${tab === t.id ? " active" : ""}`}
            disabled={!t.enabled}
            aria-current={tab === t.id ? "step" : undefined}
            onClick={() => t.enabled && setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="tab-panel">
        {tab === "connect" && (
          <section className="panel-simple" aria-label="Connect libraries">
            <h2>Connect libraries</h2>
            <p className="lead">
              Point at your Rekordbox and Serato folders, then load the source
              library.
            </p>

            <PathField
              id="rb"
              label="Rekordbox master.db or XML"
              value={paths.rekordbox_path || ""}
              placeholder="/Users/you/Library/Pioneer/rekordbox/master.db"
              candidates={detected?.rekordbox_candidates}
              onChange={(rekordbox_path) =>
                setPaths((p) => ({ ...p, rekordbox_path }))
              }
            />

            <PathField
              id="sr"
              label="Serato _Serato_ folder"
              value={paths.serato_path || ""}
              placeholder="/Users/you/Music/_Serato_"
              candidates={detected?.serato_candidates}
              onChange={(serato_path) => setPaths((p) => ({ ...p, serato_path }))}
            />

            <PathField
              id="music"
              label="Music root (for path checks & heal scan)"
              value={paths.music_root || ""}
              placeholder="/Users/you/Music"
              candidates={detected?.music_root_candidates}
              hint="Used to find moved files when tracks show as missing."
              onChange={(music_root) => setPaths((p) => ({ ...p, music_root }))}
            />

            <div className="row">
              <button
                type="button"
                className="primary"
                disabled={busy || !canBrowse}
                onClick={connectAndLoad}
              >
                {busy ? "Loading…" : `Load ${sourceLabel} →`}
              </button>
            </div>
            <p className="hint">
              Close Serato before applying crates. Serato → Rekordbox writes an
              XML file you import in Rekordbox.
            </p>
          </section>
        )}

        {tab === "select" && (
          <section className="panel-simple wide" aria-label="Select playlists">
            <div className="panel-head-row">
              <div>
                <h2>Select playlists</h2>
                <p className="lead">
                  Check one or more playlists. Folders select everything inside.
                </p>
              </div>
              <span className="pane-meta">
                {selection.count} selected · {selection.trackTotal} tracks
              </span>
            </div>

            <TreeView
              nodes={tree}
              selectedIds={selectedIds}
              onToggle={toggleNode}
            />

            <div className="row sticky-actions">
              <button
                type="button"
                className="ghost"
                onClick={() => setSelectedIds(new Set())}
                disabled={selectedIds.size === 0}
              >
                Clear
              </button>
              <button
                type="button"
                className="primary"
                disabled={selectedIds.size === 0 || busy}
                onClick={() => runConvert(true)}
              >
                Preview {selection.count || ""} →
              </button>
            </div>
          </section>
        )}

        {tab === "convert" && (
          <section className="panel-simple wide" aria-label="Convert">
            {applied && preview ? (
              <>
                <ApplyConfirm
                  direction={direction}
                  destLabel={destLabel}
                  playlists={preview.playlists.filter((pl) =>
                    selectedIds.has(pl.source_id),
                  )}
                  message={preview.message}
                  onConvertMore={convertMore}
                  onStartOver={startOver}
                />
                <details className="apply-details">
                  <summary>What was written</summary>
                  <PreviewList
                    playlists={preview.playlists}
                    includedIds={applyIds}
                    musicRootSet={Boolean(paths.music_root)}
                    busy
                    onToggleInclude={() => undefined}
                    onHeal={() => undefined}
                  />
                </details>
              </>
            ) : (
              <>
                <h2>Convert</h2>
                {!preview ? (
                  <p className="lead">
                    {selection.count} playlist{selection.count === 1 ? "" : "s"}{" "}
                    ready. Preview the mapping, then apply.
                  </p>
                ) : (
                  <div className="message warn" role="status">
                    {preview.message}
                  </div>
                )}

                {direction === "serato_to_rekordbox" && (
                  <div className="field">
                    <label htmlFor="xmlout">Output XML path</label>
                    <input
                      id="xmlout"
                      type="text"
                      value={xmlOut}
                      onChange={(e) => setXmlOut(e.target.value)}
                      placeholder="/Users/you/Music/dj-converter-export.xml"
                    />
                  </div>
                )}

                {preview && missingTotal > 0 && (
                  <div className="message warn heal-banner" role="status">
                    <div>
                      <strong>
                        {missingTotal} missing file
                        {missingTotal === 1 ? "" : "s"}
                      </strong>
                      <p className="hint" style={{ margin: "0.35rem 0 0" }}>
                        Scan your music root for matching filenames and rematch
                        tracks before applying.
                        {!paths.music_root &&
                          " Set a Music root on the Connect tab first."}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="primary"
                      disabled={busy || !paths.music_root}
                      onClick={() => runConvert(true, true)}
                    >
                      {busy ? "Scanning…" : "Scan & heal missing"}
                    </button>
                  </div>
                )}

                {preview?.heal && (
                  <p className="hint">
                    Last heal: indexed {preview.heal.scanned_files} files ·
                    rematched {preview.heal.healed}/{preview.heal.attempted}
                    {preview.heal.still_missing > 0
                      ? ` · ${preview.heal.still_missing} still missing`
                      : ""}
                    {preview.heal.ambiguous > 0
                      ? ` · ${preview.heal.ambiguous} ambiguous`
                      : ""}
                  </p>
                )}

                {preview && (
                  <PreviewList
                    playlists={preview.playlists}
                    includedIds={applyIds}
                    musicRootSet={Boolean(paths.music_root)}
                    busy={busy}
                    onToggleInclude={toggleInclude}
                    onHeal={() => runConvert(true, true)}
                  />
                )}

                <div className="row sticky-actions">
                  <button
                    type="button"
                    className="ghost"
                    onClick={() => setTab("select")}
                  >
                    ← Select
                  </button>
                  {!preview && (
                    <button
                      type="button"
                      className="primary"
                      disabled={selectedIds.size === 0 || busy}
                      onClick={() => runConvert(true)}
                    >
                      Preview
                    </button>
                  )}
                  <button
                    type="button"
                    className="primary"
                    disabled={applyIds.size === 0 || busy}
                    onClick={() =>
                      runConvert(false, healOnApply || missingTotal > 0)
                    }
                    title={
                      missingTotal > 0 || healOnApply
                        ? "Will scan & heal missing files, then write"
                        : undefined
                    }
                  >
                    {missingTotal > 0 || healOnApply
                      ? `Heal & apply ${applyIds.size} to ${destLabel}`
                      : `Apply ${applyIds.size} to ${destLabel}`}
                  </button>
                </div>
              </>
            )}
          </section>
        )}
      </main>

      <footer className="status-bar">
        <span className="row" style={{ margin: 0, gap: "0.45rem" }}>
          {busy ? (
            <>
              <span className="busy-dot" aria-hidden="true" />
              Working…
            </>
          ) : (
            "Nothing leaves this machine"
          )}
        </span>
        {error ? (
          <p className="error" role="alert">
            {error}
          </p>
        ) : (
          <span>
            {selection.count > 0
              ? `${selection.count} selected`
              : `${sourceLabel} → ${destLabel}`}
          </span>
        )}
      </footer>
    </div>
  );
}
