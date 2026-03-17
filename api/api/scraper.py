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
            place_el = item.select_one('[cl
