"""
Color rules.

Extracted color count alone is insufficient evidence of poor visual
hierarchy or palette inconsistency.

Palette suggestions are generated independently by the recommendation
service. Future color findings must be based on reliable visual evidence.
"""

from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding


def run(extraction: ExtractionResult) -> list[RawFinding]:
    """Do not generate findings from the number of extracted colors alone."""
    return []