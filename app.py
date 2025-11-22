# app.py (نسخه نهایی بدون Instaloader و بدون نیاز به لاگین)

import json
import subprocess
import re 
from flask import Flask, request, jsonify
import os # همچنان برای استفاده‌های احتمالی آینده باقی می‌ماند اما در این کد استفاده نمی‌شود.

app = Flask(__name__)

# ******* تابع‌های کمکی *******

def get_shortcode_from_url(url):
    """استخراج shortcode پست از فرمت‌های مختلف لینک اینستاگرام."""
    match = re.search(r'/(?:p|tv|reel)/([^/]+)', url)
    if match:
        return match.group(1)
    return None

def extract_media_from_ytdlp(insta_url, title):
    """اجرای yt-dlp برای استخراج اطلاعات پست (عکس، ویدیو، آلبوم) بدون لاگین."""
    items = []
    
    # 1. اجرای yt-dlp با حداقل آرگومان‌ها
    try:
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
    except subprocess.CalledProcessError as e:
        print(f"yt-dlp failed to extract info. Error: {e.stderr.strip()}")
        return []
    except Exception as e:
        print(f"yt-dlp general error: {e}")
        return []

    # 2. پردازش خروجی: آلبوم‌ها (Carousel)
    if video_info.get('_type') == 'playlist':
        entries = video_info.get('entries', [])
        for item in entries:
            if not item or not item.get('url'): continue
            
            # تشخیص نوع: اگر is_video یا mp4 بود -> ویدیو، در غیر این صورت -> عکس
            media_type = 'video' if item.get('is_video') or item.get('ext') == 'mp4' else 'photo'
            download_url = item.get('url')
            
            # جستجو برای لینک پایدارتر در requested_formats (برای آلبوم‌ها مهم است)
            if item.get('requested_formats'):
                target_ext = 'mp4' if media_type == 'video' else 'jpg'
                for fmt in item['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == target_ext:
                        download_url = fmt['url']
                        break
                        
            if download_url and download_url.startswith('http'):
                 items.append({
                    'type': media_type,
                    'download_url': download_url,
                    'thumbnail_url': item.get('thumbnail'),
                    'description': item.get('description', f"آیتم آلبوم ({media_type})")
                })
    
    # 3. پردازش خروجی: پست‌های تکی (ریلز، ویدیو، عکس)
    else:
        media_type = 'video' if video_info.get('is_video') or video_info.get('ext') == 'mp4' else 'photo'
        download_url = video_info.get('url')
        
        # جستجو برای لینک پایدارتر در requested_formats
        if video_info.get('requested_formats'):
            target_ext = 'mp4' if media_type == 'video' else 'jpg'
            # اگر پست عکس باشد، به دنبال بهترین کیفیت 'jpg' می‌گردیم
            if media_type == 'photo':
                # معمولاً لینک با کیفیت بالاتر در انتهای لیست requested_formats است
                reversed_formats = reversed(video_info['requested_formats'])
                for fmt in reversed_formats:
                    if fmt.get('url') and fmt.get('ext') == 'jpg':
                        download_url = fmt['url']
                        break
            # اگر ویدیو باشد، به دنبال لینک 'mp4' می‌گردیم
            elif media_type == 'video':
                 for fmt in video_info['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        download_url = fmt['url']
                        break
                    
        if download_url and download_url.startswith('http'):
             items.append({
                'type': media_type,
                'download_url': download_url,
                'thumbnail_url': video_info.get('thumbnail'),
                'description': video_info.get('description', title)
            })

    return items


# ******* مسیرهای API *******

@app.route('/')
def home():
    return 'Instagram Downloader API is running successfully! Status: LIVE'

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({'success': False, 'message': 'لطفاً لینک معتبر ارائه دهید.'}), 400

    title = "Instagram_Media"
    
    # اجرای مستقیم yt-dlp
    try:
        media_items = extract_media_from_ytdlp(insta_url, title)
        
        if not media_items:
             # اگر yt-dlp هیچ آیتمی برنگرداند، احتمالاً پست پرایوت یا حذف شده است.
             return jsonify({'success': False, 'message': 'محتوایی پیدا نشد، احتمالاً پست خصوصی یا نامعتبر است.'}), 404

        return jsonify({
            'success': True,
            'title': media_items[0].get('description', title), # عنوان را از اولین آیتم می‌گیریم
            'media_items': media_items
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'خطای ناشناخته در سرور: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
