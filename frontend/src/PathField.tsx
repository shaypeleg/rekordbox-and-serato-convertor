import { useEffect, useId, useRef, useState } from "react";

function shortPath(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  if (parts.length <= 3) return path;
  return `…/${parts.slice(-3).join("/")}`;
}

interface Props {
  id?: string;
  label: string;
  value: string;
  placeholder?: string;
  hint?: string;
  candidates?: string[];
  onChange: (value: string) => void;
}

/**
 * Shows the resolved path by default; Change opens edit + other detected locations.
 */
export function PathField({
  id: idProp,
  label,
  value,
  placeholder,
  hint,
  candidates = [],
  onChange,
}: Props) {
  const autoId = useId();
  const id = idProp || autoId;
  const inputRef = useRef<HTMLInputElement>(null);
  const [editing, setEditing] = useState(false);
  const others = candidates.filter((c) => c !== value);
  const showDisplay = Boolean(value) && !editing;

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  function pick(path: string) {
    onChange(path);
    setEditing(false);
  }

  function doneEditing() {
    if (value.trim()) setEditing(false);
  }

  return (
    <div className="field path-field">
      <label htmlFor={id}>{label}</label>

      {showDisplay ? (
        <div className="path-display">
          <code className="path-display-value" title={value}>
            {value}
          </code>
          <button type="button" className="ghost" onClick={() => setEditing(true)}>
            Change
          </button>
        </div>
      ) : (
        <>
          <input
            ref={inputRef}
            id={id}
            type="text"
            value={value}
            placeholder={placeholder}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                doneEditing();
              }
              if (e.key === "Escape" && value.trim()) {
                e.preventDefault();
                setEditing(false);
              }
            }}
            onBlur={() => {
              // Reason: keep edit open while choosing an alternate candidate.
              window.setTimeout(() => {
                if (document.activeElement?.closest(".path-field") === null) {
                  doneEditing();
                }
              }, 0);
            }}
          />
          {value.trim() && (
            <div className="path-edit-actions">
              <button type="button" className="ghost" onClick={doneEditing}>
                Done
              </button>
            </div>
          )}
          {others.length > 0 && (
            <div className="path-alts" role="list">
              <p className="hint">Other detected locations</p>
              {others.map((c) => (
                <button
                  key={c}
                  type="button"
                  className="path-alt"
                  role="listitem"
                  title={c}
                  onClick={() => pick(c)}
                >
                  {shortPath(c)}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}
