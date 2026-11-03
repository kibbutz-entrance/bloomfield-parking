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

    def test_city_api_uses_utc_and_actual_venue(self):
        event = dict(id=1, title='הפועל תל־אביב – מכבי חיפה', utc_start_date='2026-11-02 18:30:00',
                     venue=dict(venue='אצטדיון בלומפילד'), url='https://sportlv.co.il/event/1', all_day=False)
        result = u.parse_city(json.dumps(dict(events=[event], total=1)))
        self.assertEqual(result[0]['k'], '20:30')
        self.assertEqual(result[0]['d'], '2026-11-02')

    def test_city_api_does_not_silently_truncate_pagination(self):
        source = next(s for s in u.SOURCES if s['id'] == 'city')
        with patch.object(u, 'fetch', return_value=json.dumps(dict(events=[], total=3))):
            with self.assertRaises(ValueError):
                u.fetch_city(source, NOW)

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

    def test_same_publisher_feeds_do_not_count_as_corroboration(self):
        g = u.build_games([record(source='stadium_sports'), record(source='stadium_culture')], NOW.date())[0]
        self.assertEqual(g['independent_publishers'], 1)
        self.assertEqual(g['verification'], 'official')

    def test_independent_agreement_has_inspectable_evidence(self):
        g = u.build_games([record(), record(source='maccabi')], NOW.date())[0]
        self.assertEqual(g['independent_publishers'], 2)
        self.assertEqual(g['verification'], 'cross_checked')
        self.assertEqual(len(g['evidence']), 2)

    def test_old_time_cannot_overrule_current_observation(self):
        g = u.build_games([record(current=False, k='19:00'), record(source='maccabi', current=True, k='14:00')], NOW.date())[0]
        self.assertFalse(g['conflict'])
        self.assertEqual(g['k'], '14:00')
        self.assertEqual(g['ignored_cached_sources'], ['ifa_maccabi'])

    def test_current_cancellation_overrules_cached_active_event(self):
        self.assertEqual(u.build_games([record(current=False), record(source='maccabi', current=True, cancelled=True)], NOW.date()), [])

    def test_current_away_venue_overrules_cached_bloomfield(self):
        self.assertEqual(u.build_games([record(current=False), record(source='maccabi', current=True, venue='נתניה')], NOW.date()), [])

    def test_current_reschedule_does_not_create_a_phantom_old_day(self):
        games = u.build_games([record(current=False), record(source='maccabi', current=True, d='2026-11-07')], NOW.date())
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0]['d'], '2026-11-07')
        self.assertFalse(games[0]['conflict'])

    def test_stale_unique_fixture_is_retained_as_a_warning(self):
        g = u.build_games([record(current=False)], NOW.date())[0]
        self.assertFalse(g['evidence'][0]['current'])

    def test_haoman_uses_explicit_event_date_not_publication_date(self):
        page = dict(items=[dict(id='1', title='Party', body='<p>Friday, November 6, 2026 Doors 23:55</p>', fullUrl='/events/party', publishOn=1)], pagination={})
        r = u.parse_haoman(json.dumps(page))[0]
        self.assertEqual((r['d'], r['k']), ('2026-11-06', '23:55'))
        r['source'] = 'haoman'
        g = u.build_games([r], NOW.date())[0]
        self.assertEqual(g['start'], '2026-11-06T22:55:00+02:00')
        self.assertEqual(g['end'], '2026-11-07T05:55:00+02:00')
        self.assertEqual(g['kind'], 'nightlife')

    def test_haoman_partial_parse_retains_only_explicit_dated_events(self):
        page = dict(items=[dict(id='1', title='Party', body='November 6, 2026 Doors 23:55', fullUrl='/events/party'),
                           dict(id='2', title='Undated', body='Tickets soon', fullUrl='/events/undated')], pagination={})
        self.assertEqual(len(u.parse_haoman(json.dumps(page), strict=False)), 1)
        with patch.object(u, 'fetch_haoman', return_value=dict(records=u.parse_haoman(json.dumps(page), strict=False), unresolved_items=1)):
            result = u.collect_source(next(s for s in u.SOURCES if s['id']=='haoman'), {}, NOW)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['unresolved_items'], 1)
            self.assertEqual(len(result['records']), 1)

    def test_haoman_abbreviated_month_and_am_time(self):
        page = dict(items=[dict(id='1', title='Afterparty', body='Friday, Nov 6, 2026 Doors 2:00 am', fullUrl='/events/party')], pagination={})
        r = u.parse_haoman(json.dumps(page))[0]
        self.assertEqual((r['d'], r['k']), ('2026-11-06', '02:00'))

    def test_haoman_pagination_does_not_assume_publication_order_is_event_order(self):
        def page(day, pagination):
            return json.dumps(dict(items=[dict(id=day, title='Party', body=day + ' Doors 23:55', fullUrl='/events/party')], pagination=pagination))
        pages = [page('October 1, 2026', dict(nextPage=True, nextPageUrl='/events?offset=1')),
                 page('November 6, 2026', dict(nextPage=False))]
        with patch.object(u, 'fetch', side_effect=pages):
            result = u.fetch_haoman(next(s for s in u.SOURCES if s['id']=='haoman'), NOW)
        self.assertEqual(len(result['records']), 2)
        self.assertEqual(result['records'][1]['d'], '2026-11-06')

    def test_haoman_pagination_loop_is_a_failure(self):
        page = json.dumps(dict(items=[], pagination=dict(nextPage=True, nextPageUrl='/events?format=json')))
        with patch.object(u, 'fetch', return_value=page), self.assertRaises(ValueError):
            u.fetch_haoman(next(s for s in u.SOURCES if s['id']=='haoman'), NOW)

    def test_haoman_missing_event_date_is_a_parse_failure(self):
        with self.assertRaises(ValueError):
            u.parse_haoman(json.dumps(dict(items=[dict(body='Tickets soon', publishOn=1793172777307)], pagination={})))

    def test_nearby_unknown_time_stays_planned(self):
        g = u.build_games([record(source='haoman', venue='האומן 17', venue_id='haoman', kind='nightlife', k='', tentative=True)], NOW.date())[0]
        self.assertFalse(g['c'])
        self.assertIsNone(g['start'])

    def test_all_upstreams_failing_publish_partial_health(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(u, 'fetch', side_effect=TimeoutError('offline')):
            output, cache = Path(folder)/'games.json', Path(folder)/'cache.json'
            result = u.update(output, cache, NOW)
            self.assertFalse(result['coverage']['complete'])
            self.assertIsNone(result['updated'])
            self.assertEqual(json.loads(output.read_text())['games'], [])


if __name__ == '__main__':
    unittest.main()
