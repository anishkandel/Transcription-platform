import { useId, useRef, useState, type DragEvent } from "react";
import { FileAudio, Upload, X } from "lucide-react";

type Props = {
  file: File | null;
  onChange: (file: File | null) => void;
  accept?: string;
  label?: string;
  hint?: string;
  disabled?: boolean;
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FileDropzone({
  file,
  onChange,
  accept = "audio/*,video/*",
  label = "Drop audio or video here",
  hint = "or click to browse · m4a, wav, mp3, mp4",
  disabled = false,
}: Props) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function takeFile(next: File | null | undefined) {
    if (!next || disabled) return;
    onChange(next);
  }

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    takeFile(event.dataTransfer.files?.[0]);
  }

  if (file) {
    return (
      <div className={`file-dropzone selected ${disabled ? "disabled" : ""}`}>
        <div className="file-dropzone-icon selected">
          <FileAudio size={18} />
        </div>
        <div className="file-dropzone-meta">
          <strong title={file.name}>{file.name}</strong>
          <span>{formatSize(file.size)}</span>
        </div>
        <button
          type="button"
          className="file-dropzone-clear"
          aria-label="Remove file"
          disabled={disabled}
          onClick={() => {
            onChange(null);
            if (inputRef.current) inputRef.current.value = "";
          }}
        >
          <X size={14} />
        </button>
      </div>
    );
  }

  return (
    <label
      htmlFor={inputId}
      className={`file-dropzone ${dragging ? "dragging" : ""} ${disabled ? "disabled" : ""}`}
      onDragEnter={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={(e) => {
        e.preventDefault();
        setDragging(false);
      }}
      onDrop={onDrop}
    >
      <div className="file-dropzone-icon">
        <Upload size={18} />
      </div>
      <div className="file-dropzone-copy">
        <strong>{label}</strong>
        <span>{hint}</span>
      </div>
      <input
        id={inputId}
        ref={inputRef}
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={(e) => takeFile(e.target.files?.[0] || null)}
      />
    </label>
  );
}
