"""One atomic operational summary per invocation, without payloads or raw exceptions."""
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
import time
from uuid import uuid4

from src.sec.json_cache import atomic_json

REPORT_DIR = Path(__file__).resolve().parents[2] / "logs" / "sec-production"
_active = ContextVar("sec_report", default=None)
COUNTERS = ("http_requests", "successful_requests", "retries", "responses_429", "responses_5xx",
            "network_failures", "changed_payloads", "unchanged_payloads", "historical_shards_reused",
            "historical_shards_downloaded", "targeted_recovery_attempts", "targeted_recovery_resolved",
            "current_required_unresolved", "non_current_fact_linked_gaps")


def add(key, count=1):
    report = _active.get()
    if report is not None:
        report.data["counters"][key] += count


def result(key, value):
    report = _active.get()
    if report is not None:
        report.data[key] = value


def resource(kind, cik, status):
    report = _active.get()
    if report is not None:
        report.resources[kind][status].add(str(cik).zfill(10))


def unresolved(cik, accessions):
    report = _active.get()
    if report is not None:
        report.pending[str(cik).zfill(10)] = set(accessions)


def cutover(timestamp):
    report = _active.get()
    if report is not None:
        value = timestamp.isoformat() if timestamp is not None else None
        observed = report.data["cutover"]["observed_timestamps"]
        if value not in observed:
            observed.append(value)
        report.data["cutover"].update(
            state="CHANGED" if len(observed) > 1 else ("DISABLED" if value is None else "ENABLED"),
            timestamp=observed[0] if len(observed) == 1 else None)


def filing_coverage(cik, counts, non_current_gaps):
    report = _active.get()
    if report is not None:
        report.coverage[str(cik).zfill(10)] = dict(counts)
        report.coverage_gaps[str(cik).zfill(10)] = sorted(non_current_gaps)


def failure(resource_name, error, cik=None, ticker=None):
    report = _active.get()
    if report is not None:
        # Raw network/DB exceptions may contain credentials or response bodies.
        report.data["failures"].append(dict(resource=resource_name, cik=cik, ticker=ticker,
                                            error=type(error).__name__))


class RunReport:
    def __init__(self, universe, mode="production-refresh", directory=None):
        self.started = time.monotonic()
        self.pending = {}
        self.coverage = {}
        self.coverage_gaps = {}
        self.resources = {kind: {state: set() for state in ("attempted", "succeeded", "failed")}
                          for kind in ("company_facts", "submissions")}
        self.data = dict(report_version=2, run_id=uuid4().hex, start_timestamp=self.timestamp(),
                         end_timestamp=None, duration_seconds=None, mode=mode, universe=universe,
                         status="RUNNING", freshness="FAIL", counters=dict.fromkeys(COUNTERS, 0),
                         failures=[], financial_import={}, filing_import={},
                         cutover=dict(state="UNKNOWN", timestamp=None, observed_timestamps=[]))
        self.path = Path(directory or REPORT_DIR) / f"{self.data['run_id']}.json"

    @staticmethod
    def timestamp():
        return datetime.now(timezone.utc).isoformat()

    def write(self):
        totals = {key: sum(c[key] for c in self.coverage.values())
                  for key in ("targeted", "available", "reused", "persisted", "unresolved")}
        totals["issuers_complete"] = sum(c["complete"] for c in self.coverage.values())
        totals["issuers_attempted"] = len(self.coverage)
        totals["status"] = ("NOT_EVALUATED" if not self.coverage else
                            "INCOMPLETE" if totals["issuers_complete"] != len(self.coverage) else
                            "GAPS" if totals["unresolved"] else "COMPLETE")
        self.data["filing_coverage"] = totals
        self.data["non_current_fact_linked_gaps"] = [
            {"cik": cik, "accession": accession}
            for cik, accessions in sorted(self.coverage_gaps.items()) for accession in accessions]
        self.data["counters"]["non_current_fact_linked_gaps"] = len(self.data["non_current_fact_linked_gaps"])
        self.data["current_required_unresolved_accessions"] = [
            {"cik": cik, "accession": accession}
            for cik, accessions in sorted(self.pending.items()) for accession in sorted(accessions)]
        for kind, states in self.resources.items():
            self.data[kind] = {state: len(ciks) for state, ciks in states.items()}
        atomic_json(self.path, self.data)

    def __enter__(self):
        self.write()  # Failure here prevents any live work.
        self.token = _active.set(self)
        print(f"SEC production report: {self.path}")
        return self

    def __exit__(self, kind, error, traceback):
        try:
            if error is not None:
                failure("runner", error)
            incomplete = bool(self.data["failures"] or any(self.pending.values())
                              or self.data["counters"]["current_required_unresolved"]
                              or any(not c["complete"] for c in self.coverage.values()))
            failed = kind is not None or incomplete
            self.data.update(end_timestamp=self.timestamp(), duration_seconds=round(time.monotonic()-self.started, 3),
                             status="FAIL" if failed else "PASS",
                             freshness="PASS" if not failed and self.data["mode"] == "production-refresh" else "FAIL")
            self.data["counters"]["current_required_unresolved"] += sum(map(len, self.pending.values()))
            self.write()  # A failed final write leaves RUNNING on disk and propagates.
            counts = self.data["counters"]
            coverage = self.data["filing_coverage"]
            print(f"SEC {self.data['status']} | facts {self.data['company_facts']['succeeded']}/"
                  f"{self.data['company_facts']['attempted']} | submissions "
                  f"{self.data['submissions']['succeeded']}/{self.data['submissions']['attempted']} | "
                  f"HTTP {counts['http_requests']} retries {counts['retries']} | "
                  f"required-unresolved {counts['current_required_unresolved']} | freshness {self.data['freshness']} | "
                  f"cutover {self.data['cutover']['state']} | fact-coverage {coverage['status']} "
                  f"persisted {coverage['persisted']} gaps {counts['non_current_fact_linked_gaps']} | report {self.path}")
            if incomplete and kind is None:
                raise RuntimeError("SEC report records incomplete production processing")
        finally:
            _active.reset(self.token)


def run_reported(universe, operation, mode="production-refresh"):
    if _active.get() is not None:
        return operation()
    with RunReport(universe, mode):
        return operation()
