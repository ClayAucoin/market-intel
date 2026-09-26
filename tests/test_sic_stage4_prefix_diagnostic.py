"""Submission prefix tests: temporary fixtures; network and database blocked."""
import io
import fcntl
from pathlib import Path
import unittest
from unittest.mock import patch,MagicMock

from tests import test_sic_stage4_diagnostic as fixture
from src.backtesting import sic_stage4 as stage
from src.backtesting import sic_stage4_diagnostic as index
from src.backtesting import sic_stage4_prefix_diagnostic as prefix


class PrefixTests(unittest.TestCase):
    def setUp(self):
        # Reuse fixture construction only, not the preceding extension's tests.
        fixture.DiagnosticTests.setUp(self)
        prepared=index.prepare(self.root,self.review,stage.sha(self.review.read_bytes()))
        raw=f'<a href="{prefix.request()["saved_href"]}">Complete submission text file</a>'.encode()
        with patch.object(index,'transport',return_value=(dict(status=200,outcome='SUCCESS',truncated=False,incomplete_read=False),raw)):
            index.fetch(self.root,Path(prepared['path']),prepared['sha256'])
        for name,value in [('EXPECTED_LEDGER',stage.digest(stage.ledger(self.root))),('INDEX_MANIFEST',prepared['sha256'])]:
            override=patch.object(prefix,name,value);override.start();self.addCleanup(override.stop)
        self.before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def prepare(self):
        result=prefix.prepare(self.root,self.review,stage.sha(self.review.read_bytes()))
        return Path(result['path']),result['sha256']

    def run_fetch(self,status,body,headers=None):
        manifest,pin=self.prepare();response=MagicMock();response.status_code=status;response.headers=headers or {}
        response.__enter__.return_value=response
        response.raw.stream.return_value=iter(body)
        with patch('requests.get',return_value=response) as get,patch('src.sec.sec_http._pace') as pace:
            result=prefix.fetch(self.root,manifest,pin)
        get.assert_called_once();pace.assert_called_once()
        self.assertEqual(get.call_args.kwargs['headers']['Range'],'bytes=0-262143')
        self.assertEqual(get.call_args.kwargs['headers']['Accept-Encoding'],'identity')
        self.assertEqual(get.call_args.kwargs['timeout'],(10,30));self.assertFalse(get.call_args.kwargs['allow_redirects'])
        response.raw.stream.assert_called_once_with(8192,decode_content=False)
        metadata=stage.read(self.root/'prefix_diagnostics/000008/response.json')
        self.assertEqual(metadata['raw_sha256'],stage.sha((self.root/metadata['body']).read_bytes()))
        return result,metadata,manifest,pin

    def test_206_prefix_and_shared_accounting(self):
        before=stage.all_evidence(self.root)
        result,m,manifest,pin=self.run_fetch(206,[b'x'*prefix.LIMIT],{'Content-Range':'bytes 0-262143/24438849','Content-Length':'262144','Accept-Ranges':'bytes'})
        self.assertEqual(result['outcome'],'SUCCESS');self.assertTrue(m['requested_prefix_complete'])
        self.assertFalse(m['submission_complete']);self.assertFalse(m['truncated']);self.assertTrue(m['response_complete'])
        rows=stage.ledger(self.root);self.assertEqual(len(rows),8)
        self.assertEqual(sum(r['charged_envelope']=='contingency' for r in rows),2)
        self.assertEqual(stage.all_evidence(self.root),before);stage.load_inputs(self.root)
        for p,raw in self.before.items():
            if p.name!='requests.json':self.assertEqual(p.read_bytes(),raw)
        with self.assertRaises(stage.GuardFailure):prefix.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),8)

    def test_range_ignored_200_is_bounded(self):
        result,m,_,_=self.run_fetch(200,[b'x'*(prefix.LIMIT+100)],{'Content-Length':'24438849'})
        self.assertEqual(result['outcome'],'SIZE_FAILURE');self.assertTrue(m['range_ignored'])
        self.assertTrue(m['truncated']);self.assertTrue(m['requested_prefix_complete']);self.assertFalse(m['submission_complete'])
        self.assertEqual(m['raw_bytes'],prefix.LIMIT)

    def test_small_complete_submission(self):
        result,m,_,_=self.run_fetch(206,[b'abc'],{'Content-Range':'bytes 0-2/3','Content-Length':'3'})
        self.assertTrue(m['requested_prefix_complete']);self.assertTrue(m['submission_complete'])
        self.assertEqual(result['outcome'],'SUCCESS')

    def test_short_206_not_complete_requested_prefix(self):
        _,m,_,_=self.run_fetch(206,[b'abc'],{'Content-Range':'bytes 0-2/24438849'})
        self.assertFalse(m['requested_prefix_complete']);self.assertFalse(m['submission_complete'])

    def test_invalid_range_is_processing_failure(self):
        result,m,_,_=self.run_fetch(206,[b'abc'],{'Content-Range':'bytes 10-12/100'})
        self.assertEqual(result['outcome'],'PROCESSING_FAILURE');self.assertFalse(m['range_valid'])

    def test_unexpected_encoding_not_promoted(self):
        result,m,_,_=self.run_fetch(206,[b'encoded'],{'Content-Range':'bytes 0-6/7','Content-Encoding':'gzip'})
        self.assertEqual((self.root/m['body']).read_bytes(),b'encoded')
        self.assertEqual(result['outcome'],'PROCESSING_FAILURE')
        self.assertFalse(m['requested_prefix_complete']);self.assertFalse(m['submission_complete'])

    def test_non200_preserved(self):
        result,m,_,_=self.run_fetch(404,[b'not found'],{'Content-Length':'9'})
        self.assertEqual(result['outcome'],'HTTP_FAILURE');self.assertEqual(m['status'],404)
        self.assertFalse(m['requested_prefix_complete']);self.assertFalse(m['submission_complete'])
        self.assertEqual((self.root/m['body']).read_bytes(),b'not found')

    def test_redirect_no_followup(self):
        result,m,_,_=self.run_fetch(302,[b'redirect'])
        self.assertEqual(result['outcome'],'HTTP_FAILURE');self.assertEqual(m['status'],302)

    def test_non200_oversize(self):
        result,m,_,_=self.run_fetch(500,[b'x'*(prefix.LIMIT+1)])
        self.assertEqual(result['outcome'],'SIZE_FAILURE');self.assertTrue(m['truncated'])
        self.assertFalse(m['requested_prefix_complete'])

    def test_interrupted_body_keeps_prefix(self):
        def chunks():
            yield b'prefix'
            raise OSError('secret failure detail')
        result,m,_,_=self.run_fetch(206,chunks(),{'Content-Range':'bytes 0-262143/24438849'})
        self.assertEqual(result['outcome'],'NETWORK_FAILURE');self.assertTrue(m['incomplete_read'])
        self.assertFalse(m['requested_prefix_complete']);self.assertEqual((self.root/m['body']).read_bytes(),b'prefix')
        self.assertNotIn('secret',str(m))

    def test_length_mismatch(self):
        result,m,_,_=self.run_fetch(200,[b'abc'],{'Content-Length':'100'})
        self.assertEqual(result['outcome'],'NETWORK_FAILURE');self.assertTrue(m['incomplete_read'])
        self.assertFalse(m['submission_complete'])

    def test_transport_failure(self):
        manifest,pin=self.prepare()
        with patch('requests.get',side_effect=OSError('fixture')),patch('src.sec.sec_http._pace'):
            result=prefix.fetch(self.root,manifest,pin)
        self.assertIsNone(result['http_status']);self.assertEqual(result['outcome'],'NETWORK_FAILURE')
        rows=stage.ledger(self.root)
        stage.stop_review(rows,dict(continuation=dict(ledger_sha256=stage.digest(rows),acknowledged_attempts=[6,8])))

    def test_reservation_before_transport_and_crash(self):
        manifest,pin=self.prepare()
        def crash():
            self.assertEqual(stage.ledger(self.root)[-1]['outcome'],'IN_FLIGHT')
            raise KeyboardInterrupt()
        with patch.object(prefix,'transport',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):prefix.fetch(self.root,manifest,pin)
        with self.assertRaises(stage.GuardFailure):prefix.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),8)

    def test_hash_and_implementation_rejection(self):
        manifest,pin=self.prepare()
        with self.assertRaises(stage.GuardFailure):prefix.fetch(self.root,manifest,'0'*64)
        with patch.object(prefix,'implementation_pins',return_value={}):
            with self.assertRaises(stage.GuardFailure):prefix.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),7)

    def test_prepared_package_dependency_change_rejected(self):
        manifest,pin=self.prepare()
        path=self.root/'diagnostics/extension_01_reservation.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(stage.GuardFailure):prefix.fetch(self.root,manifest,pin)
        self.assertEqual(len(stage.ledger(self.root)),7)

    def test_index_link_and_body_pin_enforced(self):
        (self.root/'diagnostics/000007/body.bin').write_bytes(b'changed')
        with self.assertRaises(stage.GuardFailure):self.prepare()

    def test_index_target_link_required(self):
        body=self.root/'diagnostics/000007/body.bin';body.write_bytes(b'<a href="other.txt">other</a>')
        data=stage.read(self.root/'diagnostics/000007/response.json');data.update(raw_sha256=stage.sha(body.read_bytes()),raw_bytes=body.stat().st_size)
        (self.root/'diagnostics/000007/response.json').write_bytes(stage.encoded(data))
        outcome=stage.read(self.root/'outcomes/000007.json');outcome['result']['diagnostic_evidence']=data
        (self.root/'outcomes/000007.json').write_bytes(stage.encoded(outcome))
        rows=stage.read(self.root/'requests.json');rows[6]['diagnostic_evidence']=data;stage.atomic_json(self.root/'requests.json',rows)
        with patch.object(prefix,'EXPECTED_LEDGER',stage.digest(rows)):
            with self.assertRaises(stage.GuardFailure):self.prepare()

    def test_lock_budget_and_default(self):
        with (self.root/'.lock').open('a') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(stage.GuardFailure):self.prepare()
        with self.assertRaises(stage.GuardFailure):prefix.budget([dict(url='other',charged_envelope='contingency')]*30)
        with self.assertRaises(stage.GuardFailure):prefix.budget([dict(url='other',charged_envelope='periodic')]*240)
        with patch('sys.stdout',new=io.StringIO()),patch.object(prefix,'prepare') as prepare,patch.object(prefix,'fetch') as fetch:
            prefix.main([])
        prepare.assert_not_called();fetch.assert_not_called()


if __name__=='__main__':unittest.main()
