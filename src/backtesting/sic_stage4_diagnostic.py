"""One separately pinned index diagnostic; never promotes diagnostic evidence."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from src.backtesting import sic_stage4 as stage

CIK = '0000826083'
ACCESSION = '0000826083-12-000006'
LIMIT = 262144
EXPECTED_LEDGER = 'd5a833f52a11dd755b857901d7907512b43d376cfd3f94b9874cf47d576ea63c'
BLOCKED = ['0001175454', '0001572709', '0001754308']


def implementation_pins():
    paths = [Path(__file__), Path('src/backtesting/sic_stage4.py')]
    return {str(p.resolve().relative_to(Path.cwd())): stage.sha(p.read_bytes()) for p in paths}


def request():
    return dict(kind='index_diagnostic', cik=CIK, accession=ACCESSION,
                url=f'https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{ACCESSION.replace("-", "")}/{ACCESSION}-index.html',
                envelope='contingency', reason='Inspect ordinary index resource links after header HTTP 404')


def budget(rows):
    stage.require(len(rows) < stage.CAP, 'Stage attempt ceiling reached')
    stage.require(Counter(r['charged_envelope'] for r in rows)['contingency'] < stage.ENVELOPES['contingency'],
                  'Contingency ceiling reached')
    stage.require(not any(r['url'] == request()['url'] for r in rows), 'Diagnostic already reserved')


def state(root, review_path, review_pin):
    inputs = stage.load_inputs(root)  # Original byte/code checks remain authoritative.
    rows = stage.ledger(root)
    stage.require(stage.digest(rows) == EXPECTED_LEDGER, 'Diagnostic requires the reviewed six-attempt ledger')
    stage.require(len(rows) == 6 and all(r['outcome'] == 'SUCCESS' for r in rows[:5])
                  and rows[5]['outcome'] == 'HTTP_FAILURE' and rows[5].get('status') == 404
                  and rows[5]['item']['cik'] == CIK and rows[5]['item']['accession'] == ACCESSION
                  and rows[5]['item']['kind'] == 'header'
                  and rows[5]['url'] == stage.url(dict(kind='header', cik=CIK, accession=ACCESSION)),
                  'Unexpected prior attempt state')
    review, ref = stage.review_file(root, review_path, review_pin)
    stage.require(all(not review.get(k) for k in ('issuer_reviews', 'relationships', 'clock_reviews',
                                                'identity_requests', 'eight_k_intervals')), 'Approvals must remain empty')
    stage.require(review['acknowledged_contradictions'] == BLOCKED
                  and len(review['acknowledged_clock_conflicts']) == 27, 'Required acknowledgements changed')
    # Explicit continuation is in the extension, not an edited original review.
    continuation = dict(ledger_sha256=stage.digest(rows), acknowledged_attempts=[6])
    stage.stop_review(rows, dict(review, continuation=continuation))
    entries = stage.all_evidence(root)
    catalogs, _, checks = stage.inventories(root, inputs, entries)
    stage.require_acknowledgements(root, inputs, entries, catalogs, checks, review)
    stage.require(not checks[CIK]['contradictions'] and any(r['accessionNumber'] == ACCESSION
                  for r in catalogs[CIK]['rows']), 'Target absent or contradicted in saved catalogue')
    budget(rows)
    dependencies = {str(p.relative_to(root)): stage.sha(p.read_bytes()) for p in root.rglob('*')
                    if p.is_file() and (p.suffix in ('.json', '.gz') or p.name == 'inputs.sha256')
                    and 'diagnostics' not in p.relative_to(root).parts}
    return dict(inputs_sha256=stage.sha((root/'inputs.json').read_bytes()), ledger_sha256=stage.digest(rows),
                evidence_sha256=stage.digest(entries), dependencies=dependencies, review=ref,
                continuation=continuation, request=request(), cap=stage.CAP, envelopes=stage.ENVELOPES,
                body_limit=LIMIT, timeout=[10, 30], redirects=False, automatic_retries=False,
                identity_acceptance=False, implementation_pins=implementation_pins())


def prepare(root, review_path, review_pin):
    root = stage.safe_root(root)
    with stage.locked(root):
        stage.require(not (root/'diagnostics').is_symlink(), 'Diagnostic directory cannot be a symlink')
        data = state(root, review_path, review_pin)
        directory = root/'diagnostics'
        stage.require(not list(directory.glob('extension_*.json')), 'One diagnostic extension already prepared')
        data.update(version=1, reviewed_by='Codex implementation; offline preparation executed by operator',
                    scope='One index diagnostic only; attempt 6 acknowledged, no header retry authorized')
        path = directory/'extension_01.json'
        stage.frozen(path, data)
        return dict(status='DIAGNOSTIC_PREPARED_OFFLINE', path=str(path), sha256=stage.sha(path.read_bytes()))


def transport():
    """Exactly one streamed request; retain bounded bytes for every status."""
    import requests
    from src.sec.sec_client import SEC_HEADERS
    from src.sec.sec_http import _pace
    raw = bytearray()
    result = dict(status=None, outcome='NETWORK_FAILURE', truncated=False, incomplete_read=False)
    try:
        _pace()
        with requests.get(request()['url'], headers=SEC_HEADERS, timeout=(10, 30),
                          stream=True, allow_redirects=False) as response:
            result['status'] = response.status_code
            for chunk in response.iter_content(8192):
                remaining = LIMIT - len(raw)
                raw.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    result.update(outcome='SIZE_FAILURE', truncated=True)
                    break
            else:
                result['outcome'] = 'SUCCESS' if response.status_code == 200 else 'HTTP_FAILURE'
    except Exception as exc:
        # Never persist credential-bearing exception text.
        if result['outcome'] != 'SIZE_FAILURE':
            result['outcome'] = 'NETWORK_FAILURE'
        result['incomplete_read'] = result['status'] is not None
        result['error_type'] = type(exc).__name__
    return result, bytes(raw)


def fetch(root, manifest_path, manifest_pin):
    root = stage.safe_root(root)
    manifest_path = Path(manifest_path)
    with stage.locked(root):
        stage.require(not (root/'diagnostics').is_symlink(), 'Diagnostic directory cannot be a symlink')
        stage.require(manifest_path.resolve().parent == (root/'diagnostics').resolve()
                      and re.fullmatch(r'extension_\d{2,}\.json', manifest_path.name), 'Invalid extension path')
        stage.require(manifest_pin and stage.sha(manifest_path.read_bytes()) == manifest_pin, 'Extension hash mismatch')
        manifest = stage.read(manifest_path)
        stage.require(manifest['implementation_pins'] == implementation_pins(), 'Extension implementation changed')
        receipt = root/'diagnostics'/f'{manifest_path.stem}_reservation.json'
        stage.require(not receipt.exists(), 'Diagnostic extension already reserved')
        current = state(root, manifest['review']['path'], manifest['review']['sha256'])
        stage.require(all(manifest[k] == v for k, v in current.items()), 'Extension state or configuration changed')
        rows = stage.ledger(root)
        n = len(rows)+1
        reservation = dict(attempt=n, item=request(), url=request()['url'], plan=manifest_path.name,
                           charged_envelope='contingency', outcome='IN_FLIGHT',
                           reserved_at=datetime.now(timezone.utc).isoformat())
        # Reserve once even if interruption occurs before transport or snapshot update.
        stage.frozen(receipt, dict(manifest_sha256=manifest_pin, attempt=n))
        attempt_path = root/'attempts'/f'{n:06d}.json'
        stage.frozen(attempt_path, reservation)
        stage.atomic_json(root/'requests.json', rows+[reservation])
        result, raw = transport()
        destination = root/'diagnostics'/f'{n:06d}'
        destination.mkdir()
        stage.sync_directory(destination.parent)
        body = destination/'body.bin'
        with body.open('xb') as handle:
            handle.write(raw)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        stage.sync_directory(destination)
        evidence = dict(url=request()['url'], status=result['status'], raw_sha256=stage.sha(raw),
                        raw_bytes=len(raw), body=str(body.relative_to(root)),
                        reservation_sha256=stage.sha(attempt_path.read_bytes()), manifest_sha256=manifest_pin,
                        provenance=dict(basis='index_diagnostic_only', reserved_at=reservation['reserved_at']),
                        truncated=result['truncated'], incomplete_read=result['incomplete_read'])
        if 'error_type' in result:
            evidence['error_type'] = result['error_type']
        stage.frozen(destination/'response.json', evidence)
        # No ordinary `evidence` key or responses/ entry: original readers ignore this body.
        ledger_result = dict(result, diagnostic_evidence=evidence)
        # Original stop_review treats an absent HTTP status as zero; None would
        # break its numeric redirect check. Diagnostics still retain null status.
        if ledger_result['status'] is None:
            del ledger_result['status']
        stage.finish(root, reservation, ledger_result)
        return dict(status='DIAGNOSTIC_SAVED', attempt=n, outcome=result['outcome'], http_status=result['status'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir', type=Path, default=stage.DEFAULT_ROOT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare', action='store_true')
    modes.add_argument('--fetch', action='store_true')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--review-sha256')
    parser.add_argument('--extension-manifest', type=Path)
    parser.add_argument('--extension-sha256')
    args = parser.parse_args(argv)
    if args.prepare:
        stage.require(args.review is not None and args.review_sha256, 'Preparation requires pinned existing review')
        result = prepare(args.package_dir, args.review, args.review_sha256)
    elif args.fetch:
        stage.require(args.extension_manifest is not None and args.extension_sha256, 'Fetch requires pinned extension')
        result = fetch(args.package_dir, args.extension_manifest, args.extension_sha256)
    else:
        parser.print_help()
        return
    import json
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
