from src.financials.financial_metrics import (
    FINANCIAL_METRICS,
    get_metric_history,
)

from src.financials.financial_repository import (
    save_financial_history,
)


def import_financial_metrics(ticker):
    print(
        f"Importing financial metrics "
        f"for {ticker}"
    )

    print()

    for metric_name in FINANCIAL_METRICS:
        print(
            f"Importing {metric_name}..."
        )

        try:
            result = get_metric_history(
                ticker,
                metric_name,
            )

            save_financial_history(
                company_id=
                    result["company"]["id"],

                metric=
                    result["metric"],

                concept=
                    result["concept"],

                unit=
                    result["unit"],

                history=
                    result["history"],
            )

        except Exception as error:
            print(
                f"ERROR importing "
                f"{metric_name}: {error}"
            )

        print()


if __name__ == "__main__":
    import_financial_metrics(
        "DELL"
    )