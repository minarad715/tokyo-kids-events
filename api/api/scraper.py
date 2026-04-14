#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json, re, time, datetime, os, sys
from urllib.parse import urljoin

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; TokyoKidsBot/1.0)'}
BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..')

REGION_CONFIG = {
    'tokyo':    {'pref_id': '13', 'output': 'events.json'},
    'kanagawa': {'pref_id': '14', 'output': 'events_kanagawa.json'},
    'saitama':  {'pref_id': '11', 'output': 'events_saitama.json'},
    'chiba':    {'pref_id': '12', 'output': 'events_chiba.json'},
}

def fetch_html(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"  取得失敗 {url}: {e}")
        return None

def fetch_rss(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.content, 'lxml-xml')
    except Exception as e:
        print(f"  RSS取得失敗 {url}: {e}")
        return None

# ─── 代々木公園系サイト（静的HTML・地域別） ───
PARK_SITES = {
    'tokyo':    'https://www.yoyogikoen.info/',
    'kanagawa': 'https://www.yokohamaevent.info/',
    'saitama':  'https://www.saitama-shintoshin.com/',
    'chiba':    'https://www.inageseasidepark.com/',
}

PARK_SOURCE = {
    'tokyo':    'yoyogi',
    'kanagawa': 'yokohama',
    'saitama':  'saitama',
    'chiba':    'chiba_park',
}

def scrape_park_site(region):
    events = []
    url = PARK_SITES.get(region)
    source = PARK_SOURCE.get(region, region)
    if not url:
        return events
    soup = fetch_html(url)
    if not soup:
        return events
    for section in soup.select('h3, h2'):
        header = section.get_text()
        if not re.search(r'\d{4}年\d{1,2}月|\d{4}年', header):
            continue
        ul = section.find_next_sibling('ul')
        if not ul:
            continue
        for li in ul.select('li'):
            try:
                link_el = li.select_one('a[href]')
                if not link_el:
                    continue
                title = link_el.get_text(strip=True)
                if len(title) < 3:
                    continue
                event_url = link_el['href']
                if not event_url.startswith('http'):
                    event_url = urljoin(url, event_url)
                text = li.get_text()
                d1, d2 = parse_date_range(text)
                events.append({
                    'title': title,
                    'date': d1,
                    'endDate': d2,
                    'place': get_region_place(region),
                    'url': event_url,
                    'source': source,
                    'cost': 'free' if '無料' in text else 'paid',
                    'ages': ['toddler', 'preschool', 'elementary', 'family'],
                    'cats': guess_cats(title),
                    'area': 'other',
                    'desc': '',
                })
            except:
                pass
    site_name = url.split('//')[1].split('/')[0]
    print(f"  {site_name}: {len(events)}件")
    return events

def get_region_place(region):
    places = {
        'tokyo': '東京都',
        'kanagawa': '神奈川県',
        'saitama': '埼玉県',
        'chiba': '千葉県',
    }
    return places.get(region, '不明')

# ─── いこーよ（RSS・地域別） ───
def scrape_ikoyo(pref_id, region):
    events = []
    url = f"https://iko-yo.net/events.rss?prefecture_ids[]={pref_id}"
    soup = fetch_rss(url)
    if not soup:
        return events
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link = item.find('link').get_text(strip=True) if item.find('link') else ''
            desc_raw = item.find('description')
            desc = BeautifulSoup(desc_raw.get_text(), 'html.parser').get_text(strip=True) if desc_raw else ''
            pub_date = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ''
            if not title or len(title) < 3:
                continue
            text = title + ' ' + desc
            d1, d2 = parse_date_range(desc + ' ' + pub_date)
            events.append({
                'title': title,
                'date': d1,
                'endDate': d2,
                'place': extract_place(desc) or get_region_place(region),
                'url': link,
                'source': 'ikoy',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title),
                'area': 'other',
                'desc': desc[:120],
            })
        except:
            pass
    print(f"  いこーよ({region}): {len(events)}件")
    return events

# ─── キッズイベント（RSS） ───
def scrape_kids_rss(region):
    events = []
    url = "https://www.kids-event.jp/feed/"
    soup = fetch_rss(url)
    if not soup:
        return events
    region_keywords = {
        'kanagawa': r'神奈川|横浜|川崎|相模|藤沢|鎌倉|小田原|湘南',
        'saitama': r'埼玉|さいたま|川口|所沢|川越|熊谷|大宮',
        'chiba': r'千葉|船橋|松戸|柏|市川|浦安|幕張|成田',
    }
    kw = region_keywords.get(region, '')
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link = item.find('link').get_text(strip=True) if item.find('link') else ''
            desc_raw = item.find('description')
            desc = BeautifulSoup(desc_raw.get_text(), 'html.parser').get_text(strip=True) if desc_raw else ''
            if not title:
                continue
            text = title + ' ' + desc
            if kw and not re.search(kw, text):
                continue
            d1, d2 = parse_date_range(desc)
            events.append({
                'title': title,
                'date': d1,
                'endDate': d2,
                'place': extract_place(desc) or get_region_place(region),
                'url': link,
                'source': 'kids',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title),
                'area': 'other',
                'desc': desc[:120],
            })
        except:
            pass
    print(f"  キッズイベント({region}): {len(events)}件")
    return events

# ─── 神奈川専用：横浜市公式 ───
def scrape_yokohama():
    events = []
    url = "https://www.city.yokohama.lg.jp/kurashi/kosodate-kyoiku/kosodateshien/event/"
    soup = fetch_html(url)
    if not soup:
        return events
    items = soup.select('article, li[class*="event"], [class*="event-item"]')[:20]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, [class*="title"]')
            date_el = item.select_one('[class*="date"], time')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1, 'endDate': d2,
                'place': '横浜市',
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'yokohama_city',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': 'other',
                'desc': '',
            })
        except:
            pass
    print(f"  横浜市公式: {len(events)}件")
    return events

# ─── 埼玉専用：さいたま市公式 ───
def scrape_saitama_city():
    events = []
    url = "https://www.city.saitama.lg.jp/001/011/003/index.html"
    soup = fetch_html(url)
    if not soup:
        return events
    items = soup.select('article, li, [class*="event"]')[:20]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, a, [class*="title"]')
            date_el = item.select_one('[class*="date"], time')
            link_el = item.select_one('a[href]')
            if not title_el or len(title_el.get_text(strip=True)) < 4:
                continue
            text = item.get_text()
            if not re.search(r'子ども|こども|キッズ|ファミリー|親子|幼児|小学', text):
                continue
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1, 'endDate': d2,
                'place': 'さいたま市',
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'saitama_city',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': 'other',
                'desc': '',
            })
        except:
            pass
    print(f"  さいたま市公式: {len(events)}件")
    return events

# ─── 千葉専用：千葉市公式 ───
def scrape_chiba_city():
    events = []
    url = "https://www.city.chiba.jp/kodomomirai/kodomomirai/event.html"
    soup = fetch_html(url)
    if not soup:
        return events
    items = soup.select('article, li, [class*="event"], table tr')[:20]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, a, [class*="title"]')
            date_el = item.select_one('[class*="date"], time, td')
            link_el = item.select_one('a[href]')
            if not title_el or len(title_el.get_text(strip=True)) < 4:
                continue
            text = item.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1, 'endDate': d2,
                'place': '千葉市',
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'chiba_city',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': 'other',
                'desc': '',
            })
        except:
            pass
    print(f"  千葉市公式: {len(events)}件")
    return events

# ─── ヘルパー ───
def extract_place(text):
    for p in [r'会場[：:]\s*([^\n。、]{2,20})', r'場所[：:]\s*([^\n。、]{2,20})']:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return ''

def parse_date_range(text):
    now = datetime.date.today()
    year = now.year
    dates = []
    for m in re.finditer(r'(\d{4})[年](\d{1,2})[月](\d{1,2})', text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.append(f"{y}-{mo:02d}-{d:02d}")
    if not dates:
        for m in re.finditer(r'(\d{1,2})[月](\d{1,2})[日]', text):
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                yr = year if mo >= now.month else year + 1
                dates.append(f"{yr}-{mo:02d}-{d:02d}")
    if not dates:
        d = now.strftime('%Y-%m-%d')
        return d, d
    if len(dates) == 1:
        return dates[0], dates[0]
    return dates[0], dates[-1]

def guess_ages(text):
    ages = []
    if re.search(r'0歳|1歳|乳児|赤ちゃん', text): ages.append('baby')
    if re.search(r'2歳|3歳|よちよち', text): ages.append('toddler')
    if re.search(r'4歳|5歳|6歳|年長|幼児|保育園|幼稚園', text): ages.append('preschool')
    if re.search(r'小学|小1|小2|小3|小4|小5|小6|児童', text): ages.append('elementary')
    if re.search(r'家族|ファミリー|親子', text) or not ages: ages.append('family')
    return list(dict.fromkeys(ages)) or ['family']

def guess_cats(title):
    cats = []
    if re.search(r'コンサート|音楽|クラシック|演奏|オーケストラ|吹奏楽', title): cats.append('concert')
    if re.search(r'博物館|美術館|展示|展覧|ミュージアム|科学館', title): cats.append('museum')
    if re.search(r'工作|体験|ワークショップ|プログラミング|料理|実験', title): cats.append('workshop')
    if re.search(r'動物|自然|公園|植物|虫|花|水族館|昆虫', title): cats.append('nature')
    if re.search(r'スポーツ|運動|水泳|サッカー|体操', title): cats.append('sport')
    if re.search(r'ミュージカル|劇|舞台|公演|落語', title): cats.append('stage')
    if re.search(r'まつり|フェスタ|フェア|フェス|お祭り|花見|桜|マルシェ', title): cats.append('festival')
    return cats or ['festival']

def dedup(events):
    seen = set()
    result = []
    for e in events:
        key = re.sub(r'\s', '', e['title'])[:20]
        if key not in seen:
            seen.add(key)
            result.append(e)
    return result

def is_valid(e):
    garbage = ['期間を選択する','カテゴリを選択する','対象年齢','開催エリア']
    if e['title'] in garbage or len(e['title']) < 4: return False
    try:
        d = datetime.datetime.strptime(e['date'], '%Y-%m-%d')
        return True
    except:
        return False

# ─── 地域別スクレイプ ───
def scrape_region(region, pref_id):
    print(f"\n{'='*40}")
    print(f"地域: {region} (都道府県ID: {pref_id})")
    print(f"{'='*40}")
    all_events = []

    scrapers = [
        lambda: scrape_park_site(region),
        lambda: scrape_ikoyo(pref_id, region),
        lambda: scrape_kids_rss(region),
    ]

    if region == 'kanagawa':
        scrapers.append(scrape_yokohama)
    elif region == 'saitama':
        scrapers.append(scrape_saitama_city)
    elif region == 'chiba':
        scrapers.append(scrape_chiba_city)

    for scraper in scrapers:
        try:
            evs = scraper()
            all_events.extend(evs)
            time.sleep(2.0)
        except Exception as e:
            print(f"  エラー: {e}")

    all_events = [e for e in all_events if is_valid(e)]
    all_events = dedup(all_events)
    for i, e in enumerate(all_events):
        e['id'] = i + 1
        if not e.get('endDate'): e['endDate'] = e['date']
        if not e.get('desc'): e['desc'] = ''

    output_file = os.path.join(BASE_DIR, REGION_CONFIG[region]['output'])
    output = {
        'updated': datetime.datetime.now().isoformat(),
        'region': region,
        'count': len(all_events),
        'events': all_events,
    }
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✓ {region}: {len(all_events)}件 → {REGION_CONFIG[region]['output']}")
    return len(all_events)

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    regions_to_run = REGION_CONFIG if target == 'all' else {target: REGION_CONFIG[target]}

    for region, config in regions_to_run.items():
        scrape_region(region, config['pref_id'])
        time.sleep(3.0)

    print("\n全地域のスクレイピング完了！")

if __name__ == '__main__':
    main()
