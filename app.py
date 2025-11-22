# app.py (نسخه اولویت HTML - مشابه تلگرام)

import json
import subprocess
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return 'Instagram Downloader (Telegram Style) is LIVE!'

# --- تابع استخراج مستقیم از HTML (روش تلگرام) ---
def scrape_html_metadata(insta_url):
    print(f"Scraping HTML for: {insta_url}")
    try:
        # استفاده از User-Agent فیس‌بوک/تلگرام
        # این باعث می‌شود اینستاگرام فکر کند ما ربات پیش‌نمایش هستیم و متاتگ‌های اصلی را بدهد
        headers = {
            'User-Agent': 'facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        
        # درخواست مستقیم به صفحه
        response = requests.get(insta_url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            print(f"HTML Scraping failed with status: {response.status_code}")
            return None
            
        html_content = response.text
        
        # 1. استخراج لینک عکس اصلی (og:image)
        # این لینک همیشه بالاترین کیفیت موجود است
        image_match = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        
        # 2. استخراج لینک ویدیو (og:video) - اگر باشد
        video_match = re.search(r'<meta property="og:video" content="([^"]+)"', html_content)
        
        # 3. استخراج عنوان
        desc_match = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
        description = desc_match.group(1) if desc_match else "Instagram Media"

        # تصمیم‌گیری:
        # اگر ویدیو در متاتگ‌ها بود، یعنی پست ویدیو است.
        # اگر نبود ولی عکس بود، یعنی پست عکس است.
        
        if video_match:
            # اگر ویدیو بود، ترجیح می‌دهیم کار را به yt-dlp بسپاریم چون og:video گاهی کیفیت پایین است
            # اما عکس کاور را برمی‌داریم
            return {
                'type': 'video_detected', # علامت می‌گذاریم که yt-dlp وارد شود
                'thumbnail': image_match.group(1).replace('&amp;', '&') if image_match else None
            }
            
        elif image_match:
            # اگر فقط عکس بود، همین لینک og:image عالی است!
            clean_url = image_match.group(1).replace('&amp;', '&')
            
            # چک می‌کنیم لینک خیلی کوچک نباشد (مثلا 150x150)
            # اگر لینک s150x150 بود، سعی می‌کنیم حذفش کنیم تا سایز اصلی شود
            # اما معمولا og:image سایز کامل است.
            
            return {
                'type': 'photo',
                'download_url': clean_url,
                'thumbnail_url': clean_url,
                'description': description
            }
            
        return None

    except Exception as e:
        print(f"Scraping Error: {e}")
        return None

# --- تابع yt-dlp (برای ویدیوها و آلبوم‌ها) ---
def run_ytdlp(insta_url):
    fake_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    try:
        command = [
            'yt-dlp',
            '--dump-single-json',
            '--no-playlist',
            '--skip-download',
            '--user-agent', fake_user_agent,
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
    
    # ******* استراتژی جدید: اول HTML Scraping (برای عکس) *******
    scraped_data = scrape_html_metadata(insta_url)
    
    # 1. اگر اسکرپر موفق شد و فهمید که این یک "عکس" است:
    if scraped_data and scraped_data['type'] == 'photo':
        print("Photo detected via HTML scraping. Returning High-Res image.")
        media_items.append(scraped_data)
        title = scraped_data['description']
        return jsonify({'success': True, 'title': title, 'media_items': media_items})

    # 2. اگر اسکرپر فهمید "ویدیو" است یا شکست خورد -> اجرای yt-dlp
    print("Video detected or Scraping failed. Falling back to yt-dlp.")
    video_info = run_ytdlp(insta_url)
    
    if video_info:
        title = video_info.get('title', 'Instagram_Media')
        
        # پردازش آلبوم‌ها
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
        
        # پردازش پست تکی (ویدیو)
        else:
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
