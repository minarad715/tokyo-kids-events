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

# ─── いこーよ Playwright版 ───
def scrape_ikoyo_playwright(pref_id, region):
    events = []
    try:
        from playwright.sync_api import sync_playwright
        url = f"https://iko-yo.net/events?prefecture_ids[]={pref_id}&per=50&sort=new"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)
            html = page.content()
            browser.close()
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find event cards
        cards = []
        for sel in ['.p-event-card', '[class*="event-card"]', '[class*="eventCard"]', 
                    'article[class*="event"]', '.event-list-item']:
            cards = soup.select(sel)
            if len(cards) > 3:
                break
        
        if not cards:
            # Fallback: find event links
            cards = soup.select('a[href*="/events/"]')
        
        for card in cards[:30]:
            try:
                title_el = card.select_one('h2, h3, h4, [class*="title"], [class*="name"]')
                date_el = card.select_one('[class*="date"], [class*="period"], time, [class*="schedule"]')
                place_el = card.select_one('[class*="place"], [class*="venue"], [class*="location"], [class*="area"]')
                link_el = card.select_one('a[href]') if card.name != 'a' else card
                
                if not title_el and card.name == 'a':
                    title_el = card
                if not title_el or len(title_el.get_text(strip=True)) < 3:
                    continue
                
                text = card.get_text()
                d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
                
                today = datetime.date.today().strftime('%Y-%m-%d')
                if not d1 or d1 < today:
                    d1 = today
                if not d2 or d2 < d1:
                    d2 = d1
                
                href = link_el.get('href', '') if link_el else ''
                event_url = urljoin('https://iko-yo.net', href) if href else url
                
                events.append({
                    'title': title_el.get_text(strip=True),
                    'date': d1,
                    'endDate': d2,
                    'place': place_el.get_text(strip=True) if place_el else get_region_place(region),
                    'url': event_url,
                    'source': 'ikoy',
                    'cost': 'free' if '無料' in text else 'paid',
                    'ages': guess_ages(text),
                    'cats': guess_cats(title_el.get_text(strip=True)),
                    'area': 'other',
                    'desc': '',
                })
            except:
                pass
        
        print(f"  いこーよPlaywright({region}): {len(events)}件")
    
    except Exception as e:
        print(f"  Playwrightエラー({region}): {e}")
        # フォールバック：RSS
        events = scrape_ikoyo_rss(pref_id, region)
    
    return events

# ─── いこーよ RSS版（フォールバック） ───
def scrape_ikoyo_rss(pref_id, region):
    events = []
    url = f"https://iko-yo.net/events.rss?prefecture_ids[]={pref_id}"
    soup = fetch_rss(url)
    if not soup:
        return events
    today = datetime.date.today().strftime('%Y-%m-%d')
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link_tag = item.find('link')
            link = str(link_tag.next_sibling).strip() if link_tag and link_tag.next_sibling else ''
            if not link.startswith('http'):
                link = f"https://iko-yo.net/events?prefecture_ids[]={pref_id}"
            desc_raw = item.find('description')
            desc = BeautifulSoup(desc_raw.get_text(), 'html.parser').get_text(strip=True) if desc_raw else ''
            if not title or len(title) < 3:
                continue
            text = title + ' ' + desc
            d1, d2 = parse_date_range(desc)
            if not d1 or d1 < today:
                d1 = today
            if not d2 or d2 < d1:
                d2 = d1
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
    print(f"  いこーよRSS({region}): {len(events)}件")
    return events

# ─── 代々木公園系サイト ───
PARK_SITES = {
    'tokyo':    ('https://www.yoyogikoen.info/', 'yoyogi'),
    'kanagawa': ('https://www.yokohamaevent.info/', 'yokohama'),
    'saitama':  ('https://www.saitama-shintoshin.com/', 'saitama'),
    'chiba':    ('https://www.inageseasidepark.com/', 'chiba_park'),
}

def scrape_park_site(region):
    events = []
    if region not in PARK_SITES:
        return events
    url, source = PARK_SITES[region]
    soup = fetch_html(url)
    if not soup:
        return events
    for section in soup.select('h3, h2'):
        header = section.get_text()
        if not re.search(r'\d{4}', header):
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
    domain = url.split('//')[1].split('/')[0]
    print(f"  {domain}: {len(events)}件")
    return events

# ─── コンサートスクエア ───
def scrape_concert_sq():
    events = []
    url = "https://www.concertsquare.jp/concert/search/ticketFree"
    soup = fetch_html(url)
    if not soup:
        return events
    items = []
    for sel in ['li[class*="concert"]', 'article', '[class*="item"]', 'li']:
        items = [i for i in soup.select(sel) if i.select_one('a') and len(i.get_text()) > 20]
        if items:
            break
    for item in items[:20]:
        try:
            title_el = item.select_one('h3, h2, h4, [class*="title"], [class*="name"]')
            date_el = item.select_one('[class*="date"], time, [class*="day"]')
            hall_el = item.select_one('[class*="hall"], [class*="venue"], [class*="place"]')
            link_el = item.select_one('a[href]')
            if not title_el or len(title_el.get_text(strip=True)) < 3:
                continue
            place = hall_el.get_text(strip=True) if hall_el else '東京都内'
            combined = title_el.get_text() + place
            if not re.search(r'東京|渋谷|新宿|上野|銀座|池袋|六本木|立川|紀尾井|サントリー', combined):
                continue
            date_text = date_el.get_text() if date_el else ''
            m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_text)
            if m:
                d1 = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                d2 = d1
            else:
                d1, d2 = parse_date_range(date_text)
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1, 'endDate': d2,
                'place': place,
                'url': urljoin(url, link_el['href']) if link_el else url,
                'source': 'concert',
                'cost': 'free',
                'ages': ['preschool', 'elementary', 'family'],
                'cats': ['concert'],
                'area': guess_area(place),
                'desc': '',
            })
        except:
            pass
    print(f"  コンサートスクエア: {len(events)}件")
    return events

# ─── キッズイベント RSS ───
def scrape_kids_rss(region):
    events = []
    url = "https://www.kids-event.jp/feed/"
    soup = fetch_rss(url)
    if not soup:
        return events
    kw_map = {
        'kanagawa': r'神奈川|横浜|川崎|相模|藤沢|鎌倉|小田原|湘南',
        'saitama':  r'埼玉|さいたま|川口|所沢|川越|熊谷|大宮',
        'chiba':    r'千葉|船橋|松戸|柏|市川|浦安|幕張|成田',
    }
    kw = kw_map.get(region, '')
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link = item.find('link').get_text(strip=True) if item.find('link') else ''
            desc_raw = item.find('description')
            desc = BeautifulSoup(desc_raw.get_text(), 'html.parser').get_text(strip=True) if desc_raw else ''
            if not title or len(title) < 3:
                continue
            text = title + ' ' + desc
            if kw and not re.search(kw, text):
                continue
            d1, d2 = parse_date_range(desc)
            events.append({
                'title': title, 'date': d1, 'endDate': d2,
                'place': extract_place(desc) or get_region_place(region),
                'url': link, 'source': 'kids',
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

# ─── 東京都公式 ───
def scrape_tokyo_official():
    events = []
    urls = [
        'https://tokyo-kodomo-hp.metro.tokyo.lg.jp/event/',
        'https://kodomo-smile.metro.tokyo.lg.jp/events',
    ]
    for url in urls:
        soup = fetch_html(url)
        if not soup:
            continue
        for item in soup.select('article, li, [class*="event"]')[:20]:
            try:
                title_el = item.select_one('h2,h3,h4,[class*="title"]')
                date_el = item.select_one('[class*="date"],time')
                link_el = item.select_one('a[href]')
                if not title_el or len(title_el.get_text(strip=True)) < 5:
                    continue
                text = item.get_text()
                d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
                events.append({
                    'title': title_el.get_text(strip=True),
                    'date': d1, 'endDate': d2,
                    'place': '東京都',
                    'url': urljoin(url, link_el['href']) if link_el else url,
                    'source': 'tokyo',
                    'cost': 'free' if '無料' in text else 'paid',
                    'ages': guess_ages(text),
                    'cats': guess_cats(title_el.get_text(strip=True)),
                    'area': 'other', 'desc': '',
                })
            except:
                pass
    print(f"  東京都公式: {len(events)}件")
    return events

# ─── ヘルパー ───
def get_region_place(region):
    return {'tokyo':'東京都','kanagawa':'神奈川県','saitama':'埼玉県','chiba':'千葉県'}.get(region,'不明')

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
    return (dates[0], dates[0]) if len(dates) == 1 else (dates[0], dates[-1])

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

def guess_area(place):
    mapping = {
        'shibuya': ['渋谷','代々木','原宿','恵比寿'],
        'shinjuku': ['新宿','中野','杉並'],
        'ueno': ['上野','浅草','台東','文京'],
        'odaiba': ['お台場','有明','豊洲','江東','墨田'],
        'tachikawa': ['立川','八王子','多摩'],
    }
    for area, kws in mapping.items():
        if any(k in place for k in kws):
            return area
    return 'other'

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
    if e['title'] in garbage or len(e['title']) < 4:
        return False
    try:
        datetime.datetime.strptime(e['date'], '%Y-%m-%d')
        return True
    except:
        return False

# ─── 地域別スクレイプ ───
def scrape_region(region, pref_id):
    print(f"\n{'='*40}\n地域: {region}\n{'='*40}")
    all_events = []

    if region == 'tokyo':
        scrapers = [
            lambda: scrape_park_site('tokyo'),
            lambda: scrape_ikoyo_playwright(pref_id, region),
            scrape_tokyo_official,
            lambda: scrape_kids_rss('tokyo'),
            scrape_concert_sq,
        ]
    else:
        scrapers = [
            lambda r=region: scrape_park_site(r),
            lambda p=pref_id, r=region: scrape_ikoyo_playwright(p, r),
            lambda r=region: scrape_kids_rss(r),
        ]

    for scraper in scrapers:
        try:
            evs = scraper()
            all_events.extend(evs if evs else [])
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
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    output = {
        'updated': datetime.datetime.now().isoformat(),
        'region': region,
        'count': len(all_events),
        'events': all_events,
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✓ {region}: {len(all_events)}件 → {REGION_CONFIG[region]['output']}")

def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if target == 'all':
        for region, cfg in REGION_CONFIG.items():
            scrape_region(region, cfg['pref_id'])
            time.sleep(3.0)
    else:
        if target in REGION_CONFIG:
            scrape_region(target, REGION_CONFIG[target]['pref_id'])
        else:
            print(f"Unknown region: {target}")
    print("\n全スクレイピング完了！")

if __name__ == '__main__':
    main()
