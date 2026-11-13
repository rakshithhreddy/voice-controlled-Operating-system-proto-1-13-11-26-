"""
Hold-To-Talk (Push-To-Talk) Audio Capture Engine.
Captures continuous microphone audio while a key (Enter) is held down,
buffering complete PCM audio into an in-memory WAV container upon key release.
"""

import io
import wave
import time
import threading
import logging
from typing import Callable, Optional, List
import pyaudio

logger = logging.getLogger("VoiceOS.HoldToTalk")


class HoldToTalkManager:
    """
    Manages physical push-to-talk microphone capture.
    Records continuously without silence cutoffs until released.
    """

    RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK = 1024

    def __init__(
        self,
        on_recording_start: Optional[Callable[[], None]] = None,
        on_recording_tick: Optional[Callable[[float], None]] = None,
        on_recording_complete: Optional[Callable[[bytes], None]] = None,
        on_error: Optional[Callable[[str], None]] = None
    ):
        self.on_recording_start = on_recording_start
        self.on_recording_tick = on_recording_tick
        self.on_recording_complete = on_recording_complete
        self.on_error = on_error

        self._pyaudio: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._is_recording = False
        self._key_held = False
        self._frames: List[bytes] = []
        self._start_time: float = 0.0
        self._worker_thread: Optional[threading.Thread] = None
        self._tick_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def is_recording(self) -> bool:
        return self._is_recording

    def handle_key_press(self) -> bool:
        """
        Called on KeyPress event. Returns True if recording was started,
        False if ignored due to debouncing (key was already down).
        """
        with self._lock:
            if self._key_held:
                # Debounce auto-repeat
                return False
            self._key_held = True

        return self.start_recording()

    def handle_key_release(self) -> bool:
        """
        Called on KeyRelease event. Returns True if recording was stopped.
        """
        with self._lock:
            if not self._key_held:
                return False
            self._key_held = False

        return self.stop_recording()

    def start_recording(self) -> bool:
        """Starts microphone capture stream in background thread."""
        with self._lock:
            if self._is_recording:
                return False

            try:
                if self._pyaudio is None:
                    self._pyaudio = pyaudio.PyAudio()

                self._frames.clear()
                self._stream = self._pyaudio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
                self._is_recording = True
                self._start_time = time.time()

            except Exception as e:
                logger.error(f"Failed to open audio input stream: {e}")
                self._is_recording = False
                if self.on_error:
                    self.on_error(f"Microphone error: {str(e)}")
                return False

        if self.on_recording_start:
            try:
                self.on_recording_start()
            except Exception as e:
                logger.error(f"Error in on_recording_start: {e}")

        # Worker thread to read audio chunks
        self._worker_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._worker_thread.start()

        # Tick thread for live elapsed duration updates
        self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
        self._tick_thread.start()

        return True

    def _capture_loop(self) -> None:
        """Continuously reads PCM chunks from the open audio stream."""
        while self._is_recording and self._stream:
            try:
                data = self._stream.read(self.CHUNK, exception_on_overflow=False)
                if data:
                    self._frames.append(data)
            except Exception as e:
                logger.warning(f"Error reading audio chunk: {e}")
                break

    def _tick_loop(self) -> None:
        """Reports elapsed recording seconds every 100ms."""
        while self._is_recording:
            elapsed = time.time() - self._start_time
            if self.on_recording_tick:
                try:
                    self.on_recording_tick(elapsed)
                except Exception:
                    pass
            time.sleep(0.1)

    def stop_recording(self) -> bool:
        """Stops audio stream and creates WAV payload for transcription."""
        with self._lock:
            if not self._is_recording:
                return False
            self._is_recording = False

        # Close audio stream safely
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
        except Exception as e:
            logger.error(f"Error closing audio stream: {e}")

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=0.5)

        # Check captured frames
        if not self._frames:
            logger.warning("No audio frames were captured.")
            return False

        # Build WAV in memory
        wav_bytes = self._build_wav(self._frames)
        logger.info(f"Captured {len(wav_bytes)} bytes of WAV audio ({time.time() - self._start_time:.2f}s).")

        if self.on_recording_complete:
            try:
                self.on_recording_complete(wav_bytes)
            except Exception as e:
                logger.error(f"Error in on_recording_complete: {e}")

        return True

    def cancel_recording(self) -> None:
        """Cancels recording without dispatching."""
        with self._lock:
            self._is_recording = False
            self._key_held = False
            try:
                if self._stream:
                    self._stream.stop_stream()
                    self._stream.close()
                    self._stream = None
            except Exception:
                pass
            self._frames.clear()

    def _build_wav(self, frames: List[bytes]) -> bytes:
        """Packages raw PCM chunks into standard 16kHz mono WAV format."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(self._pyaudio.get_sample_size(self.FORMAT) if self._pyaudio else 2)
            wf.setframerate(self.RATE)
            wf.writeframes(b"".join(frames))
        return buf.getvalue()

    def terminate(self) -> None:
        """Terminates PyAudio instance on application shutdown."""
        self.cancel_recording()
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except Exception:
                pass
            self._pyaudio = None
