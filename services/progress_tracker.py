"""
Real-time progress tracking for the News Intelligence Agent.

Provides a thread-safe progress tracker that emits events
consumed by the SSE endpoint for live dashboard updates.

Usage:
    tracker = get_tracker()
    tracker.start("collecting")
    tracker.update_stage("rss_fetch", "Fetching RSS feeds", current=5, total=28)
    tracker.complete(results)
"""

import time
import json
import threading
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from queue import Queue, Empty
from datetime import datetime, timezone

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProgressEvent:
    """A single progress update event."""
    stage: str                              # Current stage ID
    stage_name: str                         # Human-readable stage name
    stage_number: int = 0                   # Current stage number (1-based)
    total_stages: int = 10                  # Total number of stages
    current_items: int = 0                  # Items processed in current stage
    total_items: int = 0                    # Total items in current stage
    elapsed_seconds: float = 0.0            # Time since start
    eta_seconds: float = 0.0               # Estimated time remaining
    status: str = "running"                 # running | completed | error | stuck
    message: str = ""                       # Optional detail message
    results: Dict[str, Any] = field(default_factory=dict)  # Final results (on complete)
    timestamp: str = ""                     # ISO timestamp

    def to_json(self) -> str:
        return json.dumps(asdict(self), default=str)


class ProgressTracker:
    """Thread-safe progress tracker with SSE event broadcasting.
    
    Maintains current state and broadcasts updates to all
    connected SSE clients via a list of subscriber queues.
    """

    # Stage definitions with historical average durations (seconds)
    STAGES = [
        ("rss_fetch", "Fetching RSS feeds", 60),
        ("newsapi_fetch", "Fetching from NewsAPI", 20),
        ("normalize", "Normalizing articles", 2),
        ("filter", "Filtering articles", 1),
        ("deduplicate", "Removing duplicates", 3),
        ("score", "Scoring articles", 2),
        ("group", "Grouping related stories", 2),
        ("authenticity", "Checking authenticity", 2),
        ("store", "Storing in database", 20),
        ("cleanup", "Finalizing", 3),
    ]

    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: List[Queue] = []
        self._start_time: Optional[float] = None
        self._stage_times: Dict[str, float] = {}  # Track actual stage durations
        self._current_event: Optional[ProgressEvent] = None
        self._is_running = False
        self._stage_start_time: Optional[float] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def subscribe(self) -> Queue:
        """Subscribe to progress events. Returns a queue that receives events."""
        q = Queue(maxsize=100)
        with self._lock:
            self._subscribers.append(q)
            # Send current state immediately if running
            if self._current_event:
                try:
                    q.put_nowait(self._current_event)
                except Exception:
                    pass
        return q

    def unsubscribe(self, q: Queue):
        """Remove a subscriber queue."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def start(self, process_type: str = "news"):
        """Signal that a collection process has started."""
        with self._lock:
            self._start_time = time.time()
            self._stage_times = {}
            self._is_running = True
            self._stage_start_time = time.time()

        event = ProgressEvent(
            stage="starting",
            stage_name="Starting collection...",
            stage_number=0,
            total_stages=len(self.STAGES),
            status="running",
            message=f"Initializing {process_type} collection pipeline",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._broadcast(event)

    def update_stage(
        self,
        stage_id: str,
        message: str = "",
        current: int = 0,
        total: int = 0,
    ):
        """Update progress for the current stage."""
        if not self._is_running:
            return

        elapsed = time.time() - self._start_time if self._start_time else 0

        # Find stage number
        stage_num = 0
        for i, (sid, sname, _) in enumerate(self.STAGES):
            if sid == stage_id:
                stage_num = i + 1
                break

        # Calculate ETA based on elapsed time and progress
        eta = self._estimate_eta(stage_id, stage_num, elapsed)

        # Find stage name
        stage_name = message
        for sid, sname, _ in self.STAGES:
            if sid == stage_id:
                stage_name = sname if not message else message
                break

        event = ProgressEvent(
            stage=stage_id,
            stage_name=stage_name,
            stage_number=stage_num,
            total_stages=len(self.STAGES),
            current_items=current,
            total_items=total,
            elapsed_seconds=round(elapsed, 1),
            eta_seconds=round(max(0, eta), 1),
            status="running",
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._current_event = event
        self._broadcast(event)

    def stage_complete(self, stage_id: str):
        """Record that a stage has completed (for ETA calculation)."""
        now = time.time()
        if self._stage_start_time:
            self._stage_times[stage_id] = now - self._stage_start_time
        self._stage_start_time = now

    def complete(self, results: Dict = None):
        """Signal that collection is complete."""
        elapsed = time.time() - self._start_time if self._start_time else 0

        event = ProgressEvent(
            stage="completed",
            stage_name="Collection complete!",
            stage_number=len(self.STAGES),
            total_stages=len(self.STAGES),
            elapsed_seconds=round(elapsed, 1),
            eta_seconds=0,
            status="completed",
            message=f"Completed in {elapsed:.1f}s",
            results=results or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._current_event = event
            self._is_running = False
        self._broadcast(event)

    def error(self, message: str):
        """Signal that an error occurred."""
        elapsed = time.time() - self._start_time if self._start_time else 0

        event = ProgressEvent(
            stage="error",
            stage_name="Error occurred",
            elapsed_seconds=round(elapsed, 1),
            status="error",
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        with self._lock:
            self._current_event = event
            self._is_running = False
        self._broadcast(event)

    def _estimate_eta(self, current_stage_id: str, stage_num: int, elapsed: float) -> float:
        """Estimate remaining time based on completed stages and historical averages."""
        if stage_num <= 0:
            # Use sum of all stage averages
            return sum(dur for _, _, dur in self.STAGES)

        # Calculate average time per completed stage
        remaining_stages = self.STAGES[stage_num:]  # Stages not yet started

        # Use actual durations for completed stages to calibrate
        if self._stage_times:
            # We have real data — use ratio of actual vs estimated
            total_estimated_done = sum(
                dur for sid, _, dur in self.STAGES[:stage_num]
            )
            total_actual_done = sum(self._stage_times.values())

            if total_estimated_done > 0:
                calibration_factor = total_actual_done / total_estimated_done
            else:
                calibration_factor = 1.0

            # Apply calibration to remaining stages
            remaining_estimate = sum(dur for _, _, dur in remaining_stages) * calibration_factor
            return remaining_estimate
        else:
            # No real data yet — use raw estimates
            return sum(dur for _, _, dur in remaining_stages)

    def _broadcast(self, event: ProgressEvent):
        """Send event to all subscribers."""
        dead_queues = []
        with self._lock:
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except Exception:
                    dead_queues.append(q)

            # Clean up dead subscribers
            for q in dead_queues:
                if q in self._subscribers:
                    self._subscribers.remove(q)


# Global singleton
_tracker = None
_tracker_lock = threading.Lock()


def get_tracker() -> ProgressTracker:
    """Get the global progress tracker singleton."""
    global _tracker
    if _tracker is None:
        with _tracker_lock:
            if _tracker is None:
                _tracker = ProgressTracker()
    return _tracker
