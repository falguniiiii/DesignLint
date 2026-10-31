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
  const [activeSection, setActiveSection] = useState(null);
  const [isScrolled, setIsScrolled] = useState(false);

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

  useEffect(() => {
    const sectionOrder = ["start-audit", "audit-checks", "about"];

    const updateActiveSection = () => {
      const activationPoint = window.scrollY + 140;
      let currentSection = null;

      sectionOrder.forEach((id) => {
        const element = document.getElementById(id);

        if (!element) return;

        const sectionTop = element.getBoundingClientRect().top + window.scrollY;

        if (sectionTop <= activationPoint) {
          currentSection = id;
        }
      });

      setActiveSection(currentSection);
    };

    updateActiveSection();

    window.addEventListener("scroll", updateActiveSection, {
      passive: true,
    });

    return () => {
      window.removeEventListener("scroll", updateActiveSection);
    };
  }, [showResults]);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };

    handleScroll();

    window.addEventListener("scroll", handleScroll, {
      passive: true,
    });

    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  return (
    <main
      id="top"
      className={`analyzer-page ${showResults ? "analyzer-page--results" : ""}`}
    >
      <header
        className={`analyzer-page__header ${
          isScrolled ? "analyzer-page__header--scrolled" : ""
        }`}
      >
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
            <a
              href="#about"
              aria-current={activeSection === "about" ? "location" : undefined}
              onClick={() => setActiveSection("about")}
            >
              About
            </a>

            <a
              href="#audit-checks"
              aria-current={
                activeSection === "audit-checks" ? "location" : undefined
              }
              onClick={() => setActiveSection("audit-checks")}
            >
              Audit checks
            </a>

            <a
              href="#start-audit"
              aria-current={
                activeSection === "start-audit" ? "location" : undefined
              }
              onClick={() => setActiveSection("start-audit")}
            >
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
            <div className="analyzer-page__intro">
              <p className="analyzer-page__eyebrow">UI/UX DESIGN AUDIT</p>

              <h2 id="upload-heading" className="analyzer-page__title">
                Better design starts with a closer look.
              </h2>

              <p className="analyzer-page__description">
                Turn a website screenshot into a clear, practical design audit.
                Spot visual inconsistencies and discover what to improve next.
              </p>
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

      {!showResults && (
        <section
          id="about"
          className="analyzer-page__about"
          aria-labelledby="about-heading"
        >
          <div className="analyzer-page__about-intro">
            <div className="analyzer-page__about-copy">
              <p className="analyzer-page__about-eyebrow">ABOUT DESIGNLINT</p>

              <h2 id="about-heading">
                Design feedback grounded in what’s on the screen.
              </h2>
            </div>

            <p className="analyzer-page__about-description">
              DesignLint turns a website screenshot into structured visual
              feedback. It identifies interface elements and evaluates their
              visual properties against defined design rules, helping you
              understand what needs attention and why.
            </p>
          </div>

          <div className="analyzer-page__about-process">
            <div className="analyzer-page__about-process-heading">
              <p className="analyzer-page__about-eyebrow">HOW IT WORKS</p>

              <h3>From screenshot to clearer next steps.</h3>
            </div>

            <ol className="analyzer-page__about-steps">
              <li>
                <span className="analyzer-page__about-number">01</span>
                <div>
                  <h4>Upload a screenshot</h4>
                  <p>
                    Choose a screenshot of the website or interface you want to
                    review.
                  </p>
                </div>
              </li>

              <li>
                <span className="analyzer-page__about-number">02</span>
                <div>
                  <h4>Inspect the design</h4>
                  <p>
                    Visual information is extracted and evaluated against
                    DesignLint’s defined design rules.
                  </p>
                </div>
              </li>

              <li>
                <span className="analyzer-page__about-number">03</span>
                <div>
                  <h4>Review and improve</h4>
                  <p>
                    Explore the audit score, highlighted findings and practical
                    recommendations.
                  </p>
                </div>
              </li>
            </ol>
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
