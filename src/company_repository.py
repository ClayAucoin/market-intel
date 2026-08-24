from src.database import get_connection

def save_company(company):
    cik = str(company["cik"]).zfill(10)

    ticker = company["tickers"][0] if company["tickers"] else None
    exchange = company["exchanges"][0] if company["exchanges"] else None

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO companies (
                    cik,
                    ticker,
                    company_name,
                    exchange
                )
                VALUES (%s, %s, %s, %s)

                ON CONFLICT (cik)
                DO UPDATE SET
                    ticker = EXCLUDED.ticker,
                    company_name = EXCLUDED.company_name,
                    exchange = EXCLUDED.exchange,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (
                    cik,
                    ticker,
                    company["name"],
                    exchange,
                ),
            )

    print(f"Saved {ticker} - {company['name']}")


def save_companies(companies):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO companies (
                    cik,
                    ticker,
                    company_name,
                    exchange
                )
                VALUES (%s, %s, %s, %s)

                ON CONFLICT (cik)
                DO UPDATE SET
                    ticker = EXCLUDED.ticker,
                    company_name = EXCLUDED.company_name,
                    exchange = EXCLUDED.exchange,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                companies,
            )

    print(f"Saved {len(companies):,} companies.")


def get_company_by_ticker(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, cik, ticker, company_name, exchange
                FROM companies
                WHERE UPPER(ticker) = UPPER(%s)
                LIMIT 1;
                """,
                (ticker,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row[0],
        "cik": row[1],
        "ticker": row[2],
        "company_name": row[3],
        "exchange": row[4],
    }