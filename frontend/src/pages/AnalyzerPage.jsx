import { useCallback, useEffect, useState } from "react";
import UploadDropzone from "../components/upload/UploadDropzone";
import ImagePreviewCard from "../components/upload/ImagePreviewCard";
import ScreenshotViewer from "../components/analyzer/ScreenshotViewer";
import AuditResults from "../components/analyzer/AuditResults";
import AnalysisProgress from "../components/analyzer/AnalysisProgress";
import { checkHealth, analyzeImage } from "../services/api";

export default function AnalyzerPage() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dimensions, setDimensions] = useState(null);
  const [backendStatus, setBackendStatus] = useState("checking");

  const [status, setStatus] = useState("idle"); // idle | analyzing | done | error
  const [uploaded, setUploaded] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [activeFindingId, setActiveFindingId] = useState(null);

  // One check on page load, plus a manual "Retry connection" button when
  // the backend is offline. No polling: it only re-checks when asked.
  const checkBackend = useCallback(() => {
    checkHealth()
      .then(() => setBackendStatus("online"))
      .catch(() => setBackendStatus("offline"));
  }, []);

  useEffect(() => {
    checkBackend(); // initial state is already "checking"
  }, [checkBackend]);

  const handleRetryConnection = () => {
    setBackendStatus("checking");
    checkBackend();
  };

  const handleFileAccepted = (selectedFile) => {
    const url = URL.createObjectURL(selectedFile);
    setFile(selectedFile);
    setPreviewUrl(url);
    setDimensions(null);
    setResult(null);
    setError(null);
    setStatus("idle");
    setActiveFindingId(null);

    const img = new Image();
    img.onload = () => setDimensions({ width: img.width, height: img.height });
    img.src = url;
  };

  const handleRemove = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl(null);
    setDimensions(null);
    setResult(null);
    setError(null);
    setStatus("idle");
    setActiveFindingId(null);
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setStatus("analyzing");
    setUploaded(false);
    setError(null);
    setResult(null);
    setActiveFindingId(null);

    try {
      const data = await analyzeImage(file, { onUploadComplete: () => setUploaded(true) });
      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  };

  // Clicking a finding card or a marker toggles the same shared state,
  // which is what links the two views together.
  const handleSelectFinding = (findingId) => {
    setActiveFindingId((current) => (current === findingId ? null : findingId));
    const el = document.getElementById(`finding-${findingId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const showResults = status === "done" && result;

  return (
    <main className={`analyzer-page ${showResults ? "analyzer-page--results" : ""}`}>
      <header className="analyzer-page__header">
        <h1>DesignLint</h1>
        <div className="analyzer-page__header-status">
          <p
            className={`backend-status backend-status--${backendStatus}`}
            role="status"
          >
            Backend: {backendStatus}
          </p>
          {backendStatus === "offline" && (
            <button type="button" className="retry-connection" onClick={handleRetryConnection}>
              Retry connection
            </button>
          )}
        </div>
      </header>

      {!showResults && (
        <section aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="visually-hidden">
            Upload a screenshot
          </h2>

          {!file && <UploadDropzone onFileAccepted={handleFileAccepted} />}

          {file && (
            <ImagePreviewCard
              file={file}
              previewUrl={previewUrl}
              dimensions={dimensions}
              onRemove={handleRemove}
            />
          )}

          <button
            type="button"
            className="analyze-button"
            disabled={!file || backendStatus !== "online" || status === "analyzing"}
            onClick={handleAnalyze}
          >
            {status === "analyzing" ? "Analyzing…" : status === "error" ? "Try again" : "Analyze Design"}
          </button>

          {file && backendStatus !== "online" && (
            <p className="analyzer-page__hint">
              The backend isn't reachable yet, so analysis can't run. Start it, then press “Retry connection”.
            </p>
          )}

          {status === "analyzing" && <AnalysisProgress uploaded={uploaded} />}

          {status === "error" && (
            <div className="analyzer-page__error" role="alert">
              <p className="analyzer-page__error-title">The analysis didn't complete</p>
              <p>{error}</p>
              <p className="analyzer-page__error-hint">
                Your screenshot is still selected — press “Try again”, or remove it to choose a different one.
              </p>
            </div>
          )}
        </section>
      )}

      {showResults && (
        <section className="analyzer-page__results-layout" aria-label="Audit results">
          <ScreenshotViewer
            previewUrl={previewUrl}
            image={result.image}
            elements={result.elements}
            findings={result.findings}
            activeFindingId={activeFindingId}
            onMarkerClick={handleSelectFinding}
          />
          <AuditResults
            audit={result}
            activeFindingId={activeFindingId}
            onFindingClick={handleSelectFinding}
          />
        </section>
      )}

      {showResults && (
        <button type="button" className="analyzer-page__new-analysis" onClick={handleRemove}>
          Analyze another screenshot
        </button>
      )}
    </main>
  );
}
