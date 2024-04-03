from pymediainfo import MediaInfo


def get_media_info(file_location=None):
    if not file_location:
        print("No file provided")
        return False
    audio_language = []
    audio_info = {}
    subtitles = []
    video_info = {}
    media_info = MediaInfo.parse(file_location)

    for track in media_info.tracks:
        if track.track_type == "Video":
            video_info["bit_rate"] = track.bit_rate
            video_info["frame_rate"] = track.frame_rate
            video_info["format"] = track.format
            video_info["height"] = track.height
            video_info["width"] = track.width
        elif track.track_type == "Audio":
            track_id = f"track_{str(track.track_id)}"
            audio_info[track_id] = {}  # Initialize dictionary for this track_id
            audio_info[track_id]["language"] = track.language
            audio_info[track_id]["channels"] = track.channel_s
            audio_info[track_id]["format"] = track.format
            audio_language.append(track.language)
        elif track.track_type == "Text":
            subtitles.append(track.language)
    return (audio_language, subtitles, video_info, audio_info)

def format_media_info(mediainfo=None):
    if not mediainfo:
        print("Error: No mediainfo provided")
        return None
    
    audio_language = mediainfo["audio_language(s)"]
    audio_info = mediainfo["audio_info"]
    subtitles = mediainfo["subtitle(s)"]
    video_info = mediainfo["video_info"]

    return(audio_language, audio_info, subtitles, video_info)

