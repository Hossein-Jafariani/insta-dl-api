#!/usr/bin/env bash

# نصب yt-dlp و Instaloader
pip install yt-dlp flask instaloader gunicorn

# اجرای برنامه
gunicorn --workers 4 app:app
