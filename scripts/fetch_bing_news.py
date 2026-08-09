#!/usr/bin/env python3
"""
Fetch news from Bing News Search API or fallback to free DuckDuckGo HTML scraping.

Usage:
  export BING_API_KEY="..."
  python3 scripts/fetch_bing_news.py

If no API key is provided, the script will use DuckDuckGo instead of Bing.
"""
import os
import sys
import json
import hashlib
import requests
from urllib.parse import parse_qs, unquote, urlparse, urljoin
from pathlib import Path
from PIL import Image

try:
    from bs4 import BeautifulSoup
except ImportError:
    print('Missing beautifulsoup4. Install it with: python3 -m pip install beautifulsoup4')
    sys.exit(1)

API_KEY = os.environ.get('BING_API_KEY') or os.environ.get('BING_NEWS_KEY')
USE_FREE_SEARCH = API_KEY is None
BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / 'data'
IMAGES_DIR = BASE / 'assets' / 'images'
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    'video game', 'game release', 'Ubisoft', 'EA', 'Activision', 'Nintendo', 'Sony', 'Microsoft Gaming',
    'CD Projekt', 'Square Enix', 'Epic Games', 'Fortnite', 'Elden Ring', 'Call of Duty',
    'IGN Brasil', 'Adrenaline', 'Critical Hits', 'Flor Games', 'IGN Brasil news', 'Crítica de jogos Brasil'
]

BING_ENDPOINT = 'https://api.bing.microsoft.com/v7.0/news/search'
DUCK_ENDPOINT = 'https://html.duckduckgo.com/html/'
USER_AGENT = 'Mozilla/5.0 (compatible; Pixelwire/1.0; +https://example.com)'


def fetch_for_query(q, count=5):
    if API_KEY:
        return fetch_from_bing(q, count)
    return fetch_from_duckduckgo(q, count)


def fetch_from_bing(q, count=5):
    headers = {'Ocp-Apim-Subscription-Key': API_KEY}
    params = {'q': q, 'mkt': 'en-US', 'count': count, 'freshness': 'Day'}
    r = requests.get(BING_ENDPOINT, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get('value', [])


def extract_duckduckgo_url(href):
    parsed = urlparse(href)
    if parsed.netloc.endswith('duckduckgo.com'):
        params = parse_qs(parsed.query)
        uddg = params.get('uddg')
        if uddg:
            return unquote(uddg[0])
    return href


def extract_image_from_page(url):
    try:
        headers = {'User-Agent': USER_AGENT}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        meta = soup.select_one('meta[property="og:image"], meta[name="og:image"], meta[name="twitter:image"], meta[name="twitter:image:src"]')
        if meta and meta.get('content'):
            return urljoin(url, meta['content'])
        icon = soup.find('link', rel=lambda value: value and 'icon' in value.lower())
        if icon and icon.get('href'):
            return urljoin(url, icon['href'])
    except Exception:
        return None
    return None


def fetch_from_duckduckgo(q, count=5):
    data = {'q': f'{q} news', 's': '0', 'dc': '0'}
    headers = {'User-Agent': USER_AGENT}
    r = requests.post(DUCK_ENDPOINT, data=data, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, 'html.parser')
    results = []

    for item in soup.select('div.result')[:count]:
        anchor = item.select_one('a.result__a')
        if not anchor:
            continue
        url = extract_duckduckgo_url(anchor.get('href', ''))
        title = anchor.get_text(strip=True)
        snippet = item.select_one('.result__snippet') or item.select_one('.result__extras__url')
        desc = snippet.get_text(strip=True) if snippet else ''
        image_url = None
        img_tag = item.select_one('img.result__img')
        if img_tag and img_tag.get('src'):
            image_url = img_tag['src']
        if not image_url and url:
            image_url = extract_image_from_page(url)
        results.append({
            'url': url,
            'name': title,
            'description': desc,
            'datePublished': None,
            'provider': [{'name': 'DuckDuckGo'}],
            'image': {'thumbnail': {'contentUrl': image_url}} if image_url else None,
        })

    if not results:
        for anchor in soup.select('a.result__a')[:count]:
            url = extract_duckduckgo_url(anchor.get('href', ''))
            title = anchor.get_text(strip=True)
            results.append({
                'url': url,
                'name': title,
                'description': '',
                'datePublished': None,
                'provider': [{'name': 'DuckDuckGo'}],
            })

    return results


def download_image(url, dest):
    try:
        r = requests.get(url, stream=True, timeout=15)
        r.raise_for_status()
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return True
    except Exception:
        return False


def make_thumb(src_path, dest_path, size=(400,240)):
    try:
        im = Image.open(src_path)
        im.thumbnail(size, Image.LANCZOS)
        im.convert('RGB').save(dest_path, 'JPEG', quality=85)
        return True
    except Exception:
        return False


def url_hash(u):
    return hashlib.sha1(u.encode('utf-8')).hexdigest()[:12]


def normalize_item(item):
    url = item.get('url') or item.get('webSearchUrl') or item.get('image', {}).get('url')
    title = item.get('name')
    desc = item.get('description')
    date = item.get('datePublished')
    providers = item.get('provider') or []
    source = ''
    if isinstance(providers, list) and providers:
        source = providers[0].get('name', '')
    elif isinstance(providers, dict):
        source = providers.get('name', '')
    image_url = None
    if 'image' in item and item['image']:
        t = item['image'].get('thumbnail') or item['image']
        image_url = t.get('contentUrl') if isinstance(t, dict) else None
    if not image_url and url:
        image_url = extract_image_from_page(url)
    id_ = url_hash(url or title or desc)
    image_name = None
    thumb_name = None
    if image_url:
        parsed = urlparse(image_url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        image_name = f'{id_}{ext}'
        image_path = IMAGES_DIR / image_name
        if download_image(image_url, image_path):
            thumb_name = f'{id_}_thumb.jpg'
            make_thumb(image_path, IMAGES_DIR / thumb_name, size=(600,360))
        else:
            image_name = None
    return {
        'id': id_,
        'titulo': title,
        'resumo': desc,
        'data': date,
        'fonte': source,
        'url': url,
        'imagem': f'assets/images/{image_name}' if image_name else None,
        'thumb': f'assets/images/{thumb_name}' if thumb_name else None,
        'fetched_by': 'IA (Bing News API)' if API_KEY else 'IA (DuckDuckGo free search)'
    }


def main():
    if USE_FREE_SEARCH:
        print('Bing API key not found. Using free DuckDuckGo fallback search.')
    seen = set()
    out = []
    for q in QUERIES:
        try:
            items = fetch_for_query(q, count=5)
        except Exception as e:
            print('Error fetching', q, e)
            continue
        for it in items:
            url = it.get('url') or it.get('webSearchUrl')
            if not url or url in seen:
                continue
            seen.add(url)
            norm = normalize_item(it)
            out.append(norm)
    out = sorted(out, key=lambda x: x.get('data') or '', reverse=True)
    with open(DATA_DIR / 'news.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Wrote', len(out), 'items to data/news.json')

if __name__ == '__main__':
    main()
