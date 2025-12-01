"""
测试事件日志系统

测试事件日志记录、切割、清理和检索功能
"""

import asyncio
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from openagents.core.event_logging import EventLogEntry, EventLogWriter
from openagents.models.event import Event, EventVisibility


class TestEventLogEntry:
    """测试 EventLogEntry 数据结构"""

    def test_from_event_inbound(self):
        """测试从 Event 创建 inbound 日志条目"""
        event = Event(
            event_name="agent.message",
            source_id="agent:alice",
            destination_id="agent:bob",
            payload={"content": "Hello"},
            visibility=EventVisibility.DIRECT,
        )
        
        entry = EventLogEntry.from_event(event, direction="inbound")
        
        assert entry.direction == "inbound"
        assert entry.event_name == "agent.message"
        assert entry.source_id == "agent:alice"
        assert entry.destination_id == "agent:bob"
        assert entry.payload == {"content": "Hello"}
        assert entry.visibility == "direct"
        assert entry.request_id == event.event_id

    def test_from_event_outbound(self):
        """测试从 Event 创建 outbound 日志条目"""
        event = Event(
            event_name="project.run.completed",
            source_id="agent:worker",
            destination_id="agent:manager",
            payload={"result": "success"},
            visibility=EventVisibility.NETWORK,
            response_to="prev-event-id",
        )
        
        entry = EventLogEntry.from_event(event, direction="outbound")
        
        assert entry.direction == "outbound"
        assert entry.event_name == "project.run.completed"
        assert entry.response_to == "prev-event-id"

    def test_to_dict(self):
        """测试转换为字典"""
        event = Event(
            event_name="system.health_check",
            source_id="system:system",
            payload={},
        )
        
        entry = EventLogEntry.from_event(event, direction="inbound")
        data = entry.to_dict()
        
        assert isinstance(data, dict)
        assert "timestamp" in data
        assert "direction" in data
        assert "event_name" in data
        assert data["event_name"] == "system.health_check"

    def test_to_json(self):
        """测试转换为 JSON"""
        event = Event(
            event_name="channel.message.posted",
            source_id="agent:alice",
            destination_id="channel:general",
            payload={"text": "Hello channel"},
        )
        
        entry = EventLogEntry.from_event(event, direction="inbound")
        json_str = entry.to_json()
        
        # 验证可以解析回来
        parsed = json.loads(json_str)
        assert parsed["event_name"] == "channel.message.posted"
        assert parsed["payload"]["text"] == "Hello channel"


class TestEventLogWriter:
    """测试 EventLogWriter"""

    @pytest.fixture
    async def temp_logs_dir(self):
        """创建临时日志目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_initialization(self, temp_logs_dir):
        """测试日志写入器初始化"""
        writer = EventLogWriter(
            logs_path=temp_logs_dir,
            max_file_size_mb=10,
            retention_days=7,
        )
        
        assert writer.logs_path == temp_logs_dir
        assert writer.max_file_size_bytes == 10 * 1024 * 1024
        assert writer.retention_days == 7
        assert not writer.running

    @pytest.mark.asyncio
    async def test_start_stop(self, temp_logs_dir):
        """测试启动和停止"""
        writer = EventLogWriter(logs_path=temp_logs_dir)
        
        await writer.start()
        assert writer.running
        assert writer.task is not None
        
        await writer.stop()
        assert not writer.running

    @pytest.mark.asyncio
    async def test_log_event(self, temp_logs_dir):
        """测试记录事件"""
        writer = EventLogWriter(logs_path=temp_logs_dir)
        await writer.start()
        
        # 创建测试事件
        event = Event(
            event_name="test.event.created",
            source_id="agent:test",
            destination_id="agent:receiver",
            payload={"data": "test"},
        )
        entry = EventLogEntry.from_event(event, direction="inbound")
        
        # 记录事件
        await writer.log_event(entry)
        
        # 等待写入
        await asyncio.sleep(0.5)
        await writer.stop()
        
        # 验证文件创建
        log_files = list(temp_logs_dir.glob("events.*.log"))
        assert len(log_files) == 1
        
        # 验证内容
        with open(log_files[0], 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            log_data = json.loads(lines[0])
            assert log_data["event_name"] == "test.event.created"
            assert log_data["source_id"] == "agent:test"
            assert log_data["direction"] == "inbound"

    @pytest.mark.asyncio
    async def test_multiple_events(self, temp_logs_dir):
        """测试记录多个事件"""
        writer = EventLogWriter(logs_path=temp_logs_dir)
        await writer.start()
        
        # 记录多个事件
        for i in range(5):
            event = Event(
                event_name=f"test.event.number_{i}",
                source_id=f"agent:sender_{i}",
                destination_id=f"agent:receiver_{i}",
                payload={"index": i},
            )
            entry = EventLogEntry.from_event(event, direction="inbound")
            await writer.log_event(entry)
        
        # 等待写入
        await asyncio.sleep(0.5)
        await writer.stop()
        
        # 验证所有事件都被记录
        log_files = list(temp_logs_dir.glob("events.*.log"))
        assert len(log_files) == 1
        
        with open(log_files[0], 'r') as f:
            lines = f.readlines()
            assert len(lines) == 5
            
            for i, line in enumerate(lines):
                log_data = json.loads(line)
                assert log_data["event_name"] == f"test.event.number_{i}"
                assert log_data["payload"]["index"] == i

    @pytest.mark.asyncio
    async def test_file_rotation_by_size(self, temp_logs_dir):
        """测试基于大小的日志切割"""
        # 使用很小的文件大小限制来触发切割
        writer = EventLogWriter(
            logs_path=temp_logs_dir,
            max_file_size_mb=0.001,  # 1KB
        )
        await writer.start()
        
        # 记录大量事件以触发切割
        for i in range(50):
            event = Event(
                event_name=f"test.large.event_num_{i}",
                source_id=f"agent:sender_{i}",
                destination_id=f"agent:receiver_{i}",
                payload={"data": "x" * 100},  # 较大的payload
            )
            entry = EventLogEntry.from_event(event, direction="inbound")
            await writer.log_event(entry)
            await asyncio.sleep(0.01)  # 稍微延迟以便写入
        
        # 等待写入完成
        await asyncio.sleep(1)
        await writer.stop()
        
        # 应该创建了多个日志文件
        log_files = list(temp_logs_dir.glob("events.*.log"))
        assert len(log_files) > 1

    @pytest.mark.asyncio
    async def test_get_all_log_files(self, temp_logs_dir):
        """测试获取所有日志文件"""
        writer = EventLogWriter(logs_path=temp_logs_dir)
        
        # 手动创建一些日志文件
        (temp_logs_dir / "events.2025-11-25.log").touch()
        await asyncio.sleep(0.1)
        (temp_logs_dir / "events.2025-11-26.log").touch()
        await asyncio.sleep(0.1)
        (temp_logs_dir / "events.2025-11-27.log").touch()
        
        log_files = writer.get_all_log_files()
        
        # 应该按时间倒序排列
        assert len(log_files) == 3
        assert log_files[0].name == "events.2025-11-27.log"
        assert log_files[2].name == "events.2025-11-25.log"

    @pytest.mark.asyncio
    async def test_extract_date_from_filename(self, temp_logs_dir):
        """测试从文件名提取日期"""
        writer = EventLogWriter(logs_path=temp_logs_dir)
        
        assert writer._extract_date_from_filename("events.2025-11-26.log") == "2025-11-26"
        assert writer._extract_date_from_filename("events.2025-11-26-14-30-45.log") == "2025-11-26"
        assert writer._extract_date_from_filename("other.log") is None


@pytest.mark.asyncio
async def test_event_logging_integration():
    """集成测试：测试事件日志在网络中的完整流程
    
    注意：这个测试需要完整的网络环境，可能需要根据实际情况调整
    """
    # 这个测试作为示例，实际运行可能需要完整的网络设置
    pass

