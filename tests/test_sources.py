import importlib.util
import json
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('updater', Path(__file__).parents[1] / 'scripts/update_games.py')
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)
NOW = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)


def record(**kwargs):
    return dict(dict(d='2026-11-06', k='14:00', title='מכבי ת"א - מכבי פ"ת', venue='בלומפילד',
                     source='ifa_maccabi', url='https://www.football.org.il/', tentative=False, cancelled=False), **kwargs)


class SourceTests(unittest.TestCase):
    def test_calendar_venue_and_utc_conversion(self):
        text = 'BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:1\nDTSTART:20261106T120000Z\nSUMMARY:מכבי ת"א-\n מכבי פ"ת\nX-LOCATION-DISPLAYNAME:אצטדיון בלומפילד\nEND:VEVENT\nBEGIN:VEVENT\nDTSTART:20261106T120000Z\nSUMMARY:משחק בבלומפילד\nLOCATION:סמי עופר\nEND:VEVENT\nEND:VCALENDAR'
        items = u.parse_ics(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['k'], '14:00')
        self.assertEqual(items[0]['title'], 'מכבי ת"א-מכבי פ"ת')

    def test_html_error_cannot_be_an_empty_calendar(self):
        with self.assertRaises(ValueError):
            u.parse_ics('<html>403 Access denied</html>')

    def test_ifa_placeholder_is_not_midnight_kickoff(self):
        cols = ['06/11/2026', 'מכבי ת"א - מכבי פ"ת', 'בלומפילד', '00:00', '']
        html = '<a class="table_row">' + ''.join('<div class="table_col">'+c+'</div>' for c in cols)+'</a>'
        self.assertEqual(u.parse_ifa(html)[0]['k'], '')

    def test_mta_unpublished_time_not_invented(self):
        html = '<div class="fixture-short"><div class="nn">מכבי תל אביב</div><div class="nn">הפועל תל אביב</div><div class="location">26 דצמ 2026 <div>בלומפילד</div><span>מועד לא סופי</span></div></div>'
        r = u.parse_mta(html)[0]
        self.assertEqual(r['k'], '')
        self.assertTrue(r['tentative'])

    def test_cross_source_aliases_deduplicate(self):
        games = u.build_games([record(), record(title='מכבי תל אביב – מכבי פתח תקווה', source='maccabi')], NOW.date())
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]['sources'], ['ifa_maccabi', 'maccabi'])
        self.assertTrue(games[0]['c'])

    def test_time_disagreement_is_not_confirmed(self):
        g = u.build_games([record(), record(k='19:00', source='maccabi')], NOW.date())[0]
        self.assertFalse(g['c'])
        self.assertTrue(g['conflict'])
        self.assertEqual((g['s'], g['e']), ('11:00', '21:30'))

    def test_changed_venue_is_flagged(self):
        g = u.build_games([record(), record(venue='נתניה', source='maccabi')], NOW.date())[0]
        self.assertTrue(g['conflict'])
        self.assertFalse(g['c'])

    def test_unpublished_home_venue_cannot_be_used_as_an_all_clear(self):
        g = u.build_games([record(venue='', k='')], NOW.date())[0]
        self.assertTrue(g['venue_unconfirmed'])
        self.assertFalse(g['c'])

    def test_confirmed_other_venue_does_not_create_a_bloomfield_event(self):
        self.assertEqual(u.build_games([record(venue='רחובות')], NOW.date()), [])

    def test_cancelled_event_disappears(self):
        self.assertEqual(u.build_games([record(cancelled=True)], NOW.date()), [])

    def test_date_disagreement_flags_both_days(self):
        games = u.build_games([record(), record(d='2026-11-07', source='maccabi')], NOW.date())
        self.assertTrue(all(g['conflict'] for g in games))

    def test_cross_midnight_preserves_end_date(self):
        g = u.build_games([record(k='23:30')], NOW.date())[0]
        self.assertEqual(g['end'], '2026-11-07T02:00:00+02:00')

    def test_no_time_has_no_estimated_window(self):
        g = u.build_games([record(k='', tentative=True)], NOW.date())[0]
        self.assertIsNone(g['start'])
        self.assertFalse(g['c'])

    def test_failure_does_not_refresh_cached_success(self):
        previous = dict(last_success='2026-11-01T12:00:00+00:00', records=[record()])
        with patch.object(u, 'fetch', side_effect=TimeoutError('offline')):
            result = u.collect_source(u.SOURCES[0], previous, NOW)
        self.assertEqual(result['last_success'], previous['last_success'])
        self.assertEqual(result['records'], previous['records'])
        self.assertEqual(result['status'], 'error')

    def test_all_upstreams_failing_publish_partial_health(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(u, 'fetch', side_effect=TimeoutError('offline')):
            output, cache = Path(folder)/'games.json', Path(folder)/'cache.json'
            result = u.update(output, cache, NOW)
            self.assertFalse(result['coverage']['complete'])
            self.assertIsNone(result['updated'])
            self.assertEqual(json.loads(output.read_text())['games'], [])


if __name__ == '__main__':
    unittest.main()
