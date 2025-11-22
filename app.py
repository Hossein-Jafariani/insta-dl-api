# app.py (نسخه هوشمند: آلبوم با yt-dlp، عکس با HTML Scraper)

import json
import subprocess
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram Hybrid API is LIVE!'

# --- روش 1: اسکرپ HTML (روش تلگرام/فیسبوک) ---
# این روش برای تک‌عکس‌ها عالی است و بلاک نمی‌شود
def scrape_html_metadata(insta_url):
    print(f"Running HTML Scraper for: {insta_url}")
    try:
        # این User-Agent کلید موفقیت است: اینستاگرام فکر می‌کند ما ربات تلگرام هستیم
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        response = requests.get(insta_url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        html = response.text
        
        # استخراج عکس اصلی (og:image) - همیشه کیفیت بالاست
        img_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        # استخراج توضیحات
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        description = desc_match.group(1) if desc_match else "Instagram Media"

        if img_match:
            clean_url = img_match.group(1).replace('&amp;', '&')
            return [{
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': description
            }]
            
    except Exception as e:
        print(f"Scrape Error: {e}")
    
    return None

# --- روش 2: yt-dlp (قدرتمند برای آلبوم و ویدیو) ---
def run_ytdlp(insta_url):
    print(f"Running yt-dlp for: {insta_url}")
    try:
        fake_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist', # ما خودمان دستی پلی‌لیست را پردازش می‌کنیم
            '--skip-download',
            '--user-agent', fake_ua,
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0: 
            print(f"yt-dlp failed: {result.stderr}")
            return None
        return json.loads(result.stdout)
    except Exception as e:
        print(f"yt-dlp Exception: {e}")
        return None

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    media_items = []
    title = "Instagram_Media"

    # استراتژی هوشمند:
    # 1. اول yt-dlp را اجرا کن تا ببینیم آیا آلبوم (Playlist) یا ویدیو است؟
    video_info = run_ytdlp(insta_url)

    is_album_or_video = False
    
    if video_info:
        # الف) اگر آلبوم است: حتماً از yt-dlp استفاده کن (چون HTML Scraper فقط عکس اول را می‌بیند)
        if video_info.get('_type') == 'playlist':
            print("Detected Type: ALBUM (Playlist)")
            is_album_or_video = True
            title = video_info.get('title', 'Instagram Album')
            entries = video_info.get('entries', [])
            
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url')
                
                # تلاش برای کیفیت بهتر
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

        # ب) اگر پست تکی است اما ویدیو/ریلز است
        elif video_info.get('is_video') or video_info.get('ext') == 'mp4':
            print("Detected Type: SINGLE VIDEO/REEL")
            is_album_or_video = True
            title = video_info.get('title', 'Instagram Reel')
            dl_link = video_info.get('url')
            
            if video_info.get('requested_formats'):
                for fmt in video_info['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        dl_link = fmt['url']; break
            
            if dl_link:
                media_items.append({
                    'type': 'video', 'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 'description': title
                })

    # 2. تصمیم‌گیری نهایی:
    # اگر yt-dlp چیزی پیدا نکرد (شکست خورد) 
    # یا اگر yt-dlp پیدا کرد اما "تک عکس" بود (که معمولاً کیفیت پایین است)
    # ==> برو سراغ HTML Scraping
    
    if not is_album_or_video:
        print("yt-dlp failed OR it is a Single Photo. Falling back to HTML Scraping...")
        scraped_data = scrape_html_metadata(insta_url)
        
        if scraped_data:
            print("HTML Scraping SUCCESS!")
            return jsonify({'success': True, 'title': 'Instagram Photo', 'media_items': scraped_data})
        
        # اگر اسکرپر هم شکست خورد اما yt-dlp یک عکس (شاید کیفیت پایین) داشت، همان را بده
        elif video_info and not media_items: # اگر yt-dlp دیتا داشت اما ما بالا ردش کردیم
             # اینجا کد مربوط به استخراج عکس از yt-dlp را به عنوان آخرین چاره می‌گذاریم
             dl_link = video_info.get('url')
             if video_info.get('requested_formats'):
                 for fmt in reversed(video_info['requested_formats']):
                     if fmt.get('url') and fmt.get('ext') != 'mp4':
                         dl_link = fmt['url']; break
             if dl_link:
                 media_items.append({
                     'type': 'photo', 'download_url': dl_link,
                     'thumbnail_url': video_info.get('thumbnail'), 'description': title
                 })

    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (404).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
