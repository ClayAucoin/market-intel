from src.database import get_connection


def create_universe(
    name,
    description=None,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO analysis_universes (
                    name,
                    description
                )
                VALUES (
                    %s,
                    %s
                )

                ON CONFLICT (name)
                DO UPDATE SET
                    description =
                        EXCLUDED.description,

                    updated_at =
                        CURRENT_TIMESTAMP

                RETURNING id;
                """,
                (
                    name,
                    description,
                ),
            )

            return cursor.fetchone()[0]


def get_universe_id(name):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id

                FROM analysis_universes

                WHERE name = %s

                LIMIT 1;
                """,
                (
                    name,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_security_id(ticker):
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
        return None

    return row[0]


def add_security_to_universe(
    universe_name,
    ticker,
    sector=None,
    industry=None,
):
    universe_id = get_universe_id(
        universe_name
    )

    if universe_id is None:
        raise ValueError(
            f"Universe not found: "
            f"{universe_name}"
        )

    security_id = get_security_id(
        ticker
    )

    if security_id is None:
        raise ValueError(
            f"Security not found: "
            f"{ticker}"
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO analysis_universe_members (
                    universe_id,
                    security_id,
                    sector,
                    industry
                )

                VALUES (
                    %s,
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (
                    universe_id,
                    security_id
                )

                DO UPDATE SET
                    sector =
                        EXCLUDED.sector,

                    industry =
                        EXCLUDED.industry;
                """,
                (
                    universe_id,
                    security_id,
                    sector,
                    industry,
                ),
            )


def get_universe(name):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.id,
                    s.ticker,
                    s.exchange,

                    c.id,
                    c.cik,
                    c.company_name,

                    aum.sector,
                    aum.industry

                FROM analysis_universes au

                JOIN analysis_universe_members aum
                    ON aum.universe_id =
                       au.id

                JOIN securities s
                    ON s.id =
                       aum.security_id

                JOIN companies c
                    ON c.id =
                       s.company_id

                WHERE au.name = %s

                ORDER BY s.ticker;
                """,
                (
                    name,
                ),
            )

            rows = cursor.fetchall()

    return [
        {
            "security_id": row[0],
            "ticker": row[1],
            "exchange": row[2],

            "company_id": row[3],
            "cik": row[4],
            "company_name": row[5],

            "name": row[5],

            "sector": row[6],
            "industry": row[7],
        }
        for row in rows
    ]


def get_tickers(name):
    return [
        company["ticker"]
        for company in get_universe(
            name
        )
    ]


def get_member(
    universe_name,
    ticker,
):
    ticker = ticker.upper()

    for company in get_universe(
        universe_name
    ):
        if (
            company["ticker"].upper()
            == ticker
        ):
            return company

    return None