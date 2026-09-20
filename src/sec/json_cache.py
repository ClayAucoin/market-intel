"""Atomic JSON replacement shared by SEC caches and operational reports."""
from datetime import date, datetime
import json
import os
from pathlib import Path
import tempfile


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp",
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_company_facts(data, cik):
    if (not isinstance(data, dict) or str(data.get("cik", "")).zfill(10) != str(cik).zfill(10)
            or not isinstance(data.get("facts"), dict)):
        raise ValueError("Invalid Company Facts envelope or CIK")
    for taxonomy in data["facts"].values():
        if not isinstance(taxonomy, dict):
            raise ValueError("Invalid Company Facts taxonomy")
        for concept in taxonomy.values():
            if not isinstance(concept, dict) or not isinstance(concept.get("units"), dict):
                raise ValueError("Invalid Company Facts concept")
            for values in concept["units"].values():
                if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
                    raise ValueError("Invalid Company Facts unit values")


def validate_columns(data):
    if not isinstance(data, dict) or not isinstance(data.get("accessionNumber"), list):
        raise ValueError("Invalid submissions columns")
    size = len(data["accessionNumber"])
    for name in ("filingDate", "acceptanceDateTime"):
        if not isinstance(data.get(name), list) or len(data[name]) != size:
            raise ValueError("Invalid submissions date columns")
        for value in data[name]:
            if value is None or value == "":
                continue  # Missing metadata is evaluated separately for current sources.
            if not isinstance(value, str):
                raise ValueError("Invalid submissions date value")
            if name == "filingDate":
                date.fromisoformat(value)
            else:
                datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    if any(not isinstance(a, str) or not a for a in data["accessionNumber"]):
        raise ValueError("Invalid submissions accession")
    if any(isinstance(v, list) and len(v) != size for v in data.values()):
        raise ValueError("Unequal submissions column lengths")


def validate_submissions(data, cik):
    if (not isinstance(data, dict) or str(data.get("cik", "")).zfill(10) != str(cik).zfill(10)
            or not isinstance(data.get("filings"), dict)):
        raise ValueError("Invalid submissions envelope or CIK")
    validate_columns(data["filings"].get("recent"))
    shards = data["filings"].get("files", [])
    if not isinstance(shards, list) or any(not isinstance(s, dict) or not s.get("name")
                                         or Path(s["name"]).name != s["name"] for s in shards):
        raise ValueError("Invalid submissions history index")
    for shard in shards:
        for key in ("filingFrom", "filingTo"):
            if shard.get(key):
                if not isinstance(shard[key], str):
                    raise ValueError("Invalid submissions history date")
                date.fromisoformat(shard[key])
