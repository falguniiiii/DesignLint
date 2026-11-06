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
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
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
    const sectionOrder = [
      "about",
      "how-it-works",
      "what-we-check",
      "get-started",
    ];

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
          <button
            type="button"
            className="analyzer-page__menu-toggle"
            aria-label={
              isMobileNavOpen ? "Close navigation menu" : "Open navigation menu"
            }
            aria-expanded={isMobileNavOpen}
            aria-controls="primary-navigation"
            onClick={() => setIsMobileNavOpen((open) => !open)}
          >
            <span aria-hidden="true">{isMobileNavOpen ? "×" : "☰"}</span>
          </button>
        )}

        {!showResults && (
          <nav
            id="primary-navigation"
            className={`analyzer-page__nav ${
              isMobileNavOpen ? "analyzer-page__nav--open" : ""
            }`}
            aria-label="Main navigation"
          >
            <a
              href="#about"
              onClick={() => {
                setActiveSection("about");
                setIsMobileNavOpen(false);
              }}
              aria-current={activeSection === "about" ? "location" : undefined}
            >
              About
            </a>

            <a
              href="#how-it-works"
              onClick={() => {
                setActiveSection("how-it-works");
                setIsMobileNavOpen(false);
              }}
              aria-current={
                activeSection === "how-it-works" ? "location" : undefined
              }
            >
              How it works
            </a>

            <a
              href="#what-we-check"
              onClick={() => {
                setActiveSection("what-we-check");
                setIsMobileNavOpen(false);
              }}
              aria-current={
                activeSection === "what-we-check" ? "location" : undefined
              }
            >
              What we check
            </a>

            <a
              href="#get-started"
              onClick={() => {
                setActiveSection("get-started");
                setIsMobileNavOpen(false);
              }}
              aria-current={
                activeSection === "get-started" ? "location" : undefined
              }
            >
              Get started
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
              <div className="landing-hero-actions">
                <a href="#get-started" className="landing-primary-link">
                  Upload your screenshot <span aria-hidden="true">↗</span>
                </a>
                <a href="#how-it-works" className="landing-text-link">
                  See how it works
                </a>
              </div>
              <div className="landing-proof-points">
                <span>✦ Rule-based visual checks</span>
                <span>✦ Actionable findings</span>
                <span>✦ No account required</span>
              </div>

              <div
                className="analyzer-page__preview"
                role="img"
                aria-label="Illustrative preview of a DesignLint audit showing a sample website and audit findings"
              >
                <div className="analyzer-page__preview-header">
                  <span className="analyzer-page__preview-label">
                    A LOOK INSIDE DESIGNLINT
                  </span>
                  <span className="analyzer-page__preview-badge">
                    Product preview
                  </span>
                </div>

                <div className="analyzer-page__preview-content">
                  <div className="analyzer-page__preview-screen">
                    <div className="analyzer-page__preview-browser">
                      <span />
                      <span />
                      <span />
                    </div>

                    <div className="analyzer-page__preview-website">
                      <div className="analyzer-page__preview-website-nav">
                        <span className="analyzer-page__preview-logo" />
                        <span />
                        <span />
                        <span />
                      </div>

                      <div className="analyzer-page__preview-website-hero">
                        <div className="analyzer-page__preview-lines">
                          <span />
                          <span />
                          <span />
                          <span />
                        </div>

                        <div className="analyzer-page__preview-image" />
                      </div>

                      <div className="analyzer-page__preview-website-cards">
                        <span />
                        <span />
                        <span />
                      </div>
                    </div>

                    <span className="analyzer-page__preview-marker analyzer-page__preview-marker--one">
                      01
                    </span>
                    <span className="analyzer-page__preview-marker analyzer-page__preview-marker--two">
                      02
                    </span>
                  </div>

                  <div className="analyzer-page__preview-findings">
                    <div className="analyzer-page__preview-findings-heading">
                      <span>Audit findings</span>
                      <span>Preview</span>
                    </div>

                    <div className="analyzer-page__preview-finding">
                      <span className="analyzer-page__preview-finding-number">
                        01
                      </span>
                      <div>
                        <strong>Color &amp; contrast</strong>
                        <span>Review text readability</span>
                      </div>
                    </div>

                    <div className="analyzer-page__preview-finding">
                      <span className="analyzer-page__preview-finding-number">
                        02
                      </span>
                      <div>
                        <strong>Component consistency</strong>
                        <span>Compare repeated button and card dimensions</span>
                      </div>
                    </div>

                    <p className="analyzer-page__preview-note">
                      Illustrative interface preview
                    </p>
                  </div>
                </div>
              </div>
            </div>
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
        </section>
      )}

      {!showResults && (
        <section
          id="how-it-works"
          className="landing-section landing-how"
          aria-labelledby="how-heading"
        >
          <div className="landing-section__heading">
            <p className="landing-eyebrow">SIMPLE PROCESS</p>
            <h2 id="how-heading">How it works</h2>
            <p>Get useful design insights in three straightforward steps.</p>
          </div>
          <ol className="landing-steps">
            <li>
              <span className="landing-step-icon">↥</span>
              <span className="landing-step-index">01 / UPLOAD</span>
              <h3>Share a screenshot</h3>
              <p>
                Choose a screenshot of the website or interface you want to
                review.
              </p>
            </li>
            <li>
              <span className="landing-step-icon">⌕</span>
              <span className="landing-step-index">02 / ANALYZE</span>
              <h3>Inspect the design</h3>
              <p>
                DesignLint extracts visual details and checks them against
                defined design rules.
              </p>
            </li>
            <li>
              <span className="landing-step-icon">✳</span>
              <span className="landing-step-index">03 / IMPROVE</span>
              <h3>Make informed changes</h3>
              <p>
                Review the score, highlighted findings and practical
                recommendations.
              </p>
            </li>
          </ol>
        </section>
      )}

      {!showResults && (
        <section
          id="what-we-check"
          className="landing-section landing-checks"
          aria-labelledby="checks-heading"
        >
          <div className="landing-section__heading">
            <p className="landing-eyebrow">AUDIT CATEGORIES</p>
            <h2 id="checks-heading">What we check</h2>
            <p>
              A closer look at the visual details that shape a clear, consistent
              interface.
            </p>
          </div>
          <div className="landing-check-grid">
            <article>
              <span className="landing-check-icon">◉</span>
              <h3>Color &amp; contrast</h3>
              <p>
                Prominent color variety and contrast between detected text and
                background colors, where their roles can be identified.
              </p>
            </article>
            <article>
              <span className="landing-check-icon">Aa</span>
              <h3>Typography</h3>
              <p>
                Estimated text sizes, font-size variety, small text and heading
                hierarchy.
              </p>
            </article>
            <article>
              <span className="landing-check-icon">⌗</span>
              <h3>Spacing</h3>
              <p>
                Vertical spacing variation between repeated elements of the same
                type.
              </p>
            </article>
            <article>
              <span className="landing-check-icon">◇</span>
              <h3>Consistency</h3>
              <p>
                Height consistency across repeated buttons and cards, plus card
                width variation.
              </p>
            </article>
          </div>
        </section>
      )}

      {!showResults && (
        <section
          id="get-started"
          className="landing-cta"
          aria-labelledby="get-started-heading"
        >
          <div className="landing-cta__copy">
            <p className="landing-eyebrow">READY WHEN YOU ARE</p>
            <h2 id="get-started-heading">
              Make your design clearer, one review at a time.
            </h2>
            <p>
              Upload a screenshot and get focused visual feedback in seconds.
            </p>
          </div>
          <div className="landing-cta__upload">
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
        </section>
      )}

      {!showResults && (
        <footer className="landing-footer">
          <a href="#top" className="landing-footer__brand">
            ✳ DesignLint
          </a>
          <span>Structured visual feedback for better interfaces.</span>
          <a href="#top">Back to top ↑</a>
        </footer>
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
