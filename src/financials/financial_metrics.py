from datetime import date

from src.data.company_repository import (
    get_company_by_ticker,
)

from src.universe.company_universe import (
    get_company,
)

from src.financials.financial_history import (
    build_multi_concept_quarterly_history,
)

from src.data.issuer_repository import (
    get_issuer_history_by_ticker,
)

from src.sec.xbrl_client import (
    get_company_facts,
    get_quarterly_values,
)


FINANCIAL_METRICS = {
    "revenue": {
        "concepts": [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
            "RegulatedAndUnregulatedOperatingRevenue",
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


BANK_REVENUE_COMPONENTS = [
    "InterestIncomeExpenseNet",
    "NoninterestIncome",
]


BANK_REVENUE_CONCEPT = (
    "InterestIncomeExpenseNet"
    " + NoninterestIncome"
)


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

    concepts = list(
        metric["concepts"]
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
                sector,
                []
            )
        )

        concepts = (
            sector_concepts
            + [
                concept
                for concept in concepts
                if concept
                not in sector_concepts
            ]
        )

    return concepts


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


def is_financial_company(
    ticker,
):
    company_config = get_company(
        ticker
    )

    if company_config is None:
        return False

    return (
        company_config.get("sector")
        == "Financials"
    )


def get_bank_revenue_history(
    facts,
):
    component_histories = {}

    for concept_name in (
        BANK_REVENUE_COMPONENTS
    ):
        values = get_quarterly_values(
            facts,
            concept_name,
            "USD",
        )

        if not values:
            return []

        component_histories[
            concept_name
        ] = {
            value["end"]: value
            for value in values
        }

    common_periods = set(
        component_histories[
            BANK_REVENUE_COMPONENTS[0]
        ]
    )

    for concept_name in (
        BANK_REVENUE_COMPONENTS[1:]
    ):
        common_periods &= set(
            component_histories[
                concept_name
            ]
        )

    history = []

    for period_end in sorted(
        common_periods
    ):
        interest_value = (
            component_histories[
                "InterestIncomeExpenseNet"
            ][period_end]
        )

        noninterest_value = (
            component_histories[
                "NoninterestIncome"
            ][period_end]
        )

        #
        # Both components must describe
        # the same standalone quarter.
        #
        if (
            interest_value.get("start")
            != noninterest_value.get(
                "start"
            )
        ):
            continue

        filed_dates = [
            filed
            for filed in [
                interest_value.get(
                    "filed"
                ),
                noninterest_value.get(
                    "filed"
                ),
            ]
            if filed is not None
        ]

        filed = (
            max(filed_dates)
            if filed_dates
            else None
        )

        accessions = [
            accn
            for accn in [
                interest_value.get(
                    "accn"
                ),
                noninterest_value.get(
                    "accn"
                ),
            ]
            if accn
        ]

        accession = (
            accessions[0]
            if accessions
            else None
        )

        history.append(
            {
                "fy":
                    interest_value.get(
                        "fy"
                    ),

                "fp":
                    interest_value.get(
                        "fp"
                    ),

                "start":
                    interest_value.get(
                        "start"
                    ),

                "end":
                    period_end,

                "value": (
                    interest_value[
                        "value"
                    ]
                    + noninterest_value[
                        "value"
                    ]
                ),

                #
                # The combined value was
                # not fully public until
                # both components were
                # available.
                #
                "filed":
                    filed,

                "accn":
                    accession,

                "days":
                    interest_value.get(
                        "days"
                    ),

                "derived":
                    True,

                "concept":
                    BANK_REVENUE_CONCEPT,
            }
        )

    return history


def supplement_bank_revenue_history(
    ticker,
    facts,
    history,
):
    if not is_financial_company(
        ticker
    ):
        return history

    bank_history = (
        get_bank_revenue_history(
            facts
        )
    )

    if not bank_history:
        return history

    #
    # Keep directly reported / existing
    # revenue history whenever we already
    # have a quarter.
    #
    # The bank-specific construction only
    # fills missing quarterly periods.
    #
    merged = {
        item["end"]: item
        for item in history
    }

    for item in bank_history:
        if item["end"] in merged:
            continue

        merged[item["end"]] = item

    return sorted(
        merged.values(),
        key=lambda item:
            item["end"],
    )


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

    if metric_name == "revenue":
        history = (
            supplement_bank_revenue_history(
                ticker,
                facts,
                history,
            )
        )

        if (
            any(
                item.get("concept")
                == BANK_REVENUE_CONCEPT
                for item in history
            )
        ):
            for concept_name in (
                BANK_REVENUE_COMPONENTS
            ):
                if (
                    concept_name
                    not in concepts
                ):
                    concepts.append(
                        concept_name
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