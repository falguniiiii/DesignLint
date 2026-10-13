"""
Every number that affects the final score lives here. Rules never
hardcode a deduction value themselves - they just pick a severity,
and this config decides what that severity is worth. This means the
scoring model can be tuned without touching rule logic.
"""

CATEGORY_WEIGHTS: dict[str, float] = {
    "Color": 0.25,
    "Typography": 0.25,
    "Spacing": 0.25,
    "Consistency": 0.25,
}

SEVERITY_DEDUCTIONS: dict[str, int] = {
    "major": -10,
    "minor": -5,
    "suggestion": -2,
}

CATEGORY_STARTING_SCORE = 100
