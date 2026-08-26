from src.database import get_connection


SOURCE_CURRENT = "SEC current ticker mapping"
SOURCE_LINEAGE = "SEC corporate succession"


def seed_current_issuers(cursor):
    cursor.execute(
        """
        INSERT INTO security_issuer_history (
            security_id,
            company_id,
            is_current,
            source
        )

        SELECT
            s.id,
            s.company_id,
            TRUE,
            %s

        FROM securities s

        ON CONFLICT (
            security_id,
            company_id
        )
        DO UPDATE SET
            is_current = TRUE,
            source = EXCLUDED.source,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (
            SOURCE_CURRENT,
        ),
    )


def get_security_id(
    cursor,
    ticker,
):
    cursor.execute(
        """
        SELECT id

        FROM securities

        WHERE UPPER(ticker) =
              UPPER(%s)

        ORDER BY id

        LIMIT 1;
        """,
        (
            ticker,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        raise ValueError(
            f"Security not found: {ticker}"
        )

    return row[0]


def get_or_create_company(
    cursor,
    cik,
    company_name,
):
    cik = str(cik).zfill(10)

    cursor.execute(
        """
        SELECT id

        FROM companies

        WHERE cik = %s

        LIMIT 1;
        """,
        (
            cik,
        ),
    )

    row = cursor.fetchone()

    if row is not None:
        return row[0]

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

    return cursor.fetchone()[0]


def add_xom_lineage(cursor):
    security_id = get_security_id(
        cursor,
        "XOM",
    )

    predecessor_id = get_or_create_company(
        cursor,
        "0000034088",
        "EXXON MOBIL CORP",
    )

    successor_id = get_or_create_company(
        cursor,
        "0002115436",
        "ExxonMobil Holdings Corp",
    )

    #
    # Predecessor issuer.
    #
    cursor.execute(
        """
        INSERT INTO security_issuer_history (
            security_id,
            company_id,
            effective_to,
            is_current,
            source,
            notes
        )
        VALUES (
            %s,
            %s,
            DATE '2026-06-30',
            FALSE,
            %s,
            %s
        )

        ON CONFLICT (
            security_id,
            company_id
        )
        DO UPDATE SET
            effective_to =
                EXCLUDED.effective_to,

            is_current = FALSE,

            source =
                EXCLUDED.source,

            notes =
                EXCLUDED.notes,

            updated_at =
                CURRENT_TIMESTAMP;
        """,
        (
            security_id,
            predecessor_id,
            SOURCE_LINEAGE,
            (
                "Exxon Mobil Corporation "
                "predecessor issuer for XOM."
            ),
        ),
    )

    #
    # Successor issuer.
    #
    cursor.execute(
        """
        INSERT INTO security_issuer_history (
            security_id,
            company_id,
            effective_from,
            is_current,
            source,
            notes
        )
        VALUES (
            %s,
            %s,
            DATE '2026-07-01',
            TRUE,
            %s,
            %s
        )

        ON CONFLICT (
            security_id,
            company_id
        )
        DO UPDATE SET
            effective_from =
                EXCLUDED.effective_from,

            effective_to = NULL,

            is_current = TRUE,

            source =
                EXCLUDED.source,

            notes =
                EXCLUDED.notes,

            updated_at =
                CURRENT_TIMESTAMP;
        """,
        (
            security_id,
            successor_id,
            SOURCE_LINEAGE,
            (
                "Successor public parent "
                "effective July 1, 2026."
            ),
        ),
    )


def import_lineage():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            seed_current_issuers(
                cursor
            )

            add_xom_lineage(
                cursor
            )

    print(
        "Issuer lineage imported "
        "successfully."
    )


if __name__ == "__main__":
    import_lineage()