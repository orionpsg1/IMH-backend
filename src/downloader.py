"""Download management with rate limiting for IMHentai."""

import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any
import time
from rich.progress import Progress, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console

from .imhentai_api import Gallery
from .utils import PathTemplater, ArchiveManager


class DownloadManager:
    """Manages file downloads with rate limiting and retry logic."""

    def __init__(
        self,
        output_dir: Path,
        delay_seconds: int = 30,
        max_retries: int = 3,
        timeout_seconds: int = 30,
        concurrent_downloads: int = 1
    ):
        """Initialize download manager.
        
        Args:
            output_dir: Directory where downloaded files will be saved.
            delay_seconds: Delay in seconds between downloads.
            max_retries: Maximum number of retries for failed downloads.
            timeout_seconds: HTTP request timeout in seconds.
            concurrent_downloads: Maximum concurrent downloads.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.delay_seconds = delay_seconds
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds
        self.concurrent_downloads = concurrent_downloads

        self.archive = ArchiveManager(self.output_dir / "imhentai-archive.json")
        self.console = Console()

        self._last_download_time = 0

    async def download_galleries(
        self,
        galleries: List[Gallery],
        image_fetcher,
        output_template: str
    ) -> Dict[str, Any]:
        """Download all images from multiple galleries.
        
        Args:
            galleries: List of Gallery objects to download.
            image_fetcher: Function that takes gallery_url and returns list of image URLs.
            output_template: Path template string for output files.
            
        Returns:
            Dictionary with download statistics.
        """
        stats = {
            "total_galleries": len(galleries),
            "downloaded_galleries": 0,
            "downloaded_images": 0,
            "skipped_images": 0,
            "failed_images": 0,
            "bytes_downloaded": 0
        }

        # Create a queue of download tasks
        download_queue = asyncio.Queue()

        for gallery in galleries:
            await download_queue.put((gallery, image_fetcher, output_template))

        # Create workers to process downloads
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            workers = [
                asyncio.create_task(self._download_worker(session, download_queue, stats))
                for _ in range(self.concurrent_downloads)
            ]

            # Wait for all items to be processed
            await download_queue.join()

            # Cancel workers
            for worker in workers:
                worker.cancel()

            try:
                await asyncio.gather(*workers)
            except asyncio.CancelledError:
                pass

        return stats

    async def _download_worker(
        self,
        session: aiohttp.ClientSession,
        queue: asyncio.Queue,
        stats: Dict[str, Any]
    ) -> None:
        """Worker coroutine to download items from queue.
        
        Args:
            session: aiohttp ClientSession.
            queue: Queue of (gallery, image_fetcher, output_template) tuples.
            stats: Statistics dictionary to update.
        """
        while True:
            try:
                gallery, image_fetcher, output_template = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            try:
                # Get images for this gallery
                images = image_fetcher(gallery.url)
                
                if images:
                    stats["downloaded_galleries"] += 1

                for image_url in images:
                    # Check if already downloaded
                    if self.archive.is_downloaded(image_url):
                        stats["skipped_images"] += 1
                        continue

            

                    # Download image with retries
                    success = await self._download_image_with_retry(
                        session,
                        image_url,
                        gallery,
                        output_template
                    )

                    if success:
                        stats["downloaded_images"] += 1
                        self.archive.mark_downloaded(image_url, {
                            "gallery": gallery.title,
                            "url": image_url
                        })
                    else:
                        stats["failed_images"] += 1

            except Exception as e:
                self.console.print(f"[red]Error processing gallery {gallery.title}: {e}[/red]")

            finally:
                queue.task_done()

    async def _download_image_with_retry(
        self,
        session: aiohttp.ClientSession,
        image_url: str,
        gallery: Gallery,
        output_template: str
    ) -> bool:
        """Download a single image with retry logic.
        
        Args:
            session: aiohttp ClientSession.
            image_url: URL of the image.
            gallery: Gallery object.
            output_template: Path template for output.
            
        Returns:
            True if successful, False otherwise.
        """
        for attempt in range(self.max_retries):
            try:
                # Enforce download delay
                await self._wait_for_rate_limit()

                # Determine output path
                filename = self._get_filename_from_url(image_url)
                output_path = self.output_dir / PathTemplater.format_path(
                    output_template,
                    title=gallery.title,
                    release_date=gallery.release_date,
                    filename=filename
                )

                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Download image
                async with session.get(image_url, allow_redirects=True) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        
                        async with aiofiles.open(output_path, 'wb') as f:
                            await f.write(content)

                        self.console.print(f"[green]✓[/green] Downloaded: {output_path.name}")
                        return True

                    elif resp.status == 429:  # Rate limited
                        wait_time = int(resp.headers.get('Retry-After', 60))
                        self.console.print(f"[yellow]Rate limited. Waiting {wait_time}s...[/yellow]")
                        await asyncio.sleep(wait_time)
                        continue

                    elif resp.status >= 500:  # Server error, retry
                        if attempt < self.max_retries - 1:
                            wait_time = 2 ** (attempt + 1)  # Exponential backoff
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            self.console.print(f"[red]✗[/red] Server error for {image_url}")
                            return False

                    else:
                        self.console.print(f"[red]✗[/red] Failed to download {image_url}: {resp.status}")
                        return False

            except asyncio.TimeoutError:
                if attempt < self.max_retries - 1:
                    self.console.print(f"[yellow]Timeout, retrying... (attempt {attempt + 1}/{self.max_retries})[/yellow]")
                    await asyncio.sleep(2 ** attempt)
                else:
                    self.console.print(f"[red]✗[/red] Timeout: {image_url}")
                    return False

            except Exception as e:
                self.console.print(f"[red]✗[/red] Error downloading {image_url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                else:
                    return False

        return False

    # ZIP functionality removed; viewer-based image scraping is used instead via download_galleries

    async def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting delay between downloads."""
        elapsed = time.time() - self._last_download_time
        if elapsed < self.delay_seconds:
            wait_time = self.delay_seconds - elapsed
            await asyncio.sleep(wait_time)

        self._last_download_time = time.time()

    @staticmethod
    def _get_filename_from_url(url: str) -> str:
        """Extract filename from URL.
        
        Args:
            url: URL to extract filename from.
            
        Returns:
            Filename with extension.
        """
        # Remove query parameters
        url = url.split('?')[0]
        # Get last part of path
        filename = url.split('/')[-1]
        return filename or "image"

    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics.
        
        Returns:
            Dictionary with archive stats.
        """
        return {
            "files_downloaded": self.archive.get_download_count(),
            "archive_file": str(self.archive.archive_file)
        }
