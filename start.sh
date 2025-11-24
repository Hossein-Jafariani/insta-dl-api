pip install flask gunicorn requests instaloader
pip install --upgrade --force-reinstall "git+https://github.com/yt-dlp/yt-dlp.git"
gunicorn --workers 4 app:app
