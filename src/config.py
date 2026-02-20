"""Configuration management for IMHentai downloader."""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class PresetConfig:
    """Configuration for a download preset."""
    tags: List[str]
    exclude_tags: List[str]
    max_results: int
    max_pages: Optional[int]
    output_template: str


@dataclass
class DownloadConfig:
    """Global download configuration."""
    download_delay_seconds: float = 30.0
    max_retries: int = 3
    timeout_seconds: int = 30
    concurrent_downloads: int = 2


class ConfigManager:
    """Manages loading and merging configuration from files and CLI args."""

    def __init__(self, config_file: Optional[Path] = None):
        """Initialize config manager.
        
        Args:
            config_file: Path to presets.json config file. If None, uses default location.
        """
        if config_file is None:
            config_file = Path(__file__).parent.parent / "config" / "presets.json"
        
        self.config_file = config_file
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_file}")

        with open(self.config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Parse presets
        self.presets: Dict[str, PresetConfig] = {}
        for name, preset_data in data.get("presets", {}).items():
            self.presets[name] = PresetConfig(
                tags=preset_data.get("tags", []),
                exclude_tags=preset_data.get("exclude_tags", []),
                max_results=preset_data.get("max_results", 50),
                max_pages=preset_data.get("max_pages", 5),
                output_template=preset_data.get("output_template", "imhentai/{title}/{filename}.{ext}")
            )

        # Parse global settings
        self.download_config = DownloadConfig(
            download_delay_seconds=data.get("download_delay_seconds", 30),
            max_retries=data.get("max_retries", 3),
            timeout_seconds=data.get("timeout_seconds", 30),
            concurrent_downloads=data.get("concurrent_downloads", 2)
        )

    def get_preset(self, preset_name: str) -> Optional[PresetConfig]:
        """Get a preset by name.
        
        Args:
            preset_name: Name of the preset.
            
        Returns:
            PresetConfig if found, None otherwise.
        """
        return self.presets.get(preset_name)

    def merge_preset_with_cli(
        self,
        preset_name: str,
        tags: Optional[List[str]] = None,
        exclude_tags: Optional[List[str]] = None,
        max_results: Optional[int] = None,
        max_pages: Optional[int] = None,
        delay_seconds: Optional[float] = None
    ) -> tuple[PresetConfig, DownloadConfig]:
        """Merge a preset with CLI overrides.
        
        Args:
            preset_name: Name of preset to start with.
            tags: Override tags (if None, uses preset tags).
            exclude_tags: Override exclude_tags (if None, uses preset exclude_tags).
            max_results: Override max_results (if None, uses preset max_results).
            max_pages: Override max_pages (if None, uses preset max_pages).
            delay_seconds: Override delay_seconds (if None, uses config delay).
            
        Returns:
            Tuple of (merged PresetConfig, DownloadConfig with potential delay override).
        """
        preset = self.get_preset(preset_name)
        if preset is None:
            raise ValueError(f"Unknown preset: {preset_name}")

        merged = PresetConfig(
            tags=tags if tags is not None else preset.tags,
            exclude_tags=exclude_tags if exclude_tags is not None else preset.exclude_tags,
            max_results=max_results if max_results is not None else preset.max_results,
            max_pages=max_pages if max_pages is not None else preset.max_pages,
            output_template=preset.output_template
        )

        dl_config = DownloadConfig(
            download_delay_seconds=delay_seconds if delay_seconds is not None else self.download_config.download_delay_seconds,
            max_retries=self.download_config.max_retries,
            timeout_seconds=self.download_config.timeout_seconds,
            concurrent_downloads=self.download_config.concurrent_downloads
        )

        return merged, dl_config

    def list_presets(self) -> List[str]:
        """List all available preset names."""
        return list(self.presets.keys())
