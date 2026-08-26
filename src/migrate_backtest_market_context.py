from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE backtest_events
                    ADD COLUMN IF NOT EXISTS
                        pre_return_20d NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        pre_return_60d NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        pre_excess_20d NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        pre_excess_60d NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        pre_volatility_20d NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        previous_close NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        entry_open NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        opening_gap_pct NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        spy_opening_gap_pct NUMERIC,

                    ADD COLUMN IF NOT EXISTS
                        opening_gap_excess NUMERIC;
                """
            )

    print(
        "backtest_events market context "
        "migration completed successfully."
    )


if __name__ == "__main__":
    migrate()