#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json, re, time, datetime, os
from urllib.parse import urljoin

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; TokyoKidsBot/1.0)'}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'events.json')

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

# ─────────────────────────────────────────────
# 代々木公園（HTML静的リスト）
# ─────────────────────────────────────────────
def scrape_yoyogi():
    events = []
    url = "https://www.yoyogikoen.info/"
    soup = fetch_html(url)
    if not soup:
        return events
    for section in soup.select('h3'):
        header = section.get_text()
        if not re.search(r'\d{4}年\d{1,2}月', header):
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
                event_url = link_el['href']
                text = li.get_text()
                d1, d2 = parse_date_range(text)
                events.append({
                    'title': title,
                    'date': d1,
                    'endDate': d2,
                    'place': '渋谷区・代々木公園',
                    'url': event_url,
                    'source': 'yoyogi',
                    'cost': 'free' if '無料' in text else 'paid',
                    'ages': ['toddler', 'preschool', 'elementary', 'family'],
                    'cats': guess_cats(title),
                    'area': 'shibuya',
                    'desc': '',
                })
            except:
                pass
    print(f"  代々木公園: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# いこーよ（RSS）
# ─────────────────────────────────────────────
def scrape_ikoyo():
    events = []
    url = "https://iko-yo.net/events.rss?prefecture_ids[]=13"
    soup = fetch_rss(url)
    if not soup:
        return events
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link = item.find('link').get_text(strip=True) if item.find('link') else ''
            desc = item.find('description').get_text(strip=True) if item.find('description') else ''
            pub_date = item.find('pubDate').get_text(strip=True) if item.find('pubDate') else ''
            if not title:
                continue
            d1, d2 = parse_date_range(desc + ' ' + pub_date)
            text = title + ' ' + desc
            # 東京のみ
            if not re.search(r'東京|渋谷|新宿|上野|品川|豊島|台東|港区|千代田|中央|江東|墨田|足立|葛飾|荒川|北区|板橋|練馬|杉並|世田谷|目黒|大田|中野', text):
                continue
            events.append({
                'title': title,
                'date': d1,
                'endDate': d2,
                'place': extract_place(desc),
                'url': link,
                'source': 'ikoy',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title),
                'area': guess_area(desc),
                'desc': desc[:120],
            })
        except:
            pass
    print(f"  いこーよ: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# 東京都公式（HTML）
# ─────────────────────────────────────────────
def scrape_tokyo():
    events = []
    url = "https://tokyo-kodomo-hp.metro.tokyo.lg.jp/event/"
    soup = fetch_html(url)
    if not soup:
        return events
    # Try multiple selectors
    items = (soup.select('article') or
             soup.select('.event-list__item') or
             soup.select('[class*="event"]'))[:25]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, [class*="title"]')
            date_el = item.select_one('[class*="date"], time, [class*="period"]')
            place_el = item.select_one('[class*="place"], [class*="venue"]')
            desc_el = item.select_one('p, [class*="desc"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            place = place_el.get_text(strip=True) if place_el else '東京都'
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place,
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'tokyo',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place),
                'desc': desc_el.get_text(strip=True)[:120] if desc_el else '',
            })
        except:
            pass
    print(f"  東京都公式: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# こどもスマイルムーブメント（東京都）
# ─────────────────────────────────────────────
def scrape_smile():
    events = []
    url = "https://kodomo-smile.metro.tokyo.lg.jp/events"
    soup = fetch_html(url)
    if not soup:
        return events
    items = (soup.select('article') or
             soup.select('[class*="event-card"]') or
             soup.select('[class*="eventCard"]'))[:20]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, [class*="title"]')
            date_el = item.select_one('[class*="date"], time')
            place_el = item.select_one('[class*="place"], [class*="area"], [class*="venue"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            place = place_el.get_text(strip=True) if place_el else '東京都'
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place,
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'tokyo',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place),
                'desc': '',
            })
        except:
            pass
    print(f"  こどもスマイル: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# キッズイベント.jp（RSS）
# ─────────────────────────────────────────────
def scrape_kids():
    events = []
    url = "https://www.kids-event.jp/feed/"
    soup = fetch_rss(url)
    if not soup:
        return events
    for item in soup.select('item')[:30]:
        try:
            title = item.find('title').get_text(strip=True) if item.find('title') else ''
            link = item.find('link').get_text(strip=True) if item.find('link') else ''
            desc_raw = item.find('description')
            desc = BeautifulSoup(desc_raw.get_text(), 'html.parser').get_text(strip=True) if desc_raw else ''
            if not title:
                continue
            text = title + ' ' + desc
            if not re.search(r'東京|渋谷|新宿|上野|品川|豊島|台東|港区|千代田|中央|江東|墨田|お台場|池袋|銀座|六本木', text):
                continue
            d1, d2 = parse_date_range(desc)
            events.append({
                'title': title,
                'date': d1,
                'endDate': d2,
                'place': extract_place(desc),
                'url': link,
                'source': 'kids',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title),
                'area': guess_area(desc),
                'desc': desc[:120],
            })
        except:
            pass
    print(f"  キッズイベント: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# コンサートスクエア（HTML）
# ─────────────────────────────────────────────
def scrape_concert():
    events = []
    url = "https://www.concertsquare.jp/concert/search/ticketFree"
    soup = fetch_html(url)
    if not soup:
        return events
    # Try broad selector
    items = soup.select('li, article, [class*="concert"], [class*="item"]')
    items = [i for i in items if i.find('a') and len(i.get_text()) > 20][:20]
    for item in items:
        try:
            title_el = item.select_one('h3, h2, h4, [class*="title"], [class*="name"]')
            date_el = item.select_one('[class*="date"], time, [class*="day"]')
            hall_el = item.select_one('[class*="hall"], [class*="venue"], [class*="place"]')
            link_el = item.select_one('a[href]')
            if not title_el or len(title_el.get_text(strip=True)) < 3:
                continue
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
            place = hall_el.get_text(strip=True) if hall_el else '東京都内'
            combined = title_el.get_text() + place
            if not re.search(r'東京|渋谷|新宿|上野|銀座|池袋|六本木|恵比寿|表参道|豊洲|お台場|立川|紀尾井|サントリー|オペラシティ|東京文化', combined):
                continue
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place,
                'url': urljoin(url, link_el['href']) if link_el and link_el.get('href') else url,
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

# ─────────────────────────────────────────────
# レッツエンジョイ東京（RSS）
# ─────────────────────────────────────────────
def scrape_enjoytokyo():
    events = []
    url = "https://www.enjoytokyo.jp/event/list/"
    soup = fetch_html(url)
    if not soup:
        return events
    items = (soup.select('[class*="event-list"] li') or
             soup.select('[class*="eventList"] li') or
             soup.select('article') or
             soup.select('[class*="item"]'))[:25]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, [class*="title"]')
            date_el = item.select_one('[class*="date"], time, [class*="period"]')
            place_el = item.select_one('[class*="place"], [class*="venue"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            if not re.search(r'子ども|こども|キッズ|ファミリー|親子|赤ちゃん|幼児|小学', text):
                continue
            d1, d2 = parse_date_range(date_el.get_text() if date_el else text)
            place = place_el.get_text(strip=True) if place_el else '東京都'
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place,
                'url': urljoin('https://www.enjoytokyo.jp', link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'enjoy',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place),
                'desc': '',
            })
        except:
            pass
    print(f"  レッツエンジョイ東京: {len(events)}件")
    return events

# ─────────────────────────────────────────────
# ヘルパー関数
# ─────────────────────────────────────────────
def extract_place(text):
    patterns = [
        r'会場[：:]\s*([^\n。、]{2,20})',
        r'場所[：:]\s*([^\n。、]{2,20})',
        r'開催[：:]\s*([^\n。、]{2,20})',
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return '東京都'

def parse_date_range(text):
    now = datetime.date.today()
    year = now.year
    dates = []
    for m in re.finditer(r'(\d{4})[年](\d{1,2})[月](\d{1,2})', text):
        dates.append(f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}")
    if not dates:
        for m in re.finditer(r'(\d{1,2})[月/](\d{1,2})', text):
            mo, dy = int(m.group(1)), int(m.group(2))
            yr = year if mo >= now.month else year + 1
            dates.append(f"{yr}-{mo:02d}-{dy:02d}")
    if not dates:
        d = now.strftime('%Y-%m-%d')
        return d, d
    if len(dates) == 1:
        return dates[0], dates[0]
    return dates[0], dates[-1]

def guess_ages(text):
    ages = []
    if re.search(r'0歳|1歳|乳児|赤ちゃん|ねんね', text):
        ages.append('baby')
    if re.search(r'2歳|3歳|よちよち', text):
        ages.append('toddler')
    if re.search(r'4歳|5歳|6歳|年長|幼児|保育園|幼稚園', text):
        ages.append('preschool')
    if re.search(r'小学|小1|小2|小3|小4|小5|小6|児童', text):
        ages.append('elementary')
    if re.search(r'家族|ファミリー|親子', text) or not ages:
        ages.append('family')
    return list(dict.fromkeys(ages)) or ['family']

def guess_cats(title):
    cats = []
    if re.search(r'コンサート|音楽|クラシック|演奏|オーケストラ|ピアノ|バイオリン|吹奏楽', title):
        cats.append('concert')
    if re.search(r'博物館|美術館|展示|展覧|ミュージアム|科学館', title):
        cats.append('museum')
    if re.search(r'工作|体験|ワークショップ|プログラミング|料理|実験|ものづくり', title):
        cats.append('workshop')
    if re.search(r'動物|自然|公園|植物|虫|花|水族館|昆虫|森|ネイチャー', title):
        cats.append('nature')
    if re.search(r'スポーツ|運動|水泳|サッカー|体操|マラソン|ランニング', title):
        cats.append('sport')
    if re.search(r'ミュージカル|劇|舞台|公演|落語|人形劇|演劇', title):
        cats.append('stage')
    if re.search(r'まつり|フェスタ|フェア|フェス|お祭り|花見|桜|マルシェ|マーケット', title):
        cats.append('festival')
    return cats or ['festival']

def guess_area(place):
    mapping = {
        'ueno': ['上野', '台東', '谷中', '浅草'],
        'shibuya': ['渋谷', '代々木', '恵比寿', '目黒', '代官山'],
        'shinjuku': ['新宿', '四谷', '大久保', '高田馬場'],
        'odaiba': ['お台場', '港区', '品川', '豊洲', '有明'],
        'tachikawa': ['立川', '多摩', '八王子', '府中', '国分寺', '調布'],
    }
    for area, keywords in mapping.items():
        if any(k in place for k in keywords):
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

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
def main():
    print("東京こどもイベント スクレイパー開始")
    scrapers = [
        scrape_yoyogi,
        scrape_ikoyo,
        scrape_tokyo,
        scrape_smile,
        scrape_kids,
        scrape_concert,
        scrape_enjoytokyo,
    ]
    all_events = []
    for scraper in scrapers:
        try:
            evs = scraper()
            all_events.extend(evs)
            time.sleep(2.0)
        except Exception as e:
            print(f"  エラー {scraper.__name__}: {e}")

    all_events = dedup(all_events)
    for i, e in enumerate(all_events):
        e['id'] = i + 1
        if not e.get('endDate'):
            e['endDate'] = e['date']
        if not e.get('desc'):
            e['desc'] = ''

    output = {
        'updated': datetime.datetime.now().isoformat(),
        'count': len(all_events),
        'events': all_events,
    }
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"完了: {len(all_events)}件保存")

if __name__ == '__main__':
    main()
