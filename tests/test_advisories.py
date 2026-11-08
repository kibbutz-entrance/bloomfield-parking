import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('updater', Path(__file__).parents[1]/'scripts/update_games.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
NOW = datetime(2026, 11, 8, 7, tzinfo=timezone.utc)
FILE = u.ROOT/'data/nearby-advisories.json'

class AdvisoryTests(unittest.TestCase):
    def test_reviewed_primary_notices_are_kept_separate_from_matches(self):
        items = u.load_advisories(FILE, NOW)
        self.assertEqual(len(items), 13)
        self.assertTrue(all(x['parking_impact']=='unmeasured' for x in items))
        self.assertTrue(all('haoman' not in str(x).lower() for x in items))

    def test_conflicting_duplex_clock_is_not_invented(self):
        item = next(x for x in u.load_advisories(FILE,NOW) if x['id']=='duplex-2026-11-12')
        self.assertEqual(item['k'], '')
        self.assertIn('23:55', item['note']['he'])
        self.assertIn('23:59', item['note']['he'])

    def test_protected_gagarin_event_keeps_unknown_time(self):
        item = next(x for x in u.load_advisories(FILE,NOW) if x['id']=='gagarin-insomnia')
        self.assertEqual(item['k'], '')
        self.assertIsNone(item['start'])
        self.assertEqual(item['through'], '2026-11-14')

    def test_night_work_has_explicit_next_day_end(self):
        item = next(x for x in u.load_advisories(FILE,NOW) if x['id']=='lavon-2026-11-12')
        self.assertEqual(item['end'], '2026-11-13T05:00:00+02:00')

    def test_expired_notices_disappear_without_changing_review_age(self):
        items = u.load_advisories(FILE, datetime(2026,11,15,7,tzinfo=timezone.utc))
        self.assertTrue(all(x['through']>='2026-11-15' for x in items))
        self.assertTrue(all(x['verified_at']=='2026-11-08T06:15:05+00:00' for x in items))

    def test_unapproved_source_and_duplicate_id_are_rejected(self):
        data=json.loads(FILE.read_text())
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'notices.json'
            broken=copy.deepcopy(data);broken['advisories'][0]['references']=['https://www.haoman17.com/events']
            p.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):u.load_advisories(p,NOW)
            broken=copy.deepcopy(data);broken['advisories'].append(broken['advisories'][0]);p.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):u.load_advisories(p,NOW)

    def test_refresh_outage_keeps_reviewed_notices_and_does_not_change_sources(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(u,'fetch',side_effect=TimeoutError('offline')):
            result=u.update(Path(folder)/'games.json',Path(folder)/'cache.json',NOW)
            self.assertEqual(len(result['nearby_advisories']),13)
            self.assertEqual(result['games'],[])
            self.assertIsNone(result['updated'])
            self.assertEqual(len(result['sources']),6)
            again=u.update(Path(folder)/'games.json',Path(folder)/'cache.json',NOW)
            self.assertEqual(again['nearby_advisories'],result['nearby_advisories'])
