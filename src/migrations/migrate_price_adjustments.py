from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE daily_prices
                ADD COLUMN IF NOT EXISTS adjusted_open NUMERIC;
                """
            )

    print(
        "Price adjustment migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()