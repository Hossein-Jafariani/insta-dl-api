# app.py (نسخه نهایی با پشتیبانی دوگانه: Instaloader و yt-dlp)

import json
import subprocess
import instaloader
from flask import Flask, request, jsonify

app = Flask(__name__)

# ساخت یک نمونه Instaloader برای استخراج ابرداده
L = instaloader.Instaloader(
    compress_json=False,  # خروجی JSON فشرده نشود
    quiet=True,           # خروجی کنسول خاموش باشد
    download_videos=False, 
    download_pictures=False,
    download_comments=False,
    save_metadata=False,
    max_connection_attempts=1
)

@app.route('/')
def home():
    return 'Instagram Downloader API is running successfully! Status: LIVE'

# تابع کمکی برای استخراج لینک‌های دانلود از اطلاعات Instaloader
def extract_media_from_instaloader(post, title):
    items = []
    
    # اگر پست آلبوم باشد (Carousel)
    if post.mediacount > 1:
        for i, (is_video, display_url, video_url) in enumerate(zip(
            post.is_video, post.display_url, post.video_url
        )):
            media_type = 'video' if is_video else 'photo'
            download_link = video_url if is_video else display_url # لینک مستقیم عکس/ویدیو
            
            # اگر لینک دانلود معتبر باشد، آن را اضافه کن
            if download_link and download_link.startswith('http'):
                 items.append({
                    'type': media_type,
                    'download_url': download_link,
                    'thumbnail_url': post.url, # تامبنیل اصلی پست
                    'description': f"آیتم {i+1} آلبوم ({media_type})",
                })
    
    # اگر پست تکی باشد
    else:
        media_type = 'video' if post.is_video else 'photo'
        download_link = post.video_url if post.is_video else post.display_url
        
        if download_link and download_link.startswith('http'):
            items.append({
                'type': media_type,
                'download_url': download_link,
                'thumbnail_url': post.url,
                'description': title,
            })
            
    return items

# تابع کمکی برای استخراج لینک‌های دانلود از اطلاعات yt-dlp (Fallback)
def extract_media_from_ytdlp(insta_url, title):
    # yt-dlp را با حداقل آرگومان‌ها اجرا کن تا ویدیوها خراب نشوند.
    command = [
        'yt-dlp',
        '--dump-single-json',
        '--no-playlist',
        '--skip-download',
        insta_url
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    video_info = json.loads(result.stdout)
    
    media_items = []
    
    # yt-dlp برای آلبوم‌ها:
    if video_info.get('_type') == 'playlist':
        entries = video_info.get('entries', [])
        for item in entries:
            if not item or not item.get('url'): continue
            
            media_type = 'video' if item.get('is_video') or item.get('ext') == 'mp4' else 'photo'
            download_url = item.get('url') # لینک پیش‌فرض
            
            # پیدا کردن بهترین لینک MP4 یا JPG
            if item.get('requested_formats'):
                target_ext = 'mp4' if media_type == 'video' else 'jpg'
                for fmt in item['requested_formats']:
                    if fmt.get('url') and fmt.get('ext') == target_ext:
                        download_url = fmt['url']
                        break
                        
            if download_url.startswith('http'):
                 media_items.append({
                    'type': media_type,
                    'download_url': download_url,
                    'thumbnail_url': item.get('thumbnail'),
                    'description': item.get('description', f"آیتم آلبوم ({media_type})")
                })
    
    # yt-dlp برای پست‌های تکی:
    else:
        media_type = 'video' if video_info.get('is_video') or video_info.get('ext') == 'mp4' else 'photo'
        download_url = video_info.get('url')
        
        # پیدا کردن بهترین لینک MP4 یا JPG
        if video_info.get('requested_formats'):
            target_ext = 'mp4' if media_type == 'video' else 'jpg'
            for fmt in video_info['requested_formats']:
                if fmt.get('url') and fmt.get('ext') == target_ext:
                    download_url = fmt['url']
                    break
                    
        if download_url and download_url.startswith('http'):
             media_items.append({
                'type': media_type,
                'download_url': download_url,
                'thumbnail_url': video_info.get('thumbnail'),
                'description': video_info.get('description', title)
            })

    return media_items

@app.route('/info', methods=['GET']) 
def get_info():
    insta_url = request.args.get('url')
    
    if not insta_url:
        return jsonify({'success': False, 'message': 'لطفاً لینک معتبر ارائه دهید.'}), 400

    # 1. --- تلاش برای استخراج با Instaloader (برای ثبات عکس‌ها) ---
    try:
        post = instaloader.Post.from_shortcode(L, insta_url.split('/')[-2])
        title = post.title if post.title else post.shortcode
        media_items = extract_media_from_instaloader(post, title)
        
        if media_items:
            return jsonify({
                'success': True,
                'title': title,
                'media_items': media_items
            })
            
    except Exception as e:
        # اگر Instaloader شکست خورد یا پستی پیدا نکرد، به مرحله دوم می‌رویم.
        print(f"Instaloader failed, falling back to yt-dlp: {e}")

    # 2. --- اگر Instaloader شکست خورد، از yt-dlp استفاده کن (برای ریلزهای پایدار) ---
    try:
        title = "Instagram_Media"
        media_items = extract_media_from_ytdlp(insta_url, title)
        
        if not media_items:
             return jsonify({'success': False, 'message': 'محتوایی پیدا نشد، خصوصی است یا فرمت پشتیبانی نمی‌شود.'}), 404

        return jsonify({
            'success': True,
            'title': title,
            'media_items': media_items
        })

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip().split('\n')[-1]
        return jsonify({'success': False, 'message': f'خطا در استخراج: پست خصوصی یا نامعتبر است. {error_msg}'}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'خطای ناشناخته در سرور: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
