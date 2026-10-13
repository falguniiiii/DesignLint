// Centralized API access. Every backend call goes through here so the
// base URL and error handling live in one place, not scattered across
// components.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Generous on purpose: complex screenshots can legitimately take a while.
const ANALYZE_TIMEOUT_MS = 120_000;

export async function checkHealth() {
  const res = await fetch(`${API_BASE_URL}/api/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

// What the user sees for failures the backend couldn't describe itself
// (network down, server crashed, proxy error page, ...). Backend-supplied
// `detail` messages for 400/500/502 are already beginner-friendly and are
// used as-is when present.
function fallbackMessageForStatus(status) {
  if (status === 413) return "That file is too large for the server. Please use a smaller image.";
  if (status >= 500) return "The server ran into a problem while analyzing this screenshot. Please try again in a moment.";
  return "The analysis couldn't be completed. Please try again.";
}

/**
 * Uploads a screenshot for analysis.
 *
 * Uses XMLHttpRequest rather than fetch ONLY because it can report when
 * the upload has really finished (`upload.onload`) - the one piece of
 * real progress evidence the browser can give us. The server does
 * extraction, rule checks and scoring inside this single request and
 * doesn't stream stage updates, so nothing finer-grained is reported.
 *
 * @param {File} file
 * @param {{ onUploadComplete?: () => void }} [options]
 */
export function analyzeImage(file, { onUploadComplete } = {}) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/analyze`);
    xhr.timeout = ANALYZE_TIMEOUT_MS;
    xhr.responseType = "json";

    xhr.upload.onload = () => onUploadComplete?.();

    xhr.onload = () => {
      const body = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300 && body) {
        resolve(body);
        return;
      }
      const detail = body && typeof body.detail === "string" ? body.detail : null;
      reject(new Error(detail || fallbackMessageForStatus(xhr.status)));
    };

    xhr.onerror = () =>
      reject(
        new Error(
          "Couldn't reach the DesignLint server. Check that the backend is running and your connection is working, then try again."
        )
      );
    xhr.ontimeout = () =>
      reject(
        new Error(
          "The analysis took too long and was stopped. Try again, or use a smaller or simpler screenshot."
        )
      );

    xhr.send(formData);
  });
}
