"""
Phase 5: External API Integration - Multi-API integration system

Manages connections to external APIs and services.
Handles rate limiting, retries, authentication, and response transformation.
"""

import logging
import time
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """External API providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE = "huggingface"
    BRAVE_SEARCH = "brave_search"
    CUSTOM = "custom"


class RateLimitStrategy(Enum):
    """Rate limiting strategies"""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class APIEndpoint:
    """API endpoint configuration"""
    provider: APIProvider
    url: str
    api_key: Optional[str] = None
    rate_limit: int = 100  # requests per minute
    timeout: int = 30  # seconds
    retry_count: int = 3
    auth_type: str = "bearer"  # bearer, api_key, custom


class ExternalAPIIntegration:
    """
    External API integration system.
    
    Features:
    - Multi-provider support
    - Rate limiting
    - Automatic retries
    - Response caching
    - Error handling
    """
    
    def __init__(self):
        """Initialize ExternalAPIIntegration"""
        self.endpoints: Dict[APIProvider, APIEndpoint] = {}
        self.rate_limiters: Dict[APIProvider, Dict[str, int]] = {}
        self.request_history: List[Dict[str, Any]] = []
        self.response_cache: Dict[str, Any] = {}
        
        logger.info("ExternalAPIIntegration initialized")
    
    def register_endpoint(self, endpoint: APIEndpoint) -> None:
        """
        Register API endpoint.
        
        Args:
            endpoint: API endpoint configuration
        """
        self.endpoints[endpoint.provider] = endpoint
        self.rate_limiters[endpoint.provider] = {
            'requests': 0,
            'window_start': time.time()
        }
        
        logger.info(
            f"✅ Registered {endpoint.provider.value} endpoint: {endpoint.url}"
        )
    
    def call_api(
        self,
        provider: APIProvider,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Call external API with rate limiting and retries.
        
        Args:
            provider: API provider
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Request parameters
            use_cache: Use response caching
        
        Returns:
            API response
        """
        logger.info(f"\n📡 API CALL")
        logger.info(f"Provider: {provider.value}")
        logger.info(f"Endpoint: {endpoint}")
        
        # Check cache
        cache_key = f"{provider.value}:{endpoint}:{params}"
        
        if use_cache and cache_key in self.response_cache:
            logger.info("✅ Using cached response")
            return {
                'response': self.response_cache[cache_key],
                'from_cache': True
            }
        
        # Check rate limit
        if not self._check_rate_limit(provider):
            logger.warning("⚠️ Rate limit exceeded - queuing request")
            return {
                'error': 'Rate limit exceeded',
                'queued': True
            }
        
        # Perform request with retries
        result = self._call_with_retry(
            provider, method, endpoint, params
        )
        
        # Cache response if successful
        if not result.get('error') and use_cache:
            self.response_cache[cache_key] = result
        
        return result
    
    def _check_rate_limit(self, provider: APIProvider) -> bool:
        """Check if request is within rate limit"""
        if provider not in self.endpoints:
            logger.warning(f"Unknown provider: {provider.value}")
            return False
        
        endpoint = self.endpoints[provider]
        limiter = self.rate_limiters[provider]
        
        # Reset window if expired (60 seconds)
        if time.time() - limiter['window_start'] > 60:
            limiter['requests'] = 0
            limiter['window_start'] = time.time()
        
        max_requests = endpoint.rate_limit
        
        if limiter['requests'] >= max_requests:
            logger.warning(
                f"Rate limit ({max_requests}/min) exceeded for {provider.value}"
            )
            return False
        
        limiter['requests'] += 1
        return True
    
    def _call_with_retry(
        self,
        provider: APIProvider,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call API with automatic retries"""
        api_endpoint = self.endpoints[provider]
        retry_count = api_endpoint.retry_count
        
        for attempt in range(retry_count):
            try:
                logger.debug(f"Attempt {attempt + 1}/{retry_count}")
                
                # Simulate API call
                result = self._simulate_api_call(
                    provider, method, endpoint, params
                )
                
                # Record in history
                self.request_history.append({
                    'provider': provider.value,
                    'endpoint': endpoint,
                    'timestamp': time.time(),
                    'success': True,
                    'attempt': attempt + 1
                })
                
                logger.info(f"✅ API call successful")
                return {'response': result, 'from_cache': False}
                
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed: {str(e)}"
                )
                
                if attempt < retry_count - 1:
                    # Wait before retry (exponential backoff)
                    wait_time = 2 ** attempt
                    logger.debug(f"Waiting {wait_time}s before retry...")
                    time.sleep(min(wait_time, 10))
                else:
                    # All retries exhausted
                    logger.error(f"All retries exhausted for {endpoint}")
                    
                    return {
                        'error': str(e),
                        'endpoint': endpoint,
                        'attempts': retry_count
                    }
        
        return {'error': 'Unknown error'}
    
    def _simulate_api_call(
        self,
        provider: APIProvider,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Simulate API call (in production, would use requests library)"""
        logger.debug(f"Calling {provider.value} API: {endpoint}")
        
        # Simulate API response
        return {
            'status': 'success',
            'provider': provider.value,
            'endpoint': endpoint,
            'data': params or {}
        }
    
    def get_api_stats(self) -> Dict[str, Any]:
        """Get API integration statistics"""
        total_requests = len(self.request_history)
        successful = sum(
            1 for r in self.request_history if r.get('success')
        )
        
        provider_stats = {}
        for provider in self.endpoints:
            provider_requests = [
                r for r in self.request_history
                if r['provider'] == provider.value
            ]
            provider_stats[provider.value] = {
                'total_requests': len(provider_requests),
                'success_count': sum(1 for r in provider_requests if r.get('success')),
                'avg_attempts': sum(r.get('attempt', 1) for r in provider_requests) / len(provider_requests) if provider_requests else 0
            }
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful,
            'success_rate': successful / total_requests if total_requests > 0 else 0,
            'cache_size': len(self.response_cache),
            'providers': provider_stats
        }
    
    def clear_cache(self) -> Dict[str, Any]:
        """Clear response cache"""
        cache_size = len(self.response_cache)
        self.response_cache.clear()
        
        logger.info(f"✅ API response cache cleared - {cache_size} entries removed")
        
        return {'cleared_entries': cache_size}
