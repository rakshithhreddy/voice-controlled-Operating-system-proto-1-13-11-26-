"""
Text-to-Speech (TTS) Speaker Module.
Utilizes local offline Windows SAPI5 voice synthesis via pyttsx3.
Uses a dedicated non-blocking thread queue to prevent freezing the UI.
"""

import queue
import threading
import logging
from typing import Optional
import pyttsx3

from src.config import TTS_RATE, TTS_VOLUME, LOG_FILE

logger = logging.getLogger("VoiceOS.Speaker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [Speaker] %(message)s"))
    logger.addHandler(fh)


class VoiceSpeaker:
    """
    Offline Text-To-Speech engine using pyttsx3 with thread-safe queue.
    """

    def __init__(self, rate: int = TTS_RATE, volume: float = TTS_VOLUME, enabled: bool = True):
        self.rate = rate
        self.volume = volume
        self.enabled = enabled

        self._queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        if self.enabled:
            self._start_worker()

    def _start_worker(self) -> None:
        """Starts background worker thread for speech synthesis."""
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _worker_loop(self) -> None:
        """Worker thread loop initializing and running pyttsx3 engine."""
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)

            # Pick default English voice if available
            voices = engine.getProperty("voices")
            for v in voices:
                if "english" in v.name.lower() or "zira" in v.name.lower() or "david" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
        except Exception as e:
            logger.warning(f"Could not initialize local pyttsx3 engine in worker: {e}")
            return

        while not self._stop_event.is_set():
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break

                if self.enabled and text.strip():
                    try:
                        logger.info(f"Speaking: '{text}'")
                        engine.say(text)
                        engine.runAndWait()
                    except Exception as ex:
                        logger.error(f"Error during TTS synthesis: {ex}")
                self._queue.task_done()
            except queue.Empty:
                continue

    def speak(self, text: str) -> None:
        """Enqueues text to be spoken asynchronously."""
        if not self.enabled or not text:
            return
        # Clean text of long multi-line dumps or code blocks before speaking
        clean_text = self._clean_speech_text(text)
        self._queue.put(clean_text)

    def _clean_speech_text(self, text: str) -> str:
        """Removes code blocks, long paths, or excess symbols for natural speech."""
        lines = text.splitlines()
        if len(lines) > 4:
            # Shorten long text output for voice
            return f"{lines[0]}. Plus {len(lines) - 1} more lines."
        return text

    def set_enabled(self, enabled: bool) -> None:
        """Enables or mutes speech output."""
        self.enabled = enabled

    def stop(self) -> None:
        """Stops the speaker worker."""
        self._stop_event.set()
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
