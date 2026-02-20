# IMHentai Downloader

A tag-based manga/doujin downloader for www.imhentai.xxx with preset search configurations, respectful rate limiting, and account support via browser cookies. This is primarily to be used with my [MediaTools](https://github.com/orionpsg1/MediaTools) wrapper.

## Features

- **Tag-Based Search**: Define preset tag combinations for automated searches
- **Browser Authentication**: Extract cookies from Firefox/Chrome for logged-in access
- **Rate Limiting**: Configurable delays (default 0.5 seconds) to respect site limits
- **Smart Deduplication**: Archive-based tracking prevents re-downloading already-retrieved files
- **Flexible Configuration**: JSON presets with CLI override capability
- **Async Downloads**: Concurrent downloads with retry logic and exponential backoff
- **Progress Tracking**: Rich console output with real-time download status

## Requirements

- Python 3.8+
- Dependencies listed in `requirements.txt`

## Installation

1. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

2. **Configure presets** (optional):
   Edit `config/presets.json` to define your custom search presets.

## Usage

### Basic Search

**List available presets:**
```powershell
python main.py --list-presets
```

**Download using a preset:**
```powershell
python main.py --preset default
```

### Advanced Options

**Override tags from command line:**
```powershell
python main.py --preset default --tags "school,romance" --exclude-tags "rape"
```

**Control rate limiting:**
```powershell
python main.py --preset default --delay 0.5
```

**Language filter (defaults to English-only):**
```powershell
python main.py --preset default --lang en
```
You can pass multiple language codes (comma-separated) to include more than one language, e.g. `--lang en,jp`.

**Skip interactive confirmation (non-interactive):**
```powershell
python main.py --preset default --yes
```

**Limit search results:**
```powershell
python main.py --preset default --max-results 100 --max-pages 5
```

**Specify output directory:**
```powershell
python main.py --preset default --output "C:\Downloads\Manga"
```

**Test authentication:**
```powershell
python main.py --test-connection
```

### Full Command Reference

```
usage: main.py [-h] [--preset PRESET] [--tags TAGS] [--exclude-tags EXCLUDE_TAGS]
               [--max-results MAX_RESULTS] [--max-pages MAX_PAGES] [--delay DELAY]
               [--output OUTPUT] [--browser {firefox,chrome}] [--list-presets]
               [--test-connection]

Options:
  --preset PRESET              Preset name (default: "default")
  --tags TAGS                  Override tags (comma-separated)
  --exclude-tags EXCLUDE_TAGS  Tags to exclude (comma-separated)
  --max-results MAX_RESULTS    Maximum galleries to download
  --max-pages MAX_PAGES        Maximum pages to search
  --delay DELAY                Delay between downloads in seconds
  --output OUTPUT              Output directory
  --browser {firefox,chrome}   Browser for cookie extraction (default: firefox)
  --lang LANG                  Languages to include (comma-separated codes, default: en)
  -y, --yes                    Proceed without confirmation (non-interactive)
  --list-presets              List all available presets
  --test-connection           Test IMHentai connection and authentication
  -h, --help                  Show help message
```

## Configuration

### Presets (config/presets.json)

Define named preset configurations:

```json
{
  "presets": {
    "my_favorite_tags": {
      "tags": ["school", "romance", "uncensored"],
      "exclude_tags": ["rape", "violence"],
      "max_results": 200,
      "max_pages": null,
      "output_template": "imhentai/{title}/[{release_date}] {filename}.{ext}"
    }
  },
  "download_delay_seconds": 0.5,
  "max_retries": 3,
  "timeout_seconds": 30,
  "concurrent_downloads": 2
}
```

**Key Fields:**
- `tags`: List of tags to search for (AND logic)
- `exclude_tags`: List of tags to exclude from results
- `max_results`: Maximum galleries to download from this preset (None = unlimited)
- `max_pages`: Maximum pages to search (None = all results)
- `output_template`: Directory/filename template with placeholders:
  - `{title}`: Gallery title
  - `{release_date}`: Publication date (YYYY-MM-DD)
  - `{filename}`: Image filename
  - `{ext}`: File extension

### Global Settings

- `download_delay_seconds`: Minimum delay between downloads (default 0.5 seconds; increase if you encounter rate limits)
- `max_retries`: Number of retry attempts for failed downloads
- `timeout_seconds`: HTTP request timeout
- `concurrent_downloads`: Number of parallel download workers

## Authentication

### Extract Browser Cookies

The tool automatically extracts cookies from your browser for authenticated access:

**Firefox (default):**
```powershell
python main.py --preset default --browser firefox
```

**Google Chrome:**
```powershell
python main.py --preset default --browser chrome
```

### No Manual Login Required

Cookies are extracted automatically from your browser's cookie store. Simply visit imhentai.xxx in your browser while logged in, and the tool will use those cookies.

**Why cookies instead of passwords?**
- More secure (no credentials stored)
- Automatic session management
- Respects your existing browser session

## Archive & Deduplication

The tool maintains an `imhentai-archive.json` file in the output directory to track downloaded files. This prevents re-downloading the same images if you run the tool again.

**Clear archive to re-download everything:**
```powershell
Remove-Item imhentai-archive.json
```

## Rate Limiting & Site Courtesy

By default, this tool enforces a short delay (0.5s) between consecutive downloads. Increase `download_delay_seconds` in `config/presets.json` or pass `--delay` if you encounter rate limits or throttling.

**Why be cautious with rate limits?**
- Prevents IP blocking
- Reduces server load
- Avoids triggering anti-bot measures

If you rely on a free account with explicit server-side buffers, increase the delay accordingly.

## Troubleshooting

### "Connection test failed"

- Ensure you have internet connectivity
- IMHentai may be temporarily down
- Your ISP/network may be blocking the site

### "Not authenticated (proceeding as guest user)"

- Ensure you're logged into IMHentai in your browser of choice
- Cookies may have expired - log in again

### Downloads are very slow

- This is intentional due to rate limiting
- Increase `concurrent_downloads` in config if desired
- Check your internet connection speed

### "Rate limited. Waiting..."

- The site returned a 429 Too Many Requests
- The tool will automatically wait and retry
- Consider increasing `download_delay_seconds` in config

## Integration with MediaTools

To use from the MediaTools PowerShell module:

```powershell
# Add this to your MediaTools.psm1 if not already present
imhentai --preset default
# or
imhentai --tags "tag1,tag2" --max-results 50
```

## Legal Notice

This tool is provided for educational and personal use only. Please respect the website's terms of service and copyright laws. The author is not responsible for misuse of this tool.

## Support

For issues, suggestions, or contributions, please refer to the main MediaTools documentation.
