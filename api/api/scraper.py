#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json, re, time, datetime, os
from urllib.parse import urljoin

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; TokyoKidsBot/1.0)'}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'public', 'events.json')

def fetch(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        r.encoding = r.apparent_encoding
        return BeautifulSoup(r.text, 'html.parser')
    except Exception as e:
        print(f"  取得失敗 {url}: {e}")
        return None

def scrape_ikoyo():
    events = []
    url = "https://iko-yo.net/events?area[]=13&per=30"
    soup = fetch(url)
    if not soup:
        return events
    cards = []
    for sel in ['.p-event-card', '.event-card', '[class*="eventCard"]']:
        cards = soup.select(sel)
        if cards:
            break
    for card in cards[:20]:
        try:
            title_el = card.select_one('h2, h3, [class*="title"]')
            date_el = card.select_one('[class*="date"], [class*="period"], time')
            place_el = card.select_one('[class*="place"], [class*="venue"]')
            link_el = card.select_one('a[href]')
            if not title_el:
                continue
            text = card.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place_el.get_text(strip=True) if place_el else '東京',
                'url': urljoin('https://iko-yo.net', link_el['href']) if link_el else url,
                'source': 'ikoy',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place_el.get_text(strip=True) if place_el else ''),
                'desc': '',
            })
        except:
            pass
    print(f"  いこーよ: {len(events)}件")
    return events

def scrape_tokyo():
    events = []
    url = "https://tokyo-kodomo-hp.metro.tokyo.lg.jp/event/"
    soup = fetch(url)
    if not soup:
        return events
    items = soup.select('article, .event-list__item, li[class*="event"]')[:20]
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
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
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

def scrape_concert():
    events = []
    url = "https://www.concertsquare.jp/concert/search/ticketFree"
    soup = fetch(url)
    if not soup:
        return events
    items = soup.select('li[class*="concert"], [class*="concert-list"] li')[:15]
    for item in items:
        try:
            title_el = item.select_one('h3, h2, [class*="name"], [class*="title"]')
            date_el = item.select_one('[class*="date"], time')
            hall_el = item.select_one('[class*="hall"], [class*="venue"], [class*="place"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
            place = hall_el.get_text(strip=True) if hall_el else '東京都内'
            combined = title_el.get_text() + place
            if not re.search(r'東京|渋谷|新宿|上野|銀座|池袋|六本木|立川', combined):
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

def scrape_walker():
    events = []
    url = "https://www.walkerplus.com/event_list/ar0313/tag12/"
    soup = fetch(url)
    if not soup:
        return events
    items = soup.select('.event-list__item, [class*="eventCard"]')[:20]
    for item in items:
        try:
            title_el = item.select_one('h3, h2, [class*="title"]')
            date_el = item.select_one('[class*="date"], [class*="period"]')
            place_el = item.select_one('[class*="place"], [class*="venue"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place_el.get_text(strip=True) if place_el else '東京',
                'url': urljoin('https://www.walkerplus.com', link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'walker',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place_el.get_text(strip=True) if place_el else ''),
                'desc': '',
            })
        except:
            pass
    print(f"  ウォーカープラス: {len(events)}件")
    return events

def scrape_kids():
    events = []
    url = "https://www.kids-event.jp/"
    soup = fetch(url)
    if not soup:
        return events
    items = soup.select('article, .event, li.event-item')[:20]
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, [class*="title"]')
            date_el = item.select_one('[class*="date"], time')
            place_el = item.select_one('[class*="place"], [class*="venue"]')
            link_el = item.select_one('a[href]')
            if not title_el:
                continue
            text = item.get_text()
            if not re.search(r'東京|渋谷|新宿|上野|品川|豊島|台東|港区|千代田', text):
                continue
            d1, d2 = parse_date_range(date_el.get_text() if date_el else '')
            events.append({
                'title': title_el.get_text(strip=True),
                'date': d1,
                'endDate': d2,
                'place': place_el.get_text(strip=True) if place_el else '東京',
                'url': urljoin('https://www.kids-event.jp', link_el['href']) if link_el and link_el.get('href') else url,
                'source': 'kids',
                'cost': 'free' if '無料' in text else 'paid',
                'ages': guess_ages(text),
                'cats': guess_cats(title_el.get_text(strip=True)),
                'area': guess_area(place_el.get_text(strip=True) if place_el else ''),
                'desc': '',
            })
        except:
            pass
    print(f"  キッズイベント: {len(events)}件")
    return events

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
    if re.search(r'0歳|1歳|乳児|赤ちゃん', text):
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
    if re.search(r'コンサート|音楽|クラシック|演奏|オーケストラ', title):
        cats.append('concert')
    if re.search(r'博物館|美術館|展示|展覧|ミュージアム|科学館', title):
        cats.append('museum')
    if re.search(r'工作|体験|ワークショップ|プログラミング|料理|実験', title):
        cats.append('workshop')
    if re.search(r'動物|自然|公園|植物|虫|花|水族館|昆虫', title):
        cats.append('nature')
    if re.search(r'スポーツ|運動|水泳|サッカー|体操', title):
        cats.append('sport')
    if re.search(r'ミュージカル|劇|舞台|公演|落語', title):
        cats.append('stage')
    if re.search(r'まつり|フェスタ|フェア|お祭り|花見|桜', title):
        cats.append('festival')
    return cats or ['festival']

def guess_area(place):
    mapping = {
        'ueno': ['上野', '台東', '谷中', '浅草'],
        'shibuya': ['渋谷', '代々木', '恵比寿', '目黒'],
        'shinjuku': ['新宿', '四谷', '大久保'],
        'odaiba': ['お台場', '港区', '品川', '豊洲'],
        'tachikawa': ['立川', '多摩', '八王子', '府中', '国分寺'],
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
def scrape_yoyogi():
    events = []
    url = "https://www.yoyogikoen.info/"
    soup = fetch(url)
    if not soup:
        return events
    # 年月スケジュールのリスト形式を取得
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
def main():
    print("東京こどもイベント スクレイパー開始")
    scrapers = [scrape_ikoyo, scrape_tokyo, scrape_concert, scrape_walker, scrape_kids,scrape_yoyogi,]
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
