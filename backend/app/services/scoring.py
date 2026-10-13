"""
Turns a list of findings into category scores and one overall score.

This is intentionally simple and fully explainable: each category starts
at 100, each finding deducts a fixed amount based on its severity (see
app/config/scoring.py), and the overall score is a weighted average.
Nothing here is a black box - given the findings, you can recompute the
score by hand.
"""
from app.config.scoring import CATEGORY_WEIGHTS, SEVERITY_DEDUCTIONS, CATEGORY_STARTING_SCORE
from app.schemas.findings import RawFinding, CategoryScore


def calculate_scores(findings: list[RawFinding]) -> tuple[list[CategoryScore], int]:
    raw_scores: dict[str, int] = {
        category: CATEGORY_STARTING_SCORE for category in CATEGORY_WEIGHTS
    }

    for finding in findings:
        deduction = SEVERITY_DEDUCTIONS[finding.severity]
        raw_scores[finding.category] = max(0, raw_scores[finding.category] + deduction)

    category_scores = [
        CategoryScore(category=category, score=score)
        for category, score in raw_scores.items()
    ]

    overall = sum(
        raw_scores[category] * weight for category, weight in CATEGORY_WEIGHTS.items()
    )

    return category_scores, round(overall)
