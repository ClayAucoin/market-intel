from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS index_membership_history (
                    id BIGSERIAL PRIMARY KEY,

                    index_name VARCHAR(100) NOT NULL,

                    security_id BIGINT NOT NULL
                        REFERENCES securities(id)
                        ON DELETE CASCADE,

                    effective_from DATE,
                    effective_to DATE,

                    source VARCHAR(100),
                    notes TEXT,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        index_name,
                        security_id,
                        effective_from
                    )
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_index_membership_history_index
                ON index_membership_history (
                    index_name
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_index_membership_history_security
                ON index_membership_history (
                    security_id
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_index_membership_history_dates
                ON index_membership_history (
                    effective_from,
                    effective_to
                );
                """
            )

    print(
        "Index membership history migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()