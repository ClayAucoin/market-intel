from src.database import get_connection
from src.migrations.migrate_prospective_paper_trading import MIGRATION_SQL


CREATE_ACCOUNT_TABLE = """
CREATE TABLE IF NOT EXISTS paper_accounts (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    starting_cash NUMERIC NOT NULL,
    cash NUMERIC NOT NULL,
    trade_size NUMERIC NOT NULL,
    ticker_cap_percent NUMERIC NOT NULL,
    minimum_priority INTEGER NOT NULL,
    holding_days INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


CREATE_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS paper_signals (
    id BIGSERIAL PRIMARY KEY,

    account_id BIGINT NOT NULL
        REFERENCES paper_accounts(id)
        ON DELETE CASCADE,

    security_id BIGINT NOT NULL
        REFERENCES securities(id)
        ON DELETE CASCADE,

    backtest_event_id BIGINT
        REFERENCES backtest_events(id)
        ON DELETE SET NULL,

    ticker TEXT NOT NULL,
    sector TEXT,

    signal_date DATE NOT NULL,
    period_end DATE,

    score INTEGER NOT NULL,
    classification TEXT,

    sector_confidence TEXT,

    recommendation TEXT NOT NULL,
    priority INTEGER NOT NULL,
    recommendation_reason TEXT,

    revenue_yoy NUMERIC,
    revenue_acceleration NUMERIC,
    eps_yoy NUMERIC,
    operating_margin_change NUMERIC,
    pre_excess_20d NUMERIC,

    action TEXT NOT NULL,

    action_reason TEXT,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        account_id,
        security_id,
        signal_date
    )
);
"""


MIGRATE_SIGNALS_TABLE = """
ALTER TABLE paper_signals
ADD COLUMN IF NOT EXISTS
    operating_margin_change NUMERIC;

ALTER TABLE paper_signals
ADD COLUMN IF NOT EXISTS
    pre_excess_20d NUMERIC;
"""


CREATE_POSITIONS_TABLE = """
CREATE TABLE IF NOT EXISTS paper_positions (
    id BIGSERIAL PRIMARY KEY,

    account_id BIGINT NOT NULL
        REFERENCES paper_accounts(id)
        ON DELETE CASCADE,

    signal_id BIGINT NOT NULL
        REFERENCES paper_signals(id)
        ON DELETE RESTRICT,

    security_id BIGINT NOT NULL
        REFERENCES securities(id)
        ON DELETE CASCADE,

    ticker TEXT NOT NULL,

    status TEXT NOT NULL
        DEFAULT 'OPEN',

    entry_date DATE NOT NULL,
    entry_price NUMERIC NOT NULL,

    shares NUMERIC NOT NULL,
    invested_amount NUMERIC NOT NULL,

    planned_exit_date DATE NOT NULL,

    exit_date DATE,
    exit_price NUMERIC,

    exit_value NUMERIC,
    profit NUMERIC,
    return_percent NUMERIC,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
"""


CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS
    idx_paper_signals_account_date
ON paper_signals (
    account_id,
    signal_date
);

CREATE INDEX IF NOT EXISTS
    idx_paper_positions_account_status
ON paper_positions (
    account_id,
    status
);

CREATE INDEX IF NOT EXISTS
    idx_paper_positions_ticker
ON paper_positions (
    ticker
);
"""


CREATE_DEFAULT_ACCOUNT = """
INSERT INTO paper_accounts (
    name,
    starting_cash,
    cash,
    trade_size,
    ticker_cap_percent,
    minimum_priority,
    holding_days
)
VALUES (
    'Primary Paper Account',
    10000,
    10000,
    1000,
    20,
    3,
    45
)
ON CONFLICT (name)
DO NOTHING;
"""


def main():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                CREATE_ACCOUNT_TABLE
            )

            cur.execute(
                CREATE_SIGNALS_TABLE
            )

            cur.execute(
                MIGRATE_SIGNALS_TABLE
            )

            cur.execute(
                CREATE_POSITIONS_TABLE
            )

            cur.execute(
                CREATE_INDEXES
            )

            cur.execute(MIGRATION_SQL)

            cur.execute(
                CREATE_DEFAULT_ACCOUNT
            )

        conn.commit()

    print()
    print(
        "PAPER TRADING TABLES READY"
    )

    print("=" * 60)

    print(
        "paper_accounts"
    )

    print(
        "paper_signals"
    )

    print(
        "paper_positions"
    )

    print()

    print(
        "Default account:"
    )

    print(
        "  Starting cash:       $10,000"
    )

    print(
        "  Trade size:          $1,000"
    )

    print(
        "  Minimum priority:    3"
    )

    print(
        "  Holding period:      45 days"
    )

    print(
        "  Per-ticker cap:      20%"
    )


if __name__ == "__main__":
    main()
