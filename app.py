# app.py (نسخه نهایی هیبریدی: yt-dlp + HTML Fallback)

import json
import subprocess
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (Hybrid Mode) is LIVE!'

# --- روش اول: yt-dlp (عالی برای ویدیو/ریلز) ---
def try_ytdlp(insta_url):
    fake_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    try:
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            '--user-agent', fake_user_agent,
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True) # check=False تا دستی مدیریت کنیم
        
        if result.returncode != 0:
            return None # شکست خورد

        return json.loads(result.stdout)
    except Exception:
        return None

# --- روش دوم: HTML Scraping (عالی برای عکس‌های تک) ---
def fallback_html_scraping(insta_url):
    print("yt-dlp failed. Trying HTML scraping fallback...")
    try:
        # استفاده از هدرهای شبیه به ربات‌های تلگرام/فیسبوک که معمولاً بلاک نمی‌شوند
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        
        response = requests.get(insta_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        html_content = response.text
        
        media_items = []
        
        # 1. جستجو برای og:video (اگر ویدیو باشد)
        video_match = re.search(r'<meta property="og:video" content="([^"]+)"', html_content)
        # 2. جستجو برای og:image (برای عکس یا کاور ویدیو)
        image_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        # 3. جستجو برای توضیحات (Caption)
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        
        description = desc_match.group(1) if desc_match else "Instagram Media"
        
        # اولویت با ویدیو است
        if video_match:
            media_items.append({
                'type': 'video',
                'download_url': video_match.group(1).replace('&amp;', '&'),
                'thumbnail_url': image_match.group(1).replace('&amp;', '&') if image_match else None,
                'description': description
            })
        # اگر ویدیو نبود ولی عکس بود
        elif image_match:
            media_items.append({
                'type': 'photo',
                'download_url': image_match.group(1).replace('&amp;', '&'),
                'thumbnail_url': image_match.group(1).replace('&amp;', '&'),
                'description': description
            })
            
        return media_items
        
    except Exception as e:
        print(f"Fallback failed: {e}")
        return None


@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    # مرحله 1: تلاش با yt-dlp (برای ریلز و آلبوم‌ها بهترین است)
    video_info = try_ytdlp(insta_url)
    
    if video_info:
        # ... (منطق پردازش yt-dlp که قبلاً داشتیم) ...
        media_items = []
        title = video_info.get('title', 'Instagram_Media')

        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for item in entries:
                if not item: continue
                is_video = item.get('is_video') or item.get('ext') == 'mp4'
                m_type = 'video' if is_video else 'photo'
                dl_link = item.get('url')
                # منطق یافتن بهترین لینک
                if item.get('requested_formats'):
                     target_ext = 'mp4' if m_type == 'video' else 'jpg'
                     for fmt in item['requested_formats']:
                        if fmt.get('url') and fmt.get('ext') == target_ext:
                            dl_link = fmt['url']; break
                
                if dl_link:
                    media_items.append({
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"آلبوم ({m_type})"
                    })
        else:
            # پست تکی
            is_video = video_info.get('is_video') or video_info.get('ext') == 'mp4'
            m_type = 'video' if is_video else 'photo'
            dl_link = video_info.get('url')
            
            if video_info.get('requested_formats'):
                target_ext = 'mp4' if m_type == 'video' else 'jpg'
                formats = video_info['requested_formats']
                if m_type == 'photo': formats = reversed(formats) # بهترین کیفیت عکس
                for fmt in formats:
                    if fmt.get('url') and fmt.get('ext') == target_ext:
                        dl_link = fmt['url']; break
            
            # اگر yt-dlp لینک عکس نداد (مشکل رایج)، null برمی‌گرداند
            if not dl_link and m_type == 'photo':
                # اگر yt-dlp لینک نداد، پاس بده به مرحله 2
                pass 
            elif dl_link:
                media_items.append({
                    'type': m_type, 'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 'description': title
                })

        # اگر yt-dlp موفق شد و آیتم پیدا کرد، برگردان
        if media_items:
            return jsonify({'success': True, 'title': title, 'media_items': media_items})
        
        # اگر yt-dlp اجرا شد اما آیتمی پیدا نکرد (مثلاً لینک عکس خالی بود)، برو به مرحله 2
    
    # مرحله 2: تلاش با Fallback HTML Scraping (برای عکس‌هایی که yt-dlp رد می‌کند)
    fallback_items = fallback_html_scraping(insta_url)
    
    if fallback_items:
        return jsonify({
            'success': True,
            'title': fallback_items[0]['description'],
            'media_items': fallback_items
        })

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (پست خصوصی یا محدودیت سرور).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
