"""
Orchestrates all rule modules. Adding a new rule category later means
writing a new module in app/rules/ and adding one line here - nothing
else in the app needs to change.
"""
from app.schemas.extraction import ExtractionResult
from app.schemas.findings import RawFinding
from app.rules import color_rules, contrast_rules, typography_rules, spacing_rules, consistency_rules

RULE_MODULES = [color_rules, contrast_rules, typography_rules, spacing_rules, consistency_rules]


def run_rule_engine(extraction: ExtractionResult) -> list[RawFinding]:
    findings: list[RawFinding] = []
    for module in RULE_MODULES:
        findings.extend(module.run(extraction))
    return findings
