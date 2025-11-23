import json
import subprocess
import requests
import html
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

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
    """
    اجرای yt-dlp برای محتوای پیچیده‌تر (آلبوم و ویدیو). 
    *بدون پرچم --no-playlist* برای استخراج کامل آلبوم.
    """
    print(f"Running yt-dlp for: {insta_url}")
    
    # ⭐️ تغییر User-Agent به موبایل برای افزایش شانس دریافت JSON آلبوم ⭐️
    fake_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
    
    command = [
        'yt-dlp',
        '--dump-single-json',
        # ⭐️ اصلاح حیاتی: حذف پرچم --no-playlist برای فعال کردن استخراج آلبوم ⭐️
        '--skip-download',
        '--user-agent', fake_ua,
        insta_url
    ]
    
    try:
        # تایم‌اوت سخاوتمندانه ۱۸۰ ثانیه 
        result = subprocess.run(command, capture_output=True, text=True, timeout=180) 
        
        if result.returncode != 0: 
            print(f"yt-dlp FAILED with code {result.returncode}")
            print(f"yt-dlp STDERR: {result.stderr[:500]}...")
            return None
            
        return json.loads(result.stdout)
        
    except subprocess.TimeoutExpired:
        print("yt-dlp TIMED OUT after 180 seconds.")
        return None
    except Exception as e:
        print(f"Exception during yt-dlp execution: {e}")
        return None

# ----------------------------------------------------------------------
# --- Route اصلی ---
# ----------------------------------------------------------------------

@app.route('/')
def home():
    return 'Instagram API (Final Stable Version) is LIVE!'

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    media_items = []
    title = "Instagram_Media"

    # 1. اجرای yt-dlp برای تعیین نوع پست و گرفتن داده‌های خام
    video_info = run_ytdlp(insta_url)
    
    is_video_or_album = False
    
    if video_info:
        # ⭐️ پردازش آلبوم (Slideshow) ⭐️
        if video_info.get('_type') == 'playlist':
            is_video_or_album = True
            entries = video_info.get('entries', [])
            title = video_info.get('title', 'Instagram Album')
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url')
                
                # --- منطق جستجوی کیفیت بالا برای عکس‌های اسلایدی ---
                if m_type == 'photo':
                    found_high_res = False
                    
                    # 1. اولویت: بررسی Requested Formats
                    if item.get('requested_formats'):
                         formats = item['requested_formats']
                         for fmt in reversed(formats): # معکوس برای گرفتن بزرگترین سایز
                            if fmt.get('url') and fmt.get('ext') == 'jpg':
                                dl_link = fmt['url']
                                found_high_res = True
                                break

                    # 2. فال‌بک: بررسی لیست Thumbnails
                    if not found_high_res:
                        thumbnails = item.get('thumbnails', [])
                        if thumbnails:
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
        
        # فال‌بک برای هر چیز دیگری که yt-dlp برگردانده (به عنوان عکس تکی کم کیفیت)
        elif not media_items:
            dl_link = video_info.get('url')
            if dl_link:
                 media_items.append({
                     'type': 'photo', 'download_url': dl_link,
                     'thumbnail_url': video_info.get('thumbnail'), 'description': title
                 })
                 is_video_or_album = True 


    # 2. اگر نه آلبوم بود و نه ویدیو (عکس تکی است) ==> استفاده از روش oEmbed
    if not is_video_or_album:
        print("Not a video/album. Trying oEmbed for High-Res Photo...")
        oembed_data = get_oembed_data(insta_url)
        
        if oembed_data:
            media_items.append(oembed_data)
            title = oembed_data['description']
        
    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    # اگر تا اینجا هیچ محتوایی پیدا نشد (404)
    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد. احتمالا پست خصوصی است یا لینک نامعتبر.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
