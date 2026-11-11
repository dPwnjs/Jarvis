import queue
import threading
import time
import pyaudio

INPUT_RATE = 16000
OUTPUT_RATE = 24000
CHANNELS = 1
CHUNK_SIZE = 1024
AUDIO_FORMAT = pyaudio.paInt16


class AudioManager:
    """
    Handles real-time microphone capture and low-latency audio playback for J.A.R.V.I.S.
    Microphone is kept 100% always-on with zero gating for immediate follow-up conversations.
    """

    def __init__(self, input_rate: int = INPUT_RATE, output_rate: int = OUTPUT_RATE):
        self.input_rate = input_rate
        self.output_rate = output_rate
        self.p = pyaudio.PyAudio()

        self.input_stream = None
        self.output_stream = None

        # Queue for incoming audio chunks from Gemini
        self.playback_queue: queue.Queue = queue.Queue()
        self._playback_thread = None
        self._running = False
        self._is_speaking = False

    def start(self):
        """Initializes and opens audio hardware streams."""
        self._running = True

        # Open Microphone Input Stream (16kHz Mono)
        self.input_stream = self.p.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=self.input_rate,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        # Open Speaker Output Stream (24kHz Mono, matching Gemini output)
        self.output_stream = self.p.open(
            format=AUDIO_FORMAT,
            channels=CHANNELS,
            rate=self.output_rate,
            output=True,
            frames_per_buffer=CHUNK_SIZE,
        )

        # Start dedicated playback worker thread
        self._playback_thread = threading.Thread(
            target=self._playback_worker, daemon=True
        )
        self._playback_thread.start()

    def _playback_worker(self):
        """Worker thread to continuously play audio chunks from the queue."""
        while self._running:
            try:
                chunk = self.playback_queue.get(timeout=0.02)
                if chunk is None:
                    continue

                self._is_speaking = True
                if self.output_stream and self.output_stream.is_active():
                    self.output_stream.write(chunk)
                self.playback_queue.task_done()

                if self.playback_queue.empty():
                    self._is_speaking = False
            except queue.Empty:
                self._is_speaking = False
            except Exception:
                pass

    def play_chunk(self, data: bytes):
        """Enqueue PCM audio chunk sliced into uniform sizes for smooth playback."""
        if not self._running or not data:
            return

        slice_size = 2048
        for i in range(0, len(data), slice_size):
            self.playback_queue.put(data[i : i + slice_size])

    def stop_playback(self):
        """Discard all queued audio and stop playback immediately."""
        while not self.playback_queue.empty():
            try:
                self.playback_queue.get_nowait()
                self.playback_queue.task_done()
            except queue.Empty:
                break
        self._is_speaking = False

    def is_speaking(self) -> bool:
        """Returns True if audio is actively being played out."""
        return self._is_speaking or not self.playback_queue.empty()

    def read_mic_chunk(self) -> bytes:
        """Read a single chunk from the microphone."""
        if not self.input_stream:
            return b""
        try:
            return self.input_stream.read(CHUNK_SIZE, exception_on_overflow=False)
        except Exception:
            return b""

    def close(self):
        """Clean up audio streams and terminate PyAudio."""
        self._running = False
        self.stop_playback()

        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except Exception:
                pass

        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except Exception:
                pass

        self.p.terminate()
