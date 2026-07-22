# 🚀 Bexo Downloader

Professional Telegram Bot for downloading media from multiple platforms.

## ✨ Features

- 📥 Download from 15+ platforms
- 🎬 Multiple formats (Video, Audio, Images)
- 📊 Quality selection (144p to 4K)
- 🌍 Multi-language support (Arabic/English)
- 🔒 Security protections
- 📊 Admin panel with statistics
- 🔔 Force subscription
- ⚡ Async performance
- 🐳 Docker support

## 📋 Supported Platforms

| Platform | Video | Audio | Images |
|----------|-------|-------|--------|
| TikTok | ✅ | ✅ | ❌ |
| Instagram | ✅ | ❌ | ✅ |
| YouTube | ✅ | ✅ | ❌ |
| Facebook | ✅ | ✅ | ❌ |
| X/Twitter | ✅ | ❌ | ✅ |
| Reddit | ✅ | ✅ | ✅ |
| Pinterest | ✅ | ❌ | ✅ |
| SoundCloud | ❌ | ✅ | ❌ |
| And more... | | | |

## 🛠 Installation

### Prerequisites

- Python 3.12+
- FFmpeg
- 2GB RAM minimum

### Local Installation

```bash
# Clone repository
git clone https://github.com/yourusername/bexo-downloader.git
cd bexo-downloader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run
python main.py
