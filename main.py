from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.core.window import Window
from kivy.clock import mainthread
from plyer import audio, storagepath
import threading
import requests
import json
import urllib.parse
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth, CacheFileHandler
import webbrowser

# Force Dark Mode UI
Window.clearcolor = (0.07, 0.07, 0.07, 1)

# ==========================================
# 1. API KEYS & SYSTEM PROMPT
# ==========================================
SECURE_GROQ_KEY = "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"
SPOTIFY_ID = "71800f671f3244bd8a89f00b08e55892"
SPOTIFY_SECRET = "fe1b9000372445308d9877478843568c"

SYSTEM_PROMPT = """
You are a Kia Sonet Infotainment AI. Respond ONLY in valid JSON format exactly like this:
{"command": "COMMAND_NAME", "parameter": "detail", "reason": "brief reason"}
Use commands: MUSIC_PLAY, MUSIC_PAUSE, MUSIC_SKIP, NAVIGATE.
"""

class KiaCoPilotApp(App):
    def build(self):
        self.is_recording = False
        
        # Determine safe Android path for audio file
        try:
            self.audio_file = os.path.join(storagepath.get_application_dir(), 'cmd.wav')
            self.cache_path = os.path.join(storagepath.get_application_dir(), '.spotify_cache')
        except:
            self.audio_file = 'cmd.wav'
            self.cache_path = '.spotify_cache'

        # Main Layout
        layout = BoxLayout(orientation='vertical', padding=20, spacing=20)

        # Header
        header = Label(text="KIA CO-PILOT", font_size='30sp', bold=True, color=(0, 0.9, 1, 1), size_hint_y=0.1)
        layout.add_widget(header)

        # Telemetry Log
        self.scroll = ScrollView(size_hint_y=0.7)
        self.terminal = Label(text="[SYS] Booting systems...\n", markup=True, halign="left", valign="top", font_name="RobotoMono-Regular")
        self.terminal.bind(size=self.terminal.setter('text_size'))
        self.scroll.add_widget(self.terminal)
        layout.add_widget(self.scroll)

        # Mic Button
        self.mic_btn = Button(text="🎤 TAP TO SPEAK", font_size='20sp', bold=True, background_color=(0.1, 0.5, 0.8, 1), size_hint_y=0.2)
        self.mic_btn.bind(on_press=self.toggle_mic)
        layout.add_widget(self.mic_btn)

        # Boot Spotify in background
        threading.Thread(target=self.boot_spotify).start()

        return layout

    @mainthread
    def log_msg(self, msg, color="00FF00"):
        self.terminal.text += f"[color={color}]{msg}[/color]\n"
        self.scroll.scroll_y = 0  # Auto-scroll to bottom

    def boot_spotify(self):
        try:
            cache_handler = CacheFileHandler(cache_path=self.cache_path)
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_ID,
                client_secret=SPOTIFY_SECRET,
                redirect_uri="https://google.com/callback",
                scope="user-modify-playback-state user-read-playback-state playlist-read-private",
                open_browser=False,
                cache_handler=cache_handler 
            ))
            self.log_msg("[SYS] Spotify Cloud Connected", "00FF00")
            self.log_msg("[SYS] System Ready.", "00FFFF")
        except Exception as e:
            self.log_msg(f"[ERR] Spotify Boot: {str(e)}", "FF0000")

    def toggle_mic(self, instance):
        if not self.is_recording:
            try:
                audio.file_path = self.audio_file
                audio.start()
                self.mic_btn.text = "🛑 STOP & PROCESS"
                self.mic_btn.background_color = (0.8, 0.1, 0.1, 1)
                self.log_msg("[SYS] Listening...", "FFFF00")
                self.is_recording = True
            except Exception as e:
                self.log_msg(f"[ERR] Mic failed: {str(e)}", "FF0000")
        else:
            try:
                audio.stop()
                self.mic_btn.text = "🎤 TAP TO SPEAK"
                self.mic_btn.background_color = (0.1, 0.5, 0.8, 1)
                self.is_recording = False
                self.log_msg("[SYS] Sending to Groq...", "FFFF00")
                threading.Thread(target=self.process_audio).start()
            except Exception as e:
                self.log_msg(f"[ERR] Stop failed: {str(e)}", "FF0000")

    def process_audio(self):
        try:
            # 1. WHISPER AUDIO TRANSCRIPTION
            headers_audio = {"Authorization": f"Bearer {SECURE_GROQ_KEY}"}
            with open(self.audio_file, "rb") as f:
                files = {"file": ("cmd.wav", f)}
                data = {"model": "whisper-large-v3-turbo"}
                res = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers=headers_audio, files=files, data=data)
            
            user_text = res.json().get("text", "")
            if not user_text:
                self.log_msg("[ERR] Could not hear anything.", "FF0000")
                return
            self.log_msg(f"[USER] '{user_text}'", "FFFFFF")

            # 2. LLAMA INTENT PARSING
            headers_chat = {"Authorization": f"Bearer {SECURE_GROQ_KEY}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_text}],
                "response_format": {"type": "json_object"}
            }
            chat_res = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers_chat, json=payload)
            ai_decision = json.loads(chat_res.json()["choices"][0]["message"]["content"])
            
            command = ai_decision.get("command", "UNKNOWN")
            parameter = ai_decision.get("parameter", "None")
            self.log_msg(f"[AI INTENT] {command} -> {parameter}", "00FFFF")

            # 3. EXECUTION
            if command == "MUSIC_PLAY":
                target = parameter if parameter != "None" else "my music"
                result = self.sp.search(q=target, limit=1, type='track')
                if result['tracks']['items']:
                    track_uri = result['tracks']['items'][0]['uri']
                    self.sp.start_playback(device_id=self.sp.devices()['devices'][0]['id'], uris=[track_uri])
                    self.log_msg(f"[CLOUD] Playing {target}!", "00FF00")
            elif command in ["NAVIGATE", "NAVGATE", "NAVIGATION"]:
                self.log_msg(f"[ANDROID] Routing to {parameter}...", "FFFF00")
                webbrowser.open(f"google.navigation:q={urllib.parse.quote(parameter)}")

        except Exception as e:
            self.log_msg(f"[ERR] Engine: {str(e)}", "FF0000")

if __name__ == '__main__':
    KiaCoPilotApp().run()
