from src.database import get_connection


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            #
            # Add security_id.
            #
            cursor.execute(
                """
                ALTER TABLE financial_facts
                ADD COLUMN IF NOT EXISTS
                    security_id BIGINT;
                """
            )

            #
            # Add the foreign key only if it
            # does not already exist.
            #
            cursor.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname =
                            'financial_facts_security_id_fkey'
                    ) THEN

                        ALTER TABLE financial_facts
                        ADD CONSTRAINT
                            financial_facts_security_id_fkey

                        FOREIGN KEY (
                            security_id
                        )

                        REFERENCES securities(id)
                        ON DELETE CASCADE;

                    END IF;
                END
                $$;
                """
            )

            #
            # Backfill existing Dell financial
            # facts using the company's ticker
            # through the new securities table.
            #
            cursor.execute(
                """
                UPDATE financial_facts ff

                SET security_id = s.id

                FROM securities s

                WHERE ff.security_id IS NULL
                  AND s.company_id =
                      ff.company_id

                  AND UPPER(s.ticker) = (
                      SELECT UPPER(c.ticker)
                      FROM companies c
                      WHERE c.id =
                          ff.company_id
                  );
                """
            )

            #
            # Dell's old companies.ticker value
            # should resolve, but use a second
            # fallback for any remaining rows
            # where the issuer currently has
            # only one security.
            #
            cursor.execute(
                """
                UPDATE financial_facts ff

                SET security_id = lookup.security_id

                FROM (
                    SELECT
                        company_id,
                        MIN(id) AS security_id

                    FROM securities

                    GROUP BY company_id

                    HAVING COUNT(*) = 1
                ) lookup

                WHERE ff.security_id IS NULL
                  AND lookup.company_id =
                      ff.company_id;
                """
            )

            #
            # Verify that every existing row
            # was successfully mapped before
            # making the column NOT NULL.
            #
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM financial_facts
                WHERE security_id IS NULL;
                """
            )

            missing = cursor.fetchone()[0]

            if missing > 0:
                raise ValueError(
                    f"{missing} financial_facts rows "
                    "could not be mapped to a security."
                )

            cursor.execute(
                """
                ALTER TABLE financial_facts
                ALTER COLUMN security_id
                SET NOT NULL;
                """
            )

            #
            # Remove old uniqueness constraint.
            #
            cursor.execute(
                """
                ALTER TABLE financial_facts
                DROP CONSTRAINT IF EXISTS
                    financial_facts_company_id_metric_period_end_key;
                """
            )

            #
            # Add the new lineage-aware
            # uniqueness constraint.
            #
            cursor.execute(
                """
                ALTER TABLE financial_facts
                ADD CONSTRAINT
                    financial_facts_security_company_metric_period_end_key

                UNIQUE (
                    security_id,
                    company_id,
                    metric,
                    period_end
                );
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_financial_facts_security_id

                ON financial_facts (
                    security_id
                );
                """
            )

    print(
        "financial_facts security migration "
        "completed successfully."
    )


if __name__ == "__main__":
    migrate()