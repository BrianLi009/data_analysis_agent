# -*- coding: utf-8 -*-
"""
Configuration management module
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


from dotenv import load_dotenv
load_dotenv()



@dataclass
class LLMConfig:
    """LLM configuration"""

    provider: str = "openai"  # openai, anthropic, etc.
    api_key: str = os.environ.get("OPENAI_API_KEY", "")
    base_url: str = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model: str = os.environ.get("OPENAI_MODEL", "gpt-4-turbo-preview")
    temperature: float = 0.1
    max_tokens: int = 16384

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMConfig':
        """Create configuration from dictionary"""
        return cls(**data)

    def validate(self) -> bool:
        """Validate configuration validity"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if not self.base_url:
            raise ValueError("OPENAI_BASE_URL is required")
        if not self.model:
            raise ValueError("OPENAI_MODEL is required")
        return True
