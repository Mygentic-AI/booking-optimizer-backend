"""
Throttling logic for sending medical narratives to diagnosis API.
Prevents overwhelming the diagnosis service while ensuring timely updates.
"""

import time
import yaml
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DiagnosisThrottler:
    """Manages when to send medical narratives for diagnosis based on configurable rules."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize throttler with configuration."""
        self.config = self._load_config(config_path)
        self.last_sent_time = 0
        self.last_sent_narrative = ""
        self.last_sent_word_count = 0
        
        # Extract config values
        throttle_config = self.config.get("diagnosis_throttling", {})
        self.minimum_interval = throttle_config.get("minimum_interval_seconds", 15)
        self.maximum_interval = throttle_config.get("maximum_interval_seconds", 60)
        self.word_count_threshold = throttle_config.get("word_count_threshold", 20)
        self.trigger_sections = throttle_config.get("trigger_sections", [])
        
        logger.info(f"DiagnosisThrottler initialized with config: min={self.minimum_interval}s, "
                   f"max={self.maximum_interval}s, word_threshold={self.word_count_threshold}")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load config from {config_path}: {e}. Using defaults.")
            return {}
    
    def should_send_update(self, narrative: str) -> bool:
        """
        Determine if we should send the narrative for diagnosis.
        
        Args:
            narrative: Current medical narrative
            
        Returns:
            bool: True if update should be sent, False otherwise
        """
        current_time = time.time()
        time_since_last = current_time - self.last_sent_time
        
        # Check minimum interval
        if time_since_last < self.minimum_interval:
            logger.debug(f"Too soon: {time_since_last:.1f}s < {self.minimum_interval}s")
            return False
        
        # Check if narrative changed
        if narrative == self.last_sent_narrative:
            logger.debug("Narrative unchanged")
            return False
        
        # Force send after maximum interval
        if time_since_last >= self.maximum_interval:
            logger.info(f"Maximum interval reached: {time_since_last:.1f}s")
            return True
        
        # Check word count change
        current_word_count = len(narrative.split())
        words_added = current_word_count - self.last_sent_word_count
        
        if words_added >= self.word_count_threshold:
            logger.info(f"Word threshold met: {words_added} words added")
            return True
        
        # Check for trigger sections
        for section in self.trigger_sections:
            if section in narrative and section not in self.last_sent_narrative:
                logger.info(f"Trigger section detected: {section}")
                return True
        
        logger.debug(f"No triggers met: {time_since_last:.1f}s elapsed, {words_added} words added")
        return False
    
    def mark_sent(self, narrative: str):
        """
        Mark that a narrative was sent.
        
        Args:
            narrative: The narrative that was sent
        """
        self.last_sent_time = time.time()
        self.last_sent_narrative = narrative
        self.last_sent_word_count = len(narrative.split())
        logger.debug(f"Marked sent: {self.last_sent_word_count} words at {self.last_sent_time}")