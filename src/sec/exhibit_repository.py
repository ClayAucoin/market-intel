from src.database import get_connection


def save_exhibits(filing_id, exhibits):
    rows = []

    for exhibit in exhibits:
        rows.append(
            (
                filing_id,
                exhibit["sequence"],
                exhibit["document_type"],
                exhibit["document_name"],
                exhibit["description"],
                exhibit["document_url"],
            )
        )

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO filing_exhibits (
                    filing_id,
                    sequence,
                    exhibit_type,
                    document_name,
                    description,
                    document_url
                )
                VALUES (%s, %s, %s, %s, %s, %s)

                ON CONFLICT (filing_id, document_name)
                DO UPDATE SET
                    sequence = EXCLUDED.sequence,
                    exhibit_type = EXCLUDED.exhibit_type,
                    description = EXCLUDED.description,
                    document_url = EXCLUDED.document_url;
                """,
                rows,
            )

    print(f"Saved {len(rows):,} filing documents.")