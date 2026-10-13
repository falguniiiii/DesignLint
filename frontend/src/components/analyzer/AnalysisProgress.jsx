import { useEffect, useState } from "react";

// Honest progress indication.
//
// - "Screenshot uploaded" is marked done only when the browser reports the
//   upload really finished (see analyzeImage's onUploadComplete).
// - The backend does extraction, rule checks and scoring in ONE request and
//   doesn't report which step it is on, so those steps are shown as
//   "in progress" / "up next" - never as completed - until the response
//   actually arrives (at which point this component is replaced by the
//   results). No percentage is shown because none can be known.
// - The waiting messages are reassurance based on elapsed time only.

const STEPS = [
  { key: "upload", label: "Screenshot uploaded" },
  { key: "extract", label: "Extracting interface structure" },
  { key: "checks", label: "Running deterministic design checks" },
  { key: "prepare", label: "Preparing the results" },
];

const SLOW_AFTER_SECONDS = 20;

function waitingMessage(seconds, uploaded) {
  if (!uploaded) return "Sending your screenshot to the DesignLint server…";
  if (seconds >= SLOW_AFTER_SECONDS) {
    return "This is taking longer than usual. Complex screenshots with many elements can take a while — please keep this page open.";
  }
  if (seconds >= 8) return "Still working. Reading every element in a screenshot takes a few seconds.";
  return "Gemini is reading the screenshot. DesignLint's own rules will judge it afterwards.";
}

export default function AnalysisProgress({ uploaded }) {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const activeIndex = uploaded ? 1 : 0;

  return (
    <div className="analysis-progress" role="status" aria-live="polite">
      <ol className="analysis-progress__steps">
        {STEPS.map((step, index) => {
          const state = index < activeIndex ? "done" : index === activeIndex ? "active" : "pending";
          return (
            <li
              key={step.key}
              className={`analysis-progress__step analysis-progress__step--${state}`}
              aria-current={state === "active" ? "step" : undefined}
            >
              <span className="analysis-progress__marker" aria-hidden="true">
                {state === "done" ? "✓" : ""}
              </span>
              <span>
                {step.label}
                <span className="visually-hidden">
                  {state === "done" ? " (done)" : state === "active" ? " (in progress)" : " (up next)"}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="analysis-progress__message">{waitingMessage(seconds, uploaded)}</p>
      <p className="analysis-progress__note">
        The server runs these steps in one request, so exact progress isn't available.
      </p>
    </div>
  );
}
