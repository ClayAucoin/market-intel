from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id BIGSERIAL PRIMARY KEY,

                    portfolio_name VARCHAR(100) NOT NULL,

                    snapshot_month DATE NOT NULL,

                    valuation_date DATE,

                    cash NUMERIC(20, 2),

                    total_portfolio_value NUMERIC(20, 2),

                    total_cost_basis NUMERIC(20, 2),

                    source_filename VARCHAR(255),

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    CONSTRAINT portfolio_snapshots_unique
                        UNIQUE (
                            portfolio_name,
                            snapshot_month
                        )
                );
                """
            )

            cursor.execute(
                """
                ALTER TABLE portfolio_snapshots
                ADD COLUMN IF NOT EXISTS
                    valuation_date DATE;
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS
                    portfolio_snapshot_holdings (
                        id BIGSERIAL PRIMARY KEY,

                        snapshot_id BIGINT NOT NULL
                            REFERENCES portfolio_snapshots(id)
                            ON DELETE CASCADE,

                        security_id BIGINT NOT NULL
                            REFERENCES securities(id)
                            ON DELETE RESTRICT,

                        ticker VARCHAR(20) NOT NULL,

                        description TEXT,

                        price NUMERIC(20, 6),

                        shares NUMERIC(20, 8),

                        market_value NUMERIC(20, 2),

                        cost_basis NUMERIC(20, 2),

                        gain_loss NUMERIC(20, 2),

                        created_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        updated_at TIMESTAMPTZ
                            DEFAULT CURRENT_TIMESTAMP,

                        CONSTRAINT
                            portfolio_snapshot_holdings_unique
                            UNIQUE (
                                snapshot_id,
                                security_id
                            )
                    );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_portfolio_snapshots_month
                ON portfolio_snapshots(
                    snapshot_month
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_portfolio_snapshot_holdings_snapshot
                ON portfolio_snapshot_holdings(
                    snapshot_id
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_portfolio_snapshot_holdings_security
                ON portfolio_snapshot_holdings(
                    security_id
                );
                """
            )

        conn.commit()

    print(
        "portfolio snapshot migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()