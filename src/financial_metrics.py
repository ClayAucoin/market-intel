from src.company_repository import get_company_by_ticker
from src.financial_history import build_quarterly_history
from src.xbrl_client import get_company_facts


FINANCIAL_METRICS = {
    "revenue": {
        "concept": "Revenues",
        "unit": "USD",
    },
    "operating_income": {
        "concept": "OperatingIncomeLoss",
        "unit": "USD",
    },
    "net_income": {
        "concept": "NetIncomeLoss",
        "unit": "USD",
    },
    "diluted_eps": {
        "concept": "EarningsPerShareDiluted",
        "unit": "USD/shares",
    },
    "operating_cash_flow": {
        "concept": "NetCashProvidedByUsedInOperatingActivities",
        "unit": "USD",
    },
    "gross_profit": {
        "concept": "GrossProfit",
        "unit": "USD",
    },
}


def get_metric_history(ticker, metric_name):
    metric = FINANCIAL_METRICS.get(metric_name)

    if metric is None:
        raise ValueError(
            f"Unknown metric: {metric_name}"
        )

    company = get_company_by_ticker(ticker)

    if company is None:
        raise ValueError(
            f"Ticker not found: {ticker}"
        )

    facts = get_company_facts(
        company["cik"]
    )

    history = build_quarterly_history(
        facts,
        metric["concept"],
        metric["unit"],
    )

    return {
        "company": company,
        "metric": metric_name,
        "concept": metric["concept"],
        "unit": metric["unit"],
        "history": history,
    }


if __name__ == "__main__":
    result = get_metric_history(
        "DELL",
        "diluted_eps",
    )

    print(
        result["company"]["ticker"],
        result["metric"],
    )

    print()

    for item in result["history"][-12:]:
        source = (
            "DERIVED"
            if item["derived"]
            else "REPORTED"
        )

        print(
            item["end"],
            "| FY:",
            item["fy"],
            "| FP:",
            item["fp"],
            "| Value:",
            item["value"],
            "|",
            source,
            "| Filed:",
            item["filed"],
        )