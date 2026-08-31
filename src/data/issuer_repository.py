from src.database import get_connection


def get_issuer_history_by_ticker(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.cik,
                    c.company_name,
                    sih.effective_from,
                    sih.effective_to,
                    sih.is_current

                FROM security_issuer_history sih

                JOIN securities s
                    ON s.id = sih.security_id

                JOIN companies c
                    ON c.id = sih.company_id

                WHERE UPPER(s.ticker) =
                      UPPER(%s)

                ORDER BY
                    sih.effective_from
                    NULLS FIRST,
                    c.id;
                """,
                (ticker,),
            )

            rows = cursor.fetchall()

    return [
        {
            "company_id": row[0],
            "cik": row[1],
            "company_name": row[2],
            "effective_from": row[3],
            "effective_to": row[4],
            "is_current": row[5],
        }
        for row in rows
    ]