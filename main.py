from flask import Flask, render_template, request, jsonify, send_file, Response
import yt_dlp
import os
import uuid
import threading
import time
import shutil
import json
import traceback
import sys
from datetime import datetime, timedelta

# Set UTF-8 as default encoding for Python
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Get the absolute path of the current directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Initialize Flask app with the correct template directory
app = Flask(__name__, 
    template_folder=TEMPLATE_DIR,
    static_folder=BASE_DIR)

# Enable debugging and set JSON settings
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['JSON_SORT_KEYS'] = False
app.config['JSON_AS_ASCII'] = False  # Allow UTF-8 characters in JSON
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# Configuration
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Store download progress
downloads = {}

def sanitize_string(s):
    """Sanitize string to handle potential encoding issues"""
    if s is None:
        return ''
    if isinstance(s, bytes):
        return s.decode('utf-8', errors='replace')
    return str(s)

def sanitize_data(data):
    """Recursively sanitize all strings in a data structure"""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    return data

def clean_old_files():
    """Clean files older than 1 hour"""
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

def download_video(url, quality, download_id):
    try:
        # Create download directory
        download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
        os.makedirs(download_dir, exist_ok=True)

        if quality == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'progress_hooks': [get_progress_hook(download_id)],
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{download_id}/%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            # Generate correct format string
            if quality == 'best':
                format_string = 'bestvideo+bestaudio/best'
            else:
                height = quality.replace('p', '')
                format_string = f'bestvideo[height<={height}]+bestaudio/best'
            
            ydl_opts = {
                'format': format_string,
                'progress_hooks': [get_progress_hook(download_id)],
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{download_id}/%(title)s.mp4'),
                'merge_output_format': 'mp4',
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Get the correct filename after merging
            sanitized_title = sanitize_string(info.get('title', 'video')).replace('/', '_')
            filename = os.path.join(download_dir, f"{sanitized_title}.mp4")
            downloads[download_id]['filename'] = filename
            downloads[download_id]['status'] = 'finished'
            
    except Exception as e:
        downloads[download_id]['status'] = 'error'
        downloads[download_id]['error'] = str(e)
        # Cleanup directory if error occurs
        shutil.rmtree(download_dir, ignore_errors=True)
        
def get_progress_hook(download_id):
    def progress_hook(d):
        if d['status'] == 'downloading':
            try:
                downloads[download_id].update({
                    'status': 'downloading',
                    'speed': d.get('speed', 0),
                    'progress': float(d['_percent_str'].replace('%', '')),
                    'eta': d.get('eta', 0)
                })
            except:
                pass
        elif d['status'] == 'finished':
            downloads[download_id]['status'] = 'processing'
    return progress_hook

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering template: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return str(e), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
            
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        url = data.get('url')
        quality = data.get('quality')

        if not url:
            return jsonify({'error': 'No URL provided'}), 400

        print(f"Processing URL: {url} with quality: {quality}")

        # If quality is 'info', just return video info without downloading
        if quality == 'info':
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best'
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    formats = []
                    if info.get('formats'):
                        for f in info['formats']:
                            if f.get('ext') == 'mp4' and f.get('vcodec') != 'none':
                                formats.append({
                                    'url': f.get('url', ''),
                                    'ext': f.get('ext', ''),
                                    'filesize': f.get('filesize', 0),
                                    'format_id': f.get('format_id', ''),
                                    'format': f.get('format', ''),
                                    'qualityLabel': f.get('height', ''),
                                    'mimeType': f'video/{f.get("ext", "mp4")}'
                                })
                    
                    response_data = {
                        'title': info.get('title', ''),
                        'thumbnail': info.get('thumbnail', ''),
                        'uploader': info.get('uploader', 'Unknown'),
                        'duration': info.get('duration', 0),
                        'formats': formats
                    }
                    
                    return jsonify(response_data)
                    
            except Exception as e:
                print(f"Error extracting video info: {str(e)}")
                print("Traceback:", traceback.format_exc())
                return jsonify({'error': f'Error extracting video info: {str(e)}'}), 500

        # For actual downloads
        print("Starting download process...")
        download_id = str(uuid.uuid4())
        downloads[download_id] = {'status': 'starting', 'progress': 0}

        thread = threading.Thread(
            target=download_video,
            args=(url, quality, download_id)
        )
        thread.start()

        return jsonify({
            'download_id': download_id,
            'status': 'started'
        })

    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        print("Traceback:", traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/status/<download_id>')
def status(download_id):
    if download_id not in downloads:
        return jsonify({'error': 'Download not found'}), 404
    return jsonify(downloads[download_id])

@app.route('/download/<download_id>')
def get_file(download_id):
    if download_id not in downloads or 'filename' not in downloads[download_id]:
        return jsonify({'error': 'File not found'}), 404
        
    filename = downloads[download_id]['filename']
    if not os.path.exists(filename):
        return jsonify({'error': 'File not found'}), 404
        
    return send_file(
        filename,
        as_attachment=True,
        download_name=os.path.basename(filename)
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
