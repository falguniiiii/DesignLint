// Draws the uploaded screenshot with numbered markers over findings that
// have related elements. Marker position is the centroid of the union of
// all related elements' bounding boxes, expressed as a percentage of the
// image's own reported dimensions - the container below is forced to the
// exact same aspect ratio as the image, so percentage math lines up
// without any letterboxing distortion. Findings with no relatedElements
// get no marker, per the original spec ("don't invent coordinates just
// to make every finding clickable").

function computeMarkerPosition(relatedElementIds, elementsById, image) {
  const boxes = relatedElementIds
    .map((id) => elementsById[id])
    .filter(Boolean)
    .map((el) => el.boundingBox);

  if (boxes.length === 0) return null;

  const minX = Math.min(...boxes.map((b) => b.x));
  const minY = Math.min(...boxes.map((b) => b.y));
  const maxX = Math.max(...boxes.map((b) => b.x + b.width));
  const maxY = Math.max(...boxes.map((b) => b.y + b.height));

  const centerX = (minX + maxX) / 2;
  const centerY = (minY + maxY) / 2;

  return {
    left: `${(centerX / image.width) * 100}%`,
    top: `${(centerY / image.height) * 100}%`,
    box: { minX, minY, maxX, maxY },
  };
}

export default function ScreenshotViewer({ previewUrl, image, elements, findings, activeFindingId, onMarkerClick }) {
  const elementsById = Object.fromEntries(elements.map((e) => [e.id, e]));

  const markers = findings
    .map((finding, index) => {
      const position = computeMarkerPosition(finding.relatedElements, elementsById, image);
      if (!position) return null;
      return { finding, index, position };
    })
    .filter(Boolean);

  const activeMarker = markers.find((m) => m.finding.id === activeFindingId);

  return (
    <div className="screenshot-viewer">
      <div
        className="screenshot-viewer__frame"
        style={{ aspectRatio: `${image.width} / ${image.height}` }}
      >
        <img src={previewUrl} alt="Analyzed screenshot" className="screenshot-viewer__image" />

        {/* Outline boxes for the active finding's related elements */}
        {activeMarker &&
          activeMarker.finding.relatedElements.map((id) => {
            const el = elementsById[id];
            if (!el) return null;
            const { x, y, width, height } = el.boundingBox;
            return (
              <div
                key={id}
                className="screenshot-viewer__highlight-box"
                style={{
                  left: `${(x / image.width) * 100}%`,
                  top: `${(y / image.height) * 100}%`,
                  width: `${(width / image.width) * 100}%`,
                  height: `${(height / image.height) * 100}%`,
                }}
              />
            );
          })}

        {markers.map(({ finding, index, position }) => (
          <button
            key={finding.id}
            type="button"
            className={`screenshot-viewer__marker screenshot-viewer__marker--${finding.severity} ${
              activeFindingId === finding.id ? "is-active" : ""
            }`}
            style={{ left: position.left, top: position.top }}
            onClick={() => onMarkerClick(finding.id)}
            aria-label={`Issue ${index + 1}: ${finding.title}`}
          >
            {index + 1}
          </button>
        ))}
      </div>
      {markers.length > 0 && (
        <ul className="screenshot-viewer__legend" aria-label="Marker colors">
          <li><span className="screenshot-viewer__legend-dot screenshot-viewer__legend-dot--major" aria-hidden="true" />Major</li>
          <li><span className="screenshot-viewer__legend-dot screenshot-viewer__legend-dot--minor" aria-hidden="true" />Minor</li>
          <li><span className="screenshot-viewer__legend-dot screenshot-viewer__legend-dot--suggestion" aria-hidden="true" />Suggestion</li>
        </ul>
      )}
      <p className="screenshot-viewer__note">
        Numbers match the findings list. Marker positions are estimated from AI vision extraction and may be approximate.
      </p>
    </div>
  );
}
