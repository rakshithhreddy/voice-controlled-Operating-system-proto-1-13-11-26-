"""
Speech Recognition Engine.
Provides microphone audio capture, noise adjustment, offline Vosk & SpeechRecognition transcription,
microphone enumeration, and in-memory WAV buffer transcription.
"""

import io
import os
import json
import logging
from typing import Callable, Optional, List, Dict, Any
from pathlib import Path
import speech_recognition as sr

try:
    import vosk
    HAS_VOSK = True
except ImportError:
    HAS_VOSK = False

from src.config import (
    LOG_FILE,
    ENERGY_THRESHOLD,
    DYNAMIC_ENERGY_THRESHOLD,
    PAUSE_THRESHOLD,
    PHRASE_TIME_LIMIT,
    PROJECT_ROOT
)

logger = logging.getLogger("VoiceOS.VoiceRecognizer")


class SpeechRecognitionEngine:
    """
    Manages speech transcription from microphones, audio files, or in-memory WAV buffers.
    Supports offline Vosk when models are present, falling back to local speech recognizer.
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

        # Check for local Vosk model
        self.vosk_model = None
        self._init_vosk()

    def _init_vosk(self) -> None:
        """Initializes Vosk offline engine if model directory exists."""
        if not HAS_VOSK:
            return
        
        # Check standard model locations
        model_paths = [
            PROJECT_ROOT / "models" / "vosk-model-small-en-us",
            PROJECT_ROOT / "models" / "vosk-model-en-us",
            Path.home() / ".cache" / "vosk" / "vosk-model-small-en-us"
        ]
        for p in model_paths:
            if p.exists() and p.is_dir():
                try:
                    logger.info(f"Loading local offline Vosk model from: {p}")
                    self.vosk_model = vosk.Model(str(p))
                    logger.info("Vosk offline model successfully loaded.")
                    return
                except Exception as e:
                    logger.warning(f"Failed to load Vosk model at {p}: {e}")

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
        self.device_index = index

    def set_status(self, status: str) -> None:
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
            logger.warning(f"Microphone calibration unavailable: {e}")
            self.set_status("MIC_ERROR")
            return False

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> Optional[str]:
        """
        Transcribes speech directly from an in-memory WAV byte buffer.
        Used by the Hold-Enter-to-Speak push-to-talk engine.
        """
        if not wav_bytes:
            return None

        # 1. If Vosk model is available, use fast offline kaldi transcription
        if self.vosk_model and HAS_VOSK:
            try:
                import wave
                with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                    rec = vosk.KaldiRecognizer(self.vosk_model, wf.getframerate())
                    rec.SetWords(True)
                    while True:
                        data = wf.readframes(4000)
                        if len(data) == 0:
                            break
                        rec.AcceptWaveform(data)
                    res = json.loads(rec.FinalResult())
                    text = res.get("text", "").strip()
                    if text:
                        logger.info(f"Vosk offline transcribed: '{text}'")
                        return text
            except Exception as e:
                logger.warning(f"Vosk transcription error, falling back: {e}")

        # 2. Standard SpeechRecognition pipeline
        try:
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio = self.recognizer.record(source)
            return self._transcribe(audio)
        except Exception as e:
            logger.error(f"Error reading WAV bytes for transcription: {e}")
            return None

    def listen_once(self, timeout: float = 5.0) -> Optional[str]:
        """Listens synchronously for a single phrase."""
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
            self.set_status("IDLE")
            return None
        except Exception as e:
            logger.error(f"Error during audio listening: {e}")
            self.set_status("MIC_ERROR")
            return None

    def start_continuous_listening(self) -> bool:
        """Starts background continuous listening thread."""
        if self._is_listening:
            return True

        try:
            mic = sr.Microphone(device_index=self.device_index)
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
            return True
        except Exception as e:
            logger.error(f"Failed to start background listening: {e}")
            self.set_status("MIC_ERROR")
            return False

    def stop_continuous_listening(self) -> None:
        if self._stop_listening_fn:
            try:
                self._stop_listening_fn(wait_for_stop=False)
            except Exception:
                pass
            self._stop_listening_fn = None
        self._is_listening = False
        self.set_status("IDLE")

    def is_listening(self) -> bool:
        return self._is_listening

    def transcribe_audio_file(self, audio_file_path: str) -> Optional[str]:
        try:
            with sr.AudioFile(audio_file_path) as source:
                audio = self.recognizer.record(source)
            return self._transcribe(audio)
        except Exception as e:
            logger.error(f"Error transcribing audio file '{audio_file_path}': {e}")
            return None

    def _transcribe(self, audio_data: sr.AudioData) -> Optional[str]:
        try:
            text = self.recognizer.recognize_google(audio_data, language="en-US")
            return text.strip()
        except sr.UnknownValueError:
            return None
        except sr.RequestError as e:
            logger.warning(f"Google speech service unavailable: {e}. Trying offline fallback.")
            try:
                return self.recognizer.recognize_sphinx(audio_data).strip()
            except Exception:
                return None
        except Exception as e:
            logger.error(f"Recognition error: {e}")
            return None
