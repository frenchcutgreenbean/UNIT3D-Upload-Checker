#!/usr/bin/env python3
"""
Standardized HDR format constants to ensure consistency across the codebase.
"""

# Standard HDR format names
SDR = "SDR"
HDR = "HDR"
HDR10_PLUS = "HDR10+"
DOLBY_VISION = "DV"
DOLBY_VISION_HDR = "DV + HDR"
DOLBY_VISION_HDR10P = "DV + HDR10+"

# HDR quality hierarchy (higher index = better)
HDR_HIERARCHY = [
    SDR,              # 0: Standard Dynamic Range
    HDR,              # 1: Generic HDR (including HDR10)
    HDR10_PLUS,       # 2: HDR10+
    DOLBY_VISION,     # 3: Dolby Vision
    DOLBY_VISION_HDR, # 4: Dolby Vision + HDR
    DOLBY_VISION_HDR10P  # 5: Dolby Vision + HDR10+ (best)
]

# Format detection regular expressions
HDR_REGEXES = {
    DOLBY_VISION: r"\bdolby\s*vision\b|\bdolbyvision\b|\bdv\b|\bdvhe\b",
    HDR10_PLUS: r"hdr10\+|hdr10plus|hdr10\s+plus",  # Simplified regex for HDR10+
    HDR: r"(?:\bhdr\b|\bhdr10\b|\bsmpte\s*st\s*2094(?:.*?app\s*4)?|\bst\s*2094\b)",
    # todo
    # "HLG": r"\bhlg\b|\bhybrid\s+log\s+gamma\b",
    # "PQ": r"\bpq\b|\bst\s*2084\b|\bperceptual\s*quantizer\b",
}
