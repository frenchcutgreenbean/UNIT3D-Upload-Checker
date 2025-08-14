from pymediainfo import MediaInfo


def detect_hdr_types(track):
    hdr_types = set()
    hdr_attrs = [
        "hdr_format",
        "hdr_format_commercial",
        "hdr_format_compatibility",
        "hdr_format_profile",
        "hdr_format_settings",
        "hdr_format_version",
        "other_hdr_format",
    ]
    hdr_map = {
        "dolby vision": "Dolby Vision",
        "hdr10+": "HDR10+",
        "hdr10": "HDR10",
        "hlg": "HLG",
    }
    for attr in hdr_attrs:
        value = getattr(track, attr, None)
        if value:
            if isinstance(value, list):
                value = " ".join(str(v).lower() for v in value)
            else:
                value = str(value).lower()
            for key, label in hdr_map.items():
                if key in value:
                    hdr_types.add(label)
    if not hdr_types:
        hdr_types.add("SDR")
    return ", ".join(sorted(hdr_types))


def get_media_info(file_location=None):
    if not file_location:
        print("No file provided")
        return False
    audio_language = []
    audio_info = {}
    subtitles = []
    video_info = {}
    runtime = None
    hdr_type = "SDR"

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
            hdr_type = detect_hdr_types(track)
        elif track.track_type == "Audio":
            track_id = f"track_{str(track.track_id)}"
            audio_info[track_id] = {}
            audio_info[track_id]["language"] = track.language
            audio_info[track_id]["channels"] = track.channel_s
            audio_info[track_id]["format"] = track.format
            audio_language.append(track.language)
        elif track.track_type == "Text":
            subtitles.append(track.language)

    return {
        "audio_language(s)": audio_language,
        "subtitle(s)": subtitles,
        "video_info": video_info,
        "audio_info": audio_info,
        "hdr_type": hdr_type,
        "runtime": runtime,
    }
