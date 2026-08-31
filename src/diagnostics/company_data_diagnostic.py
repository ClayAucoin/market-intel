from src.database import get_connection


TICKERS = [
    "NEE",
    "DUK",
    "V",
]


def get_security_ids():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    ticker
                FROM securities
                WHERE ticker = ANY(%s)
                ORDER BY ticker;
                """,
                (TICKERS,),
            )

            return cursor.fetchall()


def get_security_id_tables():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    table_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND column_name = 'security_id'
                ORDER BY table_name;
                """
            )

            return [
                row[0]
                for row in cursor.fetchall()
            ]


def get_table_columns(table_name):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position;
                """,
                (table_name,),
            )

            return [
                row[0]
                for row in cursor.fetchall()
            ]


def count_rows(
    table_name,
    security_id,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            query = (
                f'SELECT COUNT(*) '
                f'FROM "{table_name}" '
                f'WHERE security_id = %s;'
            )

            cursor.execute(
                query,
                (security_id,),
            )

            return cursor.fetchone()[0]


def get_date_range(
    table_name,
    security_id,
    columns,
):
    candidate_columns = [
        "entry_date",
        "filing_date",
        "filed_date",
        "report_date",
        "period_end",
        "period_start",
        "created_at",
        "updated_at",
    ]

    date_columns = [
        column
        for column in candidate_columns
        if column in columns
    ]

    results = []

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for column in date_columns:
                query = (
                    f'SELECT '
                    f'MIN("{column}"), '
                    f'MAX("{column}") '
                    f'FROM "{table_name}" '
                    f'WHERE security_id = %s;'
                )

                cursor.execute(
                    query,
                    (security_id,),
                )

                minimum, maximum = (
                    cursor.fetchone()
                )

                if (
                    minimum is not None
                    or maximum is not None
                ):
                    results.append(
                        (
                            column,
                            minimum,
                            maximum,
                        )
                    )

    return results


def print_security_summary(
    securities,
):
    print()
    print(
        "SECURITY RECORDS"
    )

    print("=" * 50)

    print(
        f"{'Ticker':<10}"
        f"{'Security ID':>14}"
    )

    print("-" * 50)

    for security_id, ticker in securities:
        print(
            f"{ticker:<10}"
            f"{security_id:>14}"
        )


def print_table_coverage(
    securities,
    tables,
):
    print()
    print(
        "TABLE COVERAGE"
    )

    print("=" * 110)

    for table_name in tables:
        columns = get_table_columns(
            table_name
        )

        counts = []

        for (
            security_id,
            ticker,
        ) in securities:
            count = count_rows(
                table_name,
                security_id,
            )

            counts.append(
                (
                    ticker,
                    security_id,
                    count,
                )
            )

        if not any(
            count > 0
            for _, _, count in counts
        ):
            continue

        print()
        print(
            table_name
        )

        print("-" * 110)

        print(
            f"{'Ticker':<10}"
            f"{'Rows':>10}"
            f"{'Date Column':<24}"
            f"{'Earliest':>24}"
            f"{'Latest':>24}"
        )

        for (
            ticker,
            security_id,
            count,
        ) in counts:
            if count == 0:
                print(
                    f"{ticker:<10}"
                    f"{count:>10}"
                )

                continue

            ranges = get_date_range(
                table_name,
                security_id,
                columns,
            )

            if not ranges:
                print(
                    f"{ticker:<10}"
                    f"{count:>10}"
                    f"{'-':<24}"
                    f"{'-':>24}"
                    f"{'-':>24}"
                )

                continue

            first = True

            for (
                column,
                minimum,
                maximum,
            ) in ranges:
                display_ticker = (
                    ticker
                    if first
                    else ""
                )

                display_count = (
                    str(count)
                    if first
                    else ""
                )

                print(
                    f"{display_ticker:<10}"
                    f"{display_count:>10}"
                    f"{column:<24}"
                    f"{str(minimum):>24}"
                    f"{str(maximum):>24}"
                )

                first = False


def main():
    securities = get_security_ids()

    print()
    print(
        "NEE / DUK / V DATA DIAGNOSTIC"
    )

    print_security_summary(
        securities
    )

    tables = get_security_id_tables()

    print()
    print(
        "Tables containing security_id:",
        len(tables),
    )

    print_table_coverage(
        securities,
        tables,
    )


if __name__ == "__main__":
    main()