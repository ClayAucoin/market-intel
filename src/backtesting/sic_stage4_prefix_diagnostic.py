"""One pinned, bounded submission-prefix diagnostic; no research promotion."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import os
import re

from bs4 import BeautifulSoup
from src.backtesting import sic_stage4 as stage
from src.backtesting import sic_stage4_diagnostic as index

EXPECTED_LEDGER = 'fa013e6ab012ffbd7f057f063babc993b6d7b327e5276b6a4e5201f4a683dc6d'
INDEX_MANIFEST = '84be968a5fb4d3492bba87666dccbc337cb98189b84c0a2ac80f52596339cb30'
LIMIT = 262144
DIRECTORY = 'prefix_diagnostics'


def request():
    relative = f'/Archives/edgar/data/{int(index.CIK)}/{index.ACCESSION.replace("-", "")}/{index.ACCESSION}.txt'
    return dict(kind='submission_prefix_diagnostic', cik=index.CIK, accession=index.ACCESSION,
                url='https://www.sec.gov'+relative, saved_href=relative, envelope='contingency',
                reason='Inspect bounded submission prefix for complete SEC header; diagnostic only')


def implementation_pins():
    paths = [Path(__file__), Path(index.__file__), Path(stage.__file__)]
    return {str(p.resolve().relative_to(Path.cwd())): stage.sha(p.read_bytes()) for p in paths}


def budget(rows):
    stage.require(len(rows)<stage.CAP, 'Stage ceiling reached')
    stage.require(Counter(r['charged_envelope'] for r in rows)['contingency']<stage.ENVELOPES['contingency'],
                  'Contingency ceiling reached')
    stage.require(not any(r['url']==request()['url'] for r in rows), 'Prefix request already reserved')


def state(root, review_path, review_pin):
    inputs=stage.load_inputs(root)
    rows=stage.ledger(root)
    stage.require(stage.digest(rows)==EXPECTED_LEDGER and len(rows)==7, 'Expected reviewed seven-attempt ledger')
    stage.require([r['outcome'] for r in rows]==['SUCCESS']*5+['HTTP_FAILURE','SUCCESS']
                  and rows[5].get('status')==404 and rows[6].get('status')==200
                  and rows[6]['charged_envelope']=='contingency', 'Unexpected prior outcomes')
    manifest_path=root/'diagnostics/extension_01.json'
    stage.require(stage.sha(manifest_path.read_bytes())==INDEX_MANIFEST, 'Original index manifest changed')
    prior=stage.read(manifest_path)
    for path,pin in prior['implementation_pins'].items():
        stage.require(stage.sha(Path(path).read_bytes())==pin, 'Original diagnostic implementation changed')
    response=stage.read(root/'diagnostics/000007/response.json')
    attempt=root/'attempts/000007.json'
    stage.require(response==rows[6]['diagnostic_evidence'] and response['reservation_sha256']==stage.sha(attempt.read_bytes())
                  and response['manifest_sha256']==INDEX_MANIFEST and response['url']==index.request()['url']
                  and not response['truncated'] and not response['incomplete_read'], 'Index result inconsistent or incomplete')
    body_path=root/response['body']
    stage.require(body_path.resolve().is_relative_to(root.resolve()), 'Index body escapes package')
    raw=body_path.read_bytes()
    stage.require(stage.sha(raw)==response['raw_sha256'] and len(raw)==response['raw_bytes'], 'Index body changed')
    links=BeautifulSoup(raw,'html.parser').find_all('a',href=True)
    stage.require(any(a['href']==request()['saved_href'] for a in links), 'Exact target not linked in saved index')
    review,ref=stage.review_file(root,review_path,review_pin)
    stage.require(review['acknowledged_contradictions']==index.BLOCKED and len(review['acknowledged_clock_conflicts'])==27
                  and all(not review.get(k) for k in ('issuer_reviews','relationships','clock_reviews','identity_requests','eight_k_intervals')),
                  'Blockers or empty approvals changed')
    continuation=dict(ledger_sha256=stage.digest(rows),acknowledged_attempts=[6])
    stage.stop_review(rows,dict(review,continuation=continuation))
    entries=stage.all_evidence(root)
    catalogs,_,checks=stage.inventories(root,inputs,entries)
    stage.require_acknowledgements(root,inputs,entries,catalogs,checks,review)
    stage.require(not checks[index.CIK]['contradictions'] and any(r['accessionNumber']==index.ACCESSION
                  for r in catalogs[index.CIK]['rows']), 'Saved catalogue target missing or blocked')
    budget(rows)
    dependencies={str(p.relative_to(root)):stage.sha(p.read_bytes()) for p in root.rglob('*')
                  if p.is_file() and (p.suffix in ('.json','.gz','.bin') or p.name=='inputs.sha256')
                  and DIRECTORY not in p.relative_to(root).parts}
    return dict(inputs_sha256=stage.sha((root/'inputs.json').read_bytes()),ledger_sha256=stage.digest(rows),
                evidence_sha256=stage.digest(entries),dependencies=dependencies,review=ref,continuation=continuation,
                request=request(),implementation_pins=implementation_pins(),cap=stage.CAP,envelopes=stage.ENVELOPES,
                range_header=f'bytes=0-{LIMIT-1}',body_limit=LIMIT,timeout=[10,30],redirects=False,
                automatic_retries=False,diagnostic_only=True)


def prepare(root, review_path, review_pin):
    root=stage.safe_root(root)
    with stage.locked(root):
        directory=root/DIRECTORY
        stage.require(not directory.is_symlink(), 'Prefix directory cannot be a symlink')
        stage.require(not list(directory.glob('extension_*.json')), 'Prefix extension already prepared')
        manifest=state(root,review_path,review_pin)
        manifest.update(version=1,scope='Exactly one submission-prefix diagnostic; no header retry or research acceptance')
        path=directory/'extension_01.json'
        stage.frozen(path,manifest)
        return dict(status='PREFIX_DIAGNOSTIC_PREPARED_OFFLINE',path=str(path),sha256=stage.sha(path.read_bytes()))


def transport():
    import requests
    from src.sec.sec_client import SEC_HEADERS
    from src.sec.sec_http import _pace
    raw=bytearray()
    result=dict(status=None,outcome='NETWORK_FAILURE',truncated=False,incomplete_read=False,
                response_complete=False,requested_prefix_complete=False,submission_complete=False,
                range_ignored=False,response_headers={})
    try:
        _pace()
        headers=dict(SEC_HEADERS,Range=f'bytes=0-{LIMIT-1}')
        headers['Accept-Encoding']='identity'
        with requests.get(request()['url'],headers=headers,timeout=(10,30),stream=True,allow_redirects=False) as response:
            result['status']=response.status_code
            result['range_ignored']=response.status_code==200
            result['response_headers']={k:response.headers[k] for k in
                ('Content-Range','Content-Length','Accept-Ranges','Content-Encoding') if k in response.headers}
            # Preserve actual response-body bytes even if Content-Encoding
            # violates the requested identity encoding.
            for chunk in response.raw.stream(8192, decode_content=False):
                remaining=LIMIT-len(raw)
                raw.extend(chunk[:remaining])
                if len(chunk)>remaining:
                    result.update(outcome='SIZE_FAILURE',truncated=True)
                    break
            else:
                result['response_complete']=True
                result['outcome']='SUCCESS' if response.status_code in (200,206) else 'HTTP_FAILURE'
    except Exception as exc:
        if result['outcome']!='SIZE_FAILURE': result['outcome']='NETWORK_FAILURE'
        result['incomplete_read']=result['status'] is not None
        result['error_type']=type(exc).__name__
    encoding=result['response_headers'].get('Content-Encoding','identity').lower()
    length=result['response_headers'].get('Content-Length')
    if result['response_complete'] and encoding=='identity' and length and length.isdigit() and int(length)!=len(raw):
        result.update(response_complete=False,incomplete_read=True,outcome='NETWORK_FAILURE')
    if result['status']==206:
        match=re.fullmatch(r'bytes 0-(\d+)/(\d+|\*)',result['response_headers'].get('Content-Range',''))
        valid=bool(match and int(match[1])+1==len(raw) and int(match[1])<LIMIT
                   and (match[2]=='*' or int(match[2])>int(match[1])) and encoding=='identity')
        result['range_valid']=valid
        if valid and result['response_complete'] and not result['incomplete_read']:
            total=None if match[2]=='*' else int(match[2])
            result['submission_complete']=total==len(raw)
            result['requested_prefix_complete']=len(raw)==LIMIT or result['submission_complete']
        elif result['outcome']=='SUCCESS': result['outcome']='PROCESSING_FAILURE'
    elif result['status']==200 and encoding=='identity' and not result['incomplete_read']:
        result['submission_complete']=result['response_complete']
        result['requested_prefix_complete']=len(raw)==LIMIT or result['response_complete']
    return result,bytes(raw)


def fetch(root,manifest_path,manifest_pin):
    root=stage.safe_root(root);manifest_path=Path(manifest_path)
    with stage.locked(root):
        directory=root/DIRECTORY
        stage.require(not directory.is_symlink() and manifest_path.resolve().parent==directory.resolve()
                      and re.fullmatch(r'extension_\d{2,}\.json',manifest_path.name), 'Invalid prefix manifest path')
        stage.require(manifest_pin and stage.sha(manifest_path.read_bytes())==manifest_pin, 'Prefix manifest hash mismatch')
        manifest=stage.read(manifest_path)
        stage.require(manifest['implementation_pins']==implementation_pins(), 'Prefix implementation changed')
        receipt=directory/f'{manifest_path.stem}_reservation.json'
        stage.require(not receipt.exists(), 'Prefix extension already reserved')
        current=state(root,manifest['review']['path'],manifest['review']['sha256'])
        stage.require(all(manifest[k]==v for k,v in current.items()), 'Prefix state changed')
        rows=stage.ledger(root);n=len(rows)+1
        reservation=dict(attempt=n,item=request(),url=request()['url'],plan=manifest_path.name,
                         charged_envelope='contingency',outcome='IN_FLIGHT',reserved_at=datetime.now(timezone.utc).isoformat())
        stage.frozen(receipt,dict(manifest_sha256=manifest_pin,attempt=n))
        attempt_path=root/'attempts'/f'{n:06d}.json'
        stage.frozen(attempt_path,reservation)
        stage.atomic_json(root/'requests.json',rows+[reservation])
        result,raw=transport()
        destination=directory/f'{n:06d}';destination.mkdir();stage.sync_directory(directory)
        body=destination/'body.bin'
        with body.open('xb') as handle:
            handle.write(raw);handle.flush();os.fsync(handle.fileno())
        stage.sync_directory(destination)
        evidence=dict(result,url=request()['url'],raw_sha256=stage.sha(raw),raw_bytes=len(raw),
                      body=str(body.relative_to(root)),reservation_sha256=stage.sha(attempt_path.read_bytes()),
                      manifest_sha256=manifest_pin,provenance=dict(basis='submission_prefix_diagnostic_only',reserved_at=reservation['reserved_at']))
        stage.frozen(destination/'response.json',evidence)
        ledger_result=dict(result,diagnostic_evidence=evidence)
        if ledger_result['status'] is None:del ledger_result['status']
        stage.finish(root,reservation,ledger_result)
        return dict(status='PREFIX_DIAGNOSTIC_SAVED',attempt=n,outcome=result['outcome'],http_status=result['status'])


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package-dir',type=Path,default=stage.DEFAULT_ROOT)
    modes=parser.add_mutually_exclusive_group();modes.add_argument('--prepare',action='store_true');modes.add_argument('--fetch',action='store_true')
    parser.add_argument('--review',type=Path);parser.add_argument('--review-sha256')
    parser.add_argument('--extension-manifest',type=Path);parser.add_argument('--extension-sha256')
    args=parser.parse_args(argv)
    if args.prepare:
        stage.require(args.review is not None and args.review_sha256, 'Pinned existing review required')
        result=prepare(args.package_dir,args.review,args.review_sha256)
    elif args.fetch:
        stage.require(args.extension_manifest is not None and args.extension_sha256, 'Pinned prefix manifest required')
        result=fetch(args.package_dir,args.extension_manifest,args.extension_sha256)
    else:parser.print_help();return
    import json
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
