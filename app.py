# app.py (نسخه نهایی با تضمین کیفیت عکس اصلی)

import json
import subprocess
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram High-Quality API is LIVE!'

# تابع تشخیص لینک بی‌کیفیت (Thumbnail)
def is_low_quality_url(url):
    if not url: return True
    # اینستاگرام معمولاً سایز را در URL می‌نویسد: s150x150, p320x320, s640x640
    # ما می‌خواهیم اگر این الگوها بود، بگوییم کیفیت پایین است.
    # الگوی Regex برای پیدا کردن /s123x123/ یا /p123x123/
    pattern = r'/[sp]\d+x\d+/'
    if re.search(pattern, url):
        return True
    return False

# --- روش اول: yt-dlp ---
def try_ytdlp(insta_url):
    # User-Agent واقعی دسکتاپ
    fake_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    try:
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            '--user-agent', fake_user_agent,
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            return None 

        return json.loads(result.stdout)
    except Exception:
        return None

# --- روش دوم: HTML Scraping (برای دریافت og:image با کیفیت بالا) ---
def get_high_res_from_html(insta_url):
    print("Attempting to fetch High-Res image via HTML Scraping...")
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        response = requests.get(insta_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            return None
            
        html_content = response.text
        
        # استخراج og:image (همیشه کیفیت بالا است)
        image_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        
        # استخراج توضیحات
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        description = desc_match.group(1) if desc_match else "Instagram Photo"

        if image_match:
            # تبدیل &amp; به & برای درست شدن لینک
            clean_url = image_match.group(1).replace('&amp;', '&')
            return {
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': description,
                'type': 'photo'
            }
            
        return None
        
    except Exception as e:
        print(f"HTML Scraping failed: {e}")
        return None


@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    # 1. ابتدا yt-dlp را اجرا می‌کنیم (برای ساختار کلی، ریلز و آلبوم‌ها عالی است)
    video_info = try_ytdlp(insta_url)
    
    media_items = []
    title = "Instagram_Media"

    # اگر yt-dlp موفق شد
    if video_info:
        title = video_info.get('title', 'Instagram_Media')

        # الف) اگر آلبوم (Playlist) باشد
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for item in entries:
                if not item: continue
                is_video = item.get('is_video') or item.get('ext') == 'mp4'
                m_type = 'video' if is_video else 'photo'
                dl_link = item.get('url')
                
                # تلاش برای پیدا کردن لینک بهتر
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
                        'description': f"آلبوم ({m_type})"
                    })

        # ب) اگر پست تکی باشد
        else:
            is_video = video_info.get('is_video') or video_info.get('ext') == 'mp4'
            m_type = 'video' if is_video else 'photo'
            dl_link = video_info.get('url')
            
            # تلاش برای لینک بهتر
            if video_info.get('requested_formats'):
                target_ext = 'mp4' if m_type == 'video' else 'jpg'
                formats = video_info['requested_formats']
                if m_type == 'photo': formats = reversed(formats)
                for fmt in formats:
                    if fmt.get('url') and fmt.get('ext') == target_ext:
                        dl_link = fmt['url']; break

            # ***** اصلاح کیفیت عکس *****
            # اگر عکس بود و لینک پیدا شده کیفیت پایین به نظر می‌رسید (یا خالی بود)
            if m_type == 'photo' and (not dl_link or is_low_quality_url(dl_link)):
                print("yt-dlp returned low quality photo. Fetching from HTML...")
                hq_data = get_high_res_from_html(insta_url)
                if hq_data:
                    dl_link = hq_data['download_url']
                    # تامبنیل هم همان کیفیت بالا باشد
                    video_info['thumbnail'] = hq_data['download_url'] 

            if dl_link:
                media_items.append({
                    'type': m_type, 'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 'description': title
                })

    # 2. اگر yt-dlp کلاً شکست خورد (مثلاً برای برخی عکس‌های خاص)، مستقیماً HTML را چک کن
    if not media_items:
        hq_data = get_high_res_from_html(insta_url)
        if hq_data:
            media_items.append(hq_data)
            title = hq_data['description']

    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (پست خصوصی یا محدودیت سرور).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
