"""Paper-only migration. Does not activate trading or rewrite legacy records."""

from src.database import get_connection


MIGRATION_SQL = """
ALTER TABLE paper_accounts
    ADD COLUMN IF NOT EXISTS prospective_cutover_at TIMESTAMPTZ;
ALTER TABLE paper_signals
    ADD COLUMN IF NOT EXISTS purchase_committed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS not_before_date DATE,
    ADD COLUMN IF NOT EXISTS committed_amount NUMERIC,
    ADD COLUMN IF NOT EXISTS source_accession TEXT,
    ADD COLUMN IF NOT EXISTS source_acceptance_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS execution_session_date DATE;

ALTER TABLE paper_signals ALTER COLUMN period_end SET NOT NULL;
ALTER TABLE paper_signals DROP CONSTRAINT IF EXISTS
    paper_signals_account_id_security_id_signal_date_key;
CREATE UNIQUE INDEX IF NOT EXISTS paper_signals_logical_event_key
    ON paper_signals (account_id, security_id, period_end);
CREATE UNIQUE INDEX IF NOT EXISTS paper_positions_signal_key
    ON paper_positions (signal_id);

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'paper_signals'::regclass
                     AND conname = 'paper_signals_commitment_check') THEN
        ALTER TABLE paper_signals ADD CONSTRAINT paper_signals_commitment_check
        CHECK (
            action IS NOT NULL AND (
                (action IN ('SKIP_CASH', 'SKIP_CAP')
                 AND purchase_committed_at IS NULL
                 AND not_before_date IS NULL
                 AND committed_amount IS NULL
                 AND source_accession IS NULL
                 AND source_acceptance_at IS NULL
                 AND execution_session_date IS NULL)
                OR
                (action IN ('PENDING_BUY', 'BUY')
                 AND purchase_committed_at IS NOT NULL
                 AND not_before_date IS NOT NULL
                 AND committed_amount IS NOT NULL AND committed_amount > 0
                 AND committed_amount < 'Infinity'::numeric
                 AND source_accession IS NOT NULL
                 AND source_accession ~ '[^[:space:]]'
                 AND source_acceptance_at IS NOT NULL
                 AND source_acceptance_at <= purchase_committed_at
                 AND not_before_date =
                     (purchase_committed_at AT TIME ZONE 'America/New_York')::date + 1
                 AND (execution_session_date IS NULL
                      OR execution_session_date >= not_before_date)
                 AND (action = 'PENDING_BUY' OR execution_session_date IS NOT NULL))
            )
        );
    END IF;
END $$;

CREATE OR REPLACE FUNCTION preserve_paper_commitment()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.action IS DISTINCT FROM OLD.action AND NOT
       (OLD.action = 'PENDING_BUY' AND NEW.action = 'BUY') THEN
        RAISE EXCEPTION 'Invalid paper signal action transition';
    END IF;
    IF ROW(NEW.account_id, NEW.security_id, NEW.period_end, NEW.signal_date, NEW.ticker)
       IS DISTINCT FROM
       ROW(OLD.account_id, OLD.security_id, OLD.period_end, OLD.signal_date, OLD.ticker)
    THEN
        RAISE EXCEPTION 'A paper signal logical identity is immutable';
    END IF;
    IF OLD.purchase_committed_at IS NOT NULL AND
       ROW(NEW.purchase_committed_at, NEW.not_before_date, NEW.committed_amount,
           NEW.source_accession, NEW.source_acceptance_at)
       IS DISTINCT FROM
       ROW(OLD.purchase_committed_at, OLD.not_before_date, OLD.committed_amount,
           OLD.source_accession, OLD.source_acceptance_at)
    THEN
        RAISE EXCEPTION 'A paper purchase commitment is immutable';
    END IF;
    IF NEW.execution_session_date IS DISTINCT FROM OLD.execution_session_date AND
       (OLD.execution_session_date IS NOT NULL OR OLD.action <> 'PENDING_BUY') THEN
        RAISE EXCEPTION 'A paper execution session is immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS preserve_paper_commitment ON paper_signals;
CREATE TRIGGER preserve_paper_commitment BEFORE UPDATE ON paper_signals
    FOR EACH ROW EXECUTE FUNCTION preserve_paper_commitment();
"""


def migrate():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(MIGRATION_SQL)
    print("Prospective paper schema ready; cutover remains unchanged/unset.")


if __name__ == "__main__":
    migrate()
