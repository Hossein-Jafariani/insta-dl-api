# app.py

import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# مسیر اصلی (روت) برای تست سلامت سرور
@app.route('/')
def home():
    # این پیام نشان می‌دهد که سرور پایتون فعال و آماده دریافت درخواست است.
    return 'Instagram Downloader API is running successfully! Status: LIVE'

# مسیر اصلی API برای دریافت اطلاعات پست (استفاده شده در اپلیکیشن اندروید)
@app.route('/info', methods=['GET']) 
def get_info():
    # دریافت لینک اینستاگرام از پارامتر url
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({
            'success': False,
            'message': 'لطفاً لینک معتبر اینستاگرام را ارائه دهید.'
        }), 400

    try:
        # اجرای دستور yt-dlp برای استخراج اطلاعات کامل
        # -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best": مطمئن می‌شویم بهترین ترکیب MP4 استخراج شود.
        # --no-playlist: برای اینکه محتویات آلبوم در "entries" ظاهر شود.
        # --skip-download: فقط اطلاعات را استخراج کن، دانلود نکن.
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            # این سوئیچ کمک می‌کند لینک‌های پایدارتری برای ویدیوها استخراج شود.
            '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best', 
            insta_url
        ]
        
        # اجرای دستور در ترمینال سرور
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
        media_items = []
        title = video_info.get('title', 'instagram_media')
        
        # 1. پردازش آلبوم‌ها (Carousel Posts)
        if video_info.get('_type') == 'playlist':
            entries = video_info.get('entries', [])
            for item in entries:
                if item and 'url' in item:
                    # yt-dlp لینک‌های آیتم‌های آلبوم را در item['url'] می‌گذارد.
                    media_type = 'video' if item.get('ext') == 'mp4' or item.get('is_video') else 'photo'
                    
                    # yt-dlp گاهی اوقات اطلاعات کاملی برای تامبنیل آیتم‌های آلبوم نمی‌دهد، از تامبنیل اصلی پست استفاده می‌کنیم.
                    thumbnail_link = item.get('thumbnail') if item.get('thumbnail') else video_info.get('thumbnail')
                    
                    media_items.append({
                        'type': media_type,
                        'download_url': item.get('url'),
                        'thumbnail_url': thumbnail_link,
                        'description': item.get('description', 'آیتم آلبوم')
                    })
        else:
            # 2. پردازش پست‌های تکی (ریلز، ویدیو، یا عکس)
            
            # استخراج نوع رسانه
            media_type = 'video' if video_info.get('ext') == 'mp4' or video_info.get('is_video') else 'photo'
            
            # استخراج لینک دانلود نهایی
            download_url = video_info.get('url') 

            # اگر لینک اصلی نامعتبر بود، از requested_formats بهترین لینک را می‌گیریم (برای اطمینان از MP4 بودن)
            if media_type == 'video' and video_info.get('requested_formats'):
                for fmt in video_info['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == 'mp4':
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
             return jsonify({'success': False, 'message': 'محتوایی پیدا نشد یا خصوصی است. لطفاً لینک را چک کنید.'}), 404

        return jsonify({
            'success': True,
            'title': title,
            'media_items': final_media_items
        })

    except subprocess.CalledProcessError as e:
        # مدیریت خطاهایی که yt-dlp هنگام اجرا برمی‌گرداند (مثلا پست خصوصی است یا حذف شده)
        error_msg = e.stderr.strip().split('\n')[-1] # فقط آخرین خط خطا را می‌گیریم
        return jsonify({
            'success': False,
            'message': f'خطا در استخراج: پست خصوصی یا نامعتبر است. جزئیات: {error_msg}'
        }), 500
    
    except Exception as e:
        # سایر خطاهای عمومی
        return jsonify({
            'success': False,
            'message': f'خطای ناشناخته در سرور: {str(e)}'
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
