import json
import subprocess
import requests
import html
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- متد 1: Instagram oEmbed API (برای عکس‌های تکی) ---
def get_oembed_data(insta_url):
    """
    استفاده از API رسمی oEmbed اینستاگرام برای گرفتن لینک عکس با کیفیت بالا (High-Res).
    """
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

# --- متد 2: yt-dlp (برای تعیین نوع محتوا و گرفتن ویدیو) ---
def run_ytdlp(insta_url, timeout=30): # ⭐️ تایم‌اوت کاهش یافت ⭐️
    """
    اجرای yt-dlp برای تعیین نوع محتوا (ویدیو یا آلبوم).
    """
    print(f"Running yt-dlp for: {insta_url}")
    
    # User-Agent موبایل برای افزایش شانس دریافت JSON
    fake_ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1'
    
    command = [
        'yt-dlp',
        '--dump-single-json',
        '--skip-download',
        '--user-agent', fake_ua,
        insta_url
    ]
    
    try:
        # ⭐️ تایم‌اوت ۳۰ ثانیه برای اجرای سریع ⭐️
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
    return 'Instagram API (Fast Cover Version) is LIVE!'

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    if not insta_url:
        return jsonify({'success': False, 'message': 'لینک نامعتبر است.'}), 400

    media_items = []
    title = "Instagram_Media"

    # 1. اجرای yt-dlp برای تعیین نوع پست (ویدیو یا آلبوم)
    # اگر نتواند نوع پست را در 30 ثانیه بفهمد، به مرحله 2 می‌رویم (که احتمالاً عکس تکی است)
    video_info = run_ytdlp(insta_url, timeout=30)
    
    if video_info:
        title = video_info.get('title', 'Instagram Media')
        
        # ⭐️ تغییر حیاتی: پردازش آلبوم ⭐️
        if video_info.get('_type') == 'playlist':
            print("Detected ALBUM. Extracting only the first slide/cover...")
            
            # اگر آلبوم باشد، فقط لینک اولین اسلاید را می‌گیریم و با oEmbed پردازش می‌کنیم
            if video_info.get('entries') and video_info['entries'][0]:
                first_item = video_info['entries'][0]
                first_url = first_item.get('webpage_url', insta_url)
                
                # بررسی می‌کنیم اگر ویدیو بود، لینک ویدیو را مستقیماً از yt-dlp بگیریم
                if first_item.get('is_video') or first_item.get('ext') == 'mp4':
                    print("First slide is VIDEO. Extracting video URL...")
                    dl_link = first_item.get('url')
                    if dl_link:
                        media_items.append({
                            'type': 'video', 
                            'download_url': dl_link,
                            'thumbnail_url': first_item.get('thumbnail'), 
                            'description': title
                        })
                    
                # اگر عکس بود، لینک oEmbed را برای کیفیت بالا صدا می‌زنیم
                else:
                    print("First slide is PHOTO. Using oEmbed for cover quality.")
                    oembed_data = get_oembed_data(first_url)
                    if oembed_data:
                        media_items.append(oembed_data)
                    else:
                        # فال‌بک: اگر oEmbed هم نشد، لینک کم کیفیت yt-dlp را می‌دهیم
                         dl_link = first_item.get('url')
                         if dl_link:
                              media_items.append({
                                'type': 'photo', 
                                'download_url': dl_link,
                                'thumbnail_url': first_item.get('thumbnail'), 
                                'description': title
                              })
            
        # پردازش ویدیو/ریلز تکی
        elif video_info.get('is_video') or video_info.get('ext') == 'mp4':
            print("Detected single VIDEO. Extracting video URL...")
            dl_link = video_info.get('url')
            if video_info.get('requested_formats'):
                for fmt in video_info['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        dl_link = fmt['url']; break
            
            if dl_link:
                media_items.append({
                    'type': 'video', 
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'), 
                    'description': title
                })
        
        # اگر yt-dlp چیز دیگری برگرداند (عکس تکی با لینک کم کیفیت)
        elif not media_items:
             dl_link = video_info.get('url')
             if dl_link:
                 media_items.append({
                     'type': 'photo', 'download_url': dl_link,
                     'thumbnail_url': video_info.get('thumbnail'), 'description': title
                 })


    # 2. اگر yt-dlp نتوانست پاسخ دهد یا محتوای تکی است (عکس تکی)
    # ==> استفاده از روش oEmbed
    if not media_items:
        print("yt-dlp failed or assumed single item. Trying oEmbed for High-Res Photo...")
        oembed_data = get_oembed_data(insta_url)
        
        if oembed_data:
            media_items.append(oembed_data)
            title = oembed_data['description']
        
    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد. احتمالا پست خصوصی است یا لینک نامعتبر.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)

