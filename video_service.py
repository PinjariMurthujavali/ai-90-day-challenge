# ============================================
# video_service.py  (NEW FILE)
# "AI video" generation without a paid video-gen API.
#
# How it works (free-tier friendly):
#   1. Ask the Groq LLM to expand one prompt into N short scene
#      descriptions (keeps the video visually coherent instead of
#      4 random unrelated images).
#   2. Generate one image per scene with the same free Pollinations
#      image API the app already uses for "🎨 Image".
#   3. Stitch the scenes into a short MP4 with moviepy, adding a
#      slow Ken-Burns style zoom + crossfade so it reads as a real
#      video and not a slideshow.
#
# Needs `moviepy` (requirements.txt) + the `ffmpeg` system binary
# (packages.txt) — both must be present for this to work on
# Streamlit Community Cloud.
# ============================================

import io
import os
import tempfile
import urllib.parse

import requests
from PIL import Image

SCENE_COUNT = 4
SECONDS_PER_SCENE = 2.5
VIDEO_SIZE = (640, 640)  # square, keeps file size small


def _expand_prompt_to_scenes(client, prompt: str) -> list[str]:
    """Turn one idea into N short, visually-coherent scene prompts."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Break the user's video idea into exactly {SCENE_COUNT} short, "
                        "vivid image-generation prompts that form a coherent visual sequence "
                        "(like storyboard frames). Reply with ONLY the prompts, one per line, "
                        "no numbering, no extra text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        lines = [l.strip("-• \t") for l in resp.choices[0].message.content.split("\n") if l.strip()]
        scenes = [l for l in lines if l][:SCENE_COUNT]
        if len(scenes) < SCENE_COUNT:
            scenes += [prompt] * (SCENE_COUNT - len(scenes))
        return scenes
    except Exception:
        # fall back to using the same prompt for every scene
        return [prompt] * SCENE_COUNT


def _fetch_scene_image(prompt: str) -> Image.Image:
    encoded = urllib.parse.quote(prompt.strip())
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=768&height=768&nologo=true&model=flux"
    )
    resp = requests.get(url, timeout=45)
    resp.raise_for_status()
    return Image.open(io.BytesIO(resp.content)).convert("RGB")


def generate_video(client, prompt: str, progress_callback=None) -> bytes:
    """
    Generates a short MP4 (≈ SCENE_COUNT * SECONDS_PER_SCENE seconds) from a
    text prompt. Returns raw MP4 bytes. Raises on failure (caller should
    catch and show st.error).
    """
    from moviepy import ImageClip, concatenate_videoclips, vfx

    scenes = _expand_prompt_to_scenes(client, prompt)

    clips = []
    tmp_paths = []
    try:
        for i, scene_prompt in enumerate(scenes):
            if progress_callback:
                progress_callback(i, len(scenes), scene_prompt)

            img = _fetch_scene_image(scene_prompt)
            img = img.resize(VIDEO_SIZE)

            fd, path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            img.save(path, "JPEG", quality=90)
            tmp_paths.append(path)

            clip = (
                ImageClip(path)
                .with_duration(SECONDS_PER_SCENE)
                .with_effects([vfx.Resize(lambda t: 1 + 0.06 * t)])  # slow zoom-in
                .with_effects([vfx.CrossFadeIn(0.5)] if i > 0 else [])
            )
            clips.append(clip)

        final = concatenate_videoclips(clips, method="compose", padding=-0.5)

        out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(out_fd)
        final.write_videofile(
            out_path, fps=24, codec="libx264", audio=False,
            preset="ultrafast", logger=None,
        )

        with open(out_path, "rb") as f:
            video_bytes = f.read()

        os.remove(out_path)
        return video_bytes
    finally:
        for p in tmp_paths:
            try:
                os.remove(p)
            except OSError:
                pass
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
