# app.py (نسخه نهایی ۳ لایه: yt-dlp -> Instaloader -> HTML)

import json
import subprocess
import re
import requests
import instaloader
from flask import Flask, request, jsonify

app = Flask(__name__)

# تنظیم Instaloader (بدون لاگین)
L = instaloader.Instaloader(
    quiet=True,
    download_videos=False,
    download_pictures=False,
    save_metadata=False,
    max_connection_attempts=1
)

@app.route('/')
def home():
    return 'Instagram Ultimate API is LIVE!'

def get_shortcode(url):
    match = re.search(r'/(?:p|tv|reel)/([^/]+)', url)
    if match: return match.group(1)
    return None

# ---------------------------------------------------------
# لایه ۱: yt-dlp (برای ریلز و ویدیو عالی است)
# ---------------------------------------------------------
def run_ytdlp(insta_url):
    print("LAYER 1: Running yt-dlp...")
    try:
        # استفاده از User-Agent موبایل سامسونگ (کمتر بلاک می‌شود)
        mobile_ua = 'Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36'
        
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist', 
            '--skip-download',
            '--user-agent', mobile_ua,
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0: return None
        return json.loads(result.stdout)
    except:
        return None

# ---------------------------------------------------------
# لایه ۲: Instaloader (برای آلبوم‌ها عالی است)
# ---------------------------------------------------------
def run_instaloader(shortcode):
    print("LAYER 2: Running Instaloader...")
    items = []
    try:
        post = instaloader.Post.from_shortcode(L, shortcode)
        
        # اگر آلبوم است
        if post.mediacount > 1:
            print("Instaloader detected ALBUM.")
            # حلقه روی اسلایدها (Sidecars)
            for i, node in enumerate(post.get_sidecar_nodes()):
                media_type = 'video' if node.is_video else 'photo'
                dl_url = node.video_url if node.is_video else node.display_url
                
                if dl_url:
                    items.append({
                        'type': media_type,
                        'download_url': dl_url,
                        'thumbnail_url': post.url, # تامبنیل کلی
                        'description': f"اسلاید {i+1} ({media_type})"
                    })
        # اگر پست تکی است (که yt-dlp نتوانسته بگیرد)
        else:
            media_type = 'video' if post.is_video else 'photo'
            dl_url = post.video_url if post.is_video else post.display_url
            if dl_url:
                items.append({
                    'type': media_type,
                    'download_url': dl_url,
                    'thumbnail_url': post.url,
                    'description': 'Instagram Media (Via Instaloader)'
                })
                
        return items
    except Exception as e:
        print(f"Instaloader Failed: {e}")
        return None

# ---------------------------------------------------------
# لایه ۳: HTML Scraping (آخرین امید - عکس با کیفیت)
# ---------------------------------------------------------
def run_html_scraper(insta_url):
    print("LAYER 3: Running HTML Scraper...")
    try:
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html',
        }
        response = requests.get(insta_url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        html = response.text
        img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        
        if img_match:
            clean_url = img_match.group(1).replace('&amp;', '&')
            return [{
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': desc_match.group(1) if desc_match else "Instagram Photo"
            }]
    except:
        pass
    return None


@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    shortcode = get_shortcode(insta_url)
    media_items = []
    title = "Instagram_Media"

    # --- استراتژی آبشاری ---

    # 1. تلاش با yt-dlp
    video_info = run_ytdlp(insta_url)
    if video_info:
        # اگر yt-dlp موفق شد دیتا بگیرد
        if video_info.get('_type') == 'playlist': # آلبوم تشخیص داد
            entries = video_info.get('entries', [])
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url')
                # پیدا کردن لینک بهتر
                if item.get('requested_formats'):
                     target_ext = 'mp4' if m_type == 'video' else 'jpg'
                     formats = item['requested_formats']
                     if m_type == 'photo': formats = reversed(formats)
                     for fmt in formats:
                        if fmt.get('url') and fmt.get('ext') == target_ext:
                            dl_link = fmt['url']; break
                
                if dl_link:
                    media_items.append({
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"اسلاید {i+1} ({m_type})"
                    })
        else:
            # پست تکی (ویدیو یا عکس)
            is_vid = video_info.get('is_video') or video_info.get('ext') == 'mp4'
            m_type = 'video' if is_vid else 'photo'
            dl_link = video_info.get('url')
            
            if video_info.get('requested_formats'):
                target_ext = 'mp4' if m_type == 'video' else 'jpg'
                formats = video_info['requested_formats']
                if m_type == 'photo': formats = reversed(formats)
                for fmt in formats:
                    if fmt.get('url') and fmt.get('ext') == target_ext:
                        dl_link = fmt['url']; break
            
            # فیلتر کردن لینک های خالی yt-dlp (برای عکس‌ها گاهی خالی میفرستد)
            if dl_link:
                media_items.append({
                    'type': m_type, 'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 'description': video_info.get('title', title)
                })

    # 2. اگر yt-dlp شکست خورد (یا لیست خالی بود)، برو سراغ Instaloader
    if not media_items and shortcode:
        loader_items = run_instaloader(shortcode)
        if loader_items:
            media_items = loader_items
            title = "Instagram Album (Instaloader)"

    # 3. اگر Instaloader هم شکست خورد، برو سراغ HTML Scraper (عکس اول)
    if not media_items:
        html_items = run_html_scraper(insta_url)
        if html_items:
            media_items = html_items
            title = "Instagram Photo (HTML)"

    # نتیجه نهایی
    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
