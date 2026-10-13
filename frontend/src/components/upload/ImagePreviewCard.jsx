import { formatFileSize } from "../../utils/formatFileSize";

export default function ImagePreviewCard({ file, previewUrl, dimensions, onRemove }) {
  return (
    <div className="preview-card">
      <img
        src={previewUrl}
        alt={`Preview of uploaded screenshot: ${file.name}`}
        className="preview-card__image"
      />
      <div className="preview-card__meta">
        <div>
          <p className="preview-card__filename">{file.name}</p>
          <p className="preview-card__details">
            {dimensions ? `${dimensions.width} × ${dimensions.height}px` : "Reading dimensions…"}
            {" · "}
            {formatFileSize(file.size)}
          </p>
        </div>
        <button
          type="button"
          className="preview-card__remove"
          onClick={onRemove}
          aria-label={`Remove ${file.name}`}
        >
          Remove
        </button>
      </div>
    </div>
  );
}
