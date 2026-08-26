from src.database import get_connection


def get_security_id(
    ticker,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id

                FROM securities

                WHERE UPPER(ticker) =
                      UPPER(%s)

                ORDER BY
                    is_primary DESC,
                    id

                LIMIT 1;
                """,
                (
                    ticker,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Security not found: {ticker}"
        )

    return row[0]


def save_financial_history(
    ticker,
    metric,
    unit,
    history,
):
    security_id = get_security_id(
        ticker
    )

    rows = []

    for item in history:
        company_id = item.get(
            "company_id"
        )

        concept = item.get(
            "concept"
        )

        if company_id is None:
            raise ValueError(
                f"{ticker} {metric} history "
                "item is missing company_id."
            )

        if concept is None:
            raise ValueError(
                f"{ticker} {metric} history "
                "item is missing concept."
            )

        rows.append(
            (
                security_id,
                company_id,
                metric,
                concept,
                unit,
                item.get("fy"),
                item.get("fp"),
                item.get("start"),
                item.get("end"),
                item.get("value"),
                item.get("filed"),
                item.get("accn"),
                item.get(
                    "derived",
                    False,
                ),
            )
        )

    if not rows:
        print(
            f"No records found for "
            f"{ticker} {metric}."
        )
        return 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO financial_facts (
                    security_id,
                    company_id,

                    metric,
                    concept,
                    unit,

                    fiscal_year,
                    fiscal_period,

                    period_start,
                    period_end,

                    value,

                    filed_date,
                    accession_number,

                    is_derived
                )

                VALUES (
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s,
                    %s, %s,
                    %s
                )

                ON CONFLICT (
                    security_id,
                    company_id,
                    metric,
                    period_end
                )

                DO UPDATE SET

                    concept =
                        EXCLUDED.concept,

                    unit =
                        EXCLUDED.unit,

                    fiscal_year =
                        EXCLUDED.fiscal_year,

                    fiscal_period =
                        EXCLUDED.fiscal_period,

                    period_start =
                        EXCLUDED.period_start,

                    value =
                        EXCLUDED.value,

                    filed_date =
                        EXCLUDED.filed_date,

                    accession_number =
                        EXCLUDED.accession_number,

                    is_derived =
                        EXCLUDED.is_derived,

                    updated_at =
                        CURRENT_TIMESTAMP;
                """,
                rows,
            )

    print(
        f"Saved {len(rows):,} "
        f"{ticker} {metric} records."
    )

    return len(rows)