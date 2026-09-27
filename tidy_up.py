"""
Offline Tidy-Up
---------------
Press Record, talk, press Stop. Your speech is transcribed on this computer
with Whisper, then tidied up by a local Ollama model. Nothing leaves your
machine, so it's fine to use real names.

Run with:  python tidy_up.py
"""

import json
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import scrolledtext

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# ---------------------------------------------------------------- settings ---
# Change these if you like.

OLLAMA_MODEL = "llama3.1:8b"   # any model you've pulled with `ollama pull ...`
WHISPER_MODEL = "small.en"     # "base.en" is faster, "medium.en" is more accurate
SPELLING = "British English"
AUTO_COPY = True               # put the tidied text on the clipboard automatically

# Optional: put names (one per line) in names.txt next to this file.
# They help Whisper spell them correctly and tell the tidy-up to leave them alone.
NAMES_FILE = Path(__file__).with_name("names.txt")

OLLAMA_URL = "http://localhost:11434/api/chat"
SAMPLE_RATE = 16000

# ------------------------------------------------------------------ prompt ---

RULES_TIDY = """\
- Add correct punctuation and capital letters.
- Split the text into sensible paragraphs.
- Remove filler words (um, er, 'you know', 'like' used as filler), false starts and accidental repetition.
- Fix words that were obviously mis-heard by the speech-to-text."""

RULES_IMPROVE = """\
- Improve the sentences so they read clearly and flow well.
- Keep the speaker's own voice, tone and everyday vocabulary. Do not make it
  more formal, flowery or 'AI-sounding' than the original."""

RULES_ALWAYS = """\
- Keep every fact and detail. Do not add new information, opinions or conclusions.
- Do not summarise or shorten the meaning.
- Keep people's names exactly as they are.
- Use {spelling} spelling.
- Reply with ONLY the tidied text: no introduction, no notes, no quotation marks."""


def build_system_prompt(improve, names):
    rules = RULES_TIDY
    if improve:
        rules += "\n" + RULES_IMPROVE
    rules += "\n" + RULES_ALWAYS.format(spelling=SPELLING)
    prompt = ("You tidy up text that someone dictated and that was transcribed "
              "by speech-to-text software. Follow these rules:\n" + rules)
    if names:
        prompt += ("\n\nThese names may appear; spell them exactly like this: "
                   + ", ".join(names) + ".")
    return prompt


def load_names():
    if not NAMES_FILE.exists():
        return []
    lines = NAMES_FILE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def tidy_with_ollama(text, improve, names):
    body = json.dumps({
        "model": OLLAMA_MODEL,
        "stream": False,
        "options": {"temperature": 0.3},
        "messages": [
            {"role": "system", "content": build_system_prompt(improve, names)},
            {"role": "user", "content": text},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(OLLAMA_URL, data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        reply = json.loads(response.read())
    return reply["message"]["content"].strip()


# --------------------------------------------------------------------- app ---

class App:
    def __init__(self, root):
        self.root = root
        self.whisper = None
        self.recording = False
        self.chunks = []
        self.stream = None

        root.title("Offline Tidy-Up")
        root.geometry("1000x600")

        bar = tk.Frame(root)
        bar.pack(fill="x", padx=10, pady=8)
        self.record_btn = tk.Button(bar, text="● Record", width=12, command=self.toggle_record)
        self.record_btn.pack(side="left")
        tk.Button(bar, text="Tidy again", command=self.start_tidy).pack(side="left", padx=5)
        tk.Button(bar, text="Copy tidied text", command=self.copy).pack(side="left")
        tk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=5)
        self.improve = tk.BooleanVar(value=True)
        tk.Checkbutton(bar, text="Improve sentences (not just punctuation)",
                       variable=self.improve).pack(side="left", padx=10)

        self.status = tk.Label(root, text="Loading Whisper...", anchor="w", fg="grey20")
        self.status.pack(fill="x", padx=10)

        panes = tk.PanedWindow(root, orient="horizontal", sashwidth=6)
        panes.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        self.raw_box = self._text_pane(panes, "What you said (you can edit this, then press 'Tidy again')")
        self.tidy_box = self._text_pane(panes, "Tidied up")

        threading.Thread(target=self.load_whisper, daemon=True).start()

    def _text_pane(self, panes, title):
        frame = tk.Frame(panes)
        tk.Label(frame, text=title, anchor="w").pack(fill="x")
        box = scrolledtext.ScrolledText(frame, wrap="word", font=("Helvetica", 12), undo=True)
        box.pack(fill="both", expand=True)
        panes.add(frame, stretch="always")
        return box

    # Tk widgets must only be touched from the main thread.
    def set_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def load_whisper(self):
        try:
            self.whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            self.set_status("Ready. Press Record and start talking.")
        except Exception as e:
            self.set_status(f"Couldn't load Whisper: {e}")

    # ---- recording ----

    def toggle_record(self):
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.whisper is None:
            self.set_status("Whisper is still loading, give it a moment...")
            return
        self.chunks = []
        try:
            self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                         callback=lambda data, *_: self.chunks.append(data.copy()))
            self.stream.start()
        except Exception as e:
            self.set_status(f"Couldn't use the microphone: {e}")
            return
        self.recording = True
        self.record_btn.config(text="■ Stop", fg="red")
        self.set_status("Recording... press Stop when you're done.")

    def stop_recording(self):
        self.stream.stop()
        self.stream.close()
        self.recording = False
        self.record_btn.config(text="● Record", fg="black", state="disabled")
        if not self.chunks:
            self.record_btn.config(state="normal")
            self.set_status("Didn't catch any audio.")
            return
        audio = np.concatenate(self.chunks).flatten()
        self.set_status("Transcribing...")
        threading.Thread(target=self.transcribe_then_tidy, args=(audio,), daemon=True).start()

    def transcribe_then_tidy(self, audio):
        names = load_names()
        hint = ("Names: " + ", ".join(names) + ".") if names else None
        try:
            segments, _ = self.whisper.transcribe(audio, language="en", initial_prompt=hint,
                                                  vad_filter=True)
            text = " ".join(s.text.strip() for s in segments).strip()
        except Exception as e:
            self.set_status(f"Transcription failed: {e}")
            self.root.after(0, lambda: self.record_btn.config(state="normal"))
            return
        self.root.after(0, self.after_transcribe, text)

    def after_transcribe(self, text):
        self.record_btn.config(state="normal")
        if not text:
            self.set_status("Didn't hear any speech.")
            return
        # Each new recording is added on, so you can dictate in bits.
        existing = self.raw_box.get("1.0", "end").strip()
        self.raw_box.insert("end", ("\n\n" if existing else "") + text)
        self.start_tidy()

    # ---- tidying ----

    def start_tidy(self):
        text = self.raw_box.get("1.0", "end").strip()
        if not text:
            self.set_status("Nothing to tidy yet.")
            return
        self.set_status(f"Tidying with {OLLAMA_MODEL}...")
        threading.Thread(target=self.tidy, args=(text, self.improve.get()), daemon=True).start()

    def tidy(self, text, improve):
        try:
            result = tidy_with_ollama(text, improve, load_names())
        except urllib.error.HTTPError as e:
            self.set_status(f"Ollama said: {e}  (Have you run `ollama pull {OLLAMA_MODEL}`?)")
            return
        except urllib.error.URLError:
            self.set_status("Couldn't reach Ollama. Is it running? (Open the Ollama app, "
                            "or run `ollama serve`.)")
            return
        except Exception as e:
            self.set_status(f"Tidy-up failed: {e}  (Have you run `ollama pull {OLLAMA_MODEL}`?)")
            return
        self.root.after(0, self.show_result, result)

    def show_result(self, result):
        self.tidy_box.delete("1.0", "end")
        self.tidy_box.insert("1.0", result)
        if AUTO_COPY:
            self.copy()
            self.set_status("Done - tidied text copied to the clipboard.")
        else:
            self.set_status("Done.")

    def copy(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.tidy_box.get("1.0", "end").strip())
        self.set_status("Copied to the clipboard.")

    def clear(self):
        self.raw_box.delete("1.0", "end")
        self.tidy_box.delete("1.0", "end")
        self.set_status("Cleared.")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
