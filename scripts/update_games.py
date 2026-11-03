#!/usr/bin/env python3
"""Pull public official schedules; preserve source age and failures. Python 3.11+."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request

TZ = ZoneInfo('Asia/Jerusalem')
ROOT = Path(__file__).resolve().parents[1]
BEFORE_MIN, AFTER_MIN, FRESH_HOURS, COVERAGE_DAYS = 180, 150, 2, 365
MTA_URL = 'https://www.maccabi-tlv.co.il/' + urllib.parse.quote('משחקים-ותוצאות/הקבוצה-הבוגרת/לוח-משחקים/')
SOURCES = [
    dict(id='stadium_sports', label='היכלי הספורט · ספורט', url='https://www.sportpalace.co.il/index.php?id=10&option=com_dpcalendar&task=ical.download', parser='ics', required=True),
    dict(id='stadium_culture', label='היכלי הספורט · תרבות', url='https://www.sportpalace.co.il/index.php?id=11&option=com_dpcalendar&task=ical.download', parser='ics', required=True),
    dict(id='ifa_maccabi', label='ההתאחדות · מכבי ת״א', url='https://www.football.org.il/team-details/team-games/?team_id=1061', parser='ifa', required=False),
    dict(id='ifa_hapoel', label='ההתאחדות · הפועל ת״א', url='https://www.football.org.il/team-details/team-games/?team_id=2176', parser='ifa', required=False),
    dict(id='maccabi', label='מכבי ת״א · האתר הרשמי', url=MTA_URL, parser='mta', required=True),
    dict(id='haoman', label='האומן 17 · לוח רשמי', url='https://www.haoman17.com/events?format=json', parser='haoman', required=False),
    dict(id='city', label='רשות הספורט · תל אביב־יפו', url='https://sportlv.co.il/wp-json/tribe/events/v1/events', parser='city', required=True),
]


# Feeds from the same organization are never counted as independent evidence.
PUBLISHERS = dict(stadium_sports='stadium', stadium_culture='stadium',
                  ifa_maccabi='ifa', ifa_hapoel='ifa', maccabi='maccabi', city='city', haoman='haoman')


def parse_haoman(text, strict=True):
    data = json.loads(text)
    if not isinstance(data.get('items'), list) or not isinstance(data.get('pagination'), dict):
        raise ValueError('Haoman schedule response has changed')
    records = []
    months = {}
    for i, name in enumerate('January February March April May June July August September October November December'.split(), 1):
        months[name] = months[name[:3]] = i
    months['Sept'] = 9
    for item in data['items']:
        body = re.sub(r'<(style|script)\b[^>]*>.*?</\1>', '', item.get('body', ''), flags=re.S | re.I)
        body = Tree(body).root.text()
        match = re.search(r'\b(' + '|'.join(months) + r')\s+(\d{1,2}),?\s+(20\d{2})\b', body, re.I)
        if not match:
            # Never use the blog publication timestamp as the event date.
            if strict:
                raise ValueError('Haoman event is missing an explicit full event date')
            continue
        day = date(int(match[3]), months[match[1].title()], int(match[2]))
        clock = re.search(r'\bDoors\s+([0-2]?\d):([0-5]\d)\s*(am|pm)?\b', body, re.I)
        kick = ''
        if clock:
            hour = int(clock[1])
            if clock[3]:
                if not 1 <= hour <= 12:
                    raise ValueError('Invalid 12-hour event time')
                hour = hour % 12 + (12 if clock[3].lower() == 'pm' else 0)
            if hour > 23:
                raise ValueError('Invalid event hour')
            kick = f'{hour:02d}:{clock[2]}'
        records.append(dict(native_id=item['id'], d=day.isoformat(), k=kick,
                            title=Tree(item['title']).root.text(), venue='האומן 17', venue_id='haoman', kind='nightlife',
                            url=urllib.parse.urljoin('https://www.haoman17.com', item['fullUrl']),
                            tentative=not bool(clock), cancelled=bool(re.search(r'\b(cancelled|canceled|postponed)\b|בוטל|נדחה', body))))
    return records


def fetch_haoman(source, now):
    records, url, seen, unresolved = [], source['url'], set(), 0
    for _ in range(20):
        if url in seen:
            raise ValueError('Haoman pagination loop')
        seen.add(url)
        text = fetch(url)
        data = json.loads(text)
        page = parse_haoman(text, strict=False)
        unresolved += len(data['items']) - len(page)
        records.extend(page)
        # Publication order is not event order: follow every page, even if the
        # current page contains only past events. Never silently truncate.
        if not data['pagination'].get('nextPage'):
            return dict(records=records, unresolved_items=unresolved)
        next_url = urllib.parse.urljoin(source['url'], data['pagination']['nextPageUrl'])
        if urllib.parse.urlparse(next_url).hostname != 'www.haoman17.com':
            raise ValueError('Unexpected Haoman pagination host')
        url = next_url + ('&' if '?' in next_url else '?') + 'format=json'
    raise ValueError('Haoman pagination is incomplete')


class Node:
    def __init__(self, tag='root', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return re.sub(r'\s+', ' ', ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)).strip()

    def find(self, cls):
        out = []
        for c in self.children:
            if isinstance(c, Node):
                if cls in c.attrs.get('class', '').split():
                    out.append(c)
                out.extend(c.find(cls))
        return out


class Tree(HTMLParser):
    VOID = set('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def stamp(now):
    return now.astimezone(timezone.utc).isoformat(timespec='seconds')


def is_bloomfield(venue):
    return bool(re.search('בלומפילד|bloomfield|blumfield', venue, re.I))


def ics_unescape(text):
    return re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1].lower() == 'n' else m[1], text)


def ics_datetime(value, params):
    if re.fullmatch(r'\d{8}', value):
        return datetime.strptime(value, '%Y%m%d').date()
    fmt = '%Y%m%dT%H%M%S' if len(value.rstrip('Z')) == 15 else '%Y%m%dT%H%M'
    x = datetime.strptime(value.rstrip('Z'), fmt)
    tzid = re.search(r'(?:^|;)TZID=([^;]+)', params)
    tz = timezone.utc if value.endswith('Z') else ZoneInfo(tzid[1].strip('"')) if tzid else TZ
    return x.replace(tzinfo=tz).astimezone(TZ)


def parse_ics(text):
    if 'BEGIN:VCALENDAR' not in text or 'END:VCALENDAR' not in text:
        raise ValueError('Calendar response is missing VCALENDAR markers')
    text = re.sub(r'\r?\n[ \t]', '', text)
    records = []
    for block in text.split('BEGIN:VEVENT')[1:]:
        props = {}
        for line in block.split('END:VEVENT', 1)[0].splitlines():
            if ':' in line:
                head, value = line.split(':', 1)
                props[head.split(';', 1)[0]] = (head, value)
        get = lambda key: ics_unescape(props.get(key, ('', ''))[1])
        venue = get('X-LOCATION-DISPLAYNAME') or get('LOCATION')
        if not is_bloomfield(venue):
            continue
        if 'RRULE' in props or 'RECURRENCE-ID' in props:
            raise ValueError('Recurring Bloomfield events need explicit expansion')
        if 'DTSTART' not in props or not get('SUMMARY'):
            raise ValueError('Bloomfield event is missing its date/title')
        start = ics_datetime(props['DTSTART'][1], props['DTSTART'][0])
        timed = isinstance(start, datetime)
        records.append(dict(native_id=get('UID'), d=start.date().isoformat() if timed else start.isoformat(),
                            k=start.strftime('%H:%M') if timed else '', title=get('SUMMARY'), venue=venue,
                            url=get('URL'), cancelled=get('STATUS').upper() == 'CANCELLED',
                            tentative=not timed or get('STATUS').upper() == 'TENTATIVE'))
    return records


def parse_ifa(text):
    records = []
    for row in Tree(text).root.find('table_row'):
        cols = row.find('table_col')
        if len(cols) != 5:
            continue
        values = [re.sub(r'^(תאריך|משחק|אצטדיון|שעה|תוצאה)\s*', '', x.text()).strip() for x in cols]
        d, title, venue, kick, result = values
        if not re.fullmatch(r'\d{2}/\d{2}/\d{4}', d):
            continue
        day = datetime.strptime(d, '%d/%m/%Y').date().isoformat()
        k = kick if re.fullmatch(r'\d{2}:\d{2}', kick) and kick != '00:00' else ''
        records.append(dict(native_id='', d=day, k=k, title=title, venue=venue,
                            url='https://www.football.org.il' + row.attrs.get('href', ''),
                            cancelled=any(w in row.text() for w in ('בוטל', 'נדחה')), tentative=not k))
    if not records:
        raise ValueError('No fixture rows found; source format may have changed')
    return records


MONTHS = dict(zip('ינו פבר מרץ אפר מאי יונ יול אוג ספט אוק נוב דצמ'.split(), range(1, 13)))


def parse_city(text):
    data = json.loads(text)
    if not isinstance(data.get('events'), list) or not isinstance(data.get('total'), int):
        raise ValueError('City events API returned an invalid response')
    records = []
    for event in data['events']:
        venue = (event.get('venue') or {}).get('venue', '')
        if not is_bloomfield(venue):
            continue
        # Use the published UTC value, rather than a fixed UTC+2 label across DST.
        start = datetime.fromisoformat(event['utc_start_date']).replace(tzinfo=timezone.utc).astimezone(TZ)
        cancelled = any(word in str(event.get('event_status', '')).lower() for word in ('cancelled', 'canceled', 'postponed'))
        records.append(dict(native_id=str(event['id']), d=start.date().isoformat(),
                            k='' if event.get('all_day') else start.strftime('%H:%M'),
                            title=Tree(event['title']).root.text(), venue=venue, url=event['url'],
                            cancelled=cancelled, tentative=bool(event.get('all_day'))))
    return records


def fetch_city(source, now):
    today = now.astimezone(TZ).date()
    params = dict(start_date=str(today - timedelta(days=1)) + ' 00:00:00',
                  end_date=str(today + timedelta(days=COVERAGE_DAYS)) + ' 23:59:59', per_page=50)
    records, received, expected = [], 0, None
    for page in range(1, 11):
        text = fetch(source['url'] + '?' + urllib.parse.urlencode({**params, 'page': page}))
        data = json.loads(text)
        records.extend(parse_city(text))
        received += len(data['events'])
        expected = data['total'] if expected is None else expected
        if received >= expected:
            return records
        if not data['events']:
            break
    raise ValueError('City API pagination is incomplete')


def parse_mta(text):
    records = []
    for f in Tree(text).root.find('fixture-short'):
        locs, teams = f.find('location'), f.find('nn')
        if not locs or len(teams) != 2:
            raise ValueError('A fixture is missing its location or teams')
        loc = locs[0].text()
        match = re.search(r'(\d{2})\s+(\S+)\s+(\d{4})', loc)
        if not match:
            raise ValueError('Unrecognized Hebrew fixture date')
        day = date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()
        tm = re.search(r'\b(\d{2}:\d{2})\b', loc)
        kick = tm[1] if tm else ''
        venue = loc[match.end():].replace(kick, '').replace('מועד לא סופי', '').strip()
        league = f.find('league-title')
        title = ' – '.join(t.text() for t in teams)
        if league and 'גביע' in league[0].text():
            title += ' (' + league[0].text() + ')'
        records.append(dict(native_id='', d=day, k=kick, title=title, venue=venue, url=MTA_URL,
                            tentative='מועד לא סופי' in loc or not kick, cancelled=any(w in loc for w in ('בוטל', 'נדחה'))))
    if not records:
        raise ValueError('No fixture cards found; source format may have changed')
    return records


ALIASES = {
    'maccabi_ta': ('מכבי תל אביב', 'מכבי תא'), 'hapoel_ta': ('הפועל תל אביב', 'הפועל תא'),
    'maccabi_pt': ('מכבי פתח תקווה', 'מכבי פתח תקוה', 'מכבי פת'), 'hapoel_pt': ('הפועל פתח תקווה', 'הפועל פתח תקוה', 'הפועל פת'),
    'maccabi_haifa': ('מכבי חיפה',), 'hapoel_haifa': ('הפועל חיפה',), 'netanya': ('מכבי נתניה',),
    'tiberias': ('עירוני טבריה', 'עירוני דורות טבריה'), 'jerusalem': ('הפועל ירושלים', 'הפועל ים'),
    'beersheva': ('הפועל באר שבע', 'הפועל בש'), 'kiryat_shmona': ('עירוני קריית שמונה', 'הפועל קש', 'עירוני קש'),
    'beitar': ('ביתר ירושלים', 'ביתר ים'), 'ramat_gan': ('הפועל רמת גן', 'הפועל רג'), 'sakhnin': ('בני סכנין',),
}
EN = dict(zip(ALIASES, ['Maccabi Tel Aviv', 'Hapoel Tel Aviv', 'Maccabi Petah Tikva', 'Hapoel Petah Tikva', 'Maccabi Haifa', 'Hapoel Haifa', 'Maccabi Netanya', 'Ironi Tiberias', 'Hapoel Jerusalem', "Hapoel Be'er Sheva", 'Ironi Kiryat Shmona', 'Beitar Jerusalem', 'Hapoel Ramat Gan', 'Bnei Sakhnin']))


def norm(title):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', title.replace('־', ' '))).strip()


def identity(title):
    normalized = norm(title)
    teams = [key for key, variants in ALIASES.items() if any(v in normalized for v in variants)]
    return '|'.join(sorted(teams)) if len(teams) == 2 else normalized


def english_title(title):
    value, teams = norm(title), []
    for key, variants in ALIASES.items():
        positions = [value.find(v) for v in variants if v in value]
        if positions:
            teams.append((min(positions), EN[key]))
    return ' vs '.join(t[1] for t in sorted(teams)) if len(teams) == 2 else title


def build_games(records, today):
    groups = {}
    for item in records:
        if today - timedelta(days=1) <= date.fromisoformat(item['d']) <= today + timedelta(days=365):
            key = identity(item['title']) + ('@' + item['venue_id'] if item.get('venue_id') else '')
            groups.setdefault((key, item['d']), []).append(item)
    # Reconcile dates/venues/cancellations using current observations first.
    # Failed-source caches remain a fallback only when no current observation
    # of the same event exists within the rescheduling window.
    discarded = {}
    for (key, day), items in list(groups.items()):
        has_current = any(x.get('current', True) for (other, when), peers in groups.items()
                          if other == key and abs((date.fromisoformat(when) - date.fromisoformat(day)).days) <= 3
                          for x in peers)
        if has_current:
            discarded[(key, day)] = [x for x in items if not x.get('current', True)]
            groups[(key, day)] = [x for x in items if x.get('current', True)]
    groups = {key: items for key, items in groups.items() if items}
    games = []
    for (key, day), items in groups.items():
        bloom = [x for x in items if is_bloomfield(x['venue']) or x.get('venue_id') == 'haoman']
        active = [x for x in bloom if not x.get('cancelled')]
        # A home fixture with an unpublished venue could still be at Bloomfield.
        # Keep it uncertain instead of using its absence as an all-clear signal.
        pending = [x for x in items if not x['venue'] and not x.get('cancelled') and
                   any(alias in norm(re.split(r'\s[-–]\s', x['title'])[0]) for alias in ('מכבי תא', 'מכבי תל אביב', 'הפועל תא', 'הפועל תל אביב'))]
        if not active and pending and not any(x['venue'] for x in items):
            active = pending
        if not active:
            continue
        times = sorted({x['k'] for x in active if x.get('k')})
        venue_conflict = any(x['venue'] and not (is_bloomfield(x['venue']) or x.get('venue_id') == 'haoman') for x in items)
        date_conflict = any(okey == key and oday != day and abs((date.fromisoformat(oday) - date.fromisoformat(day)).days) <= 3 for okey, oday in groups)
        conflict = len(times) > 1 or venue_conflict or date_conflict or any(x.get('cancelled') for x in bloom)
        known = [x for x in active if x.get('k') and not x.get('tentative')]
        chosen = next((x for x in active if x['source'].startswith('ifa')), active[0])
        start = end = None
        if times:
            before, after = (60, 360) if chosen.get('kind') == 'nightlife' else (BEFORE_MIN, AFTER_MIN)
            start = datetime.fromisoformat(day + 'T' + min(times)).replace(tzinfo=TZ) - timedelta(minutes=before)
            end = datetime.fromisoformat(day + 'T' + max(times)).replace(tzinfo=TZ) + timedelta(minutes=after)
        title = chosen['title']
        game = dict(id=hashlib.sha256((key + day).encode()).hexdigest()[:16], d=day,
                    k=times[0] if len(times) == 1 else '', s=start.strftime('%H:%M') if start else '', e=end.strftime('%H:%M') if end else '',
                    start=start.isoformat() if start else None, end=end.isoformat() if end else None,
                    c=bool(known) and bool(bloom) and not conflict, conflict=conflict, venue_unconfirmed=not bool(bloom), t=dict(he=title, en=english_title(title)),
                    sources=sorted({x['source'] for x in items}), references=sorted({x['url'] for x in active if x.get('url')}),
                    kind=chosen.get('kind') or ('culture' if all(x['source'] == 'stadium_culture' for x in active) else 'sport'),
                    venue=chosen['venue'],
                    evidence=[dict(source=x['source'], publisher=PUBLISHERS[x['source']], observed_at=x.get('observed_at'),
                                   current=x.get('current', True), date=x['d'], time=x.get('k', ''), venue=x['venue'],
                                   tentative=x.get('tentative', False), cancelled=x.get('cancelled', False), url=x.get('url', '')) for x in items],
                    ignored_cached_sources=sorted({x['source'] for x in discarded.get((key, day), [])}),
                    independent_publishers=len({PUBLISHERS[x['source']] for x in known if x.get('current', True)}))
        game['verification'] = 'cached' if not any(x.get('current', True) for x in active) else 'conflict' if conflict else 'cross_checked' if game['c'] and game['independent_publishers'] >= 2 else 'official' if game['c'] else 'planned'
        if (end.date() if end else date.fromisoformat(day)) >= today:
            games.append(game)
    return sorted(games, key=lambda g: (g['d'], g['k'], g['id']))


def fetch(url):
    url = urllib.parse.quote(url, safe=':/?=&%+;@')
    req = urllib.request.Request(url, headers={'User-Agent': 'KibbutzParking/2.0 (public event schedules; every 30 minutes)', 'Accept': 'text/calendar,text/html;q=0.9'})
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                if urllib.parse.urlparse(response.url).hostname != urllib.parse.urlparse(url).hostname:
                    raise ValueError('Source redirected to another host')
                data = response.read(4_000_001)
                if len(data) > 4_000_000:
                    raise ValueError('Source exceeds the response-size limit')
                return data.decode('utf-8-sig')
        except Exception:
            if attempt:
                raise
            time.sleep(1)


def collect_source(source, previous, now, fixture_dir=None):
    checked = stamp(now)
    try:
        suffix = '.ics' if source['parser'] == 'ics' else '.html'
        if source['parser'] in ('city', 'haoman') and not fixture_dir:
            parsed = (fetch_city if source['parser'] == 'city' else fetch_haoman)(source, now)
        else:
            text = (fixture_dir / (source['id'] + suffix)).read_text() if fixture_dir else fetch(source['url'])
            parsed = dict(ics=parse_ics, ifa=parse_ifa, mta=parse_mta, city=parse_city, haoman=parse_haoman)[source['parser']](text)
        unresolved = parsed.get('unresolved_items', 0) if isinstance(parsed, dict) else 0
        if isinstance(parsed, dict):
            parsed = parsed['records']
        return dict(status='partial' if unresolved else 'ok', checked_at=checked, last_success=checked,
                    unresolved_items=unresolved, records=[{**r, 'source': source['id']} for r in parsed])
    except Exception as error:
        return dict(status='error', checked_at=checked, last_success=previous.get('last_success'),
                    error=type(error).__name__ + ': ' + str(error)[:160], records=previous.get('records', []))


def update(output, cache_path, now, fixture_dir=None):
    try:
        previous = json.loads(cache_path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        previous = {}
    with ThreadPoolExecutor(max_workers=len(SOURCES)) as pool:
        results = list(pool.map(lambda s: collect_source(s, previous.get(s['id'], {}), now, fixture_dir), SOURCES))
    cache = dict(zip((s['id'] for s in SOURCES), results))
    today = now.astimezone(TZ).date()
    games = build_games([{**r, 'current': value['status'] in ('ok', 'partial'), 'observed_at': value.get('last_success')} for value in results for r in value['records']], today)
    sources = [{**{k: s[k] for k in ('id', 'label', 'url', 'required')}, **{k: r[k] for k in ('status', 'checked_at', 'last_success', 'error', 'unresolved_items') if k in r},
                'publisher': PUBLISHERS[s['id']], 'scope': 'nearby' if s['id'] == 'haoman' else 'stadium',
                'events_count': sum(is_bloomfield(x['venue']) or bool(x.get('venue_id')) for x in r['records'])} for s, r in zip(SOURCES, results)]
    required_ok = all(not s['required'] or s['status'] == 'ok' for s in sources)
    successful = [s['last_success'] for s in sources if s.get('last_success')]
    data = dict(schema=2, updated=max(successful) if successful else None, last_attempt=stamp(now), timezone='Asia/Jerusalem', fresh_hours=FRESH_HOURS,
                coverage=dict(start=today.isoformat(), through=(today + timedelta(days=COVERAGE_DAYS)).isoformat(), complete=required_ok, basis='published_schedules', detailed_through=(today + timedelta(days=14)).isoformat()),
                sources=sources, games=games, parking_window=dict(before_minutes=BEFORE_MIN, after_minutes=AFTER_MIN, estimated=True))
    for path, value in ((cache_path, cache), (output, data)):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(path)
    print(json.dumps(dict(games=len(games), healthy_sources=sum(s['status'] == 'ok' for s in sources), total_sources=len(sources), coverage_complete=required_ok, basis='published_schedules', detailed_through=(today + timedelta(days=14)).isoformat())))
    for s in sources:
        if s['status'] == 'error':
            print(f"::warning::{s['id']}: {s['error']}")
    return data  # Publish partial status, so failures don't leave an old green signal.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'games.json')
    parser.add_argument('--cache', type=Path, default=ROOT / 'data/source-cache.json')
    parser.add_argument('--fixtures', type=Path)
    args = parser.parse_args()
    update(args.output, args.cache, datetime.now(timezone.utc), args.fixtures)
