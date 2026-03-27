"""
LLM Code Validator – Multi-provider LLM integration for validating and improving
generated Spring Boot code.

Supported providers:
  - Anthropic Claude (claude-sonnet-4-20250514, claude-3-5-sonnet, claude-3-opus)
  - OpenAI GPT (gpt-4o, gpt-4-turbo, gpt-4o-mini)
  - Google Gemini (gemini-2.0-flash, gemini-1.5-pro, gemini-2.5-pro)
  - DeepSeek (deepseek-chat, deepseek-coder)
  - Groq (llama-3.3-70b, mixtral-8x7b) — for open-source models
  - Ollama (local models — codellama, llama3, mistral, deepseek-coder-v2)

Each provider validates generated Java/Spring Boot code for:
  - Compilation correctness
  - Spring Boot best practices
  - Security vulnerabilities
  - Missing imports / annotations
  - TODO items that need manual attention
  - Performance suggestions
"""
import json
import os
import re
from abc import ABC, abstractmethod


# ══════════════════════════════════════════════════════════════════════════════
#  Provider Registry
# ══════════════════════════════════════════════════════════════════════════════
LLM_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic Claude",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4 (Latest)", "tier": "premium"},
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "tier": "premium"},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "tier": "premium"},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku (Fast)", "tier": "standard"},
        ],
        "env_key": "ANTHROPIC_API_KEY",
        "docs_url": "https://console.anthropic.com/",
    },
    "openai": {
        "name": "OpenAI GPT",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (Latest)", "tier": "premium"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "tier": "premium"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast)", "tier": "standard"},
            {"id": "o3-mini", "name": "o3-mini (Reasoning)", "tier": "premium"},
        ],
        "env_key": "OPENAI_API_KEY",
        "docs_url": "https://platform.openai.com/",
    },
    "google": {
        "name": "Google Gemini",
        "models": [
            {"id": "gemini-2.5-pro-preview-05-06", "name": "Gemini 2.5 Pro (Latest)", "tier": "premium"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash (Fast)", "tier": "standard"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "tier": "premium"},
        ],
        "env_key": "GOOGLE_API_KEY",
        "docs_url": "https://aistudio.google.com/",
    },
    "deepseek": {
        "name": "DeepSeek",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek V3 (Chat)", "tier": "standard"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder", "tier": "standard"},
            {"id": "deepseek-reasoner", "name": "DeepSeek R1 (Reasoning)", "tier": "premium"},
        ],
        "env_key": "DEEPSEEK_API_KEY",
        "docs_url": "https://platform.deepseek.com/",
    },
    "groq": {
        "name": "Groq (Open Source)",
        "models": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "tier": "free"},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "tier": "free"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B (Fast)", "tier": "free"},
        ],
        "env_key": "GROQ_API_KEY",
        "docs_url": "https://console.groq.com/",
    },
    "ollama": {
        "name": "Ollama (Local)",
        "models": [
            {"id": "codellama:13b", "name": "CodeLlama 13B", "tier": "free"},
            {"id": "llama3:8b", "name": "Llama 3 8B", "tier": "free"},
            {"id": "deepseek-coder-v2:16b", "name": "DeepSeek Coder V2", "tier": "free"},
            {"id": "mistral:7b", "name": "Mistral 7B", "tier": "free"},
            {"id": "qwen2.5-coder:14b", "name": "Qwen 2.5 Coder 14B", "tier": "free"},
        ],
        "env_key": "",
        "docs_url": "https://ollama.com/",
        "base_url": "http://localhost:11434",
    },
}


# ══════════════════════════════════════════════════════════════════════════════
#  Validation prompt template
# ══════════════════════════════════════════════════════════════════════════════
VALIDATION_SYSTEM_PROMPT = """You are a senior Java/Spring Boot engineer reviewing auto-migrated code.
The code was produced by automatically migrating a MuleSoft 4 application to Spring Boot 3.2.

Review the code and provide a JSON response with this EXACT structure:
{
  "overallScore": <number 1-10>,
  "summary": "<1-2 sentence overall assessment>",
  "issues": [
    {
      "severity": "critical|warning|info",
      "file": "<filename>",
      "line": "<line hint or empty>",
      "message": "<description of issue>",
      "suggestion": "<how to fix>"
    }
  ],
  "improvements": [
    {
      "file": "<filename>",
      "description": "<improvement description>",
      "code": "<corrected code snippet if applicable>"
    }
  ],
  "missingItems": ["<list of things that need manual implementation>"],
  "securityIssues": ["<list of security concerns>"],
  "bestPractices": ["<list of Spring Boot best practice violations>"]
}

Be precise. Focus on real issues. Do NOT flag stylistic preferences."""


def _build_validation_prompt(files: dict, summary: dict) -> str:
    """Build the user prompt with all generated files."""
    prompt_parts = [
        "Review the following auto-migrated Spring Boot project.\n",
        f"Migration summary: {json.dumps(summary, default=str)}\n\n",
        "=== GENERATED FILES ===\n",
    ]

    # Include all Java files and config files (skip binary-like content)
    for filepath, content in sorted(files.items()):
        if any(filepath.endswith(ext) for ext in
               ('.java', '.properties', '.yml', '.xml', '.gradle')):
            # Truncate very large files
            if len(content) > 8000:
                content = content[:8000] + "\n... [truncated]"
            prompt_parts.append(f"\n--- {filepath} ---\n{content}\n")

    prompt_parts.append(
        "\n\nReturn ONLY valid JSON matching the schema described. "
        "No markdown fences, no extra text."
    )
    return "".join(prompt_parts)


# ══════════════════════════════════════════════════════════════════════════════
#  Abstract base provider
# ══════════════════════════════════════════════════════════════════════════════
class BaseLLMProvider(ABC):
    def __init__(self, api_key: str = "", model: str = "", base_url: str = ""):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    @abstractmethod
    def validate(self, files: dict, summary: dict) -> dict:
        """Send files to the LLM for validation and return structured results."""
        pass

    @abstractmethod
    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        """Send a generic chat request to the LLM and return the raw text response.
        Used by the conversion pipeline for real-time code generation during migration.
        Raises Exception on failure (callers handle fallback)."""
        pass

    def _parse_response(self, text: str) -> dict:
        """Parse JSON from LLM response, handling markdown fences."""
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*\n?", "", text)
            text = re.sub(r"\n?```\s*$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    pass
            return {
                "overallScore": 0,
                "summary": "Failed to parse LLM response",
                "issues": [{"severity": "warning", "file": "",
                           "line": "", "message": "LLM returned invalid JSON",
                           "suggestion": "Try again or use a different model"}],
                "improvements": [],
                "missingItems": [],
                "securityIssues": [],
                "bestPractices": [],
                "rawResponse": text[:2000],
            }


# ══════════════════════════════════════════════════════════════════════════════
#  Anthropic Claude Provider
# ══════════════════════════════════════════════════════════════════════════════
class AnthropicProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        try:
            import anthropic
        except ImportError:
            return _import_error("anthropic", "pip install anthropic")

        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return _missing_key_error("ANTHROPIC_API_KEY")

        client = anthropic.Anthropic(api_key=api_key)
        user_prompt = _build_validation_prompt(files, summary)

        try:
            response = client.messages.create(
                model=self.model or "claude-sonnet-4-20250514",
                max_tokens=4096,
                system=VALIDATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return self._parse_response(response.content[0].text)
        except Exception as e:
            return _api_error("Anthropic", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import anthropic
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model or "claude-sonnet-4-20250514",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text


# ══════════════════════════════════════════════════════════════════════════════
#  OpenAI GPT Provider
# ══════════════════════════════════════════════════════════════════════════════
class OpenAIProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        try:
            import openai
        except ImportError:
            return _import_error("openai", "pip install openai")

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return _missing_key_error("OPENAI_API_KEY")

        client = openai.OpenAI(api_key=api_key)
        user_prompt = _build_validation_prompt(files, summary)

        try:
            response = client.chat.completions.create(
                model=self.model or "gpt-4o",
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            return _api_error("OpenAI", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import openai
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model or "gpt-4o",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


# ══════════════════════════════════════════════════════════════════════════════
#  Google Gemini Provider
# ══════════════════════════════════════════════════════════════════════════════
class GoogleProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        try:
            import google.generativeai as genai
        except ImportError:
            return _import_error("google-generativeai", "pip install google-generativeai")

        api_key = self.api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not api_key:
            return _missing_key_error("GOOGLE_API_KEY")

        genai.configure(api_key=api_key)
        user_prompt = _build_validation_prompt(files, summary)

        try:
            model = genai.GenerativeModel(
                model_name=self.model or "gemini-2.0-flash",
                system_instruction=VALIDATION_SYSTEM_PROMPT,
            )
            response = model.generate_content(
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )
            return self._parse_response(response.text)
        except Exception as e:
            return _api_error("Google Gemini", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import google.generativeai as genai
        api_key = self.api_key or os.environ.get("GOOGLE_API_KEY", "")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name=self.model or "gemini-2.0-flash",
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
            ),
        )
        return response.text


# ══════════════════════════════════════════════════════════════════════════════
#  DeepSeek Provider (OpenAI-compatible API)
# ══════════════════════════════════════════════════════════════════════════════
class DeepSeekProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        try:
            import openai
        except ImportError:
            return _import_error("openai", "pip install openai")

        api_key = self.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return _missing_key_error("DEEPSEEK_API_KEY")

        client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url or "https://api.deepseek.com",
        )
        user_prompt = _build_validation_prompt(files, summary)

        try:
            response = client.chat.completions.create(
                model=self.model or "deepseek-chat",
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            return _api_error("DeepSeek", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import openai
        api_key = self.api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url or "https://api.deepseek.com",
        )
        response = client.chat.completions.create(
            model=self.model or "deepseek-chat",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


# ══════════════════════════════════════════════════════════════════════════════
#  Groq Provider (OpenAI-compatible API — Llama, Mixtral)
# ══════════════════════════════════════════════════════════════════════════════
class GroqProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        try:
            import openai
        except ImportError:
            return _import_error("openai", "pip install openai")

        api_key = self.api_key or os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return _missing_key_error("GROQ_API_KEY")

        client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url or "https://api.groq.com/openai/v1",
        )
        user_prompt = _build_validation_prompt(files, summary)
        # Groq has smaller context — truncate if needed
        if len(user_prompt) > 25000:
            user_prompt = user_prompt[:25000] + "\n... [truncated for context limit]"

        try:
            response = client.chat.completions.create(
                model=self.model or "llama-3.3-70b-versatile",
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            return self._parse_response(response.choices[0].message.content)
        except Exception as e:
            return _api_error("Groq", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import openai
        api_key = self.api_key or os.environ.get("GROQ_API_KEY", "")
        client = openai.OpenAI(
            api_key=api_key,
            base_url=self.base_url or "https://api.groq.com/openai/v1",
        )
        response = client.chat.completions.create(
            model=self.model or "llama-3.3-70b-versatile",
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content


# ══════════════════════════════════════════════════════════════════════════════
#  Ollama Provider (Local — no API key needed)
# ══════════════════════════════════════════════════════════════════════════════
class OllamaProvider(BaseLLMProvider):
    def validate(self, files: dict, summary: dict) -> dict:
        import urllib.request
        import urllib.error

        base_url = self.base_url or "http://localhost:11434"
        user_prompt = _build_validation_prompt(files, summary)
        # Local models have smaller context
        if len(user_prompt) > 15000:
            user_prompt = user_prompt[:15000] + "\n... [truncated for context limit]"

        payload = json.dumps({
            "model": self.model or "codellama:13b",
            "messages": [
                {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"num_predict": 4096},
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return self._parse_response(data.get("message", {}).get("content", "{}"))
        except urllib.error.URLError:
            return _api_error("Ollama",
                "Cannot connect to Ollama. Make sure it's running: ollama serve")
        except Exception as e:
            return _api_error("Ollama", str(e))

    def chat(self, system_prompt: str, user_prompt: str,
             max_tokens: int = 2048) -> str:
        import urllib.request
        base_url = self.base_url or "http://localhost:11434"
        payload = json.dumps({
            "model": self.model or "codellama:13b",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"num_predict": max_tokens},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "")


# ══════════════════════════════════════════════════════════════════════════════
#  Provider Factory
# ══════════════════════════════════════════════════════════════════════════════
PROVIDER_CLASSES = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "google": GoogleProvider,
    "deepseek": DeepSeekProvider,
    "groq": GroqProvider,
    "ollama": OllamaProvider,
}


def get_provider(provider_name: str, api_key: str = "",
                 model: str = "", base_url: str = "") -> BaseLLMProvider:
    """Factory method to get the appropriate LLM provider."""
    cls = PROVIDER_CLASSES.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown LLM provider: {provider_name}. "
                        f"Available: {', '.join(PROVIDER_CLASSES.keys())}")
    return cls(api_key=api_key, model=model, base_url=base_url)


def get_available_providers() -> dict:
    """Return the full provider registry for the frontend."""
    return LLM_PROVIDERS


def validate_code(provider_name: str, api_key: str, model: str,
                  files: dict, summary: dict, base_url: str = "") -> dict:
    """Main entry point — validate generated code using the specified LLM."""
    provider = get_provider(provider_name, api_key, model, base_url)
    result = provider.validate(files, summary)

    # Ensure consistent structure
    result.setdefault("overallScore", 0)
    result.setdefault("summary", "")
    result.setdefault("issues", [])
    result.setdefault("improvements", [])
    result.setdefault("missingItems", [])
    result.setdefault("securityIssues", [])
    result.setdefault("bestPractices", [])

    return result


def chat_with_llm(config: dict, system_prompt: str,
                  user_prompt: str, max_tokens: int = 2048) -> str:
    """Convenience function for generic LLM chat — used by the conversion pipeline.

    Args:
        config: dict with keys 'provider', 'apiKey', 'model', optionally 'baseUrl'
        system_prompt: system-level instructions for the LLM
        user_prompt: the user-facing prompt
        max_tokens: max response length

    Returns:
        Raw text response from the LLM.

    Raises:
        Exception on any failure (caller handles fallback).
    """
    provider = get_provider(
        config.get("provider", ""),
        api_key=config.get("apiKey", ""),
        model=config.get("model", ""),
        base_url=config.get("baseUrl", ""),
    )
    return provider.chat(system_prompt, user_prompt, max_tokens)


# ══════════════════════════════════════════════════════════════════════════════
#  Error helpers
# ══════════════════════════════════════════════════════════════════════════════
def _import_error(package: str, install_cmd: str) -> dict:
    return {
        "overallScore": 0,
        "summary": f"Missing dependency: {package}",
        "issues": [{
            "severity": "critical", "file": "", "line": "",
            "message": f"Python package '{package}' is not installed.",
            "suggestion": f"Run: {install_cmd}",
        }],
        "improvements": [], "missingItems": [],
        "securityIssues": [], "bestPractices": [],
    }


def _missing_key_error(env_var: str) -> dict:
    return {
        "overallScore": 0,
        "summary": f"Missing API key: {env_var}",
        "issues": [{
            "severity": "critical", "file": "", "line": "",
            "message": f"API key not provided. Set the '{env_var}' environment variable or enter it in the settings.",
            "suggestion": f"Export {env_var}=your_key or provide it in the UI.",
        }],
        "improvements": [], "missingItems": [],
        "securityIssues": [], "bestPractices": [],
    }


def _api_error(provider: str, error_msg: str) -> dict:
    return {
        "overallScore": 0,
        "summary": f"{provider} API error",
        "issues": [{
            "severity": "critical", "file": "", "line": "",
            "message": f"{provider} API call failed: {error_msg}",
            "suggestion": "Check your API key, model name, and network connection.",
        }],
        "improvements": [], "missingItems": [],
        "securityIssues": [], "bestPractices": [],
    }
