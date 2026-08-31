from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS security_issuer_history (
                    id BIGSERIAL PRIMARY KEY,

                    security_id BIGINT NOT NULL
                        REFERENCES securities(id)
                        ON DELETE CASCADE,

                    company_id BIGINT NOT NULL
                        REFERENCES companies(id)
                        ON DELETE CASCADE,

                    effective_from DATE,
                    effective_to DATE,

                    is_current BOOLEAN
                        NOT NULL DEFAULT FALSE,

                    source VARCHAR(100),
                    notes TEXT,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        security_id,
                        company_id
                    )
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_issuer_history_security
                ON security_issuer_history (
                    security_id
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_security_issuer_history_company
                ON security_issuer_history (
                    company_id
                );
                """
            )

    print(
        "Security issuer history migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()