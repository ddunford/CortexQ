"""
Clean Web Scraper Connector - Focused on Two-Phase Crawling
"""

import asyncio
import aiohttp
import uuid
import json
import hashlib
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

from services.base_connector import BaseConnector, ConnectorConfig, Document, SyncResult

logger = logging.getLogger(__name__)


class WebScraperConnector(BaseConnector):
    """Clean, focused web scraper with two-phase crawling approach"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        
        # Parse configuration
        auth_config = config.auth_config or {}
        self.start_urls = self._parse_start_urls(auth_config.get('start_urls', ''))
        self.max_pages = int(auth_config.get('max_pages', 100))
        self.max_depth = int(auth_config.get('max_depth', 2))
        self.delay = float(auth_config.get('delay_ms', 2000)) / 1000.0  # Convert to seconds
        self.respect_robots = auth_config.get('respect_robots', True)
        self.follow_external = auth_config.get('follow_external', False)
        self.include_patterns = auth_config.get('include_patterns', [])
        self.exclude_patterns = auth_config.get('exclude_patterns', [])
        
        # Session state
        self.visited_urls = set()
        self.user_agent = 'Mozilla/5.0 (compatible; CortexQ-Crawler/1.0)'
        
        logger.info(f"🔧 Web scraper initialized: {len(self.start_urls)} URLs, max_pages={self.max_pages}")

    def _parse_start_urls(self, start_urls_str: str) -> List[str]:
        """Parse start URLs from configuration string"""
        if not start_urls_str:
            return []
        
        urls = []
        for line in start_urls_str.strip().split('\n'):
            url = line.strip()
            if url and url.startswith(('http://', 'https://')):
                urls.append(url)
        
        return urls

    # ============================================================================
    # PHASE 1: URL DISCOVERY
    # ============================================================================
    
    async def discover_urls(self) -> Dict[str, Any]:
        """Phase 1: Discover URLs from sitemap and light crawling"""
        logger.info("🔍 Starting URL Discovery Phase...")
        
        discovered_urls = {
            'sitemap_urls': [],
            'crawled_urls': [],
            'external_urls': [],
            'blocked_urls': [],
            'robots_blocked': [],
            'total_discovered': 0,
            'estimated_pages': 0,
            'discovery_method': 'sitemap_first'
        }
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            # Step 1: Enhanced Sitemap Discovery
            logger.info("🗺️  Step 1: Sitemap Discovery")
            sitemap_urls = await self._discover_from_sitemap(session)
            discovered_urls['sitemap_urls'] = sitemap_urls
            logger.info(f"📊 Found {len(sitemap_urls)} URLs from sitemaps")
            
            # Step 2: Light Crawling (only if sitemap yields few results)
            if len(sitemap_urls) < 10:
                logger.info("🕷️  Step 2: Light Crawling (few sitemap results)")
                crawled_urls = await self._discover_from_crawling(session, max_pages=20)
                discovered_urls['crawled_urls'] = crawled_urls
                logger.info(f"📊 Found {len(crawled_urls)} additional URLs from crawling")
            else:
                logger.info("✅ Skipping crawling - sitemap provided sufficient URLs")
            
            # Step 3: Filter and categorize all discovered URLs
            all_urls = sitemap_urls + discovered_urls['crawled_urls']
            filtered_results = await self._filter_urls(all_urls, session)
            
            discovered_urls.update(filtered_results)
            discovered_urls['total_discovered'] = len(filtered_results['allowed_urls'])
            discovered_urls['estimated_pages'] = min(len(filtered_results['allowed_urls']), self.max_pages)
            
            # Step 4: Store results for later scraping
            await self._store_discovered_urls(discovered_urls)
            
            logger.info(f"🎉 Discovery Complete! Found {discovered_urls['total_discovered']} scrapable URLs")
            return discovered_urls

    async def _discover_from_sitemap(self, session: aiohttp.ClientSession) -> List[str]:
        """Discover URLs from sitemap.xml files"""
        all_urls = []
        processed_sitemaps = set()
        
        for start_url in self.start_urls:
            parsed = urlparse(start_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            
            # Try common sitemap locations
            sitemap_candidates = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/sitemaps.xml",
                f"{base_url}/robots.txt"  # Check for sitemap references
            ]
            
            for candidate in sitemap_candidates:
                if candidate in processed_sitemaps:
                    continue
                
                try:
                    logger.debug(f"🗺️  Checking: {candidate}")
                    async with session.get(candidate, timeout=aiohttp.ClientTimeout(total=15)) as response:
                        if response.status == 200:
                            content = await response.text()
                            processed_sitemaps.add(candidate)
                            
                            if candidate.endswith('robots.txt'):
                                # Extract sitemap references from robots.txt
                                sitemap_refs = self._extract_sitemaps_from_robots(content, base_url)
                                sitemap_candidates.extend(sitemap_refs)
                            else:
                                # Parse XML sitemap
                                urls = self._parse_sitemap_xml(content)
                                all_urls.extend(urls)
                                logger.info(f"✅ Found {len(urls)} URLs in {candidate}")
                        
                except Exception as e:
                    logger.debug(f"❌ Failed to fetch {candidate}: {e}")
        
        return list(set(all_urls))  # Remove duplicates

    def _extract_sitemaps_from_robots(self, robots_content: str, base_url: str) -> List[str]:
        """Extract sitemap URLs from robots.txt"""
        sitemap_urls = []
        for line in robots_content.split('\n'):
            line = line.strip()
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                if sitemap_url.startswith('/'):
                    sitemap_url = base_url + sitemap_url
                if sitemap_url.startswith(('http://', 'https://')):
                    sitemap_urls.append(sitemap_url)
        return sitemap_urls

    def _parse_sitemap_xml(self, xml_content: str) -> List[str]:
        """Parse XML sitemap and extract URLs"""
        urls = []
        
        try:
            root = ET.fromstring(xml_content)
            
            # Find URL entries
            url_elements = root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}url')
            for url_elem in url_elements:
                loc_elem = url_elem.find('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc_elem is not None and loc_elem.text:
                    url = loc_elem.text.strip()
                    if url.startswith(('http://', 'https://')):
                        urls.append(url)
            
            # If no URLs found, try regex fallback
            if not urls:
                import re
                url_pattern = r'<loc>(.*?)</loc>'
                urls = re.findall(url_pattern, xml_content)
                urls = [url for url in urls if url.startswith(('http://', 'https://'))]
                
        except ET.ParseError:
            # Regex fallback for malformed XML
            import re
            url_pattern = r'<loc>(.*?)</loc>'
            urls = re.findall(url_pattern, xml_content)
            urls = [url for url in urls if url.startswith(('http://', 'https://'))]
        
        return urls

    async def _discover_from_crawling(self, session: aiohttp.ClientSession, max_pages: int = 20) -> List[str]:
        """Light crawling for URL discovery (only extracts links, doesn't scrape content)"""
        discovered_urls = []
        url_queue = [(url, 0) for url in self.start_urls]
        visited = set()
        
        while url_queue and len(discovered_urls) < max_pages:
            current_url, depth = url_queue.pop(0)
            
            if current_url in visited or depth > 2:  # Limit depth for discovery
                continue
                
            visited.add(current_url)
            
            try:
                async with session.get(current_url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                    if response.status == 200 and 'text/html' in response.headers.get('content-type', ''):
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Extract links
                        for link in soup.find_all('a', href=True):
                            href = link['href']
                            absolute_url = urljoin(current_url, href)
                            
                            # Clean URL (remove fragments and queries)
                            parsed = urlparse(absolute_url)
                            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
                            
                            if (clean_url not in visited and 
                                clean_url not in discovered_urls and
                                self._is_valid_url(clean_url)):
                                discovered_urls.append(clean_url)
                                
                                if depth < 2:  # Continue crawling
                                    url_queue.append((clean_url, depth + 1))
                
                await asyncio.sleep(0.5)  # Be respectful
                
            except Exception as e:
                logger.debug(f"❌ Failed to crawl {current_url}: {e}")
        
        return discovered_urls

    async def _filter_urls(self, urls: List[str], session: aiohttp.ClientSession) -> Dict[str, List[str]]:
        """Filter and categorize discovered URLs"""
        allowed_urls = []
        blocked_urls = []
        external_urls = []
        robots_blocked = []
        
        for url in urls:
            try:
                # File type check
                if not self._is_valid_url(url):
                    blocked_urls.append(url)
                    continue
                
                # Pattern matching
                if not self._matches_patterns(url):
                    blocked_urls.append(url)
                    continue
                
                # External URL check
                if not self.follow_external and self._is_external_url(url):
                    external_urls.append(url)
                    continue
                
                # Robots.txt check
                if self.respect_robots and not await self._check_robots_txt(url, session):
                    robots_blocked.append(url)
                    continue
                
                allowed_urls.append(url)
                
            except Exception as e:
                logger.debug(f"❌ Error filtering {url}: {e}")
                blocked_urls.append(url)
        
        return {
            'allowed_urls': allowed_urls[:self.max_pages],
            'blocked_urls': blocked_urls,
            'external_urls': external_urls,
            'robots_blocked': robots_blocked
        }

    # ============================================================================
    # PHASE 2: CONTENT SCRAPING
    # ============================================================================
    
    async def scrape_discovered_urls(self) -> List[Dict[str, Any]]:
        """Phase 2: Scrape content from previously discovered URLs"""
        logger.info("🚀 Starting Scraping Phase...")
        
        # Load discovered URLs
        discovered_urls = await self._load_discovered_urls()
        if not discovered_urls:
            logger.warning("⚠️  No discovered URLs found. Run discovery phase first.")
            return []
        
        allowed_urls = discovered_urls.get('allowed_urls', [])
        logger.info(f"📋 Scraping {len(allowed_urls)} approved URLs")
        
        return await self._scrape_url_list(allowed_urls)

    async def _scrape_url_list(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape content from a list of URLs"""
        scraped_pages = []
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            for i, url in enumerate(urls[:self.max_pages], 1):
                logger.info(f"📄 Scraping {i}/{min(len(urls), self.max_pages)}: {url}")
                
                page_data = await self._scrape_page(url, session)
                if page_data:
                    scraped_pages.append(page_data)
                    logger.info(f"✅ {i}/{min(len(urls), self.max_pages)} - {page_data.get('title', 'Untitled')[:50]}...")
                    
                    # Store in database immediately
                    await self._store_scraped_content(page_data)
                else:
                    logger.warning(f"❌ Failed to scrape {url}")
                
                # Respect delay
                await asyncio.sleep(self.delay)
        
        logger.info(f"🎉 Scraping complete! Successfully scraped {len(scraped_pages)} pages")
        return scraped_pages

    async def _scrape_page(self, url: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Scrape content from a single page"""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract content
                text_content = self._extract_text(soup)
                metadata = self._extract_metadata(soup, url)
                
                return {
                    'url': url,
                    'title': metadata.get('title', ''),
                    'content': text_content,
                    'metadata': metadata,
                    'word_count': len(text_content.split()),
                    'scraped_at': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to scrape {url}: {e}")
            return None

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from HTML"""
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Try to find main content area
        main_content = soup.find('main') or soup.find('article') or soup.find('body') or soup
        
        # Extract text
        text = main_content.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        import re
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Extract metadata from HTML"""
        metadata = {'url': url}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = desc_tag.get('content', '').strip()
        
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Headings
        headings = []
        for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            headings.append(h.get_text().strip())
        metadata['headings'] = headings[:10]  # Limit to first 10
        
        return metadata

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL should be crawled based on file type"""
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Skip non-HTML file extensions
            skip_extensions = {
                '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.ico',
                '.mp3', '.mp4', '.avi', '.mov', '.wav', '.wmv',
                '.zip', '.rar', '.tar', '.gz', '.7z',
                '.js', '.css', '.json', '.xml', '.csv',
                '.woff', '.woff2', '.ttf', '.otf', '.eot'
            }
            
            return not any(path.endswith(ext) for ext in skip_extensions)
            
        except Exception:
            return False

    def _matches_patterns(self, url: str) -> bool:
        """Check if URL matches include/exclude patterns"""
        import re
        
        # Check exclude patterns first
        for pattern in self.exclude_patterns:
            if re.search(pattern, url):
                return False
        
        # If no include patterns, allow all
        if not self.include_patterns:
            return True
        
        # Check include patterns
        for pattern in self.include_patterns:
            if re.search(pattern, url):
                return True
        
        return False

    def _is_external_url(self, url: str) -> bool:
        """Check if URL is external to start domains"""
        if not self.start_urls:
            return False
        
        url_domain = urlparse(url).netloc
        start_domains = [urlparse(start_url).netloc for start_url in self.start_urls]
        
        return url_domain not in start_domains

    async def _check_robots_txt(self, url: str, session: aiohttp.ClientSession) -> bool:
        """Simple robots.txt check"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    # Simple check for Disallow: / or Disallow: <path>
                    path = parsed.path
                    for line in robots_content.split('\n'):
                        line = line.strip()
                        if line.lower().startswith('disallow:'):
                            disallow_path = line.split(':', 1)[1].strip()
                            if disallow_path == '/' or (disallow_path and path.startswith(disallow_path)):
                                return False
            
            return True
            
        except Exception:
            return True  # Allow if robots.txt check fails

    # ============================================================================
    # STORAGE METHODS
    # ============================================================================
    
    async def _store_discovered_urls(self, discovered_urls: Dict[str, Any]) -> None:
        """Store discovered URLs in database"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            
            db = next(get_db())
            
            # Get current sync_config or create empty object
            current_config = db.execute(
                text("SELECT sync_config FROM connectors WHERE id = :connector_id"),
                {"connector_id": self.config.id}
            ).fetchone()
            
            # Merge discovered URLs into sync_config
            if current_config and current_config.sync_config:
                sync_config = current_config.sync_config.copy()
            else:
                sync_config = {}
            
            sync_config['discovered_urls'] = discovered_urls
            
            # Update with new sync_config
            db.execute(
                text("""
                    UPDATE connectors 
                    SET sync_config = :sync_config,
                        updated_at = NOW()
                    WHERE id = :connector_id
                """),
                {
                    "connector_id": self.config.id,
                    "sync_config": json.dumps(sync_config)
                }
            )
            db.commit()
            
            logger.info(f"💾 Stored {discovered_urls['total_discovered']} discovered URLs")
            
        except Exception as e:
            logger.error(f"❌ Failed to store discovered URLs: {e}")

    async def _load_discovered_urls(self) -> Optional[Dict[str, Any]]:
        """Load discovered URLs from database"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            
            db = next(get_db())
            
            result = db.execute(
                text("""
                    SELECT sync_config->>'discovered_urls' as discovered_urls
                    FROM connectors 
                    WHERE id = :connector_id
                """),
                {"connector_id": self.config.id}
            ).fetchone()
            
            if result and result.discovered_urls:
                return json.loads(result.discovered_urls)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to load discovered URLs: {e}")
            return None

    async def _store_scraped_content(self, page_data: Dict[str, Any]) -> None:
        """Store scraped page content in database"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            import hashlib
            
            db = next(get_db())
            
            # Generate hashes
            url_hash = hashlib.md5(page_data['url'].encode()).hexdigest()
            content_hash = hashlib.md5(page_data['content'].encode()).hexdigest() if page_data.get('content') else None
            
            # Check if page already exists
            existing = db.execute(
                text("""
                    SELECT id FROM crawled_pages 
                    WHERE organization_id = :org_id AND connector_id = :connector_id AND url_hash = :url_hash
                """),
                {
                    "org_id": self.config.organization_id,
                    "connector_id": self.config.id,
                    "url_hash": url_hash
                }
            ).fetchone()
            
            if existing:
                # Update existing page
                db.execute(
                    text("""
                        UPDATE crawled_pages 
                        SET content = :content, 
                            title = :title,
                            metadata = :metadata, 
                            last_crawled = NOW(), 
                            content_hash = :content_hash,
                            word_count = :word_count,
                            status = 'success',
                            depth = :depth,
                            updated_at = NOW()
                        WHERE id = :page_id
                    """),
                    {
                        "page_id": existing.id,
                        "content": page_data.get('content', ''),
                        "title": page_data.get('title', ''),
                        "metadata": json.dumps(page_data.get('metadata', {})),
                        "content_hash": content_hash,
                        "word_count": page_data.get('word_count', 0),
                        "depth": 0  # URLs from discovery are considered depth 0
                    }
                )
                logger.debug(f"💾 Updated existing page: {page_data['url']}")
            else:
                # Insert new page
                page_id = str(uuid.uuid4()) if 'uuid' in globals() else f"web_{hash(page_data['url'])}"
                
                db.execute(
                    text("""
                        INSERT INTO crawled_pages 
                        (id, connector_id, organization_id, domain_id, url, url_hash, title, content, 
                         metadata, first_crawled, last_crawled, content_hash, word_count, status, 
                         content_type, depth, created_at, updated_at)
                        VALUES 
                        (:id, :connector_id, :organization_id, :domain_id, :url, :url_hash, :title, :content,
                         :metadata, NOW(), NOW(), :content_hash, :word_count, 'success',
                         'text/html', :depth, NOW(), NOW())
                    """),
                    {
                        "id": page_id,
                        "connector_id": self.config.id,
                        "organization_id": self.config.organization_id,
                        "domain_id": self._get_domain_id(),
                        "url": page_data['url'],
                        "url_hash": url_hash,
                        "title": page_data.get('title', ''),
                        "content": page_data.get('content', ''),
                        "metadata": json.dumps(page_data.get('metadata', {})),
                        "content_hash": content_hash,
                        "word_count": page_data.get('word_count', 0),
                        "depth": 0  # URLs from discovery are considered depth 0
                    }
                )
                logger.debug(f"💾 Stored new page: {page_data['url']}")
            
            db.commit()
            
            # Generate embeddings for searchability
            await self._generate_embeddings(page_data, db)
            
        except Exception as e:
            logger.error(f"❌ Failed to store scraped content for {page_data.get('url', 'unknown')}: {e}")
            if 'db' in locals():
                db.rollback()

    async def _generate_embeddings(self, page_data: Dict[str, Any], db) -> None:
        """Generate embeddings for scraped content to make it searchable"""
        try:
            from sqlalchemy import text
            
            content = page_data.get('content', '')
            title = page_data.get('title', '')
            
            if not content or len(content.strip()) < 50:
                logger.debug(f"🔸 Skipping embedding for short content: {page_data['url']}")
                return
            
            # Combine title and content for embedding
            combined_text = f"{title}\n\n{content}" if title else content
            
            # Truncate if too long (typical embedding models have token limits)
            max_chars = 8000  # Roughly 2000 tokens for most models
            if len(combined_text) > max_chars:
                combined_text = combined_text[:max_chars] + "..."
            
            # Get the actual crawled_pages ID for this URL
            url_hash = hashlib.md5(page_data['url'].encode()).hexdigest()
            
            crawled_page_result = db.execute(
                text("""
                    SELECT id FROM crawled_pages 
                    WHERE organization_id = :org_id 
                    AND url_hash = :url_hash
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {
                    "org_id": self.config.organization_id,
                    "url_hash": url_hash
                }
            ).fetchone()
            
            if not crawled_page_result:
                logger.error(f"❌ No crawled_pages record found for URL: {page_data['url']}")
                return
            
            crawled_page_id = crawled_page_result.id
            
            # Generate embedding using the configured embedding service
            try:
                # Use the existing embedding service
                from search.embedding_service import EmbeddingService
                from config import get_settings
                
                settings = get_settings()
                embedding_service = EmbeddingService(settings)
                await embedding_service.initialize()
                
                # Generate embedding vector
                embedding_vector = await embedding_service.generate_embedding(combined_text)
                
                if embedding_vector is not None:
                    # Store embedding in database using correct schema with actual crawled_pages ID
                    embedding_id = str(uuid.uuid4())
                    
                    # Convert numpy array to list for PostgreSQL vector column
                    if hasattr(embedding_vector, 'tolist'):
                        embedding_list = embedding_vector.tolist()
                    else:
                        embedding_list = list(embedding_vector)
                    
                    db.execute(
                        text("""
                            INSERT INTO embeddings 
                            (id, organization_id, domain_id, source_type, source_id,
                             content_text, embedding, metadata, embedding_model)
                            VALUES 
                            (:id, :org_id, :domain_id, :source_type, :source_id,
                             :content_text, :embedding, :metadata, :embedding_model)
                        """),
                        {
                            "id": embedding_id,
                            "org_id": self.config.organization_id,
                            "domain_id": self._get_domain_id(),
                            "source_type": "web_page",
                            "source_id": crawled_page_id,  # Use actual crawled_pages ID
                            "content_text": combined_text,
                            "embedding": embedding_list,  # Use list format for vector column
                            "metadata": json.dumps({
                                "title": title,
                                "url": page_data['url'],
                                "word_count": page_data.get('word_count', 0),
                                "scraped_at": page_data.get('scraped_at'),
                                "connector_id": self.config.id,
                                "content_type": "web_page"
                            }),
                            "embedding_model": settings.EMBEDDING_MODEL
                        }
                    )
                    
                    db.commit()
                    logger.debug(f"🔍 Generated embedding for: {page_data['url']}")
                else:
                    logger.warning(f"⚠️  No embedding generated for: {page_data['url']}")
                    
            except ImportError:
                logger.warning("⚠️  EmbeddingService not available - content won't be searchable")
            except Exception as e:
                logger.error(f"❌ Failed to generate embedding for {page_data['url']}: {e}")
                
        except Exception as e:
            logger.error(f"❌ Embedding generation error for {page_data.get('url', 'unknown')}: {e}")

    def _get_domain_id(self) -> str:
        """Get domain ID from domain name"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            
            db = next(get_db())
            
            result = db.execute(
                text("""
                    SELECT id FROM organization_domains 
                    WHERE organization_id = :org_id AND domain_name = :domain_name
                    LIMIT 1
                """),
                {
                    "org_id": self.config.organization_id,
                    "domain_name": self.config.domain
                }
            ).fetchone()
            
            if result:
                return str(result.id)
            else:
                # Create default domain if it doesn't exist
                domain_id = str(uuid.uuid4()) if 'uuid' in globals() else "default"
                db.execute(
                    text("""
                        INSERT INTO organization_domains (id, organization_id, domain_name, created_at)
                        VALUES (:id, :org_id, :domain_name, NOW())
                        ON CONFLICT (organization_id, domain_name) DO NOTHING
                    """),
                    {
                        "id": domain_id,
                        "org_id": self.config.organization_id,
                        "domain_name": self.config.domain
                    }
                )
                db.commit()
                return domain_id
                
        except Exception as e:
            logger.error(f"❌ Failed to get domain ID: {e}")
            return "default"

    # ============================================================================
    # CONNECTOR INTERFACE METHODS
    # ============================================================================
    
    async def fetch_data(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Legacy method - now calls scrape_discovered_urls"""
        return await self.scrape_discovered_urls()

    async def authenticate(self) -> tuple[bool, Optional[str]]:
        """No authentication needed for web scraping"""
        return True, None

    async def test_connection(self) -> tuple[bool, Dict[str, Any]]:
        """Test connection by checking start URLs"""
        try:
            if not self.start_urls:
                return False, {"error": "No start URLs configured"}
            
            async with aiohttp.ClientSession() as session:
                async with session.head(self.start_urls[0], timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        return True, {"status": "Connection successful", "status_code": response.status}
                    else:
                        return False, {"error": f"HTTP {response.status}", "status_code": response.status}
                        
        except Exception as e:
            return False, {"error": str(e)}

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Document]:
        """Transform scraped data to Document objects"""
        documents = []
        
        for item in raw_data:
            try:
                doc = Document(
                    id=f"web_{hash(item['url'])}",
                    title=item.get('title', 'Untitled'),
                    content=item.get('content', ''),
                    source=item.get('url', ''),
                    metadata=item.get('metadata', {}),
                    created_at=datetime.fromisoformat(item.get('scraped_at', datetime.utcnow().isoformat()))
                )
                documents.append(doc)
            except Exception as e:
                logger.error(f"❌ Failed to transform document: {e}")
        
        return documents

    async def sync(self, full_sync: bool = False) -> SyncResult:
        """Perform sync operation"""
        try:
            # For full sync, run discovery then scraping
            if full_sync:
                logger.info("🔄 Full sync: running discovery + scraping")
                await self.discover_urls()
            
            # Scrape discovered URLs
            raw_data = await self.scrape_discovered_urls()
            documents = await self.transform_data(raw_data)
            
            return SyncResult(
                success=True,
                records_processed=len(raw_data),
                records_created=len(documents),
                records_updated=0,
                documents=documents
            )
            
        except Exception as e:
            logger.error(f"❌ Sync failed: {e}")
            return SyncResult(
                success=False,
                error_message=str(e),
                records_processed=0,
                records_created=0,
                records_updated=0
            )

    async def regenerate_missing_embeddings(self) -> Dict[str, Any]:
        """Regenerate embeddings for crawled pages that don't have embeddings yet"""
        try:
            from dependencies import get_db
            from sqlalchemy import text
            import json
            
            db = next(get_db())
            
            # Find crawled pages that don't have embeddings
            result = db.execute(
                text("""
                    SELECT cp.id, cp.url, cp.title, cp.content, cp.scraped_at
                    FROM crawled_pages cp
                    LEFT JOIN embeddings e ON e.metadata->>'url' = cp.url 
                        AND e.source_type = 'web_page'
                        AND e.organization_id = :org_id
                    WHERE cp.organization_id = :org_id 
                        AND cp.content IS NOT NULL 
                        AND LENGTH(cp.content) > 50
                        AND e.id IS NULL
                """),
                {"org_id": self.config.organization_id}
            ).fetchall()
            
            if not result:
                logger.info("✅ All crawled pages already have embeddings")
                return {"processed": 0, "created": 0, "errors": 0}
            
            logger.info(f"🔄 Found {len(result)} crawled pages missing embeddings")
            
            processed = 0
            created = 0
            errors = 0
            
            for row in result:
                try:
                    # Convert row to dict format expected by _generate_embeddings
                    page_data = {
                        "url": row.url,
                        "title": row.title or "",
                        "content": row.content or "",
                        "scraped_at": row.scraped_at.isoformat() if row.scraped_at else None
                    }
                    
                    # Generate embedding for this page
                    await self._generate_embeddings(page_data, db)
                    created += 1
                    processed += 1
                    
                    if processed % 10 == 0:
                        logger.info(f"🔄 Processed {processed}/{len(result)} pages...")
                        
                except Exception as e:
                    logger.error(f"❌ Failed to generate embedding for {row.url}: {e}")
                    errors += 1
                    processed += 1
            
            logger.info(f"✅ Embedding regeneration complete: {created} created, {errors} errors")
            
            return {
                "processed": processed,
                "created": created,
                "errors": errors,
                "total_pages": len(result)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to regenerate embeddings: {e}")
            return {"error": str(e), "processed": 0, "created": 0, "errors": 0} 