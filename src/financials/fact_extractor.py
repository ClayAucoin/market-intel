import json

from pydantic import BaseModel

from src.ai_client import analyze_text
from src.document_service import download_exhibit_text


class FinancialFact(BaseModel):
    metric: str

    current_value: float | None = None
    previous_value: float | None = None

    current_period: str | None = None
    previous_period: str | None = None

    unit: str | None = None

    change_percent: float | None = None

    direction: str | None = None

    evidence: str

class FactExtraction(BaseModel):
    event_type: str
    facts: list[FinancialFact]


def extract_facts(exhibit_id):
    document = download_exhibit_text(exhibit_id)

    prompt = f"""
Extract factual financial and business metrics from this SEC exhibit.

Your job is DATA EXTRACTION ONLY.

Do not:
- judge whether results are good or bad
- make investment recommendations
- provide sentiment
- combine multiple financial metrics into one fact

IMPORTANT:

When a current-period value and a prior-period value are both present,
extract BOTH.

When a percentage change is explicitly provided, extract it.

When direction can be determined directly from the two reported values,
set direction to:
- "up"
- "down"
- "unchanged"

Use numeric values only in current_value and previous_value.

Examples:

If the document says:

Net revenue
$43,842
$23,378
88%

Return:

{{
  "metric": "net_revenue",
  "current_value": 43842,
  "previous_value": 23378,
  "current_period": "May 1, 2026",
  "previous_period": "May 2, 2025",
  "unit": "USD millions",
  "change_percent": 88,
  "direction": "up",
  "evidence": "Net revenue $43,842 $23,378 88%"
}}

If the document says:

Gross margin percentage
18.1%
21.6%

Return:

{{
  "metric": "non_gaap_gross_margin_percent",
  "current_value": 18.1,
  "previous_value": 21.6,
  "unit": "percent",
  "change_percent": null,
  "direction": "down",
  "evidence": "18.1% 21.6%"
}}

Use short machine-friendly metric names such as:
- net_revenue
- gross_margin_percent
- operating_income
- operating_margin_percent
- net_income
- diluted_eps
- free_cash_flow
- adjusted_free_cash_flow

Company: {document["company_name"]}
Ticker: {document["ticker"]}
Form: {document["form"]}
Exhibit: {document["exhibit_type"]}
Filing date: {document["filing_date"]}

DOCUMENT:

{document["text"]}
"""

    raw_result = analyze_text(
        prompt,
        format_schema=FactExtraction.model_json_schema(),
        num_predict=1200,
    )

    result = FactExtraction.model_validate_json(
        raw_result
    )

    return document, result


if __name__ == "__main__":
    EXHIBIT_ID = 28

    document, facts = extract_facts(
        EXHIBIT_ID
    )

    print()
    print(
        json.dumps(
            facts.model_dump(),
            indent=2,
        )
    )