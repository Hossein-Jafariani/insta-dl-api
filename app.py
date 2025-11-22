# app.py (نسخه نهایی: Embed Method)

import json
import subprocess
import re
import requests
import html
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram API (Embed Strategy) is LIVE!'

def get_shortcode(url):
    match = re.search(r'/(?:p|tv|reel)/([^/]+)', url)
    if match:
        return match.group(1)
    return None

# --- روش طلایی: Embed Page Scraping ---
def scrape_embed(shortcode):
    print(f"Attempting Embed Scraping for: {shortcode}")
    
    # آدرس مخصوص Embed که امنیت کمتری دارد
    embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    try:
        response = requests.get(embed_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        html_content = response.text
        
        # 1. استخراج عکس اصلی از کلاس EmbeddedMediaImage
        # اینستاگرام عکس با کیفیت را در این کلاس قرار می‌دهد
        img_match = re.search(r'class="EmbeddedMediaImage" src="([^"]+)"', html_content)
        
        if img_match:
            # لینک را تمیز می‌کنیم (تبدیل &amp; به &)
            clean_url = html.unescape(img_match.group(1))
            
            return [{
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': 'Instagram Photo (Embed Source)'
            }]
            
        return None
        
    except Exception as e:
        print(f"Embed failed: {e}")
        return None

# --- روش yt-dlp (برای ویدیوها) ---
def run_ytdlp(insta_url):
    try:
        # استفاده از کوکی‌های موبایل (User Agent موبایل) گاهی برای ویدیو بهتر است
        mobile_ua = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            '--user-agent', mobile_ua,
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

    shortcode = get_shortcode(insta_url)
    media_items = []
    title = "Instagram_Media"

    # 1. اولویت اول: Embed Scraping (مخصوصا برای عکس‌های تک)
    # چون yt-dlp روی سرورهای ابری عکس را خراب می‌کند، اول این را تست می‌کنیم.
    if shortcode:
        embed_data = scrape_embed(shortcode)
        if embed_data:
            print("Success with Embed Scraping!")
            return jsonify({
                'success': True, 
                'title': 'Instagram Photo', 
                'media_items': embed_data
            })

    # 2. اولویت دوم: yt-dlp (برای ویدیوها/ریلز و آلبوم‌ها)
    print("Embed failed or skipping. Trying yt-dlp for Video/Album...")
    video_info = run_ytdlp(insta_url)
    
    if video_info:
        title = video_info.get('title', 'Instagram_Media')
        
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for item in entries:
                if not item: continue
                m_type = 'video' if item.get('is_video') or item.get('ext') == 'mp4' else 'photo'
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
                        'type': m_type, 'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"آلبوم ({m_type})"
                    })
        else:
            # پست تکی
            m_type = 'video' if video_info.get('is_video') or video_info.get('ext') == 'mp4' else 'photo'
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

    return jsonify({'success': False, 'message': 'محتوایی پیدا نشد.'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=8000)
