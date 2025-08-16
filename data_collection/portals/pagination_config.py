"""
Configuration settings for Portals API pagination.
This file contains all the configurable parameters for pagination behavior.
"""

# Pagination limits and thresholds
PAGINATION_CONFIG = {
    # Maximum offset to prevent infinite loops
    "max_offset": 10000,
    
    # Number of items per page
    "limit": 100,
    
    # Retry settings
    "max_retries": 3,
    "retry_delay": 1.0,
    "retry_backoff_multiplier": 2,
    
    # Consecutive page thresholds
    "max_consecutive_empty_pages": 3,
    "max_consecutive_repeated_pages": 5,
    
    # Rate limiting delays (in seconds)
    "base_delay": (0.8, 1.2),  # Random range
    "repeated_page_delay_base": 0.5,
    "repeated_page_delay_multiplier": 0.3,
    "max_delay": 2.0,
    
    # HTTP status codes
    "rate_limit_status": 429,
    "success_status": 200,
    
    # Timeout settings
    "request_timeout": 30,  # seconds
    
    # Debug settings
    "verbose_logging": True,
    "log_duplicate_ids": True,
    "log_repeated_ids": True,
}

# API endpoint configuration
API_CONFIG = {
    "base_url": "https://portals-market.com/api/",
    "search_endpoint": "nfts/search",
    "collections_endpoint": "collections",
    
    # Query parameters
    "default_status": "listed",
    "default_sort": "gift_id_asc",
    
    # Headers
    "headers": {
        "User-Agent": "TelegramBot",
        "Accept": "application/json",
    }
}

# Error handling configuration
ERROR_CONFIG = {
    # Retryable errors
    "retryable_status_codes": [429, 500, 502, 503, 504],
    
    # Fatal errors
    "fatal_status_codes": [400, 401, 403, 404],
    
    # Error messages
    "error_messages": {
        429: "Rate limited - too many requests",
        500: "Internal server error",
        502: "Bad gateway",
        503: "Service unavailable",
        504: "Gateway timeout",
        400: "Bad request - check parameters",
        401: "Unauthorized - check authentication",
        403: "Forbidden - access denied",
        404: "Not found - endpoint or resource not available",
    }
}

# Collection-specific overrides
COLLECTION_OVERRIDES = {
    # Some collections might need different settings
    "Plush Pepes": {
        "max_offset": 5000,  # Lower limit for testing
        "base_delay": (1.0, 1.5),  # Slower for this collection
    },
    "Telegram Stickers": {
        "max_offset": 8000,
        "base_delay": (0.6, 1.0),  # Faster for this collection
    },
}

def get_pagination_config(collection_name: str = None) -> dict:
    """
    Get pagination configuration, with optional collection-specific overrides.
    
    Args:
        collection_name (str, optional): Name of the collection for specific overrides
        
    Returns:
        dict: Configuration dictionary
    """
    config = PAGINATION_CONFIG.copy()
    
    if collection_name and collection_name in COLLECTION_OVERRIDES:
        config.update(COLLECTION_OVERRIDES[collection_name])
    
    return config


def get_api_config() -> dict:
    """Get API configuration."""
    return API_CONFIG.copy()


def get_error_config() -> dict:
    """Get error handling configuration."""
    return ERROR_CONFIG.copy()


# Validation functions
def validate_pagination_config(config: dict) -> bool:
    """
    Validate pagination configuration.
    
    Args:
        config (dict): Configuration to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_keys = [
        "max_offset", "limit", "max_retries", "retry_delay",
        "max_consecutive_empty_pages", "max_consecutive_repeated_pages"
    ]
    
    for key in required_keys:
        if key not in config:
            print(f"❌ Missing required config key: {key}")
            return False
    
    if config["limit"] <= 0:
        print("❌ Limit must be positive")
        return False
    
    if config["max_offset"] <= 0:
        print("❌ Max offset must be positive")
        return False
    
    return True


# Utility functions
def calculate_delay(config: dict, consecutive_repeated_pages: int = 0) -> float:
    """
    Calculate delay based on configuration and current state.
    
    Args:
        config (dict): Pagination configuration
        consecutive_repeated_pages (int): Number of consecutive repeated pages
        
    Returns:
        float: Delay in seconds
    """
    import random
    
    if consecutive_repeated_pages > 0:
        delay = config["repeated_page_delay_base"] + (consecutive_repeated_pages * config["repeated_page_delay_multiplier"])
        return min(config["max_delay"], delay)
    else:
        base_delay = config["base_delay"]
        return random.uniform(base_delay[0], base_delay[1])


def should_retry_request(status_code: int, config: dict) -> bool:
    """
    Determine if a request should be retried based on status code.
    
    Args:
        status_code (int): HTTP status code
        config (dict): Error configuration
        
    Returns:
        bool: True if request should be retried
    """
    return status_code in config.get("retryable_status_codes", [429, 500, 502, 503, 504])


def get_error_message(status_code: int, config: dict) -> str:
    """
    Get human-readable error message for status code.
    
    Args:
        status_code (int): HTTP status code
        config (dict): Error configuration
        
    Returns:
        str: Error message
    """
    error_messages = config.get("error_messages", {})
    return error_messages.get(status_code, f"Unknown error (status {status_code})")
