import { useState, useCallback, useRef } from "react";

const API = "http://localhost:5000/diff/pdf";

// ── Word-level Myers diff ─────────────────────────────────────────────────────

// Tokenise preserving whitespace as separate tokens
function tokenise(text) {
  return text.split(/(\s+)/).filter((t) => t.length > 0);
}

// Normalise for comparison: strip trailing punctuation + lowercase
// so "new" matches "new." and "guess," matches "guess"
function normalise(tok) {
  return tok
    .toLowerCase()
    .replace(/[.,!?;:)(\'"+\-]+$/, "")
    .replace(/^[.,!?;:)(\'"+\-]+/, "");
}

function myersDiff(a, b, keyFn = (x) => x) {
  const frontier = { 1: { x: 0, history: [] } };
  const aMax = a.length,
    bMax = b.length;
  for (let d = 0; d <= aMax + bMax; d++) {
    for (let k = -d; k <= d; k += 2) {
      const goDown =
        k === -d ||
        (k !== d && (frontier[k - 1]?.x ?? -1) < (frontier[k + 1]?.x ?? -1));
      let x, history;
      if (goDown) {
        x = frontier[k + 1]?.x ?? 0;
        history = [...(frontier[k + 1]?.history ?? [])];
      } else {
        x = (frontier[k - 1]?.x ?? 0) + 1;
        history = [...(frontier[k - 1]?.history ?? [])];
      }
      let y = x - k;
      if (goDown && y >= 1 && y <= bMax)
        history.push({ type: "insert", text: b[y - 1] });
      else if (!goDown && x >= 1 && x <= aMax)
        history.push({ type: "remove", text: a[x - 1] });
      while (x < aMax && y < bMax && keyFn(a[x]) === keyFn(b[y])) {
        x++;
        y++;
        history.push({ type: "keep", text: a[x - 1] });
      }
      if (x >= aMax && y >= bMax) return history;
      frontier[k] = { x, history };
    }
  }
  return a
    .map((t) => ({ type: "remove", text: t }))
    .concat(b.map((t) => ({ type: "insert", text: t })));
}

function wordDiff(oldText, newText) {
  return myersDiff(tokenise(oldText), tokenise(newText), normalise);
}

function similarity(a, b) {
  const longer = Math.max(a.length, b.length);
  if (longer === 0) return 1;
  let common = 0;
  const shorter = a.length < b.length ? a : b;
  const other = a.length < b.length ? b : a;
  for (let i = 0; i < shorter.length; i++)
    if (shorter[i] === other[i]) common++;
  return common / longer;
}

// ── Inline token renderer ─────────────────────────────────────────────────────

function InlineTokens({ tokens, side }) {
  return (
    <span>
      {tokens.map((tok, i) => {
        if (tok.type === "keep") return <span key={i}>{tok.text}</span>;
        if (tok.type === "remove" && side === "left")
          return (
            <mark
              key={i}
              style={{
                background: "#ffd7d7",
                color: "#c00",
                borderRadius: 2,
                padding: "0 1px",
              }}
            >
              {tok.text}
            </mark>
          );
        if (tok.type === "insert" && side === "right")
          return (
            <mark
              key={i}
              style={{
                background: "#d4f7d4",
                color: "#1a6e1a",
                borderRadius: 2,
                padding: "0 1px",
              }}
            >
              {tok.text}
            </mark>
          );
        return null;
      })}
    </span>
  );
}

// ── Side-by-side diff ─────────────────────────────────────────────────────────

function SideBySide({ diff }) {
  const rows = [];
  let i = 0;
  while (i < diff.length) {
    const cur = diff[i];
    if (cur.type === "keep") {
      rows.push({ type: "keep", left: cur.text, right: cur.text });
      i++;
    } else if (cur.type === "remove") {
      const next = diff[i + 1];
      if (next?.type === "insert") {
        rows.push({ type: "change", left: cur.text, right: next.text });
        i += 2;
      } else {
        rows.push({ type: "remove", left: cur.text, right: null });
        i++;
      }
    } else {
      rows.push({ type: "insert", left: null, right: cur.text });
      i++;
    }
  }

  const cell = {
    padding: "6px 12px",
    fontSize: 13,
    lineHeight: 1.6,
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    borderBottom: "1px solid #e5e7eb",
    verticalAlign: "top",
    textAlign: "left",
    fontFamily: "inherit",
  };

  return (
    <table
      style={{
        width: "100%",
        borderCollapse: "collapse",
        tableLayout: "fixed",
      }}
    >
      <colgroup>
        <col style={{ width: "50%" }} />
        <col style={{ width: "50%" }} />
      </colgroup>
      <thead>
        <tr style={{ borderBottom: "2px solid #111" }}>
          <th
            style={{
              ...cell,
              fontWeight: 600,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#555",
              background: "#fafafa",
            }}
          >
            PDF A — Original
          </th>
          <th
            style={{
              ...cell,
              fontWeight: 600,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#555",
              background: "#fafafa",
              borderLeft: "1px solid #e5e7eb",
            }}
          >
            PDF B — Modified
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row, idx) => {
          if (row.type === "keep") {
            return (
              <tr key={idx}>
                <td style={{ ...cell, color: "#374151" }}>{row.left}</td>
                <td
                  style={{
                    ...cell,
                    color: "#374151",
                    borderLeft: "1px solid #e5e7eb",
                  }}
                >
                  {row.right}
                </td>
              </tr>
            );
          }
          if (row.type === "remove") {
            return (
              <tr key={idx} style={{ background: "#fff5f5" }}>
                <td style={{ ...cell, color: "#b91c1c" }}>
                  <span
                    style={{
                      userSelect: "none",
                      marginRight: 6,
                      opacity: 0.4,
                      fontSize: 11,
                    }}
                  >
                    −
                  </span>
                  {row.left}
                </td>
                <td
                  style={{
                    ...cell,
                    borderLeft: "1px solid #e5e7eb",
                    color: "#9ca3af",
                  }}
                />
              </tr>
            );
          }
          if (row.type === "insert") {
            return (
              <tr key={idx} style={{ background: "#f0fdf4" }}>
                <td style={{ ...cell, color: "#9ca3af" }} />
                <td
                  style={{
                    ...cell,
                    color: "#15803d",
                    borderLeft: "1px solid #e5e7eb",
                  }}
                >
                  <span
                    style={{
                      userSelect: "none",
                      marginRight: 6,
                      opacity: 0.4,
                      fontSize: 11,
                    }}
                  >
                    +
                  </span>
                  {row.right}
                </td>
              </tr>
            );
          }

          // change row — word-level diff
          const sim = similarity(row.left, row.right);
          const tokens = sim > 0.3 ? wordDiff(row.left, row.right) : null;

          return (
            <tr key={idx}>
              <td style={{ ...cell, background: "#fff5f5" }}>
                <span
                  style={{
                    userSelect: "none",
                    marginRight: 6,
                    opacity: 0.4,
                    fontSize: 11,
                    color: "#b91c1c",
                  }}
                >
                  −
                </span>
                {tokens ? (
                  <InlineTokens tokens={tokens} side="left" />
                ) : (
                  <span style={{ color: "#b91c1c" }}>{row.left}</span>
                )}
              </td>
              <td
                style={{
                  ...cell,
                  background: "#f0fdf4",
                  borderLeft: "1px solid #e5e7eb",
                }}
              >
                <span
                  style={{
                    userSelect: "none",
                    marginRight: 6,
                    opacity: 0.4,
                    fontSize: 11,
                    color: "#15803d",
                  }}
                >
                  +
                </span>
                {tokens ? (
                  <InlineTokens tokens={tokens} side="right" />
                ) : (
                  <span style={{ color: "#15803d" }}>{row.right}</span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Layout changes ────────────────────────────────────────────────────────────

function LayoutChanges({ changes }) {
  if (!changes.length)
    return (
      <p style={{ color: "#6b7280", fontSize: 13 }}>
        No layout or style changes detected.
      </p>
    );

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ borderBottom: "2px solid #111" }}>
          {["Type", "Text", "Detail"].map((h) => (
            <th
              key={h}
              style={{
                padding: "6px 12px",
                textAlign: "left",
                fontWeight: 600,
                fontSize: 12,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#555",
              }}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {changes.map((c, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #e5e7eb" }}>
            <td
              style={{
                padding: "8px 12px",
                color: "#374151",
                whiteSpace: "nowrap",
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.04em",
                  color: c.type === "layout_change" ? "#92400e" : "#1e40af",
                  background:
                    c.type === "layout_change" ? "#fef3c7" : "#dbeafe",
                  padding: "2px 7px",
                  borderRadius: 3,
                }}
              >
                {c.type === "layout_change" ? "Position" : "Font"}
              </span>
            </td>
            <td
              style={{ padding: "8px 12px", color: "#374151", maxWidth: 320 }}
            >
              {c.text}
            </td>
            <td
              style={{
                padding: "8px 12px",
                color: "#6b7280",
                fontFamily: "monospace",
                fontSize: 12,
              }}
            >
              {c.type === "layout_change" ? (
                <>
                  y: {c.old_bbox[1].toFixed(0)} → {c.new_bbox[1].toFixed(0)}
                </>
              ) : (
                <>
                  {c.old_font} → {c.new_font}
                </>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ── Metadata ──────────────────────────────────────────────────────────────────

function MetaView({ metadata }) {
  const fields = [
    "title",
    "author",
    "producer",
    "pages",
    "is_encrypted",
    "creation_date",
    "modification_date",
  ];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
      <thead>
        <tr style={{ borderBottom: "2px solid #111" }}>
          <th
            style={{
              padding: "6px 12px",
              textAlign: "left",
              fontWeight: 600,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#555",
              width: 160,
            }}
          >
            Field
          </th>
          <th
            style={{
              padding: "6px 12px",
              textAlign: "left",
              fontWeight: 600,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#555",
            }}
          >
            PDF A
          </th>
          <th
            style={{
              padding: "6px 12px",
              textAlign: "left",
              fontWeight: 600,
              fontSize: 12,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#555",
            }}
          >
            PDF B
          </th>
        </tr>
      </thead>
      <tbody>
        {fields.map((f) => {
          const va = String(metadata.pdf_a[f] ?? "—");
          const vb = String(metadata.pdf_b[f] ?? "—");
          const diff = va !== vb;
          return (
            <tr
              key={f}
              style={{
                borderBottom: "1px solid #e5e7eb",
                background: diff ? "#fffbeb" : "transparent",
              }}
            >
              <td
                style={{
                  padding: "7px 12px",
                  color: "#6b7280",
                  fontWeight: 500,
                }}
              >
                {f}
              </td>
              <td
                style={{
                  padding: "7px 12px",
                  color: "#111",
                  fontFamily: "monospace",
                }}
              >
                {va}
              </td>
              <td
                style={{
                  padding: "7px 12px",
                  color: diff ? "#92400e" : "#111",
                  fontFamily: "monospace",
                  fontWeight: diff ? 600 : 400,
                }}
              >
                {vb}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

// ── Drop zone ─────────────────────────────────────────────────────────────────

function DropZone({ label, file, onFile }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef();

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragging(false);
      const f = e.dataTransfer.files[0];
      if (f?.type === "application/pdf") onFile(f);
    },
    [onFile],
  );

  return (
    <div
      onClick={() => inputRef.current.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      style={{
        border: `1px solid ${dragging ? "#111" : file ? "#111" : "#d1d5db"}`,
        borderRadius: 4,
        padding: "20px 16px",
        textAlign: "center",
        cursor: "pointer",
        background: dragging ? "#f9fafb" : "#fff",
        transition: "border-color .15s",
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        style={{ display: "none" }}
        onChange={(e) => e.target.files[0] && onFile(e.target.files[0])}
      />
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          color: "#374151",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      {file ? (
        <div style={{ fontSize: 13, color: "#111" }}>
          {file.name}{" "}
          <span style={{ color: "#9ca3af" }}>
            ({(file.size / 1024).toFixed(1)} KB)
          </span>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "#9ca3af" }}>
          Drop or click to select
        </div>
      )}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "diff", label: "Diff" },
  { id: "layout_changes", label: "Layout" },
  { id: "metadata", label: "Metadata" },
];

export default function PDFDiff() {
  const [pdfA, setPdfA] = useState(null);
  const [pdfB, setPdfB] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("diff");

  const compare = useCallback(async () => {
    if (!pdfA || !pdfB) return;
    setLoading(true);
    setError(null);
    setResult(null);
    const form = new FormData();
    form.append("pdf_a", pdfA);
    form.append("pdf_b", pdfB);
    try {
      const res = await fetch(API, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Server error");
      setResult(data);
      setActiveTab("diff");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [pdfA, pdfB]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#fff",
        color: "#111",
        fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
        fontSize: 14,
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      {/* Top bar */}
      <div style={{ borderBottom: "1px solid #e5e7eb", padding: "0 32px" }}>
        <div
          style={{
            maxWidth: 1100,
            margin: "0 auto",
            height: 48,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{ fontWeight: 600, fontSize: 14, letterSpacing: "-0.01em" }}
          >
            PDF Diff
          </span>
          {result && (
            <span style={{ fontSize: 12, color: "#6b7280" }}>
              {result.identical_bytes
                ? "Files are identical"
                : `${result.stats.additions} added · ${result.stats.removals} removed · ${result.stats.unchanged} unchanged`}
            </span>
          )}
        </div>
      </div>

      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "32px 32px" }}>
        {/* Upload + button row */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr auto",
            gap: 12,
            alignItems: "end",
            marginBottom: 32,
          }}
        >
          <DropZone label="Original" file={pdfA} onFile={setPdfA} />
          <DropZone label="Modified" file={pdfB} onFile={setPdfB} />
          <button
            onClick={compare}
            disabled={!pdfA || !pdfB || loading}
            style={{
              padding: "0 24px",
              height: 64,
              borderRadius: 4,
              border: "1px solid #111",
              background: pdfA && pdfB && !loading ? "#111" : "#f3f4f6",
              color: pdfA && pdfB && !loading ? "#fff" : "#9ca3af",
              fontFamily: "inherit",
              fontWeight: 600,
              fontSize: 13,
              cursor: pdfA && pdfB && !loading ? "pointer" : "default",
              transition: "background .15s",
              whiteSpace: "nowrap",
            }}
          >
            {loading ? "Comparing…" : "Compare"}
          </button>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              border: "1px solid #fca5a5",
              background: "#fff5f5",
              borderRadius: 4,
              padding: "10px 14px",
              color: "#b91c1c",
              marginBottom: 24,
              fontSize: 13,
            }}
          >
            {error}
          </div>
        )}

        {/* Results */}
        {result && (
          <div>
            {/* Tabs */}
            <div
              style={{
                display: "flex",
                gap: 0,
                borderBottom: "1px solid #e5e7eb",
                marginBottom: 24,
              }}
            >
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setActiveTab(t.id)}
                  style={{
                    padding: "10px 20px",
                    border: "none",
                    borderBottom:
                      activeTab === t.id
                        ? "2px solid #111"
                        : "2px solid transparent",
                    background: "transparent",
                    color: activeTab === t.id ? "#111" : "#6b7280",
                    fontFamily: "inherit",
                    fontWeight: activeTab === t.id ? 600 : 400,
                    fontSize: 13,
                    cursor: "pointer",
                    marginBottom: -1,
                    transition: "color .1s",
                  }}
                >
                  {t.label}
                  {t.id === "diff" && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: 11,
                        background: "#f3f4f6",
                        color: "#374151",
                        borderRadius: 10,
                        padding: "1px 7px",
                      }}
                    >
                      {result.stats.total}
                    </span>
                  )}
                  {t.id === "layout_changes" &&
                    result.layout_changes.length > 0 && (
                      <span
                        style={{
                          marginLeft: 8,
                          fontSize: 11,
                          background: "#fef3c7",
                          color: "#92400e",
                          borderRadius: 10,
                          padding: "1px 7px",
                        }}
                      >
                        {result.layout_changes.length}
                      </span>
                    )}
                </button>
              ))}
            </div>

            {/* Panel */}
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 4,
                overflow: "hidden",
              }}
            >
              {activeTab === "diff" && <SideBySide diff={result.diff} />}
              {activeTab === "layout_changes" && (
                <div style={{ padding: 16 }}>
                  <LayoutChanges changes={result.layout_changes} />
                </div>
              )}
              {activeTab === "metadata" && (
                <div style={{ padding: 16 }}>
                  <MetaView metadata={result.metadata} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
