from datetime import date, timedelta
from decimal import Decimal

import requests

from src.database import get_connection
from src.financials.financial_repository import save_financial_history


FDIC_FINANCIALS_URL = (
    "https://api.fdic.gov/banks/financials"
)

BANKS = {
    "FRC": {
        "cert": 59017,
    },
    "SBNY": {
        "cert": 57053,
    },
}


def get_company_id(
    ticker,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.company_id

                FROM securities s

                WHERE UPPER(s.ticker) =
                      UPPER(%s)

                ORDER BY
                    s.is_primary DESC,
                    s.id

                LIMIT 1;
                """,
                (
                    ticker,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Company not found for {ticker}"
        )

    return row[0]


def fetch_fdic_history(
    cert,
):
    response = requests.get(
        FDIC_FINANCIALS_URL,
        params={
            "filters": f"CERT:{cert}",
            "fields": (
                "REPDTE,"
                "NIM,"
                "NONII,"
                "NONIX,"
                "NETINC"
            ),
            "limit": 500,
            "sort_by": "REPDTE",
            "sort_order": "ASC",
            "format": "json",
        },
        timeout=30,
    )

    response.raise_for_status()

    return [
        item["data"]
        for item
        in response.json().get(
            "data",
            []
        )
    ]


def parse_report_date(
    value,
):
    value = str(value)

    return date(
        int(value[0:4]),
        int(value[4:6]),
        int(value[6:8]),
    )


def fiscal_period(
    report_date,
):
    quarter = (
        (
            report_date.month - 1
        )
        // 3
        + 1
    )

    return f"Q{quarter}"


def quarter_start(
    report_date,
):
    quarter = (
        (
            report_date.month - 1
        )
        // 3
        + 1
    )

    month = (
        (quarter - 1)
        * 3
        + 1
    )

    return date(
        report_date.year,
        month,
        1,
    )


def as_decimal(
    value,
):
    if value is None:
        return None

    return Decimal(
        str(value)
    )


def standalone_quarter_value(
    current_value,
    previous_value,
    quarter,
):
    current_value = as_decimal(
        current_value
    )

    if current_value is None:
        return None

    if quarter == 1:
        return current_value

    previous_value = as_decimal(
        previous_value
    )

    if previous_value is None:
        return None

    return (
        current_value
        - previous_value
    )


def build_quarterly_records(
    ticker,
    rows,
):
    company_id = get_company_id(
        ticker
    )

    results = {
        "revenue": [],
        "operating_income": [],
        "net_income": [],
    }

    previous = {}

    for row in rows:
        report_date = parse_report_date(
            row["REPDTE"]
        )

        year = report_date.year

        quarter = (
            (
                report_date.month - 1
            )
            // 3
            + 1
        )

        prior = previous.get(
            year,
            {}
        )

        nim = standalone_quarter_value(
            row.get("NIM"),
            prior.get("NIM"),
            quarter,
        )

        noninterest_income = (
            standalone_quarter_value(
                row.get("NONII"),
                prior.get("NONII"),
                quarter,
            )
        )

        noninterest_expense = (
            standalone_quarter_value(
                row.get("NONIX"),
                prior.get("NONIX"),
                quarter,
            )
        )

        net_income = (
            standalone_quarter_value(
                row.get("NETINC"),
                prior.get("NETINC"),
                quarter,
            )
        )

        previous[year] = row

        if (
            nim is None
            or noninterest_income is None
        ):
            continue

        revenue = (
            nim
            + noninterest_income
        )

        operating_income = None

        if noninterest_expense is not None:
            operating_income = (
                revenue
                - noninterest_expense
            )

        filed_date = (
            report_date
            + timedelta(
                days=30
            )
        )

        common = {
            "company_id": company_id,
            "fy": year,
            "fp": fiscal_period(
                report_date
            ),
            "start": quarter_start(
                report_date
            ),
            "end": report_date,
            "filed": filed_date,
            "accn": (
                f"FDIC-{ticker}-"
                f"{report_date:%Y%m%d}"
            ),
            "derived": True,
        }

        results["revenue"].append(
            {
                **common,
                "concept": (
                    "FDIC_NIM_PLUS_NONII"
                ),
                "value": (
                    revenue
                    * Decimal("1000")
                ),
            }
        )

        if operating_income is not None:
            results[
                "operating_income"
            ].append(
                {
                    **common,
                    "concept": (
                        "FDIC_NIM_PLUS_"
                        "NONII_MINUS_NONIX"
                    ),
                    "value": (
                        operating_income
                        * Decimal("1000")
                    ),
                }
            )

        if net_income is not None:
            results[
                "net_income"
            ].append(
                {
                    **common,
                    "concept": (
                        "FDIC_NETINC"
                    ),
                    "value": (
                        net_income
                        * Decimal("1000")
                    ),
                }
            )

    return results


def import_bank(
    ticker,
    cert,
):
    print()
    print(
        f"Importing FDIC financials "
        f"for {ticker}"
    )
    print("=" * 70)

    rows = fetch_fdic_history(
        cert
    )

    histories = (
        build_quarterly_records(
            ticker,
            rows,
        )
    )

    total = 0

    for metric in (
        "revenue",
        "operating_income",
        "net_income",
    ):
        count = save_financial_history(
            ticker=ticker,
            metric=metric,
            unit="USD",
            history=histories[
                metric
            ],
        )

        total += count

    print(
        f"Total {ticker} records "
        f"saved: {total:,}"
    )

    return total


def main():
    grand_total = 0

    for ticker, config in BANKS.items():
        grand_total += import_bank(
            ticker,
            config["cert"],
        )

    print()
    print("=" * 70)
    print(
        f"Total FDIC records saved: "
        f"{grand_total:,}"
    )


if __name__ == "__main__":
    main()