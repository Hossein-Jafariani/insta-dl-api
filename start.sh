#!/usr/bin/env bash

# نصب و آپدیت اجباری yt-dlp به آخرین نسخه گیت‌هاب
pip install --upgrade --force-reinstall "git+https://github.com/yt-dlp/yt-dlp.git"
pip install flask gunicorn

# اجرای برنامه
gunicorn --workers 4 app:app
