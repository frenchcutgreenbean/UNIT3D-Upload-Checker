#!/usr/bin/env python3
import re
from typing import Dict, Any, Optional
from guessit import guessit
from ..PTN.parse import PTN
from ..settings import Settings

# Quality mappings
QUALITY_MAPPINGS = {"bluray": "encode", "web": "webrip"}
# tokens sometimes injected into titles by parsers that we want removed
FP_KEYWORDS = ["UHD", "HYBRID"]


class FileParser:
    """Parse filename metadata using PTN and guessit with simple, readable helpers."""

    def __init__(self):
        self.ptn = PTN()
        self.settings = Settings()
        self.current_settings = self.settings.current_settings
        self.ignored_keywords = self.current_settings.get("ignored_keywords", []) or []
        self.ignored_qualities = self.current_settings.get("ignored_qualities", []) or []

    def parse_file(self, name: str, verbose: bool = False) -> Dict[str, Any]:
        """Return a rich metadata dict (titles, year, quality, resolution, codec, group, plus raw parser keys)."""
        ptn_info = self.ptn.parse(name) or {}
        guessit_info = dict(guessit(name)) if name else {}

        # Titles and years from both parsers
        title_ptn = (ptn_info.get("title") or "").strip()
        title_guess = (guessit_info.get("title") or "").strip()
        year_ptn = str(ptn_info.get("year")).strip() if ptn_info.get("year") else ""
        year_guess = str(guessit_info.get("year")).strip() if guessit_info.get("year") else ""

        # Decide canonical title
        title = self._choose_title(title_ptn, title_guess, FP_KEYWORDS)

        # Decide year (prefer when both agree, otherwise try to extract from chosen title)
        year = year_ptn if year_ptn == year_guess and year_ptn else ""
        if not year:
            year_from_title, cleaned = self._extract_year_from_title(title)
            if year_from_title:
                year = year_from_title
                title = cleaned
                if verbose:
                    print(f"Year extracted from title -> {year}; title now: '{title}'")

        # Other common fields with fallbacks
        quality = ptn_info.get("quality") or guessit_info.get("quality") or ""
        resolution = (
            (ptn_info.get("resolution") or "").strip() or (guessit_info.get("screen_size") or "").strip()
        ) or None
        group = ptn_info.get("group") or guessit_info.get("release_group") or ""
        codec = ptn_info.get("codec") or guessit_info.get("video_codec") or ""

        result: Dict[str, Any] = {
            "title": title,
            "year": year,
            "quality": quality,
            "resolution": resolution,
            "codec": codec,
            "group": group,
        }

        # Add unique keys from PTN and guessit without overwriting existing keys in result
        for src in (ptn_info, guessit_info):
            for k, v in src.items():
                if k not in result and v is not None:
                    result[k] = v

        return result

    def parse_filename(self, file_name: str, verbose: bool = False) -> Dict[str, Any]:
        """Higher-level parse used by scanner: returns minimal fields plus banned flag and tmdb placeholder."""
        parsed = self.parse_file(file_name, verbose)
        banned = self._check_if_show(parsed, file_name)
        quality = self._normalize_quality(parsed.get("quality") or "")
        if quality in self.ignored_qualities:
            banned = True
        if any(kw.lower() in (parsed.get("title") or "").lower() for kw in self.ignored_keywords):
            banned = True
        return {
            "title": parsed.get("title", ""),
            "year": parsed.get("year", ""),
            "quality": quality,
            "resolution": parsed.get("resolution", ""),
            "codec": parsed.get("codec", ""),
            "group": parsed.get("group", ""),
            "banned": banned,
            "tmdb": None,
        }

    # --- Helpers ------------------------------------------------------------

    def _choose_title(self, title_ptn: str, title_guess: str, fp_keywords: Optional[list]) -> str:
        """Pick a canonical title.

        Dynamic handling of false-positive tokens (fp_keywords):
        - If a token appears in one title but not the other, remove it from that title.
        - If a token appears in both titles, leave it (could be part of the real title).
        - After cleanup, choose the longer non-empty title; prefer PTN when equal length.
        """
        t1 = title_ptn or ""
        t2 = title_guess or ""

        # fast-path
        if not fp_keywords:
            # choose longer, prefer PTN on tie
            if not t1 and not t2:
                return ""
            if not t1:
                return t2
            if not t2:
                return t1
            return t1 if len(t1) >= len(t2) else t2

        # Normalize for token detection (case-insensitive)
        up1 = t1.upper()
        up2 = t2.upper()
        tokens = [tok.upper() for tok in fp_keywords]

        # Detect which tokens appear in each title
        tokens_in_t1 = {tok for tok in tokens if re.search(r"\b" + re.escape(tok) + r"\b", up1)}
        tokens_in_t2 = {tok for tok in tokens if re.search(r"\b" + re.escape(tok) + r"\b", up2)}

        # Tokens to remove are those present in one title but not the other
        rem_t1 = tokens_in_t1 - tokens_in_t2
        rem_t2 = tokens_in_t2 - tokens_in_t1

        def _remove_tokens(s: str, rem_set: set) -> str:
            if not rem_set or not s:
                return s
            pattern = r"\b(?:" + "|".join(re.escape(tok) for tok in rem_set) + r")\b"
            return re.sub(pattern, "", s, flags=re.IGNORECASE).strip()

        t1_clean = _remove_tokens(t1, rem_t1)
        t2_clean = _remove_tokens(t2, rem_t2)

        # Choose the best title: longer wins, prefer PTN (t1) on ties
        if not t1_clean and not t2_clean:
            return ""
        if not t1_clean:
            return t2_clean
        if not t2_clean:
            return t1_clean
        return t1_clean if len(t1_clean) >= len(t2_clean) else t2_clean

    def _extract_year_from_title(self, title: str) -> tuple[str, str]:
        """If a YYYY exists in the title, return (year, title-without-year)."""
        if not title:
            return "", title
        m = re.search(r"\b(19|20)\d{2}\b", title)
        if not m:
            return "", title
        year = m.group(0)
        cleaned = re.sub(r"\b" + re.escape(year) + r"\b", "", title).strip()
        return year, cleaned

    def _check_if_show(self, parsed: Dict[str, Any], filename: str) -> bool:
        """Heuristic: show/episode if guessit/ptn exposed episode/season keys or filename contains SxxExx."""
        if any(k in parsed for k in ("episode", "season", "episode_title", "episode_details")):
            if re.search(r"[Ss]\d{1,2}[Ee]\d{1,2}", filename):
                return True
        return False

    def _normalize_quality(self, quality: str) -> str:
        """Normalize quality strings to a canonical token (lowercase)."""
        if not quality:
            return ""
        clean = re.sub(r"[^a-zA-Z]", "", quality).strip().lower()
        return QUALITY_MAPPINGS.get(clean, clean)
