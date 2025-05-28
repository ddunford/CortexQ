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
from dataclasses import dataclass, asdict
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

from .base_connector import BaseConnector, Document, ConnectorConfig

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


class WebScraperConnector(BaseConnector):
    """Enhanced web scraper connector with comprehensive features"""
    
    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
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

    async def store_crawled_page(self, db: Session, page_data: Dict, connector_id: str, organization_id: str, domain: str):
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
                        WHERE url_hash = :url_hash AND connector_id = :connector_id AND organization_id = :org_id
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
                        "connector_id": connector_id,
                        "org_id": organization_id
                    }
                )
            else:
                # Insert new page
                db.execute(
                    text("""
                        INSERT INTO crawled_pages (
                            connector_id, organization_id, domain, url, url_hash,
                            title, content, metadata, first_crawled, last_crawled,
                            content_hash, word_count, status, error_message,
                            depth, content_type, file_size, created_at, updated_at
                        ) VALUES (
                            :connector_id, :organization_id, :domain, :url, :url_hash,
                            :title, :content, :metadata, :crawled_at, :crawled_at,
                            :content_hash, :word_count, :status, :error_message,
                            :depth, :content_type, :file_size, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                    """),
                    {
                        "connector_id": connector_id,
                        "organization_id": organization_id,
                        "domain": domain,
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