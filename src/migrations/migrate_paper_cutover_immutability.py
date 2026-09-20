"""Freeze an activated paper cutover; never assign or change account values."""

from src.database import get_connection


MIGRATION_SQL = """
CREATE OR REPLACE FUNCTION preserve_paper_cutover()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.prospective_cutover_at IS NOT NULL AND
       NEW.prospective_cutover_at IS DISTINCT FROM OLD.prospective_cutover_at THEN
        RAISE EXCEPTION 'An activated paper cutover is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS preserve_paper_cutover ON paper_accounts;
CREATE TRIGGER preserve_paper_cutover BEFORE UPDATE ON paper_accounts
    FOR EACH ROW EXECUTE FUNCTION preserve_paper_cutover();
"""


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
    print("Paper cutover protection ready; existing cutovers unchanged.")


if __name__ == "__main__":
    migrate()
