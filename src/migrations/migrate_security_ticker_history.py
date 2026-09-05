from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    security_ticker_history (
                        id BIGSERIAL PRIMARY KEY,

                        security_id BIGINT NOT NULL
                            REFERENCES securities(id)
                            ON DELETE CASCADE,

                        ticker VARCHAR(50) NOT NULL,

                        effective_from DATE,
                        effective_to DATE,

                        source VARCHAR(100),
                        notes TEXT,

                        created_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        updated_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        UNIQUE (
                            security_id,
                            ticker,
                            effective_from
                        )
                    );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_ticker_history_ticker
                ON security_ticker_history (
                    ticker
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_ticker_history_security
                ON security_ticker_history (
                    security_id
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_ticker_history_dates
                ON security_ticker_history (
                    effective_from,
                    effective_to
                );
                """
            )

    print(
        "Security ticker history migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()