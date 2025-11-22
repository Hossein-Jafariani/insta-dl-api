#!/usr/bin/env bash

# نصب پکیج‌ها (requests اضافه شد)
pip install flask gunicorn requests
# نصب آخرین نسخه yt-dlp
pip install --upgrade --force-reinstall "git+https://github.com/yt-dlp/yt-dlp.git"

# اجرای برنامه
gunicorn --workers 4 app:app
