import threading
from queue import Queue
from typing import Any, Callable, Dict
import time


class Singleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        pass


class QueueCommunicate(metaclass=Singleton):
    def __init__(self):
        self.request_queues = {}
        self.response_queues = {}
        self.lock = threading.Lock()

    def send_event(self, request_id: str, event: Any) -> Any:
        if request_id not in self.request_queues:
            with self.lock:
                if request_id not in self.request_queues:
                    self.request_queues[request_id] = Queue()
                    self.response_queues[request_id] = {}

        request_queue = self.request_queues[request_id]
        response_queues = self.response_queues[request_id]
        response_queue = Queue()
        with self.lock:
            # Store the response queue for the event in the response_queues dict for the request_id
            response_queues[event] = response_queue
        # Send the event to the request queue for the request_id
        request_queue.put(event)
        # Wait for the response from the response queue for the event
        response = response_queue.get()
        with self.lock:
            # Remove the response queue for the event from the response_queues dict for the request_id
            del response_queues[event]
        return response

    def consume_events(self, request_id: str, event_handler: Callable[[Any], Any]):
        
        while True:
            if request_id not in self.request_queues: 
                time.sleep(0.001)               
                continue

            request_queue = self.request_queues[request_id]
            response_queues = self.response_queues[request_id]
            # Get the next event from the request queue for the request_id
            event = request_queue.get()
            # Process the event
            response = event_handler(event)
            with self.lock:
                # Get the response queue for the event from the response_queues dict for the request_id
                response_queue = response_queues.get(event)
            # Put the response in the response queue
            response_queue.put(response)
            request_queue.task_done()


# Global instance of AsyncCommunicate
queue_communicate = QueueCommunicate()
