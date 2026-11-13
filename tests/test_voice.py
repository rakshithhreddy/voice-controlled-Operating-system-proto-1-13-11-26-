"""
Unit tests for Speech Recognition and Voice Speaker subsystems.
"""

import pytest
from src.voice.recognizer import SpeechRecognitionEngine
from src.voice.speaker import VoiceSpeaker


def test_microphone_enumeration():
    mics = SpeechRecognitionEngine.list_microphones()
    assert isinstance(mics, list)
    # On Windows systems with audio drivers, devices are enumerated
    if len(mics) > 0:
        assert "name" in mics[0]
        assert "index" in mics[0]


def test_recognizer_initialization():
    engine = SpeechRecognitionEngine()
    assert engine.is_listening() is False
    assert engine.recognizer is not None


def test_speaker_initialization_and_sanitization():
    speaker = VoiceSpeaker(enabled=False)
    assert speaker.enabled is False

    long_multiline = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5\nLine 6"
    cleaned = speaker._clean_speech_text(long_multiline)
    assert "Plus 5 more lines" in cleaned


def test_vosk_offline_model_loaded():
    engine = SpeechRecognitionEngine()
    assert engine.vosk_model is not None, "Offline Vosk model should be loaded"


def test_hold_to_talk_manager_lifecycle():
    from src.voice.hold_to_talk import HoldToTalkManager
    htt = HoldToTalkManager()
    assert htt.is_recording() is False
    assert htt._key_held is False
