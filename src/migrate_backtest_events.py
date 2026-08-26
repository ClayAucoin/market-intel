from src.database import get_connection


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS backtest_events (
    id BIGSERIAL PRIMARY KEY,

    security_id BIGINT NOT NULL
        REFERENCES securities(id)
        ON DELETE CASCADE,

    period_end DATE NOT NULL,
    entry_date DATE NOT NULL,
    entry_price NUMERIC NOT NULL,

    revenue_yoy NUMERIC,
    revenue_acceleration NUMERIC,
    eps_yoy NUMERIC,
    gross_margin_change NUMERIC,
    operating_margin_change NUMERIC,

    return_30d NUMERIC,
    spy_return_30d NUMERIC,
    excess_30d NUMERIC,

    return_90d NUMERIC,
    spy_return_90d NUMERIC,
    excess_90d NUMERIC,

    return_180d NUMERIC,
    spy_return_180d NUMERIC,
    excess_180d NUMERIC,

    created_at TIMESTAMPTZ
        DEFAULT CURRENT_TIMESTAMP,

    updated_at TIMESTAMPTZ
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT
        backtest_events_security_period_key

        UNIQUE (
            security_id,
            period_end
        )
);
"""


CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS
    idx_backtest_events_security_id
ON backtest_events (
    security_id
);

CREATE INDEX IF NOT EXISTS
    idx_backtest_events_period_end
ON backtest_events (
    period_end
);

CREATE INDEX IF NOT EXISTS
    idx_backtest_events_entry_date
ON backtest_events (
    entry_date
);
"""


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                CREATE_TABLE_SQL
            )

            cursor.execute(
                CREATE_INDEXES_SQL
            )

    print(
        "backtest_events migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()