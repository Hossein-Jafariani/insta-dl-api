#!/usr/bin/env bash

# نصب همه پکیج‌های مورد نیاز برای ۳ لایه
pip install flask gunicorn requests instaloader
# آپدیت yt-dlp
pip install --upgrade --force-reinstall "git+https://github.com/yt-dlp/yt-dlp.git"

# اجرا
gunicorn --workers 4 app:app
