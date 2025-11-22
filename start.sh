#!/usr/bin/env bash
# فقط yt-dlp و Flask مورد نیاز هستند
pip install yt-dlp flask gunicorn

# اجرای برنامه
gunicorn --workers 4 app:app
