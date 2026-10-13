import { useCallback, useRef, useState } from "react";

const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/webp"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB, mirrors backend limit

export default function UploadDropzone({ onFileAccepted }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const validateAndAccept = useCallback(
    (file) => {
      if (!file) return;
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setError("Unsupported file type. Please use PNG, JPG, or WEBP.");
        return;
      }
      if (file.size > MAX_SIZE_BYTES) {
        setError("File is too large. Please use an image smaller than 10 MB.");
        return;
      }
      setError(null);
      onFileAccepted(file);
    },
    [onFileAccepted]
  );

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    validateAndAccept(file);
  };

  const handleInputChange = (e) => {
    const file = e.target.files?.[0];
    validateAndAccept(file);
  };

  return (
    <div className="upload-dropzone-wrapper">
      <div
        className={`upload-dropzone ${isDragging ? "is-dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload a screenshot by dragging a file here or pressing enter to browse"
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <p className="upload-dropzone__title">Drag and drop a screenshot</p>
        <p className="upload-dropzone__subtitle">or click to browse (PNG, JPG, WEBP · up to 10MB)</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          onChange={handleInputChange}
          hidden
        />
      </div>
      {error && (
        <p className="upload-dropzone__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
