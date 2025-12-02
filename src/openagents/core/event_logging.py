"""
Event Logging System

This module provides event logging functionality, including:
- EventLogEntry: event log data structure
- EventLogWriter: background async writer task
- Log file rotation and cleanup
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

from openagents.models.event import Event

logger = logging.getLogger(__name__)


@dataclass
class EventLogEntry:
    """Event log entry data structure"""
    timestamp: float  # Unix timestamp with milliseconds
    direction: str  # "inbound" or "outbound"
    event_name: str
    source_id: str
    destination_id: Optional[str]
    payload: Dict[str, Any]
    visibility: str
    request_id: str  # event_id
    response_to: Optional[str]

    @classmethod
    def from_event(cls, event: Event, direction: str) -> "EventLogEntry":
        """Create a log entry from an Event object
        
        Args:
            event: Event object
            direction: "inbound" or "outbound"
        """
        return cls(
            timestamp=time.time(),
            direction=direction,
            event_name=event.event_name,
            source_id=event.source_id or "",
            destination_id=event.destination_id,
            payload=event.payload,
            visibility=event.visibility.value if hasattr(event.visibility, 'value') else str(event.visibility),
            request_id=event.event_id,
            response_to=event.response_to,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "timestamp": self.timestamp,
            "direction": self.direction,
            "event_name": self.event_name,
            "source_id": self.source_id,
            "destination_id": self.destination_id,
            "payload": self.payload,
            "visibility": self.visibility,
            "request_id": self.request_id,
            "response_to": self.response_to,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class EventLogWriter:
    """
    Event log writer.

    A standalone async task that consumes log entries from a queue and writes them
    into a JSONL file. Supports log rotation and automatic cleanup.
    """

    def __init__(
        self,
        logs_path: Path,
        max_file_size_mb: int = 100,
        retention_days: int = 7,
    ):
        """Initialize event log writer
        
        Args:
            logs_path: Directory where log files are stored
            max_file_size_mb: Maximum size of a single log file (MB)
            retention_days: Number of days to retain log files
        """
        self.logs_path = Path(logs_path)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.retention_days = retention_days
        
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self.task: Optional[asyncio.Task] = None
        
        self.current_log_file: Optional[Path] = None
        self.current_file_handle = None
        
        logger.info(
            f"EventLogWriter initialized: logs_path={self.logs_path}, "
            f"max_file_size={max_file_size_mb}MB, retention={retention_days} days"
        )

    async def start(self):
        """Start the event log writer"""
        if self.running:
            logger.warning("EventLogWriter is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._write_loop())
        logger.info("EventLogWriter started")

    async def stop(self):
        """Stop the event log writer"""
        if not self.running:
            return
        
        self.running = False
        
        # Wait for queue to be fully consumed
        await self.queue.join()
        
        # Cancel background task
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        # Close file handle
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None
        
        logger.info("EventLogWriter stopped")

    async def log_event(self, entry: EventLogEntry):
        """Add a log entry to the queue
        
        Args:
            entry: Event log entry
        """
        try:
            self.queue.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning("Event log queue is full, dropping event")

    async def _write_loop(self):
        """Background write loop"""
        try:
            while self.running:
                try:
                    # Retrieve event from queue, timeout every 1 second
                    entry = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    
                    # Write entry
                    await self._write_event(entry)
                    
                    self.queue.task_done()
                    
                except asyncio.TimeoutError:
                    # Normal condition for periodic checks
                    continue
                    
        except asyncio.CancelledError:
            logger.info("EventLogWriter write loop cancelled")
        except Exception as e:
            logger.error(f"Error in EventLogWriter write loop: {e}", exc_info=True)

    async def _write_event(self, entry: EventLogEntry):
        """Write a single event into the log file"""
        try:
            # Check file rotation
            await self._check_rotation()
            
            # Ensure file handle is open
            if not self.current_file_handle:
                await self._open_new_log_file()
            
            json_line = entry.to_json() + "\n"
            self.current_file_handle.write(json_line)
            self.current_file_handle.flush()
            
        except Exception as e:
            logger.error(f"Error writing event to log: {e}", exc_info=True)

    async def _check_rotation(self):
        """Check whether log rotation is needed"""
        should_rotate = False
        
        # By date
        if self.current_log_file:
            current_date = datetime.now().strftime("%Y-%m-%d")
            file_date = self._extract_date_from_filename(self.current_log_file.name)
            if file_date != current_date:
                should_rotate = True
                logger.info("Date changed, rotating log file")
        
        # By size
        if self.current_log_file and self.current_log_file.exists():
            file_size = self.current_log_file.stat().st_size
            if file_size >= self.max_file_size_bytes:
                should_rotate = True
                logger.info(
                    f"Log file size {file_size} bytes exceeds limit "
                    f"{self.max_file_size_bytes} bytes, rotating"
                )
        
        if should_rotate:
            await self._rotate_log_file()
            await self._cleanup_old_logs()

    async def _rotate_log_file(self):
        """Rotate the log file"""
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None
        
        await self._open_new_log_file()

    async def _open_new_log_file(self):
        """Open a new log file"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        base_filename = f"events.{current_date}.log"
        log_file_path = self.logs_path / base_filename
        
        # If file already exists and is close to size limit, append timestamp
        if log_file_path.exists():
            file_size = log_file_path.stat().st_size
            if file_size >= self.max_file_size_bytes * 0.9:
                timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                base_filename = f"events.{timestamp}.log"
                log_file_path = self.logs_path / base_filename
        
        self.current_log_file = log_file_path
        self.current_file_handle = open(log_file_path, "a", encoding="utf-8")
        
        logger.info(f"Opened log file: {log_file_path}")

    async def _cleanup_old_logs(self):
        """Clean up old log files"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            log_files = list(self.logs_path.glob("events.*.log"))
            
            for log_file in log_files:
                file_date_str = self._extract_date_from_filename(log_file.name)
                if not file_date_str:
                    continue
                
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                    
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info(f"Deleted old log file: {log_file}")
                        
                except ValueError:
                    logger.warning(f"Could not parse date from filename: {log_file.name}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}", exc_info=True)

    def _extract_date_from_filename(self, filename: str) -> Optional[str]:
        """Extract date string from filename
        
        Args:
            filename: Name like "events.2025-11-26.log"
        
        Returns:
            "YYYY-MM-DD" or None
        """
        match = re.search(r'events\.(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)
        return None

    def get_all_log_files(self) -> List[Path]:
        """Get all log files sorted by modification time descending"""
        log_files = list(self.logs_path.glob("events.*.log"))
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return log_files
