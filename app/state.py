import asyncio
import logging
import threading
import collections

# Thread-safe log buffer for GUI
log_buffer = collections.deque(maxlen=50)
buffer_lock = threading.Lock()

class LogBufferHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        with buffer_lock:
            log_buffer.append(log_entry)

# Global state
stop_event = asyncio.Event()
mapping_in_progress = False
configured_uia_url = "127.0.0.1:5006"
config_verified = False
active_mapping_task = None  # Track active background task

# Progress tracking
progress_current = 0
progress_total = 0

def get_logs():
    with buffer_lock:
        return list(log_buffer)

def reset_state():
    global mapping_in_progress, active_mapping_task, progress_current, progress_total
    mapping_in_progress = False
    active_mapping_task = None
    stop_event.clear()
    progress_current = 0
    progress_total = 0
