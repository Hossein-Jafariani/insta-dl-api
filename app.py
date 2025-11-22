# app.py

import json
import subprocess
import instaloader
import re 
import os 
from flask import Flask, request, jsonify
from instaloader.exceptions import TwoFactorAuthRequiredException, BadCredentialsException, PostException

app = Flask(__name__)

# ******* تنظیمات Instaloader *******
# این نمونه به صورت خاموش و بدون دانلود فایل کار می‌کند و فقط برای استخراج ابرداده استفاده می‌شود.
L = instaloader.Instaloader(
    compress_json=False,
    quiet=True,          
    download_videos=False,
    download_pictures=False,
    download_comments=False,
    save_metadata=False,
    max_connection_attempts=1
)

# خواندن اطلاعات کاربری از متغیرهای محیطی برای Login (اختیاری اما توصیه می‌شود)
INSTA_USERNAME = os.environ.get('INSTA_USERNAME')
INSTA_PASSWORD = os.environ.get('INSTA_PASSWORD')

if INSTA_USERNAME and INSTA_PASSWORD:
    try:
        print(f"Attempting Instaloader login as {INSTA_USERNAME}...")
        L.login(INSTA_USERNAME, INSTA_PASSWORD)
        print("Instaloader logged in successfully.")
    except TwoFactorAuthRequiredException:
        print("Login failed: Two-factor authentication is required.")
    except BadCredentialsException:
        print("Login failed: Bad username or password.")
    except Exception as e:
        print(f"Instaloader login failed: {e}")
else:
    print("INSTA_USERNAME or INSTA_PASSWORD not set. Running Instaloader without login (less stable).")

# ******* تابع‌های کمکی *******

def get_shortcode_from_url(url):
    """استخراج shortcode پست از فرمت‌های مختلف لینک اینستاگرام."""
    match = re.search(r'/(?:p|tv|reel)/([^/]+)', url)
    if match:
        return match.group(1)
    return None

def extract_media_from_instaloader(post, title):
    """پردازش خروجی Instaloader برای پست‌های آلبوم و تکی."""
    items = []
    
    # اگر پست آلبوم باشد (Carousel)
    if post.mediacount > 1:
        for i, (is_video, display_url, video_url) in enumerate(zip(
            post.is_video, post.display_url, post.video_url
        )):
            media_type = 'video' if is_video else 'photo'
            download_link = video_url if is_video else display_url 
            
            if download_link and download_link.startswith('http'):
                 items.append({
                    'type': media_type,
                    'download_url': download_link,
                    'thumbnail_url': post.url,
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

def extract_media_from_ytdlp(insta_url, title):
    """اجرای yt-dlp برای ویدیوها و آلبوم‌های پیچیده (Fallback)."""
    items = []
    try:
        # اجرای yt-dlp با حداقل آرگومان‌ها
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            insta_url
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        video_info = json.loads(result.stdout)
        
    except subprocess.CalledProcessError:
        return []

    # yt-dlp برای آلبوم‌ها:
    if video_info.get('_type') == 'playlist':
        entries = video_info.get('entries', [])
        for item in entries:
            if not item or not item.get('url'): continue
            
            media_type = 'video' if item.get('is_video') or item.get('ext') == 'mp4' else 'photo'
            download_url = item.get('url') 
            
            # جستجو برای لینک پایدارتر در requested_formats
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
    
    # yt-dlp برای پست‌های تکی:
    else:
        media_type = 'video' if video_info.get('is_video') or video_info.get('ext') == 'mp4' else 'photo'
        download_url = video_info.get('url')
        
        # جستجو برای لینک پایدارتر در requested_formats
        if video_info.get('requested_formats'):
            target_ext = 'mp4' if media_type == 'video' else 'jpg'
            for fmt in video_info['requested_formats']:
                if fmt.get('url') and fmt.get('ext') == target_ext:
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

    shortcode = get_shortcode_from_url(insta_url)
    instaloader_failed = False
    
    # 1. --- تلاش برای استخراج با Instaloader (Fast Track) ---
    if shortcode:
        try:
            post = instaloader.Post.from_shortcode(L, shortcode) 
            title = post.title if post.title else post.shortcode
            media_items = extract_media_from_instaloader(post, title)
            
            if media_items:
                return jsonify({
                    'success': True,
                    'title': title,
                    'media_items': media_items
                })
            
            instaloader_failed = True # اگر آیتمی برنگردد یا مشکلی باشد، به fallback می‌رویم
                
        except (PostException, Exception) as e:
            error_message = str(e)
            
            # مدیریت خطای 'no video' برای عکس‌ها و سایر خطاها
            if "there is no video in this post" in error_message or "not found" in error_message:
                print(f"Instaloader failed (Photo Post/Not Found): Forced fallback to yt-dlp. Error: {error_message}")
                instaloader_failed = True 
            else:
                 print(f"Instaloader General Error: {e}. Falling back to yt-dlp.")
                 instaloader_failed = True

    # 2. --- اگر Instaloader شکست خورد، از yt-dlp استفاده کن (Fallback) ---
    if instaloader_failed or not shortcode:
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

    # اگر به اینجا برسد، یعنی هیچکدام از ابزارها کار نکردند.
    return jsonify({'success': False, 'message': 'دریافت اطلاعات پست امکان‌پذیر نیست.'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
