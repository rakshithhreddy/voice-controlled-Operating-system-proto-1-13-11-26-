"""
Speech Recognition Engine.
Provides microphone audio capture, noise adjustment, offline/online transcription,
microphone enumeration, and background/push-to-talk listening modes.
Includes simulated audio feeding for testing without a physical microphone.
"""

import threading
import logging
from typing import Callable, Optional, List, Dict, Any
import speech_recognition as sr

from src.config import (
    LOG_FILE,
    ENERGY_THRESHOLD,
    DYNAMIC_ENERGY_THRESHOLD,
    PAUSE_THRESHOLD,
    PHRASE_TIME_LIMIT
)

logger = logging.getLogger("VoiceOS.VoiceRecognizer")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [VoiceRecognizer] %(message)s"))
    logger.addHandler(fh)


class SpeechRecognitionEngine:
    """
    Manages speech capture and transcription from microphones or audio files.
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
        on_status_change: Optional[Callable[[str], None]] = None
    ):
        self.device_index = device_index
        self.on_transcription = on_transcription
        self.on_status_change = on_status_change

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = ENERGY_THRESHOLD
        self.recognizer.dynamic_energy_threshold = DYNAMIC_ENERGY_THRESHOLD
        self.recognizer.pause_threshold = PAUSE_THRESHOLD

        self._is_listening = False
        self._stop_listening_fn: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()

    @staticmethod
    def list_microphones() -> List[Dict[str, Any]]:
        """Returns list of available microphones with device index and name."""
        try:
            names = sr.Microphone.list_microphone_names()
            return [{"index": i, "name": name} for i, name in enumerate(names)]
        except Exception as e:
            logger.error(f"Failed to list microphones: {e}")
            return []

    def set_device_index(self, index: Optional[int]) -> None:
        """Sets the active input microphone index."""
        with self._lock:
            self.device_index = index

    def set_status(self, status: str) -> None:
        """Emits state changes to listeners."""
        if self.on_status_change:
            try:
                self.on_status_change(status)
            except Exception as e:
                logger.error(f"Error in on_status_change callback: {e}")

    def calibrate_noise(self, duration: float = 1.0) -> bool:
        """Adjusts recognizer energy threshold for ambient room noise."""
        try:
            self.set_status("CALIBRATING")
            with sr.Microphone(device_index=self.device_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
            logger.info(f"Calibrated noise threshold: {self.recognizer.energy_threshold}")
            self.set_status("IDLE")
            return True
        except Exception as e:
            logger.warning(f"Microphone calibration unavailable or failed: {e}")
            self.set_status("MIC_ERROR")
            return False

    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """
        Listens synchronously for a single phrase and returns transcribed text.
        Useful for push-to-talk mode.
        """
        try:
            self.set_status("LISTENING")
            with sr.Microphone(device_index=self.device_index) as source:
                logger.info("Listening for speech...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=PHRASE_TIME_LIMIT
                )

            self.set_status("PROCESSING")
            text = self._transcribe(audio)
            self.set_status("IDLE")
            return text
        except sr.WaitTimeoutError:
            logger.info("Speech listen timed out (no speech detected).")
            self.set_status("IDLE")
            return None
        except Exception as e:
            logger.error(f"Error during audio listening: {e}")
            self.set_status("MIC_ERROR")
            return None

    def start_continuous_listening(self) -> bool:
        """Starts background continuous listening thread."""
        with self._lock:
            if self._is_listening:
                return True

            try:
                mic = sr.Microphone(device_index=self.device_index)
                # Test opening mic to verify availability
                with mic as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

                def callback(recognizer, audio):
                    self.set_status("PROCESSING")
                    try:
                        text = self._transcribe(audio)
                        if text:
                            logger.info(f"Transcribed speech: '{text}'")
                            if self.on_transcription:
                                self.on_transcription(text)
                    except Exception as ex:
                        logger.error(f"Transcription callback error: {ex}")
                    finally:
                        if self._is_listening:
                            self.set_status("LISTENING")

                self._stop_listening_fn = self.recognizer.listen_in_background(
                    mic,
                    callback,
                    phrase_time_limit=PHRASE_TIME_LIMIT
                )
                self._is_listening = True
                self.set_status("LISTENING")
                logger.info("Continuous background listening started.")
                return True
            except Exception as e:
                logger.error(f"Failed to start background listening: {e}")
                self.set_status("MIC_ERROR")
                return False

    def stop_continuous_listening(self) -> None:
        """Stops the background continuous listening thread."""
        with self._lock:
            if self._stop_listening_fn:
                try:
                    self._stop_listening_fn(wait_for_stop=False)
                except Exception as e:
                    logger.error(f"Error stopping listening function: {e}")
                self._stop_listening_fn = None
            self._is_listening = False
            self.set_status("IDLE")
            logger.info("Continuous background listening stopped.")

    def is_listening(self) -> bool:
        return self._is_listening

    def transcribe_audio_file(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribes speech from a WAV audio file.
        Essential for testing audio pipelines without hardware microphone dependencies.
        """
        try:
            with sr.AudioFile(audio_file_path) as source:
                audio = self.recognizer.record(source)
            return self._transcribe(audio)
        except Exception as e:
            logger.error(f"Error transcribing audio file '{audio_file_path}': {e}")
            return None

    def _transcribe(self, audio_data: sr.AudioData) -> Optional[str]:
        """Transcribes raw AudioData into text."""
        # Primary recognition path: SpeechRecognition built-in offline/online handler
        try:
            # Uses Google Web Speech default handler in SpeechRecognition (free, no API key needed)
            text = self.recognizer.recognize_google(audio_data, language="en-US")
            return text.strip()
        except sr.UnknownValueError:
            logger.info("Speech was unintelligible.")
            return None
        except sr.RequestError as e:
            logger.warning(f"Network speech recognition service unavailable: {e}. Trying offline fallback.")
            # Offline fallback (Sphinx or Vosk if installed)
            try:
                return self.recognizer.recognize_sphinx(audio_data).strip()
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return None
