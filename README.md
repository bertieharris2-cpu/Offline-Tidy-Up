# Offline Tidy-Up

Press **Record**, talk, press **Stop**. It writes down what you said, then tidies it up:
punctuation, paragraphs, no "um"s, and clearer sentences that still sound like you.
The tidied text is copied to your clipboard automatically, ready to paste.

Everything runs on your own computer (Whisper for the speech, Ollama for the tidying),
so you can use children's real names.

## One-off setup

1. **Install Python 3.10 or newer** from <https://www.python.org/downloads/>
   (on Windows, tick "Add Python to PATH" during install).
2. **Install Ollama** from <https://ollama.com/download> and open it.
3. **Download a model for Ollama.** In a terminal (Command Prompt on Windows):
   ```
   ollama pull llama3.1:8b
   ```
4. **Install this program's bits.** In a terminal, in this folder:
   ```
   pip install -r requirements.txt
   ```

The first time you run it, Whisper downloads its speech model (about 500 MB). After that,
it works with the internet switched off.

## Using it

```
python tidy_up.py
```

- **Record / Stop**: each recording is added to the left-hand box, so you can dictate in bits.
- The right-hand box shows the tidied version, already copied to the clipboard.
- If Whisper mishears a word, fix it in the left-hand box and press **Tidy again**.
- Untick **Improve sentences** if you only want punctuation and paragraphs.
- You can also paste text into the left box and press **Tidy again**.

### Getting names spelled right

Copy `names.example.txt` to `names.txt` and list the children's names, one per line.
Whisper will spell them properly and the tidy-up will leave them alone.
`names.txt` never gets uploaded anywhere (it's in `.gitignore`).

## Tweaks

The settings are at the top of `tidy_up.py`:

| Setting | What it does |
|---|---|
| `OLLAMA_MODEL` | Which Ollama model tidies the text. On a slower laptop try `llama3.2` (smaller and faster). |
| `WHISPER_MODEL` | `base.en` is faster, `medium.en` is more accurate. |
| `SPELLING` | `"British English"` by default. |
| `AUTO_COPY` | Set to `False` if you don't want it copying automatically. |

To change *how* it rewrites, edit the rules text just below the settings.

## If something goes wrong

- **"Couldn't reach Ollama"**: open the Ollama app (or run `ollama serve`).
- **"Have you run `ollama pull ...`?"**: the model in `OLLAMA_MODEL` isn't downloaded yet.
- **Microphone errors on a Mac**: allow Terminal to use the microphone in
  System Settings → Privacy & Security → Microphone.
- **`No module named tkinter`** (Linux only): `sudo apt install python3-tk`.
