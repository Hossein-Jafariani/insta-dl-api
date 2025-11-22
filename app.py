# app.py (نسخه جدید برای استخراج اطلاعات کامل)

import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# مسیر اصلی (روت) برای تست سلامت سرور
@app.route('/')
def home():
    return 'Instagram Downloader API is running successfully!'

# مسیر اصلی API برای دریافت اطلاعات پست
@app.route('/info', methods=['GET']) # مسیر را به /info تغییر دادیم
def get_info():
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({
            'success': False,
            'message': 'لطفاً لینک معتبر اینستاگرام را ارائه دهید.'
        }), 400

    try:
        # اجرای دستور yt-dlp برای استخراج اطلاعات کامل
        # --dump-single-json: فقط JSON خروجی را بده (نه آرایه)
        # --no-playlist: اگر پست آلبوم باشد، به عنوان یک لیست در entries خروجی می‌دهد.
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            insta_url
        ]
        
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        # 1. ساخت لیست محتوا (برای پشتیبانی از آلبوم‌ها)
        media_items = []
        title = video_info.get('title', 'instagram_media')
        
        # بررسی می‌کنیم که آیا پست آلبوم (Playlist) است
        if video_info.get('_type') == 'playlist':
            # اگر آلبوم باشد، هر آیتم در entries ذخیره شده است
            entries = video_info.get('entries', [])
            for item in entries:
                if item and 'url' in item:
                    media_items.append({
                        'type': item.get('ext', 'photo') if item.get('ext') != 'mp4' else 'video',
                        'download_url': item.get('url'),
                        'thumbnail_url': item.get('thumbnail'),
                        'description': item.get('description', 'آیتم آلبوم')
                    })
        else:
            # اگر پست تکی باشد (ریلز، ویدیو، یا عکس)
            # yt-dlp لینک نهایی دانلود را در 'url' می‌گذارد و نوع را در 'ext'
            media_type = 'video' if video_info.get('ext') == 'mp4' else 'photo'
            
            media_items.append({
                'type': media_type,
                'download_url': video_info.get('url'),
                'thumbnail_url': video_info.get('thumbnail'),
                'description': video_info.get('description', title)
            })

        if not media_items:
             return jsonify({'success': False, 'message': 'محتوایی پیدا نشد.'}), 404

        return jsonify({
            'success': True,
            'title': title,
            'media_items': media_items
        })

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip()
        return jsonify({
            'success': False,
            'message': f'خطا در استخراج: پست خصوصی یا نامعتبر است. {error_msg}'
        }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'خطای ناشناخته: {str(e)}'
        }), 500

if __name__ == '__main__':
    # توجه: در Render این بخش اجرا نمی‌شود.
    app.run(debug=True, port=8000)
