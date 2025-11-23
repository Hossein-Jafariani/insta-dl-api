# app.py (نسخه نهایی: اولویت مطلق با متد تلگرام برای عکس‌ها)

import json
import subprocess
import re
import requests
import html
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (Telegram Method Priority) is LIVE!'

# --- متد 1: استخراج HTML (دقیقاً مثل تلگرام) ---
# این متد همیشه عکس باکیفیت (1080p) را می‌دهد
def scrape_html_like_telegram(insta_url):
    print(f"Running HTML Scraper (Telegram Method) for: {insta_url}")
    try:
        # هدر دقیق فیس‌بوک/تلگرام برای فریب دادن اینستاگرام
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        }
        
        # درخواست مستقیم به صفحه HTML
        response = requests.get(insta_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        html_content = response.text
        
        # 1. آیا ویدیو است؟ (og:video)
        video_match = re.search(r'<meta property="og:video" content="([^"]+)"', html_content)
        if video_match:
            print("Detected VIDEO via HTML. Switching to yt-dlp logic...")
            return "IS_VIDEO" # علامت می‌دهیم که این ویدیو است و باید با yt-dlp دانلود شود

        # 2. آیا عکس است؟ (og:image)
        image_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        
        if image_match:
            # تمیز کردن لینک (تبدیل &amp; به &)
            clean_url = html.unescape(image_match.group(1))
            
            print("Detected PHOTO via HTML. Returning High-Res URL.")
            return [{
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': desc_match.group(1) if desc_match else "Instagram Photo (High-Res)"
            }]
            
    except Exception as e:
        print(f"HTML Scraper Failed: {e}")
    
    return None

# --- متد 2: yt-dlp (برای ویدیو، ریلز و آلبوم‌ها) ---
def run_ytdlp(insta_url):
    print(f"Running yt-dlp for Video/Album: {insta_url}")
    try:
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
        if result.returncode != 0: return None
        return json.loads(result.stdout)
    except:
        return None

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    media_items = []
    title = "Instagram_Media"

    # **********************************************************
    # قدم اول: اجرای متد تلگرام (HTML)
    # هدف: اگر عکس تکی است، همینجا با کیفیت اصلی بگیریم و تمام.
    # **********************************************************
    html_result = scrape_html_like_telegram(insta_url)

    # حالت A: اگر خروجی لیست بود، یعنی عکس تکی پیدا شد -> برگرداندن نتیجه
    if isinstance(html_result, list):
        return jsonify({
            'success': True, 
            'title': html_result[0]['description'], 
            'media_items': html_result
        })

    # حالت B: اگر خروجی "IS_VIDEO" بود یا کلاً None بود -> برو سراغ yt-dlp
    # (چون برای ویدیو و آلبوم، yt-dlp بهتر عمل می‌کند)
    
    # **********************************************************
    # قدم دوم: اجرای yt-dlp (برای ویدیو و آلبوم)
    # **********************************************************
    video_info = run_ytdlp(insta_url)
    
    if video_info:
        title = video_info.get('title', 'Instagram_Media')
        
        # پردازش آلبوم (Slideshow)
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url')
                
                # تلاش برای پیدا کردن بهترین لینک در آلبوم
                if item.get('requested_formats'):
                     target_ext = 'mp4' if m_type == 'video' else 'jpg'
                     formats = item['requested_formats']
                     if m_type == 'photo': formats = reversed(formats) # بزرگترین عکس
                     for fmt in formats:
                        if fmt.get('url') and fmt.get('ext') == target_ext:
                            dl_link = fmt['url']; break
                
                if dl_link:
                    media_items.append({
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"اسلاید {i+1} ({m_type})"
                    })

        # پردازش ویدیو/ریلز تکی
        else:
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

            if dl_link:
                media_items.append({
                    'type': m_type, 'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 'description': title
                })

    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (404).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
