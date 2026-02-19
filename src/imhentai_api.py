"""IMHentai API and scraping functionality."""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse

from .utils import URLGenerator


@dataclass
class Gallery:
    """Represents a manga/doujin gallery on IMHentai."""
    id: str
    title: str
    url: str
    thumbnail_url: Optional[str] = None
    pages: int = 0
    tags: List[str] = None
    release_date: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class IMHentaiAPI:
    """API client for IMHentai."""

    def __init__(self, session: requests.Session):
        """Initialize API client.
        
        Args:
            session: Configured requests.Session with cookies.
        """
        self.session = session

    def search(
        self,
        tags: List[str],
        exclude_tags: List[str] = None,
        max_results: Optional[int] = 100,
        max_pages: Optional[int] = 5
    ) -> List[Gallery]:
        """Search galleries by tags.
        
        Args:
            tags: List of tags to search for.
            exclude_tags: List of tags to exclude.
            max_results: Maximum number of results to return.
            max_pages: Maximum number of pages to search. If None, search all.
            
        Returns:
            List of Gallery objects matching the search.
        """
        if exclude_tags is None:
            exclude_tags = []

        galleries = []
        page = 1

        while True:
            # Check if we've hit max_pages limit
            if max_pages is not None and page > max_pages:
                break

            # Check if we've hit max_results limit
            if max_results is not None and len(galleries) >= max_results:
                break

            try:
                page_galleries = self._search_page(tags, page)
                
                if not page_galleries:
                    # No more results
                    break

                # Filter out excluded tags
                for gallery in page_galleries:
                    if not any(tag in gallery.tags for tag in exclude_tags):
                        galleries.append(gallery)
                        if max_results and len(galleries) >= max_results:
                            break

                page += 1

            except Exception as e:
                print(f"Error searching page {page}: {e}")
                break

        # Trim to max_results
        if max_results:
            galleries = galleries[:max_results]

        return galleries

    def _search_page(self, tags: List[str], page: int = 1) -> List[Gallery]:
        """Search a single page of results.
        
        Args:
            tags: List of tags to search for.
            page: Page number (1-indexed).
            
        Returns:
            List of Gallery objects from this page.
        """
        url = URLGenerator.search_url(tags, page)
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')
        galleries = []

        # Parse gallery cards from the search results
        # IMHentai uses gallery grid layout
        gallery_elements = soup.find_all('div', class_=re.compile(r'gallery|thumbnail|card'))
        
        for element in gallery_elements:
            try:
                gallery = self._parse_gallery_element(element)
                if gallery:
                    galleries.append(gallery)
            except Exception as e:
                # Skip malformed gallery elements
                continue

        return galleries

    def _parse_gallery_element(self, element) -> Optional[Gallery]:
        """Parse a single gallery element from HTML.
        
        Args:
            element: BeautifulSoup element containing gallery data.
            
        Returns:
            Gallery object or None if parsing fails.
        """
        try:
            # Try to find title link
            title_elem = element.find('a', class_=re.compile(r'title|name|link'))
            if not title_elem:
                title_elem = element.find('a')
            
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            url = title_elem.get('href', '')

            if not url:
                return None

            # Make URL absolute if relative
            if url.startswith('/'):
                url = urljoin(URLGenerator.BASE_URL, url)

            # Extract gallery ID from URL
            gallery_id = self._extract_id_from_url(url)
            if not gallery_id:
                return None

            # Try to find thumbnail
            img_elem = element.find('img')
            thumbnail_url = img_elem.get('src', '') if img_elem else None

            # Try to find page count
            pages = self._extract_page_count(element)

            # Try to find tags
            tag_elements = element.find_all('a', class_=re.compile(r'tag'))
            tags = [tag.get_text(strip=True) for tag in tag_elements]

            return Gallery(
                id=gallery_id,
                title=title,
                url=url,
                thumbnail_url=thumbnail_url,
                pages=pages,
                tags=tags
            )

        except Exception as e:
            return None

    @staticmethod
    def _extract_id_from_url(url: str) -> Optional[str]:
        """Extract gallery ID from URL.
        
        Args:
            url: Gallery URL.
            
        Returns:
            Gallery ID or None.
        """
        # Try to match /gallery/{id}/ pattern
        match = re.search(r'/gallery/([^/]+)', url)
        if match:
            return match.group(1)
        
        # Fallback: use URL hash
        parsed = urlparse(url)
        if parsed.path:
            return parsed.path.strip('/').split('/')[-1]
        
        return None

    @staticmethod
    def _extract_page_count(element) -> int:
        """Extract page count from gallery element.
        
        Args:
            element: BeautifulSoup element.
            
        Returns:
            Number of pages or 0 if not found.
        """
        try:
            # Look for text like "42 photos" or "42 pages"
            text = element.get_text()
            match = re.search(r'(\d+)\s*(photos|pages|images)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        except:
            pass

        return 0

    def get_gallery_images(self, gallery_url: str) -> List[str]:
        """Get list of image URLs from a gallery.
        
        Args:
            gallery_url: URL of the gallery.
            
        Returns:
            List of image URLs.
        """
        try:
            response = self.session.get(gallery_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')
            images = []

            # Look for image elements (typically in a viewer/container)
            img_elements = soup.find_all('img', class_=re.compile(r'image|photo|page|content'))
            
            for img in img_elements:
                src = img.get('src') or img.get('data-src')
                if src and ('http' in src or src.startswith('/')):
                    # Make absolute URL
                    if src.startswith('/'):
                        src = urljoin(URLGenerator.BASE_URL, src)
                    images.append(src)

            return images

        except Exception as e:
            print(f"Error getting gallery images: {e}")
            return []
