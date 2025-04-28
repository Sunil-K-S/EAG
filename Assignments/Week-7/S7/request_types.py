import time
import uuid
from typing import Dict

class RequestContext:
    """Context for tracking request state and timing."""
    
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.stage_times = {}
        self.start_time = time.time()
        
    def log_stage_time(self, stage: str):
        """Log the time taken for a stage."""
        self.stage_times[stage] = time.time() - self.start_time
        
    def calculate_total_time(self) -> float:
        """Calculate the total time taken for the request."""
        return time.time() - self.start_time 