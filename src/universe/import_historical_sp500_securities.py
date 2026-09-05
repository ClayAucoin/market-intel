import requests

from src.database import get_connection
from src.sec.sec_client import SEC_HEADERS
from src.universe.historical_sp500_mappings import (
    HISTORICAL_SP500_TICKER_TO_CIK,
)


SOURCE_NAME = "S&P 500 historical constituent"

SEC_SUBMISSIONS_URL = (
    "https://data.sec.gov/submissions/"
    "CIK{cik}.json"
)


def fetch_company_name(cik):
    response = requests.get(
        SEC_SUBMISSIONS_URL.format(cik=cik),
        headers=SEC_HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    name = data.get("name")

    if not name:
        raise ValueError(
            f"No SEC company name for CIK {cik}"
        )

    return name


def get_or_create_company(
    cursor,
    cik,
    company_name,
):
    cursor.execute(
        """
        SELECT id
        FROM companies
        WHERE cik = %s
        LIMIT 1;
        """,
        (cik,),
    )

    row = cursor.fetchone()

    if row:
        return row[0], False

    cursor.execute(
        """
        INSERT INTO companies (
            cik,
            ticker,
            company_name,
            exchange
        )
        VALUES (
            %s,
            NULL,
            %s,
            NULL
        )
        RETURNING id;
        """,
        (
            cik,
            company_name,
        ),
    )

    return cursor.fetchone()[0], True


def import_historical_securities():
    company_inserted = 0
    company_existing = 0
    security_inserted = 0
    security_existing = 0

    with get_connection() as conn:
        with conn.cursor() as cursor:
            for ticker, cik in sorted(
                HISTORICAL_SP500_TICKER_TO_CIK.items()
            ):
                company_name = fetch_company_name(
                    cik
                )

                company_id, created = (
                    get_or_create_company(
                        cursor,
                        cik,
                        company_name,
                    )
                )

                if created:
                    company_inserted += 1
                else:
                    company_existing += 1

                cursor.execute(
                    """
                    SELECT id
                    FROM securities
                    WHERE company_id = %s
                      AND ticker = %s
                    LIMIT 1;
                    """,
                    (
                        company_id,
                        ticker,
                    ),
                )

                existing = cursor.fetchone()

                if existing:
                    security_existing += 1

                    print(
                        f"{ticker:6} "
                        f"| existing "
                        f"| CIK {cik} "
                        f"| {company_name}"
                    )

                    continue

                cursor.execute(
                    """
                    INSERT INTO securities (
                        company_id,
                        ticker,
                        exchange,
                        source
                    )
                    VALUES (
                        %s,
                        %s,
                        NULL,
                        %s
                    );
                    """,
                    (
                        company_id,
                        ticker,
                        SOURCE_NAME,
                    ),
                )

                security_inserted += 1

                print(
                    f"{ticker:6} "
                    f"| inserted "
                    f"| CIK {cik} "
                    f"| {company_name}"
                )

    print()
    print("=" * 80)
    print(
        "Companies inserted:",
        company_inserted,
    )
    print(
        "Companies already existed:",
        company_existing,
    )
    print(
        "Securities inserted:",
        security_inserted,
    )
    print(
        "Securities already existed:",
        security_existing,
    )
    print(
        "Total mappings:",
        len(
            HISTORICAL_SP500_TICKER_TO_CIK
        ),
    )


if __name__ == "__main__":
    import_historical_securities()
