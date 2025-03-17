# YouTube Video Downloader

A web application that allows users to download YouTube videos in various formats and qualities.

## Features

- Download YouTube videos in different qualities (720p, 1080p, etc.)
- Download audio-only versions in MP3 format
- Progress tracking for downloads
- Clean and modern user interface
- Automatic file cleanup
- Support for both YouTube and YouTube Shorts

## Tech Stack

- Python 3.x
- Flask
- yt-dlp
- FFmpeg
- HTML/CSS/JavaScript

## Prerequisites

- Python 3.x installed
- FFmpeg installed on your system
- pip (Python package manager)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/youtube-downloader.git
cd youtube-downloader
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
   - Windows: Download from [FFmpeg official website](https://ffmpeg.org/download.html)
   - Linux: `sudo apt-get install ffmpeg`
   - macOS: `brew install ffmpeg`

## Usage

1. Start the application:
```bash
python ytdownloader/app.py
```

2. Open your web browser and navigate to:
```
http://localhost:5000
```

3. Enter a YouTube URL and select your preferred quality.

## Project Structure

```
youtube-downloader/
├── ytdownloader/
│   ├── app.py
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── css/
│       └── js/
├── downloads/
├── requirements.txt
└── README.md
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/)
- [Flask](https://flask.palletsprojects.com/) 