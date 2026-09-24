"""Offline SIC observation semantics and saved public evidence replay."""
from datetime import datetime, timedelta, timezone
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

with patch('dotenv.load_dotenv'):
    from src.backtesting import sic_validation_study as study


class SICValidationTests(unittest.TestCase):
    def obs(self, stamp, sic='1000', accession='a', cik='0000000001'):
        return dict(cik=cik,accepted_at=stamp,sic=sic,accession=accession)

    def test_inclusive_cutoff_and_no_backdate(self):
        old=self.obs('2020-01-01T12:00:00Z')
        new=self.obs('2020-04-03T20:00:00Z','2000','b')
        cutoff=study.instant(new['accepted_at'])
        self.assertEqual(study.lookup([old,new],old['cik'],cutoff-timedelta(microseconds=1))['sic'],'1000')
        self.assertEqual(study.lookup([old,new],old['cik'],cutoff)['sic'],'2000')
        self.assertEqual(study.lookup([old,new],old['cik'],cutoff+timedelta(days=3))['sic'],'2000')

    def test_no_prior_and_other_issuer_unknown(self):
        obs=self.obs('2020-01-01T12:00:00Z')
        for cik,cutoff in [('0000000002','2021-01-01T00:00:00Z'),(obs['cik'],'2019-12-31T00:00:00Z')]:
            self.assertEqual(study.lookup([obs],cik,study.instant(cutoff))['status'],'UNKNOWN')

    def test_same_sic_multiple_filings_and_long_gap_disclosure(self):
        obs=[self.obs('2020-01-01T12:00:00Z'),self.obs('2020-02-01T12:00:00Z',accession='b')]
        result=study.lookup(obs,obs[0]['cik'],study.instant('2025-01-01T00:00:00Z'))
        self.assertEqual(result['accessions'],['b'])
        self.assertGreater(result['age_days'],365)
        self.assertFalse(result['continuity_proven'])
        self.assertEqual(study.transitions(obs),[])

    def test_same_instant_conflict_different_timezones_ambiguous(self):
        obs=[self.obs('2020-01-01T12:00:00Z'),self.obs('2020-01-01T07:00:00-05:00','2000','b')]
        self.assertEqual(study.lookup(obs,obs[0]['cik'],study.instant('2020-01-02T00:00:00Z'))['status'],'AMBIGUOUS')
        self.assertEqual(study.transitions(obs),[])

    def test_transition_uses_last_old_and_first_new(self):
        obs=[self.obs('2020-01-01T12:00:00Z'),self.obs('2020-02-01T12:00:00Z',accession='b'),
             self.obs('2020-03-01T12:00:00Z','2000','c'),self.obs('2020-04-01T12:00:00Z','2000','d')]
        result=study.transitions(obs)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['last_old']['accession'],'b')
        self.assertEqual(result[0]['first_new']['accession'],'c')
        self.assertFalse(result[0]['effective_date_known'])

    def test_density_deduplicates_instant(self):
        obs=[self.obs('2020-01-01T12:00:00Z'),self.obs('2020-01-03T12:00:00Z',accession='b'),self.obs('2020-01-03T07:00:00-05:00',accession='c')]
        self.assertEqual(study.density(obs),dict(observations=3,unique_instants=2,median_gap_days=2,maximum_gap_days=2))

    def test_naive_cutoff_rejected(self):
        with self.assertRaises(ValueError):study.lookup([],'1',datetime(2020,1,1))
        with self.assertRaises(ValueError):study.instant('2020-01-01T00:00:00')

    def test_request_cap_and_prior_access_denial_stop_without_network(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(study,'ROOT',Path(tmp)),patch.object(study,'_pace'),patch.object(study.requests,'get') as get:
            plan=[study.header_request('0000000001','0000000001-20-000001','fixture')]
            study.save(Path(tmp)/'plan.json',plan)
            for ledger in ([dict(url='fixture',status=403)], [dict(url='fixture',status=200)]*80):
                study.save(Path(tmp)/'requests.json',ledger)
                with self.assertRaises(ValueError):study.fetch(Path(tmp)/'plan.json')
            get.assert_not_called()

    def test_saved_headers_and_results_replay_without_network(self):
        with patch.object(study.requests,'get',side_effect=AssertionError('Network forbidden')):
            observations=study.verified_observations()
            saved=json.loads((study.ROOT/'results.json').read_text())
            self.assertEqual(observations,saved['observations'])
            self.assertEqual(study.transitions(observations),saved['transitions'])
            for e in saved['event_lookups']:
                identity=next(i for i in saved['identities'] if i['security_id']==e['security_id'])
                self.assertEqual(study.lookup(observations,identity['ciks'][0],study.instant(e['decision_at'])),e['issuer_lookup'])
            for p in saved['transition_probes']:
                self.assertEqual(study.lookup(observations,p['cik'],study.instant(p['decision_at'])),p['observed_lookup'])


if __name__=='__main__':unittest.main()
