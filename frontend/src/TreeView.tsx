import { useMemo, useState } from "react";
import type { PlaylistNode } from "./api";

interface Props {
  nodes: PlaylistNode[];
  selectedIds: Set<string>;
  onToggle: (node: PlaylistNode) => void;
  depth?: number;
}

/** Collect playlist leaf ids under a node (inclusive if playlist). */
export function collectPlaylistIds(node: PlaylistNode): string[] {
  if (node.kind === "playlist") return [node.id];
  return node.children.flatMap(collectPlaylistIds);
}

export function findNodeById(
  nodes: PlaylistNode[],
  id: string,
): PlaylistNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    const found = findNodeById(node.children, id);
    if (found) return found;
  }
  return null;
}

function folderCheckState(
  node: PlaylistNode,
  selectedIds: Set<string>,
): "checked" | "unchecked" | "indeterminate" {
  const ids = collectPlaylistIds(node);
  if (ids.length === 0) return "unchecked";
  const selected = ids.filter((id) => selectedIds.has(id)).length;
  if (selected === 0) return "unchecked";
  if (selected === ids.length) return "checked";
  return "indeterminate";
}

export function TreeView({
  nodes,
  selectedIds,
  onToggle,
  depth = 0,
}: Props) {
  const [open, setOpen] = useState<Record<string, boolean>>({});

  if (nodes.length === 0) {
    return (
      <div className="tree">
        <p className="tree-empty">Load a library on the Connect tab first.</p>
      </div>
    );
  }

  return (
    <div
      className="tree"
      role="tree"
      aria-label="Library playlists"
      aria-multiselectable="true"
    >
      {nodes.map((node) => {
        const isFolder = node.kind === "folder";
        const expanded = open[node.id] ?? depth < 1;
        const check = isFolder
          ? folderCheckState(node, selectedIds)
          : selectedIds.has(node.id)
            ? "checked"
            : "unchecked";

        return (
          <div key={node.id} role="group">
            <div
              className={`tree-item${check !== "unchecked" ? " selected" : ""}`}
              style={{ paddingLeft: `${0.45 + depth * 0.85}rem` }}
              role="treeitem"
              aria-expanded={isFolder ? expanded : undefined}
              aria-selected={check === "checked"}
            >
              <button
                type="button"
                className="tree-expand"
                aria-label={
                  isFolder
                    ? expanded
                      ? `Collapse ${node.name}`
                      : `Expand ${node.name}`
                    : undefined
                }
                tabIndex={isFolder ? 0 : -1}
                onClick={() => {
                  if (!isFolder) return;
                  setOpen((prev) => ({ ...prev, [node.id]: !expanded }));
                }}
              >
                <span className="chevron" aria-hidden="true">
                  {isFolder ? (expanded ? "▾" : "▸") : ""}
                </span>
              </button>
              <input
                type="checkbox"
                className="tree-check"
                checked={check === "checked"}
                ref={(el) => {
                  if (el) el.indeterminate = check === "indeterminate";
                }}
                onChange={() => onToggle(node)}
                aria-label={`Select ${node.name}`}
              />
              <span className="name">{node.name}</span>
              <span className="meta">{node.track_count}</span>
            </div>
            {isFolder && expanded && node.children.length > 0 && (
              <TreeView
                nodes={node.children}
                selectedIds={selectedIds}
                onToggle={onToggle}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export function useSelectedSummary(
  tree: PlaylistNode[],
  selectedIds: Set<string>,
): { count: number; trackTotal: number; names: string[] } {
  return useMemo(() => {
    const names: string[] = [];
    let trackTotal = 0;
    const walk = (nodes: PlaylistNode[]) => {
      for (const n of nodes) {
        if (n.kind === "playlist" && selectedIds.has(n.id)) {
          names.push(n.path.join(" / ") || n.name);
          trackTotal += n.track_count;
        }
        walk(n.children || []);
      }
    };
    walk(tree);
    return { count: names.length, trackTotal, names };
  }, [tree, selectedIds]);
}
