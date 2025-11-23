# app.py (نسخه oEmbed - روشی که تلگرام استفاده می‌کند)

import json
import subprocess
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (oEmbed Strategy) is LIVE!'

# --- متد 1: Instagram oEmbed API (رسمی و با کیفیت) ---
def get_oembed_data(insta_url):
    print(f"Checking oEmbed API for: {insta_url}")
    try:
        # آدرس API رسمی اینستاگرام
        api_url = f"https://www.instagram.com/api/v1/oembed/?url={insta_url}"
        
        # هدر ساده (نیازی به جعل پیچیده نیست)
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        # اگر پاسخ موفق بود
        if response.status_code == 200:
            data = response.json()
            
            # دریافت لینک عکس با کیفیت (thumbnail_url در oEmbed معمولا کیفیت اصلی است)
            image_url = data.get('thumbnail_url')
            title = data.get('title', 'Instagram Photo')
            
            # نکته مهم: oEmbed نوع مدیا را دقیق نمی‌گوید، اما اگر thumbnail_url باشد، یعنی عکس کاور داریم.
            # ما فعلا فرض می‌کنیم عکس است. اگر yt-dlp پایین‌تر تشخیص داد ویدیو است، اصلاح می‌شود.
            
            if image_url:
                print("oEmbed Success! Found High-Res Image.")
                return {
                    'type': 'photo', # پیش‌فرض عکس
                    'download_url': image_url,
                    'thumbnail_url': image_url,
                    'description': title
                }
    except Exception as e:
        print(f"oEmbed Failed: {e}")
        
    return None

# --- متد 2: yt-dlp (برای ویدیو و آلبوم) ---
def run_ytdlp(insta_url):
    print(f"Running yt-dlp for Video check...")
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

    # 1. ابتدا yt-dlp را چک می‌کنیم تا بفهمیم "ویدیو/آلبوم" است یا نه؟
    # (چون oEmbed برای ویدیو، لینک دانلود فیلم را نمی‌دهد، فقط کاور می‌دهد)
    video_info = run_ytdlp(insta_url)
    
    is_video_or_album = False
    
    if video_info:
        # اگر آلبوم بود
        if video_info.get('_type') == 'playlist':
            is_video_or_album = True
            entries = video_info.get('entries', [])
            title = video_info.get('title', 'Instagram Album')
            for i, item in enumerate(entries):
                if not item: continue
                m_type = 'video' if (item.get('is_video') or item.get('ext') == 'mp4') else 'photo'
                dl_link = item.get('url')
                
                # تلاش برای لینک بهتر در آلبوم
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

        # اگر ویدیو/ریلز تکی بود
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

    # 2. اگر ویدیو یا آلبوم نبود (یعنی عکس تکی است یا yt-dlp شکست خورد)
    # ==> از روش oEmbed استفاده کن (اینجاست که عکس با کیفیت میاد)
    if not is_video_or_album:
        print("Not a video/album. Trying oEmbed for High-Res Photo...")
        oembed_data = get_oembed_data(insta_url)
        
        if oembed_data:
            media_items.append(oembed_data)
            title = oembed_data['description']
        
        # فال‌بک نهایی: اگر oEmbed هم نشد ولی yt-dlp یه چیزی داشت (حتی بی کیفیت)
        elif video_info and not media_items:
             dl_link = video_info.get('url')
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
