import json
import subprocess
import requests
import html
import re
import os # برای لاگین اینستاگرام

from flask import Flask, request, jsonify

app = Flask(__name__)

# --- ابزارهای کمکی ---

def is_instagram_url(url):
    """بررسی می‌کند آیا لینک مربوط به اینستاگرام است یا خیر."""
    return "instagram.com" in url.lower() or "instagr.am" in url.lower()


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

# --- متد 2: yt-dlp (همه سایت‌ها) ---
def run_ytdlp(input_url, timeout=60): # ⭐️ تایم‌اوت افزایش یافت به ۶۰ ثانیه ⭐️
    """
    اجرای yt-dlp برای همه انواع محتوا (اینستاگرام، یوتیوب، تیک‌تاک، فیس‌بوک).
    """
    
    IG_USERNAME = os.environ.get('igdlll')
    IG_PASSWORD = os.environ.get('Igdlll3456')

    print(f"Running yt-dlp for: {input_url}")
    
    fake_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
    
    command = [
        'yt-dlp',
        '--dump-single-json',
        '--skip-download',
        '--no-playlist', # ⭐️ برای ویدیوهای تکی یوتیوب/تیک‌تاک این پرچم لازم نیست، اما برای سرعت بهتر است
        '--user-agent', fake_ua,
        input_url
    ]
    
    if IG_USERNAME and IG_PASSWORD and is_instagram_url(input_url):
        print("Using provided Instagram credentials for login...")
        command.extend(['--username', IG_USERNAME, '--password', IG_PASSWORD])
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout) 
        
        if result.returncode != 0: 
            print(f"yt-dlp FAILED with code {result.returncode}")
            return None
            
        return json.loads(result.stdout)
        
    except subprocess.TimeoutExpired:
        print(f"yt-dlp TIMED OUT after {timeout} seconds.")
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
    input_url = request.args.get('url')
    if not input_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    media_items = []
    title = "Media"
    
    is_insta = is_instagram_url(input_url)

    # 1. اجرای yt-dlp برای گرفتن داده‌های خام
    video_info = run_ytdlp(input_url, timeout=60) # ⭐️ استفاده از تایم‌اوت ۶۰ ثانیه ⭐️
    
    if video_info:
        title = video_info.get('title', 'Media')
        
        # ⭐️ پردازش محتوای ویدیو (برای یوتیوب، تیک‌تاک، فیس‌بوک و اینستا-ویدیو) ⭐️
        
        # الف) اگر محتوا آلبوم یا پلی‌لیست بود (فقط اولین آیتم را می‌خواهیم)
        if video_info.get('_type') == 'playlist' and video_info.get('entries'):
            # فقط اولین آیتم (اسلاید/ویدیو) را برمی‌داریم (درخواست قبلی شما)
            first_item = video_info['entries'][0]
            m_type = 'video' if (first_item.get('is_video') or first_item.get('ext') == 'mp4') else 'photo'
            dl_link = first_item.get('url')
            
            # اگر اینستاگرام بود و عکس، از oEmbed برای کاور با کیفیت استفاده می‌کنیم
            if is_insta and m_type == 'photo':
                oembed_data = get_oembed_data(first_item.get('webpage_url', input_url))
                if oembed_data:
                    media_items.append(oembed_data)
                
            # در غیر این صورت (ویدیو یا عکس غیر اینستاگرام) لینک yt-dlp را می‌دهیم
            elif dl_link:
                media_items.append({
                    'type': m_type, 
                    'download_url': dl_link,
                    'thumbnail_url': first_item.get('thumbnail'), 
                    'description': first_item.get('title', title)
                })

        # ب) اگر محتوای تکی بود (یوتیوب شورت/ویدیو، تیک‌تاک، فیس‌بوک، عکس یا ویدیو اینستاگرام)
        else:
            m_type = 'video' if (video_info.get('is_video') or video_info.get('ext') == 'mp4') else 'photo'
            dl_link = video_info.get('url')
            
            # اگر اینستاگرام و عکس تکی بود، اولویت با oEmbed است
            if is_insta and m_type == 'photo':
                oembed_data = get_oembed_data(input_url)
                if oembed_data:
                    media_items.append(oembed_data)
                # اگر oEmbed شکست خورد، از لینک کم کیفیت yt-dlp استفاده می‌کنیم
                elif dl_link:
                    media_items.append({
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': video_info.get('thumbnail'), 'description': title
                    })
            
            # برای همه ویدیوها (یوتیوب، تیک‌تاک، فیس‌بوک، اینستا)
            elif m_type == 'video' and dl_link:
                 media_items.append({
                    'type': m_type, 
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 
                    'description': title
                 })
            
            # برای عکس‌های تکی غیر اینستاگرام (مثلاً فیس‌بوک)
            elif m_type == 'photo' and dl_link:
                 media_items.append({
                    'type': m_type, 
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 
                    'description': title
                 })


    # 2. اگر yt-dlp شکست خورد و اینستاگرام بود (فقط یک فال‌بک نهایی برای عکس تکی)
    # این فقط برای اطمینان از پوشش موارد سخت اینستاگرام است
    if is_insta and not media_items:
        print("yt-dlp failed on Insta. Trying oEmbed as last resort...")
        oembed_data = get_oembed_data(input_url)
        
        if oembed_data:
            media_items.append(oembed_data)
            title = oembed_data['description']
        
    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    # اگر تا اینجا هیچ محتوایی پیدا نشد (404)
    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد. احتمالا لینک نامعتبر است یا محتوای غیر قابل دانلود است.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
