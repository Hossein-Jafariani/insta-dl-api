# app.py

import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram Downloader API is LIVE! (Supports Photo & Video)'

def get_best_url(item_info, media_type):
    """یافتن بهترین لینک دانلود بر اساس نوع رسانه"""
    download_url = item_info.get('url')
    
    # 1. اگر ویدیو است، سعی کن MP4 پیدا کنی
    if media_type == 'video':
        if item_info.get('requested_formats'):
            for fmt in item_info['requested_formats']:
                if fmt.get('url') and fmt.get('ext') == 'mp4':
                    return fmt['url']
        return download_url # بازگشت لینک پیش‌فرض

    # 2. اگر عکس است، باید بهترین کیفیت JPG/WEBP را پیدا کنیم
    elif media_type == 'photo':
        # الف) بررسی requested_formats (گاهی عکس‌ها اینجا هستند)
        if item_info.get('requested_formats'):
            # معمولاً آخرین فرمت، بهترین کیفیت است
            for fmt in reversed(item_info['requested_formats']):
                if fmt.get('url') and fmt.get('ext') != 'mp4':
                    return fmt['url']
        
        # ب) اگر لینک اصلی موجود و http بود، همان را برگردان
        if download_url and download_url.startswith('http'):
            return download_url

        # ج) اگر لینک اصلی نبود، از لیست thumbnails بزرگترین را بردار
        thumbnails = item_info.get('thumbnails')
        if thumbnails:
            # آخرین تامبنیل معمولاً بزرگترین است
            return thumbnails[-1].get('url')
            
    return None

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({'success': False, 'message': 'لطفاً لینک معتبر ارائه دهید.'}), 400

    # User-Agent واقعی برای جلوگیری از بلاک شدن توسط اینستاگرام
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
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        media_items = []
        title = video_info.get('title', 'Instagram_Media')

        # --- پردازش خروجی ---
        
        # حالت 1: آلبوم (Playlist)
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for i, item in enumerate(entries):
                if not item: continue
                
                is_video = item.get('is_video') or item.get('ext') == 'mp4'
                m_type = 'video' if is_video else 'photo'
                
                dl_link = get_best_url(item, m_type)
                
                if dl_link:
                    media_items.append({
                        'type': m_type,
                        'download_url': dl_link,
                        'thumbnail_url': item.get('thumbnail'),
                        'description': f"آیتم {i+1}"
                    })
        
        # حالت 2: پست تکی (عکس یا ویدیو)
        else:
            is_video = video_info.get('is_video') or video_info.get('ext') == 'mp4'
            m_type = 'video' if is_video else 'photo'
            
            dl_link = get_best_url(video_info, m_type)
            
            if dl_link:
                media_items.append({
                    'type': m_type,
                    'download_url': dl_link,
                    'thumbnail_url': video_info.get('thumbnail'),
                    'description': title
                })

        # بررسی نهایی
        if not media_items:
             return jsonify({'success': False, 'message': 'محتوایی استخراج نشد. ممکن است پست خصوصی باشد.'}), 404

        return jsonify({
            'success': True,
            'title': title,
            'media_items': media_items
        })

    except subprocess.CalledProcessError as e:
        # لاگ کردن خطای دقیق برای دیباگ
        print(f"YT-DLP Error: {e.stderr}")
        return jsonify({'success': False, 'message': 'خطا در پردازش لینک. سرور اینستاگرام پاسخ نمی‌دهد.'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'خطای سرور: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
