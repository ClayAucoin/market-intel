from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE analysis_universe_members
                ADD COLUMN IF NOT EXISTS
                    sector VARCHAR(100);
                """
            )

            cursor.execute(
                """
                ALTER TABLE analysis_universe_members
                ADD COLUMN IF NOT EXISTS
                    industry VARCHAR(150);
                """
            )

    print(
        "analysis universe metadata migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()