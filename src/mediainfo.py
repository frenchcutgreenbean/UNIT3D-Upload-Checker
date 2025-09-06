from pymediainfo import MediaInfo
import re
from src.utils.logger import logger


def detect_hdr_formats(track):
    from src.utils.hdr_formats import SDR, HDR, HDR10_PLUS, DOLBY_VISION, DOLBY_VISION_HDR, DOLBY_VISION_HDR10P
    from src.utils.hdr_formats import HDR_REGEXES
    
    hdr_formats = set()
    hdr_attrs = [
        "hdr_format",
        "hdr_format_commercial",
        "hdr_format_compatibility",
        "hdr_format_profile",
        "hdr_format_settings",
        "hdr_format_version",
        "other_hdr_format",
    ]

    # Combine all attribute values into a single string
    combined_value = ""
    for attr in hdr_attrs:
        value = getattr(track, attr, None)
        if value:
            if isinstance(value, list):
                combined_value += " " + " ".join(str(v) for v in value)
            else:
                combined_value += " " + str(value)

    combined_value = combined_value.lower()

    # Check for Dolby Vision
    if re.search(HDR_REGEXES[DOLBY_VISION], combined_value):
        hdr_formats.add(DOLBY_VISION)

    # Check for HDR10+
    has_hdr10_plus = re.search(HDR_REGEXES[HDR10_PLUS], combined_value)
    
    # Check for HDR (including HDR10)
    has_hdr = re.search(HDR_REGEXES[HDR], combined_value)
    
    # Check for combined formats - DV + HDR10+
    if DOLBY_VISION in hdr_formats and has_hdr10_plus:
        hdr_formats.remove(DOLBY_VISION)
        hdr_formats.add(DOLBY_VISION_HDR10P)
    # Check for combined formats - DV + HDR
    elif DOLBY_VISION in hdr_formats and has_hdr:
        hdr_formats.remove(DOLBY_VISION)
        hdr_formats.add(DOLBY_VISION_HDR)
    # Add HDR10+ if detected (and not part of a combination)
    elif has_hdr10_plus:
        hdr_formats.add(HDR10_PLUS)
    # Add HDR if detected (and not part of a combination)
    elif has_hdr:
        hdr_formats.add(HDR)

    # If no HDR detected, it's SDR
    if not hdr_formats:
        hdr_formats.add(SDR)

    return ", ".join(sorted(hdr_formats))


def check_has_english_content(media_info: dict) -> bool:
    """Check if media info contains English audio or subtitles."""
    if not media_info:
        return False
        
    audio_languages = media_info.get("audio_language(s)", [])
    subtitles = media_info.get("subtitle(s)", [])

    # Ensure they are lists
    if isinstance(audio_languages, str):
        audio_languages = [audio_languages]
    if isinstance(subtitles, str):
        subtitles = [subtitles]

    has_english_audio = any(
        lang and lang.lower().startswith("en") for lang in audio_languages if lang is not None
    )
    has_english_subs = any(
        sub and sub.lower().startswith("en") for sub in subtitles if sub is not None
    )

    return has_english_audio or has_english_subs

def get_media_info(file_location=None):
    if not file_location:
        logger.error("No file provided")
        return False
    audio_language = []
    audio_info = {}
    subtitles = []
    video_info = {}
    runtime = None
    hdr_format = "SDR"

    media_info = MediaInfo.parse(file_location)

    for track in media_info.tracks:
        if track.track_type == "General":
            if hasattr(track, "duration") and track.duration:
                runtime = int(track.duration / 60000)  # Convert ms to minutes
        if track.track_type == "Video":
            video_info["bit_rate"] = track.bit_rate
            video_info["frame_rate"] = track.frame_rate
            video_info["format"] = track.format
            video_info["height"] = track.height
            video_info["width"] = track.width
            hdr_format = detect_hdr_formats(track)
        elif track.track_type == "Audio":
            track_id = f"track_{str(track.track_id)}"
            audio_info[track_id] = {}
            audio_info[track_id]["language"] = track.language
            audio_info[track_id]["channels"] = track.channel_s
            audio_info[track_id]["format"] = track.format
            audio_language.append(track.language)
        elif track.track_type == "Text":
            subtitles.append(track.language)

    media_info = {
        "audio_language(s)": audio_language,
        "subtitle(s)": subtitles,
        "video_info": video_info,
        "audio_info": audio_info,
        "hdr_format": hdr_format,
        "runtime": runtime,
    }
    
    # Add English content check directly to the media_info
    media_info["has_english_content"] = check_has_english_content(media_info)
    
    return media_info
