import os, json, requests, random, textwrap, subprocess, time, shutil
from PIL import Image, ImageDraw, ImageFont
import moviepy.editor as mp

# 🔥 Pillow Fix
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# 🔐 Credentials
KEYS = [os.environ.get('KEY1')]
PEXELS_KEY = os.environ.get('PEXELS_API_KEY')
TG_TOKEN = os.environ.get('TG_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_pexels_video(query):
    headers = {'Authorization': PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=15&orientation=portrait"
    try:
        r = requests.get(url, headers=headers).json()
        video_data = random.choice(r['videos'])['video_files']
        video_url = next(v['link'] for v in video_data if v['width'] >= 720)
        with requests.get(video_url, stream=True) as v:
            with open("bg.mp4", 'wb') as f:
                for chunk in v.iter_content(chunk_size=1024): f.write(chunk)
        return "bg.mp4"
    except: return None

def draw_overlay(text, timer=None, is_answer=False, hint=None):
    W, H = (1080, 1920)
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    f_p = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    font_q = ImageFont.truetype(f_p, 55)  
    font_t = ImageFont.truetype(f_p, 250) 
    font_h = ImageFont.truetype(f_p, 42)  

    draw.rectangle([70, 420, 1010, 1550], fill=(0, 0, 0, 215))
    y = 480
    display_text = f"ANSWER:\n{text}" if is_answer else text
    lines = textwrap.wrap(display_text, width=24) 
    for line in lines:
        l, t, r, b = draw.textbbox((0, 0), line, font=font_q)
        draw.text(((W-(r-l))/2, y), line, fill=(255, 255, 255), font=font_q)
        y += (b-t) + 40

    if timer and not is_answer:
        l, t, r, b = draw.textbbox((0, 0), str(timer), font=font_t)
        draw.text(((W-(r-l))/2, 1000), str(timer), fill=(255, 60, 60, 180), font=font_t)

    if hint and not is_answer:
        hint_lines = textwrap.wrap(f"Hint: {hint}", width=35)
        hy = 1380 
        for h_line in hint_lines:
            l, t, r, b = draw.textbbox((0, 0), h_line, font=font_h)
            draw.text(((W-(r-l))/2, hy), h_line, fill=(255, 255, 120), font=font_h)
            hy += (b-t) + 20
    img.save("frame.png")
    return "frame.png"

def main():
    with open('config.json', 'r') as f: cfg = json.load(f)
    with open('topics.txt', 'r') as f: topics = [t.strip() for t in f.readlines() if t.strip()]
    
    done = []
    if os.path.exists('processed.txt'):
        with open('processed.txt', 'r') as f: done = f.read().splitlines()
    
    topic = next((t for t in topics if t not in done), None)
    if not topic: return

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={KEYS[0]}"
    payload = {"contents": [{"parts": [{"text": cfg['prompt_template'].format(topic=topic)}]}],
               "safetySettings": [{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]}
    
    try:
        res = requests.post(url, json=payload).json()
        raw_text = res['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(raw_text.replace("```json", "").replace("```", "").strip())
    except: return

    bg_video = get_pexels_video(cfg['pexels_query'])
    if not bg_video: return

    subprocess.run(['edge-tts', '--voice', 'en-IN-NeerjaNeural', '--text', f"Riddle: {data['question']}", '--write-media', 'q.mp3'])
    subprocess.run(['edge-tts', '--voice', 'en-IN-NeerjaNeural', '--text', f"The answer is {data['answer']}", '--write-media', 'a.mp3'])

    # 🔔 Timer Sound (Tick-Tick) Generate
    subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=f=800:d=0.1', 'tick.mp3'])
    tick_aud = mp.AudioFileClip("tick.mp3")

    bg_clip = mp.VideoFileClip(bg_video).resize(height=1920).crop(x1=0, y1=0, x2=1080, y2=1920)
    q_aud, a_aud = mp.AudioFileClip("q.mp3"), mp.AudioFileClip("a.mp3")

    clips = [mp.ImageClip(draw_overlay(data['question'], hint=data['hint'])).set_duration(q_aud.duration).set_audio(q_aud)]
    for i in range(cfg.get('timer_seconds', 5), 0, -1):
        clips.append(mp.ImageClip(draw_overlay(data['question'], timer=i, hint=data['hint'])).set_duration(1).set_audio(tick_aud))
    clips.append(mp.ImageClip(draw_overlay(data['answer'], is_answer=True)).set_duration(a_aud.duration + 2).set_audio(a_aud))

    final_video = mp.CompositeVideoClip([bg_clip.loop(duration=sum(c.duration for c in clips)), mp.concatenate_videoclips(clips, method="compose")])
    final_video.write_videofile("riddle.mp4", fps=24, codec="libx264", audio_codec="aac", logger=None)

    # Telegram Upload
    with open("riddle.mp4", 'rb') as f:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendVideo", data={'chat_id': USER_ID}, files={'video': f})
    
    with open('processed.txt', 'a') as f: f.write(topic + "\n")
    print("✅ Timer Sound added and Video Sent!")

if __name__ == "__main__":
    main()
