"""
Voice input/output helpers using SpeechRecognition and pyttsx3.
"""

from __future__ import annotations

from typing import Optional


def listen(timeout: int = 5, phrase_time_limit: int = 10) -> str:
    """
    Capture microphone audio and return recognized text.
    Raises RuntimeError for user-friendly error handling in UI.
    """
    try:
        import speech_recognition as sr
    except ImportError as exc:
        raise RuntimeError(
            "SpeechRecognition is not installed. Run: pip install SpeechRecognition pyaudio"
        ) from exc

    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        return recognizer.recognize_google(audio)
    except sr.WaitTimeoutError as exc:
        raise RuntimeError("Microphone timeout. Please try speaking again.") from exc
    except sr.UnknownValueError as exc:
        raise RuntimeError("Could not understand audio. Please try again.") from exc
    except sr.RequestError as exc:
        raise RuntimeError(f"Speech recognition service error: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Microphone error: {exc}") from exc


def speak(text: str, rate: Optional[int] = 180) -> None:
    """
    Convert text to speech using offline pyttsx3.
    Raises RuntimeError if TTS engine fails.
    """
    if not text.strip():
        return

    try:
        import pyttsx3
    except ImportError as exc:
        raise RuntimeError("pyttsx3 is not installed. Run: pip install pyttsx3") from exc

    try:
        engine = pyttsx3.init()
        if rate is not None:
            engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        raise RuntimeError(f"Text-to-speech failed: {exc}") from exc
