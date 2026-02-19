#!/usr/bin/env python3
"""Main entry point for IMHentai downloader."""

import argparse
import asyncio
import sys
from pathlib import Path

from src.config import ConfigManager
from src.session import SessionManager
from src.imhentai_api import IMHentaiAPI
from src.downloader import DownloadManager
from rich.console import Console
from rich.table import Table


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="IMHentai tag-based downloader - search and download manga by tags"
    )

    parser.add_argument(
        "--preset",
        type=str,
        default="default",
        help="Preset name to use (see config/presets.json for available presets)"
    )

    parser.add_argument(
        "--tags",
        type=str,
        help="Override preset tags (comma-separated, e.g., 'tag1,tag2')"
    )

    parser.add_argument(
        "--exclude-tags",
        type=str,
        help="Tags to exclude from search (comma-separated)"
    )

    parser.add_argument(
        "--max-results",
        type=int,
        help="Maximum number of galleries to download"
    )

    parser.add_argument(
        "--max-pages",
        type=int,
        help="Maximum number of search result pages to examine"
    )

    parser.add_argument(
        "--delay",
        type=int,
        help="Delay in seconds between consecutive downloads (respects site limits)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory for downloads (default: current directory)"
    )

    parser.add_argument(
        "--browser",
        type=str,
        default="firefox",
        choices=["firefox", "chrome"],
        help="Browser to extract cookies from"
    )

    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets and exit"
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to IMHentai and authentication status"
    )

    args = parser.parse_args()

    console = Console()

    # Load configuration
    try:
        config_manager = ConfigManager()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    # List presets if requested
    if args.list_presets:
        presets = config_manager.list_presets()
        console.print("\n[bold]Available Presets:[/bold]")
        for preset_name in presets:
            preset = config_manager.get_preset(preset_name)
            console.print(f"  • {preset_name}")
            if preset.tags:
                console.print(f"    Tags: {', '.join(preset.tags)}")
            if preset.exclude_tags:
                console.print(f"    Exclude: {', '.join(preset.exclude_tags)}")
            console.print(f"    Max Results: {preset.max_results}, Max Pages: {preset.max_pages}")
        return 0

    # Initialize session and test connection
    console.print("[bold]Initializing session...[/bold]")
    session_manager = SessionManager(browser=args.browser)

    if args.test_connection:
        console.print(f"[bold]Testing connection to IMHentai...[/bold]")
        if session_manager.test_connection():
            console.print("[green]✓ Connection successful[/green]")
        else:
            console.print("[red]✗ Connection failed[/red]")
            return 1

        is_auth = session_manager.is_authenticated()
        if is_auth:
            console.print("[green]✓ Authenticated (cookies found)[/green]")
        else:
            console.print("[yellow]⚠ Not authenticated (proceeding as guest user)[/yellow]")

        return 0

    # Parse CLI overrides
    tags = None
    exclude_tags = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(',')]
    if args.exclude_tags:
        exclude_tags = [t.strip() for t in args.exclude_tags.split(',')]

    # Merge preset with CLI arguments
    try:
        preset_config, dl_config = config_manager.merge_preset_with_cli(
            args.preset,
            tags=tags,
            exclude_tags=exclude_tags,
            max_results=args.max_results,
            max_pages=args.max_pages,
            delay_seconds=args.delay
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return 1

    # Determine output directory
    output_dir = args.output or Path.cwd()

    # Check authentication
    if not session_manager.is_authenticated():
        console.print("[yellow]⚠ Warning: Not logged in (extracted cookies not found)[/yellow]")
        console.print("   You may have limited access to galleries")

    # Perform search
    console.print(f"\n[bold]Searching for galleries with tags: {preset_config.tags}[/bold]")
    if preset_config.exclude_tags:
        console.print(f"  Excluding tags: {preset_config.exclude_tags}")

    api = IMHentaiAPI(session_manager.get_session())

    try:
        galleries = api.search(
            tags=preset_config.tags,
            exclude_tags=preset_config.exclude_tags,
            max_results=preset_config.max_results,
            max_pages=preset_config.max_pages
        )
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/red]")
        return 1

    if not galleries:
        console.print("[yellow]No galleries found matching your criteria[/yellow]")
        return 0

    console.print(f"\n[green]Found {len(galleries)} galleries[/green]")

    # Display galleries
    table = Table(title="Search Results")
    table.add_column("Title", style="cyan")
    table.add_column("Pages", justify="right", style="magenta")
    table.add_column("Tags", style="green")

    for gallery in galleries[:10]:  # Show first 10
        tag_str = ", ".join(gallery.tags[:3])
        if len(gallery.tags) > 3:
            tag_str += f", +{len(gallery.tags) - 3}"
        table.add_row(gallery.title[:40], str(gallery.pages), tag_str)

    if len(galleries) > 10:
        table.add_row(f"... and {len(galleries) - 10} more", "", "")

    console.print(table)

    # Confirm before downloading
    if not _confirm_download(console, len(galleries)):
        console.print("[yellow]Download cancelled[/yellow]")
        return 0

    # Start downloading
    console.print(f"\n[bold]Starting downloads to: {output_dir}[/bold]")
    console.print(f"Rate limit: {dl_config.download_delay_seconds}s between downloads")

    downloader = DownloadManager(
        output_dir=output_dir,
        delay_seconds=dl_config.download_delay_seconds,
        max_retries=dl_config.max_retries,
        timeout_seconds=dl_config.timeout_seconds,
        concurrent_downloads=dl_config.concurrent_downloads
    )

    # Run async download
    try:
        stats = asyncio.run(downloader.download_galleries(
            galleries,
            api.get_gallery_images,
            preset_config.output_template
        ))

        # Print summary
        console.print("\n[bold]Download Summary:[/bold]")
        console.print(f"  Galleries processed: {stats['downloaded_galleries']}/{stats['total_galleries']}")
        console.print(f"  Images downloaded: {stats['downloaded_images']}")
        console.print(f"  Images skipped (already downloaded): {stats['skipped_images']}")
        console.print(f"  Images failed: {stats['failed_images']}")
        console.print(f"  [bold]Total in archive: {downloader.archive.get_download_count()}[/bold]")

        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Download interrupted by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red]Download failed: {e}[/red]")
        return 1


def _confirm_download(console: Console, gallery_count: int) -> bool:
    """Prompt user to confirm download.
    
    Args:
        console: Rich Console object.
        gallery_count: Number of galleries.
        
    Returns:
        True if user confirms, False otherwise.
    """
    if gallery_count > 100:
        console.print(f"\n[bold yellow]⚠ Warning: About to download from {gallery_count} galleries[/bold yellow]")
        console.print("This may take a significant amount of time and bandwidth.")

    response = console.input("\n[bold]Proceed with download? [y/N]:[/bold] ").strip().lower()
    return response == 'y'


if __name__ == "__main__":
    sys.exit(main())
