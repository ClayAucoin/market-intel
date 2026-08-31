from src.database import get_connection


TICKERS = [
    "DUK",
    "NEE",
    "V",
]


def get_financial_fact_columns():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'financial_facts'
                ORDER BY ordinal_position;
                """
            )

            return [
                row[0]
                for row in cursor.fetchall()
            ]


def get_securities():
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


def print_columns(columns):
    print()
    print(
        "FINANCIAL_FACTS COLUMNS"
    )

    print("=" * 70)

    for column in columns:
        print(
            column
        )


def find_concept_column(columns):
    candidates = [
        "concept",
        "concept_name",
        "tag",
        "fact_name",
        "name",
        "xbrl_concept",
    ]

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def find_value_column(columns):
    candidates = [
        "value",
        "numeric_value",
        "amount",
        "fact_value",
    ]

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


def print_concept_summary(
    securities,
    concept_column,
):
    print()
    print(
        "CONCEPT SUMMARY"
    )

    print("=" * 120)

    for security_id, ticker in securities:
        print()
        print(
            ticker
        )

        print("-" * 120)

        with get_connection() as conn:
            with conn.cursor() as cursor:
                query = f"""
                    SELECT
                        "{concept_column}",
                        COUNT(*) AS rows,
                        MIN(period_end),
                        MAX(period_end),
                        MIN(filed_date),
                        MAX(filed_date)

                    FROM financial_facts

                    WHERE security_id = %s

                    GROUP BY
                        "{concept_column}"

                    ORDER BY
                        MAX(period_end) DESC,
                        COUNT(*) DESC,
                        "{concept_column}";
                """

                cursor.execute(
                    query,
                    (security_id,),
                )

                rows = cursor.fetchall()

        print(
            f"{'Concept':<55}"
            f"{'Rows':>7}"
            f"{'First Period':>14}"
            f"{'Last Period':>14}"
            f"{'Last Filed':>14}"
        )

        print("-" * 120)

        for row in rows:
            (
                concept,
                count,
                first_period,
                last_period,
                first_filed,
                last_filed,
            ) = row

            print(
                f"{str(concept):<55}"
                f"{count:>7}"
                f"{str(first_period or '-'):>14}"
                f"{str(last_period or '-'):>14}"
                f"{str(last_filed or '-'):>14}"
            )


def print_recent_facts(
    securities,
    concept_column,
    value_column,
):
    print()
    print(
        "RECENT FINANCIAL FACTS"
    )

    print("=" * 150)

    for security_id, ticker in securities:
        print()
        print(
            ticker
        )

        print("-" * 150)

        with get_connection() as conn:
            with conn.cursor() as cursor:
                if value_column:
                    query = f"""
                        SELECT
                            "{concept_column}",
                            "{value_column}",
                            period_start,
                            period_end,
                            filed_date
                        FROM financial_facts
                        WHERE security_id = %s
                        ORDER BY
                            period_end DESC,
                            filed_date DESC,
                            "{concept_column}"
                        LIMIT 60;
                    """
                else:
                    query = f"""
                        SELECT
                            "{concept_column}",
                            NULL,
                            period_start,
                            period_end,
                            filed_date
                        FROM financial_facts
                        WHERE security_id = %s
                        ORDER BY
                            period_end DESC,
                            filed_date DESC,
                            "{concept_column}"
                        LIMIT 60;
                    """

                cursor.execute(
                    query,
                    (security_id,),
                )

                rows = cursor.fetchall()

        print(
            f"{'Concept':<55}"
            f"{'Value':>22}"
            f"{'Period Start':>14}"
            f"{'Period End':>14}"
            f"{'Filed':>14}"
        )

        print("-" * 150)

        for row in rows:
            (
                concept,
                value,
                period_start,
                period_end,
                filed_date,
            ) = row

            print(
                f"{str(concept):<55}"
                f"{str(value if value is not None else '-'):>22}"
                f"{str(period_start or '-'):>14}"
                f"{str(period_end or '-'):>14}"
                f"{str(filed_date or '-'):>14}"
            )


def main():
    columns = get_financial_fact_columns()

    print()
    print(
        "DUK / NEE / V FINANCIAL FACT "
        "CONCEPT DIAGNOSTIC"
    )

    print_columns(
        columns
    )

    concept_column = find_concept_column(
        columns
    )

    value_column = find_value_column(
        columns
    )

    print()
    print(
        "Detected concept column:",
        concept_column or "NONE",
    )

    print(
        "Detected value column:",
        value_column or "NONE",
    )

    if concept_column is None:
        print()
        print(
            "Unable to continue because no "
            "concept-name column was detected."
        )

        return

    securities = get_securities()

    print_concept_summary(
        securities,
        concept_column,
    )

    print_recent_facts(
        securities,
        concept_column,
        value_column,
    )


if __name__ == "__main__":
    main()