// Renders the structured Recommendation object the backend now attaches
// to every finding: why it matters, what to change, a concrete suggested
// value, and (for color findings) a derived palette. Kept as distinct
// labeled sections rather than one paragraph, matching the backend's
// structure 1:1. Also supports click-to-highlight against the screenshot
// annotations (activeFindingId / onFindingClick).

const SEVERITY_LABEL = {
  major: "Major",
  minor: "Minor",
  suggestion: "Suggestion",
};

const SOURCE_LABEL = {
  detected: "Detected in your screenshot",
  derived: "Derived by DesignLint",
};

function PaletteSwatches({ palette }) {
  return (
    <ul className="palette-swatches">
      {palette.map((c) => (
        <li key={c.role} className="palette-swatches__item">
          <span
            className="palette-swatches__color"
            style={{ backgroundColor: c.hex }}
            aria-hidden="true"
          />
          <div className="palette-swatches__text">
            <span className="palette-swatches__role">
              {c.role} <span className="audit-results__mono">{c.hex}</span>
            </span>
            <span
              className={`palette-swatches__source palette-swatches__source--${c.source || "derived"}`}
            >
              {SOURCE_LABEL[c.source] || SOURCE_LABEL.derived}
            </span>
            <span className="palette-swatches__usage">{c.usage}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function AuditResults({
  audit,
  activeFindingId,
  onFindingClick,
}) {
  const { overallScore, categoryScores, findings } = audit;

  return (
    <div className="audit-results">
      <h2 className="visually-hidden">Audit results</h2>

      <div className="audit-results__score">
        <span className="audit-results__score-value">{overallScore}</span>
        <span className="audit-results__score-max">/100</span>
      </div>
      <p className="audit-results__score-explainer">
        Each category starts at 100 and loses points for every finding (major
        −10, minor −5, suggestion −2). The overall score averages the four
        categories. It reflects the patterns DesignLint's rules can check, not a
        full design review.
      </p>

      <h3 className="audit-results__subheading">Category scores</h3>
      <ul className="audit-results__categories">
        {categoryScores.map((c) => (
          <li key={c.category} className="audit-results__category">
            <span>{c.category}</span>
            <span
              className="audit-results__bar"
              role="img"
              aria-label={`${c.category} score ${c.score} out of 100`}
            >
              <span
                className="audit-results__bar-fill"
                style={{ width: `${c.score}%` }}
              />
            </span>
            <span className="audit-results__mono">{c.score}</span>
          </li>
        ))}
      </ul>

      <h3>Findings ({findings.length})</h3>

      {findings.length === 0 && (
        <p className="audit-results__empty">
          No issues were flagged by DesignLint's current rules. That's a good
          sign, but it doesn't guarantee the design is perfect — the rules only
          check a limited set of patterns (color count, contrast, type sizes,
          spacing and consistency).
        </p>
      )}

      <ul className="audit-results__findings">
        {findings.map((f, index) => (
          <li
            key={f.id}
            id={`finding-${f.id}`}
            className={`finding finding--${f.severity} ${
              activeFindingId === f.id ? "is-active" : ""
            }`}
            onClick={() => onFindingClick?.(f.id)}
          >
            <div className="finding__header">
              {f.relatedElements.length > 0 && (
                <span className="finding__number">{index + 1}</span>
              )}
              <span
                className={`finding__severity finding__severity--${f.severity}`}
              >
                {SEVERITY_LABEL[f.severity]}
              </span>
              <span className="finding__category">{f.category}</span>
              <span className="finding__confidence">
                {Math.round(f.confidence * 100)}% confidence
              </span>
            </div>

            <h4 className="finding__title">{f.title}</h4>
            <p className="finding__description">{f.description}</p>

            {f.relatedElements.length > 0 && (
              <button
                type="button"
                className="finding__locate"
                aria-pressed={activeFindingId === f.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onFindingClick?.(f.id);
                }}
              >
                {activeFindingId === f.id
                  ? "Hide on screenshot"
                  : `Show issue ${index + 1} on screenshot`}
              </button>
            )}

            <details
              className="finding__details"
              onClick={(e) => e.stopPropagation()}
            >
              <summary className="finding__details-summary">
                Recommendation details
              </summary>

              <div className="finding__section">
                <span className="finding__section-label">Why it matters</span>
                <p className="finding__section-body">
                  {f.recommendation.whyItMatters}
                </p>
              </div>

              <div className="finding__section">
                <span className="finding__section-label">Try this</span>
                <p className="finding__section-body">{f.recommendation.fix}</p>
                {f.recommendation.suggestedValue && (
                  <p className="finding__suggested-value">
                    {f.recommendation.suggestedValue}
                  </p>
                )}
              </div>

              {f.recommendation.palette && (
                <div className="finding__section">
                  <span className="finding__section-label">
                    Suggested palette
                  </span>
                  <PaletteSwatches palette={f.recommendation.palette} />
                </div>
              )}
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}
