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
#   3. Ask the LLM for a short narration script, synthesize it with
#      gTTS (free, no API key), and size each scene's on-screen time
#      to the narration's actual length so voice + visuals line up.
#   4. Stitch the scenes into a short MP4 with moviepy, adding a
#      slow Ken-Burns style zoom + crossfade, with the narration
#      audio track attached.
#
# Needs `moviepy` + `gTTS` (requirements.txt) + the `ffmpeg` system
# binary (packages.txt) — all must be present for this to work on
# Streamlit Community Cloud.
# ============================================

import io
import os
import tempfile
import time
import urllib.parse

import requests
from PIL import Image

SCENE_COUNT = 4
MIN_SECONDS_PER_SCENE = 2.0
MAX_SECONDS_PER_SCENE = 5.0
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


def _generate_narration_script(client, prompt: str) -> str:
    """Short (~8-12s spoken) narration line for the video."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Write ONE short, energetic narration line (18-28 words) for a "
                        "short video about the user's topic. Plain spoken sentence(s) only — "
                        "no stage directions, no quotes, no markdown."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        return resp.choices[0].message.content.strip().strip('"')
    except Exception:
        return prompt


def _synthesize_narration(text: str, out_path: str):
    """Free TTS via gTTS — needs internet access at runtime (no API key)."""
    from gtts import gTTS
    gTTS(text=text, lang="en").save(out_path)


def _fetch_scene_image(prompt: str, attempts: int = 3) -> Image.Image:
    encoded = urllib.parse.quote(prompt.strip())
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=768&height=768&nologo=true&model=flux"
    )
    last_error = None
    for attempt in range(attempts):
        try:
            # Pollinations can be slow under load — 90s timeout + retries
            # instead of failing the whole video on one slow scene.
            resp = requests.get(url, timeout=90)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            last_error = e
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))  # 2s, 4s backoff before retrying
    raise last_error


def generate_video(client, prompt: str, progress_callback=None) -> bytes:
    """
    Generates a short MP4 with AI voice narration from a text prompt.
    Returns raw MP4 bytes. Raises on failure (caller should catch and
    show st.error).
    """
    from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, vfx

    scenes = _expand_prompt_to_scenes(client, prompt)

    # ---- narration: script -> speech, BEFORE building clips, so we know
    # how long the video needs to be to match the voice ----
    audio_path = None
    audio_clip = None
    try:
        narration_text = _generate_narration_script(client, prompt)
        fd, audio_path = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        if progress_callback:
            progress_callback(0, len(scenes) + 1, "Recording narration...")
        _synthesize_narration(narration_text, audio_path)
        audio_clip = AudioFileClip(audio_path)
    except Exception:
        # Narration is a nice-to-have — silently fall back to a silent
        # video if TTS/network fails, rather than failing the whole thing.
        audio_clip = None

    seconds_per_scene = MIN_SECONDS_PER_SCENE
    if audio_clip is not None:
        seconds_per_scene = max(
            MIN_SECONDS_PER_SCENE,
            min(MAX_SECONDS_PER_SCENE, audio_clip.duration / SCENE_COUNT),
        )

    clips = []
    tmp_paths = []
    failed_scenes = []
    try:
        for i, scene_prompt in enumerate(scenes):
            if progress_callback:
                progress_callback(i + 1, len(scenes) + 1, scene_prompt)

            try:
                img = _fetch_scene_image(scene_prompt)
            except Exception:
                # One slow/failed scene shouldn't kill the whole video —
                # skip it and keep going with whatever scenes did work.
                failed_scenes.append(scene_prompt)
                continue

            img = img.resize(VIDEO_SIZE)

            fd, path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            img.save(path, "JPEG", quality=90)
            tmp_paths.append(path)

            is_first_clip = len(clips) == 0
            clip = (
                ImageClip(path)
                .with_duration(seconds_per_scene)
                .with_effects([vfx.Resize(lambda t: 1 + 0.06 * t)])  # slow zoom-in
                .with_effects([] if is_first_clip else [vfx.CrossFadeIn(0.5)])
            )
            clips.append(clip)

        if not clips:
            raise RuntimeError(
                "All scenes failed to generate (image service was unreachable/slow). Try again."
            )

        final = concatenate_videoclips(clips, method="compose", padding=-0.5)

        if audio_clip is not None:
            # Match audio length to the final video length: trim if the
            # voiceover runs long, loop silence otherwise if it's short.
            if audio_clip.duration > final.duration:
                audio_clip = audio_clip.subclipped(0, final.duration)
            final = final.with_audio(audio_clip)

        out_fd, out_path = tempfile.mkstemp(suffix=".mp4")
        os.close(out_fd)
        final.write_videofile(
            out_path, fps=24, codec="libx264",
            audio=audio_clip is not None, audio_codec="aac",
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
        if audio_clip is not None:
            try:
                audio_clip.close()
            except Exception:
                pass
        if audio_path:
            try:
                os.remove(audio_path)
            except OSError:
                pass
