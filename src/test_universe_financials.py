import sys

from src.company_universe import (
    DEFAULT_UNIVERSE,
    get_companies,
)

from src.financial_metrics import (
    FINANCIAL_METRICS,
    get_metric_history,
)


def test_company(ticker):
    results = []

    for metric_name, metric in (
        FINANCIAL_METRICS.items()
    ):
        availability = metric[
            "availability"
        ]

        try:
            result = get_metric_history(
                ticker,
                metric_name,
            )

            records = len(
                result["history"]
            )

            if records > 0:
                status = "OK"

            elif availability == "core":
                status = "CORE MISSING"

            elif availability == "preferred":
                status = "PREFERRED"

            else:
                status = "OPTIONAL"

            results.append(
                {
                    "metric":
                        metric_name,

                    "availability":
                        availability,

                    "concept":
                        result["concept"],

                    "records":
                        records,

                    "status":
                        status,

                    "error":
                        None,
                }
            )

        except Exception as error:
            results.append(
                {
                    "metric":
                        metric_name,

                    "availability":
                        availability,

                    "concept":
                        None,

                    "records":
                        0,

                    "status":
                        "ERROR",

                    "error":
                        str(error),
                }
            )

    return results


def print_company_results(
    company,
    results,
):
    ticker = company["ticker"]

    print()
    print(
        f"{ticker} - "
        f"{company['name']}"
    )

    print("-" * 116)

    print(
        f"{'Metric':<24}"
        f"{'Availability':<14}"
        f"{'Status':<16}"
        f"{'Records':>10}  "
        f"{'Concept'}"
    )

    print("-" * 116)

    for result in results:
        concept = (
            result["concept"]
            if result["concept"]
            else "-"
        )

        print(
            f"{result['metric']:<24}"
            f"{result['availability']:<14}"
            f"{result['status']:<16}"
            f"{result['records']:>10}  "
            f"{concept}"
        )

        if result["error"]:
            print(
                f"  ERROR: "
                f"{result['error']}"
            )


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def main():
    universe_name = (
        get_universe_name()
    )

    companies = get_companies(
        universe_name
    )

    if not companies:
        raise ValueError(
            f"Universe not found or empty: "
            f"{universe_name}"
        )

    print()
    print(
        "MARKET INTEL UNIVERSE "
        "FINANCIAL TEST"
    )

    print(
        "Universe:",
        universe_name,
    )

    print("=" * 116)

    total_metrics = 0
    available = 0

    core_missing = 0
    preferred_unavailable = 0
    optional_unavailable = 0

    errors = 0

    company_attention = []

    for company in companies:
        results = test_company(
            company["ticker"]
        )

        print_company_results(
            company,
            results,
        )

        company_core_missing = 0
        company_preferred_unavailable = 0
        company_errors = 0

        for result in results:
            total_metrics += 1

            status = result[
                "status"
            ]

            if status == "OK":
                available += 1

            elif status == "CORE MISSING":
                core_missing += 1
                company_core_missing += 1

            elif status == "PREFERRED":
                preferred_unavailable += 1
                company_preferred_unavailable += 1

            elif status == "OPTIONAL":
                optional_unavailable += 1

            else:
                errors += 1
                company_errors += 1

        if (
            company_core_missing > 0
            or company_preferred_unavailable > 0
            or company_errors > 0
        ):
            company_attention.append(
                {
                    "ticker":
                        company["ticker"],

                    "core_missing":
                        company_core_missing,

                    "preferred_unavailable":
                        company_preferred_unavailable,

                    "errors":
                        company_errors,
                }
            )

    print()
    print("=" * 116)

    print(
        "SUMMARY"
    )

    print(
        "Universe:",
        universe_name,
    )

    print(
        "Companies:",
        len(companies),
    )

    print(
        "Metrics tested:",
        total_metrics,
    )

    print(
        "Available:",
        available,
    )

    print(
        "Core missing:",
        core_missing,
    )

    print(
        "Preferred unavailable:",
        preferred_unavailable,
    )

    print(
        "Optional unavailable:",
        optional_unavailable,
    )

    print(
        "Errors:",
        errors,
    )

    if company_attention:
        print()
        print(
            "COMPANIES NEEDING ATTENTION"
        )

        print("-" * 78)

        print(
            f"{'Ticker':<12}"
            f"{'Core Missing':>16}"
            f"{'Preferred Missing':>20}"
            f"{'Errors':>12}"
        )

        print("-" * 78)

        for item in company_attention:
            print(
                f"{item['ticker']:<12}"
                f"{item[
                    'core_missing'
                ]:>16}"
                f"{item[
                    'preferred_unavailable'
                ]:>20}"
                f"{item['errors']:>12}"
            )


if __name__ == "__main__":
    main()