"""
事件日志系统

该模块提供事件日志记录功能，包括：
- EventLogEntry: 事件日志数据结构
- EventLogWriter: 后台异步写入任务
- 日志文件切割和清理功能
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
    """事件日志条目数据结构"""
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
        """从 Event 对象创建日志条目
        
        Args:
            event: 事件对象
            direction: "inbound" 或 "outbound"
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
        """转换为字典用于序列化"""
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
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())


class EventLogWriter:
    """事件日志写入器
    
    独立的异步任务，从队列中消费事件并写入 JSONL 文件。
    支持日志切割和自动清理。
    """

    def __init__(
        self,
        logs_path: Path,
        max_file_size_mb: int = 100,
        retention_days: int = 7,
    ):
        """初始化事件日志写入器
        
        Args:
            logs_path: 日志目录路径
            max_file_size_mb: 单个日志文件的最大大小（MB）
            retention_days: 日志文件保留天数
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
        """启动日志写入器"""
        if self.running:
            logger.warning("EventLogWriter is already running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._write_loop())
        logger.info("EventLogWriter started")

    async def stop(self):
        """停止日志写入器"""
        if not self.running:
            return
        
        self.running = False
        
        # 等待队列清空
        await self.queue.join()
        
        # 取消任务
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        # 关闭文件句柄
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None
        
        logger.info("EventLogWriter stopped")

    async def log_event(self, entry: EventLogEntry):
        """将事件条目添加到队列
        
        Args:
            entry: 事件日志条目
        """
        try:
            # 使用 put_nowait 避免阻塞
            self.queue.put_nowait(entry)
        except asyncio.QueueFull:
            logger.warning("Event log queue is full, dropping event")

    async def _write_loop(self):
        """后台写入循环"""
        try:
            while self.running:
                try:
                    # 从队列获取事件，超时 1 秒以便定期检查状态
                    entry = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                    
                    # 写入事件
                    await self._write_event(entry)
                    
                    # 标记任务完成
                    self.queue.task_done()
                    
                except asyncio.TimeoutError:
                    # 超时是正常的，继续循环
                    continue
                    
        except asyncio.CancelledError:
            logger.info("EventLogWriter write loop cancelled")
        except Exception as e:
            logger.error(f"Error in EventLogWriter write loop: {e}", exc_info=True)

    async def _write_event(self, entry: EventLogEntry):
        """写入单个事件到日志文件
        
        Args:
            entry: 事件日志条目
        """
        try:
            # 检查是否需要切割日志文件
            await self._check_rotation()
            
            # 确保有打开的文件句柄
            if not self.current_file_handle:
                await self._open_new_log_file()
            
            # 写入 JSONL 行
            json_line = entry.to_json() + "\n"
            self.current_file_handle.write(json_line)
            self.current_file_handle.flush()
            
        except Exception as e:
            logger.error(f"Error writing event to log: {e}", exc_info=True)

    async def _check_rotation(self):
        """检查是否需要切割日志文件"""
        should_rotate = False
        
        # 检查日期变化
        if self.current_log_file:
            current_date = datetime.now().strftime("%Y-%m-%d")
            file_date = self._extract_date_from_filename(self.current_log_file.name)
            if file_date != current_date:
                should_rotate = True
                logger.info(f"Date changed, rotating log file")
        
        # 检查文件大小
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
        """切割日志文件"""
        # 关闭当前文件
        if self.current_file_handle:
            self.current_file_handle.close()
            self.current_file_handle = None
        
        # 打开新文件
        await self._open_new_log_file()

    async def _open_new_log_file(self):
        """打开新的日志文件"""
        # 生成日志文件名: events.YYYY-MM-DD.log 或 events.YYYY-MM-DD-HH-MM-SS.log
        current_date = datetime.now().strftime("%Y-%m-%d")
        base_filename = f"events.{current_date}.log"
        log_file_path = self.logs_path / base_filename
        
        # 如果文件已存在且大小接近限制，添加时间戳
        if log_file_path.exists():
            file_size = log_file_path.stat().st_size
            if file_size >= self.max_file_size_bytes * 0.9:  # 90% of limit
                timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
                base_filename = f"events.{timestamp}.log"
                log_file_path = self.logs_path / base_filename
        
        # 打开文件（追加模式）
        self.current_log_file = log_file_path
        self.current_file_handle = open(log_file_path, "a", encoding="utf-8")
        
        logger.info(f"Opened log file: {log_file_path}")

    async def _cleanup_old_logs(self):
        """清理旧的日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            
            # 查找所有日志文件
            log_files = list(self.logs_path.glob("events.*.log"))
            
            for log_file in log_files:
                # 从文件名提取日期
                file_date_str = self._extract_date_from_filename(log_file.name)
                if not file_date_str:
                    continue
                
                try:
                    file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                    
                    # 如果文件超过保留期限，删除它
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info(f"Deleted old log file: {log_file}")
                        
                except ValueError:
                    logger.warning(f"Could not parse date from filename: {log_file.name}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}", exc_info=True)

    def _extract_date_from_filename(self, filename: str) -> Optional[str]:
        """从文件名提取日期
        
        Args:
            filename: 文件名，如 "events.2025-11-26.log"
        
        Returns:
            日期字符串 "YYYY-MM-DD" 或 None
        """
        # 匹配 events.YYYY-MM-DD.log 或 events.YYYY-MM-DD-HH-MM-SS.log
        match = re.search(r'events\.(\d{4}-\d{2}-\d{2})', filename)
        if match:
            return match.group(1)
        return None

    def get_all_log_files(self) -> List[Path]:
        """获取所有日志文件，按时间倒序排列
        
        Returns:
            日志文件路径列表
        """
        log_files = list(self.logs_path.glob("events.*.log"))
        # 按修改时间倒序排序（最新的在前）
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return log_files

