import certifi
import os
import sys
import requests
import urllib3
import ssl
from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading
import time
import shutil
from datetime import datetime, timedelta

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set SSL verification to false globally
ssl._create_default_https_context = ssl._create_unverified_context

# Configure requests to use system certificates
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

app = Flask(__name__, template_folder='templates', static_folder='static')

# Download folder setup
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Dictionary to track downloads
downloads = {}

# Cleanup function to remove old files
def clean_old_files():
    while True:
        now = datetime.now()
        for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
            for file in files:
                file_path = os.path.join(root, file)
                file_time = datetime.fromtimestamp(os.path.getctime(file_path))
                if now - file_time > timedelta(hours=1):
                    try:
                        os.remove(file_path)
                    except:
                        pass
        time.sleep(300)  # Check every 5 minutes

# Start cleanup thread
cleanup_thread = threading.Thread(target=clean_old_files, daemon=True)
cleanup_thread.start()

# Progress hook for download status
def get_progress_hook(download_id):
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                # Remove ANSI color codes from percentage string
                percent_str = d['_percent_str']
                percent_str = ''.join([i for i in percent_str if i.isdigit() or i == '.'])
                percent = float(percent_str) if percent_str else 0.0
                
                downloads[download_id].update({
                    'status': 'downloading',
                    'progress': percent,
                    'eta': d.get('eta', 0)
                })
            except Exception as e:
                print(f"Error updating progress: {str(e)}")
                downloads[download_id].update({
                    'status': 'downloading',
                    'progress': 0.0,
                    'eta': d.get('eta', 0)
                })
        elif d['status'] == 'finished':
            downloads[download_id]['status'] = 'processing'
    return progress_hook

# Function to download video
def download_video(url, quality, download_id):
    try:
        download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
        os.makedirs(download_dir, exist_ok=True)
        
        # Common options for both audio and video
        common_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [get_progress_hook(download_id)],
            'nocheckcertificate': True,
            'ignoreerrors': True,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }
        }
        
        if quality == 'audio':
            ydl_opts = {
                **common_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
                'keepvideo': False
            }
        else:
            if quality == 'best':
                format_string = 'bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best'
            else:
                format_string = f'bestvideo[height<={quality.replace("p", "")}]+bestaudio/best[height<={quality.replace("p", "")}]'
            
            ydl_opts = {
                **common_opts,
                'format': format_string,
                'merge_output_format': 'mp4',
                'prefer_ffmpeg': True,
                'postprocessors': [{
                    'key': 'FFmpegVideoRemuxer',
                    'preferedformat': 'mp4'
                }]
            }

        # Configure yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # Extract video ID from URL if it's a YouTube URL
                if 'youtu' in url:
                    video_id = None
                    if 'youtu.be/' in url:
                        video_id = url.split('youtu.be/')[-1].split('?')[0]
                    elif 'youtube.com/watch?v=' in url:
                        video_id = url.split('v=')[-1].split('&')[0]
                    
                    if video_id:
                        url = f'https://www.youtube.com/watch?v={video_id}'

                # Download with retries
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        info = ydl.extract_info(url, download=True)
                        if info:
                            break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        print(f"Attempt {attempt + 1} failed, retrying...")
                        time.sleep(2)

                if not info:
                    raise Exception("Could not extract video information")
                
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    # Try alternative filename pattern
                    if quality == 'audio':
                        filename = os.path.join(download_dir, f"audio_{download_id}.mp3")
                    else:
                        filename = os.path.join(download_dir, f"video_{download_id}.mp4")
                
                downloads[download_id]['filename'] = filename
                downloads[download_id]['status'] = 'finished'
                
            except Exception as e:
                print(f"Error during download: {str(e)}")
                downloads[download_id]['status'] = 'error'
                downloads[download_id]['error'] = str(e)
                shutil.rmtree(download_dir, ignore_errors=True)
                
    except Exception as e:
        print(f"System error: {str(e)}")
        downloads[download_id]['status'] = 'error'
        downloads[download_id]['error'] = str(e)
        shutil.rmtree(download_dir, ignore_errors=True)

# Index route
@app.route('/')
def index():
    return render_template('index.html')

# Download route
@app.route('/download', methods=['POST'])
def download():
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality')
        
        if not url:
            return jsonify({'error': 'No URL provided'}), 400
        
        if quality == 'info':
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    return jsonify({
                        'title': info.get('title', ''),
                        'thumbnail': info.get('thumbnail', ''),
                        'uploader': info.get('uploader', 'Unknown'),
                        'duration': info.get('duration', 0),
                    })
            except yt_dlp.utils.DownloadError as e:
                return jsonify({'error': f'Invalid URL or video unavailable: {str(e)}'}), 400
            except Exception as e:
                app.logger.error(f'Error extracting video info: {str(e)}')
                return jsonify({'error': 'Failed to extract video info'}), 500
        
        download_id = str(uuid.uuid4())
        downloads[download_id] = {'status': 'starting', 'progress': 0}
        thread = threading.Thread(target=download_video, args=(url, quality, download_id))
        thread.start()
        return jsonify({'download_id': download_id, 'status': 'started'})
    except Exception as e:
        app.logger.error(f'Error in download route: {str(e)}')
        return jsonify({'error': 'An error occurred'}), 500

# Status route
@app.route('/status/<download_id>')
def status(download_id):
    if download_id not in downloads:
        return jsonify({'error': 'Download not found'}), 404
    return jsonify(downloads[download_id])

# File download route
@app.route('/download/<download_id>')
def get_file(download_id):
    if download_id not in downloads or 'filename' not in downloads[download_id]:
        return jsonify({'error': 'File not found'}), 404
    filename = downloads[download_id]['filename']
    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404
    return send_file(filename, as_attachment=True, download_name=os.path.basename(filename))

if __name__ == '__main__':
    app.run(debug=True, port=5000)