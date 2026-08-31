from src.database import get_connection


def normalize_cik(cik):
    return str(cik).zfill(10)


def save_company(
    cik,
    ticker=None,
    company_name=None,
    exchange=None,
):
    #
    # Support dictionary input too.
    #
    if isinstance(cik, dict):
        company = cik

        cik = company.get("cik")
        ticker = company.get("ticker")
        company_name = (
            company.get("company_name")
            or company.get("title")
            or company.get("name")
        )
        exchange = company.get(
            "exchange"
        )

    cik = normalize_cik(cik)

    if not company_name:
        raise ValueError(
            "company_name is required"
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO companies (
                    cik,
                    ticker,
                    company_name,
                    exchange
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (cik)
                DO UPDATE SET
                    company_name =
                        EXCLUDED.company_name,

                    updated_at =
                        CURRENT_TIMESTAMP

                RETURNING id;
                """,
                (
                    cik,
                    ticker,
                    company_name,
                    exchange,
                ),
            )

            company_id = (
                cursor.fetchone()[0]
            )

            #
            # If ticker information was
            # supplied, also maintain the
            # proper securities mapping.
            #
            if ticker:
                cursor.execute(
                    """
                    INSERT INTO securities (
                        company_id,
                        ticker,
                        exchange,
                        source
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s
                    )

                    ON CONFLICT (
                        company_id,
                        ticker
                    )
                    DO UPDATE SET
                        exchange =
                            EXCLUDED.exchange,

                        updated_at =
                            CURRENT_TIMESTAMP;
                    """,
                    (
                        company_id,
                        ticker.upper(),
                        exchange,
                        "application",
                    ),
                )

    return company_id


def get_company_by_cik(cik):
    cik = normalize_cik(cik)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cik,
                    company_name

                FROM companies

                WHERE cik = %s

                LIMIT 1;
                """,
                (cik,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "cik": row[1],
        "company_name": row[2],
    }


def get_company_by_ticker(ticker):
    ticker = ticker.upper()

    #
    # Primary path:
    # ticker/security -> SEC issuer.
    #
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    c.id,
                    c.cik,
                    s.ticker,
                    c.company_name,
                    s.exchange

                FROM securities s

                JOIN companies c
                    ON c.id =
                       s.company_id

                WHERE UPPER(s.ticker) =
                      UPPER(%s)

                ORDER BY
                    s.is_primary DESC,
                    s.id

                LIMIT 1;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

            if row is not None:
                return {
                    "id": row[0],
                    "cik": row[1],
                    "ticker": row[2],
                    "company_name": row[3],
                    "exchange": row[4],
                }

            #
            # Temporary legacy fallback.
            #
            cursor.execute(
                """
                SELECT
                    id,
                    cik,
                    ticker,
                    company_name,
                    exchange

                FROM companies

                WHERE UPPER(ticker) =
                      UPPER(%s)

                LIMIT 1;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "cik": row[1],
        "ticker": row[2],
        "company_name": row[3],
        "exchange": row[4],
    }