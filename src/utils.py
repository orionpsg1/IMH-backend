"""Utility functions for IMHentai downloader."""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote


class PathTemplater:
    """Handles template-based file path generation."""

    @staticmethod
    def format_path(
        template: str,
        title: str,
        release_date: Optional[str] = None,
        filename: Optional[str] = None,
        ext: str = "jpg"
    ) -> str:
        """Format a path template with metadata.
        
        Args:
            template: Path template string with placeholders like {title}, {release_date}, {filename}, {ext}
            title: Manga title
            release_date: Release date (YYYY-MM-DD format)
            filename: Filename without extension
            ext: File extension
            
        Returns:
            Formatted path string with all placeholders replaced.
        """
        if filename is None:
            filename = "unknown"
        
        if release_date is None:
            release_date = datetime.now().strftime("%Y-%m-%d")

        # Sanitize values to be filesystem safe
        title = PathTemplater._sanitize_filename(title)
        filename = PathTemplater._sanitize_filename(filename)
        
        result = template.format(
            title=title,
            release_date=release_date,
            filename=filename,
            ext=ext
        )
        
        return result

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Remove characters that are invalid in filenames.
        
        Args:
            name: Filename to sanitize
            
        Returns:
            Sanitized filename
        """
        # Replace invalid characters with underscore
        invalid_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(invalid_chars, '_', name)
        
        # Remove trailing periods and spaces
        sanitized = sanitized.rstrip('. ')
        
        # Truncate to Windows max filename length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]
        
        return sanitized or "file"


class ArchiveManager:
    """Manages download history to prevent re-downloads."""

    def __init__(self, archive_file: Optional[Path] = None):
        """Initialize archive manager.
        
        Args:
            archive_file: Path to archive JSON file. If None, creates in current directory.
        """
        if archive_file is None:
            archive_file = Path("imhentai-archive.json")
        
        self.archive_file = archive_file
        self.archive: Dict[str, Any] = self._load_archive()

    def _load_archive(self) -> Dict[str, Any]:
        """Load archive from file if it exists."""
        if self.archive_file.exists():
            try:
                with open(self.archive_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load archive file: {e}")
                return {"downloaded": {}}
        
        return {"downloaded": {}}

    def is_downloaded(self, file_id: str) -> bool:
        """Check if file has already been downloaded.
        
        Args:
            file_id: Unique identifier for the file (typically URL hash or title+page).
            
        Returns:
            True if already downloaded, False otherwise.
        """
        return file_id in self.archive.get("downloaded", {})

    def mark_downloaded(self, file_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Mark a file as downloaded.
        
        Args:
            file_id: Unique identifier for the file.
            metadata: Optional metadata to store about the download.
        """
        if "downloaded" not in self.archive:
            self.archive["downloaded"] = {}
        
        self.archive["downloaded"][file_id] = {
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        self._save_archive()

    def _save_archive(self) -> None:
        """Save archive to file."""
        try:
            self.archive_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.archive_file, 'w', encoding='utf-8') as f:
                json.dump(self.archive, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save archive file: {e}")

    def get_download_count(self) -> int:
        """Get total number of downloaded files."""
        return len(self.archive.get("downloaded", {}))


class URLGenerator:
    """Generates IMHentai search and content URLs."""

    BASE_URL = "https://imhentai.xxx"

    @staticmethod
    def search_url(tags: list[str], page: int = 1, lang_flags: dict | None = None) -> str:
        """Generate search URL for tags.
        
        Args:
            tags: List of tag names to search for.
            page: Page number (1-indexed).
            
        Returns:
            Complete search URL.
        """
        # Use the advanced search endpoint with a `key` query parameter
        # Build a key like: +tag:"tag one" +tag:"tag two"
        if not tags:
            key = ""
        else:
            terms = [f'+tag:"{t}"' for t in tags]
            key = " ".join(terms)

        # Percent-encode the key fully so + becomes %2B and spaces become %20
        encoded_key = quote(key, safe='') if key else ''

        url = f"{URLGenerator.BASE_URL}/advsearch/"
        params = []
        if encoded_key:
            params.append(f"key={encoded_key}")

        # Default advanced-search flags observed in browser (helps return results):
        # lt, pp, dl, tr: filter toggles; m/d/w/i/a/g: content type flags
        default_search_flags = {
            "lt": 0,
            "pp": 0,
            "dl": 0,
            "tr": 0,
            "m": 1,
            "d": 1,
            "w": 1,
            "i": 1,
            "a": 1,
            "g": 1,
        }

        for k, v in default_search_flags.items():
            params.append(f"{k}={v}")

        # Default language filters: English only unless overridden
        default_langs = {
            "en": 1,
            "jp": 0,
            "es": 0,
            "fr": 0,
            "kr": 0,
            "de": 0,
            "ru": 0,
        }

        if lang_flags is None:
            lang_flags = default_langs
        else:
            # Merge provided flags with defaults (missing keys use defaults)
            merged = default_langs.copy()
            for k, v in (lang_flags.items() if isinstance(lang_flags, dict) else {}):
                if k in merged:
                    merged[k] = 1 if v else 0
            lang_flags = merged

        for k, v in lang_flags.items():
            params.append(f"{k}={v}")

        # include apply=search to mimic browser behavior
        params.append("apply=search")
        if page > 1:
            params.append(f"page={page}")

        if params:
            url += "?" + "&".join(params)

        return url

    @staticmethod
    def gallery_url(gallery_id: str) -> str:
        """Generate gallery detail URL.
        
        Args:
            gallery_id: Gallery ID or slug.
            
        Returns:
            Gallery URL.
        """
        return f"{URLGenerator.BASE_URL}/gallery/{gallery_id}/"
