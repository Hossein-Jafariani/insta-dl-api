# app.py (نسخه نهایی - تعمیر آلبوم اسلاید)

import json
import subprocess
import requests
import html
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (oEmbed Strategy) is LIVE!'

# --- متد 1: Instagram oEmbed API (برای عکس‌های تکی) ---
def get_oembed_data(insta_url):
    print(f"Checking oEmbed API for: {insta_url}")
    try:
        api_url = f"https://www.instagram.com/api/v1/oembed/?url={insta_url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        }
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            image_url = data.get('thumbnail_url')
            title = data.get('title', 'Instagram Photo')
            
            if image_url:
                print("oEmbed Success! Found High-Res Image.")
                return {
                    'type': 'photo', 
                    'download_url': image_url,
                    'thumbnail_url': image_url,
                    'description': title
                }
    except Exception as e:
        print(f"oEmbed Failed: {e}")
        
    return None

# --- متد 2: yt-dlp (برای ویدیو و آلبوم) ---
def run_ytdlp(insta_url):
    print(f"Running yt-dlp for Video/Album check...")
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

    # 1. بررسی yt-dlp برای تعیین نوع پست (ویدیو، آلبوم یا عکس تکی)
    video_info = run_ytdlp(insta_url)
    
    is_video_or_album = False
    
    if video_info:
        # ************************************************
        # ⭐️ پردازش آلبوم (Slideshow) - منطقه اصلاح شده
        # ************************************************
        if video_info.get('_type') == 'playlist':
            is_video_or_album = True
            entries = video_info.get('entries', [])
            title = video_info.get('title', 'Instagram Album')
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url') # لینک پیش‌فرض (معمولاً کم کیفیت)
                
                # --- منطق جستجوی عمیق برای عکس‌های اسلایدی ---
                if m_type == 'photo':
                    found_high_res = False
                    
                    # 1. اولویت: بررسی Requested Formats
                    if item.get('requested_formats'):
                         formats = item['requested_formats']
                         # معکوس کردن لیست برای یافتن بزرگترین سایز
                         for fmt in reversed(formats): 
                            if fmt.get('url') and fmt.get('ext') == 'jpg':
                                dl_link = fmt['url']
                                found_high_res = True
                                break

                    # 2. فال‌بک: اگر Requested Formats جواب نداد، بررسی لیست Thumbnails
                    if not found_high_res:
                        thumbnails = item.get('thumbnails', [])
                        if thumbnails:
                            # مرتب‌سازی بر اساس عرض (بزرگترین سایز در آخر لیست)
                            sorted_thumbs = sorted(thumbnails, key=lambda x: x.get('width', 0) if x.get('width') else 0)
                            best_thumb = sorted_thumbs[-1]
                            if best_thumb.get('url'):
                                dl_link = best_thumb.get('url')
                # ------------------------------------------------
                
                if dl_link:
                    media_items.append({
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"اسلاید {i+1} ({m_type})"
                    })

        # پردازش ویدیو/ریلز تکی
        elif video_info.get('is_video') or video_info.get('ext') == 'mp4':
            is_video_or_album = True
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
        
        # اگر yt-dlp چیز دیگری غیر از ویدیو/آلبوم پیدا کرد، آن را به عنوان عکس تکی در نظر بگیرد
        elif not is_video_or_album:
            is_video_or_album = True # برای جلوگیری از اجرای oEmbed
            dl_link = video_info.get('url')
            if dl_link:
                 media_items.append({
                     'type': 'photo', 'download_url': dl_link,
                     'thumbnail_url': video_info.get('thumbnail'), 'description': title
                 })


    # 2. اگر ویدیو یا آلبوم نبود (عکس تکی است) ==> از روش oEmbed استفاده کن
    if not is_video_or_album:
        print("Not a video/album. Trying oEmbed for High-Res Photo...")
        oembed_data = get_oembed_data(insta_url)
        
        if oembed_data:
            media_items.append(oembed_data)
            title = oembed_data['description']
        
    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد (404).'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
