# IMHentai Downloader - Quick Start Guide

## Installation

1. **Install Python dependencies:**
   ```powershell
   pip install -r tools/imhentai/requirements.txt
   ```

2. **Verify MediaTools module recognizes the new command:**
   ```powershell
   Import-Module MediaTools
   Get-Command imhentai
   ```

## First-Time Setup

### 1. Browser Authentication

The tool uses browser cookies for authentication. To set up:

**a) Firefox (default):**
- Visit `https://imhentai.xxx` and log in to your account
- The tool will automatically extract cookies when run

**b) Chrome:**
```powershell
imhentai --test-connection --browser chrome
```

### 2. Test Connection

```powershell
imhentai --test-connection
```

Expected output:
```
✓ Connection successful
✓ Authenticated (cookies found)    [if logged in]
```

## Basic Usage

### Download with default preset:
```powershell
imhentai --preset default
```

### Download with custom tags:
```powershell
imhentai --tags "school,romance" --max-results 50
```

### Exclude certain tags:
```powershell
imhentai --tags "uncensored" --exclude-tags "rape,violence"
```

### Configure rate limiting:
```powershell
imhentai --preset default --delay 40
```

### Specify output location:
```powershell
imhentai --preset default --output "D:\MyManga"
```

## Configuration

### Edit Presets (config/presets.json)

Create a new preset by adding to the `presets` object:

```json
{
  "presets": {
    "my_collection": {
      "tags": ["school", "romance", "uncensored"],
      "exclude_tags": ["rape"],
      "max_results": 100,
      "max_pages": 5,
      "output_template": "imhentai/{title}/[{release_date}] {filename}.{ext}"
    }
  }
}
```

Then use it:
```powershell
imhentai --preset my_collection
```

## Common Tasks

### View all available presets:
```powershell
imhentai --list-presets
```

### Download everything matching multiple tags:
```powershell
imhentai --tags "tag1,tag2,tag3" --max-pages null
```

### Re-download after clearing archive:
```powershell
# Clear the archive
Remove-Item (Get-ChildItem -Recurse -Filter "imhentai-archive.json")

# Run again - will re-download everything
imhentai --preset default
```

### Control concurrent downloads:
Edit `config/presets.json`:
```json
{
  "concurrent_downloads": 4
}
```

## Rate Limiting

**Important:** IMHentai enforces a 30-second download buffer for free users.

- Default delay: 30 seconds between downloads ✓
- Do not reduce below 30 seconds
- You can increase for additional safety
- Tool respects `Retry-After` headers for 429 responses

## Troubleshooting

### "Unknown preset" error:
```powershell
# Check available presets
imhentai --list-presets
```

### "Not authenticated" warning:
```powershell
# Log in at imhentai.xxx in your browser
# Test connection:
imhentai --test-connection
```

### Slow downloads:
- This is normal due to rate limiting
- Downloads are respectfully spaced to avoid server overload
- Increase `concurrent_downloads` in config if desired

### Connection timeouts:
- Increase `timeout_seconds` in `config/presets.json` (default 30s)
- Check your internet connectivity

## Deduplication Archive

The tool creates `imhentai-archive.json` in the output directory to track downloaded files. This prevents re-downloading:

```json
{
  "downloaded": {
    "https://example.com/image.jpg": {
      "timestamp": "2026-02-19T10:30:45.123456",
      "metadata": {
        "gallery": "Gallery Title",
        "url": "https://example.com/image.jpg"
      }
    }
  }
}
```

## Integration with MediaTools

The `imhentai` command is now available as a MediaTools function:

```powershell
# Direct usage
imhentai --preset default

# Via media router (if configured)
media imhentai.xxx --preset default
```

## Tips & Best Practices

1. **Start small:** Test with `--max-results 10` first
2. **Use presets:** Define common searches in config
3. **Monitor bandwidth:** Check network usage during large downloads
4. **Keep archive:** Don't delete `imhentai-archive.json` unless intentionally re-downloading
5. **Respect the site:** Use appropriate rate limits and don't abuse the service
6. **Keep updated:** Check for updates to galleries using same preset regularly

## Support

For detailed documentation, see: [README.md](README.md)

For PowerShell module integration issues, see: [MediaTools documentation]

Happy downloading! 📦
