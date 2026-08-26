from src.company_universe import get_companies
from src.database import get_connection
from src.xbrl_client import get_company_facts


SEARCH_TERMS = {
    "revenue": [
        "revenue",
        "sales",
    ],
    "operating_income": [
        "operatingincome",
        "incomeoperations",
    ],
    "gross_profit": [
        "grossprofit",
        "grossmargin",
    ],
}


def search_local_companies(
    ticker,
    company_name,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cik,
                    ticker,
                    company_name,
                    exchange

                FROM companies

                WHERE UPPER(ticker) = UPPER(%s)
                   OR company_name ILIKE %s

                ORDER BY
                    company_name,
                    ticker;
                """,
                (
                    ticker,
                    f"%{company_name}%",
                ),
            )

            return cursor.fetchall()


def get_company_by_exact_ticker(ticker):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    cik,
                    ticker,
                    company_name,
                    exchange

                FROM companies

                WHERE UPPER(ticker) = UPPER(%s)

                LIMIT 1;
                """,
                (ticker,),
            )

            return cursor.fetchone()


def find_matching_concepts(
    facts,
    search_terms,
):
    us_gaap = (
        facts
        .get("facts", {})
        .get("us-gaap", {})
    )

    matches = []

    for concept_name, concept_data in us_gaap.items():
        normalized = concept_name.lower()

        if any(
            term.lower() in normalized
            for term in search_terms
        ):
            unit_counts = {}

            for unit, values in (
                concept_data
                .get("units", {})
                .items()
            ):
                unit_counts[unit] = len(values)

            matches.append(
                {
                    "concept": concept_name,
                    "label": concept_data.get(
                        "label"
                    ),
                    "units": unit_counts,
                }
            )

    return sorted(
        matches,
        key=lambda item:
            item["concept"],
    )


def print_company_lookup(
    ticker,
    name,
):
    print()
    print(
        f"{ticker} LOCAL COMPANY LOOKUP"
    )
    print("-" * 90)

    rows = search_local_companies(
        ticker,
        name,
    )

    if not rows:
        print(
            "No matching local company rows."
        )
        return

    for row in rows:
        print(
            "ID:",
            row[0],
            "| CIK:",
            row[1],
            "| Ticker:",
            row[2],
            "| Company:",
            row[3],
            "| Exchange:",
            row[4],
        )


def print_concept_diagnostics(
    ticker,
):
    company = get_company_by_exact_ticker(
        ticker
    )

    if company is None:
        print()
        print(
            f"{ticker}: exact ticker "
            "not available locally."
        )
        return

    cik = company[1]

    facts = get_company_facts(
        cik
    )

    print()
    print(
        f"{ticker} XBRL CONCEPT DIAGNOSTICS"
    )
    print("=" * 90)

    for category, terms in (
        SEARCH_TERMS.items()
    ):
        print()
        print(
            category.upper()
        )
        print("-" * 90)

        matches = find_matching_concepts(
            facts,
            terms,
        )

        if not matches:
            print(
                "No matching concepts."
            )
            continue

        for match in matches:
            print(
                match["concept"],
                "|",
                match["label"],
                "|",
                match["units"],
            )


def main():
    companies = get_companies()

    print()
    print(
        "LOCAL COMPANY MAPPING CHECK"
    )
    print("=" * 90)

    for company in companies:
        print_company_lookup(
            company["ticker"],
            company["name"],
        )

    print()
    print()
    print(
        "FAILED / QUESTIONABLE "
        "XBRL CONCEPT CHECKS"
    )
    print("=" * 90)

    for ticker in [
        "UNH",
        "WMT",
        "CAT",
        "XOM",
    ]:
        print_concept_diagnostics(
            ticker
        )


if __name__ == "__main__":
    main()