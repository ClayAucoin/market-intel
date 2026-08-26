from datetime import date

from src.company_repository import (
    get_company_by_ticker,
)

from src.company_universe import (
    get_company,
)

from src.financial_history import (
    build_multi_concept_quarterly_history,
)

from src.issuer_repository import (
    get_issuer_history_by_ticker,
)

from src.xbrl_client import (
    get_company_facts,
)


FINANCIAL_METRICS = {
    "revenue": {
        "concepts": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ],
        "unit": "USD",
        "availability": "core",

        "sector_concepts": {
            "Financials": [
                "RevenuesNetOfInterestExpense",
                "Revenues",
            ],
        },
    },

    "net_income": {
        "concepts": [
            "NetIncomeLoss",
            "ProfitLoss",
        ],
        "unit": "USD",
        "availability": "core",
    },

    "diluted_eps": {
        "concepts": [
            "EarningsPerShareDiluted",
        ],
        "unit": "USD/shares",
        "availability": "preferred",
    },

    "operating_income": {
        "concepts": [
            "OperatingIncomeLoss",
        ],
        "unit": "USD",
        "availability": "optional",
    },

    "operating_cash_flow": {
        "concepts": [
            "NetCashProvidedByUsedInOperatingActivities",
        ],
        "unit": "USD",
        "availability": "optional",
    },

    "gross_profit": {
        "concepts": [
            "GrossProfit",
        ],
        "unit": "USD",
        "availability": "optional",
    },
}


def get_metric_concepts(
    ticker,
    metric_name,
):
    metric = FINANCIAL_METRICS.get(
        metric_name
    )

    if metric is None:
        raise ValueError(
            f"Unknown metric: {metric_name}"
        )

    company_config = get_company(
        ticker
    )

    if company_config is not None:
        sector = company_config.get(
            "sector"
        )

        sector_concepts = (
            metric
            .get(
                "sector_concepts",
                {}
            )
            .get(
                sector
            )
        )

        if sector_concepts:
            return sector_concepts

    return metric["concepts"]


def resolve_concepts(
    facts,
    ticker,
    metric_name,
):
    concept_names = get_metric_concepts(
        ticker,
        metric_name,
    )

    us_gaap = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )

    return [
        concept_name
        for concept_name in concept_names
        if concept_name in us_gaap
    ]


def parse_period_end(value):
    if isinstance(value, date):
        return value

    return date.fromisoformat(
        value
    )


def period_belongs_to_issuer(
    period_end,
    issuer,
):
    period_end = parse_period_end(
        period_end
    )

    effective_from = issuer[
        "effective_from"
    ]

    effective_to = issuer[
        "effective_to"
    ]

    if (
        effective_from is not None
        and period_end < effective_from
    ):
        return False

    if (
        effective_to is not None
        and period_end > effective_to
    ):
        return False

    return True


def get_issuer_metric_history(
    ticker,
    issuer,
    metric_name,
):
    metric = FINANCIAL_METRICS[
        metric_name
    ]

    facts = get_company_facts(
        issuer["cik"]
    )

    concepts = resolve_concepts(
        facts,
        ticker,
        metric_name,
    )

    if not concepts:
        return {
            "issuer": issuer,
            "concepts": [],
            "history": [],
        }

    history = (
        build_multi_concept_quarterly_history(
            facts,
            concepts,
            metric["unit"],
        )
    )

    filtered_history = []

    for item in history:
        if not period_belongs_to_issuer(
            item["end"],
            issuer,
        ):
            continue

        filtered_history.append(
            {
                **item,

                "company_id":
                    issuer[
                        "company_id"
                    ],

                "issuer_cik":
                    issuer["cik"],

                "issuer_name":
                    issuer[
                        "company_name"
                    ],
            }
        )

    return {
        "issuer": issuer,
        "concepts": concepts,
        "history": filtered_history,
    }


def choose_issuer_value(
    current,
    candidate,
):
    if current is None:
        return candidate

    current_filed = current.get(
        "filed"
    )

    candidate_filed = candidate.get(
        "filed"
    )

    if (
        candidate_filed is not None
        and (
            current_filed is None
            or candidate_filed
            < current_filed
        )
    ):
        return candidate

    return current


def merge_issuer_histories(
    issuer_results,
):
    merged = {}

    for issuer_result in issuer_results:
        for item in issuer_result[
            "history"
        ]:
            key = item["end"]

            merged[key] = (
                choose_issuer_value(
                    merged.get(key),
                    item,
                )
            )

    return sorted(
        merged.values(),
        key=lambda item:
            item["end"],
    )


def get_metric_history(
    ticker,
    metric_name,
):
    metric = FINANCIAL_METRICS.get(
        metric_name
    )

    if metric is None:
        raise ValueError(
            f"Unknown metric: {metric_name}"
        )

    security_company = (
        get_company_by_ticker(
            ticker
        )
    )

    if security_company is None:
        raise ValueError(
            f"Ticker not found: {ticker}"
        )

    issuers = (
        get_issuer_history_by_ticker(
            ticker
        )
    )

    if not issuers:
        issuers = [
            {
                "company_id":
                    security_company["id"],

                "cik":
                    security_company["cik"],

                "company_name":
                    security_company[
                        "company_name"
                    ],

                "effective_from": None,
                "effective_to": None,
                "is_current": True,
            }
        ]

    issuer_results = []

    for issuer in issuers:
        issuer_results.append(
            get_issuer_metric_history(
                ticker,
                issuer,
                metric_name,
            )
        )

    history = merge_issuer_histories(
        issuer_results
    )

    concepts = []

    for result in issuer_results:
        for concept in result[
            "concepts"
        ]:
            if concept not in concepts:
                concepts.append(
                    concept
                )

    return {
        "company":
            security_company,

        "metric":
            metric_name,

        "concept": (
            " / ".join(concepts)
            if concepts
            else None
        ),

        "concepts":
            concepts,

        "unit":
            metric["unit"],

        "availability":
            metric["availability"],

        "issuers":
            issuers,

        "history":
            history,
    }


def test_company_metrics(ticker):
    print()
    print(
        f"{ticker} FINANCIAL METRICS"
    )

    print("=" * 110)

    print(
        f"{'Metric':<24}"
        f"{'Availability':<14}"
        f"{'Records':>10}  "
        f"{'Concepts'}"
    )

    print("-" * 110)

    for metric_name, metric in (
        FINANCIAL_METRICS.items()
    ):
        try:
            result = get_metric_history(
                ticker,
                metric_name,
            )

            concept_text = (
                result["concept"]
                if result["concept"]
                else "NOT AVAILABLE"
            )

            print(
                f"{metric_name:<24}"
                f"{metric['availability']:<14}"
                f"{len(result['history']):>10}  "
                f"{concept_text}"
            )

        except Exception as error:
            print(
                f"{metric_name:<24}"
                f"{metric['availability']:<14}"
                f"{'-':>10}  ERROR"
            )

            print(
                f"  {error}"
            )


if __name__ == "__main__":
    for ticker in [
        "JPM",
        "XOM",
        "GOOGL",
        "CAT",
    ]:
        test_company_metrics(
            ticker
        )

        print()