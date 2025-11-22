# app.py

import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# مسیر اصلی (روت) برای تست سلامت سرور
@app.route('/')
def home():
    return 'Instagram Downloader API is running successfully! Status: LIVE'

# مسیر اصلی API برای دریافت اطلاعات پست
@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({
            'success': False,
            'message': 'لطفاً لینک معتبر اینستاگرام را ارائه دهید.'
        }), 400

    try:
        # ******* آرگومان -f اصلاح شد *******
        # این به yt-dlp می‌گوید:
        # 1. اگر ویدیو بود، بهترین ترکیب MP4/M4A را بگیر.
        # 2. اگر ویدیو نبود (عکس بود)، بهترین فرمت را بگیر (که معمولاً JPG است).
        format_selection = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best/best[ext=jpg]' 
        
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            '-f', format_selection, # <-- استفاده از آرگومان اصلاح شده
            insta_url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        media_items = []
        title = video_info.get('title', 'instagram_media')
        
        # 1. پردازش آلبوم‌ها (Carousel Posts)
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for item in entries:
                if item and 'url' in item:
                    # بررسی نوع محتوا بر اساس پسوند فایل
                    ext = item.get('ext')
                    media_type = 'photo'
                    if ext == 'mp4' or item.get('is_video'):
                         media_type = 'video'
                    elif ext == 'jpg' or ext == 'jpeg':
                         media_type = 'photo'
                    
                    thumbnail_link = item.get('thumbnail') if item.get('thumbnail') else video_info.get('thumbnail')
                    
                    media_items.append({
                        'type': media_type,
                        'download_url': item.get('url'),
                        'thumbnail_url': thumbnail_link,
                        'description': item.get('description', f'آیتم آلبوم ({media_type})')
                    })
        else:
            # 2. پردازش پست‌های تکی (ریلز، ویدیو، یا عکس)
            
            ext = video_info.get('ext')
            media_type = 'photo'
            if ext == 'mp4' or video_info.get('is_video'):
                media_type = 'video'
            elif ext == 'jpg' or ext == 'jpeg':
                media_type = 'photo'
                
            download_url = video_info.get('url') 

            # اگر requested_formats وجود داشت (برای ویدیوها)، لینک را از آنجا بگیریم
            if media_type == 'video' and video_info.get('requested_formats'):
                for fmt in video_info['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
                        download_url = fmt['url']
                        break
            
            # اگر عکس باشد و لینک نهایی هنوز نامعتبر باشد، دوباره چک می‌کنیم.
            if media_type == 'photo' and download_url is None and video_info.get('requested_formats'):
                 for fmt in video_info['requested_formats']:
                    if fmt.get('url') and (fmt.get('ext') == 'jpg' or fmt.get('ext') == 'jpeg'):
                        download_url = fmt['url']
                        break
            
            media_items.append({
                'type': media_type,
                'download_url': download_url, 
                'thumbnail_url': video_info.get('thumbnail'),
                'description': video_info.get('description', title)
            })

        # فیلتر کردن آیتم‌هایی که لینک دانلود ندارند (لینک‌های NULL)
        final_media_items = [item for item in media_items if item.get('download_url')]
        
        if not final_media_items:
             return jsonify({'success': False, 'message': 'محتوایی پیدا نشد، خصوصی است یا فرمت آن پشتیبانی نمی‌شود.'}), 404

        return jsonify({
            'success': True,
            'title': title,
            'media_items': final_media_items
        })

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip().split('\n')[-1]
        return jsonify({
            'success': False,
            'message': f'خطا در استخراج: پست خصوصی یا نامعتبر است. جزئیات: {error_msg}'
        }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطای ناشناخته در سرور: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
