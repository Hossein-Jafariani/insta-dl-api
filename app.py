# app.py (نسخه شکارچی کیفیت بالا - High Resolution Finder)

import json
import subprocess
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (High-Res Edition) is LIVE!'

# --- تابع هوشمند برای پیدا کردن بهترین کیفیت عکس ---
def find_best_quality_url(item_info):
    """
    این تابع لیست thumbnails را بررسی می‌کند و لینکی که
    بزرگترین width (عرض) را دارد برمی‌گرداند.
    """
    # 1. اولویت اول: بررسی لیست thumbnails
    thumbnails = item_info.get('thumbnails', [])
    if thumbnails:
        # مرتب‌سازی بر اساس عرض (width) از کوچک به بزرگ
        # گاهی width نیست و preference هست، ما سعی میکنیم ایمن عمل کنیم
        sorted_thumbs = sorted(thumbnails, key=lambda x: x.get('width', 0) if x.get('width') else 0)
        
        # آخرین آیتم، بزرگترین سایز است
        best_thumb = sorted_thumbs[-1]
        
        # چک میکنیم لینک معتبر باشه
        if best_thumb.get('url'):
            print(f"Found High-Res in thumbnails: Width {best_thumb.get('width')}")
            return best_thumb.get('url')

    # 2. اولویت دوم: بررسی requested_formats (اگر عکس اونجا بود)
    formats = item_info.get('requested_formats', [])
    if formats:
        # برای عکس، فرمت‌های غیر mp4 رو جدا میکنیم
        photo_formats = [f for f in formats if f.get('ext') != 'mp4']
        if photo_formats:
            # آخرین فرمت معمولا بهترینه
            return photo_formats[-1].get('url')

    # 3. اولویت سوم: اگر هیچکدوم نبود، همون url معمولی رو بده
    return item_info.get('url')


# --- اجرای yt-dlp ---
def run_ytdlp(insta_url):
    print(f"Running yt-dlp for: {insta_url}")
    try:
        # User-Agent دسکتاپ برای گرفتن کیفیت بالا
        fake_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist', 
            '--skip-download',
            '--user-agent', fake_ua,
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0: 
            print(f"yt-dlp error: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"Exception: {e}")
        return None

# --- فال‌بک HTML (روش تلگرام) ---
def scrape_html_high_res(insta_url):
    print("Fallback: Scraping HTML for og:image...")
    try:
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html'
        }
        response = requests.get(insta_url, headers=headers, timeout=10)
        if response.status_code == 200:
            html = response.text
            # استخراج og:image (همیشه بزرگترین سایز است)
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

    media_items = []
    title = "Instagram_Media"

    # 1. تلاش با yt-dlp (با منطق جدید پیدا کردن عکس بزرگ)
    video_info = run_ytdlp(insta_url)
    
    if video_info:
        title = video_info.get('title', 'Instagram_Media')
        
        # الف) اگر آلبوم (Playlist) باشد
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for i, item in enumerate(entries):
                if not item: continue
                
                is_video = item.get('is_video') or item.get('ext') == 'mp4'
                m_type = 'video' if is_video else 'photo'
                
                # *** اینجا از تابع جدید استفاده می‌کنیم ***
                if m_type == 'photo':
                    dl_link = find_best_quality_url(item)
                else:
                    dl_link = item.get('url') # برای ویدیو معمولا url اصلی خوبه
                
                if dl_link:
                    media_items.append({
                        'type': m_type,
                        'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"اسلاید {i+1} ({m_type})"
                    })

        # ب) اگر پست تکی باشد
        else:
            is_video = video_info.get('is_video') or video_info.get('ext') == 'mp4'
            m_type = 'video' if is_video else 'photo'
            
            # *** اینجا از تابع جدید استفاده می‌کنیم ***
            if m_type == 'photo':
                dl_link = find_best_quality_url(video_info)
            else:
                dl_link = video_info.get('url')

            if dl_link:
                media_items.append({
                    'type': m_type,
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'),
                    'description': title
                })

    # 2. اگر yt-dlp شکست خورد یا عکس بی‌کیفیت داد، روش HTML (تلگرام) وارد میشود
    if not media_items:
        fallback_data = scrape_html_high_res(insta_url)
        if fallback_data:
            media_items = fallback_data
            title = "Instagram Photo (High-Res)"

    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (404).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
