from src.company_universe import (
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

            elif metric["required"]:
                status = "MISSING"

            else:
                status = "OPTIONAL"

            results.append(
                {
                    "metric":
                        metric_name,

                    "required":
                        metric["required"],

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

                    "required":
                        metric["required"],

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

    print("-" * 110)

    print(
        f"{'Metric':<24}"
        f"{'Required':<12}"
        f"{'Status':<12}"
        f"{'Records':>10}  "
        f"{'Concept'}"
    )

    print("-" * 110)

    for result in results:
        concept = (
            result["concept"]
            if result["concept"]
            else "-"
        )

        print(
            f"{result['metric']:<24}"
            f"{str(result['required']):<12}"
            f"{result['status']:<12}"
            f"{result['records']:>10}  "
            f"{concept}"
        )

        if result["error"]:
            print(
                f"  ERROR: "
                f"{result['error']}"
            )


def main():
    companies = get_companies()

    print()
    print(
        "MARKET INTEL UNIVERSE "
        "FINANCIAL TEST"
    )

    print("=" * 110)

    total_metrics = 0
    available = 0
    optional_unavailable = 0
    required_missing = 0
    errors = 0

    for company in companies:
        results = test_company(
            company["ticker"]
        )

        print_company_results(
            company,
            results,
        )

        for result in results:
            total_metrics += 1

            if (
                result["status"]
                == "OK"
            ):
                available += 1

            elif (
                result["status"]
                == "OPTIONAL"
            ):
                optional_unavailable += 1

            elif (
                result["status"]
                == "MISSING"
            ):
                required_missing += 1

            else:
                errors += 1

    print()
    print("=" * 110)

    print(
        "SUMMARY"
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
        "Optional unavailable:",
        optional_unavailable,
    )

    print(
        "Required missing:",
        required_missing,
    )

    print(
        "Errors:",
        errors,
    )


if __name__ == "__main__":
    main()