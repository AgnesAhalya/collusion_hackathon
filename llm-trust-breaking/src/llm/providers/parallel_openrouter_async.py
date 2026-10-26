"""Async parallel OpenRouter client using asyncio and aiohttp."""
from __future__ import annotations
from typing import List, Dict, Any
import asyncio
import aiohttp
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from src.llm.capabilities import is_reasoning_model, supports_structured_output


class AsyncOpenRouterParallelClient:
    """
    Execute multiple OpenRouter requests in parallel using asyncio.

    Much more efficient than threading - can handle 100+ concurrent requests
    with minimal memory overhead.
    """

    # Reasoning models spend much longer before the first token.
    REASONING_TIMEOUT = 300

    def __init__(self, api_key: str, max_concurrent: int = 50, timeout: int = 120, max_retries: int = 3,
                 base_url: str = "https://openrouter.ai/api/v1/chat/completions"):
        """
        Initialize async parallel OpenRouter client.

        Args:
            api_key: OpenRouter API key
            max_concurrent: Maximum number of concurrent requests (default: 50)
            timeout: Request timeout in seconds (default: 120)
            max_retries: Maximum number of retry attempts (default: 3)
        """
        self.api_key = api_key
        self.base_url = base_url
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.max_retries = max_retries

    @staticmethod
    def _capture_raw_call(*, request: Dict[str, Any], attempt: int,
                          request_payload: Dict[str, Any], response_status: int | None = None,
                          response_payload: Any = None, response_text: str | None = None,
                          error: str | None = None) -> None:
        """Append one credential-free HTTP attempt record when Track 2.2 enables capture."""
        raw_dir = os.getenv("TRACK22_RAW_CALLS_DIR")
        if not raw_dir:
            return
        directory = Path(raw_dir)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            os.chmod(directory, 0o700)
        except OSError:
            pass
        record = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "run_id": os.getenv("TRACK22_RUN_ID"),
            "custom_id": request.get("custom_id"),
            "attempt": attempt,
            "model_requested": request.get("model"),
            "request": request_payload,
            "http_status": response_status,
            "response": response_payload,
            "response_raw_text": response_text if response_payload is None else None,
            "usage": response_payload.get("usage") if isinstance(response_payload, dict) else None,
            "error": error,
        }
        path = directory / "calls.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(fd, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        finally:
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

    def execute_parallel(self, requests_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple requests in parallel using asyncio.

        This is a synchronous wrapper around the async implementation.

        Args:
            requests_list: List of request dictionaries

        Returns:
            Dictionary mapping custom_id to response
        """
        # Run async code in event loop
        return asyncio.run(self._execute_parallel_async(requests_list))

    async def _execute_parallel_async(self, requests_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Async implementation of parallel execution.

        Args:
            requests_list: List of request dictionaries

        Returns:
            Dictionary mapping custom_id to response
        """
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)

        # Configure connection pooling
        # TCPConnector manages the connection pool and reuses connections
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent * 2,  # Total connection pool size
            limit_per_host=self.max_concurrent,  # Connections to OpenRouter
            ttl_dns_cache=300,  # Cache DNS for 5 minutes
            enable_cleanup_closed=True  # Clean up closed connections
        )

        # Create aiohttp session with connection pooling
        # Session timeout is the ceiling; each request overrides it for its own model.
        timeout_obj = aiohttp.ClientTimeout(total=max(self.timeout, self.REASONING_TIMEOUT))
        async with aiohttp.ClientSession(timeout=timeout_obj, connector=connector) as session:
            # Create tasks for all requests
            tasks = [
                self._execute_single_async(session, semaphore, request)
                for request in requests_list
            ]

            # Execute all tasks concurrently
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert list to dict
            results = {}
            for result in results_list:
                if isinstance(result, Exception):
                    print(f"Task failed with exception: {result}")
                    continue
                if result:
                    custom_id, response = result
                    results[custom_id] = response

            return results

    async def _execute_single_async(
        self,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        request: Dict[str, Any]
    ) -> tuple[str, Dict[str, Any]]:
        """
        Execute a single request asynchronously with retry logic.

        Args:
            session: aiohttp session
            semaphore: Semaphore to limit concurrency
            request: Request dictionary

        Returns:
            Tuple of (custom_id, response)
        """
        custom_id = request['custom_id']

        # Retry with exponential backoff
        for attempt in range(self.max_retries):
            data = {}
            async with semaphore:  # Limit concurrent requests
                try:
                    # Build request data
                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    }

                    data = {
                        "model": request['model'],
                        "messages": request['messages']
                    }
                    if "openrouter.ai" in self.base_url:
                        # OpenRouter returns provider-reported token and cost details in each response.
                        data["usage"] = {"include": True}

                    # Add optional parameters
                    if 'temperature' in request:
                        data['temperature'] = request['temperature']
                    if 'seed' in request:
                        data['seed'] = request['seed']

                    if 'max_tokens' in request:
                        data['max_tokens'] = request['max_tokens']
                    elif 'max_completion_tokens' in request:
                        data['max_tokens'] = request['max_completion_tokens']
                    else:
                        data['max_tokens'] = 100

                    # Add response format if supported
                    model = request['model']
                    if 'response_format' in request and supports_structured_output(model):
                        data['response_format'] = request['response_format']

                    # Make async HTTP request
                    # Per-request timeout: a reasoning model in a heterogeneous run must not
                    # inherit the default model's budget.
                    req_timeout = aiohttp.ClientTimeout(
                        total=self.REASONING_TIMEOUT if is_reasoning_model(model) else self.timeout
                    )
                    async with session.post(self.base_url, headers=headers, json=data,
                                            timeout=req_timeout) as response:
                        response_text = await response.text()
                        try:
                            response_data = json.loads(response_text)
                        except (json.JSONDecodeError, ValueError):
                            response_data = None
                        self._capture_raw_call(
                            request=request, attempt=attempt + 1, request_payload=data,
                            response_status=response.status, response_payload=response_data,
                            response_text=response_text,
                        )
                        response.raise_for_status()
                        if response_data is None:
                            raise ValueError("Provider returned a non-JSON response")

                        content = response_data["choices"][0]["message"]["content"]

                        # Try to parse JSON content
                        try:
                            parsed = json.loads(content)
                            if isinstance(parsed, dict):
                                return custom_id, parsed
                            else:
                                return custom_id, {"content": content}
                        except (json.JSONDecodeError, ValueError):
                            # Not JSON, return as plain content
                            return custom_id, {
                                "status": "success",
                                "content": content
                            }

                # ClientResponseError is a subclass of ClientError, so it must be caught first:
                # otherwise every HTTP error -- 401 included -- lands in the retry branch below.
                except aiohttp.ClientResponseError as e:
                    # HTTP errors (rate limiting, server errors)
                    if e.status in [429, 500, 502, 503, 504] and attempt < self.max_retries - 1:
                        wait_time = (2 ** attempt) + (time.time() % 1)
                        # Silently retry rate limits and server errors
                        await asyncio.sleep(wait_time)
                    else:
                        if attempt == self.max_retries - 1:
                            print(f"HTTP error in request {custom_id} after {self.max_retries} attempts: {e}")
                        return custom_id, {
                            "status": "error",
                            "error": str(e)
                        }

                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    self._capture_raw_call(request=request, attempt=attempt + 1,
                                           request_payload=data, error=str(e))
                    # Retryable errors
                    if attempt < self.max_retries - 1:
                        wait_time = (2 ** attempt) + (time.time() % 1)
                        print(f"Retryable error in {custom_id} (attempt {attempt + 1}/{self.max_retries}): {e}")
                        print(f"Retrying in {wait_time:.2f} seconds...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Error in request {custom_id} after {self.max_retries} attempts: {e}")
                        return custom_id, {
                            "status": "error",
                            "error": f"Max retries exceeded: {str(e)}"
                        }

                except Exception as e:
                    if not isinstance(e, ValueError):
                        self._capture_raw_call(request=request, attempt=attempt + 1,
                                               request_payload=data, error=str(e))
                    # Non-retryable errors
                    print(f"Error in request {custom_id}: {e}")
                    return custom_id, {
                        "status": "error",
                        "error": str(e)
                    }

        # Should never reach here
        return custom_id, {
            "status": "error",
            "error": "Max retries exceeded"
        }


# Backwards compatibility alias
OpenRouterParallelClient = AsyncOpenRouterParallelClient
