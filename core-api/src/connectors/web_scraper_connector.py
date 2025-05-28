"""
Enhanced Web Scraper Connector with Testing, Preview, and Advanced Configuration
Implements comprehensive web scraping with URL filtering, testing, and management
"""

import asyncio
import aiohttp
import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set, Tuple, Any, Callable
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict, field
import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
import time
import statistics
from collections import defaultdict, Counter
import asyncio
import pickle
import uuid
from concurrent.futures import ThreadPoolExecutor
import random
import ssl
import certifi
from user_agents import parse as parse_user_agent

from services.base_connector import BaseConnector, Document, ConnectorConfig

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Advanced security configuration for web scraping"""
    proxy_rotation: bool = False
    proxy_list: List[str] = None
    user_agent_rotation: bool = True
    custom_user_agents: List[str] = None
    request_fingerprinting: bool = True
    stealth_mode: bool = False
    captcha_detection: bool = True
    bot_detection_evasion: bool = True
    ip_rotation_interval: int = 50  # requests before IP rotation
    session_rotation_interval: int = 100  # requests before session rotation


@dataclass
class RetryStrategy:
    """Advanced retry mechanism for failed requests"""
    max_retries: int = 3
    base_delay: float = 1.0
    exponential_backoff: bool = True
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retry_on_status: List[int] = None  # HTTP status codes to retry
    circuit_breaker_threshold: int = 5  # consecutive failures before circuit break
    circuit_breaker_timeout: int = 300  # seconds to wait before retry


@dataclass
class ContentClassification:
    """ML-based content classification"""
    content_type: str  # article, product, navigation, spam, etc.
    topic_categories: List[str]  # extracted topics
    sentiment_score: float  # -1 to 1
    entity_extraction: List[Dict[str, str]]  # Named entities
    language_confidence: float
    readability_level: str  # elementary, intermediate, advanced
    commercial_intent: float  # 0-1 likelihood of commercial content


@dataclass
class AutomationRule:
    """Automated crawling rules and triggers"""
    trigger_type: str  # time_based, event_based, content_change
    trigger_conditions: Dict[str, Any]
    actions: List[str]  # crawl, alert, export, analyze
    priority: int  # 1-10
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    execution_count: int = 0


@dataclass
class CrawlRule:
    """Rules for crawling behavior"""
    include_patterns: List[str]  # URL patterns to include
    exclude_patterns: List[str]  # URL patterns to exclude
    follow_external: bool = False  # Follow external domains
    respect_robots: bool = True  # Respect robots.txt
    max_file_size: int = 5 * 1024 * 1024  # 5MB max file size


@dataclass
class CrawlPreview:
    """Preview of what URLs would be crawled"""
    discovered_urls: List[str]
    allowed_urls: List[str]
    blocked_urls: List[str]
    robots_blocked: List[str]
    external_urls: List[str]
    estimated_pages: int
    estimated_duration: str


@dataclass
class CrawlStats:
    """Statistics from a crawl operation"""
    total_urls: int
    successful_crawls: int
    failed_crawls: int
    skipped_urls: int
    pages_processed: int
    data_extracted_mb: float
    duration_seconds: float
    last_crawl: datetime


@dataclass
class CrawlSchedule:
    """Scheduling configuration for automated crawls"""
    enabled: bool = False
    frequency_hours: int = 24  # How often to crawl
    next_run: Optional[datetime] = None
    max_concurrent_crawls: int = 3
    retry_failed_pages: bool = True
    incremental_crawl: bool = True  # Only crawl changed pages
    schedule_type: str = "interval"  # interval, cron, manual


@dataclass
class ContentQualityMetrics:
    """Enhanced content quality analysis"""
    readability_score: float
    content_density: float
    semantic_richness: float
    freshness_score: float
    authority_score: float
    engagement_potential: float
    overall_quality: float
    duplicate_similarity: float = 0.0
    content_uniqueness: float = 1.0
    information_density: float = 0.0


@dataclass
class CrawlPerformanceMetrics:
    """Performance metrics for crawl operations"""
    pages_per_second: float = 0.0
    avg_response_time: float = 0.0
    error_rate: float = 0.0
    bandwidth_usage_mb: float = 0.0
    cache_hit_rate: float = 0.0
    robots_compliance_rate: float = 0.0


@dataclass
class URLIntelligence:
    """URL discovery and prioritization intelligence"""
    priority_score: float
    discovery_depth: int
    traffic_potential: float
    content_type_hint: str
    last_updated: Optional[datetime]
    crawl_frequency: int  # hours
    error_history: List[str]


@dataclass
class CrawlSession:
    """Real-time crawl session tracking"""
    session_id: str
    start_time: datetime
    pages_discovered: int
    pages_processed: int
    pages_successful: int
    pages_failed: int
    bytes_downloaded: int
    avg_response_time: float
    current_queue_size: int
    estimated_completion: Optional[datetime]


@dataclass
class SmartScheduling:
    """Intelligent crawl scheduling"""
    optimal_times: List[int]  # Hours of day
    content_change_frequency: Dict[str, float]  # URL -> change frequency
    priority_urls: List[str]
    backoff_urls: Dict[str, datetime]  # URLs to avoid temporarily
    seasonal_patterns: Dict[str, float]  # Month -> activity multiplier


@dataclass
class AlertRule:
    """Configurable alert rules for monitoring"""
    id: str
    name: str
    rule_type: str  # error_rate, response_time, content_quality, duplicate_rate
    threshold: float
    comparison: str  # greater_than, less_than, equals
    time_window_minutes: int
    enabled: bool = True
    notification_channels: List[str] = None  # email, webhook, slack
    cooldown_minutes: int = 30
    last_triggered: Optional[datetime] = None


@dataclass
class PerformanceAlert:
    """Performance anomaly detection and alerts"""
    alert_id: str
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str  # low, medium, high, critical
    triggered_at: datetime
    description: str
    suggested_actions: List[str]


@dataclass
class WebhookNotification:
    """Webhook notification configuration"""
    webhook_id: str
    url: str
    secret: Optional[str] = None
    headers: Dict[str, str] = None
    payload_template: str = "default"
    retry_count: int = 3
    timeout_seconds: int = 30
    enabled: bool = True


@dataclass
class CrawlHealthMetrics:
    """Comprehensive health metrics for crawl operations"""
    health_score: float  # 0-100 overall health score
    availability_percentage: float
    response_time_p95: float
    error_rate_percentage: float
    content_freshness_days: float
    duplicate_content_percentage: float
    robots_compliance_percentage: float
    bandwidth_efficiency: float
    storage_efficiency: float
    security_score: float
    
    
@dataclass
class AdvancedAnalytics:
    """Advanced analytics and insights"""
    content_trends: Dict[str, List[Tuple[datetime, float]]]  # metric -> time series
    page_rank_distribution: Dict[str, int]  # quality tier -> count
    crawl_pattern_analysis: Dict[str, Any]
    predictive_insights: Dict[str, str]
    optimization_opportunities: List[Dict[str, Any]]
    competitive_analysis: Optional[Dict[str, Any]] = None


@dataclass
class URLQueueManager:
    """Advanced URL queue management with priority and throttling"""
    high_priority: List[Tuple[str, float]] = field(default_factory=list)
    medium_priority: List[Tuple[str, float]] = field(default_factory=list)
    low_priority: List[Tuple[str, float]] = field(default_factory=list)
    failed_urls: Dict[str, List[datetime]] = field(default_factory=dict)
    rate_limits: Dict[str, float] = field(default_factory=dict)
    last_access: Dict[str, datetime] = field(default_factory=dict)
    max_retries: int = 3
    retry_delay_base: float = 2.0
    
    def add_url(self, url: str, priority: float, depth: int = 0):
        """Add URL to appropriate priority queue"""
        parsed = urlparse(url)
        domain = parsed.netloc
        
        # Check rate limiting
        if self._is_rate_limited(domain):
            return False
        
        # Adjust priority based on depth and domain authority
        adjusted_priority = priority * (0.9 ** depth)
        
        url_tuple = (url, adjusted_priority)
        
        if priority >= 0.8:
            self.high_priority.append(url_tuple)
        elif priority >= 0.5:
            self.medium_priority.append(url_tuple)
        else:
            self.low_priority.append(url_tuple)
        
        return True
    
    def get_next_url(self) -> Optional[Tuple[str, float]]:
        """Get next URL from priority queues"""
        # Sort queues by priority
        self.high_priority.sort(key=lambda x: x[1], reverse=True)
        self.medium_priority.sort(key=lambda x: x[1], reverse=True)
        self.low_priority.sort(key=lambda x: x[1], reverse=True)
        
        # Return from highest priority available
        if self.high_priority:
            return self.high_priority.pop(0)
        elif self.medium_priority:
            return self.medium_priority.pop(0)
        elif self.low_priority:
            return self.low_priority.pop(0)
        
        return None
    
    def mark_failed(self, url: str):
        """Mark URL as failed for retry logic"""
        if url not in self.failed_urls:
            self.failed_urls[url] = []
        self.failed_urls[url].append(datetime.utcnow())
    
    def can_retry(self, url: str) -> bool:
        """Check if URL can be retried"""
        if url not in self.failed_urls:
            return True
        
        failures = self.failed_urls[url]
        if len(failures) >= self.max_retries:
            return False
        
        # Exponential backoff
        last_failure = failures[-1]
        delay = self.retry_delay_base ** len(failures)
        return (datetime.utcnow() - last_failure).total_seconds() > delay * 60
    
    def _is_rate_limited(self, domain: str) -> bool:
        """Check if domain is rate limited"""
        if domain not in self.last_access:
            self.last_access[domain] = datetime.utcnow()
            return False
        
        min_delay = self.rate_limits.get(domain, 1.0)
        elapsed = (datetime.utcnow() - self.last_access[domain]).total_seconds()
        
        if elapsed < min_delay:
            return True
        
        self.last_access[domain] = datetime.utcnow()
        return False

@dataclass
class ContentExtractionPipeline:
    """Advanced content extraction and processing pipeline"""
    extractors: List[str] = field(default_factory=lambda: ['text', 'metadata', 'links', 'images'])
    filters: List[str] = field(default_factory=lambda: ['length', 'quality', 'language'])
    enrichers: List[str] = field(default_factory=lambda: ['keywords', 'topics', 'sentiment'])
    
    async def process(self, soup: BeautifulSoup, url: str, config: Dict) -> Dict[str, Any]:
        """Process content through extraction pipeline"""
        result = {
            'url': url,
            'processed_at': datetime.utcnow(),
            'pipeline_version': '2.0'
        }
        
        # Content extraction phase
        for extractor in self.extractors:
            try:
                if extractor == 'text':
                    result['text_content'] = self._extract_enhanced_text(soup, config)
                elif extractor == 'metadata':
                    result['metadata'] = self._extract_comprehensive_metadata(soup, url)
                elif extractor == 'links':
                    result['links'] = self._extract_categorized_links(soup, url)
                elif extractor == 'images':
                    result['images'] = self._extract_image_metadata(soup, url)
                elif extractor == 'forms':
                    result['forms'] = self._extract_form_metadata(soup)
                elif extractor == 'tables':
                    result['tables'] = self._extract_table_data(soup)
            except Exception as e:
                logger.warning(f"Extractor {extractor} failed for {url}: {e}")
        
        # Content filtering phase
        for filter_name in self.filters:
            try:
                if filter_name == 'length':
                    if not self._passes_length_filter(result, config):
                        result['filtered_reason'] = 'content_too_short'
                        return result
                elif filter_name == 'quality':
                    quality_score = self._calculate_quality_score(result)
                    result['quality_score'] = quality_score
                    if quality_score < config.get('min_quality_score', 0.3):
                        result['filtered_reason'] = 'low_quality'
                        return result
                elif filter_name == 'language':
                    language = self._detect_language(result.get('text_content', ''))
                    result['detected_language'] = language
                    allowed_languages = config.get('allowed_languages', [])
                    if allowed_languages and language not in allowed_languages:
                        result['filtered_reason'] = 'language_mismatch'
                        return result
            except Exception as e:
                logger.warning(f"Filter {filter_name} failed for {url}: {e}")
        
        # Content enrichment phase
        for enricher in self.enrichers:
            try:
                if enricher == 'keywords':
                    result['extracted_keywords'] = self._extract_keywords(result.get('text_content', ''))
                elif enricher == 'topics':
                    result['topic_categories'] = self._categorize_content(result.get('text_content', ''))
                elif enricher == 'sentiment':
                    result['sentiment_analysis'] = self._analyze_sentiment(result.get('text_content', ''))
                elif enricher == 'readability':
                    result['readability_metrics'] = self._calculate_readability(result.get('text_content', ''))
            except Exception as e:
                logger.warning(f"Enricher {enricher} failed for {url}: {e}")
        
        result['status'] = 'success'
        return result
    
    def _extract_enhanced_text(self, soup: BeautifulSoup, config: Dict) -> str:
        """Enhanced text extraction with advanced filtering"""
        # Advanced content area detection
        content_selectors = [
            'main', 'article', '[role="main"]', '.main-content',
            '.content', '.post-content', '.entry-content',
            '.article-content', '.page-content', '#content'
        ]
        
        main_content = None
        for selector in content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body') or soup
        
        # Remove noise elements
        noise_selectors = [
            'script', 'style', 'nav', 'header', 'footer',
            '.advertisement', '.sidebar', '.widget', '.popup',
            '.cookie-notice', '.social-share', '.comments'
        ]
        
        for selector in noise_selectors:
            for element in main_content.select(selector):
                element.decompose()
        
        # Extract and clean text
        text = main_content.get_text(separator=' ', strip=True)
        
        # Advanced text cleaning
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common noise patterns
        text = re.sub(r'(?i)(skip to|jump to|go to) (content|navigation|main)', '', text)
        text = re.sub(r'(?i)(click here|read more|learn more)(?!\w)', '', text)
        text = re.sub(r'(?i)copyright \d{4}.*?all rights reserved', '', text)
        
        return text.strip()
    
    def _extract_image_metadata(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract comprehensive image metadata"""
        images = []
        for img in soup.find_all('img'):
            if img.get('src'):
                img_url = urljoin(base_url, img.get('src'))
                images.append({
                    'url': img_url,
                    'alt_text': img.get('alt', ''),
                    'title': img.get('title', ''),
                    'width': img.get('width'),
                    'height': img.get('height'),
                    'loading': img.get('loading', ''),
                    'srcset': img.get('srcset', ''),
                    'sizes': img.get('sizes', '')
                })
        return images[:20]  # Limit to prevent huge metadata
    
    def _extract_form_metadata(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract form structure for interaction potential"""
        forms = []
        for form in soup.find_all('form'):
            form_data = {
                'action': form.get('action', ''),
                'method': form.get('method', 'get').lower(),
                'fields': []
            }
            
            for field in form.find_all(['input', 'textarea', 'select']):
                field_data = {
                    'type': field.get('type', field.name),
                    'name': field.get('name', ''),
                    'required': field.has_attr('required'),
                    'placeholder': field.get('placeholder', '')
                }
                form_data['fields'].append(field_data)
            
            forms.append(form_data)
        
        return forms[:5]  # Limit form count
    
    def _extract_table_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract structured table data"""
        tables = []
        for table in soup.find_all('table')[:5]:  # Limit tables
            rows = []
            for tr in table.find_all('tr')[:10]:  # Limit rows
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            
            if rows:
                tables.append({
                    'headers': rows[0] if rows else [],
                    'rows': rows[1:] if len(rows) > 1 else [],
                    'row_count': len(rows),
                    'column_count': len(rows[0]) if rows else 0
                })
        
        return tables
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords using simple frequency analysis"""
        if not text or len(text) < 100:
            return []
        
        import re
        from collections import Counter
        
        # Simple keyword extraction (in production, use NLTK or spaCy)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Filter out common stop words
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'this', 'that', 'are', 'was', 'were', 'been', 'have',
            'has', 'had', 'will', 'would', 'could', 'should', 'may', 'might'
        }
        
        filtered_words = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Get most common words
        counter = Counter(filtered_words)
        return [word for word, count in counter.most_common(10) if count > 1]
    
    def _categorize_content(self, text: str) -> List[str]:
        """Simple content categorization"""
        if not text:
            return []
        
        categories = []
        text_lower = text.lower()
        
        # Technical content indicators
        tech_keywords = ['api', 'documentation', 'code', 'programming', 'development', 'software']
        if any(keyword in text_lower for keyword in tech_keywords):
            categories.append('technical')
        
        # Business content indicators
        business_keywords = ['company', 'business', 'product', 'service', 'customer', 'solution']
        if any(keyword in text_lower for keyword in business_keywords):
            categories.append('business')
        
        # Support content indicators
        support_keywords = ['help', 'support', 'faq', 'troubleshoot', 'guide', 'tutorial']
        if any(keyword in text_lower for keyword in support_keywords):
            categories.append('support')
        
        return categories
    
    def _analyze_sentiment(self, text: str) -> Dict[str, float]:
        """Simple sentiment analysis"""
        if not text:
            return {'neutral': 1.0}
        
        # Simple word-based sentiment (in production, use proper NLP)
        positive_words = ['good', 'great', 'excellent', 'amazing', 'fantastic', 'wonderful', 'best']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'worst', 'disappointing']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return {'neutral': 1.0}
        
        return {
            'positive': positive_count / total,
            'negative': negative_count / total,
            'neutral': max(0, 1 - (positive_count + negative_count) / len(text.split()) * 10)
        }

    def _extract_comprehensive_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract comprehensive metadata (reusing existing method)"""
        # This method already exists in the main class, so we'll call it
        # For now, return basic metadata - can be enhanced later
        metadata = {'url': url}
        
        # Basic metadata
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
        
        return metadata
    
    def _extract_categorized_links(self, soup: BeautifulSoup, base_url: str) -> Dict:
        """Extract and categorize links"""
        internal_links = []
        external_links = []
        
        parsed_base = urlparse(base_url)
        base_domain = parsed_base.netloc
        
        for link in soup.find_all('a', href=True)[:50]:  # Limit to prevent huge metadata
            href = link.get('href')
            if href:
                absolute_url = urljoin(base_url, href)
                link_domain = urlparse(absolute_url).netloc
                
                link_data = {
                    'url': absolute_url,
                    'text': link.get_text().strip()[:100],  # Limit text length
                    'title': link.get('title', '')
                }
                
                if link_domain == base_domain:
                    internal_links.append(link_data)
                else:
                    external_links.append(link_data)
        
        return {
            'internal': internal_links[:20],  # Limit counts
            'external': external_links[:10]
        }
    
    def _passes_length_filter(self, result: Dict, config: Dict) -> bool:
        """Check if content passes length filter"""
        text_content = result.get('text_content', '')
        min_word_count = config.get('min_word_count', 10)
        word_count = len(text_content.split())
        return word_count >= min_word_count
    
    def _calculate_quality_score(self, result: Dict) -> float:
        """Calculate content quality score"""
        text_content = result.get('text_content', '')
        if not text_content:
            return 0.0
        
        score = 0.0
        
        # Length score (0-0.3)
        word_count = len(text_content.split())
        if word_count > 100:
            score += 0.3
        elif word_count > 50:
            score += 0.2
        elif word_count > 20:
            score += 0.1
        
        # Structure score (0-0.3)
        metadata = result.get('metadata', {})
        if metadata.get('title'):
            score += 0.1
        if metadata.get('description'):
            score += 0.1
        if result.get('images') and len(result['images']) > 0:
            score += 0.05
        if result.get('tables') and len(result['tables']) > 0:
            score += 0.05
        
        # Content richness score (0-0.4)
        if result.get('extracted_keywords') and len(result['extracted_keywords']) > 3:
            score += 0.2
        if result.get('topic_categories') and len(result['topic_categories']) > 0:
            score += 0.1
        if result.get('links', {}).get('internal') and len(result['links']['internal']) > 2:
            score += 0.1
        
        return min(1.0, score)
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection"""
        if not text:
            return 'unknown'
        
        # Very basic language detection based on common words
        # In production, use langdetect or similar library
        english_words = ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with']
        spanish_words = ['el', 'la', 'de', 'que', 'y', 'en', 'un', 'es', 'se', 'no', 'te']
        french_words = ['le', 'de', 'et', 'à', 'un', 'il', 'être', 'et', 'en', 'avoir', 'que']
        
        text_lower = text.lower()
        
        english_count = sum(1 for word in english_words if word in text_lower)
        spanish_count = sum(1 for word in spanish_words if word in text_lower)
        french_count = sum(1 for word in french_words if word in text_lower)
        
        if english_count >= spanish_count and english_count >= french_count:
            return 'en'
        elif spanish_count >= french_count:
            return 'es'
        elif french_count > 0:
            return 'fr'
        else:
            return 'unknown'
    
    def _calculate_readability(self, text: str) -> Dict[str, float]:
        """Calculate readability metrics"""
        if not text:
            return {'readability_score': 0.0, 'complexity': 'unknown'}
        
        # Simple readability calculation
        sentences = len([s for s in text.split('.') if s.strip()])
        words = len(text.split())
        characters = len(text)
        
        if sentences == 0 or words == 0:
            return {'readability_score': 0.0, 'complexity': 'unknown'}
        
        avg_sentence_length = words / sentences
        avg_word_length = characters / words
        
        # Simplified Flesch Reading Ease
        score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length)
        normalized_score = max(0.0, min(1.0, score / 100))
        
        if score >= 60:
            complexity = 'easy'
        elif score >= 30:
            complexity = 'medium'
        else:
            complexity = 'difficult'
        
        return {
            'readability_score': normalized_score,
            'complexity': complexity,
            'avg_sentence_length': avg_sentence_length,
            'avg_word_length': avg_word_length
        }

@dataclass 
class SmartRetryMechanism:
    """Intelligent retry mechanism with adaptive backoff"""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    def __init__(self):
        self.retry_history: Dict[str, List[Dict]] = {}
        self.domain_health: Dict[str, float] = {}
    
    async def execute_with_retry(self, url: str, fetch_func, *args, **kwargs):
        """Execute function with intelligent retry logic"""
        domain = urlparse(url).netloc
        attempt = 0
        last_exception = None
        
        while attempt < self.max_retries:
            try:
                # Adjust request based on domain health
                if domain in self.domain_health:
                    health_score = self.domain_health[domain]
                    if health_score < 0.5:
                        # Slow down requests to unhealthy domains
                        await asyncio.sleep(2.0)
                
                result = await fetch_func(url, *args, **kwargs)
                
                # Update domain health on success
                self._update_domain_health(domain, True)
                return result
                
            except Exception as e:
                last_exception = e
                attempt += 1
                
                # Log retry attempt
                self._log_retry_attempt(url, attempt, str(e))
                
                # Update domain health on failure
                self._update_domain_health(domain, False)
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, domain)
                    logger.info(f"Retrying {url} in {delay:.1f}s (attempt {attempt}/{self.max_retries})")
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        logger.error(f"All retries exhausted for {url}: {last_exception}")
        raise last_exception
    
    def _calculate_delay(self, attempt: int, domain: str) -> float:
        """Calculate adaptive delay based on attempt and domain health"""
        base_delay = self.base_delay * (self.backoff_factor ** (attempt - 1))
        
        # Adjust delay based on domain health
        if domain in self.domain_health:
            health_score = self.domain_health[domain]
            base_delay *= (2.0 - health_score)  # Slower for unhealthy domains
        
        # Add jitter to prevent thundering herd
        if self.jitter:
            import random
            jitter_factor = 0.1 * random.random()
            base_delay *= (1 + jitter_factor)
        
        return min(base_delay, self.max_delay)
    
    def _update_domain_health(self, domain: str, success: bool):
        """Update domain health score"""
        if domain not in self.domain_health:
            self.domain_health[domain] = 0.8
        
        current_health = self.domain_health[domain]
        
        if success:
            # Gradually improve health on success
            self.domain_health[domain] = min(1.0, current_health + 0.1)
        else:
            # Penalize health on failure
            self.domain_health[domain] = max(0.1, current_health - 0.2)
    
    def _log_retry_attempt(self, url: str, attempt: int, error: str):
        """Log retry attempt for analysis"""
        if url not in self.retry_history:
            self.retry_history[url] = []
        
        self.retry_history[url].append({
            'attempt': attempt,
            'timestamp': datetime.utcnow(),
            'error': error
        })


class WebScraperConnector(BaseConnector):
    """Enhanced web scraper connector with comprehensive features"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        
        # Initialize advanced components
        self.url_queue_manager = URLQueueManager()
        self.content_pipeline = ContentExtractionPipeline()
        self.retry_mechanism = SmartRetryMechanism()
        
        self.visited_urls: Set[str] = set()
        self.session: Optional[aiohttp.ClientSession] = None
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.performance_metrics = CrawlPerformanceMetrics()
        self.content_cache: Dict[str, Dict] = {}  # URL -> cached content
        
        # Enhanced features
        self.url_intelligence: Dict[str, URLIntelligence] = {}
        self.content_hashes: Set[str] = set()  # For duplicate detection
        self.crawl_session: Optional[CrawlSession] = None
        self.smart_scheduling = SmartScheduling(
            optimal_times=[9, 14, 19],  # Default optimal crawl times
            content_change_frequency={},
            priority_urls=[],
            backoff_urls={},
            seasonal_patterns={}
        )
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Security and automation features
        self.security_config = SecurityConfig()
        self.retry_strategy = RetryStrategy()
        self.automation_rules: List[AutomationRule] = []
        self.current_proxy_index = 0
        self.current_user_agent_index = 0
        self.request_count = 0
        self.session_request_count = 0
        self.circuit_breaker_state = {}  # URL -> failure count
        self.proxy_sessions: Dict[str, aiohttp.ClientSession] = {}
        
        # Extract configuration
        auth_config = config.auth_config or {}
        self.start_urls = auth_config.get('start_urls', '').split(',')
        self.start_urls = [url.strip() for url in self.start_urls if url.strip()]
        self.max_depth = int(auth_config.get('max_depth', 2))
        self.max_pages = int(auth_config.get('max_pages', 100))
        self.delay_ms = int(auth_config.get('delay_ms', 1000))
        self.delay = self.delay_ms / 1000.0
        
        # Advanced configuration
        self.include_patterns = auth_config.get('include_patterns', [])
        self.exclude_patterns = auth_config.get('exclude_patterns', [])
        self.follow_external = auth_config.get('follow_external', False)
        self.respect_robots = auth_config.get('respect_robots', True)
        self.max_file_size = auth_config.get('max_file_size', 5 * 1024 * 1024)
        
        # Enhanced features configuration
        self.duplicate_threshold = auth_config.get('duplicate_threshold', 0.85)
        self.quality_threshold = auth_config.get('quality_threshold', 0.3)
        self.intelligent_discovery = auth_config.get('intelligent_discovery', True)
        self.real_time_monitoring = auth_config.get('real_time_monitoring', True)
        self.adaptive_scheduling = auth_config.get('adaptive_scheduling', True)
        
        # Security configuration
        self._configure_security(auth_config)
        self._configure_retry_strategy(auth_config)
        
        # User agent and scheduling
        self.user_agent = auth_config.get('user_agent', 'CortexQ-Bot/1.0')
        self.schedule = CrawlSchedule(
            enabled=auth_config.get('schedule_enabled', False),
            frequency_hours=auth_config.get('crawl_frequency_hours', 24),
            max_concurrent_crawls=auth_config.get('max_concurrent_crawls', 3),
            retry_failed_pages=auth_config.get('retry_failed_pages', True),
            incremental_crawl=auth_config.get('incremental_crawl', True)
        )
        
        # Content quality thresholds
        self.min_word_count = auth_config.get('min_word_count', 10)
        self.content_filters = auth_config.get('content_filters', {})
    
        self.crawl_session = None
        self.content_cache = {}
        self.url_intelligence_cache = {}
        
        # Enhanced monitoring and alerting
        self.alert_rules: List[AlertRule] = []
        self.active_alerts: List[PerformanceAlert] = []
        self.webhook_notifications: List[WebhookNotification] = []
        self.health_history: List[Tuple[datetime, CrawlHealthMetrics]] = []
        self.performance_baseline: Dict[str, float] = {}
        
        # Advanced analytics
        self.analytics_data: Dict[str, Any] = {}
        self.trend_analysis: Dict[str, List[float]] = {
            'response_times': [],
            'success_rates': [],
            'quality_scores': [],
            'content_freshness': []
        }
    
        # Enhanced configuration options
        self.enable_advanced_pipeline = self.config.auth_config.get('enable_advanced_pipeline', True)
        self.enable_smart_retry = self.config.auth_config.get('enable_smart_retry', True)
        self.enable_url_queue_management = self.config.auth_config.get('enable_url_queue_management', True)
        
        # Content extraction settings
        pipeline_config = self.config.auth_config.get('content_pipeline', {})
        if pipeline_config:
            self.content_pipeline.extractors = pipeline_config.get('extractors', self.content_pipeline.extractors)
            self.content_pipeline.filters = pipeline_config.get('filters', self.content_pipeline.filters)
            self.content_pipeline.enrichers = pipeline_config.get('enrichers', self.content_pipeline.enrichers)

    def _configure_security(self, auth_config: Dict):
        """Configure security settings"""
        security_config = auth_config.get('security', {})
        
        self.security_config.proxy_rotation = security_config.get('proxy_rotation', False)
        self.security_config.proxy_list = security_config.get('proxy_list', [])
        self.security_config.user_agent_rotation = security_config.get('user_agent_rotation', True)
        self.security_config.stealth_mode = security_config.get('stealth_mode', False)
        self.security_config.captcha_detection = security_config.get('captcha_detection', True)
        self.security_config.bot_detection_evasion = security_config.get('bot_detection_evasion', True)
        
        # Default user agents for rotation
        if not self.security_config.custom_user_agents:
            self.security_config.custom_user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            ]
    
    def _configure_retry_strategy(self, auth_config: Dict):
        """Configure retry strategy"""
        retry_config = auth_config.get('retry_strategy', {})
        
        self.retry_strategy.max_retries = retry_config.get('max_retries', 3)
        self.retry_strategy.base_delay = retry_config.get('base_delay', 1.0)
        self.retry_strategy.exponential_backoff = retry_config.get('exponential_backoff', True)
        self.retry_strategy.retry_on_status = retry_config.get('retry_on_status', [429, 500, 502, 503, 504])
        self.retry_strategy.circuit_breaker_threshold = retry_config.get('circuit_breaker_threshold', 5)
    
    def _get_next_proxy(self) -> Optional[str]:
        """Get next proxy from rotation list"""
        if not self.security_config.proxy_rotation or not self.security_config.proxy_list:
            return None
        
        proxy = self.security_config.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.security_config.proxy_list)
        return proxy
    
    def _get_next_user_agent(self) -> str:
        """Get next user agent from rotation list"""
        if not self.security_config.user_agent_rotation or not self.security_config.custom_user_agents:
            return self.user_agent
        
        user_agent = self.security_config.custom_user_agents[self.current_user_agent_index]
        self.current_user_agent_index = (self.current_user_agent_index + 1) % len(self.security_config.custom_user_agents)
        return user_agent
    
    async def _create_secure_session(self) -> aiohttp.ClientSession:
        """Create a secure HTTP session with anti-detection features"""
        headers = {
            'User-Agent': self._get_next_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Add stealth headers if enabled
        if self.security_config.stealth_mode:
            headers.update({
                'Cache-Control': 'max-age=0',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
            })
        
        # Configure SSL context
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        if self.security_config.stealth_mode:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        
        # Configure connector with proxy if available
        proxy = self._get_next_proxy()
        connector_kwargs = {
            'ssl': ssl_context,
            'limit': 10,
            'limit_per_host': 5,
            'enable_cleanup_closed': True,
        }
        
        if proxy:
            connector_kwargs['trust_env'] = True
        
        connector = aiohttp.TCPConnector(**connector_kwargs)
        
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        session_kwargs = {
            'connector': connector,
            'timeout': timeout,
            'headers': headers,
        }
        
        if proxy:
            session_kwargs['trust_env'] = True
        
        return aiohttp.ClientSession(**session_kwargs)
    
    async def _detect_captcha_or_block(self, response: aiohttp.ClientResponse, content: str) -> bool:
        """Detect if the response contains a CAPTCHA or bot detection"""
        if not self.security_config.captcha_detection:
            return False
        
        # Check status codes that indicate blocking
        if response.status in [403, 429, 503]:
            return True
        
        # Check for common CAPTCHA/bot detection patterns
        captcha_indicators = [
            'captcha', 'recaptcha', 'hcaptcha', 'prove you are human',
            'robot', 'automated', 'suspicious activity', 'blocked',
            'access denied', 'rate limit', 'verify you are not a robot'
        ]
        
        content_lower = content.lower()
        for indicator in captcha_indicators:
            if indicator in content_lower:
                logger.warning(f"Potential CAPTCHA/blocking detected: {indicator}")
                return True
        
        return False
    
    async def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic and circuit breaker"""
        url = args[0] if args else kwargs.get('url', 'unknown')
        
        # Check circuit breaker
        if url in self.circuit_breaker_state:
            failure_count, last_failure = self.circuit_breaker_state[url]
            if failure_count >= self.retry_strategy.circuit_breaker_threshold:
                if datetime.now() - last_failure < timedelta(seconds=self.retry_strategy.circuit_breaker_timeout):
                    logger.warning(f"Circuit breaker open for {url}")
                    return None
                else:
                    # Reset circuit breaker
                    del self.circuit_breaker_state[url]
        
        last_exception = None
        
        for attempt in range(self.retry_strategy.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                # Reset circuit breaker on success
                if url in self.circuit_breaker_state:
                    del self.circuit_breaker_state[url]
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Update circuit breaker
                if url not in self.circuit_breaker_state:
                    self.circuit_breaker_state[url] = [0, datetime.now()]
                
                self.circuit_breaker_state[url][0] += 1
                self.circuit_breaker_state[url][1] = datetime.now()
                
                if attempt < self.retry_strategy.max_retries:
                    # Calculate delay with exponential backoff and jitter
                    delay = self.retry_strategy.base_delay
                    if self.retry_strategy.exponential_backoff:
                        delay *= (self.retry_strategy.backoff_multiplier ** attempt)
                    
                    if self.retry_strategy.jitter:
                        delay *= (0.5 + random.random() * 0.5)  # 50-100% of calculated delay
                    
                    logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}. Retrying in {delay:.2f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"All retry attempts failed for {url}: {str(e)}")
        
        return None
    
    def _classify_content_ml(self, content: str, metadata: Dict) -> ContentClassification:
        """ML-based content classification (simplified implementation)"""
        # This is a simplified version - in production, you'd use actual ML models
        
        # Basic content type detection
        content_lower = content.lower()
        
        # Detect content type
        if any(term in content_lower for term in ['add to cart', 'buy now', 'price', '$', '€', '£']):
            content_type = 'product'
            commercial_intent = 0.8
        elif any(term in content_lower for term in ['about', 'contact', 'privacy', 'terms']):
            content_type = 'navigation'
            commercial_intent = 0.1
        elif any(term in content_lower for term in ['news', 'article', 'story', 'published']):
            content_type = 'article'
            commercial_intent = 0.2
        else:
            content_type = 'content'
            commercial_intent = 0.3
        
        # Basic topic extraction (simplified)
        topics = []
        tech_keywords = ['technology', 'software', 'programming', 'development', 'api', 'database']
        business_keywords = ['business', 'marketing', 'sales', 'finance', 'strategy']
        
        if any(keyword in content_lower for keyword in tech_keywords):
            topics.append('technology')
        if any(keyword in content_lower for keyword in business_keywords):
            topics.append('business')
        
        # Sentiment analysis (very basic)
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointing']
        
        positive_count = sum(1 for word in positive_words if word in content_lower)
        negative_count = sum(1 for word in negative_words if word in content_lower)
        
        if positive_count > negative_count:
            sentiment_score = 0.3 + (positive_count - negative_count) * 0.1
        elif negative_count > positive_count:
            sentiment_score = -0.3 - (negative_count - positive_count) * 0.1
        else:
            sentiment_score = 0.0
        
        sentiment_score = max(-1.0, min(1.0, sentiment_score))
        
        # Simple entity extraction (basic implementation)
        entities = []
        # Look for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        for email in emails:
            entities.append({'type': 'email', 'value': email})
        
        # Look for phone numbers (simple pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, content)
        for phone in phones:
            entities.append({'type': 'phone', 'value': phone})
        
        # Language confidence (simplified - just check for English indicators)
        english_indicators = ['the', 'and', 'of', 'to', 'a', 'in', 'for', 'is', 'on', 'that']
        english_count = sum(1 for indicator in english_indicators if indicator in content_lower.split())
        total_words = len(content_lower.split())
        language_confidence = min(1.0, english_count / max(1, total_words) * 10)
        
        # Readability level (simplified Flesch reading ease)
        sentences = len(re.split(r'[.!?]+', content))
        words = len(content.split())
        syllables = sum(len(re.findall(r'[aeiouAEIOU]', word)) for word in content.split())
        
        if sentences > 0 and words > 0:
            avg_sentence_length = words / sentences
            avg_syllables_per_word = syllables / words
            flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            
            if flesch_score >= 60:
                readability_level = 'elementary'
            elif flesch_score >= 30:
                readability_level = 'intermediate'
            else:
                readability_level = 'advanced'
        else:
            readability_level = 'intermediate'
        
        return ContentClassification(
            content_type=content_type,
            topic_categories=topics,
            sentiment_score=sentiment_score,
            entity_extraction=entities,
            language_confidence=language_confidence,
            readability_level=readability_level,
            commercial_intent=commercial_intent
        )
    
    def add_automation_rule(self, rule: AutomationRule):
        """Add an automation rule"""
        self.automation_rules.append(rule)
        logger.info(f"Added automation rule: {rule.trigger_type}")
    
    async def check_automation_triggers(self, db: Session, connector_id: str, organization_id: str) -> List[Dict[str, Any]]:
        """Check if any automation rules should be triggered"""
        triggered_actions = []
        
        for rule in self.automation_rules:
            if not rule.enabled:
                continue
            
            should_trigger = False
            
            if rule.trigger_type == "time_based":
                frequency_hours = rule.trigger_conditions.get('frequency_hours', 24)
                if not rule.last_triggered or datetime.now() - rule.last_triggered >= timedelta(hours=frequency_hours):
                    should_trigger = True
            
            elif rule.trigger_type == "content_change":
                # Check if content has changed significantly
                threshold = rule.trigger_conditions.get('change_threshold', 0.1)
                # This would require implementing content change detection
                should_trigger = False  # Placeholder
            
            elif rule.trigger_type == "event_based":
                # Check for specific events (errors, quality drops, etc.)
                should_trigger = False  # Placeholder
            
            if should_trigger:
                rule.last_triggered = datetime.now()
                rule.execution_count += 1
                
                triggered_actions.append({
                    'rule_id': f"rule_{len(self.automation_rules)}",
                    'trigger_type': rule.trigger_type,
                    'actions': rule.actions,
                    'priority': rule.priority,
                    'triggered_at': datetime.now(),
                    'execution_count': rule.execution_count
                })
        
        return triggered_actions
    
    async def authenticate(self) -> Tuple[bool, Optional[str]]:
        """Authenticate for web scraping (always returns True as no auth required)"""
        try:
            # Web scraping typically doesn't require authentication
            # This method is here to satisfy the BaseConnector interface
            # For future enhancement, could add proxy auth, API key validation, etc.
            return True, None
        except Exception as e:
            return False, f"Authentication error: {str(e)}"
    
    async def test_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """Test the web scraper configuration"""
        try:
            if not self.start_urls:
                return False, {"error": "No start URLs provided"}
            
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'User-Agent': self.user_agent}
            ) as session:
                results = {}
                
                for url in self.start_urls:
                    try:
                        async with session.head(url) as response:
                            results[url] = {
                                "status": response.status,
                                "accessible": response.status == 200,
                                "content_type": response.headers.get('content-type', ''),
                                "robots_allowed": await self._check_robots_txt(url, session)
                            }
                    except Exception as e:
                        results[url] = {
                            "status": 0,
                            "accessible": False,
                            "error": str(e),
                            "robots_allowed": False
                        }
                
                accessible_count = sum(1 for r in results.values() if r.get('accessible', False))
                
                return accessible_count > 0, {
                    "accessible_urls": accessible_count,
                    "total_urls": len(self.start_urls),
                    "url_results": results,
                    "configuration": {
                        "max_depth": self.max_depth,
                        "max_pages": self.max_pages,
                        "delay": self.delay,
                        "respect_robots": self.respect_robots,
                        "follow_external": self.follow_external
                    }
                }
                
        except Exception as e:
            return False, {"error": f"Connection test failed: {str(e)}"}
    
    async def preview_crawl(self) -> CrawlPreview:
        """Preview what URLs would be crawled without actually crawling them"""
        discovered_urls = []
        allowed_urls = []
        blocked_urls = []
        robots_blocked = []
        external_urls = []
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            # Discover URLs from start pages
            for start_url in self.start_urls:
                try:
                    discovered = await self._discover_urls_from_page(start_url, session)
                    discovered_urls.extend(discovered)
                except Exception as e:
                    logger.warning(f"Failed to discover URLs from {start_url}: {e}")
            
            # Remove duplicates
            unique_urls = list(set(discovered_urls))
            
            # Categorize URLs
            for url in unique_urls:
                if self._is_external_url(url):
                    external_urls.append(url)
                    if not self.follow_external:
                        blocked_urls.append(url)
                        continue
                
                if not self._matches_patterns(url):
                    blocked_urls.append(url)
                    continue
                
                if self.respect_robots and not await self._check_robots_txt(url, session):
                    robots_blocked.append(url)
                    continue
                
                allowed_urls.append(url)
        
        # Estimate crawl duration
        estimated_pages = min(len(allowed_urls), self.max_pages)
        estimated_duration_seconds = estimated_pages * self.delay
        estimated_duration = self._format_duration(estimated_duration_seconds)
        
        return CrawlPreview(
            discovered_urls=unique_urls,
            allowed_urls=allowed_urls,
            blocked_urls=blocked_urls,
            robots_blocked=robots_blocked,
            external_urls=external_urls,
            estimated_pages=estimated_pages,
            estimated_duration=estimated_duration
        )
    
    async def fetch_data(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch data from websites"""
        crawled_data = []
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': self.user_agent}
        ) as session:
            self.session = session
            
            # Start crawling from start URLs
            url_queue = [(url, 0) for url in self.start_urls]
            processed_count = 0
            
            while url_queue and processed_count < self.max_pages:
                current_url, depth = url_queue.pop(0)
                
                if (current_url in self.visited_urls or 
                    depth > self.max_depth or
                    not self._matches_patterns(current_url)):
                    continue
                
                if self.respect_robots and not await self._check_robots_txt(current_url, session):
                    continue
                
                try:
                    page_data = await self._crawl_page(current_url, session)
                    if page_data:
                        crawled_data.append(page_data)
                        self.visited_urls.add(current_url)
                        processed_count += 1
                        
                        # Extract and queue new URLs if within depth limit
                        if depth < self.max_depth:
                            new_urls = await self._extract_links(page_data.get('content', ''), current_url, session)
                            for new_url in new_urls:
                                if new_url not in self.visited_urls:
                                    url_queue.append((new_url, depth + 1))
                    
                    # Respect crawl delay
                    await asyncio.sleep(self.delay)
                    
                except Exception as e:
                    logger.error(f"Error crawling {current_url}: {e}")
                    continue
        
        return crawled_data
    
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Document]:
        """Transform crawled data to documents"""
        documents = []
        
        for item in raw_data:
            try:
                # Create document
                doc = Document(
                    title=item.get('title', ''),
                    content=item.get('content', ''),
                    metadata={
                        'source_type': 'web_scraper',
                        'url': item.get('url', ''),
                        'crawled_at': item.get('crawled_at', datetime.utcnow()).isoformat(),
                        'content_hash': item.get('content_hash', ''),
                        'word_count': item.get('word_count', 0),
                        'content_type': item.get('content_type', 'text/html'),
                        'domain': urlparse(item.get('url', '')).netloc,
                        'depth': item.get('depth', 0),
                        'description': item.get('metadata', {}).get('description', ''),
                        'keywords': item.get('metadata', {}).get('keywords', ''),
                        'language': item.get('metadata', {}).get('language', ''),
                        'headings': item.get('metadata', {}).get('headings', [])
                    },
                    organization_id=self.config.organization_id,
                    domain=self.config.domain
                )
                documents.append(doc)
                
            except Exception as e:
                logger.error(f"Error transforming document from {item.get('url', 'unknown')}: {e}")
                continue
        
        return documents
    
    async def _discover_urls_from_page(self, url: str, session: aiohttp.ClientSession) -> List[str]:
        """Discover URLs from a single page without processing content"""
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return []
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return []
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute_url = urljoin(url, href)
                    
                    # Clean up URL
                    parsed = urlparse(absolute_url)
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
                    
                    if clean_url and clean_url not in links:
                        links.append(clean_url)
                
                return links
                
        except Exception as e:
            logger.warning(f"Failed to discover URLs from {url}: {e}")
            return []
    
    async def _crawl_page(self, url: str, session: aiohttp.ClientSession) -> Optional[Dict[str, Any]]:
        """Crawl a single page and extract content"""
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return None
                
                # Check file size
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.max_file_size:
                    logger.warning(f"Skipping {url}: file too large ({content_length} bytes)")
                    return None
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract text content
                text_content = self._extract_text(soup)
                
                # Skip if content is too short
                if not text_content:
                    return None
                
                # Extract metadata
                metadata = self._extract_metadata(soup, url)
                
                page_data = {
                    'url': url,
                    'title': metadata.get('title', ''),
                    'content': text_content,
                    'metadata': metadata,
                    'crawled_at': datetime.utcnow(),
                    'content_hash': hashlib.md5(text_content.encode()).hexdigest(),
                    'word_count': len(text_content.split()),
                    'content_type': content_type,
                    'file_size': len(html_content.encode('utf-8')),
                    'status': 'success'
                }
                
                # Calculate content quality score
                page_data['quality_score'] = self._calculate_enhanced_content_score(page_data)
                
                return page_data
                
        except Exception as e:
            logger.error(f"Error processing page {url}: {e}")
            return {
                'url': url,
                'title': '',
                'content': '',
                'metadata': {'url': url},
                'crawled_at': datetime.utcnow(),
                'content_hash': '',
                'word_count': 0,
                'content_type': '',
                'file_size': 0,
                'status': 'failed',
                'error_message': str(e),
                'quality_score': 0.0
            }
    
    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from HTML with enhanced filtering"""
        # Get content filtering settings
        content_filters = self.config.auth_config.get('content_filters', {})
        min_word_count = content_filters.get('min_word_count', 10)
        exclude_nav = content_filters.get('exclude_nav_elements', True)
        exclude_footer = content_filters.get('exclude_footer_elements', True)
        
        # Remove unwanted elements
        unwanted_selectors = ["script", "style", "noscript", "iframe", "object", "embed"]
        
        if exclude_nav:
            unwanted_selectors.extend(["nav", "header", ".navigation", ".nav", ".menu"])
        
        if exclude_footer:
            unwanted_selectors.extend(["footer", ".footer", ".copyright"])
        
        # Add common noise selectors
        unwanted_selectors.extend([
            ".sidebar", ".widget", ".advertisement", ".ad", ".popup", ".modal",
            ".cookie-notice", ".cookie-banner", "[role='banner']", "[role='navigation']",
            ".social-media", ".share-buttons", ".comments", ".comment-form"
        ])
        
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Focus on main content areas
        main_content_selectors = [
            "main", "article", ".content", ".main-content", "#content", "#main",
            ".post-content", ".entry-content", ".article-content", ".page-content"
        ]
        
        main_content = None
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Use main content if found, otherwise use body
        content_element = main_content if main_content else soup.find('body')
        if not content_element:
            content_element = soup
        
        # Extract text
        text = content_element.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        # Apply minimum word count filter
        if len(text.split()) < min_word_count:
            return ""
        
        return text
    
    def _extract_metadata(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract comprehensive metadata from HTML page"""
        metadata = {'url': url}
        
        # Basic metadata
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta tags
        meta_tags = {
            'description': soup.find('meta', attrs={'name': 'description'}),
            'keywords': soup.find('meta', attrs={'name': 'keywords'}),
            'author': soup.find('meta', attrs={'name': 'author'}),
            'robots': soup.find('meta', attrs={'name': 'robots'}),
            'viewport': soup.find('meta', attrs={'name': 'viewport'}),
            'canonical': soup.find('link', attrs={'rel': 'canonical'}),
        }
        
        for key, tag in meta_tags.items():
            if tag:
                content = tag.get('content') if key != 'canonical' else tag.get('href')
                if content:
                    metadata[key] = content.strip()
        
        # Open Graph metadata
        og_tags = soup.find_all('meta', attrs={'property': lambda x: x and x.startswith('og:')})
        og_data = {}
        for tag in og_tags:
            prop = tag.get('property', '').replace('og:', '')
            content = tag.get('content')
            if prop and content:
                og_data[prop] = content.strip()
        
        if og_data:
            metadata['open_graph'] = og_data
        
        # Twitter Card metadata
        twitter_tags = soup.find_all('meta', attrs={'name': lambda x: x and x.startswith('twitter:')})
        twitter_data = {}
        for tag in twitter_tags:
            name = tag.get('name', '').replace('twitter:', '')
            content = tag.get('content')
            if name and content:
                twitter_data[name] = content.strip()
        
        if twitter_data:
            metadata['twitter'] = twitter_data
        
        # Language detection
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Document structure analysis
        headings = []
        for i in range(1, 7):
            heading_tags = soup.find_all(f'h{i}')
            for tag in heading_tags:
                heading_text = tag.get_text().strip()
                if heading_text:
                    headings.append({
                        'level': i,
                        'text': heading_text,
                        'id': tag.get('id', ''),
                        'class': ' '.join(tag.get('class', []))
                    })
        
        metadata['headings'] = headings
        
        # Link analysis
        links = soup.find_all('a', href=True)
        internal_links = []
        external_links = []
        
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc
        
        for link in links:
            href = link.get('href')
            if href:
                absolute_url = urljoin(url, href)
                link_domain = urlparse(absolute_url).netloc
                
                link_data = {
                    'url': absolute_url,
                    'text': link.get_text().strip(),
                    'title': link.get('title', ''),
                    'rel': link.get('rel', [])
                }
                
                if link_domain == base_domain:
                    internal_links.append(link_data)
                else:
                    external_links.append(link_data)
        
        metadata['links'] = {
            'internal': internal_links[:20],  # Limit to prevent huge metadata
            'external': external_links[:10]
        }
        
        # Content quality metrics
        text_content = self._extract_text(soup)
        word_count = len(text_content.split())
        char_count = len(text_content)
        
        # Calculate reading time (average 200 words per minute)
        reading_time_minutes = max(1, word_count // 200)
        
        # Content complexity scoring
        avg_word_length = sum(len(word) for word in text_content.split()) / max(1, word_count)
        sentences = text_content.split('.')
        avg_sentence_length = word_count / max(1, len(sentences))
        
        metadata['content_quality'] = {
            'word_count': word_count,
            'character_count': char_count,
            'reading_time_minutes': reading_time_minutes,
            'average_word_length': round(avg_word_length, 2),
            'average_sentence_length': round(avg_sentence_length, 2),
            'heading_count': len(headings),
            'internal_link_count': len(internal_links),
            'external_link_count': len(external_links)
        }
        
        # Schema.org structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        structured_data = []
        
        for script in json_ld_scripts:
            try:
                data = json.loads(script.string)
                structured_data.append(data)
            except (json.JSONDecodeError, AttributeError):
                continue
        
        if structured_data:
            metadata['structured_data'] = structured_data
        
        # Publication metadata
        pub_date = soup.find('meta', attrs={'property': 'article:published_time'})
        if not pub_date:
            pub_date = soup.find('time', attrs={'datetime': True})
        
        if pub_date:
            date_value = pub_date.get('content') or pub_date.get('datetime')
            if date_value:
                metadata['published_date'] = date_value
        
        return metadata
    
    def _calculate_enhanced_content_score(self, page_data: Dict) -> ContentQualityMetrics:
        """Enhanced content quality scoring with duplicate detection and information density"""
        content = page_data.get('content', '')
        metadata = page_data.get('metadata', {})
        
        # Initialize metrics
        metrics = ContentQualityMetrics(
            readability_score=0.0,
            content_density=0.0,
            semantic_richness=0.0,
            freshness_score=0.0,
            authority_score=0.0,
            engagement_potential=0.0,
            overall_quality=0.0
        )
        
        if not content:
            return metrics
        
        # Basic metrics
        word_count = len(content.split())
        char_count = len(content)
        
        # Readability score (based on sentence structure)
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        if sentences:
            avg_words_per_sentence = word_count / len(sentences)
            # Optimal range is 15-20 words per sentence
            metrics.readability_score = max(0, 1 - abs(avg_words_per_sentence - 17.5) / 17.5)
        
        # Content density (meaningful content vs HTML)
        html_content = page_data.get('file_size', 0)
        if html_content > 0:
            metrics.content_density = min(1.0, char_count / html_content)
        
        # Semantic richness
        headings = metadata.get('headings', [])
        heading_score = min(1.0, len(headings) / 10)  # Optimal: 10 headings
        
        # Check for structured content
        has_lists = bool(re.search(r'•|•|\d+\.|[a-z]\)', content))
        has_quotes = bool(re.search(r'"|"', content))
        has_numbers = bool(re.search(r'\d+', content))
        
        structure_score = (has_lists * 0.3 + has_quotes * 0.2 + has_numbers * 0.5)
        metrics.semantic_richness = (heading_score + structure_score) / 2
        
        # Freshness score
        pub_date = metadata.get('published_date')
        if pub_date:
            try:
                pub_datetime = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                days_old = (datetime.utcnow() - pub_datetime).days
                metrics.freshness_score = max(0, 1 - days_old / 365)  # Decay over 1 year
            except:
                metrics.freshness_score = 0.5  # Unknown date
        else:
            metrics.freshness_score = 0.3  # No date info
        
        # Authority score (based on content quality indicators)
        domain = urlparse(page_data.get('url', '')).netloc
        authority_score = 0.5  # Base score
        
        # Boost for authoritative indicators
        if any(keyword in content.lower() for keyword in ['research', 'study', 'analysis', 'report']):
            authority_score += 0.2
        if any(keyword in domain.lower() for keyword in ['edu', 'gov', 'org']):
            authority_score += 0.3
        if len(content) > 1000:  # Substantial content
            authority_score += 0.2
            
        metrics.authority_score = min(1.0, authority_score)
        
        # Engagement potential
        engagement_score = 0.0
        if word_count > 300:  # Minimum engaging length
            engagement_score += 0.3
        if len(headings) > 2:  # Well-structured
            engagement_score += 0.2
        if has_lists:  # Scannable content
            engagement_score += 0.2
        if re.search(r'\?', content):  # Questions engage readers
            engagement_score += 0.1
        if any(word in content.lower() for word in ['how', 'why', 'what', 'when', 'where']):
            engagement_score += 0.2
            
        metrics.engagement_potential = min(1.0, engagement_score)
        
        # Duplicate similarity check
        content_hash = hashlib.md5(content.encode()).hexdigest()
        metrics.duplicate_similarity = self._calculate_duplicate_similarity(content, content_hash)
        metrics.content_uniqueness = 1.0 - metrics.duplicate_similarity
        
        # Information density
        metrics.information_density = self._calculate_information_density(content, metadata)
        
        # Overall quality (weighted average with uniqueness factor)
        base_quality = (
            metrics.readability_score * 0.15 +
            metrics.content_density * 0.10 +
            metrics.semantic_richness * 0.25 +
            metrics.freshness_score * 0.15 +
            metrics.authority_score * 0.15 +
            metrics.engagement_potential * 0.10 +
            metrics.information_density * 0.10
        )
        
        # Apply uniqueness multiplier
        uniqueness_multiplier = 0.5 + (metrics.content_uniqueness * 0.5)
        metrics.overall_quality = base_quality * uniqueness_multiplier
        
        return metrics
    
    def _calculate_duplicate_similarity(self, content: str, content_hash: str) -> float:
        """Calculate similarity to existing content"""
        if content_hash in self.content_hashes:
            return 1.0  # Exact duplicate
        
        # Add to cache for future comparison
        self.content_hashes.add(content_hash)
        
        # Simple similarity check using word overlap
        words = set(content.lower().split())
        max_similarity = 0.0
        
        # Check against a sample of cached content (for performance)
        for cached_content in list(self.content_cache.values())[-50:]:  # Last 50 pages
            cached_words = set(cached_content.get('content', '').lower().split())
            if cached_words:
                intersection = words.intersection(cached_words)
                union = words.union(cached_words)
                similarity = len(intersection) / len(union) if union else 0
                max_similarity = max(max_similarity, similarity)
        
        return max_similarity
    
    def _calculate_information_density(self, content: str, metadata: Dict) -> float:
        """Calculate information density based on content analysis"""
        if not content:
            return 0.0
        
        words = content.split()
        word_count = len(words)
        
        # Count informative elements
        numbers = len(re.findall(r'\d+', content))
        proper_nouns = len(re.findall(r'\b[A-Z][a-z]+\b', content))
        technical_terms = len(re.findall(r'\b\w{8,}\b', content))  # Long words often technical
        
        # Calculate density metrics
        number_density = numbers / word_count if word_count > 0 else 0
        proper_noun_density = proper_nouns / word_count if word_count > 0 else 0
        technical_density = technical_terms / word_count if word_count > 0 else 0
        
        # Heading structure contributes to information organization
        headings = metadata.get('headings', [])
        heading_density = len(headings) / max(1, word_count // 100)  # Headings per 100 words
        
        # Combine metrics
        info_density = (
            number_density * 0.3 +
            proper_noun_density * 0.3 +
            technical_density * 0.2 +
            min(1.0, heading_density) * 0.2
        )
        
        return min(1.0, info_density)
    
    async def _intelligent_url_discovery(self, page_data: Dict, session: aiohttp.ClientSession) -> List[Tuple[str, float]]:
        """Intelligent URL discovery with priority scoring"""
        content = page_data.get('content', '')
        url = page_data.get('url', '')
        soup = BeautifulSoup(content, 'html.parser')
        
        discovered_urls = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(url, href)
            
            # Clean URL
            parsed = urlparse(absolute_url)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
            
            if not clean_url or clean_url in self.visited_urls:
                continue
            
            # Calculate priority score
            priority = self._calculate_url_priority(link, absolute_url, page_data)
            discovered_urls.append((clean_url, priority))
        
        # Sort by priority and return top URLs
        discovered_urls.sort(key=lambda x: x[1], reverse=True)
        return discovered_urls[:20]  # Top 20 priority URLs
    
    def _calculate_url_priority(self, link_element, url: str, parent_page: Dict) -> float:
        """Calculate priority score for a discovered URL"""
        priority = 0.5  # Base priority
        
        # Link text analysis
        link_text = link_element.get_text().strip().lower()
        
        # High priority keywords
        high_priority_keywords = [
            'documentation', 'guide', 'tutorial', 'api', 'reference',
            'getting started', 'overview', 'introduction', 'help',
            'download', 'install', 'setup', 'configuration'
        ]
        
        for keyword in high_priority_keywords:
            if keyword in link_text:
                priority += 0.3
                break
        
        # Medium priority keywords
        medium_priority_keywords = [
            'blog', 'news', 'article', 'post', 'update',
            'feature', 'release', 'changelog', 'example'
        ]
        
        for keyword in medium_priority_keywords:
            if keyword in link_text:
                priority += 0.2
                break
        
        # URL structure analysis
        path = urlparse(url).path.lower()
        
        # Prefer organized content
        if any(segment in path for segment in ['/docs/', '/documentation/', '/api/', '/guide/']):
            priority += 0.4
        elif any(segment in path for segment in ['/blog/', '/news/', '/articles/']):
            priority += 0.2
        
        # Penalize deep nesting
        depth = path.count('/')
        if depth > 4:
            priority -= 0.1 * (depth - 4)
        
        # Penalize common low-value pages
        low_value_patterns = [
            'contact', 'privacy', 'terms', 'cookie', 'legal',
            'sitemap', 'search', 'login', 'register', 'cart'
        ]
        
        if any(pattern in path or pattern in link_text for pattern in low_value_patterns):
            priority -= 0.3
        
        # File type considerations
        if url.endswith('.pdf'):
            priority += 0.2  # PDFs often contain valuable content
        elif url.endswith(('.jpg', '.png', '.gif', '.svg', '.css', '.js')):
            priority -= 0.5  # Non-content files
        
        return max(0.0, min(1.0, priority))
    
    async def _start_crawl_session(self) -> str:
        """Start a new crawl session with real-time tracking"""
        session_id = str(uuid.uuid4())
        self.crawl_session = CrawlSession(
            session_id=session_id,
            start_time=datetime.utcnow(),
            pages_discovered=0,
            pages_processed=0,
            pages_successful=0,
            pages_failed=0,
            bytes_downloaded=0,
            avg_response_time=0.0,
            current_queue_size=len(self.start_urls),
            estimated_completion=None
        )
        return session_id
    
    def _update_crawl_session(self, page_data: Dict, response_time: float, success: bool):
        """Update crawl session metrics"""
        if not self.crawl_session:
            return
        
        self.crawl_session.pages_processed += 1
        
        if success:
            self.crawl_session.pages_successful += 1
            self.crawl_session.bytes_downloaded += page_data.get('file_size', 0)
        else:
            self.crawl_session.pages_failed += 1
        
        # Update average response time
        total_time = self.crawl_session.avg_response_time * (self.crawl_session.pages_processed - 1)
        self.crawl_session.avg_response_time = (total_time + response_time) / self.crawl_session.pages_processed
        
        # Update estimated completion
        if self.crawl_session.pages_processed > 5:  # Need some data for estimation
            avg_time_per_page = (datetime.utcnow() - self.crawl_session.start_time).total_seconds() / self.crawl_session.pages_processed
            remaining_pages = max(0, self.max_pages - self.crawl_session.pages_processed)
            estimated_seconds = remaining_pages * avg_time_per_page
            self.crawl_session.estimated_completion = datetime.utcnow() + timedelta(seconds=estimated_seconds)
    
    async def get_crawl_session_status(self) -> Optional[Dict]:
        """Get current crawl session status"""
        if not self.crawl_session:
            return None
        
        return {
            "session_id": self.crawl_session.session_id,
            "start_time": self.crawl_session.start_time.isoformat(),
            "duration_seconds": (datetime.utcnow() - self.crawl_session.start_time).total_seconds(),
            "pages_discovered": self.crawl_session.pages_discovered,
            "pages_processed": self.crawl_session.pages_processed,
            "pages_successful": self.crawl_session.pages_successful,
            "pages_failed": self.crawl_session.pages_failed,
            "success_rate": self.crawl_session.pages_successful / max(1, self.crawl_session.pages_processed),
            "bytes_downloaded": self.crawl_session.bytes_downloaded,
            "avg_response_time": self.crawl_session.avg_response_time,
            "current_queue_size": self.crawl_session.current_queue_size,
            "estimated_completion": self.crawl_session.estimated_completion.isoformat() if self.crawl_session.estimated_completion else None,
            "pages_per_minute": (self.crawl_session.pages_processed / max(1, (datetime.utcnow() - self.crawl_session.start_time).total_seconds())) * 60
        }

    def _calculate_advanced_quality_metrics(self, page_data: Dict, soup: BeautifulSoup) -> ContentQualityMetrics:
        """Calculate comprehensive content quality metrics"""
        metrics = ContentQualityMetrics()
        
        content = page_data.get('content', '')
        word_count = page_data.get('word_count', 0)
        
        # Readability score (Flesch Reading Ease approximation)
        if word_count > 0:
            sentences = len(re.split(r'[.!?]+', content))
            if sentences > 0:
                avg_sentence_length = word_count / sentences
                # Simplified readability calculation
                metrics.readability_score = max(0, min(1, (206.835 - 1.015 * avg_sentence_length) / 100))
        
        # Content density (text to HTML ratio)
        html_content = str(soup)
        if len(html_content) > 0:
            metrics.content_density = len(content) / len(html_content)
        
        # Semantic richness (structure analysis)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        lists = soup.find_all(['ul', 'ol'])
        tables = soup.find_all('table')
        links = soup.find_all('a', href=True)
        
        structure_score = 0
        if headings:
            structure_score += min(0.3, len(headings) * 0.05)
        if lists:
            structure_score += min(0.2, len(lists) * 0.1)
        if tables:
            structure_score += min(0.2, len(tables) * 0.1)
        if links:
            structure_score += min(0.3, len(links) * 0.01)
        
        metrics.semantic_richness = min(1.0, structure_score)
        
        # Freshness score (based on publication date)
        pub_date = self._extract_publication_date(soup)
        if pub_date:
            days_old = (datetime.utcnow() - pub_date).days
            if days_old <= 30:
                metrics.freshness_score = 1.0
            elif days_old <= 90:
                metrics.freshness_score = 0.8
            elif days_old <= 365:
                metrics.freshness_score = 0.5
            else:
                metrics.freshness_score = 0.2
        else:
            metrics.freshness_score = 0.5  # Unknown date
        
        # Authority score (domain-based)
        url = page_data.get('url', '')
        domain = urlparse(url).netloc
        
        # Simple authority scoring based on domain characteristics
        authority_indicators = [
            '.edu' in domain,
            '.gov' in domain,
            '.org' in domain,
            'wikipedia' in domain,
            len(domain.split('.')) <= 3,  # Not too many subdomains
        ]
        metrics.authority_score = sum(authority_indicators) / len(authority_indicators)
        
        # Engagement potential (content structure and media)
        images = soup.find_all('img')
        videos = soup.find_all(['video', 'iframe'])
        
        engagement_score = 0
        if word_count > 300:
            engagement_score += 0.3
        if images:
            engagement_score += min(0.2, len(images) * 0.05)
        if videos:
            engagement_score += min(0.2, len(videos) * 0.1)
        if headings and len(headings) > 2:
            engagement_score += 0.2
        if lists:
            engagement_score += 0.1
        
        metrics.engagement_potential = min(1.0, engagement_score)
        
        # Overall quality (weighted average)
        metrics.overall_quality = (
            metrics.readability_score * 0.2 +
            metrics.content_density * 0.15 +
            metrics.semantic_richness * 0.25 +
            metrics.freshness_score * 0.15 +
            metrics.authority_score * 0.15 +
            metrics.engagement_potential * 0.1
        )
        
        return metrics

    def _extract_publication_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publication date from various sources"""
        # Try meta tags first
        date_selectors = [
            'meta[property="article:published_time"]',
            'meta[name="date"]',
            'meta[name="publish-date"]',
            'meta[name="publication-date"]',
            'meta[property="og:published_time"]',
            'time[datetime]',
            '.published',
            '.date',
            '.post-date'
        ]
        
        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_str = element.get('content') or element.get('datetime') or element.get_text()
                if date_str:
                    try:
                        # Try common date formats
                        for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                            try:
                                return datetime.strptime(date_str[:19], fmt)
                            except ValueError:
                                continue
                    except:
                        continue
        
        return None

    def _detect_content_duplicates(self, content_hash: str, db: Session, organization_id: str) -> float:
        """Detect content similarity with existing pages"""
        try:
            similar_pages = db.execute(
                text("""
                    SELECT content_hash, url FROM crawled_pages 
                    WHERE organization_id = :org_id 
                    AND content_hash = :content_hash
                    LIMIT 5
                """),
                {"org_id": organization_id, "content_hash": content_hash}
            ).fetchall()
            
            if similar_pages:
                return 1.0  # Exact duplicate
            
            # Could implement fuzzy matching here for near-duplicates
            return 0.0
            
        except Exception as e:
            logger.error(f"Error checking for duplicates: {e}")
            return 0.0

    async def _check_content_freshness(self, url: str, last_modified: Optional[datetime]) -> bool:
        """Check if content has been modified since last crawl"""
        if not self.schedule.incremental_crawl:
            return True  # Always crawl if incremental is disabled
        
        if not last_modified:
            return True  # No previous crawl data
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url) as response:
                    last_mod_header = response.headers.get('Last-Modified')
                    if last_mod_header:
                        try:
                            server_modified = datetime.strptime(
                                last_mod_header, '%a, %d %b %Y %H:%M:%S %Z'
                            )
                            return server_modified > last_modified
                        except ValueError:
                            pass
                    
                    # If no Last-Modified header, check if enough time has passed
                    time_since_crawl = datetime.utcnow() - last_modified
                    return time_since_crawl.total_seconds() > (self.schedule.frequency_hours * 3600)
        
        except Exception as e:
            logger.warning(f"Error checking freshness for {url}: {e}")
            return True  # Default to crawling on error
    
    async def _extract_links(self, content: str, base_url: str, session: aiohttp.ClientSession) -> List[str]:
        """Extract links from page content"""
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            absolute_url = urljoin(base_url, href)
            
            # Clean up URL
            parsed = urlparse(absolute_url)
            clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
            
            if clean_url and clean_url not in links:
                links.append(clean_url)
        
        return links
    
    def _matches_patterns(self, url: str) -> bool:
        """Check if URL matches include/exclude patterns"""
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
        parsed = urlparse(url)
        url_domain = parsed.netloc
        
        start_domains = [urlparse(start_url).netloc for start_url in self.start_urls]
        return not any(url_domain.endswith(domain) for domain in start_domains)
    
    async def _check_robots_txt(self, url: str, session: aiohttp.ClientSession) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not self.respect_robots:
            return True
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            
            if domain not in self.robots_cache:
                robots_url = f"{parsed.scheme}://{domain}/robots.txt"
                
                try:
                    async with session.get(robots_url) as response:
                        if response.status == 200:
                            robots_content = await response.text()
                            rp = RobotFileParser()
                            rp.set_url(robots_url)
                            rp.read()
                            self.robots_cache[domain] = rp
                        else:
                            self.robots_cache[domain] = None
                except:
                    self.robots_cache[domain] = None
            
            robots_parser = self.robots_cache.get(domain)
            if robots_parser:
                return robots_parser.can_fetch(self.user_agent, url)
            
            return True
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {e}")
            return True
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format"""
        if seconds < 60:
            return f"{seconds:.0f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        else:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
    
    async def get_crawl_stats(self) -> CrawlStats:
        """Get statistics about the current crawl configuration"""
        return CrawlStats(
            total_urls=len(self.start_urls),
            successful_crawls=0,  # Would be updated during actual crawl
            failed_crawls=0,
            skipped_urls=0,
            pages_processed=len(self.visited_urls),
            data_extracted_mb=0.0,
            duration_seconds=0.0,
            last_crawl=datetime.utcnow()
        )

    async def store_crawled_page(self, db: Session, page_data: Dict, connector_id: str, organization_id: str, domain_id: str):
        """Store crawled page in database with proper organization isolation"""
        try:
            url_hash = hashlib.md5(page_data['url'].encode()).hexdigest()
            
            # Check if page already exists
            existing = db.execute(
                text("""
                    SELECT id FROM crawled_pages 
                    WHERE url_hash = :url_hash AND connector_id = :connector_id AND organization_id = :org_id
                """),
                {
                    "url_hash": url_hash,
                    "connector_id": connector_id,
                    "org_id": organization_id
                }
            ).fetchone()
            
            if existing:
                # Update existing page
                db.execute(
                    text("""
                        UPDATE crawled_pages 
                        SET content = :content, metadata = :metadata, 
                            last_crawled = :crawled_at, content_hash = :content_hash,
                            word_count = :word_count, status = :status,
                            error_message = :error_message, file_size = :file_size,
                            content_type = :content_type, title = :title,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE url_hash = :url_hash AND domain_id = :domain_id AND organization_id = :org_id
                    """),
                    {
                        "content": page_data['content'],
                        "metadata": json.dumps(page_data['metadata']),
                        "crawled_at": page_data['crawled_at'],
                        "content_hash": page_data['content_hash'],
                        "word_count": page_data['word_count'],
                        "status": page_data.get('status', 'success'),
                        "error_message": page_data.get('error_message'),
                        "file_size": page_data.get('file_size', 0),
                        "content_type": page_data.get('content_type', ''),
                        "title": page_data.get('title', ''),
                        "url_hash": url_hash,
                        "domain_id": domain_id,
                        "org_id": organization_id
                    }
                )
            else:
                # Insert new page
                db.execute(
                    text("""
                        INSERT INTO crawled_pages (
                            organization_id, domain_id, url, url_hash,
                            title, content, metadata, first_crawled, last_crawled,
                            content_hash, word_count, status, error_message,
                            depth, content_type, file_size, created_at, updated_at
                        ) VALUES (
                            :organization_id, :domain_id, :url, :url_hash,
                            :title, :content, :metadata, :crawled_at, :crawled_at,
                            :content_hash, :word_count, :status, :error_message,
                            :depth, :content_type, :file_size, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                    """),
                    {
                        "organization_id": organization_id,
                        "domain_id": domain_id,
                        "url": page_data['url'],
                        "url_hash": url_hash,
                        "title": page_data.get('title', ''),
                        "content": page_data['content'],
                        "metadata": json.dumps(page_data['metadata']),
                        "crawled_at": page_data['crawled_at'],
                        "content_hash": page_data['content_hash'],
                        "word_count": page_data['word_count'],
                        "status": page_data.get('status', 'success'),
                        "error_message": page_data.get('error_message'),
                        "depth": page_data.get('depth', 0),
                        "content_type": page_data.get('content_type', ''),
                        "file_size": page_data.get('file_size', 0)
                    }
                )
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error storing crawled page {page_data.get('url', 'unknown')}: {e}")
            db.rollback()

    async def crawl_with_intelligence(
        self, 
        db: Session = None, 
        connector_id: str = None, 
        organization_id: str = None,
        domain: str = None,
        progress_callback = None
    ) -> List[Dict[str, Any]]:
        """Enhanced crawl with intelligent discovery and real-time monitoring"""
        crawled_data = []
        
        # Start crawl session
        session_id = await self._start_crawl_session()
        logger.info(f"Started intelligent crawl session: {session_id}")
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            # Initialize priority queue with start URLs
            priority_queue = [(url, 1.0, 0) for url in self.start_urls]  # (url, priority, depth)
            processed_count = 0
            response_times = []
            
            while priority_queue and processed_count < self.max_pages:
                # Sort by priority and get next URL
                priority_queue.sort(key=lambda x: x[1], reverse=True)
                current_url, priority, depth = priority_queue.pop(0)
                
                # Update session queue size
                if self.crawl_session:
                    self.crawl_session.current_queue_size = len(priority_queue)
                
                # Progress callback
                if progress_callback:
                    session_status = await self.get_crawl_session_status()
                    await progress_callback(session_status)
                
                if (current_url in self.visited_urls or 
                    depth > self.max_depth or
                    not self._matches_patterns(current_url)):
                    continue
                
                if self.respect_robots and not await self._check_robots_txt(current_url, session):
                    continue
                
                start_time = time.time()
                
                try:
                    page_data = await self._crawl_page_enhanced(current_url, session, depth)
                    response_time = time.time() - start_time
                    response_times.append(response_time)
                    
                    if page_data:
                        # Enhanced quality scoring
                        quality_metrics = self._calculate_enhanced_content_score(page_data)
                        page_data['quality_metrics'] = asdict(quality_metrics)
                        page_data['quality_score'] = quality_metrics.overall_quality
                        
                        # Skip low-quality content if filtering is enabled
                        if quality_metrics.overall_quality < self.quality_threshold:
                            logger.debug(f"Skipping low-quality content: {current_url} (score: {quality_metrics.overall_quality:.2f})")
                            self._update_crawl_session(page_data, response_time, False)
                            continue
                        
                        # Add to results
                        crawled_data.append(page_data)
                        self.visited_urls.add(current_url)
                        processed_count += 1
                        
                        # Cache content for duplicate detection
                        self.content_cache[current_url] = page_data
                        
                        # Update session metrics
                        self._update_crawl_session(page_data, response_time, True)
                        
                        # Store in database if provided
                        if db and connector_id and organization_id:
                            await self.store_crawled_page(db, page_data, connector_id, organization_id, domain or "general")
                        
                        # Intelligent URL discovery within depth limit
                        if depth < self.max_depth and self.intelligent_discovery:
                            discovered_urls = await self._intelligent_url_discovery(page_data, session)
                            for new_url, url_priority in discovered_urls:
                                if new_url not in self.visited_urls and new_url not in [u[0] for u in priority_queue]:
                                    priority_queue.append((new_url, url_priority, depth + 1))
                                    if self.crawl_session:
                                        self.crawl_session.pages_discovered += 1
                    
                    # Adaptive delay based on server response
                    adaptive_delay = self._calculate_adaptive_delay(response_times[-10:])  # Last 10 responses
                    await asyncio.sleep(adaptive_delay)
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    logger.error(f"Error crawling {current_url}: {e}")
                    
                    # Update session with failure
                    failed_page_data = {'url': current_url, 'status': 'failed', 'error': str(e)}
                    self._update_crawl_session(failed_page_data, response_time, False)
                    continue
        
        # Final progress update
        if progress_callback:
            final_status = await self.get_crawl_session_status()
            await progress_callback(final_status)
        
        logger.info(f"Completed intelligent crawl session: {session_id}, processed: {processed_count} pages")
        return crawled_data

    async def _crawl_page_enhanced(self, url: str, session: aiohttp.ClientSession, depth: int) -> Optional[Dict[str, Any]]:
        """Enhanced page crawling with better error handling and content analysis"""
        try:
            async with session.get(url) as response:
                if response.status not in [200, 201]:
                    return None
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return None
                
                # Enhanced size checking
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.max_file_size:
                    logger.warning(f"Skipping {url}: file too large ({content_length} bytes)")
                    return None
                
                # Read content with size limit
                html_content = await response.text()
                if len(html_content.encode('utf-8')) > self.max_file_size:
                    logger.warning(f"Skipping {url}: content too large after download")
                    return None
                
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Enhanced text extraction
                text_content = self._extract_text_enhanced(soup)
                
                # Skip if content is too short or low quality
                if not text_content or len(text_content.split()) < 10:
                    return None
                
                # Enhanced metadata extraction
                metadata = self._extract_metadata_enhanced(soup, url)
                
                # Server response analysis
                server_info = {
                    'status_code': response.status,
                    'headers': dict(response.headers),
                    'response_time': time.time(),  # Will be calculated by caller
                    'content_encoding': response.headers.get('content-encoding', ''),
                    'last_modified': response.headers.get('last-modified', ''),
                    'etag': response.headers.get('etag', '')
                }
                
                page_data = {
                    'url': url,
                    'title': metadata.get('title', ''),
                    'content': text_content,
                    'metadata': metadata,
                    'crawled_at': datetime.utcnow(),
                    'content_hash': hashlib.md5(text_content.encode()).hexdigest(),
                    'word_count': len(text_content.split()),
                    'content_type': content_type,
                    'file_size': len(html_content.encode('utf-8')),
                    'depth': depth,
                    'server_info': server_info,
                    'status': 'success'
                }
                
                return page_data
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout crawling {url}")
            return self._create_failed_page_data(url, "timeout", depth)
        except aiohttp.ClientError as e:
            logger.warning(f"Client error crawling {url}: {e}")
            return self._create_failed_page_data(url, f"client_error: {e}", depth)
        except Exception as e:
            logger.error(f"Unexpected error crawling {url}: {e}")
            return self._create_failed_page_data(url, f"error: {e}", depth)

    def _create_failed_page_data(self, url: str, error_reason: str, depth: int) -> Dict[str, Any]:
        """Create consistent failed page data structure"""
        return {
            'url': url,
            'title': '',
            'content': '',
            'metadata': {'url': url},
            'crawled_at': datetime.utcnow(),
            'content_hash': '',
            'word_count': 0,
            'content_type': '',
            'file_size': 0,
            'depth': depth,
            'status': 'failed',
            'error_message': error_reason,
            'quality_score': 0.0
        }

    def _extract_text_enhanced(self, soup: BeautifulSoup) -> str:
        """Enhanced text extraction with better noise filtering"""
        # Get content filtering settings
        content_filters = self.config.auth_config.get('content_filters', {})
        min_word_count = content_filters.get('min_word_count', 10)
        exclude_nav = content_filters.get('exclude_nav_elements', True)
        exclude_footer = content_filters.get('exclude_footer_elements', True)
        
        # Enhanced unwanted element removal
        unwanted_selectors = [
            "script", "style", "noscript", "iframe", "object", "embed",
            "svg", "canvas", "audio", "video", "source"
        ]
        
        if exclude_nav:
            unwanted_selectors.extend([
                "nav", "header", ".navigation", ".nav", ".menu", ".navbar",
                "[role='navigation']", "[role='banner']", ".breadcrumb",
                ".pagination", ".skip-to-content"
            ])
        
        if exclude_footer:
            unwanted_selectors.extend([
                "footer", ".footer", ".copyright", ".legal", ".site-info",
                "[role='contentinfo']"
            ])
        
        # Remove common noise elements
        unwanted_selectors.extend([
            ".sidebar", ".widget", ".advertisement", ".ad", ".popup", ".modal",
            ".cookie-notice", ".cookie-banner", ".notification", ".alert",
            ".social-media", ".share-buttons", ".comments", ".comment-form",
            ".related-posts", ".tags", ".categories", ".metadata",
            ".author-bio", ".subscribe", ".newsletter", ".promo"
        ])
        
        # Remove unwanted elements
        for selector in unwanted_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # Focus on main content areas with priority order
        main_content_selectors = [
            "main", "article", "[role='main']",
            ".content", ".main-content", "#content", "#main",
            ".post-content", ".entry-content", ".article-content", 
            ".page-content", ".body-content", ".text-content",
            ".documentation", ".docs-content"
        ]
        
        main_content = None
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # Use main content if found, otherwise use body
        content_element = main_content if main_content else soup.find('body')
        if not content_element:
            content_element = soup
        
        # Extract text with enhanced cleaning
        text = content_element.get_text()
        
        # Advanced text cleaning
        lines = []
        for line in text.splitlines():
            line = line.strip()
            # Skip empty lines and very short lines
            if line and len(line) > 2:
                # Skip lines that are likely navigation or metadata
                if not re.match(r'^(home|about|contact|privacy|terms|©|\d{4})$', line.lower()):
                    lines.append(line)
        
        # Join lines and clean up spacing
        text = ' '.join(lines)
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single space
        text = re.sub(r'\.{3,}', '...', text)  # Multiple dots to ellipsis
        
        # Apply minimum word count filter
        if len(text.split()) < min_word_count:
            return ""
        
        return text.strip()

    def _extract_metadata_enhanced(self, soup: BeautifulSoup, url: str) -> Dict:
        """Enhanced metadata extraction with more comprehensive analysis"""
        metadata = {'url': url}
        
        # Basic metadata
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta tags
        meta_tags = {
            'description': soup.find('meta', attrs={'name': 'description'}),
            'keywords': soup.find('meta', attrs={'name': 'keywords'}),
            'author': soup.find('meta', attrs={'name': 'author'}),
            'robots': soup.find('meta', attrs={'name': 'robots'}),
            'viewport': soup.find('meta', attrs={'name': 'viewport'}),
        }
        
        for key, tag in meta_tags.items():
            if tag and tag.get('content'):
                metadata[key] = tag.get('content').strip()
        
        # Open Graph metadata
        og_tags = {}
        for og_tag in soup.find_all('meta', attrs={'property': re.compile(r'^og:')}):
            property_name = og_tag.get('property', '').replace('og:', '')
            if property_name and og_tag.get('content'):
                og_tags[property_name] = og_tag.get('content').strip()
        
        if og_tags:
            metadata['open_graph'] = og_tags
        
        # Twitter Card metadata
        twitter_tags = {}
        for twitter_tag in soup.find_all('meta', attrs={'name': re.compile(r'^twitter:')}):
            name = twitter_tag.get('name', '').replace('twitter:', '')
            if name and twitter_tag.get('content'):
                twitter_tags[name] = twitter_tag.get('content').strip()
        
        if twitter_tags:
            metadata['twitter_card'] = twitter_tags
        
        # Language detection
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Enhanced heading structure
        headings = []
        for i in range(1, 7):
            heading_tags = soup.find_all(f'h{i}')
            for tag in heading_tags:
                heading_text = tag.get_text().strip()
                if heading_text:
                    headings.append({
                        'level': i,
                        'text': heading_text[:200],  # Limit length
                        'id': tag.get('id', ''),
                        'class': ' '.join(tag.get('class', [])),
                        'position': len(headings)  # Document order
                    })
        
        metadata['headings'] = headings
        
        # Enhanced link analysis
        internal_links = []
        external_links = []
        parsed_url = urlparse(url)
        base_domain = parsed_url.netloc
        
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if href:
                absolute_url = urljoin(url, href)
                link_domain = urlparse(absolute_url).netloc
                
                link_data = {
                    'url': absolute_url,
                    'text': link.get_text().strip()[:100],  # Limit text length
                    'title': link.get('title', ''),
                    'rel': link.get('rel', [])
                }
                
                if link_domain == base_domain:
                    internal_links.append(link_data)
                else:
                    external_links.append(link_data)
        
        metadata['links'] = {
            'internal': internal_links[:50],  # Limit to prevent huge metadata
            'external': external_links[:20]
        }
        
        # Content structure analysis
        content_structure = {
            'paragraphs': len(soup.find_all('p')),
            'lists': len(soup.find_all(['ul', 'ol'])),
            'tables': len(soup.find_all('table')),
            'images': len(soup.find_all('img')),
            'forms': len(soup.find_all('form')),
            'code_blocks': len(soup.find_all(['code', 'pre'])),
            'blockquotes': len(soup.find_all('blockquote'))
        }
        
        metadata['content_structure'] = content_structure
        
        # Technical metadata
        canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
        if canonical_tag and canonical_tag.get('href'):
            metadata['canonical_url'] = canonical_tag.get('href')
        
        # Schema.org structured data
        json_ld_scripts = soup.find_all('script', type='application/ld+json')
        structured_data = []
        
        for script in json_ld_scripts:
            try:
                if script.string:
                    data = json.loads(script.string)
                    structured_data.append(data)
            except (json.JSONDecodeError, AttributeError):
                continue
        
        if structured_data:
            metadata['structured_data'] = structured_data[:5]  # Limit count
        
        # Publication date detection (enhanced)
        pub_date = self._extract_publication_date_enhanced(soup)
        if pub_date:
            metadata['published_date'] = pub_date.isoformat()
        
        return metadata

    def _extract_publication_date_enhanced(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Enhanced publication date extraction"""
        # Try multiple date selectors in order of reliability
        date_selectors = [
            ('meta[property="article:published_time"]', 'content'),
            ('meta[name="date"]', 'content'),
            ('meta[name="publish-date"]', 'content'),
            ('meta[name="publication-date"]', 'content'),
            ('meta[property="og:published_time"]', 'content'),
            ('time[datetime]', 'datetime'),
            ('time[pubdate]', 'datetime'),
            ('.published', 'text'),
            ('.date', 'text'),
            ('.post-date', 'text'),
            ('.publish-date', 'text'),
            ('.article-date', 'text')
        ]
        
        for selector, attr in date_selectors:
            element = soup.select_one(selector)
            if element:
                if attr == 'text':
                    date_str = element.get_text().strip()
                else:
                    date_str = element.get(attr)
                
                if date_str:
                    parsed_date = self._parse_date_string(date_str)
                    if parsed_date:
                        return parsed_date
        
        return None

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse various date string formats"""
        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%m/%d/%Y',
            '%d/%m/%Y'
        ]
        
        # Clean the date string
        date_str = re.sub(r'\s+', ' ', date_str.strip())
        date_str = date_str[:25]  # Limit length
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        # Try parsing with dateutil if available
        try:
            from dateutil import parser
            return parser.parse(date_str)
        except:
            pass
        
        return None

    def _calculate_adaptive_delay(self, response_times: List[float]) -> float:
        """Calculate adaptive delay based on server response times"""
        if not response_times:
            return self.delay
        
        avg_response_time = statistics.mean(response_times)
        
        # Adaptive delay strategy
        if avg_response_time < 0.5:  # Fast server
            return max(0.5, self.delay * 0.8)
        elif avg_response_time < 1.0:  # Normal server
            return self.delay
        elif avg_response_time < 3.0:  # Slow server
            return self.delay * 1.5
        else:  # Very slow server
            return min(10.0, self.delay * 2.0)

    async def get_content_analytics(self) -> Dict[str, Any]:
        """Get comprehensive content analytics for the crawled data"""
        if not self.content_cache:
            return {}
        
        analytics = {
            'content_quality_distribution': {
                'high_quality': 0,      # > 0.7
                'medium_quality': 0,    # 0.4 - 0.7
                'low_quality': 0        # < 0.4
            },
            'duplicate_analysis': {
                'unique_content': 0,
                'near_duplicates': 0,
                'exact_duplicates': 0
            },
            'content_themes': {},
            'information_density_stats': {
                'avg_density': 0.0,
                'high_density_pages': 0,
                'low_density_pages': 0
            },
            'language_distribution': {},
            'content_structure_patterns': {
                'well_structured': 0,
                'basic_structure': 0,
                'poor_structure': 0
            }
        }
        
        quality_scores = []
        density_scores = []
        languages = Counter()
        
        for url, page_data in self.content_cache.items():
            quality_metrics = page_data.get('quality_metrics', {})
            if quality_metrics:
                quality_score = quality_metrics.get('overall_quality', 0)
                quality_scores.append(quality_score)
                
                # Quality distribution
                if quality_score > 0.7:
                    analytics['content_quality_distribution']['high_quality'] += 1
                elif quality_score > 0.4:
                    analytics['content_quality_distribution']['medium_quality'] += 1
                else:
                    analytics['content_quality_distribution']['low_quality'] += 1
                
                # Duplicate analysis
                similarity = quality_metrics.get('duplicate_similarity', 0)
                if similarity < 0.1:
                    analytics['duplicate_analysis']['unique_content'] += 1
                elif similarity < 0.8:
                    analytics['duplicate_analysis']['near_duplicates'] += 1
                else:
                    analytics['duplicate_analysis']['exact_duplicates'] += 1
                
                # Information density
                density = quality_metrics.get('information_density', 0)
                density_scores.append(density)
                if density > 0.6:
                    analytics['information_density_stats']['high_density_pages'] += 1
                elif density < 0.3:
                    analytics['information_density_stats']['low_density_pages'] += 1
            
            # Language analysis
            metadata = page_data.get('metadata', {})
            language = metadata.get('language', 'unknown')
            languages[language] += 1
            
            # Structure analysis
            headings = metadata.get('headings', [])
            content_structure = metadata.get('content_structure', {})
            
            heading_count = len(headings)
            paragraph_count = content_structure.get('paragraphs', 0)
            
            if heading_count >= 3 and paragraph_count >= 5:
                analytics['content_structure_patterns']['well_structured'] += 1
            elif heading_count >= 1 and paragraph_count >= 2:
                analytics['content_structure_patterns']['basic_structure'] += 1
            else:
                analytics['content_structure_patterns']['poor_structure'] += 1
        
        # Calculate averages
        if quality_scores:
            analytics['average_quality_score'] = statistics.mean(quality_scores)
        
        if density_scores:
            analytics['information_density_stats']['avg_density'] = statistics.mean(density_scores)
        
        # Language distribution
        analytics['language_distribution'] = dict(languages.most_common(10))
        
        return analytics

    async def schedule_crawl(self, db: Session, connector_id: str, organization_id: str, domain: str) -> Dict[str, Any]:
        """Schedule a crawl based on configuration"""
        if not self.schedule.enabled:
            return {"status": "disabled", "message": "Scheduling is disabled"}
        
        # Check if it's time for next crawl
        if self.schedule.next_run and datetime.utcnow() < self.schedule.next_run:
            time_until_next = (self.schedule.next_run - datetime.utcnow()).total_seconds()
            return {
                "status": "scheduled",
                "next_run": self.schedule.next_run.isoformat(),
                "time_until_next_seconds": time_until_next
            }
        
        # Check for concurrent crawl limit
        active_crawls = await self._get_active_crawl_count(db, organization_id)
        if active_crawls >= self.schedule.max_concurrent_crawls:
            return {
                "status": "throttled",
                "message": f"Maximum concurrent crawls ({self.schedule.max_concurrent_crawls}) reached",
                "active_crawls": active_crawls
            }
        
        # Start the crawl
        try:
            crawl_results = await self.crawl_with_intelligence(
                db=db,
                connector_id=connector_id,
                organization_id=organization_id,
                domain=domain
            )
            
            # Schedule next crawl
            self.schedule.next_run = datetime.utcnow() + timedelta(hours=self.schedule.frequency_hours)
            
            return {
                "status": "completed",
                "pages_crawled": len(crawl_results),
                "next_run": self.schedule.next_run.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Scheduled crawl failed: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "next_run": (datetime.utcnow() + timedelta(hours=1)).isoformat()  # Retry in 1 hour
            }

    async def _get_active_crawl_count(self, db: Session, organization_id: str) -> int:
        """Get count of currently active crawls for organization"""
        try:
            result = db.execute(
                text("""
                    SELECT COUNT(*) as active_count
                    FROM sync_jobs 
                    WHERE organization_id = :org_id 
                    AND status = 'running'
                    AND created_at > :since
                """),
                {
                    "org_id": organization_id,
                    "since": datetime.utcnow() - timedelta(hours=2)  # Consider jobs from last 2 hours
                }
            ).fetchone()
            
            return result.active_count if result else 0
            
        except Exception as e:
            logger.error(f"Error getting active crawl count: {e}")
            return 0

    async def get_performance_metrics(self, db: Session, connector_id: str, organization_id: str) -> CrawlPerformanceMetrics:
        """Calculate performance metrics for the connector"""
        try:
            # Get recent crawl data
            recent_pages = db.execute(
                text("""
                    SELECT 
                        status,
                        file_size,
                        last_crawled,
                        word_count,
                        error_message
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id 
                    AND organization_id = :org_id
                    AND last_crawled > :since
                    ORDER BY last_crawled DESC
                    LIMIT 1000
                """),
                {
                    "connector_id": connector_id,
                    "org_id": organization_id,
                    "since": datetime.utcnow() - timedelta(days=7)
                }
            ).fetchall()
            
            if not recent_pages:
                return self.performance_metrics
            
            # Calculate metrics
            total_pages = len(recent_pages)
            successful_pages = [p for p in recent_pages if p.status == 'success']
            failed_pages = [p for p in recent_pages if p.status == 'failed']
            
            # Error rate
            self.performance_metrics.error_rate = len(failed_pages) / total_pages if total_pages > 0 else 0
            
            # Bandwidth usage
            total_bytes = sum(p.file_size or 0 for p in recent_pages)
            self.performance_metrics.bandwidth_usage_mb = total_bytes / (1024 * 1024)
            
            # Pages per second (estimate based on recent activity)
            if len(recent_pages) > 1:
                time_span = (recent_pages[0].last_crawled - recent_pages[-1].last_crawled).total_seconds()
                if time_span > 0:
                    self.performance_metrics.pages_per_second = total_pages / time_span
            
            # Average response time (estimated from file size and assumed bandwidth)
            if successful_pages:
                avg_file_size = statistics.mean(p.file_size or 0 for p in successful_pages)
                # Estimate response time based on file size (rough approximation)
                self.performance_metrics.avg_response_time = max(0.1, avg_file_size / 100000)  # 100KB/s assumed
            
            # Cache hit rate (if caching is enabled)
            if self.enable_caching:
                cache_hits = len([url for url in self.content_cache.keys() if url in [p.url for p in recent_pages]])
                self.performance_metrics.cache_hit_rate = cache_hits / total_pages if total_pages > 0 else 0
            
            # Robots compliance rate
            robots_compliant = len([p for p in recent_pages if not p.error_message or 'robots' not in p.error_message.lower()])
            self.performance_metrics.robots_compliance_rate = robots_compliant / total_pages if total_pages > 0 else 1.0
            
            return self.performance_metrics
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return self.performance_metrics

    async def optimize_crawl_settings(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Analyze performance and suggest optimizations"""
        metrics = await self.get_performance_metrics(db, connector_id, organization_id)
        suggestions = []
        
        # Analyze error rate
        if metrics.error_rate > 0.1:  # More than 10% errors
            suggestions.append({
                "type": "error_rate",
                "severity": "high" if metrics.error_rate > 0.2 else "medium",
                "message": f"High error rate ({metrics.error_rate:.1%}). Consider reducing crawl speed or checking URL patterns.",
                "recommended_action": "increase_delay" if metrics.error_rate > 0.2 else "review_patterns"
            })
        
        # Analyze crawl speed
        if metrics.pages_per_second < 0.1:  # Very slow
            suggestions.append({
                "type": "performance",
                "severity": "medium",
                "message": "Crawl speed is slow. Consider increasing concurrent requests or reducing delay.",
                "recommended_action": "increase_concurrency"
            })
        elif metrics.pages_per_second > 2.0:  # Very fast, might be aggressive
            suggestions.append({
                "type": "performance",
                "severity": "low",
                "message": "Crawl speed is very high. Ensure you're respecting server limits.",
                "recommended_action": "add_delay"
            })
        
        # Analyze bandwidth usage
        if metrics.bandwidth_usage_mb > 1000:  # More than 1GB
            suggestions.append({
                "type": "bandwidth",
                "severity": "medium",
                "message": f"High bandwidth usage ({metrics.bandwidth_usage_mb:.1f}MB). Consider filtering content types.",
                "recommended_action": "add_content_filters"
            })
        
        # Analyze robots compliance
        if metrics.robots_compliance_rate < 0.9:
            suggestions.append({
                "type": "compliance",
                "severity": "high",
                "message": f"Low robots.txt compliance ({metrics.robots_compliance_rate:.1%}). Review crawl patterns.",
                "recommended_action": "review_robots_settings"
            })
        
        # Generate recommended settings
        recommended_settings = {}
        
        if metrics.error_rate > 0.15:
            recommended_settings['delay_ms'] = min(self.delay_ms * 2, 5000)
            recommended_settings['concurrent_requests'] = max(self.concurrent_requests - 1, 1)
        elif metrics.error_rate < 0.05 and metrics.pages_per_second < 0.5:
            recommended_settings['delay_ms'] = max(self.delay_ms // 2, 500)
            recommended_settings['concurrent_requests'] = min(self.concurrent_requests + 1, 10)
        
        if metrics.bandwidth_usage_mb > 500:
            recommended_settings['max_file_size'] = min(self.max_file_size, 2 * 1024 * 1024)  # 2MB
        
        return {
            "current_metrics": asdict(metrics),
            "suggestions": suggestions,
            "recommended_settings": recommended_settings,
            "optimization_score": self._calculate_optimization_score(metrics)
        }

    def _calculate_optimization_score(self, metrics: CrawlPerformanceMetrics) -> float:
        """Calculate overall optimization score (0-1)"""
        score = 1.0
        
        # Penalize high error rate
        score -= min(0.3, metrics.error_rate * 2)
        
        # Penalize very slow or very fast crawling
        if metrics.pages_per_second < 0.1:
            score -= 0.2
        elif metrics.pages_per_second > 3.0:
            score -= 0.1
        
        # Penalize low robots compliance
        score -= (1.0 - metrics.robots_compliance_rate) * 0.3
        
        # Penalize excessive bandwidth usage
        if metrics.bandwidth_usage_mb > 1000:
            score -= 0.2
        
        return max(0.0, score)

    async def get_crawl_insights(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Get comprehensive insights about crawl performance and content"""
        try:
            # Get content quality distribution
            quality_data = db.execute(
                text("""
                    SELECT 
                        CASE 
                            WHEN (metadata->>'quality_score')::float >= 0.7 THEN 'high'
                            WHEN (metadata->>'quality_score')::float >= 0.4 THEN 'medium'
                            ELSE 'low'
                        END as quality_level,
                        COUNT(*) as count
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id 
                    AND organization_id = :org_id
                    AND metadata->>'quality_score' IS NOT NULL
                    GROUP BY quality_level
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            quality_distribution = {row.quality_level: row.count for row in quality_data}
            
            # Get content type distribution
            content_types = db.execute(
                text("""
                    SELECT content_type, COUNT(*) as count
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id 
                    AND organization_id = :org_id
                    GROUP BY content_type
                    ORDER BY count DESC
                    LIMIT 10
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            # Get URL pattern analysis
            url_patterns = db.execute(
                text("""
                    SELECT 
                        REGEXP_REPLACE(url, '[0-9]+', 'N', 'g') as pattern,
                        COUNT(*) as count
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id 
                    AND organization_id = :org_id
                    GROUP BY pattern
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                    LIMIT 10
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            # Get performance metrics
            performance_metrics = await self.get_performance_metrics(db, connector_id, organization_id)
            
            return {
                "content_quality_distribution": quality_distribution,
                "content_type_distribution": [{"type": row.content_type, "count": row.count} for row in content_types],
                "url_patterns": [{"pattern": row.pattern, "count": row.count} for row in url_patterns],
                "performance_metrics": asdict(performance_metrics),
                "crawl_efficiency": {
                    "success_rate": 1.0 - performance_metrics.error_rate,
                    "avg_crawl_time": performance_metrics.avg_response_time,
                    "pages_per_hour": performance_metrics.pages_per_second * 3600
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting crawl insights: {e}")
            return {
                "content_quality_distribution": {},
                "content_type_distribution": [],
                "url_patterns": [],
                "performance_metrics": asdict(CrawlPerformanceMetrics()),
                "crawl_efficiency": {}
            } 

    async def crawl_with_advanced_pipeline(
        self, 
        db: Session = None, 
        connector_id: str = None, 
        organization_id: str = None,
        domain: str = None,
        progress_callback = None
    ) -> List[Dict[str, Any]]:
        """Enhanced crawl with advanced pipeline and queue management"""
        crawled_data = []
        
        # Start crawl session
        session_id = await self._start_crawl_session()
        logger.info(f"Started advanced crawl session: {session_id}")
        
        # Initialize URL queue with start URLs
        if self.enable_url_queue_management:
            for url in self.start_urls:
                self.url_queue_manager.add_url(url, priority=1.0, depth=0)
        else:
            # Fallback to simple queue
            url_queue = [(url, 1.0, 0) for url in self.start_urls]
        
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': self.user_agent}
        ) as session:
            
            processed_count = 0
            
            while processed_count < self.max_pages:
                # Get next URL
                if self.enable_url_queue_management:
                    next_url_data = self.url_queue_manager.get_next_url()
                    if not next_url_data:
                        break
                    current_url, priority = next_url_data
                    depth = 0  # Calculate depth from URL queue manager
                else:
                    if not url_queue:
                        break
                    current_url, priority, depth = url_queue.pop(0)
                
                # Skip if already processed or doesn't match patterns
                if (current_url in self.visited_urls or 
                    depth > self.max_depth or
                    not self._matches_patterns(current_url)):
                    continue
                
                # Check retry eligibility
                if self.enable_smart_retry and self.enable_url_queue_management:
                    if not self.url_queue_manager.can_retry(current_url):
                        logger.debug(f"Skipping {current_url}: max retries exceeded")
                        continue
                
                # Progress callback
                if progress_callback:
                    session_status = await self.get_crawl_session_status()
                    await progress_callback(session_status)
                
                try:
                    # Use smart retry mechanism if enabled
                    if self.enable_smart_retry:
                        page_data = await self.retry_mechanism.execute_with_retry(
                            current_url, 
                            self._crawl_page_with_pipeline, 
                            session, 
                            depth
                        )
                    else:
                        page_data = await self._crawl_page_with_pipeline(current_url, session, depth)
                    
                    if page_data and page_data.get('status') == 'success':
                        # Enhanced quality scoring
                        quality_score = page_data.get('quality_score', 0.0)
                        
                        # Skip low-quality content if filtering is enabled
                        if quality_score < self.quality_threshold:
                            logger.debug(f"Skipping low-quality content: {current_url} (score: {quality_score:.2f})")
                            continue
                        
                        # Add to results
                        crawled_data.append(page_data)
                        self.visited_urls.add(current_url)
                        processed_count += 1
                        
                        # Store in database if provided
                        if db and connector_id and organization_id:
                            await self.store_crawled_page(db, page_data, connector_id, organization_id, domain or "general")
                        
                        # Discover new URLs from extracted links
                        if depth < self.max_depth and 'links' in page_data:
                            discovered_links = page_data['links'].get('internal', [])
                            for link_data in discovered_links[:10]:  # Limit new URLs
                                new_url = link_data.get('url')
                                if new_url and new_url not in self.visited_urls:
                                    link_priority = self._calculate_link_priority(link_data, page_data)
                                    
                                    if self.enable_url_queue_management:
                                        self.url_queue_manager.add_url(new_url, link_priority, depth + 1)
                                    else:
                                        url_queue.append((new_url, link_priority, depth + 1))
                    
                except Exception as e:
                    logger.error(f"Error crawling {current_url}: {e}")
                    
                    # Mark as failed in queue manager
                    if self.enable_url_queue_management:
                        self.url_queue_manager.mark_failed(current_url)
                    
                    continue
                
                # Adaptive delay
                await asyncio.sleep(self.delay)
        
        logger.info(f"Completed advanced crawl session: {session_id}, processed: {processed_count} pages")
        return crawled_data

    async def _crawl_page_with_pipeline(self, url: str, session: aiohttp.ClientSession, depth: int = 0) -> Optional[Dict[str, Any]]:
        """Crawl page with advanced content pipeline"""
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return self._create_failed_page_data(url, f"HTTP {response.status}", depth)
                
                content_type = response.headers.get('content-type', '')
                if 'text/html' not in content_type:
                    return self._create_failed_page_data(url, "Not HTML content", depth)
                
                # Check file size
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > self.max_file_size:
                    return self._create_failed_page_data(url, f"File too large ({content_length} bytes)", depth)
                
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Process through advanced pipeline
                if self.enable_advanced_pipeline:
                    pipeline_config = {
                        'min_word_count': self.config.auth_config.get('content_filters', {}).get('min_word_count', 10),
                        'min_quality_score': self.quality_threshold,
                        'allowed_languages': self.config.auth_config.get('allowed_languages', [])
                    }
                    
                    page_data = await self.content_pipeline.process(soup, url, pipeline_config)
                    
                    # Add standard fields
                    page_data.update({
                        'crawled_at': datetime.utcnow(),
                        'depth': depth,
                        'content_type': content_type,
                        'file_size': len(html_content.encode('utf-8')),
                        'word_count': len(page_data.get('text_content', '').split()),
                        'content_hash': hashlib.md5(page_data.get('text_content', '').encode()).hexdigest()
                    })
                    
                    # Check if content was filtered
                    if 'filtered_reason' in page_data:
                        page_data['status'] = 'filtered'
                        logger.debug(f"Content filtered for {url}: {page_data['filtered_reason']}")
                    
                    return page_data
                else:
                    # Fallback to basic extraction
                    return await self._crawl_page(url, session)
                
        except Exception as e:
            logger.error(f"Error processing page {url}: {e}")
            return self._create_failed_page_data(url, str(e), depth)

    def _calculate_link_priority(self, link_data: Dict, parent_page_data: Dict) -> float:
        """Calculate priority for discovered links"""
        priority = 0.5  # Base priority
        
        # Priority based on link text
        link_text = link_data.get('text', '').lower()
        high_value_terms = ['documentation', 'guide', 'tutorial', 'api', 'help', 'support']
        medium_value_terms = ['about', 'contact', 'services', 'products']
        
        if any(term in link_text for term in high_value_terms):
            priority += 0.3
        elif any(term in link_text for term in medium_value_terms):
            priority += 0.1
        
        # Priority based on URL structure
        url = link_data.get('url', '')
        if '/docs/' in url or '/documentation/' in url:
            priority += 0.2
        elif '/api/' in url or '/help/' in url:
            priority += 0.15
        elif '/blog/' in url or '/news/' in url:
            priority += 0.05
        
        # Inherit some priority from parent page
        parent_quality = parent_page_data.get('quality_score', 0.5)
        priority += parent_quality * 0.1
        
        return min(1.0, priority)

    async def get_advanced_crawler_analytics(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Get comprehensive advanced analytics for the crawler"""
        try:
            # Enhanced crawl performance analytics
            performance_stats = db.execute(
                text("""
                    SELECT 
                        AVG(word_count) as avg_word_count,
                        STDDEV(word_count) as word_count_stddev,
                        COUNT(*) as total_pages,
                        COUNT(DISTINCT domain) as unique_domains,
                        AVG(CASE WHEN metadata->>'quality_score' IS NOT NULL 
                            THEN CAST(metadata->>'quality_score' AS FLOAT) END) as avg_quality_score
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id AND organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '30 days'
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchone()
            
            return {
                "performance_analytics": {
                    "avg_word_count": float(performance_stats.avg_word_count or 0),
                    "word_count_variance": float(performance_stats.word_count_stddev or 0),
                    "total_pages": performance_stats.total_pages or 0,
                    "domain_diversity": performance_stats.unique_domains or 0,
                    "avg_quality_score": float(performance_stats.avg_quality_score or 0)
                },
                "pipeline_analytics": await self._get_pipeline_effectiveness_metrics(db, connector_id, organization_id),
                "optimization_insights": await self._generate_optimization_insights(db, connector_id, organization_id)
            }
            
        except Exception as e:
            logger.error(f"Error getting advanced analytics: {e}")
            return {"error": str(e)}

    async def optimize_crawler_settings(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Generate data-driven optimization recommendations"""
        try:
            # Analyze current performance patterns
            analytics = await self.get_advanced_crawler_analytics(db, connector_id, organization_id)
            
            recommendations = []
            
            # Quality-based optimization
            avg_quality = analytics.get("performance_analytics", {}).get("avg_quality_score", 0)
            if avg_quality < 0.5:
                recommendations.append({
                    "type": "quality_improvement",
                    "priority": "high",
                    "suggestion": "Increase content quality threshold to filter low-value pages",
                    "current_value": avg_quality,
                    "recommended_value": 0.6,
                    "expected_impact": "25% reduction in storage, improved search relevance"
                })
            
            # Performance optimization
            total_pages = analytics.get("performance_analytics", {}).get("total_pages", 0)
            if total_pages > 10000:
                recommendations.append({
                    "type": "scale_optimization",
                    "priority": "medium",
                    "suggestion": "Enable incremental crawling to reduce redundant processing",
                    "current_value": "full_crawl",
                    "recommended_value": "incremental",
                    "expected_impact": "60% faster crawl times"
                })
            
            return {
                "optimization_score": self._calculate_crawler_optimization_score(analytics),
                "recommendations": recommendations,
                "performance_forecast": await self._forecast_crawl_performance(db, connector_id, organization_id)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing crawler settings: {e}")
            return {"error": str(e)}

    async def _get_pipeline_effectiveness_metrics(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Calculate effectiveness metrics for the content extraction pipeline"""
        try:
            # Pipeline success rates
            pipeline_stats = db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_processed,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_extractions,
                        COUNT(CASE WHEN metadata->>'extracted_keywords' IS NOT NULL THEN 1 END) as keyword_extractions,
                        COUNT(CASE WHEN metadata->>'topic_categories' IS NOT NULL THEN 1 END) as topic_extractions,
                        AVG(CASE WHEN metadata->>'readability_score' IS NOT NULL 
                            THEN CAST(metadata->>'readability_score' AS FLOAT) END) as avg_readability
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id AND organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '7 days'
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchone()
            
            total = pipeline_stats.total_processed or 1
            
            return {
                "extraction_success_rate": (pipeline_stats.successful_extractions or 0) / total,
                "keyword_extraction_rate": (pipeline_stats.keyword_extractions or 0) / total,
                "topic_extraction_rate": (pipeline_stats.topic_extractions or 0) / total,
                "avg_readability_score": float(pipeline_stats.avg_readability or 0),
                "pipeline_efficiency": self._calculate_pipeline_efficiency(pipeline_stats)
            }
            
        except Exception as e:
            logger.warning(f"Error calculating pipeline metrics: {e}")
            return {}

    async def _generate_optimization_insights(self, db: Session, connector_id: str, organization_id: str) -> List[Dict[str, Any]]:
        """Generate actionable optimization insights"""
        insights = []
        
        try:
            # URL pattern analysis
            url_patterns = db.execute(
                text("""
                    SELECT 
                        REGEXP_REPLACE(url, '[0-9]+', 'N', 'g') as url_pattern,
                        COUNT(*) as frequency,
                        AVG(word_count) as avg_content_length,
                        AVG(CASE WHEN metadata->>'quality_score' IS NOT NULL 
                            THEN CAST(metadata->>'quality_score' AS FLOAT) END) as avg_quality
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id AND organization_id = :org_id
                    GROUP BY url_pattern
                    HAVING COUNT(*) > 5
                    ORDER BY frequency DESC
                    LIMIT 10
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            for pattern in url_patterns:
                if pattern.avg_quality and pattern.avg_quality < 0.4:
                    insights.append({
                        "type": "url_pattern_exclusion",
                        "message": f"URL pattern '{pattern.url_pattern}' shows low quality content",
                        "impact": f"Excluding would save {pattern.frequency} pages with avg quality {pattern.avg_quality:.2f}",
                        "recommendation": f"Add exclude pattern: {pattern.url_pattern}"
                    })
            
            # Content type analysis
            content_types = db.execute(
                text("""
                    SELECT 
                        content_type,
                        COUNT(*) as frequency,
                        AVG(word_count) as avg_word_count
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id AND organization_id = :org_id
                    GROUP BY content_type
                    ORDER BY frequency DESC
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            for content_type in content_types:
                if content_type.avg_word_count and content_type.avg_word_count < 50:
                    insights.append({
                        "type": "content_type_filtering",
                        "message": f"Content type '{content_type.content_type}' has minimal text content",
                        "impact": f"Filtering would reduce {content_type.frequency} low-value pages",
                        "recommendation": f"Consider excluding content type: {content_type.content_type}"
                    })
            
        except Exception as e:
            logger.warning(f"Error generating optimization insights: {e}")
        
        return insights

    def _calculate_pipeline_efficiency(self, stats) -> float:
        """Calculate overall pipeline efficiency score"""
        if not stats.total_processed:
            return 0.0
        
        extraction_rate = (stats.successful_extractions or 0) / stats.total_processed
        enhancement_rate = ((stats.keyword_extractions or 0) + (stats.topic_extractions or 0)) / (2 * stats.total_processed)
        
        return (extraction_rate * 0.6 + enhancement_rate * 0.4)

    def _calculate_crawler_optimization_score(self, analytics: Dict) -> float:
        """Calculate overall crawler optimization score (0-100)"""
        performance = analytics.get("performance_analytics", {})
        pipeline = analytics.get("pipeline_analytics", {})
        
        # Quality score (0-30 points)
        quality_score = min(30, (performance.get("avg_quality_score", 0) * 30))
        
        # Pipeline efficiency (0-25 points)
        pipeline_score = min(25, (pipeline.get("pipeline_efficiency", 0) * 25))
        
        # Content diversity (0-20 points)
        diversity_score = min(20, (performance.get("domain_diversity", 0) / max(1, performance.get("total_pages", 1) / 100)) * 20)
        
        # Performance consistency (0-25 points)
        variance = performance.get("word_count_variance", 0)
        avg_words = performance.get("avg_word_count", 1)
        consistency = max(0, 1 - (variance / max(1, avg_words)))
        consistency_score = consistency * 25
        
        return min(100, quality_score + pipeline_score + diversity_score + consistency_score)

    async def _forecast_crawl_performance(self, db: Session, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Forecast future crawl performance based on historical data"""
        try:
            # Get historical performance data
            historical_data = db.execute(
                text("""
                    SELECT 
                        DATE_TRUNC('day', last_crawled) as crawl_date,
                        COUNT(*) as pages_crawled,
                        AVG(word_count) as avg_content_length,
                        COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_pages
                    FROM crawled_pages 
                    WHERE connector_id = :connector_id AND organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '30 days'
                    GROUP BY DATE_TRUNC('day', last_crawled)
                    ORDER BY crawl_date DESC
                    LIMIT 30
                """),
                {"connector_id": connector_id, "org_id": organization_id}
            ).fetchall()
            
            if len(historical_data) < 3:
                return {"forecast": "Insufficient historical data for prediction"}
            
            # Simple trend analysis
            pages_trend = []
            quality_trend = []
            
            for day in historical_data:
                pages_trend.append(day.pages_crawled)
                success_rate = (day.successful_pages / max(1, day.pages_crawled)) * 100
                quality_trend.append(success_rate)
            
            # Calculate trends
            avg_pages_per_day = statistics.mean(pages_trend)
            avg_success_rate = statistics.mean(quality_trend)
            
            # Simple linear trend
            recent_avg = statistics.mean(pages_trend[:7]) if len(pages_trend) >= 7 else avg_pages_per_day
            older_avg = statistics.mean(pages_trend[7:14]) if len(pages_trend) >= 14 else avg_pages_per_day
            
            growth_rate = (recent_avg - older_avg) / max(1, older_avg) if older_avg > 0 else 0
            
            return {
                "avg_pages_per_day": round(avg_pages_per_day, 1),
                "success_rate_percentage": round(avg_success_rate, 1),
                "growth_rate_percentage": round(growth_rate * 100, 1),
                "predicted_next_week": round(avg_pages_per_day * 7 * (1 + growth_rate), 0),
                "trend": "increasing" if growth_rate > 0.05 else "decreasing" if growth_rate < -0.05 else "stable"
            }
            
        except Exception as e:
            logger.warning(f"Error forecasting performance: {e}")
            return {"forecast": "Error generating forecast"}


# ============================================================================
# MACHINE LEARNING ENHANCEMENTS
# ============================================================================

@dataclass
class MLContentClassifier:
    """Machine learning-based content classification and quality prediction"""
    model_type: str = "ensemble"
    confidence_threshold: float = 0.7
    feature_extractors: List[str] = field(default_factory=lambda: [
        'text_statistics', 'structure_analysis', 'semantic_features', 'readability_metrics'
    ])
    
    def extract_features(self, content: str, metadata: Dict, soup: BeautifulSoup) -> Dict[str, float]:
        """Extract comprehensive feature set for ML classification"""
        features = {}
        
        # Text statistical features
        if 'text_statistics' in self.feature_extractors:
            features.update(self._extract_text_statistics(content))
        
        # HTML structure features
        if 'structure_analysis' in self.feature_extractors:
            features.update(self._extract_structure_features(soup))
        
        # Semantic features
        if 'semantic_features' in self.feature_extractors:
            features.update(self._extract_semantic_features(content))
        
        # Readability features
        if 'readability_metrics' in self.feature_extractors:
            features.update(self._extract_readability_features(content))
        
        return features
    
    def _extract_text_statistics(self, content: str) -> Dict[str, float]:
        """Extract statistical features from text content"""
        if not content:
            return {}
        
        words = content.split()
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        
        return {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_word_length': statistics.mean([len(word) for word in words]) if words else 0,
            'avg_sentence_length': statistics.mean([len(sentence.split()) for sentence in sentences]) if sentences else 0,
            'unique_word_ratio': len(set(words)) / max(1, len(words)),
            'punctuation_density': sum(1 for char in content if char in '.,!?;:') / max(1, len(content)),
            'uppercase_ratio': sum(1 for char in content if char.isupper()) / max(1, len(content)),
            'digit_density': sum(1 for char in content if char.isdigit()) / max(1, len(content))
        }
    
    def _extract_structure_features(self, soup: BeautifulSoup) -> Dict[str, float]:
        """Extract HTML structure features"""
        return {
            'heading_count': len(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
            'paragraph_count': len(soup.find_all('p')),
            'link_density': len(soup.find_all('a', href=True)) / max(1, len(soup.get_text().split())),
            'image_count': len(soup.find_all('img')),
            'list_count': len(soup.find_all(['ul', 'ol'])),
            'table_count': len(soup.find_all('table')),
            'form_count': len(soup.find_all('form')),
            'script_count': len(soup.find_all('script')),
            'css_count': len(soup.find_all('style')) + len(soup.find_all('link', rel='stylesheet')),
            'html_text_ratio': len(soup.get_text()) / max(1, len(str(soup)))
        }
    
    def _extract_semantic_features(self, content: str) -> Dict[str, float]:
        """Extract semantic features using keyword analysis"""
        if not content:
            return {}
        
        content_lower = content.lower()
        
        # Topic indicators
        tech_keywords = ['api', 'code', 'programming', 'software', 'development', 'documentation']
        business_keywords = ['company', 'product', 'service', 'customer', 'business', 'solution']
        support_keywords = ['help', 'support', 'faq', 'guide', 'tutorial', 'troubleshoot']
        news_keywords = ['news', 'article', 'update', 'announcement', 'press', 'release']
        
        return {
            'tech_content_score': sum(1 for kw in tech_keywords if kw in content_lower) / len(tech_keywords),
            'business_content_score': sum(1 for kw in business_keywords if kw in content_lower) / len(business_keywords),
            'support_content_score': sum(1 for kw in support_keywords if kw in content_lower) / len(support_keywords),
            'news_content_score': sum(1 for kw in news_keywords if kw in content_lower) / len(news_keywords),
            'question_density': content.count('?') / max(1, len(content.split())),
            'exclamation_density': content.count('!') / max(1, len(content.split())),
            'numerical_content_ratio': len([w for w in content.split() if any(c.isdigit() for c in w)]) / max(1, len(content.split()))
        }
    
    def _extract_readability_features(self, content: str) -> Dict[str, float]:
        """Extract readability and linguistic features"""
        if not content:
            return {}
        
        words = content.split()
        sentences = [s.strip() for s in content.split('.') if s.strip()]
        
        # Complex word analysis (words with 3+ syllables)
        complex_words = []
        for word in words:
            syllable_count = len([char for char in word.lower() if char in 'aeiou'])
            if syllable_count >= 3:
                complex_words.append(word)
        
        return {
            'complex_word_ratio': len(complex_words) / max(1, len(words)),
            'syllable_density': sum(len([c for c in word if c.lower() in 'aeiou']) for word in words) / max(1, len(words)),
            'passive_voice_indicators': sum(1 for phrase in ['was', 'were', 'been', 'being'] if phrase in content.lower()) / max(1, len(words)),
            'transition_word_density': sum(1 for phrase in ['however', 'therefore', 'moreover', 'furthermore', 'additionally'] if phrase in content.lower()) / max(1, len(words))
        }
    
    def predict_content_quality(self, features: Dict[str, float]) -> Dict[str, Any]:
        """Predict content quality using extracted features"""
        # Simplified ML prediction (in production, use trained models)
        quality_score = 0.0
        confidence = 0.0
        
        # Quality indicators
        if features.get('word_count', 0) > 100:
            quality_score += 0.2
        if features.get('heading_count', 0) > 0:
            quality_score += 0.15
        if features.get('unique_word_ratio', 0) > 0.5:
            quality_score += 0.15
        if features.get('html_text_ratio', 0) > 0.3:
            quality_score += 0.15
        if features.get('complex_word_ratio', 0) > 0.1:
            quality_score += 0.1
        
        # Content type prediction
        content_type = "general"
        if features.get('tech_content_score', 0) > 0.3:
            content_type = "technical"
        elif features.get('business_content_score', 0) > 0.3:
            content_type = "business"
        elif features.get('support_content_score', 0) > 0.3:
            content_type = "support"
        elif features.get('news_content_score', 0) > 0.3:
            content_type = "news"
        
        # Calculate confidence based on feature strength
        feature_strength = statistics.mean([v for v in features.values() if isinstance(v, (int, float)) and v > 0])
        confidence = min(1.0, feature_strength * 2)
        
        return {
            'quality_score': min(1.0, quality_score),
            'confidence': confidence,
            'predicted_type': content_type,
            'feature_importance': self._calculate_feature_importance(features),
            'quality_reasons': self._generate_quality_reasons(features, quality_score)
        }
    
    def _calculate_feature_importance(self, features: Dict[str, float]) -> Dict[str, float]:
        """Calculate relative importance of features for quality prediction"""
        important_features = {
            'word_count': 0.25,
            'unique_word_ratio': 0.20,
            'heading_count': 0.15,
            'html_text_ratio': 0.15,
            'complex_word_ratio': 0.10,
            'avg_sentence_length': 0.10,
            'link_density': 0.05
        }
        
        # Normalize by actual feature values
        importance = {}
        for feature, weight in important_features.items():
            feature_value = features.get(feature, 0)
            importance[feature] = weight * min(1.0, feature_value / 100 if feature == 'word_count' else feature_value)
        
        return importance
    
    def _generate_quality_reasons(self, features: Dict[str, float], quality_score: float) -> List[str]:
        """Generate human-readable reasons for quality score"""
        reasons = []
        
        if features.get('word_count', 0) > 500:
            reasons.append("Substantial content length")
        elif features.get('word_count', 0) < 50:
            reasons.append("Content too short")
        
        if features.get('heading_count', 0) > 3:
            reasons.append("Well-structured with headings")
        elif features.get('heading_count', 0) == 0:
            reasons.append("Lacks structural organization")
        
        if features.get('unique_word_ratio', 0) > 0.7:
            reasons.append("Rich vocabulary diversity")
        elif features.get('unique_word_ratio', 0) < 0.3:
            reasons.append("Limited vocabulary")
        
        if features.get('html_text_ratio', 0) > 0.5:
            reasons.append("High content-to-markup ratio")
        elif features.get('html_text_ratio', 0) < 0.2:
            reasons.append("Content diluted by markup")
        
        return reasons


# ============================================================================
# COMPETITIVE INTELLIGENCE FEATURES
# ============================================================================

@dataclass
class CompetitiveIntelligence:
    """Competitive analysis and market intelligence capabilities"""
    competitor_domains: List[str] = field(default_factory=list)
    analysis_dimensions: List[str] = field(default_factory=lambda: [
        'content_volume', 'update_frequency', 'topic_coverage', 'quality_metrics'
    ])
    
    async def analyze_competitive_landscape(self, db: Session, organization_id: str) -> Dict[str, Any]:
        """Analyze competitive landscape across crawler data"""
        try:
            # Aggregate competitive data
            competitive_data = db.execute(
                text("""
                    SELECT 
                        REGEXP_REPLACE(url, '^https?://([^/]+).*', '\\1') as domain,
                        COUNT(*) as page_count,
                        AVG(word_count) as avg_content_length,
                        MAX(last_crawled) as latest_update,
                        AVG(CASE WHEN metadata->>'quality_score' IS NOT NULL 
                            THEN CAST(metadata->>'quality_score' AS FLOAT) END) as avg_quality,
                        COUNT(DISTINCT CASE WHEN metadata->>'topic_categories' IS NOT NULL 
                            THEN metadata->>'topic_categories' END) as topic_diversity
                    FROM crawled_pages 
                    WHERE organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '90 days'
                    GROUP BY REGEXP_REPLACE(url, '^https?://([^/]+).*', '\\1')
                    HAVING COUNT(*) > 10
                    ORDER BY page_count DESC
                    LIMIT 20
                """),
                {"org_id": organization_id}
            ).fetchall()
            
            # Analyze market positioning
            market_analysis = self._analyze_market_positioning(competitive_data)
            
            # Content gap analysis
            content_gaps = await self._identify_content_gaps(db, organization_id, competitive_data)
            
            # Trend analysis
            trend_analysis = await self._analyze_content_trends(db, organization_id)
            
            return {
                "competitive_landscape": {
                    "total_competitors_analyzed": len(competitive_data),
                    "market_leaders": [
                        {
                            "domain": comp.domain,
                            "page_count": comp.page_count,
                            "avg_quality": float(comp.avg_quality or 0),
                            "market_share": comp.page_count / sum(c.page_count for c in competitive_data) * 100
                        }
                        for comp in competitive_data[:5]
                    ],
                    "market_analysis": market_analysis
                },
                "content_opportunities": content_gaps,
                "trend_insights": trend_analysis,
                "competitive_recommendations": self._generate_competitive_recommendations(competitive_data, content_gaps)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing competitive landscape: {e}")
            return {"error": str(e)}
    
    def _analyze_market_positioning(self, competitive_data) -> Dict[str, Any]:
        """Analyze market positioning based on content metrics"""
        if not competitive_data:
            return {}
        
        # Calculate market segments
        page_counts = [comp.page_count for comp in competitive_data]
        quality_scores = [float(comp.avg_quality or 0) for comp in competitive_data]
        
        high_volume_threshold = statistics.median(page_counts) * 1.5
        high_quality_threshold = statistics.median(quality_scores) * 1.1
        
        segments = {
            "market_leaders": [],  # High volume + High quality
            "quality_focused": [],  # Low volume + High quality
            "volume_focused": [],  # High volume + Low quality
            "emerging_players": []  # Low volume + Low quality
        }
        
        for comp in competitive_data:
            volume = comp.page_count
            quality = float(comp.avg_quality or 0)
            
            if volume >= high_volume_threshold and quality >= high_quality_threshold:
                segments["market_leaders"].append(comp.domain)
            elif volume < high_volume_threshold and quality >= high_quality_threshold:
                segments["quality_focused"].append(comp.domain)
            elif volume >= high_volume_threshold and quality < high_quality_threshold:
                segments["volume_focused"].append(comp.domain)
            else:
                segments["emerging_players"].append(comp.domain)
        
        return {
            "market_segments": segments,
            "market_concentration": len(segments["market_leaders"]) / len(competitive_data),
            "quality_vs_volume_correlation": self._calculate_correlation(page_counts, quality_scores)
        }
    
    async def _identify_content_gaps(self, db: Session, organization_id: str, competitive_data) -> List[Dict[str, Any]]:
        """Identify content gaps and opportunities"""
        try:
            # Analyze topic coverage across competitors
            topic_analysis = db.execute(
                text("""
                    SELECT 
                        REGEXP_REPLACE(url, '^https?://([^/]+).*', '\\1') as domain,
                        metadata->>'topic_categories' as topics,
                        COUNT(*) as frequency
                    FROM crawled_pages 
                    WHERE organization_id = :org_id
                    AND metadata->>'topic_categories' IS NOT NULL
                    AND last_crawled > NOW() - INTERVAL '30 days'
                    GROUP BY domain, metadata->>'topic_categories'
                    ORDER BY frequency DESC
                """),
                {"org_id": organization_id}
            ).fetchall()
            
            # Find topics with low coverage
            topic_coverage = {}
            for analysis in topic_analysis:
                topics = analysis.topics
                if topics:
                    for topic in topics.split(','):
                        topic = topic.strip()
                        if topic not in topic_coverage:
                            topic_coverage[topic] = []
                        topic_coverage[topic].append(analysis.domain)
            
            gaps = []
            for topic, domains in topic_coverage.items():
                if len(domains) < 3:  # Low competition
                    gaps.append({
                        "topic": topic,
                        "competition_level": "low",
                        "covering_domains": domains,
                        "opportunity_score": self._calculate_opportunity_score(topic, len(domains))
                    })
            
            return sorted(gaps, key=lambda x: x["opportunity_score"], reverse=True)[:10]
            
        except Exception as e:
            logger.warning(f"Error identifying content gaps: {e}")
            return []
    
    async def _analyze_content_trends(self, db: Session, organization_id: str) -> Dict[str, Any]:
        """Analyze content trends across time periods"""
        try:
            # Weekly content volume trends
            weekly_trends = db.execute(
                text("""
                    SELECT 
                        DATE_TRUNC('week', last_crawled) as week,
                        COUNT(*) as page_count,
                        AVG(word_count) as avg_content_length,
                        COUNT(DISTINCT REGEXP_REPLACE(url, '^https?://([^/]+).*', '\\1')) as active_domains
                    FROM crawled_pages 
                    WHERE organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '12 weeks'
                    GROUP BY DATE_TRUNC('week', last_crawled)
                    ORDER BY week DESC
                """),
                {"org_id": organization_id}
            ).fetchall()
            
            if len(weekly_trends) < 2:
                return {"trends": "Insufficient data for trend analysis"}
            
            # Calculate trend direction
            recent_volume = statistics.mean([t.page_count for t in weekly_trends[:4]])
            older_volume = statistics.mean([t.page_count for t in weekly_trends[4:8]]) if len(weekly_trends) >= 8 else recent_volume
            
            volume_trend = (recent_volume - older_volume) / max(1, older_volume)
            
            return {
                "content_volume_trend": {
                    "direction": "increasing" if volume_trend > 0.1 else "decreasing" if volume_trend < -0.1 else "stable",
                    "change_percentage": round(volume_trend * 100, 1)
                },
                "market_activity": {
                    "weekly_avg_pages": round(statistics.mean([t.page_count for t in weekly_trends]), 1),
                    "avg_active_domains": round(statistics.mean([t.active_domains for t in weekly_trends]), 1)
                }
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing trends: {e}")
            return {}
    
    def _calculate_correlation(self, x_values: List[float], y_values: List[float]) -> float:
        """Calculate correlation coefficient between two variables"""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0
        
        try:
            import statistics
            n = len(x_values)
            mean_x = statistics.mean(x_values)
            mean_y = statistics.mean(y_values)
            
            numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
            denominator_x = sum((x - mean_x) ** 2 for x in x_values)
            denominator_y = sum((y - mean_y) ** 2 for y in y_values)
            
            if denominator_x == 0 or denominator_y == 0:
                return 0.0
            
            correlation = numerator / (denominator_x * denominator_y) ** 0.5
            return max(-1.0, min(1.0, correlation))
        except:
            return 0.0
    
    def _calculate_opportunity_score(self, topic: str, competitor_count: int) -> float:
        """Calculate opportunity score for a topic based on competition and relevance"""
        # Base score inversely related to competition
        competition_score = max(0, 1 - (competitor_count / 10))
        
        # Topic relevance multipliers
        high_value_topics = ['api', 'documentation', 'tutorial', 'guide', 'integration']
        medium_value_topics = ['product', 'feature', 'update', 'news', 'blog']
        
        relevance_multiplier = 1.0
        if any(keyword in topic.lower() for keyword in high_value_topics):
            relevance_multiplier = 1.5
        elif any(keyword in topic.lower() for keyword in medium_value_topics):
            relevance_multiplier = 1.2
        
        return competition_score * relevance_multiplier
    
    def _generate_competitive_recommendations(self, competitive_data, content_gaps) -> List[Dict[str, Any]]:
        """Generate actionable competitive recommendations"""
        recommendations = []
        
        if competitive_data:
            top_performer = competitive_data[0]
            recommendations.append({
                "type": "benchmark_analysis",
                "priority": "high",
                "recommendation": f"Analyze {top_performer.domain} content strategy",
                "rationale": f"Market leader with {top_performer.page_count} pages and {float(top_performer.avg_quality or 0):.2f} avg quality",
                "action_items": [
                    "Study their content structure and topics",
                    "Analyze their update frequency",
                    "Identify content gaps in your coverage"
                ]
            })
        
        if content_gaps:
            top_gap = content_gaps[0]
            recommendations.append({
                "type": "content_opportunity",
                "priority": "medium",
                "recommendation": f"Develop content for '{top_gap['topic']}' topic",
                "rationale": f"Low competition with opportunity score {top_gap['opportunity_score']:.2f}",
                "action_items": [
                    "Research audience interest in this topic",
                    "Create comprehensive content plan",
                    "Monitor competitor responses"
                ]
            })
        
        return recommendations


# ============================================================================
# ADVANCED SECURITY & MONITORING
# ============================================================================

@dataclass
class AdvancedSecurityMonitor:
    """Advanced security monitoring and threat detection for web crawling"""
    threat_indicators: List[str] = field(default_factory=lambda: [
        'rate_limiting', 'ip_blocking', 'captcha_challenges', 'honeypot_detection',
        'behavioral_analysis', 'fingerprint_detection'
    ])
    alert_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'error_rate': 0.15,  # 15% error rate
        'response_time_degradation': 2.0,  # 2x slower than baseline
        'captcha_frequency': 0.05,  # 5% of requests
        'block_rate': 0.02  # 2% blocking rate
    })
    
    async def monitor_crawl_security(self, session_metrics: Dict, historical_baseline: Dict) -> Dict[str, Any]:
        """Monitor crawl session for security threats and anomalies"""
        threats_detected = []
        security_score = 100.0
        
        # Analyze error patterns
        error_analysis = self._analyze_error_patterns(session_metrics)
        if error_analysis['threat_level'] > 0:
            threats_detected.append(error_analysis)
            security_score -= error_analysis['threat_level'] * 20
        
        # Response time analysis
        response_analysis = self._analyze_response_degradation(session_metrics, historical_baseline)
        if response_analysis['anomaly_detected']:
            threats_detected.append(response_analysis)
            security_score -= 15
        
        # Behavioral pattern analysis
        behavioral_analysis = self._analyze_crawl_behavior(session_metrics)
        if behavioral_analysis['suspicious_patterns']:
            threats_detected.append(behavioral_analysis)
            security_score -= 25
        
        return {
            "security_status": "secure" if security_score > 80 else "warning" if security_score > 50 else "threat",
            "security_score": max(0, security_score),
            "threats_detected": threats_detected,
            "recommendations": self._generate_security_recommendations(threats_detected),
            "monitoring_timestamp": datetime.utcnow().isoformat()
        }
    
    def _analyze_error_patterns(self, metrics: Dict) -> Dict[str, Any]:
        """Analyze error patterns for security threats"""
        total_requests = metrics.get('total_requests', 1)
        error_codes = metrics.get('error_codes', {})
        
        # Calculate error rates by type
        error_analysis = {
            'threat_level': 0,
            'threat_type': 'error_patterns',
            'details': {}
        }
        
        # 403 Forbidden - IP blocking
        forbidden_rate = error_codes.get('403', 0) / total_requests
        if forbidden_rate > self.alert_thresholds['block_rate']:
            error_analysis['threat_level'] = min(1.0, forbidden_rate / self.alert_thresholds['block_rate'])
            error_analysis['details']['ip_blocking'] = f"{forbidden_rate:.1%} of requests blocked"
        
        # 429 Rate Limiting
        rate_limit_rate = error_codes.get('429', 0) / total_requests
        if rate_limit_rate > 0.01:  # 1% rate limiting
            error_analysis['threat_level'] = max(error_analysis['threat_level'], 0.5)
            error_analysis['details']['rate_limiting'] = f"{rate_limit_rate:.1%} rate limited"
        
        # 503 Service Unavailable - Possible overload
        unavailable_rate = error_codes.get('503', 0) / total_requests
        if unavailable_rate > 0.05:  # 5% unavailable
            error_analysis['threat_level'] = max(error_analysis['threat_level'], 0.3)
            error_analysis['details']['service_overload'] = f"{unavailable_rate:.1%} service unavailable"
        
        return error_analysis
    
    def _analyze_response_degradation(self, current_metrics: Dict, baseline: Dict) -> Dict[str, Any]:
        """Analyze response time degradation patterns"""
        current_avg_time = current_metrics.get('avg_response_time', 0)
        baseline_avg_time = baseline.get('avg_response_time', current_avg_time)
        
        if baseline_avg_time == 0:
            return {'anomaly_detected': False}
        
        degradation_ratio = current_avg_time / baseline_avg_time
        
        return {
            'anomaly_detected': degradation_ratio > self.alert_thresholds['response_time_degradation'],
            'threat_type': 'response_degradation',
            'degradation_ratio': degradation_ratio,
            'details': {
                'current_avg_ms': current_avg_time * 1000,
                'baseline_avg_ms': baseline_avg_time * 1000,
                'slowdown_factor': f"{degradation_ratio:.1f}x"
            }
        }
    
    def _analyze_crawl_behavior(self, metrics: Dict) -> Dict[str, Any]:
        """Analyze crawl behavior for suspicious patterns"""
        suspicious_patterns = []
        
        # Unusual request patterns
        request_frequency = metrics.get('requests_per_minute', 0)
        if request_frequency > 180:  # More than 3 req/sec
            suspicious_patterns.append({
                'pattern': 'high_frequency_requests',
                'value': request_frequency,
                'risk': 'moderate'
            })
        
        # CAPTCHA detection frequency
        captcha_rate = metrics.get('captcha_encounters', 0) / max(1, metrics.get('total_requests', 1))
        if captcha_rate > self.alert_thresholds['captcha_frequency']:
            suspicious_patterns.append({
                'pattern': 'frequent_captcha',
                'value': f"{captcha_rate:.1%}",
                'risk': 'high'
            })
        
        # Geographic access patterns (if available)
        unique_ips = metrics.get('unique_source_ips', 1)
        if unique_ips > 5:  # Multiple IP addresses
            suspicious_patterns.append({
                'pattern': 'multiple_ip_sources',
                'value': unique_ips,
                'risk': 'low'
            })
        
        return {
            'suspicious_patterns': suspicious_patterns,
            'threat_type': 'behavioral_anomaly',
            'overall_risk': max([p['risk'] for p in suspicious_patterns] + ['low'])
        }
    
    def _generate_security_recommendations(self, threats: List[Dict]) -> List[Dict[str, str]]:
        """Generate security recommendations based on detected threats"""
        recommendations = []
        
        for threat in threats:
            threat_type = threat.get('threat_type', '')
            
            if threat_type == 'error_patterns':
                if 'ip_blocking' in threat.get('details', {}):
                    recommendations.append({
                        'type': 'ip_rotation',
                        'action': 'Enable IP rotation or proxy usage',
                        'priority': 'high'
                    })
                if 'rate_limiting' in threat.get('details', {}):
                    recommendations.append({
                        'type': 'delay_adjustment',
                        'action': 'Increase crawl delay between requests',
                        'priority': 'medium'
                    })
            
            elif threat_type == 'response_degradation':
                recommendations.append({
                    'type': 'load_reduction',
                    'action': 'Reduce concurrent requests or implement backoff',
                    'priority': 'medium'
                })
            
            elif threat_type == 'behavioral_anomaly':
                recommendations.append({
                    'type': 'stealth_mode',
                    'action': 'Enable stealth crawling techniques',
                    'priority': 'high'
                })
        
        # Default recommendations if no specific threats
        if not recommendations:
            recommendations.append({
                'type': 'monitoring',
                'action': 'Continue monitoring crawl patterns',
                'priority': 'low'
            })
        
        return recommendations

