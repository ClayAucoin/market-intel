from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE backtest_events
                    ADD COLUMN IF NOT EXISTS
                        exit_date_30d DATE,

                    ADD COLUMN IF NOT EXISTS
                        exit_date_90d DATE,

                    ADD COLUMN IF NOT EXISTS
                        exit_date_180d DATE;
                """
            )

    print(
        "backtest_events exit dates "
        "migration completed successfully."
    )


if __name__ == "__main__":
    migrate()