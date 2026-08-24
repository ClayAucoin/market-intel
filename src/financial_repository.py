from src.database import get_connection


def save_financial_history(
    company_id,
    metric,
    concept,
    unit,
    history,
):
    rows = []

    for item in history:
        rows.append(
            (
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
                item.get("derived", False),
            )
        )

    if not rows:
        print(
            f"No records found for {metric}."
        )
        return

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO financial_facts (
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
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )

                ON CONFLICT (
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
        f"{metric} records."
    )