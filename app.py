# app.py (نسخه پشتیبانی کامل از آلبوم‌ها + ریلز)

import json
import subprocess
import re
import requests
import html
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (Album Support) is LIVE!'

def get_shortcode(url):
    match = re.search(r'/(?:p|tv|reel)/([^/]+)', url)
    if match:
        return match.group(1)
    return None

# --- روش Embed (فقط برای عکس‌های تکی یا کاور در صورت شکست) ---
def scrape_embed(shortcode):
    try:
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(embed_url, headers=headers, timeout=10)
        if response.status_code != 200: return None
        
        img_match = re.search(r'class="EmbeddedMediaImage" src="([^"]+)"', response.text)
        if img_match:
            clean_url = html.unescape(img_match.group(1))
            return [{
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': 'Instagram Photo (Embed Fallback)'
            }]
    except:
        pass
    return None

# --- روش اصلی: yt-dlp ---
def run_ytdlp(insta_url):
    try:
        # استفاده از User-Agent دسکتاپ برای ثبات بیشتر
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist', # نکته: این فلگ را نگه می‌داریم اما yt-dlp خودش آلبوم را تشخیص می‌دهد
            '--skip-download',
            '--user-agent', user_agent,
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

    # 1. اولویت اول: تلاش با yt-dlp (چون فقط این می‌تواند آلبوم کامل را ببیند)
    video_info = run_ytdlp(insta_url)
    
    if video_info:
        title = video_info.get('title', 'Instagram_Media')
        
        # الف) حالت آلبوم (Playlist) - اینجا تمام اسلایدها استخراج می‌شوند
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for i, item in enumerate(entries):
                if not item: continue
                
                # تشخیص نوع هر اسلاید (ممکن است مخلوط عکس و فیلم باشد)
                is_vid = item.get('is_video') or item.get('ext') == 'mp4'
                m_type = 'video' if is_vid else 'photo'
                dl_link = item.get('url')
                
                # تلاش برای لینک بهتر
                if item.get('requested_formats'):
                     target_ext = 'mp4' if m_type == 'video' else 'jpg'
                     formats = item['requested_formats']
                     if m_type == 'photo': formats = reversed(formats)
                     for fmt in formats:
                        if fmt.get('url') and fmt.get('ext') == target_ext:
                            dl_link = fmt['url']; break
                
                if dl_link:
                    media_items.append({
                        'type': m_type,
                        'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"اسلاید {i+1} ({m_type})"
                    })

        # ب) حالت پست تکی
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
                    'type': m_type,
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'),
                    'description': title
                })

    # 2. اولویت دوم: اگر yt-dlp کلاً شکست خورد (مثلاً لیست خالی بود)، از Embed استفاده کن
    # (این فقط عکس اول را برمی‌گرداند اما بهتر از هیچ است)
    if not media_items:
        shortcode = get_shortcode(insta_url)
        if shortcode:
            embed_data = scrape_embed(shortcode)
            if embed_data:
                media_items = embed_data
                title = "Instagram Photo (Fallback)"

    if media_items:
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
