from pymediainfo import MediaInfo


def get_media_info(file_location=None):
    if not file_location:
        print("No file provided")
        return False
    audio_language = []
    audio_info = {}
    subtitles = []
    video_info = {}
    hdr_types = set()

    media_info = MediaInfo.parse(file_location)

    for track in media_info.tracks:
        if track.track_type == "Video":
            video_info["bit_rate"] = track.bit_rate
            video_info["frame_rate"] = track.frame_rate
            video_info["format"] = track.format
            video_info["height"] = track.height
            video_info["width"] = track.width

            if hasattr(track, "hdr_format_commercial") and track.hdr_format_commercial:
                hdr_commercial = str(track.hdr_format_commercial).lower()
                if "dolby vision" in hdr_commercial:
                    hdr_types.add("Dolby Vision")
                if "hdr10+" in hdr_commercial:
                    hdr_types.add("HDR10+")
                elif "hdr10" in hdr_commercial:
                    hdr_types.add("HDR10")

            elif (
                hasattr(track, "transfer_characteristics")
                and track.transfer_characteristics == "PQ"
            ):
                if (
                    hasattr(track, "hdr_format")
                    and track.hdr_format
                    and "2094" in str(track.hdr_format)
                ):
                    hdr_types.add("HDR10+")
                elif (
                    hasattr(track, "maximum_content_light_level")
                    and track.maximum_content_light_level
                ):
                    hdr_types.add("HDR10")
                else:
                    hdr_types.add("HDR")

        elif track.track_type == "Audio":
            track_id = f"track_{str(track.track_id)}"
            audio_info[track_id] = {}
            audio_info[track_id]["language"] = track.language
            audio_info[track_id]["channels"] = track.channel_s
            audio_info[track_id]["format"] = track.format
            audio_language.append(track.language)
        elif track.track_type == "Text":
            subtitles.append(track.language)

    if not hdr_types:
        hdr_types.add("SDR")

    return {
        "audio_language(s)": audio_language,
        "subtitle(s)": subtitles,
        "video_info": video_info,
        "audio_info": audio_info,
        "hdr_type": ", ".join(sorted(hdr_types)),
    }
