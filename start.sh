# start.sh

# نصب yt-dlp روی سرور Render (اجرا در زمان ساخت)
# Render یک سرور لینوکس است.
sudo curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp
sudo chmod a+rx /usr/local/bin/yt-dlp

# اجرای برنامه Flask با استفاده از Gunicorn (برای پایداری)
# 0.0.0.0: پورت عمومی سرور
# app:app: به فایل app.py و شیء Flask به نام app اشاره دارد
gunicorn --bind 0.0.0.0:$PORT app:app