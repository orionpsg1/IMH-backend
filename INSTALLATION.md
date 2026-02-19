# Installation & Setup Guide

## What Was Fixed

The initial implementation had a relative import issue that has been resolved:

**Issue**: Python relative imports (`.utils`) were failing because of how modules were being imported.

**Solution**: Updated `main.py` to import modules as part of the `src` package using absolute imports from the package structure.

## Installation Steps

### 1. Install Python Dependencies

```powershell
python3 -m pip install requests beautifulsoup4 lxml aiohttp aiofiles rich fake-useragent
```

Or from the requirements file:
```powershell
python3 -m pip install -r tools/imhentai/requirements.txt
```

### 2. Verify Installation

Test the basic functionality:
```powershell
cd C:\Users\Vance\Documents\WindowsPowerShell\Modules\MediaTools
python3 tools/imhentai/main.py --test-connection
```

You should see:
```
Initializing session...
Testing connection to IMHentai...
✓ Connection successful
✓ Authenticated (cookies found)
```

### 3. Load MediaTools Module

The `imhentai` command is now available in PowerShell:
```powershell
Import-Module MediaTools
imhentai --test-connection
```

Or if you have MediaTools in your PSModulePath:
```powershell
Import-Module MediaTools
imhentai --list-presets
```

## Quick Start

### Test Connection
```powershell
imhentai --test-connection
```

### List Available Presets
```powershell
imhentai --list-presets
```

### Download with Default Preset (50 galleries, 5 pages max)
```powershell
imhentai --preset default
```

### Search Specific Tags
```powershell
imhentai --tags "school,romance" --max-results 25
```

### Exclude Unwanted Tags
```powershell
imhentai --tags "uncensored" --exclude-tags "rape,violence" --max-results 50
```

### Adjust Rate Limiting
```powershell
imhentai --preset default --delay 45
```

### Use Custom Output Directory
```powershell
imhentai --preset default --output "D:\MyDownloads"
```

## Browser Authentication

The tool extracts cookies from your browser for login:

### Firefox (default)
1. Log into `https://imhentai.xxx` in Firefox
2. Run: `imhentai --test-connection`
3. Should show: `✓ Authenticated (cookies found)`

### Chrome
1. Log into `https://imhentai.xxx` in Chrome
2. Run: `imhentai --test-connection --browser chrome`
3. Should show: `✓ Authenticated (cookies found)`

## Configuration

Edit `tools/imhentai/config/presets.json` to create custom presets:

```json
{
  "presets": {
    "my_preset": {
      "tags": ["school", "romance"],
      "exclude_tags": ["rape"],
      "max_results": 100,
      "max_pages": 10,
      "output_template": "imhentai/{title}/[{release_date}] {filename}.{ext}"
    }
  },
  "download_delay_seconds": 30,
  "max_retries": 3,
  "timeout_seconds": 30,
  "concurrent_downloads": 2
}
```

Then use: `imhentai --preset my_preset`

## Troubleshooting

### "Module not found" errors
```powershell
# Reinstall dependencies
python3 -m pip install --upgrade requests beautifulsoup4 lxml aiohttp aiofiles rich fake-useragent
```

### Connection test fails
- Check internet connectivity
- IMHentai may be temporarily down
- Cookies may have expired - log in again in your browser

### "Not authenticated" warning
- Log into IMHentai in your default browser
- Run `imhentai --test-connection` again
- Use `--browser chrome` if Firefox isn't set up

### Python not found
- Ensure Python 3.8+ is installed
- Verify it's in your PATH: `python3 --version`

### Running from PowerShell fails
1. Ensure MediaTools module is imported:
   ```powershell
   Import-Module MediaTools
   ```
2. Check dependencies are installed:
   ```powershell
   python3 -m pip list | grep -E "aiohttp|requests|rich"
   ```

## File Structure

```
tools/imhentai/
├── main.py                      # Entry point (fixed relative imports)
├── requirements.txt             # Python dependencies
├── README.md                    # Full documentation
├── QUICKSTART.md               # Quick usage examples
├── INSTALLATION.md             # This file
├── config/
│   └── presets.json            # Download preset configurations
└── src/
    ├── __init__.py
    ├── config.py               # Config management
    ├── session.py              # Browser cookie extraction
    ├── imhentai_api.py         # Tag search & scraping
    ├── utils.py                # Path templating & utilities
    └── downloader.py           # Download manager with rate limiting
```

## What's Next?

1. **Set up browser authentication**: Log into IMHentai
2. **Test connection**: Run `imhentai --test-connection`
3. **Create presets**: Edit `config/presets.json` for common searches
4. **Start downloading**: Use `imhentai --preset default` or your custom presets

For detailed documentation, see [README.md](README.md)
