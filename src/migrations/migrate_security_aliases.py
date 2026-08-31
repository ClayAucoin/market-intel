from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    security_aliases (
                        id BIGSERIAL PRIMARY KEY,

                        security_id BIGINT NOT NULL
                            REFERENCES securities(id)
                            ON DELETE CASCADE,

                        source VARCHAR(50) NOT NULL,

                        symbol VARCHAR(50) NOT NULL,

                        created_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        updated_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        CONSTRAINT
                            security_aliases_security_source_unique
                            UNIQUE (
                                security_id,
                                source
                            )
                    );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_aliases_symbol
                ON security_aliases (
                    source,
                    symbol
                );
                """
            )

    print(
        "security aliases migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()