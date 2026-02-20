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
import os
import json


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
        type=float,
        help="Delay in seconds between consecutive downloads (supports fractional seconds)"
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
        "--cred-file",
        type=Path,
        help="Path to JSON file containing {\"username\":..., \"password\":...} for non-interactive login"
    )

    parser.add_argument(
        "--lang",
        type=str,
        help="Languages to include (comma-separated codes, e.g. 'en,jp'). Defaults to English only"
    )

    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Proceed without confirmation (non-interactive)"
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

    parser.add_argument(
        "--gallery-concurrency",
        type=int,
        default=None,
        help="Maximum number of galleries to process concurrently (overrides preset)."
    )

    parser.add_argument(
        "--viewer-delay-ms",
        type=int,
        default=None,
        help="Delay in milliseconds between viewer page requests (default 500)."
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
    # Ensure authentication: try browser cookies first, then env/cred-file, then optional prompt
    if not session_manager.is_authenticated():
        console.print("[yellow]⚠ Warning: Not logged in (extracted cookies not found)[/yellow]")

        # Non-interactive credential sources (env vars or cred file)
        env_user = os.environ.get('IMHENTAI_USER')
        env_pass = os.environ.get('IMHENTAI_PASS')
        cred_user = None
        cred_pass = None
        if env_user and env_pass:
            cred_user, cred_pass = env_user, env_pass
        elif args.cred_file and args.cred_file.exists():
            try:
                c = json.loads(args.cred_file.read_text(encoding='utf-8'))
                cred_user = c.get('username')
                cred_pass = c.get('password')
            except Exception:
                cred_user = cred_pass = None

        authed = False
        if cred_user and cred_pass:
            authed = session_manager.login(cred_user, cred_pass)
            if authed:
                # Save cookies for future non-interactive runs
                session_manager.save_cookies_to_store()

        # If still not authenticated, prompt interactively unless --yes supplied
        if not authed:
            if args.yes:
                console.print("   You may have limited access to galleries")
            else:
                authed = session_manager.ensure_authenticated(interactive=True)
                if authed:
                    session_manager.save_cookies_to_store()
                    console.print("[green]✓ Authenticated via credentials[/green]")
                else:
                    console.print("   You may have limited access to galleries")

    # Perform search
    console.print(f"\n[bold]Searching for galleries with tags: {preset_config.tags}[/bold]")
    if preset_config.exclude_tags:
        console.print(f"  Excluding tags: {preset_config.exclude_tags}")

    # Configure API with viewer request delay (default 500ms)
    viewer_delay = args.viewer_delay_ms if args.viewer_delay_ms is not None else 500
    api = IMHentaiAPI(session_manager.get_session(), viewer_request_delay_ms=viewer_delay)

    # Build language flags from CLI override if provided
    lang_flags = None
    if args.lang:
        requested = {x.strip().lower() for x in args.lang.split(',') if x.strip()}
        all_codes = ['en', 'jp', 'es', 'fr', 'kr', 'de', 'ru']
        lang_flags = {code: (1 if code in requested else 0) for code in all_codes}

    try:
        galleries = api.search(
            tags=preset_config.tags,
            exclude_tags=preset_config.exclude_tags,
            max_results=preset_config.max_results,
            max_pages=preset_config.max_pages,
            lang_flags=lang_flags
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

    # Confirm before downloading (skip if --yes provided)
    if not args.yes and not _confirm_download(console, len(galleries)):
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
        concurrent_downloads=(args.gallery_concurrency if args.gallery_concurrency is not None else dl_config.concurrent_downloads)
    )

    # Run async download (use viewer-based scraping; ZIP generation removed)
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
