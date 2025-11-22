# app.py

import json
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)

# مسیر اصلی (روت) برای تست سلامت سرور
@app.route('/')
def home():
    return 'Instagram Downloader API is running successfully!'

# مسیر اصلی API برای دانلود ویدیو
@app.route('/download', methods=['GET'])
def download_video():
    # دریافت لینک اینستاگرام از پارامتر url
    insta_url = request.args.get('url')
    
    # اگر لینک ارسال نشده باشد
    if not insta_url:
        return jsonify({
            'success': False,
            'message': 'Please provide a valid Instagram URL.'
        }), 400

    try:
        # 1. اجرای دستور yt-dlp برای استخراج لینک MP4
        # --print-json: خروجی را به فرمت JSON بده.
        # --skip-download: فقط اطلاعات را استخراج کن، دانلود نکن.
        # -f best: بهترین کیفیت موجود را پیدا کن.
        command = [
            'yt-dlp',
            '--print-json',
            '--skip-download',
            '-f', 'best',
            insta_url
        ]
        
        # اجرای دستور در ترمینال سرور
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        
        # 2. پردازش خروجی JSON از yt-dlp
        video_info = json.loads(result.stdout)
        
        # استخراج لینک مستقیم نهایی
        download_url = video_info.get('url')
        title = video_info.get('title', 'instagram_video')
        
        if download_url:
            return jsonify({
                'success': True,
                'download_url': download_url,
                'title': title
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Could not extract download link from Instagram post.'
            }), 404

    except subprocess.CalledProcessError as e:
        # خطاهای مربوط به yt-dlp (مثلا پست خصوصی است)
        error_msg = e.stderr.strip()
        return jsonify({
            'success': False,
            'message': f'Extraction failed: {error_msg}'
        }), 500
    
    except Exception as e:
        # سایر خطاهای عمومی
        return jsonify({
            'success': False,
            'message': f'An unexpected error occurred: {str(e)}'
        }), 500

# اگر در محیط توسعه لوکال اجرا شود
if __name__ == '__main__':
    app.run(debug=True)