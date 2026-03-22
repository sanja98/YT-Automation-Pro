import os, json, requests, random, textwrap, subprocess, time, shutil
from PIL import Image, ImageDraw, ImageFont

# 🔥 Pillow Fix for MoviePy
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

import moviepy.editor as mp

def draw_overlay(text, timer=None, is_answer=False, hint=None):
    W, H = (1080, 1920)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    f_p = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    
    # 🎨 Colors & Fonts
    font_q = ImageFont.truetype(f_p, 60) # Chota kiya taaki fit aaye
    font_t = ImageFont.truetype(f_p, 250)
    font_h = ImageFont.truetype(f_p, 45)

    # ⬛ Semi-transparent Box (Centered)
    draw.rectangle([80, 500, 1000, 1400], fill=(0, 0, 0, 190))
    
    y = 550
    display_text = f"ANSWER:\n{text}" if is_answer else text
    # Width 25 rakha hai taaki lines choti rahein
    lines = textwrap.wrap(display_text, width=25) 
    
    for line in lines:
        l, t, r, b = draw.textbbox((0, 0), line, font=font_q)
        draw.text(((W-(r-l))/2, y), line, fill=(255, 255, 255), font=font_q)
        y += (b-t) + 40

    # ⏲️ Timer Logic (Bottom par rakha hai overlap hatane ke liye)
    if timer and not is_answer:
        l, t, r, b = draw.textbbox((0, 0), str(timer), font=font_t)
        draw.text(((W-(r-l))/2, 1050), str(timer), fill=(255, 50, 50, 150), font=font_t)

    if hint and not is_answer:
        l, t, r, b = draw.textbbox((0, 0), f"Hint: {hint}", font=font_h)
        draw.text(((W-(r-l))/2, 1320), f"Hint: {hint}", fill=(255, 255, 100), font=font_h)

    img.save("frame.png")
    return "frame.png"
def main():
    with open('config.json', 'r') as f: cfg = json.load(f)
    with open('topics.txt', 'r') as f: topics = [t.strip() for t in f.readlines() if t.strip()]
    
    # Processed logic
    done = []
    if os.path.exists('processed.txt'):
        with open('processed.txt', 'r') as f: done = f.read().splitlines()
    
    topic = next((t for t in topics if t not in done), None)
    if not topic: return

    # 1. Get Riddle from Gemini
    prompt = cfg['prompt_template'].format(topic=topic)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={KEYS[0]}"
    res = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}).json()
    raw = res['candidates'][0]['content']['parts'][0]['text'].replace("```json", "").replace("```", "").strip()
    data = json.loads(raw)

    # 2. Get Video from Pexels
    bg_video = get_pexels_video(cfg['pexels_query'])
    if not bg_video: return

    # 3. Create Audio (Question + Answer)
    q_text = f"I have a riddle for you. {data['question']}"
    subprocess.run(['edge-tts', '--voice', 'en-IN-NeerjaNeural', '--text', q_text, '--write-media', 'q.mp3'])
    a_text = f"The answer is {data['answer']}"
    subprocess.run(['edge-tts', '--voice', 'en-IN-NeerjaNeural', '--text', a_text, '--write-media', 'a.mp3'])

    # 4. Composite Video
    bg_clip = mp.VideoFileClip(bg_video).resize(height=1920).crop(x1=0, y1=0, x2=1080, y2=1920)
    q_aud = mp.AudioFileClip("q.mp3")
    a_aud = mp.AudioFileClip("a.mp3")

    clips = []
    # Q Section
    clips.append(mp.ImageClip(draw_overlay(data['question'], hint=data['hint'])).set_duration(q_aud.duration).set_audio(q_aud))
    # Timer Section
    for i in range(cfg['timer_seconds'], 0, -1):
        clips.append(mp.ImageClip(draw_overlay(data['question'], timer=i, hint=data['hint'])).set_duration(1))
    # Answer Section
    clips.append(mp.ImageClip(draw_overlay(data['answer'], is_answer=True)).set_duration(a_aud.duration + 2).set_audio(a_aud))

    final_overlay = mp.concatenate_videoclips(clips, method="compose")
    # Loop background video to match overlay duration
    final_bg = bg_clip.loop(duration=final_overlay.duration)
    
    final_video = mp.CompositeVideoClip([final_bg, final_overlay])
    final_video.write_videofile("riddle.mp4", fps=24, codec="libx264", audio_codec="aac", logger=None)

    # 5. Send to Telegram
    with open("riddle.mp4", 'rb') as f:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo", data={'chat_id': USER_ID}, files={'video': f})
    
    with open('processed.txt', 'a') as f: f.write(topic + "\n")
    print("🎬 Video Done!")

if __name__ == "__main__":
    main()
