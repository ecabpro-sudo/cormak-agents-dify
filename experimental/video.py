"""Not shipped: the MCP video backend returned a refunded provider 404.
Retest a completed generation before adding video tools to a release.
"""
from cormak import CormakError, identifier
from operations import paid_request, select, text, request_id
VIDEO_DURATIONS = {"4": 4, "6": 6, "8": 8}


def start_video(client, params):
    operation_id = paid_request(params)
    resolution = select(params, "resolution", ("720p", "1080p", "4k"), "720p")
    duration = VIDEO_DURATIONS[select(params, "duration", VIDEO_DURATIONS, "8")]
    if resolution != "720p" and duration != 8:
        raise CormakError("invalid_duration_for_resolution")
    return client.mcp(
        "generate_video", request_id=operation_id, confirm_spend=True,
        prompt=text(params, "prompt", 2000), duration_seconds=duration, resolution=resolution,
        aspect_ratio=select(params, "aspect_ratio", ("16:9", "9:16"), "16:9"),
        audio_style=select(params, "audio_style", ("auto", "music", "dialogue", "effects"), "auto"),
    )


def video_status(client, params):
    value = client.mcp("get_generation", request_id=request_id(params))
    if value.get("tool") == "generate_video" and value.get("status") == "complete":
        backend_id = identifier(value.get("backend_request_id"))
        value["video"] = client.mcp("get_video_status", request_id=backend_id)
    return value
