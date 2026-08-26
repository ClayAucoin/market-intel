import sys

from src.company_universe import (
    DEFAULT_UNIVERSE,
    get_companies,
)

from src.financial_metrics import (
    FINANCIAL_METRICS,
    get_metric_history,
)

from src.financial_repository import (
    save_financial_history,
)


def import_company_metrics(
    ticker,
):
    print()
    print(
        f"Importing financial metrics "
        f"for {ticker}"
    )

    print("-" * 70)

    imported = 0
    skipped = 0

    for metric_name, metric_config in (
        FINANCIAL_METRICS.items()
    ):
        print(
            f"{metric_name}:",
            end=" ",
        )

        try:
            result = get_metric_history(
                ticker,
                metric_name,
            )

            history = result[
                "history"
            ]

            if not history:
                availability = (
                    metric_config[
                        "availability"
                    ]
                )

                if availability == "core":
                    print(
                        "MISSING CORE DATA"
                    )

                elif availability == "preferred":
                    print(
                        "preferred unavailable"
                    )

                else:
                    print(
                        "optional unavailable"
                    )

                skipped += 1
                continue

            count = save_financial_history(
                ticker=ticker,
                metric=metric_name,
                unit=result["unit"],
                history=history,
            )

            imported += count

        except Exception as error:
            print(
                f"ERROR: {error}"
            )

            skipped += 1

    return {
        "ticker": ticker,
        "imported": imported,
        "skipped": skipped,
    }


def get_universe_name():
    if len(sys.argv) >= 2:
        return sys.argv[1]

    return DEFAULT_UNIVERSE


def import_universe(
    universe_name=None,
):
    if universe_name is None:
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

    summaries = []

    print()
    print(
        "MARKET INTEL UNIVERSE "
        "FINANCIAL IMPORT"
    )

    print(
        "Universe:",
        universe_name,
    )

    print("=" * 70)

    for company in companies:
        result = import_company_metrics(
            company["ticker"]
        )

        summaries.append(
            result
        )

    print()
    print("=" * 70)

    print(
        "IMPORT SUMMARY"
    )

    print()

    print(
        f"{'Ticker':<10}"
        f"{'Records':>12}"
        f"{'Skipped':>12}"
    )

    print("-" * 34)

    total_records = 0
    total_skipped = 0

    for summary in summaries:
        print(
            f"{summary['ticker']:<10}"
            f"{summary['imported']:>12}"
            f"{summary['skipped']:>12}"
        )

        total_records += (
            summary["imported"]
        )

        total_skipped += (
            summary["skipped"]
        )

    print("-" * 34)

    print(
        f"{'TOTAL':<10}"
        f"{total_records:>12}"
        f"{total_skipped:>12}"
    )


if __name__ == "__main__":
    import_universe()