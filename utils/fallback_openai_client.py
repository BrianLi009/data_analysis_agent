# -*- coding: utf-8 -*-
import asyncio
from typing import Optional, Any, Mapping, Dict
from openai import AsyncOpenAI, APIStatusError, APIConnectionError, APITimeoutError, APIError
from openai.types.chat import ChatCompletion

class AsyncFallbackOpenAIClient:
    """
    An asynchronous OpenAI client that supports automatic fallback API switching.
    When the primary API call fails due to specific errors (such as content filtering), it will automatically try to use the fallback API.
    """
    def __init__(
        self,
        primary_api_key: str,
        primary_base_url: str,
        primary_model_name: str,
        fallback_api_key: Optional[str] = None,
        fallback_base_url: Optional[str] = None,
        fallback_model_name: Optional[str] = None,
        primary_client_args: Optional[Dict[str, Any]] = None,
        fallback_client_args: Optional[Dict[str, Any]] = None,
        content_filter_error_code: str = "1301", # Content filtering error code specific to Zhipu
        content_filter_error_field: str = "contentFilter", # Content filtering error field specific to Zhipu
        max_retries_primary: int = 1, # Primary API retry count
        max_retries_fallback: int = 1, # Fallback API retry count
        retry_delay_seconds: float = 1.0 # Retry delay time
    ):
        """
        Initialize AsyncFallbackOpenAIClient.

        Args:
            primary_api_key: Primary API key.
            primary_base_url: Primary API base URL.
            primary_model_name: Model name used by primary API.
            fallback_api_key: Fallback API key (optional).
            fallback_base_url: Fallback API base URL (optional).
            fallback_model_name: Model name used by fallback API (optional).
            primary_client_args: Additional arguments passed to primary AsyncOpenAI client.
            fallback_client_args: Additional arguments passed to fallback AsyncOpenAI client.
            content_filter_error_code: Specific error code for content filtering errors that trigger fallback.
            content_filter_error_field: Field name present in content filtering errors that trigger fallback.
            max_retries_primary: Maximum retry count when primary API fails.
            max_retries_fallback: Maximum retry count when fallback API fails.
            retry_delay_seconds: Delay time before retry (seconds).
        """
        if not primary_api_key or not primary_base_url:
            raise ValueError("Primary API key and base URL cannot be empty.")

        _primary_args = primary_client_args or {}
        self.primary_client = AsyncOpenAI(api_key=primary_api_key, base_url=primary_base_url, **_primary_args)
        self.primary_model_name = primary_model_name

        self.fallback_client: Optional[AsyncOpenAI] = None
        self.fallback_model_name: Optional[str] = None
        if fallback_api_key and fallback_base_url and fallback_model_name:
            _fallback_args = fallback_client_args or {}
            self.fallback_client = AsyncOpenAI(api_key=fallback_api_key, base_url=fallback_base_url, **_fallback_args)
            self.fallback_model_name = fallback_model_name
        else:
            print("⚠️ Warning: Fallback API client not fully configured. If primary API fails, fallback will not be available.")

        self.content_filter_error_code = content_filter_error_code
        self.content_filter_error_field = content_filter_error_field
        self.max_retries_primary = max_retries_primary
        self.max_retries_fallback = max_retries_fallback
        self.retry_delay_seconds = retry_delay_seconds
        self._closed = False

    async def _attempt_api_call(
        self,
        client: AsyncOpenAI,
        model_name: str,
        messages: list[Mapping[str, Any]],
        max_retries: int,
        api_name: str,
        **kwargs: Any
    ) -> ChatCompletion:
        """
        Attempt to call the specified OpenAI API client with retries.
        """
        last_exception = None
        for attempt in range(max_retries + 1):
            try:
                # print(f"Attempting to use {api_name} API ({client.base_url}) model: {kwargs.get('model', model_name)}, attempt {attempt + 1}")
                completion = await client.chat.completions.create(
                    model=kwargs.pop('model', model_name),
                    messages=messages,
                    **kwargs
                )
                return completion
            except (APIConnectionError, APITimeoutError) as e: # Network errors that can usually be retried
                last_exception = e
                print(f"⚠️ Retryable error occurred when calling {api_name} API ({type(e).__name__}): {e}. Attempt {attempt + 1}/{max_retries + 1}")
                if attempt < max_retries:
                    await asyncio.sleep(self.retry_delay_seconds * (attempt + 1)) # Increase delay
                else:
                    print(f"❌ {api_name} API still failed after reaching maximum retry count.")
            except APIStatusError as e: # Specific status code errors returned by API
                is_content_filter_error = False
                if e.status_code == 400:
                    try:
                        error_json = e.response.json()
                        error_details = error_json.get("error", {})
                        if (error_details.get("code") == self.content_filter_error_code and
                            self.content_filter_error_field in error_json):
                            is_content_filter_error = True
                    except Exception:
                        pass # Failed to parse error response, don't consider it a content filtering error
                
                if is_content_filter_error and api_name == "Primary": # If it's a content filtering error from primary API, raise directly for fallback
                    raise e 
                
                last_exception = e
                print(f"⚠️ APIStatusError occurred when calling {api_name} API ({e.status_code}): {e}. Attempt {attempt + 1}/{max_retries + 1}")
                if attempt < max_retries:
                    await asyncio.sleep(self.retry_delay_seconds * (attempt + 1))
                else:
                    print(f"❌ {api_name} API still failed after reaching maximum retry count (APIStatusError).")
            except APIError as e: # Other OpenAI errors that cannot be easily retried
                last_exception = e
                print(f"❌ Non-retryable error occurred when calling {api_name} API ({type(e).__name__}): {e}")
                break # Don't retry this type of error
        
        if last_exception:
            raise last_exception
        raise RuntimeError(f"{api_name} API call unexpectedly failed.") # Theoretically should not reach here

    async def chat_completions_create(
        self,
        messages: list[Mapping[str, Any]],
        **kwargs: Any  # Used to pass other OpenAI parameters such as max_tokens, temperature, etc.
    ) -> ChatCompletion:
        """
        Create chat completion using primary API, fallback to fallback API if specific content filtering error occurs or primary API call fails.
        Supports retries for retryable errors on both primary and fallback APIs.

        Args:
            messages: Message list for OpenAI API.
            **kwargs: Additional parameters passed to OpenAI API call.

        Returns:
            ChatCompletion object.

        Raises:
            APIError: If both primary API and fallback API (if attempted) return API errors.
            RuntimeError: If client is closed.
        """
        if self._closed:
            raise RuntimeError("Client is closed.")
            
        try:
            completion = await self._attempt_api_call(
                client=self.primary_client,
                model_name=self.primary_model_name,
                messages=messages,
                max_retries=self.max_retries_primary,
                api_name="Primary",
                **kwargs.copy()
            )
            return completion
        except APIStatusError as e_primary:
            is_content_filter_error = False
            if e_primary.status_code == 400:
                try:
                    error_json = e_primary.response.json()
                    error_details = error_json.get("error", {})
                    if (error_details.get("code") == self.content_filter_error_code and
                        self.content_filter_error_field in error_json):
                        is_content_filter_error = True
                except Exception:
                    pass 
            
            if is_content_filter_error and self.fallback_client and self.fallback_model_name:
                print(f"ℹ️ Primary API content filtering error ({e_primary.status_code}). Attempting to switch to fallback API ({self.fallback_client.base_url})...")
                try:
                    fallback_completion = await self._attempt_api_call(
                        client=self.fallback_client,
                        model_name=self.fallback_model_name,
                        messages=messages,
                        max_retries=self.max_retries_fallback,
                        api_name="Fallback",
                        **kwargs.copy()
                    )
                    print(f"✅ Fallback API call successful.")
                    return fallback_completion
                except APIError as e_fallback:
                    print(f"❌ Fallback API call ultimately failed: {type(e_fallback).__name__} - {e_fallback}")
                    raise e_fallback 
            else:
                if not (self.fallback_client and self.fallback_model_name and is_content_filter_error):
                     # If it's not a content filtering error, or no fallback API is available, log the original primary API error
                    print(f"ℹ️ Primary API error ({type(e_primary).__name__}: {e_primary}), and fallback conditions not met or fallback API not configured.")
                raise e_primary
        except APIError as e_primary_other: 
            print(f"❌ Primary API call ultimately failed (non-content filtering, error type: {type(e_primary_other).__name__}): {e_primary_other}")
            if self.fallback_client and self.fallback_model_name:
                print(f"ℹ️ Primary API failed, attempting to switch to fallback API ({self.fallback_client.base_url})...")
                try:
                    fallback_completion = await self._attempt_api_call(
                        client=self.fallback_client,
                        model_name=self.fallback_model_name,
                        messages=messages,
                        max_retries=self.max_retries_fallback,
                        api_name="Fallback",
                        **kwargs.copy()
                    )
                    print(f"✅ Fallback API call successful.")
                    return fallback_completion
                except APIError as e_fallback_after_primary_fail:
                    print(f"❌ Fallback API also failed after primary API failure: {type(e_fallback_after_primary_fail).__name__} - {e_fallback_after_primary_fail}")
                    raise e_fallback_after_primary_fail 
            else: 
                raise e_primary_other

    async def close(self):
        """Asynchronously close primary and fallback clients (if they exist)."""
        if not self._closed:
            await self.primary_client.close()
            if self.fallback_client:
                await self.fallback_client.close()
            self._closed = True
            # print("AsyncFallbackOpenAIClient has been closed.")

    async def __aenter__(self):
        if self._closed:
            raise RuntimeError("AsyncFallbackOpenAIClient cannot be re-entered after closing. Please create a new instance.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
