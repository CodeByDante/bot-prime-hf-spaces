import asyncio
import os
import subprocess
import time
from config import HAS_FFMPEG

async def mix_videos_side_by_side(video1_path, video2_path, audio_mode='mix'):
    """
    Mezcla dos videos (o imagenes) lado a lado (Side-by-Side).
    audio_mode: 'v1', 'v2', 'mix', 'none'
    """
    if not HAS_FFMPEG:
        return None

    output_path = f"downloads/mixed_{int(time.time())}.mp4"
    
    try:
        # 1. Analizar Inputs para ver si son Imagenes
        def is_image(path):
            ext = os.path.splitext(path)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']

        img1 = is_image(video1_path)
        img2 = is_image(video2_path)
        
        # Build Inputs
        cmd = ["ffmpeg", "-y"]
        
        # Input Duration Logic
        t_duration = "60"
        if img1 and img2: t_duration = "10" # Default for Img+Img

        # Input 1
        if img1: cmd.extend(["-loop", "1", "-framerate", "30", "-t", t_duration]) # Limit infinite loop just in case, but -shortest controls it
        cmd.extend(["-i", video1_path])
        
        # Input 2
        if img2: cmd.extend(["-loop", "1", "-framerate", "30", "-t", t_duration])
        cmd.extend(["-i", video2_path])
        
        # Si ambos son IMAGENES, ya no retornamos None.
        if img1 and img2:
            pass # Valid config now

        # 2. Filter Complex
        target_h = 720
        
        # [0:v]scale=-2:720[left];[1:v]scale=-2:720[right];[left][right]hstack[v]
        filter_complex = f"[0:v]scale=-2:{target_h}[left];[1:v]scale=-2:{target_h}[right];[left][right]hstack=inputs=2[v]"
        
        if img1 and img2:
            # Change output to JPG
            output_path = output_path.replace(".mp4", ".jpg")
            # Clear previous input args that might have been added (not easy with extend, so let's adjust logic above or overwrite)
            
            # RE-BUILD Command for Image-Only Mode (Cleaner than patching)
            cmd = ["ffmpeg", "-y", "-i", video1_path, "-i", video2_path]
            
            # Simple Filter
            # ADDED: -map "[v]" because filter_complex ends with [v] label.
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-vframes", "1", "-q:v", "2", output_path])
            
            print(f"🎬 Image Collage Cmd: {' '.join(cmd)}")
            process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            _, stderr = await process.communicate()
            
            if process.returncode != 0:
                 print(f"❌ Mixer Image Error: {stderr.decode('utf-8', errors='ignore')}")
                 return None
            return output_path

        # AUDIO LOGIC (Only for Video Output)
        
        # Handle cases where one is image (no audio stream)
        # If img1, stream 0 has no audio.
        
        final_audio_fc = ""
        has_audio_out = False
        
        if audio_mode == 'v1':
            if not img1:
                cmd.extend(["-filter_complex", filter_complex])
                cmd.extend(["-map", "[v]", "-map", "0:a?"])
                has_audio_out = True
            else:
                # Video 1 is image, so silence or nothing? Silent audio track.
                fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
                
        elif audio_mode == 'v2':
            if not img2:
                cmd.extend(["-filter_complex", filter_complex])
                cmd.extend(["-map", "[v]", "-map", "1:a?"])
                has_audio_out = True
            else:
                fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
            
        elif audio_mode == 'mix':
            if not img1 and not img2:
                # Both videos -> Mix
                fc_audio = f"{filter_complex};[0:a][1:a]amix=inputs=2:duration=longest[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
            elif not img1 and img2:
                # V1 Audio only (V2 is image)
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
                has_audio_out = True
            elif img1 and not img2:
                # V2 Audio only
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "1:a?"])
                has_audio_out = True
            else:
                # Both images (Image+Image) -> Generate Silence (Mix Mode fallback)
                fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
            
        else: # none
            fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
            cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
            has_audio_out = True
            
        # Codecs Standard
        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p"
        ])
        
        if has_audio_out:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            
        # Shortest is KEY for loop inputs (cuts to the length of the video input)
        cmd.extend(["-shortest", output_path])
        
        # Ejecutar
        print(f"🎬 Video Mixer Cmd: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            print(f"❌ Mixer Error: {stderr.decode('utf-8', errors='ignore')}")
            return None
            
        if os.path.exists(output_path):
            return output_path
            
    except Exception as e:
        print(f"❌ Video Config Error: {e}")

        

async def mix_videos_paper(video1_path, video2_path, text, audio_mode='mix'):
    """
    Creates a 'Paper Mode' meme video:
    - Side-by-side videos.
    - White background with padding.
    - Yellow header box.
    - Centered black text in the header.
    """
    if not HAS_FFMPEG: return None
    output_path = f"downloads/paper_{int(time.time())}.mp4"
    
    try:
        # Check Images
        def is_image(path):
            ext = os.path.splitext(path)[1].lower()
            return ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp']

        img1 = is_image(video1_path)
        img2 = is_image(video2_path)
        
        # Build Inputs
        cmd = ["ffmpeg", "-y"]
        # Input Duration Logic
        t_duration = "60"
        if img1 and img2: t_duration = "10"

        if img1: cmd.extend(["-loop", "1", "-framerate", "30", "-t", t_duration])
        cmd.extend(["-i", video1_path])
        
        if img2: cmd.extend(["-loop", "1", "-framerate", "30", "-t", t_duration])
        cmd.extend(["-i", video2_path])
        
        if img1 and img2: pass

        # Layout Config
        target_h = 720
        pad_top = 150 # Space for text
        pad_border = 20
        
        # Helper: Wrap Text
        import textwrap
        def wrap_text(text, width=20):
            return textwrap.fill(text, width=width)
            
        wrapped_text = wrap_text(text, width=25) # Adjust width as needed (approx chars per line)
        
        # Escape Text for FFmpeg drawtext
        # Escapes: \ -> \\, : -> \:, ' -> \', " -> \"
        # Newlines need to be escaped for drawtext if passed directly, or usually just work if passed as a string.
        # However, for drawtext, newlines are usually respected if escaped properly or using box mode (but we use simple drawtext).
        # We need to escape special chars FIRST, then handle newlines if needed or rely on textwrap. 
        # Actually, drawtext handles \n.
        
        safe_text = wrapped_text.replace('\\', '\\\\').replace(':', '\\:').replace("'", "").replace('"', '')
        
        # FFMPEG FILTER COMPLEX EXPLANATION
        # ... (omitted comments)

        font_name = "arialbd.ttf" if os.name == 'nt' else "DejaVuSans-Bold.ttf"
        font_cmd = f"fontfile='C\:\\Windows\\Fonts\\{font_name}'" if os.name == 'nt' else ""
        
        filter_complex = (
            f"[0:v]scale=-2:{target_h}[left];[1:v]scale=-2:{target_h}[right];"
            f"[left][right]hstack=inputs=2[stacked];"
            f"[stacked]pad=iw+40:ih+{pad_top}+20:20:{pad_top}:white[padded];"
            f"[padded]drawtext=text='{safe_text}':fontcolor=black:bordercolor=yellow:borderw=3:fontsize=54:x=(w-text_w)/2:y=({pad_top}-text_h)/2:{font_cmd}[v]"
        )
        
        if img1 and img2:
             output_path = output_path.replace(".mp4", ".jpg")
             
             # Re-build for Image Input
             # We need the complex filter with drawtext still
             
             # Inputs
             cmd = ["ffmpeg", "-y", "-i", video1_path, "-i", video2_path]
             
             # Filter is constructed above in 'filter_complex' variable, we can reuse it?
             # Yes, filter_complex string assumes [0:v] and [1:v] which is valid.
             # Only the [v] map output is needed.
             
             cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-vframes", "1", "-q:v", "2", output_path])
             
             print(f"🎬 Paper Image Cmd: {' '.join(cmd)}")
             process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
             _, stderr = await process.communicate()
             
             if os.path.exists(output_path): return output_path
             else: return None

        # Audio Logic
        has_audio_out = False
        
        if audio_mode == 'v1':
            if not img1:
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
                has_audio_out = True
            else:
                fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
                
        elif audio_mode == 'v2':
            if not img2:
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "1:a?"])
                has_audio_out = True
            else:
                fc_audio = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_audio, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
                
        elif audio_mode == 'mix':
            if not img1 and not img2:
                fc_full = f"{filter_complex};[0:a][1:a]amix=inputs=2:duration=longest[a]"
                cmd.extend(["-filter_complex", fc_full, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
            elif not img1 and img2:
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "0:a?"])
                has_audio_out = True
            elif img1 and not img2:
                cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "1:a?"])
                has_audio_out = True
            else:
                # Both images for Paper Mode
                fc_full = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
                cmd.extend(["-filter_complex", fc_full, "-map", "[v]", "-map", "[a]"])
                has_audio_out = True
            
        else: # none
            fc_full = f"{filter_complex};anullsrc=channel_layout=stereo:sample_rate=44100[a]"
            cmd.extend(["-filter_complex", fc_full, "-map", "[v]", "-map", "[a]"])
            has_audio_out = True
            
        cmd.extend([
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p"
        ])
        
        if has_audio_out:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            
        cmd.extend(["-shortest", output_path])
        
        print(f"🎬 Paper Mixer Cmd: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(*cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        _, stderr = await process.communicate()
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return output_path
        else:
            print(f"❌ Paper Error: {stderr.decode('utf-8', errors='ignore')}")
            return None
            
    except Exception as e:
        print(f"❌ Paper Exception: {e}")
        return None

