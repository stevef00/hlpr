import sys
import threading
import time

class Spinner:
    def __init__(self, message="Thinking"):
        self.message = message
        self.spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self.spinner_index = 0
        self.stop_event = threading.Event()
        self.spinner_thread = None

    def _spin(self):
        while not self.stop_event.is_set():
            sys.stdout.write(f"\r{self.message} {self.spinner_chars[self.spinner_index]} ")
            sys.stdout.flush()
            self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
            time.sleep(0.1)
        sys.stdout.write("\r" + " " * (len(self.message) + 3) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self.spinner_thread = threading.Thread(target=self._spin)
        self.spinner_thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        self.spinner_thread.join()
