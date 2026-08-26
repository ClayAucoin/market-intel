from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_universes (
                    id BIGSERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_universe_members (
                    id BIGSERIAL PRIMARY KEY,
                    universe_id BIGINT NOT NULL
                        REFERENCES analysis_universes(id)
                        ON DELETE CASCADE,
                    security_id BIGINT NOT NULL
                        REFERENCES securities(id)
                        ON DELETE CASCADE,
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

                    CONSTRAINT analysis_universe_members_unique
                        UNIQUE (universe_id, security_id)
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_analysis_universe_members_universe_id
                ON analysis_universe_members(universe_id);
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_analysis_universe_members_security_id
                ON analysis_universe_members(security_id);
                """
            )

        conn.commit()

    print(
        "analysis universe migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()