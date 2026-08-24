from src.database import get_connection


def create_tables():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS companies (
                    id BIGSERIAL PRIMARY KEY,
                    cik VARCHAR(10) UNIQUE NOT NULL,
                    ticker VARCHAR(10),
                    company_name TEXT NOT NULL,
                    exchange VARCHAR(50),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS filings (
                    id BIGSERIAL PRIMARY KEY,

                    company_id BIGINT NOT NULL
                        REFERENCES companies(id)
                        ON DELETE CASCADE,

                    accession_number VARCHAR(30)
                        UNIQUE NOT NULL,

                    form VARCHAR(20) NOT NULL,
                    filing_date DATE NOT NULL,
                    report_date DATE,
                    acceptance_datetime TIMESTAMPTZ,

                    primary_document TEXT,
                    primary_doc_description TEXT,
                    filing_url TEXT,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            cursor.execute(
                """
                ALTER TABLE filings
                ADD COLUMN IF NOT EXISTS filing_url TEXT;
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS filing_exhibits (
                    id BIGSERIAL PRIMARY KEY,

                    filing_id BIGINT NOT NULL
                        REFERENCES filings(id)
                        ON DELETE CASCADE,

                    sequence INTEGER,
                    exhibit_type VARCHAR(50),
                    document_name TEXT NOT NULL,
                    description TEXT,
                    document_url TEXT,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        filing_id,
                        document_name
                    )
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS document_analysis (
                    id BIGSERIAL PRIMARY KEY,

                    exhibit_id BIGINT NOT NULL
                        REFERENCES filing_exhibits(id)
                        ON DELETE CASCADE,

                    event_type VARCHAR(50),
                    sentiment VARCHAR(20),
                    materiality VARCHAR(20),

                    summary TEXT,
                    facts JSONB,
                    risks JSONB,
                    investment_implications JSONB,

                    analyzer VARCHAR(100),
                    analyzer_version VARCHAR(50),

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        exhibit_id,
                        analyzer,
                        analyzer_version
                    )
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS financial_facts (
                    id BIGSERIAL PRIMARY KEY,

                    company_id BIGINT NOT NULL
                        REFERENCES companies(id)
                        ON DELETE CASCADE,

                    metric VARCHAR(100) NOT NULL,
                    concept VARCHAR(200) NOT NULL,
                    unit VARCHAR(50) NOT NULL,

                    fiscal_year INTEGER,
                    fiscal_period VARCHAR(10),

                    period_start DATE,
                    period_end DATE NOT NULL,

                    value NUMERIC NOT NULL,

                    filed_date DATE,
                    accession_number VARCHAR(30),

                    is_derived BOOLEAN
                        NOT NULL DEFAULT FALSE,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        company_id,
                        metric,
                        period_end
                    )
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_prices (
                    id BIGSERIAL PRIMARY KEY,

                    symbol VARCHAR(20) NOT NULL,
                    trade_date DATE NOT NULL,

                    open NUMERIC,
                    high NUMERIC,
                    low NUMERIC,
                    close NUMERIC,
                    adjusted_close NUMERIC,

                    volume BIGINT,

                    dividend_cash NUMERIC,
                    split_factor NUMERIC,

                    created_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    updated_at TIMESTAMPTZ
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (
                        symbol,
                        trade_date
                    )
                );
                """
            )

    print("Database tables created successfully.")


if __name__ == "__main__":
    create_tables()