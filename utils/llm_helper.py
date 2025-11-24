# -*- coding: utf-8 -*-
"""
LLM call helper module
"""

import asyncio
import yaml
from config.llm_config import LLMConfig
from utils.fallback_openai_client import AsyncFallbackOpenAIClient

class LLMHelper:
    """LLM call helper class, supports synchronous and asynchronous calls"""
    
    def __init__(self, config: LLMConfig = None):
        self.config = config
        self.client = AsyncFallbackOpenAIClient(
            primary_api_key=config.api_key,
            primary_base_url=config.base_url,
            primary_model_name=config.model
        )
    
    async def async_call(self, prompt: str, system_prompt: str = None, max_tokens: int = None, temperature: float = None) -> str:
        """Asynchronously call LLM"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        kwargs = {}
        if max_tokens is not None:
            kwargs['max_tokens'] = max_tokens
        else:
            kwargs['max_tokens'] = self.config.max_tokens
            
        if temperature is not None:
            kwargs['temperature'] = temperature
        else:
            kwargs['temperature'] = self.config.temperature
            
        try:
            response = await self.client.chat_completions_create(
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""
    
    def call(self, prompt: str, system_prompt: str = None, max_tokens: int = None, temperature: float = None) -> str:
        """Synchronously call LLM"""
        return asyncio.run(self.async_call(prompt, system_prompt, max_tokens, temperature))
    
    def parse_yaml_response(self, response: str) -> dict:
        """Parse YAML format response"""
        try:
            # Extract content between ```yaml and ```
            if '```yaml' in response:
                start = response.find('```yaml') + 7
                end = response.find('```', start)
                yaml_content = response[start:end].strip()
            elif '```' in response:
                start = response.find('```') + 3
                end = response.find('```', start)
                yaml_content = response[start:end].strip()
            else:
                yaml_content = response.strip()
            
            return yaml.safe_load(yaml_content)
        except Exception as e:
            print(f"YAML parsing failed: {e}")
            print(f"Original response: {response}")
            return {}
    
    async def close(self):
        """Close client"""
        await self.client.close()