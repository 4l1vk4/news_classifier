"""Translation module for foreign news articles (EN -> RU).

Provides lightweight, robust machine translation without mandatory external API keys
or heavy dependencies. Implements multi-tier failover:
1. Google Translate Client endpoint (high accuracy & speed)
2. MyMemory Translation API (reliable fallback)
3. In-memory caching and graceful offline tolerance
"""
import html
import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class Translator:
    """Translates news titles and text between languages with caching and failover."""

    def __init__(self, enabled: bool = True, timeout: float = 4.0):
        self.enabled = enabled
        self.timeout = timeout
        self._cache: Dict[str, str] = {}

    def _translate_google_client(self, text: str, source: str, target: str) -> Optional[str]:
        encoded = urllib.parse.quote(text)
        url = f"https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl={source}&tl={target}&q={encoded}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and data and isinstance(data[0], str):
                return data[0].strip()
            elif isinstance(data, str) and data.strip():
                return data.strip()
        return None

    def _translate_mymemory(self, text: str, source: str, target: str) -> Optional[str]:
        encoded = urllib.parse.quote(text[:500])
        url = f"https://api.mymemory.translated.net/get?q={encoded}&langpair={source}|{target}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("responseData", {}).get("translatedText")
            if result and not result.startswith("MYMEMORY WARNING"):
                return result.strip()
        return None

    def _translate_deep_translator(self, text: str, source: str, target: str) -> Optional[str]:
        try:
            from deep_translator import GoogleTranslator
            res = GoogleTranslator(source=source, target=target).translate(text)
            if res:
                return res.strip()
        except Exception:
            pass
        return None

    def translate(self, text: str, source_lang: str = "en", target_lang: str = "ru") -> str:
        """Translate text from source_lang to target_lang.

        Returns the translated string, or empty string on failure.
        """
        if not self.enabled or not text:
            return ""

        clean_text = html.unescape(text).strip()
        if not clean_text:
            return ""

        cache_key = f"{source_lang}->{target_lang}:{clean_text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            res = self._translate_google_client(clean_text, source_lang, target_lang)
            if res:
                self._cache[cache_key] = res
                return res
        except Exception as e:
            logger.debug(f"Google translate client failed: {e}")

        #MyMemory API
        try:
            res = self._translate_mymemory(clean_text, source_lang, target_lang)
            if res:
                self._cache[cache_key] = res
                return res
        except Exception as e:
            logger.debug(f"MyMemory translate failed: {e}")


_DEFAULT_TRANSLATOR = Translator()


def translate_en_to_ru(text: str) -> str:
    """Convenience helper to translate English text to Russian."""
    return _DEFAULT_TRANSLATOR.translate(text, source_lang="en", target_lang="ru")
