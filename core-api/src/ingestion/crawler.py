"""
Web Crawler Service for ingesting website content
Implements PRD requirement 3.1: Web Crawling with configurable frequency
"""

import asyncio
import aiohttp
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import robots
from sqlalchemy.orm import Session
from sqlalchemy import text
import re


class WebCrawler:
    """Web crawler for ingesting external website content"""
    
    def __init__(self, max_depth: int = 3, delay: float = 1.0, max_pages: int = 100):
        self.max_depth = max_depth
        self.delay = delay
        self.max_pages = max_pages
        self.visited_urls: Set[str] = set()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'RAG-Searcher-Bot/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def crawl_website(
        self, 
        start_url: str, 
        allowed_domains: List[str],
        exclude_patterns: List[str] = None,
        db: Session = None
    ) -> List[Dict]:
        """
        Crawl a website starting from start_url
        
        Args:
            start_url: Starting URL for crawl
            allowed_domains: List of allowed domains to crawl
            exclude_patterns: URL patterns to exclude
            db: Database session for storing results
            
        Returns:
            List of crawled page data
        """
        if exclude_patterns is None:
            exclude_patterns = []
        
        crawled_pages = []
        url_queue = [(start_url, 0)]  # (url, depth)
        
        # Check robots.txt
        robots_parser = await self._get_robots_parser(start_url)
        
        while url_queue and len(crawled_pages) < self.max_pages:
            current_url, depth = url_queue.pop(0)
            
            if (current_url in self.visited_urls or 
                depth > self.max_depth or
                not self._is_allowed_url(current_url, allowed_domains, exclude_patterns) or
                not self._check_robots_txt(robots_parser, current_url)):
                continue
            
            try:
                page_data = await self._crawl_page(current_url)
                if page_data:
                    crawled_pages.append(page_data)
                    self.visited_urls.add(current_url)
                    
                    # Store in database if provided
                    if db:
                        await self._store_crawled_page(db, page_data)
                    
                    # Extract and queue new URLs
                    if depth < self.max_depth:
                        new_urls = self._extract_links(page_data['content'], current_url)
                        for new_url in new_urls:
                            if new_url not in self.visited_urls:
                                url_queue.append((new_url, depth + 1))
                
                # Respect crawl delay
                await asyncio.sleep(self.delay)
                
            except Exception as e:
                print(f"Error crawling {current_url}: {e}")
                continue
        
        return crawled_pages
    
    async def _crawl_page(self, url: str) -> Optional[Dict]:
        """Crawl a single page and extract content"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return None
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract text content
                text_content = self._extract_text(soup)
                
                # Extract metadata
                metadata = self._extract_metadata(soup, url)
                
                return {
                    'url': url,
                    'title': metadata.get('title', ''),
                    'content': text_content,
                    'metadata': metadata,
                    'crawled_at': datetime.utcnow(),
                    'content_hash': hashlib.md5(text_content.encode()).hexdigest(),
                    'word_count': len(text_content.split())
                }
                
        except Exception as e:
            print(f"Error processing page {url}: {e}")
            return None
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from HTML"""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()
        
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract metadata from HTML page"""
        metadata = {'url': url}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        if desc_tag:
            metadata['description'] = desc_tag.get('content', '')
        
        # Meta keywords
        keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_tag:
            metadata['keywords'] = keywords_tag.get('content', '')
        
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Headings structure
        headings = []
        for i in range(1, 7):
            heading_tags = soup.find_all(f'h{i}')
            for tag in heading_tags:
                headings.append({
                    'level': i,
                    'text': tag.get_text().strip()
                })
        metadata['headings'] = headings
        
        return metadata
    
    def _extract_links(self, content: str, base_url: str) -> List[str]:
        """Extract links from page content"""
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            
            # Clean up URL
            parsed = urlparse(absolute_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            if clean_url not in links:
                links.append(clean_url)
        
        return links
    
    def _is_allowed_url(self, url: str, allowed_domains: List[str], exclude_patterns: List[str]) -> bool:
        """Check if URL is allowed to be crawled"""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check allowed domains
        if not any(domain.endswith(allowed_domain) for allowed_domain in allowed_domains):
            return False
        
        # Check exclude patterns
        for pattern in exclude_patterns:
            if re.search(pattern, url):
                return False
        
        return True
    
    async def _get_robots_parser(self, url: str):
        """Get robots.txt parser for the domain"""
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            
            async with self.session.get(robots_url) as response:
                if response.status == 200:
                    robots_content = await response.text()
                    rp = robots.RobotFileParser()
                    rp.set_url(robots_url)
                    rp.read()
                    return rp
        except:
            pass
        
        return None
    
    def _check_robots_txt(self, robots_parser, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not robots_parser:
            return True
        
        try:
            return robots_parser.can_fetch('RAG-Searcher-Bot', url)
        except:
            return True
    
    async def _store_crawled_page(self, db: Session, page_data: Dict):
        """Store crawled page in database"""
        try:
            # Check if page already exists (by URL hash)
            url_hash = hashlib.md5(page_data['url'].encode()).hexdigest()
            
            existing = db.execute(
                text("SELECT id FROM crawled_pages WHERE url_hash = :url_hash"),
                {"url_hash": url_hash}
            ).fetchone()
            
            if existing:
                # Update existing page
                db.execute(
                    text("""
                        UPDATE crawled_pages 
                        SET content = :content, metadata = :metadata, 
                            last_crawled = :crawled_at, content_hash = :content_hash,
                            word_count = :word_count
                        WHERE url_hash = :url_hash
                    """),
                    {
                        "content": page_data['content'],
                        "metadata": str(page_data['metadata']),
                        "crawled_at": page_data['crawled_at'],
                        "content_hash": page_data['content_hash'],
                        "word_count": page_data['word_count'],
                        "url_hash": url_hash
                    }
                )
            else:
                # Insert new page
                db.execute(
                    text("""
                        INSERT INTO crawled_pages 
                        (id, url, url_hash, title, content, metadata, 
                         first_crawled, last_crawled, content_hash, word_count)
                        VALUES 
                        (gen_random_uuid(), :url, :url_hash, :title, :content, :metadata,
                         :crawled_at, :crawled_at, :content_hash, :word_count)
                    """),
                    {
                        "url": page_data['url'],
                        "url_hash": url_hash,
                        "title": page_data['title'],
                        "content": page_data['content'],
                        "metadata": str(page_data['metadata']),
                        "crawled_at": page_data['crawled_at'],
                        "content_hash": page_data['content_hash'],
                        "word_count": page_data['word_count']
                    }
                )
            
            db.commit()
            
        except Exception as e:
            print(f"Error storing crawled page: {e}")
            db.rollback()


class CrawlScheduler:
    """Scheduler for periodic website crawling"""
    
    def __init__(self):
        self.active_crawls: Dict[str, asyncio.Task] = {}
    
    async def schedule_crawl(
        self,
        crawl_config: Dict,
        db: Session
    ) -> str:
        """
        Schedule a crawl job
        
        Args:
            crawl_config: Configuration dict with url, domains, frequency, etc.
            db: Database session
            
        Returns:
            Crawl job ID
        """
        crawl_id = hashlib.md5(f"{crawl_config['url']}_{datetime.utcnow()}".encode()).hexdigest()
        
        # Store crawl config in database
        await self._store_crawl_config(db, crawl_id, crawl_config)
        
        # Start crawl task
        task = asyncio.create_task(self._run_periodic_crawl(crawl_id, crawl_config, db))
        self.active_crawls[crawl_id] = task
        
        return crawl_id
    
    async def _run_periodic_crawl(self, crawl_id: str, config: Dict, db: Session):
        """Run periodic crawl based on configuration"""
        frequency_hours = config.get('frequency_hours', 24)
        
        while True:
            try:
                async with WebCrawler(
                    max_depth=config.get('max_depth', 3),
                    delay=config.get('delay', 1.0),
                    max_pages=config.get('max_pages', 100)
                ) as crawler:
                    
                    crawled_pages = await crawler.crawl_website(
                        start_url=config['url'],
                        allowed_domains=config['allowed_domains'],
                        exclude_patterns=config.get('exclude_patterns', []),
                        db=db
                    )
                    
                    # Update crawl status
                    await self._update_crawl_status(
                        db, crawl_id, len(crawled_pages), datetime.utcnow()
                    )
                
                # Wait for next crawl
                await asyncio.sleep(frequency_hours * 3600)
                
            except Exception as e:
                print(f"Error in periodic crawl {crawl_id}: {e}")
                await asyncio.sleep(3600)  # Wait 1 hour on error
    
    async def _store_crawl_config(self, db: Session, crawl_id: str, config: Dict):
        """Store crawl configuration in database"""
        try:
            db.execute(
                text("""
                    INSERT INTO crawl_configs 
                    (id, url, config, status, created_at, last_crawl)
                    VALUES 
                    (:id, :url, :config, 'active', :created_at, NULL)
                    ON CONFLICT (id) DO UPDATE SET
                    config = :config, status = 'active'
                """),
                {
                    "id": crawl_id,
                    "url": config['url'],
                    "config": str(config),
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            print(f"Error storing crawl config: {e}")
            db.rollback()
    
    async def _update_crawl_status(self, db: Session, crawl_id: str, pages_crawled: int, timestamp: datetime):
        """Update crawl status in database"""
        try:
            db.execute(
                text("""
                    UPDATE crawl_configs 
                    SET last_crawl = :timestamp, pages_crawled = :pages_crawled
                    WHERE id = :crawl_id
                """),
                {
                    "crawl_id": crawl_id,
                    "timestamp": timestamp,
                    "pages_crawled": pages_crawled
                }
            )
            db.commit()
        except Exception as e:
            print(f"Error updating crawl status: {e}")
            db.rollback()
    
    def stop_crawl(self, crawl_id: str):
        """Stop a scheduled crawl"""
        if crawl_id in self.active_crawls:
            self.active_crawls[crawl_id].cancel()
            del self.active_crawls[crawl_id]


# Global crawler instance
crawler_scheduler = CrawlScheduler() 