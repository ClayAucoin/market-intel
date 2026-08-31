import json

from pydantic import BaseModel, Field

from src.ai.ai_client import analyze_text
from src.ai.document_service import download_exhibit_text


class Fact(BaseModel):
    type: str
    value: str
    comparison: str | None = None
    evidence: str


class Risk(BaseModel):
    risk: str
    evidence: str


class DocumentAnalysis(BaseModel):
    event_type: str

    sentiment: str = Field(
        pattern="^(positive|negative|mixed|neutral)$"
    )

    materiality: str = Field(
        pattern="^(high|medium|low)$"
    )

    summary: str

    facts: list[Fact]

    risks: list[Risk]

    investment_implications: list[str]


def analyze_exhibit(exhibit_id):
    document = download_exhibit_text(
        exhibit_id
    )

    prompt = f"""
Analyze this SEC filing exhibit for investment research.

Company: {document["company_name"]}
Ticker: {document["ticker"]}
Form: {document["form"]}
Exhibit: {document["exhibit_type"]}
Filing date: {document["filing_date"]}

Instructions:

- Use only information found in the supplied document.
- Do not invent facts.
- Extract the most important financial and business facts.
- Every fact must include a short evidence excerpt.
- Every risk must include supporting evidence.
- Keep evidence excerpts short.
- If no clear risks are stated, return an empty risks list.
- Investment implications are interpretations, not facts.
- Keep the summary concise.

DOCUMENT:

{document["text"]}
"""

    raw_result = analyze_text(
        prompt,
        format_schema=DocumentAnalysis.model_json_schema(),
        num_predict=1200,
    )

    analysis = DocumentAnalysis.model_validate_json(
        raw_result
    )

    return document, analysis


if __name__ == "__main__":
    EXHIBIT_ID = 28

    document, analysis = analyze_exhibit(
        EXHIBIT_ID
    )

    print()

    print(
        json.dumps(
            analysis.model_dump(),
            indent=2,
        )
    )