"""IMHentai API and scraping functionality."""

from typing import List, Dict, Optional, Tuple
import time
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

    def __init__(self, session: requests.Session, viewer_request_delay_ms: int = 500):
        """Initialize API client.
        
        Args:
            session: Configured requests.Session with cookies.
        """
        self.session = session
        # Delay in milliseconds between requests to viewer pages (to avoid hammering)
        self.viewer_request_delay_ms = int(viewer_request_delay_ms or 0)

    def search(
        self,
        tags: List[str],
        exclude_tags: List[str] = None,
        max_results: Optional[int] = 100,
        max_pages: Optional[int] = 5,
        lang_flags: Optional[Dict[str, int]] = None
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
                page_galleries = self._search_page(tags, page, lang_flags=lang_flags)
                
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

    def _search_page(self, tags: List[str], page: int = 1, lang_flags: Optional[Dict[str, int]] = None) -> List[Gallery]:
        """Search a single page of results.
        
        Args:
            tags: List of tags to search for.
            page: Page number (1-indexed).
            
        Returns:
            List of Gallery objects from this page.
        """
        # Use language flags if provided (URLGenerator defaults to English-only)
        url = URLGenerator.search_url(tags, page, lang_flags=lang_flags)
        
        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'lxml')
        galleries = []

        # Parse gallery cards from the search results
        # Prefer gallery/thumb elements which include a `data-tags` attribute
        gallery_elements = soup.find_all('div', attrs={'data-tags': True})
        
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
            # Prefer caption/title link inside the element
            title_elem = None
            caption = element.find('div', class_=re.compile(r'caption'))
            if caption:
                title_elem = caption.find('a')

            # Fallback: find any anchor that links to a gallery
            if not title_elem:
                for a in element.find_all('a'):
                    href = a.get('href', '')
                    if href and '/gallery/' in href:
                        title_elem = a
                        break

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
            # prefer data-src (lazy-loaded) then src
            thumbnail_url = None
            if img_elem:
                thumbnail_url = img_elem.get('data-src') or img_elem.get('src')

            # Try to find page count
            pages = self._extract_page_count(element)

            # Try to find tags (data-tags contains numeric ids; also look for tag links)
            tag_elements = element.find_all('a', class_=re.compile(r'tag'))
            tags = [tag.get_text(strip=True) for tag in tag_elements]
            # If no textual tags, leave tags empty

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

            html = response.text
            soup = BeautifulSoup(html, 'lxml')

            images: List[str] = []

            # Prefer crawling the viewer pages which contain the high-resolution images:
            # /view/{gallery_id}/{page}/
            gallery_id = self._extract_id_from_url(gallery_url)
            viewer_pages = []

            if gallery_id:
                # Search HTML for explicit /view/{id}/{n}/ links
                view_pattern = re.compile(rf"/view/{re.escape(gallery_id)}/(\d+)/")
                found = set(int(m) for m in view_pattern.findall(html))
                if found:
                    viewer_pages = sorted(found)

            # Fallback: look for viewer anchors or thumbnail links that point to the viewer
            if not viewer_pages:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if gallery_id and f"/view/{gallery_id}/" in href:
                        m = re.search(rf"/view/{re.escape(gallery_id)}/(\d+)/", href)
                        if m:
                            try:
                                viewer_pages.append(int(m.group(1)))
                            except Exception:
                                pass
                viewer_pages = sorted(set(viewer_pages))

            # If we still have no viewer page list, try to infer page count from thumbnails
            if not viewer_pages:
                # Look for thumbnail container: many galleries list thumbnails linking to viewer pages
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if gallery_id and f"/view/{gallery_id}/" in href:
                        m = re.search(rf"/view/{re.escape(gallery_id)}/(\d+)/", href)
                        if m:
                            try:
                                viewer_pages.append(int(m.group(1)))
                            except Exception:
                                pass
                viewer_pages = sorted(set(viewer_pages))

            # If still empty, attempt to parse a numeric page count from the gallery page
            if not viewer_pages:
                # try to find text like "1 of 30" or "Page 1 / 30" or a select with options
                page_count = 0
                # look for select options
                sel = soup.find('select')
                if sel:
                    try:
                        opts = sel.find_all('option')
                        nums = [int(o.get('value') or o.get_text(strip=True)) for o in opts if (o.get('value') or o.get_text(strip=True)).isdigit()]
                        if nums:
                            page_count = max(nums)
                    except Exception:
                        page_count = 0

                if not page_count:
                    # try to glean from text
                    txt = soup.get_text()
                    m = re.search(r'of\s+(\d+)\b', txt, re.IGNORECASE)
                    if m:
                        try:
                            page_count = int(m.group(1))
                        except Exception:
                            page_count = 0

                if page_count and gallery_id:
                    viewer_pages = list(range(1, page_count + 1))

            # At this point, if we have a list of viewer pages, request each viewer page and extract the high-res image
            if viewer_pages and gallery_id:
                for pg in viewer_pages:
                    try:
                        view_url = urljoin(URLGenerator.BASE_URL, f"/view/{gallery_id}/{pg}/")
                        # Respect configured viewer-request delay
                        if getattr(self, 'viewer_request_delay_ms', 0):
                            try:
                                time.sleep(self.viewer_request_delay_ms / 1000.0)
                            except Exception:
                                pass
                        vresp = self.session.get(view_url, timeout=20)
                        vresp.raise_for_status()
                        vsoup = BeautifulSoup(vresp.content, 'lxml')

                        # Heuristic: the main image on viewer pages is often the first large <img>
                        # Find candidate images and pick the first that looks like a content image
                        candidates = []
                        for img in vsoup.find_all('img'):
                            src = img.get('data-src') or img.get('src') or img.get('data-original')
                            if not src:
                                continue
                            if src.startswith('/'):
                                src = urljoin(URLGenerator.BASE_URL, src)
                            lower = src.lower()
                            # skip thumbnails and site assets
                            if 'thumb' in lower or '/images/' in lower or 'logo' in lower:
                                continue
                            if not lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                                continue
                            candidates.append(src)

                        if candidates:
                            # prefer URLs hosted on m1-m7 or dl hosts when present
                            chosen = None
                            for c in candidates:
                                if re.search(r'm\d+-?imhentai|dl\d*\.imhentai', c):
                                    chosen = c
                                    break
                            if not chosen:
                                chosen = candidates[0]
                            images.append(chosen)
                    except Exception:
                        # ignore failures for individual viewer pages
                        continue

                # remove duplicates while preserving order
                seen = set()
                final = []
                for u in images:
                    if u not in seen:
                        seen.add(u)
                        final.append(u)
                return final

            # Fallback to previous behavior: gather images from gallery page (may be previews)
            img_elements = soup.find_all('img')
            for img in img_elements:
                src = img.get('data-src') or img.get('src') or img.get('data-original')
                if not src:
                    continue
                if 'thumb' in src:
                    continue
                if src and ('http' in src or src.startswith('/')):
                    if src.startswith('/'):
                        src = urljoin(URLGenerator.BASE_URL, src)
                    lower = src.lower()
                    if '/images/' in lower or 'logo' in lower or 'thumb' in lower:
                        continue
                    if not lower.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        continue
                    images.append(src)

            return images

        except Exception as e:
            print(f"Error getting gallery images: {e}")
            return []

    def get_gallery_zip_url(self, gallery_url: str) -> Optional[str]:
        """Attempt to find a gallery-level ZIP download URL on the gallery page.

        Returns absolute URL or None if not found.
        """
        try:
            response = self.session.get(gallery_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'lxml')


            # Collect anchors; prefer direct zip links. If only a placeholder
            # download anchor (e.g. '/downloaded/') exists, we'll try the
            # server-side generation endpoint instead of returning the placeholder.
            zip_pattern = re.compile(r'https?://dl\d*\.imhentai\.xxx/[^"\'\s>]+\.zip')
            download_candidate = None
            for a in soup.find_all('a', href=True):
                href = a['href']
                text = a.get_text(strip=True).lower()
                href_clean = href.replace('&amp;', '&')
                # Direct zip link in href
                m = zip_pattern.search(href_clean)
                if m:
                    return m.group(0).replace('&amp;', '&')

                # If the href explicitly contains a zip filename (but not dl host), return it
                if href_clean.lower().endswith('.zip'):
                    if href_clean.startswith('/'):
                        href_clean = urljoin(URLGenerator.BASE_URL, href_clean)
                    return href_clean

                # Otherwise, remember download-like anchors (e.g. '/downloaded/') but don't return yet
                if 'download' in href_clean.lower() or 'download' in text:
                    if href_clean.startswith('/'):
                        href_clean = urljoin(URLGenerator.BASE_URL, href_clean)
                    download_candidate = href_clean

            # Search in the whole HTML (scripts or injected message div) for dl hosts
            html_text = str(soup)
            m = zip_pattern.search(html_text)
            if m:
                return m.group(0).replace('&amp;', '&')

            # Some sites expose a form or button with data-href
            btn = soup.find(attrs={
                'data-href': True
            })
            if btn:
                href = btn.get('data-href')
                if href and href.startswith('/'):
                    href = urljoin(URLGenerator.BASE_URL, href)
                return href

            # If no direct ZIP link found, attempt server-side ZIP generation endpoint
            # Observed browser flow: POST https://imhentai.xxx/inc/dl_new.php with form `gallery_id={id}`
            # Response body begins with "success,{zip_url}" when generation is available.
            try:
                gallery_id = self._extract_id_from_url(gallery_url)
                # Only attempt server-side generation if we found a download-like anchor
                if gallery_id and download_candidate is not None:
                    # First, GET the gallery page to extract any CSRF-like tokens
                    try:
                        gresp = self.session.get(gallery_url, timeout=15)
                        gresp.raise_for_status()
                        gsoup = BeautifulSoup(gresp.content, 'lxml')
                    except Exception:
                        gsoup = None

                    tokens = {}
                    csrf_value = None
                    if gsoup is not None:
                        # meta tags
                        for m in gsoup.find_all('meta'):
                            name = (m.get('name') or '').strip()
                            prop = (m.get('property') or '').strip()
                            content = m.get('content')
                            if content and (('csrf' in name.lower()) or ('csrf' in prop.lower()) or ('token' in name.lower()) or ('token' in prop.lower())):
                                key = name or prop
                                tokens[key] = content
                                if 'csrf' in key.lower() or 'token' in key.lower():
                                    csrf_value = content

                        # hidden inputs
                        for inp in gsoup.find_all('input', {'type': 'hidden'}):
                            in_name = inp.get('name')
                            if not in_name:
                                continue
                            if any(k in in_name.lower() for k in ('csrf', 'token', 'auth')):
                                tokens[in_name] = inp.get('value', '')
                                if 'csrf' in in_name.lower() or 'token' in in_name.lower():
                                    csrf_value = inp.get('value', '')

                    dl_endpoint = urljoin(URLGenerator.BASE_URL, '/inc/dl_new.php')
                    # Browser-like headers (include client hints and fetch metadata)
                    headers = {
                        'Origin': URLGenerator.BASE_URL,
                        'Referer': gallery_url,
                        'X-Requested-With': 'XMLHttpRequest',
                        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'User-Agent': self.session.headers.get('User-Agent'),
                        'sec-ch-ua': '"Not:A-Brand";v="99", "Brave";v="145", "Chromium";v="145"',
                        'sec-ch-ua-platform': '"Windows"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-fetch-site': 'same-origin',
                        'sec-fetch-mode': 'cors',
                        'sec-fetch-dest': 'empty'
                    }

                    data = {'gallery_id': gallery_id}
                    # include discovered tokens in POST body
                    for k, v in tokens.items():
                        if k and k not in data:
                            data[k] = v

                    # include CSRF token header if found
                    if csrf_value:
                        headers['X-CSRF-Token'] = csrf_value

                    resp = self.session.post(dl_endpoint, data=data, headers=headers, timeout=30)
                    if resp.status_code == 200 and resp.text:
                        text = resp.text.strip()
                        # Expected format: "success,https://dl4.imhentai.xxx/...zip"
                        if text.startswith('success,'):
                            zip_url = text.split(',', 1)[1].strip()
                            zip_url = zip_url.replace('&amp;', '&')
                            if zip_url.startswith('/'):
                                zip_url = urljoin(URLGenerator.BASE_URL, zip_url)
                            return zip_url
                        # Fallback: search response body for a dl-hosted zip
                        m = re.search(r'https?://dl\d*\.imhentai\.xxx/[^"\'\s>]+\.zip', text)
                        if m:
                            return m.group(0).replace('&amp;', '&')
            except Exception:
                # If anything fails here, just return None — no zip available programmatically
                pass

            return None
        except Exception as e:
            return None
