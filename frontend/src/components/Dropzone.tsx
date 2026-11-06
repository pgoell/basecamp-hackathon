import { useRef, useState, type DragEvent } from "react";
import { api, type Rfp } from "../api/client";

interface Props {
  rfp: Rfp | null;
  onChange: (rfp: Rfp | null) => void;
  disabled?: boolean;
}

/** Drop or pick a PDF; it uploads at once and shows as a floppy chip. */
export function Dropzone({ rfp, onChange, disabled }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function take(file: File | undefined) {
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("That is not a PDF. Drop an RFP in PDF format.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onChange(await api.uploadRfp(file));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  function drop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    if (!disabled) take(e.dataTransfer.files[0]);
  }

  if (rfp) {
    return (
      <div className="rfp-chip">
        <div className="floppy" aria-hidden>
          <span className="floppy-shutter" />
          <span className="floppy-label">PDF</span>
        </div>
        <div className="rfp-meta">
          <strong title={rfp.filename}>{rfp.filename}</strong>
          <span className="mono small muted">
            {rfp.pages} {rfp.pages === 1 ? "page" : "pages"} · {rfp.chars.toLocaleString()} chars
          </span>
          {rfp.preview && <p className="rfp-preview">{rfp.preview}</p>}
        </div>
        <button className="btn btn-ghost btn-sm" onClick={() => onChange(null)} disabled={disabled}>
          Eject
        </button>
      </div>
    );
  }

  return (
    <>
      <button
        type="button"
        className={`dropzone ${over ? "is-over" : ""} ${busy ? "is-busy" : ""}`}
        onClick={() => input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        disabled={disabled || busy}
      >
        <span className="dropzone-icon" aria-hidden>
          {busy ? "⌛" : "⇪"}
        </span>
        <span className="dropzone-title">{busy ? "Reading the PDF…" : "Drop your RFP here"}</span>
        <span className="mono small muted">or click to browse · PDF up to 32 MB</span>
        {busy && <span className="barber" aria-hidden />}
      </button>
      <input
        ref={input}
        type="file"
        accept="application/pdf,.pdf"
        hidden
        onChange={(e) => {
          take(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      {error && <p className="dialog dialog-danger small">{error}</p>}
    </>
  );
}
