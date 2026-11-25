import os, shutil, tempfile, threading, time
from urllib.parse import urlparse
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
# Vercel site ka URL ALLOWED_ORIGIN mein set karein (e.g. https://mysite.vercel.app)
CORS(app, origins=os.environ.get("ALLOWED_ORIGIN", "*"),
     expose_headers=["Content-Disposition"])
MAX_MB = 300
LAST = {}          # simple per-IP rate limit
LOCK = threading.Lock()

def allowed(url):
    p = urlparse(url)
    return p.scheme in ("http", "https") and bool(p.hostname)

def rate_ok(ip, gap=5):
    with LOCK:
        now = time.time()
        if now - LAST.get(ip, 0) < gap:
            return False
        LAST[ip] = now
        return True

@app.get("/")
def health():
    return "ok"

@app.post("/api/download")
def download():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    audio = data.get("type") == "audio"
    if not allowed(url):
        return jsonify(error="Valid link paste karein (http/https)."), 400
    if not rate_ok(request.remote_addr):
        return jsonify(error="Thora ruk kar dobara try karein."), 429

    tmp = tempfile.mkdtemp()
    opts = {
        "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        "format": "bestaudio[ext=m4a]/bestaudio" if audio
                  else "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
        "max_filesize": MAX_MB * 1024 * 1024,
        "socket_timeout": 20,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
        name = (info.get("title") or "video")[:60] + os.path.splitext(path)[1]
        resp = send_file(path, as_attachment=True, download_name=name)
        resp.call_on_close(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return resp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="Download nahi ho saka. Link public hai? Dobara check karein."), 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
