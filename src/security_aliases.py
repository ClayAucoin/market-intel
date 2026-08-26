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


def set_alias(
    ticker,
    source,
    symbol,
):
    security_id = get_security_id(
        ticker
    )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO security_aliases (
                    security_id,
                    source,
                    symbol
                )

                VALUES (
                    %s,
                    %s,
                    %s
                )

                ON CONFLICT (
                    security_id,
                    source
                )

                DO UPDATE SET
                    symbol =
                        EXCLUDED.symbol,

                    updated_at =
                        CURRENT_TIMESTAMP;
                """,
                (
                    security_id,
                    source.lower(),
                    symbol,
                ),
            )


def get_alias(
    ticker,
    source,
):
    security_id = get_security_id(
        ticker
    )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT symbol

                FROM security_aliases

                WHERE security_id = %s
                  AND LOWER(source) =
                      LOWER(%s)

                LIMIT 1;
                """,
                (
                    security_id,
                    source,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_symbol(
    ticker,
    source,
):
    alias = get_alias(
        ticker,
        source,
    )

    if alias is not None:
        return alias

    return ticker.upper()


def get_ticker_from_symbol(
    source,
    symbol,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT s.ticker

                FROM security_aliases sa

                JOIN securities s
                    ON s.id =
                       sa.security_id

                WHERE LOWER(sa.source) =
                      LOWER(%s)

                  AND UPPER(sa.symbol) =
                      UPPER(%s)

                LIMIT 1;
                """,
                (
                    source,
                    symbol,
                ),
            )

            row = cursor.fetchone()

    if row is not None:
        return row[0]

    #
    # Fallback for normal symbols
    # where no alias is needed.
    #
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT ticker

                FROM securities

                WHERE UPPER(ticker) =
                      UPPER(%s)

                ORDER BY
                    is_primary DESC,
                    id

                LIMIT 1;
                """,
                (
                    symbol,
                ),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]