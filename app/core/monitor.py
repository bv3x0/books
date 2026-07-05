import time
import json
import os
import subprocess
import tempfile
import traceback
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.parse
import urllib.request
import urllib.error
from app.logger import log
from app.config import (
    BASE_DIR,
    INGEST_CONCURRENCY,
    anthropic_allows_sampling_parameters,
)
from app.core.schema import SUMMARY_SCHEMA


class JSONValidationError(Exception):
    """Raised when JSON response validation fails."""
    pass


class Monitor:
    def __init__(
        self,
        client,
        book_name: str = None,
        provider: str = "anthropic",
        google_api_key: str = None,
        cache_suffix: str = "",
        model_id: str | None = None,
        use_anthropic_batch: bool = True,
    ):
        self.client = client
        self.book_name = book_name
        self.provider = (provider or "anthropic").lower()
        self.google_api_key = google_api_key
        self.cache_suffix = cache_suffix.strip()
        self.model_id = model_id
        self.use_anthropic_batch = bool(use_anthropic_batch)
        self._structured_outputs_checked = False
        self._structured_outputs_supported = False
        # Save cache to logs directory with book name for persistence
        if book_name:
            logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
            os.makedirs(logs_dir, exist_ok=True)
            self.results_cache = os.path.join(logs_dir, f"{book_name}{self.cache_suffix}_cache.json")
        else:
            self.results_cache = "cached_results.json"
        self.max_retries = 4  # Retry truncated JSON responses (allows up to 64k output)
        if self.provider == "anthropic" and self.model_id:
            self._detect_structured_output_support(self.model_id)

    @staticmethod
    def _capability_value(caps, key: str):
        if isinstance(caps, dict):
            return caps.get(key)
        return getattr(caps, key, None)

    def _detect_structured_output_support(self, model_id: str) -> bool:
        """Check Anthropic model capabilities once, falling back gracefully."""
        if self._structured_outputs_checked:
            return self._structured_outputs_supported

        self._structured_outputs_checked = True
        self._structured_outputs_supported = False
        if self.provider != "anthropic" or not self.client or not model_id:
            return False

        try:
            model = self.client.models.retrieve(model_id)
            caps = getattr(model, "capabilities", None)
            structured = self._capability_value(caps, "structured_outputs")
            supported = self._capability_value(structured, "supported")
            self._structured_outputs_supported = bool(supported)
            if self._structured_outputs_supported:
                log.info(f"Monitor: Anthropic structured outputs enabled for {model_id}")
            else:
                log.info(f"Monitor: Anthropic structured outputs unsupported for {model_id}")
        except Exception as exc:
            log.warning(
                "Monitor: Could not check Anthropic structured output capability "
                f"for {model_id}; falling back to text JSON parsing ({exc})"
            )
        return self._structured_outputs_supported

    def _use_anthropic_structured_outputs(self, model_id: str | None) -> bool:
        if self.provider != "anthropic":
            return False
        return self._detect_structured_output_support(model_id or self.model_id or "")

    @staticmethod
    def _is_success_result(result: dict) -> bool:
        return result.get("status") == "SUCCESS"

    @staticmethod
    def _summarize_results(total: int, results: list[dict]) -> tuple[int, int, str]:
        successful = sum(1 for result in results if result.get("status") == "SUCCESS")
        failed = total - successful
        state = "SUCCEEDED" if failed == 0 else "PARTIAL" if successful > 0 else "FAILED"
        return successful, failed, state

    def _api_label(self) -> str:
        if self.provider == "gemini":
            return "Gemini API"
        if self.provider == "openai":
            return "OpenAI Responses API"
        if self.provider == "codex":
            return "Codex CLI"
        return "Claude API"

    def _flatten_text_request(self, req_data: dict) -> str:
        """Render system and message text into one prompt for text-only APIs."""
        parts = []
        has_non_text_content = False

        for block in (req_data.get("system") or []):
            if isinstance(block, dict) and block.get("text"):
                parts.append(block["text"])

        for message in req_data.get("messages", []):
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
                continue
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and item.get("text"):
                    parts.append(item["text"])
                elif item.get("type") != "text":
                    has_non_text_content = True

        if has_non_text_content:
            return ""
        return "\n\n".join(part for part in parts if part).strip()

    def _extract_gemini_text(self, payload: dict) -> str:
        """Extract response text from Gemini generateContent JSON."""
        candidates = payload.get("candidates") or []
        if not candidates:
            feedback = payload.get("promptFeedback", {})
            reason = feedback.get("blockReason") or "No candidates returned"
            raise RuntimeError(f"Gemini returned no candidates: {reason}")

        content = candidates[0].get("content", {})
        parts = content.get("parts") or []
        text_parts = [p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")]
        text = "".join(text_parts).strip()

        if not text:
            finish_reason = candidates[0].get("finishReason", "UNKNOWN")
            raise RuntimeError(f"Gemini returned empty text response (finish_reason={finish_reason})")

        return text

    @staticmethod
    def _codex_output_schema() -> dict:
        """Return a strict schema for Codex's final JSON summary object."""
        return copy.deepcopy(SUMMARY_SCHEMA)

    @staticmethod
    def _tail_text(text: str, limit: int = 2000) -> str:
        text = (text or "").strip()
        if len(text) <= limit:
            return text
        return text[-limit:]

    def _call_codex(self, req_data: dict, chapter_num: int, total: int, retry_msg: str) -> tuple[str, dict]:
        """Call local Codex exec as a structured-output summarization backend."""
        prompt_content = self._flatten_text_request(req_data)
        if not prompt_content:
            raise ValueError(
                "Codex mode only supports text inputs. "
                "If this is a scanned PDF, rerun with --ocr to extract text."
            )

        api_label = self._api_label()
        log.info(f"Calling {api_label} for chunk {chapter_num}{retry_msg}...")
        print(f"⏳ Processing chunk {chapter_num}/{total}{retry_msg} with {api_label}...", flush=True)

        max_tokens = req_data.get("max_tokens")
        model = req_data["model"]
        codex_prompt = (
            "You are running as a non-interactive summarization backend.\n"
            "Do not run shell commands, inspect local files, or use repository context.\n"
            "Use only the source material and instructions below.\n"
            "Return exactly one JSON object matching the requested schema.\n"
            f"The downstream output budget is about {max_tokens} tokens; treat it as a ceiling, not a target.\n\n"
            f"{prompt_content}"
        )

        timeout_seconds = int(os.getenv("SUMMARIZER_CODEX_TIMEOUT_SECONDS", "7200"))
        with tempfile.TemporaryDirectory(prefix="summarizer-codex-") as temp_dir:
            schema_path = os.path.join(temp_dir, "summary-schema.json")
            output_path = os.path.join(temp_dir, "codex-output.json")
            with open(schema_path, "w", encoding="utf-8") as f:
                json.dump(self._codex_output_schema(), f)

            cmd = [
                "codex",
                "exec",
                "--model",
                model,
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-rules",
                "--cd",
                BASE_DIR,
                "--output-schema",
                schema_path,
                "--output-last-message",
                output_path,
                "--color",
                "never",
                "-",
            ]
            env = os.environ.copy()
            env.setdefault("NO_COLOR", "1")
            env.setdefault("CLICOLOR", "0")

            try:
                result = subprocess.run(
                    cmd,
                    input=codex_prompt,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    cwd=BASE_DIR,
                    env=env,
                )
            except subprocess.TimeoutExpired as e:
                raise RuntimeError(
                    f"Codex CLI timed out after {timeout_seconds}s for chunk {chapter_num}"
                ) from e

            if result.returncode != 0:
                detail = self._tail_text(result.stderr) or self._tail_text(result.stdout)
                raise RuntimeError(
                    f"Codex CLI failed for chunk {chapter_num} with exit code {result.returncode}: {detail}"
                )

            if not os.path.exists(output_path):
                detail = self._tail_text(result.stderr) or self._tail_text(result.stdout)
                raise RuntimeError(
                    f"Codex CLI did not write an output file for chunk {chapter_num}: {detail}"
                )

            with open(output_path, "r", encoding="utf-8") as f:
                response_text = f.read().strip()

            if not response_text:
                detail = self._tail_text(result.stderr) or self._tail_text(result.stdout)
                raise RuntimeError(
                    f"Codex CLI returned empty output for chunk {chapter_num}: {detail}"
                )

        return response_text, {}

    @staticmethod
    def _object_get(obj, key: str, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _build_anthropic_request_kwargs(
        self,
        req_data: dict,
        use_unified: bool,
    ) -> tuple[dict, bool]:
        request_kwargs = {
            "model": req_data["model"],
            "max_tokens": req_data["max_tokens"],
            "messages": req_data["messages"],
        }
        if req_data.get("system"):
            request_kwargs["system"] = req_data["system"]
        if anthropic_allows_sampling_parameters(req_data.get("model")):
            request_kwargs["temperature"] = 0.2

        use_structured_outputs = bool(use_unified) and self._use_anthropic_structured_outputs(
            req_data.get("model")
        )
        if use_structured_outputs:
            request_kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": copy.deepcopy(SUMMARY_SCHEMA)}
            }
        return request_kwargs, use_structured_outputs

    def _extract_anthropic_response_text(self, response) -> str:
        content = self._object_get(response, "content", []) or []
        text_parts = []
        for block in content:
            text = self._object_get(block, "text")
            if text:
                text_parts.append(text)
                continue
            block_type = self._object_get(block, "type")
            if block_type in {"json", "tool_result"}:
                payload = self._object_get(block, "input", None)
                if payload is not None:
                    text_parts.append(json.dumps(payload))
        return "".join(text_parts).strip()

    def _anthropic_usage_from_response(
        self,
        response,
        structured_outputs: bool = False,
        billing_multiplier: float | None = None,
    ) -> dict:
        usage_obj = self._object_get(response, "usage")
        usage = {}
        if usage_obj:
            usage = {
                "input_tokens": self._object_get(usage_obj, "input_tokens"),
                "output_tokens": self._object_get(usage_obj, "output_tokens"),
                "cache_creation_input_tokens": self._object_get(
                    usage_obj, "cache_creation_input_tokens"
                ),
                "cached_input_tokens": self._object_get(
                    usage_obj, "cache_read_input_tokens"
                ),
            }
        if structured_outputs:
            usage["structured_outputs"] = True
        if billing_multiplier is not None:
            usage["billing_multiplier"] = billing_multiplier
        return usage

    def _call_model(self, req_data: dict, chapter_num: int, total: int, retry_msg: str) -> tuple[str, dict]:
        """
        Call the configured model provider and return (response_text, usage_dict).
        """
        api_label = self._api_label()

        if self.provider == "codex":
            return self._call_codex(req_data, chapter_num, total, retry_msg)

        if self.provider == "gemini":
            prompt_content = self._flatten_text_request(req_data)
            if not prompt_content:
                raise ValueError(
                    "Gemini mode only supports text inputs. "
                    "If this is a scanned PDF, rerun with --ocr to extract text."
                )

            if not self.google_api_key:
                raise RuntimeError("Missing GOOGLE_API_KEY for Gemini mode")

            model = req_data["model"]
            endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(self.google_api_key)}"
            )
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt_content}],
                    }
                ],
                "generationConfig": {
                    "maxOutputTokens": req_data["max_tokens"],
                    "temperature": 0.2,
                    "responseMimeType": "application/json",
                },
            }
            body = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                endpoint,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            log.info(f"Calling {api_label} for chunk {chapter_num}{retry_msg}...")
            print(f"⏳ Processing chunk {chapter_num}/{total}{retry_msg} with {api_label}...", flush=True)

            try:
                with urllib.request.urlopen(request, timeout=3600) as response:
                    response_payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                err_text = e.read().decode("utf-8", errors="replace")
                try:
                    err_json = json.loads(err_text)
                    message = err_json.get("error", {}).get("message", err_text)
                except Exception:
                    message = err_text
                raise RuntimeError(f"Gemini API HTTP {e.code}: {message}") from e
            except urllib.error.URLError as e:
                raise RuntimeError(f"Gemini API network error: {e.reason}") from e

            response_text = self._extract_gemini_text(response_payload)
            usage = response_payload.get("usageMetadata", {})
            return response_text, usage

        if self.provider == "openai":
            prompt_content = self._flatten_text_request(req_data)
            if not prompt_content:
                raise ValueError(
                    "GPT mode only supports text inputs. "
                    "If this is a scanned PDF, rerun with --ocr to extract text."
                )

            log.info(f"Calling {api_label} for chunk {chapter_num}{retry_msg}...")
            print(f"⏳ Processing chunk {chapter_num}/{total}{retry_msg} with {api_label}...", flush=True)
            response = self.client.responses.create(
                model=req_data["model"],
                input=prompt_content,
                max_output_tokens=req_data["max_tokens"],
                temperature=0.2,
            )

            response_text = (getattr(response, "output_text", "") or "").strip()
            if not response_text:
                raise RuntimeError("OpenAI response did not include output_text")

            usage = {}
            if getattr(response, "usage", None):
                usage = {
                    "input_tokens": getattr(response.usage, "input_tokens", None),
                    "output_tokens": getattr(response.usage, "output_tokens", None),
                }
                details = getattr(response.usage, "input_tokens_details", None)
                if details is not None:
                    usage["cached_input_tokens"] = getattr(details, "cached_tokens", None)
            return response_text, usage

        # Anthropic default path
        log.info(f"Calling {api_label} for chunk {chapter_num}{retry_msg}...")
        print(f"⏳ Processing chunk {chapter_num}/{total}{retry_msg} with {api_label}...", flush=True)
        request_kwargs, use_structured_outputs = self._build_anthropic_request_kwargs(
            req_data,
            use_unified=bool(req_data.get("_use_unified")),
        )

        try:
            response = self.client.messages.create(**request_kwargs)
        except Exception as exc:
            if use_structured_outputs:
                log.warning(
                    "Monitor: Anthropic structured output request failed; "
                    f"falling back to text JSON parsing ({exc})"
                )
                self._structured_outputs_supported = False
                request_kwargs.pop("output_config", None)
                response = self.client.messages.create(**request_kwargs)
                use_structured_outputs = False
            else:
                raise

        response_text = self._extract_anthropic_response_text(response)
        usage = self._anthropic_usage_from_response(
            response,
            structured_outputs=use_structured_outputs,
        )
        return response_text, usage

    def _result_from_response(
        self,
        index: int,
        request: dict,
        response_text: str,
        usage: dict,
        elapsed: float,
    ) -> dict:
        """Parse a provider response into the cached result format."""
        chapter_num = index + 1
        file_metadata = request.get("file_metadata", {})
        use_unified = file_metadata.get("use_unified", False)
        response_length = len(response_text)
        normalized_usage = self._normalize_usage(usage)
        input_tokens = normalized_usage.get("input_tokens")
        output_tokens = normalized_usage.get("output_tokens")
        if input_tokens is not None and output_tokens is not None:
            log.info(
                f"Monitor: Tokens - input: {input_tokens:,}, output: {output_tokens:,}"
            )

        if use_unified:
            structured_outputs = bool(normalized_usage.get("structured_outputs"))
            parse_result = self._parse_unified_response(
                response_text,
                file_metadata,
                structured_outputs=structured_outputs,
            )

            base_result = {
                "index": index,
                "response": response_text,
                "elapsed_seconds": round(elapsed, 2),
                "response_length": response_length,
                "use_unified": True,
                "file_metadata": file_metadata,
                "model": request.get("request", {}).get("model"),
                "usage": normalized_usage,
                "structured_outputs": structured_outputs,
            }

            if parse_result["status"] == "SUCCESS":
                return {
                    **base_result,
                    "status": "SUCCESS",
                    "data": parse_result["data"],
                }

            return {
                **base_result,
                "status": "TRUNCATED" if parse_result["status"] == "TRUNCATED" else "PARSE_FAILED",
                "parse_status": parse_result["status"],
                "error": parse_result["error"],
            }

        self.validate_response(response_text, file_metadata, chapter_num)
        return {
            "index": index,
            "status": "SUCCESS",
            "response": response_text,
            "elapsed_seconds": round(elapsed, 2),
            "response_length": response_length,
            "use_unified": False,
            "model": request.get("request", {}).get("model"),
            "usage": normalized_usage,
        }

    def _process_request(self, index: int, request: dict, total: int) -> dict:
        """Process a single request with retries and unified-response parsing."""
        chapter_num = index + 1
        file_metadata = request.get("file_metadata", {})
        use_unified = file_metadata.get("use_unified", False)

        start_time = time.time()
        retry_count = 0
        current_max_tokens = request["request"]["max_tokens"]

        while retry_count <= self.max_retries:
            try:
                req_data = request["request"].copy()
                req_data["max_tokens"] = current_max_tokens
                req_data["_use_unified"] = use_unified

                retry_msg = f" (retry {retry_count})" if retry_count > 0 else ""
                response_text, usage = self._call_model(
                    req_data=req_data,
                    chapter_num=chapter_num,
                    total=total,
                    retry_msg=retry_msg,
                )

                elapsed = time.time() - start_time
                result = self._result_from_response(
                    index=index,
                    request=request,
                    response_text=response_text,
                    usage=usage,
                    elapsed=elapsed,
                )

                if use_unified:
                    if result["status"] == "TRUNCATED" and retry_count < self.max_retries:
                        retry_count += 1
                        current_max_tokens = min(current_max_tokens + 8192, 65536)
                        log.warning(
                            f"Monitor: JSON truncated, retrying with max_tokens={current_max_tokens}"
                        )
                        print(f"⚠️  Response truncated, retrying with more tokens...", flush=True)
                        time.sleep(2)
                        continue

                    if result["status"] == "SUCCESS":
                        print(f"✅ Chunk {chapter_num} completed (JSON parsed)", flush=True)
                        log.info(
                            f"Monitor: Chunk {chapter_num} completed in {elapsed:.1f}s ({len(response_text):,} chars)"
                        )
                        return result

                    print(
                        f"⚠️  Chunk {chapter_num} JSON parse failed: {result['error']}",
                        flush=True,
                    )
                    log.error(f"Monitor: JSON parse failed: {result['error']}")
                    return result

                print(f"✅ Chunk {chapter_num} API call completed", flush=True)
                log.info(
                    f"Monitor: Chunk {chapter_num} completed in {elapsed:.1f}s ({len(response_text):,} chars)"
                )
                return result

            except Exception as e:
                elapsed = time.time() - start_time
                retry_count += 1
                non_retryable = (
                    isinstance(e, ValueError)
                    or "Codex CLI" in str(e)
                    or "Missing GOOGLE_API_KEY" in str(e)
                    or "Missing OPENAI_API_KEY" in str(e)
                )

                if retry_count <= self.max_retries and not non_retryable:
                    log.warning(f"Monitor: Chunk {chapter_num} failed, retrying... ({e})")
                    time.sleep(2)
                    continue

                log.error(f"Monitor: Chunk {chapter_num} FAILED after {elapsed:.1f}s")
                log.error(f"Error type: {type(e).__name__}")
                log.error(f"Error message: {e}")
                log.debug(f"Full traceback:\n{traceback.format_exc()}")
                return {
                    "index": index,
                    "status": "FAILED",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "elapsed_seconds": round(elapsed, 2),
                    "traceback": traceback.format_exc(),
                    "use_unified": use_unified,
                    "model": request.get("request", {}).get("model"),
                }

    @staticmethod
    def _normalize_usage(usage: dict) -> dict:
        """
        Normalize provider-specific usage fields to:
          {
            "input_tokens": int|None,
            "output_tokens": int|None,
            "cached_input_tokens": int|None,
            "cache_creation_input_tokens": int|None,
          }
        """
        usage = usage or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        cached_input_tokens = usage.get("cached_input_tokens")
        cache_creation_input_tokens = usage.get("cache_creation_input_tokens")

        if input_tokens is None:
            input_tokens = usage.get("promptTokenCount")
        if output_tokens is None:
            output_tokens = usage.get("candidatesTokenCount")
        if cached_input_tokens is None:
            cached_input_tokens = usage.get("cachedContentTokenCount")

        try:
            input_tokens = int(input_tokens) if input_tokens is not None else None
        except Exception:
            input_tokens = None
        try:
            output_tokens = int(output_tokens) if output_tokens is not None else None
        except Exception:
            output_tokens = None
        try:
            cached_input_tokens = (
                int(cached_input_tokens) if cached_input_tokens is not None else None
            )
        except Exception:
            cached_input_tokens = None
        try:
            cache_creation_input_tokens = (
                int(cache_creation_input_tokens)
                if cache_creation_input_tokens is not None
                else None
            )
        except Exception:
            cache_creation_input_tokens = None

        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_input_tokens": cached_input_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "structured_outputs": bool(usage.get("structured_outputs")),
            "billing_multiplier": usage.get("billing_multiplier"),
        }

    @staticmethod
    def _strip_json_fences(text: str) -> str:
        """Remove markdown fences without modifying JSON contents."""
        text = (text or "").strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _extract_json(self, text: str, repair: bool = True) -> str:
        """Extract JSON from response, handling markdown fences and common LLM errors."""
        import re

        text = self._strip_json_fences(text)
        if not repair:
            return text

        # Fix common JSON errors from LLMs:
        # 1. Trailing commas before } or ] (most common issue)
        text = re.sub(r',(\s*[}\]])', r'\1', text)

        # 2. Fix unescaped quotes in "quotes" arrays
        # Pattern like: "quotes": ["text" word "text"] should become ["text word text"]
        def fix_quotes_array(m):
            content = m.group(1).strip()
            if not content:
                return '"quotes": []'
            # If content has patterns like "text" word "text" (unquoted text between quotes)
            # merge into single properly quoted string
            if content.count('"') > 2 and re.search(r'"\s+\w+\s+"', content):
                # Remove all internal quotes and wrap as single string
                escaped = content.replace('"', '')
                return f'"quotes": ["{escaped}"]'
            return m.group(0)

        text = re.sub(r'"quotes":\s*\[(.*?)\](?=\s*})', fix_quotes_array, text, flags=re.DOTALL)

        # 3. Fix unescaped quotes inside string values
        # LLMs sometimes output "word "quoted" word" instead of "word \"quoted\" word"
        text = self._repair_unescaped_quotes(text)

        return text

    def _repair_unescaped_quotes(self, text: str) -> str:
        """
        Escape likely internal quotes inside JSON strings.

        LLM outputs sometimes include prose like:
          "Jung wrote: \"those "sparks of light" ...\""
        which is invalid JSON because the inner quotes are unescaped.

        This scanner tracks whether we're inside a JSON string and only escapes
        quotes that do not look like structural string terminators.
        """
        out = []
        in_string = False
        escaped = False
        fixes = 0
        n = len(text)
        i = 0

        def _next_non_whitespace(start_idx: int) -> int:
            k = start_idx
            while k < n and text[k] in ' \t\r\n':
                k += 1
            return k

        def _comma_looks_structural(comma_idx: int) -> bool:
            # For a real JSON delimiter comma, the following token should start
            # with JSON punctuation, quote, number, or a literal (true/false/null).
            k = _next_non_whitespace(comma_idx + 1)
            if k >= n:
                return True
            return text[k] in '"{[}]0123456789-tnf'

        while i < n:
            ch = text[i]

            if not in_string:
                if ch == '"':
                    in_string = True
                out.append(ch)
                i += 1
                continue

            # In a JSON string
            if escaped:
                out.append(ch)
                escaped = False
                i += 1
                continue

            if ch == '\\':
                out.append(ch)
                escaped = True
                i += 1
                continue

            if ch == '"':
                # Look ahead to determine if this closes the JSON string.
                j = _next_non_whitespace(i + 1)

                next_char = text[j] if j < n else ''
                is_terminator = (
                    j >= n
                    or next_char in ('}', ']', ':')
                    or (next_char == ',' and _comma_looks_structural(j))
                )

                if is_terminator:
                    out.append(ch)
                    in_string = False
                else:
                    out.append('\\"')
                    fixes += 1
                i += 1
                continue

            out.append(ch)
            i += 1

        if fixes:
            log.debug(f"Escaped {fixes} likely internal quote(s)")
        return ''.join(out)

    def _validate_json_structure(self, data: dict) -> None:
        """
        Validate required fields exist in parsed JSON.

        Raises:
            JSONValidationError: If required fields are missing
        """
        required_top = ["book", "chapters"]
        for field in required_top:
            if field not in data:
                raise JSONValidationError(f"Missing required field: {field}")

        if "title" not in data["book"]:
            raise JSONValidationError("Missing book.title")

        if not isinstance(data["chapters"], list):
            raise JSONValidationError("chapters must be an array")

        for i, chapter in enumerate(data["chapters"]):
            if "title" not in chapter:
                raise JSONValidationError(f"Chapter {i} missing title")
            # claims are optional but should be a list if present
            if "claims" in chapter and not isinstance(chapter["claims"], list):
                raise JSONValidationError(f"Chapter {i} claims must be an array")

    def _is_truncated_json(self, text: str) -> bool:
        """Check if JSON appears to be truncated."""
        text = text.strip()
        # JSON should end with } or ]
        if not text.endswith('}') and not text.endswith(']'):
            return True
        # Check for unclosed braces/brackets
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')
        return open_braces != 0 or open_brackets != 0

    def _parse_unified_response(
        self,
        response_text: str,
        file_metadata: dict,
        structured_outputs: bool = False,
    ) -> dict:
        """
        Parse and validate a unified JSON response.

        Args:
            response_text: Raw response text from Claude
            file_metadata: Metadata about the processed file

        Returns:
            dict with 'status', 'data' (if success), or 'error' (if failed)
        """
        try:
            json_text = self._extract_json(response_text, repair=not structured_outputs)

            # Check for truncation before parsing
            if self._is_truncated_json(json_text):
                return {
                    "status": "TRUNCATED",
                    "error": "JSON response appears truncated",
                    "raw_response": response_text
                }

            parsed = json.loads(json_text)
            self._validate_json_structure(parsed)

            return {
                "status": "SUCCESS",
                "data": parsed,
                "structured_outputs": structured_outputs,
            }

        except json.JSONDecodeError as e:
            return {
                "status": "PARSE_ERROR",
                "error": f"JSON parse error: {e}",
                "raw_response": response_text
            }
        except JSONValidationError as e:
            return {
                "status": "VALIDATION_ERROR",
                "error": f"JSON validation error: {e}",
                "raw_response": response_text
            }

    def validate_response(self, response_text, file_metadata, chapter_num):
        """Check if response length is proportional to the file that was processed."""
        # Legacy markdown-path guard. Unified JSON runs use the local fidelity
        # verifier for quote, entity, coverage, and undersummarization checks.
        if not file_metadata or 'size_bytes' not in file_metadata:
            return  # Can't validate without file size info
        
        response_len = len(response_text) if response_text else 0
        file_size = file_metadata['size_bytes']
        
        # Check if response indicates minimal content
        minimal_content_phrases = [
            "contains only",
            "only a title page",
            "only minimal content",
            "only front matter",
            "only table of contents"
        ]
        
        response_lower = response_text.lower() if response_text else ""
        is_minimal_content_response = any(phrase in response_lower for phrase in minimal_content_phrases)
        
        # If PDF is small (<50KB) and response is large (>10KB), warn about potential hallucination
        if file_size < 50000 and response_len > 10000 and not is_minimal_content_response:
            log.warning(
                f"⚠️  HALLUCINATION ALERT for chapter {chapter_num}: "
                f"Response is {response_len:,} chars for a {file_size:,} byte PDF. "
                f"This may be fabricated content!"
            )
            log.warning(f"   Review this chapter carefully - AI may have invented content.")
        elif is_minimal_content_response:
            log.info(f"✓ Chapter {chapter_num}: AI correctly identified minimal content")

    @staticmethod
    def _batch_custom_id(index: int) -> str:
        return f"chunk-{index + 1}"

    def _can_use_anthropic_batch(self) -> bool:
        if self.provider != "anthropic" or not self.use_anthropic_batch or not self.client:
            return False
        messages = self._object_get(self.client, "messages")
        batches = self._object_get(messages, "batches")
        return batches is not None

    @staticmethod
    def _format_request_counts(counts) -> str:
        if not counts:
            return ""
        if isinstance(counts, dict):
            items = counts.items()
        else:
            names = ("processing", "succeeded", "errored", "canceled", "expired")
            items = ((name, getattr(counts, name, None)) for name in names)
        parts = [f"{name}={value}" for name, value in items if value is not None]
        return ", ".join(parts)

    def _build_anthropic_batch_requests(
        self,
        indexed_requests: list[tuple[int, dict]],
        current_max_tokens: dict[int, int],
    ) -> tuple[list[dict], dict[str, bool]]:
        batch_requests = []
        structured_by_custom_id = {}
        for index, request in indexed_requests:
            req_data = request["request"].copy()
            req_data["max_tokens"] = current_max_tokens[index]
            use_unified = bool(request.get("file_metadata", {}).get("use_unified"))
            request_kwargs, structured_outputs = self._build_anthropic_request_kwargs(
                req_data,
                use_unified=use_unified,
            )
            custom_id = self._batch_custom_id(index)
            batch_requests.append({"custom_id": custom_id, "params": request_kwargs})
            structured_by_custom_id[custom_id] = structured_outputs
        return batch_requests, structured_by_custom_id

    def _create_anthropic_batch(
        self,
        batch_requests: list[dict],
        structured_by_custom_id: dict[str, bool],
    ):
        batches = self.client.messages.batches
        try:
            return batches.create(requests=batch_requests), structured_by_custom_id
        except Exception as exc:
            if not any(structured_by_custom_id.values()):
                raise
            log.warning(
                "Monitor: Anthropic batch structured-output submission failed; "
                f"falling back to text JSON parsing ({exc})"
            )
            self._structured_outputs_supported = False
            for batch_request in batch_requests:
                batch_request.get("params", {}).pop("output_config", None)
                structured_by_custom_id[batch_request["custom_id"]] = False
            return batches.create(requests=batch_requests), structured_by_custom_id

    def _poll_anthropic_batch(self, batch_id: str):
        poll_seconds = max(1, int(os.getenv("ANTHROPIC_BATCH_POLL_SECONDS", "30")))
        batches = self.client.messages.batches
        while True:
            batch = batches.retrieve(batch_id)
            status = self._object_get(batch, "processing_status", "unknown")
            counts = self._format_request_counts(self._object_get(batch, "request_counts"))
            suffix = f" ({counts})" if counts else ""
            print(f"Anthropic batch {batch_id}: {status}{suffix}", flush=True)
            log.info(f"Monitor: Anthropic batch {batch_id} status={status}{suffix}")
            if status == "ended":
                return batch
            time.sleep(poll_seconds)

    def _batch_error_message(self, batch_result) -> str:
        error = self._object_get(batch_result, "error")
        if not error:
            return "Batch request did not succeed"
        message = self._object_get(error, "message")
        error_type = self._object_get(error, "type")
        if message and error_type:
            return f"{error_type}: {message}"
        return message or str(error)

    def _result_from_batch_item(
        self,
        index: int,
        request: dict,
        item,
        structured_outputs: bool,
        elapsed: float,
    ) -> dict:
        batch_result = self._object_get(item, "result")
        result_type = self._object_get(batch_result, "type")
        if result_type == "succeeded":
            message = self._object_get(batch_result, "message")
            response_text = self._extract_anthropic_response_text(message)
            usage = self._anthropic_usage_from_response(
                message,
                structured_outputs=structured_outputs,
                billing_multiplier=0.5,
            )
            return self._result_from_response(
                index=index,
                request=request,
                response_text=response_text,
                usage=usage,
                elapsed=elapsed,
            )

        return {
            "index": index,
            "status": "FAILED",
            "error": self._batch_error_message(batch_result),
            "elapsed_seconds": round(elapsed, 2),
            "use_unified": bool(request.get("file_metadata", {}).get("use_unified")),
            "file_metadata": request.get("file_metadata", {}),
            "model": request.get("request", {}).get("model"),
            "usage": {"billing_multiplier": 0.5},
            "billing_mode": "anthropic_batch",
        }

    def _submit_anthropic_batch_round(
        self,
        indexed_requests: list[tuple[int, dict]],
        current_max_tokens: dict[int, int],
        round_num: int,
        total_rounds: int,
    ) -> list[dict]:
        if not indexed_requests:
            return []

        start_time = time.time()
        batch_requests, structured_by_custom_id = self._build_anthropic_batch_requests(
            indexed_requests,
            current_max_tokens,
        )
        batch, structured_by_custom_id = self._create_anthropic_batch(
            batch_requests,
            structured_by_custom_id,
        )
        batch_id = self._object_get(batch, "id")
        print(
            f"Submitted Anthropic batch round {round_num}/{total_rounds} "
            f"with {len(batch_requests)} request(s): {batch_id}",
            flush=True,
        )
        log.info(
            f"Monitor: Submitted Anthropic batch {batch_id} round {round_num}/{total_rounds}"
        )
        self._poll_anthropic_batch(batch_id)

        custom_id_to_index = {
            self._batch_custom_id(index): index for index, _request in indexed_requests
        }
        request_by_index = {index: request for index, request in indexed_requests}
        results_by_index = {}
        elapsed = time.time() - start_time
        for item in self.client.messages.batches.results(batch_id):
            custom_id = self._object_get(item, "custom_id")
            if custom_id not in custom_id_to_index:
                log.warning(f"Monitor: Ignoring unknown batch result custom_id={custom_id}")
                continue
            index = custom_id_to_index[custom_id]
            result = self._result_from_batch_item(
                index=index,
                request=request_by_index[index],
                item=item,
                structured_outputs=structured_by_custom_id.get(custom_id, False),
                elapsed=elapsed,
            )
            result["billing_mode"] = "anthropic_batch"
            results_by_index[index] = result

        for index, request in indexed_requests:
            if index not in results_by_index:
                results_by_index[index] = {
                    "index": index,
                    "status": "FAILED",
                    "error": "Batch result missing from results stream",
                    "elapsed_seconds": round(elapsed, 2),
                    "use_unified": bool(request.get("file_metadata", {}).get("use_unified")),
                    "file_metadata": request.get("file_metadata", {}),
                    "model": request.get("request", {}).get("model"),
                    "usage": {"billing_multiplier": 0.5},
                    "billing_mode": "anthropic_batch",
                }

        return [results_by_index[index] for index, _request in indexed_requests]

    def _submit_job_anthropic_batch(self, requests: list[dict]):
        total = len(requests)
        log.info(f"Monitor: Processing {total} requests via Anthropic batch...")
        if requests:
            log.debug(f"Model: {requests[0].get('request', {}).get('model', 'unknown')}")
        print(f"Processing {total} request(s) with Anthropic batch mode.", flush=True)

        current_max_tokens = {
            index: request["request"]["max_tokens"] for index, request in enumerate(requests)
        }
        results_by_index = {}
        pending_indices = list(range(total))
        max_rounds = 2

        for round_num in range(1, max_rounds + 1):
            indexed_requests = [(index, requests[index]) for index in pending_indices]
            round_results = self._submit_anthropic_batch_round(
                indexed_requests,
                current_max_tokens,
                round_num=round_num,
                total_rounds=max_rounds,
            )
            for result in round_results:
                results_by_index[result["index"]] = result

            retry_indices = [
                result["index"]
                for result in round_results
                if result.get("status") in {"TRUNCATED", "PARSE_FAILED", "FAILED"}
            ]
            if not retry_indices or round_num == max_rounds:
                break

            for index in retry_indices:
                current_max_tokens[index] = min(current_max_tokens[index] + 8192, 65536)
            print(
                f"Retrying {len(retry_indices)} batch chunk(s) with larger max_tokens.",
                flush=True,
            )
            pending_indices = retry_indices

        results = [
            results_by_index.get(
                index,
                {
                    "index": index,
                    "status": "FAILED",
                    "error": "Batch request was not processed",
                    "use_unified": bool(requests[index].get("file_metadata", {}).get("use_unified")),
                    "file_metadata": requests[index].get("file_metadata", {}),
                    "model": requests[index].get("request", {}).get("model"),
                    "usage": {"billing_multiplier": 0.5},
                    "billing_mode": "anthropic_batch",
                },
            )
            for index in range(total)
        ]

        self._apply_fidelity_verification(requests, results)
        successful, failed, state = self._summarize_results(total, results)
        log.info(f"\n{'='*50}")
        log.info("PROCESSING COMPLETE")
        log.info(f"  Successful: {successful}/{total}")
        log.info(f"  Failed: {failed}/{total}")
        log.info(f"{'='*50}")

        self._save_results_cache(results)
        return SimpleJob(name="local_job", state=state, results=results)

    def _apply_fidelity_verification(self, requests: list[dict], results: list[dict]) -> None:
        if not self.book_name:
            return

        from app.core.verifier import FidelityVerifier

        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        verifier = FidelityVerifier(self.book_name, logs_dir=logs_dir)
        report = verifier.verify_results(results, requests)
        path = verifier.write_report(report)

        results_by_index = {result.get("index"): result for result in results}
        for chunk in report.get("chunks", []):
            result = results_by_index.get(chunk.get("index"))
            if not result:
                continue
            findings = chunk.get("findings") or []
            hard_failures = int(chunk.get("hard_failures") or 0)
            result["fidelity"] = {
                "findings_count": len(findings),
                "hard_failures": hard_failures,
                "report_path": path,
            }
            if result.get("status") == "SUCCESS" and hard_failures:
                result["status"] = "FIDELITY_FAILED"
                result["error"] = (
                    f"Fidelity hard failures: {hard_failures}; retry this chunk after reviewing {path}"
                )

        summary = report.get("summary") or {}
        quote_failures = summary.get("QUOTE_NOT_IN_SOURCE", 0)
        missing_chapters = summary.get("CHAPTER_MISSING", 0)
        ungrounded_entities = summary.get("ENTITY_NOT_IN_SOURCE", 0)
        print(
            "Fidelity: "
            f"{quote_failures} quote failures, "
            f"{missing_chapters} missing chapters, "
            f"{ungrounded_entities} ungrounded entities - see {path}",
            flush=True,
        )
        if report.get("hard_failures", 0):
            print(
                "Fidelity hard failures marked retryable; rerun with --retry after review.",
                flush=True,
            )
        
    def submit_job(self, requests):
        """
        Processes requests sequentially using Claude Messages API.

        For unified pipeline requests (use_unified=True), parses and validates
        JSON responses. Retries on truncated responses with increased max_tokens.
        """
        if self._can_use_anthropic_batch():
            return self._submit_job_anthropic_batch(requests)

        total = len(requests)
        concurrency = min(max(1, INGEST_CONCURRENCY), total or 1)
        mode_label = "sequentially" if concurrency == 1 else f"with concurrency={concurrency}"
        log.info(f"Monitor: Processing {total} requests {mode_label}...")
        if requests:
            log.debug(f"Model: {requests[0].get('request', {}).get('model', 'unknown')}")
        log.debug(f"Provider: {self.provider}")

        for i in range(total):
            log.info(f"\n{'='*50}")
            log.info(f"Monitor: Processing chunk {i + 1}/{total}...")

        if concurrency == 1:
            results = []
            for i, request in enumerate(requests):
                results.append(self._process_request(i, request, total))
                if i < total - 1:
                    log.debug("Pausing 1s before next request...")
                    time.sleep(1)
        else:
            results = []
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                future_map = {
                    executor.submit(self._process_request, i, request, total): i
                    for i, request in enumerate(requests)
                }
                for future in as_completed(future_map):
                    results.append(future.result())

            results.sort(key=lambda result: result.get("index", 0))

        self._apply_fidelity_verification(requests, results)

        # Summary
        successful, failed, state = self._summarize_results(total, results)
        log.info(f"\n{'='*50}")
        log.info(f"PROCESSING COMPLETE")
        log.info(f"  Successful: {successful}/{total}")
        log.info(f"  Failed: {failed}/{total}")
        log.info(f"{'='*50}")

        # Save results to cache for exporter to use
        self._save_results_cache(results)

        return SimpleJob(name="local_job", state=state, results=results)

    def run_ephemeral_request(self, request: dict, label: str = "ephemeral request") -> dict:
        """Process a request without writing it to the persistent results cache."""
        log.info(f"Monitor: Running {label}...")
        return self._process_request(0, request, 1)
    
    def _save_results_cache(self, results):
        """Save results to a cache file for the exporter."""
        with open(self.results_cache, 'w') as f:
            json.dump(results, f, indent=2)
        log.info(f"Monitor: Saved {len(results)} results to {self.results_cache}")

    def _salvage_cached_parse_failures(self, results: list) -> int:
        """
        Re-parse cached PARSE_FAILED unified responses.

        Useful after parser improvements: we can recover previously failed chunks
        without paying for another API call.
        """
        recovered = 0
        for result in results:
            if result.get("status") != "PARSE_FAILED":
                continue
            if not result.get("use_unified"):
                continue

            response_text = result.get("response", "")
            if not response_text:
                continue

            parse_result = self._parse_unified_response(response_text, {"use_unified": True})
            if parse_result.get("status") == "SUCCESS":
                result["status"] = "SUCCESS"
                result["data"] = parse_result["data"]
                result.pop("error", None)
                recovered += 1

        return recovered

    def load_cached_results(self) -> list:
        """Load cached results from previous run if available."""
        if os.path.exists(self.results_cache):
            try:
                with open(self.results_cache, 'r') as f:
                    results = json.load(f)
                recovered = self._salvage_cached_parse_failures(results)
                if recovered > 0:
                    self._save_results_cache(results)
                    log.info(f"Monitor: Auto-recovered {recovered} cached chunk(s) via JSON repair")
                log.info(f"Monitor: Loaded {len(results)} cached results from {self.results_cache}")
                return results
            except Exception as e:
                log.warning(f"Monitor: Could not load cached results: {e}")
        return []

    def get_failed_chunk_indices(self, cached_results: list) -> list:
        """Get indices of chunks that failed or need retry."""
        failed_indices = []
        for result in cached_results:
            status = result.get("status", "UNKNOWN")
            if status not in ("SUCCESS",):
                failed_indices.append(result.get("index", -1))
        return [i for i in failed_indices if i >= 0]

    def submit_job_retry(self, requests, cached_results: list):
        """
        Retry only failed chunks, merging with cached successful results.

        Args:
            requests: Full list of requests (same as original run)
            cached_results: Results from previous run

        Returns:
            SimpleJob with merged results
        """
        failed_indices = self.get_failed_chunk_indices(cached_results)

        if not failed_indices:
            log.info("Monitor: No failed chunks to retry")
            return SimpleJob(name="local_job", state="SUCCEEDED", results=cached_results)

        log.info(f"Monitor: Retrying {len(failed_indices)} failed chunks: {failed_indices}")
        print(f"\n🔄 Retrying {len(failed_indices)} failed chunk(s)...", flush=True)

        total = len(requests)
        new_results = []
        valid_failed_indices = [idx for idx in failed_indices if idx < len(requests)]
        for idx in failed_indices:
            if idx >= len(requests):
                log.warning(f"Monitor: Chunk index {idx} out of range, skipping")

        if self._can_use_anthropic_batch():
            current_max_tokens = {
                index: requests[index]["request"]["max_tokens"]
                for index in valid_failed_indices
            }
            pending_indices = valid_failed_indices
            max_rounds = 2
            for round_num in range(1, max_rounds + 1):
                indexed_requests = [(index, requests[index]) for index in pending_indices]
                round_results = self._submit_anthropic_batch_round(
                    indexed_requests,
                    current_max_tokens,
                    round_num=round_num,
                    total_rounds=max_rounds,
                )
                new_results.extend(round_results)
                retry_indices = [
                    result["index"]
                    for result in round_results
                    if result.get("status") in {"TRUNCATED", "PARSE_FAILED", "FAILED"}
                ]
                if not retry_indices or round_num == max_rounds:
                    break
                for index in retry_indices:
                    current_max_tokens[index] = min(current_max_tokens[index] + 8192, 65536)
                pending_indices = retry_indices
        else:
            for idx in valid_failed_indices:
                request = requests[idx]
                chapter_num = idx + 1

                log.info(f"\n{'='*50}")
                log.info(f"Monitor: Retrying chunk {chapter_num}/{total}...")
                print(f"\n{'='*50}", flush=True)
                print(f"Monitor: Retrying chunk {chapter_num}/{total}...", flush=True)

                new_results.append(self._process_request(idx, request, total))
                time.sleep(1)  # Rate limit pause

        # Merge results: replace failed chunks with new results
        merged_results = list(cached_results)
        latest_new_results = {}
        for new_result in new_results:
            latest_new_results[new_result["index"]] = new_result
        for new_result in latest_new_results.values():
            idx = new_result["index"]
            # Find and replace the old result at this index
            for i, old_result in enumerate(merged_results):
                if old_result.get("index") == idx:
                    merged_results[i] = new_result
                    break

        # Summary
        log.info(f"\n{'='*50}")
        log.info(f"RETRY COMPLETE")
        log.info(f"  Retried: {len(failed_indices)}")
        retry_successes = sum(
            1 for result in latest_new_results.values() if self._is_success_result(result)
        )
        retry_failures = len(latest_new_results) - retry_successes
        log.info(f"  Successful: {retry_successes}")
        log.info(f"  Still failed: {retry_failures}")
        log.info(f"{'='*50}")

        # Save merged results
        self._apply_fidelity_verification(requests, merged_results)
        self._save_results_cache(merged_results)

        # Determine final state
        successful, still_failed, state = self._summarize_results(
            len(merged_results),
            merged_results,
        )
        return SimpleJob(name="local_job", state=state, results=merged_results)



class SimpleJob:
    """A simple job class for local processing compatibility."""
    def __init__(self, name, state, results=None):
        self.name = name
        self.state = state
        self.results = results or []
