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
      const data = await analyzeImage(file, {
        onUploadComplete: () => setUploaded(true),
      });
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
    <main
      id="top"
      className={`analyzer-page ${showResults ? "analyzer-page--results" : ""}`}
    >
      <header className="analyzer-page__header">
        <h1 className="analyzer-page__brand">
          <a
            href="#top"
            className="analyzer-page__brand-link"
            aria-label="DesignLint home"
          >
            <img src="/brand/designlint-mark.svg" alt="" aria-hidden="true" />
            <span>DesignLint</span>
          </a>
        </h1>

        {!showResults && (
          <nav className="analyzer-page__nav" aria-label="Main navigation">
            <a href="#about">About</a>
            <a href="#audit-checks">Audit checks</a>
            <a href="#start-audit" className="analyzer-page__nav-cta">
              Start an audit
            </a>
          </nav>
        )}

        {backendStatus === "offline" && (
          <button
            type="button"
            className="retry-connection"
            onClick={handleRetryConnection}
          >
            Retry connection
          </button>
        )}
      </header>

      {!showResults && (
        <section
          className="analyzer-page__upload-section"
          aria-labelledby="upload-heading"
        >
          <div className="analyzer-page__hero-grid">
            <div id="about" className="analyzer-page__intro">
              <p className="analyzer-page__eyebrow">UI/UX DESIGN AUDIT</p>

              <h2 id="upload-heading" className="analyzer-page__title">
                Better design starts with a closer look.
              </h2>

              <p className="analyzer-page__description">
                Turn a website screenshot into a clear, practical design audit.
                Spot visual inconsistencies and discover what to improve next.
              </p>

              <ol
                className="analyzer-page__steps"
                aria-label="How DesignLint works"
              >
                <li>
                  <span className="analyzer-page__step-number">01</span>
                  <span>
                    <strong>Upload</strong>
                    <small>Choose a screenshot of your interface.</small>
                  </span>
                </li>
                <li>
                  <span className="analyzer-page__step-number">02</span>
                  <span>
                    <strong>Review</strong>
                    <small>Explore scores and highlighted findings.</small>
                  </span>
                </li>
                <li>
                  <span className="analyzer-page__step-number">03</span>
                  <span>
                    <strong>Improve</strong>
                    <small>
                      Use clear suggestions to guide your next pass.
                    </small>
                  </span>
                </li>
              </ol>
            </div>

            <div id="start-audit" className="analyzer-page__upload-panel">
              <div className="analyzer-page__panel-heading">
                <span className="analyzer-page__panel-kicker">
                  START YOUR AUDIT
                </span>
              </div>

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
                disabled={
                  !file || backendStatus !== "online" || status === "analyzing"
                }
                onClick={handleAnalyze}
              >
                {status === "analyzing"
                  ? "Analyzing…"
                  : status === "error"
                    ? "Try again"
                    : "Analyze Design"}
              </button>

              {file && backendStatus !== "online" && (
                <p className="analyzer-page__hint">
                  The backend isn't reachable yet, so analysis can't run. Start
                  it, then press “Retry connection”.
                </p>
              )}

              {status === "analyzing" && (
                <AnalysisProgress uploaded={uploaded} />
              )}

              {status === "error" && (
                <div className="analyzer-page__error" role="alert">
                  <p className="analyzer-page__error-title">
                    The analysis didn't complete
                  </p>
                  <p>{error}</p>
                  <p className="analyzer-page__error-hint">
                    Your screenshot is still selected. Press “Try again”, or
                    remove it to choose a different one.
                  </p>
                </div>
              )}
            </div>
          </div>

          <div
            id="audit-checks"
            className="analyzer-page__audit-strip"
            aria-label="Audit categories"
          >
            <span className="analyzer-page__audit-label">A closer look at</span>
            <span>Color &amp; contrast</span>
            <span>Typography</span>
            <span>Spacing</span>
            <span>Consistency</span>
          </div>
        </section>
      )}

      {showResults && (
        <section
          className="analyzer-page__results-layout"
          aria-label="Audit results"
        >
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
        <button
          type="button"
          className="analyzer-page__new-analysis"
          onClick={handleRemove}
        >
          Analyze another screenshot
        </button>
      )}
    </main>
  );
}
