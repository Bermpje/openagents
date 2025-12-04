#!/usr/bin/env python3
"""
Bulk Agent Manager for OpenAgents

This module provides utilities for discovering, starting, and managing multiple agents
from a directory of YAML configuration files.
"""
import sys, asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import asyncio
import logging
import yaml
import signal
import sys
import os
import ast
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from datetime import datetime

from openagents.agents.runner import AgentRunner

logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """Information about an agent configuration."""
    config_path: Path
    agent_id: str
    agent_type: str
    connection_settings: Dict
    file_type: str = "yaml"  # "yaml" or "python"
    is_valid: bool = True
    error_message: Optional[str] = None


@dataclass
class AgentInstance:
    """A running agent instance."""
    info: AgentInfo
    runner: Optional[AgentRunner] = None
    process: Optional[subprocess.Popen] = None  # Legacy sync process (deprecated)
    async_process: Optional[asyncio.subprocess.Process] = None  # Async subprocess for log capture
    status: str = "stopped"  # stopped, starting, running, error, stopping
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    log_buffer: List[str] = None  # Buffer for captured logs (max 1000 lines)
    log_queue: Optional[asyncio.Queue] = None  # Queue for real-time log streaming
    pid: Optional[int] = None
    exit_code: Optional[int] = None  # Process exit code when stopped
    
    def __post_init__(self):
        if self.log_buffer is None:
            self.log_buffer = []
        if self.log_queue is None:
            self.log_queue = asyncio.Queue()


class BulkAgentManager:
    """Manages multiple agents from YAML configurations in a directory."""
    
    def __init__(self):
        self.agents: Dict[str, AgentInstance] = {}
        self.running = False
        self._shutdown_event = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="AgentRunner")
        self._setup_grpc_environment()
        self._setup_error_filtering()
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    def _setup_grpc_environment(self):
        """Configure gRPC environment to prevent BlockingIOError."""
        # Aggressive gRPC optimization to prevent resource errors
        os.environ['GRPC_POLL_STRATEGY'] = 'poll'  # Use more stable polling
        os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '1'
        os.environ['GRPC_SO_REUSEPORT'] = '0'  # Disable to prevent conflicts
        
        # Minimize gRPC resource usage
        os.environ['GRPC_VERBOSITY'] = 'NONE'
        os.environ['GRPC_TRACE'] = ''
        
        # Set resource limits to prevent overload
        os.environ['GRPC_MAX_SEND_MESSAGE_LENGTH'] = '4194304'  # 4MB
        os.environ['GRPC_MAX_RECEIVE_MESSAGE_LENGTH'] = '4194304'  # 4MB
        
        # Configure asyncio to handle more concurrent connections
        try:
            import asyncio
            if hasattr(asyncio, 'set_event_loop_policy'):
                # Use a more robust event loop policy
                if sys.platform != 'win32':
                    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        except Exception:
            pass
    
    def _setup_error_filtering(self):
        """Setup logging filter to suppress BlockingIOError messages."""
        class BlockingIOErrorFilter(logging.Filter):
            def filter(self, record):
                # Suppress BlockingIOError and gRPC connection messages
                if hasattr(record, 'msg'):
                    msg = str(record.msg)
                    if any(pattern in msg for pattern in [
                        'BlockingIOError',
                        'Resource temporarily unavailable',
                        'PollerCompletionQueue._handle_events',
                        'failed to connect to all addresses',
                        'Connection refused'
                    ]):
                        return False
                return True
        
        # Apply filter to root logger and asyncio logger
        root_logger = logging.getLogger()
        asyncio_logger = logging.getLogger('asyncio')
        grpc_logger = logging.getLogger('grpc')
        
        blocker_filter = BlockingIOErrorFilter()
        root_logger.addFilter(blocker_filter)
        asyncio_logger.addFilter(blocker_filter)
        grpc_logger.addFilter(blocker_filter)
        
    def discover_agents(self, directory: Path) -> List[AgentInfo]:
        """Discover and validate agent configurations in a directory.
        
        Args:
            directory: Directory to scan for YAML and Python files
            
        Returns:
            List of AgentInfo objects for valid agent configurations
        """
        agent_configs = []
        
        # Find YAML files
        yaml_files = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
        
        # Find Python files
        python_files = list(directory.glob("*.py"))
        
        all_files = yaml_files + python_files
        
        if not all_files:
            logger.warning(f"No YAML or Python agent files found in {directory}")
            return []
        
        logger.info(f"Found {len(yaml_files)} YAML files and {len(python_files)} Python files")
        
        # Process YAML files
        for yaml_file in yaml_files:
            try:
                agent_info = self._parse_agent_config(yaml_file)
                if agent_info:
                    agent_configs.append(agent_info)
            except Exception as e:
                logger.error(f"Error parsing {yaml_file}: {e}")
                # Still add invalid configs for user feedback
                agent_configs.append(AgentInfo(
                    config_path=yaml_file,
                    agent_id=yaml_file.stem,
                    agent_type="unknown",
                    connection_settings={},
                    file_type="yaml",
                    is_valid=False,
                    error_message=str(e)
                ))
        
        # Process Python files
        for python_file in python_files:
            try:
                agent_info = self._parse_python_agent(python_file)
                if agent_info:
                    agent_configs.append(agent_info)
            except Exception as e:
                logger.error(f"Error parsing {python_file}: {e}")
                # Still add invalid configs for user feedback
                agent_configs.append(AgentInfo(
                    config_path=python_file,
                    agent_id=python_file.stem,
                    agent_type="python_agent",
                    connection_settings={},
                    file_type="python",
                    is_valid=False,
                    error_message=str(e)
                ))
        
        return agent_configs
    
    def _parse_agent_config(self, config_path: Path) -> Optional[AgentInfo]:
        """Parse a single YAML agent configuration.
        
        Args:
            config_path: Path to the YAML configuration file
            
        Returns:
            AgentInfo if valid agent config, None if not an agent config
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check if this is an agent configuration (not a network config)
            if not config or 'type' not in config:
                logger.debug(f"Skipping {config_path}: not an agent config (no 'type' field)")
                return None
            
            # Skip network configurations
            if 'network' in config and 'agent_id' not in config:
                logger.debug(f"Skipping {config_path}: appears to be a network config")
                return None
            
            # Extract agent information
            agent_type = config.get('type', 'unknown')
            agent_id = config.get('agent_id', config_path.stem)
            connection_settings = config.get('connection', {})
            
            return AgentInfo(
                config_path=config_path,
                agent_id=agent_id,
                agent_type=agent_type,
                connection_settings=connection_settings,
                file_type="yaml",
                is_valid=True
            )
            
        except Exception as e:
            logger.error(f"Error parsing config {config_path}: {e}")
            raise
    
    def _parse_python_agent(self, python_path: Path) -> Optional[AgentInfo]:
        """Parse a single Python agent file.
        
        Args:
            python_path: Path to the Python agent file
            
        Returns:
            AgentInfo if valid Python agent, None if not an agent file
        """
        try:
            with open(python_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the Python file using AST
            tree = ast.parse(content, filename=str(python_path))
            
            agent_class = None
            agent_id = None
            default_network_host = "localhost"
            default_network_port = 8700
            
            # Look for agent class definitions and metadata
            for node in ast.walk(tree):
                # Find classes that inherit from agent base classes
                if isinstance(node, ast.ClassDef):
                    # Check if it inherits from known agent classes
                    for base in node.bases:
                        base_name = self._get_ast_name(base)
                        if base_name in ['WorkerAgent', 'SimpleAgent', 'CollaboratorAgent', 'AgentRunner']:
                            agent_class = node.name
                            break
                
                # Look for default_agent_id attribute
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'default_agent_id':
                            if isinstance(node.value, ast.Constant):
                                agent_id = node.value.value
                
                # Look for network connection calls in main() or start()
                if isinstance(node, ast.Call):
                    func_name = self._get_ast_name(node.func)
                    if func_name in ['start', 'async_start']:
                        # Extract network_host and network_port from arguments
                        for keyword in node.keywords:
                            if keyword.arg == 'network_host':
                                if isinstance(keyword.value, ast.Constant):
                                    default_network_host = keyword.value.value
                            elif keyword.arg == 'network_port':
                                if isinstance(keyword.value, ast.Constant):
                                    default_network_port = keyword.value.value
            
            # Check if this looks like an agent file
            if not agent_class:
                logger.debug(f"Skipping {python_path}: no agent class found")
                return None
            
            # Check for if __name__ == "__main__" block
            has_main_block = any(
                isinstance(node, ast.If) and 
                isinstance(node.test, ast.Compare) and
                isinstance(node.test.left, ast.Name) and
                node.test.left.id == '__name__' and
                any(isinstance(comp, ast.Constant) and comp.value == '__main__' 
                    for comp in node.test.comparators)
                for node in tree.body
            )
            
            if not has_main_block:
                logger.debug(f"Skipping {python_path}: no __main__ block found")
                return None
            
            # Use filename as agent_id if not found in code
            if not agent_id:
                agent_id = python_path.stem
            
            return AgentInfo(
                config_path=python_path,
                agent_id=agent_id,
                agent_type=agent_class,
                connection_settings={
                    "host": default_network_host,
                    "port": default_network_port
                },
                file_type="python",
                is_valid=True
            )
            
        except Exception as e:
            logger.error(f"Error parsing Python file {python_path}: {e}")
            raise
    
    def _get_ast_name(self, node: ast.AST) -> str:
        """Extract name from an AST node (handles Name, Attribute, etc.)."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_ast_name(node.func)
        return ""
    
    def add_agents(self, agent_infos: List[AgentInfo]) -> None:
        """Add agent configurations to the manager.
        
        Args:
            agent_infos: List of agent configurations to add
        """
        for info in agent_infos:
            if info.agent_id in self.agents:
                logger.warning(f"Agent ID '{info.agent_id}' already exists, skipping")
                continue
                
            self.agents[info.agent_id] = AgentInstance(info=info)
    
    async def start_agent(self, agent_id: str, connection_override: Optional[Dict] = None) -> bool:
        """Start a single agent using subprocess.
        
        Args:
            agent_id: ID of the agent to start
            connection_override: Optional connection settings to override config
            
        Returns:
            True if agent started successfully, False otherwise
        """
        if agent_id not in self.agents:
            logger.error(f"Agent '{agent_id}' not found")
            return False
        
        agent_instance = self.agents[agent_id]
        
        if not agent_instance.info.is_valid:
            logger.error(f"Agent '{agent_id}' has invalid configuration: {agent_instance.info.error_message}")
            agent_instance.status = "error"
            agent_instance.error_message = agent_instance.info.error_message
            return False
        
        if agent_instance.status == "running":
            logger.warning(f"Agent '{agent_id}' is already running")
            return True
        
        try:
            agent_instance.status = "starting"
            agent_instance.start_time = time.time()
            agent_instance.error_message = None
            
            # Prepare connection settings
            connection_settings = agent_instance.info.connection_settings.copy()
            if connection_override:
                connection_settings.update(connection_override)
            
            # Build command based on file type
            if agent_instance.info.file_type == "yaml":
                # YAML agent: use openagents CLI
                cmd = [
                    sys.executable, "-m", "openagents.cli", "agent", "start",
                    str(agent_instance.info.config_path)
                ]
                
                # Add connection overrides as CLI arguments
                if connection_settings.get("host"):
                    cmd.extend(["--network-host", connection_settings["host"]])
                if connection_settings.get("port"):
                    cmd.extend(["--network-port", str(connection_settings["port"])])
                if connection_settings.get("network_id"):
                    cmd.extend(["--network-id", connection_settings["network_id"]])
            
            elif agent_instance.info.file_type == "python":
                # Python agent: direct execution
                # cmd = [sys.executable, str(agent_instance.info.config_path)]
                # cmd = [sys.executable, str(agent_instance.info.config_path.resolve())]
                # cmd = [sys.executable, "-u", str(agent_instance.info.config_path)]
                cmd = [sys.executable, "-u", str(agent_instance.info.config_path.resolve())]
                print("=== CMD:", cmd, "===")

            else:
                raise ValueError(f"Unsupported file type: {agent_instance.info.file_type}")
            
            # Set environment variables for Python agents
            env = os.environ.copy()
            if agent_instance.info.file_type == "python":
                env["OPENAGENTS_NETWORK_HOST"] = connection_settings.get("host", "localhost")
                env["OPENAGENTS_NETWORK_PORT"] = str(connection_settings.get("port", 8700))
                if connection_settings.get("network_id"):
                    env["OPENAGENTS_NETWORK_ID"] = connection_settings["network_id"]
            
            # Set working directory to the agent file's directory
            # cwd = agent_instance.info.config_path.parent
            # cwd = str(agent_instance.info.config_path.parent.resolve())

            
            # Start async subprocess for better log capture
            logger.info(f"Starting {agent_instance.info.file_type} agent '{agent_id}' with command: {' '.join(cmd)}")
            # async_process = await asyncio.create_subprocess_exec(
            #     *cmd,
            #     stdout=asyncio.subprocess.PIPE,
            #     stderr=asyncio.subprocess.PIPE,
            #     cwd=cwd,
            #     env=env
            # )

            async_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            agent_instance.async_process = async_process
            agent_instance.pid = async_process.pid
            agent_instance.status = "running"
            
            logger.info(f"Agent '{agent_id}' started successfully with PID {async_process.pid}")
            
            # Start log capture in background
            asyncio.create_task(self._capture_logs(agent_instance))
            
            # Start process monitoring in background
            asyncio.create_task(self._monitor_process_logs(agent_instance))
            
            return True
            
        except Exception as e:
            agent_instance.status = "error" 
            agent_instance.error_message = str(e)
            logger.error(f"Failed to start agent '{agent_id}': {e}", exc_info=True)
            return False
    
    async def _capture_logs(self, agent_instance: AgentInstance) -> None:
        """Capture stdout and stderr from async subprocess in parallel.
        
        Reads logs asynchronously, adds timestamps, and pushes to both
        log_queue (for real-time UI streaming) and log_buffer (for history).
        Automatically trims log_buffer to max 1000 lines.
        
        Args:
            agent_instance: Agent instance with async_process to capture from
        """
        if not agent_instance.async_process:
            return
        
        agent_id = agent_instance.info.agent_id
        logger.debug(f"Starting log capture for agent '{agent_id}'")
        
        async def read_stream(stream, stream_name: str):
            """Read from a single stream (stdout or stderr) and process logs."""
            try:
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        # Stream closed
                        break
                    
                    # Decode and strip newline
                    line = line_bytes.decode('utf-8', errors='replace').rstrip()
                    
                    # Add timestamp
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Add [STDERR] prefix for stderr lines
                    if stream_name == "stderr":
                        formatted_line = f"[{timestamp}] [STDERR] {line}"
                    else:
                        formatted_line = f"[{timestamp}] {line}"
                    
                    # Push to log queue for real-time UI streaming (non-blocking)
                    try:
                        agent_instance.log_queue.put_nowait(formatted_line)
                    except asyncio.QueueFull:
                        # Drop oldest log if queue is full (shouldn't happen with unbounded queue)
                        pass
                    
                    # Append to log buffer
                    agent_instance.log_buffer.append(formatted_line)
                    
                    # Trim log buffer to max 1000 lines
                    if len(agent_instance.log_buffer) > 1000:
                        agent_instance.log_buffer = agent_instance.log_buffer[-1000:]
                    
            except Exception as e:
                logger.debug(f"Log capture {stream_name} ended for agent '{agent_id}': {e}")
            finally:
                # Close stream to prevent resource leaks
                try:
                    stream.close()
                except Exception:
                    pass
        
        try:
            # Read stdout and stderr in parallel
            await asyncio.gather(
                read_stream(agent_instance.async_process.stdout, "stdout"),
                read_stream(agent_instance.async_process.stderr, "stderr"),
                return_exceptions=True
            )
            logger.debug(f"Log capture completed for agent '{agent_id}'")
        except Exception as e:
            logger.error(f"Error in log capture for agent '{agent_id}': {e}")
        finally:
            # Ensure streams are closed
            try:
                if agent_instance.async_process:
                    if agent_instance.async_process.stdout:
                        agent_instance.async_process.stdout.close()
                    if agent_instance.async_process.stderr:
                        agent_instance.async_process.stderr.close()
            except Exception:
                pass
    
    async def _monitor_process_logs(self, agent_instance: AgentInstance) -> None:
        """Monitor subprocess status and track exit code."""
        if not agent_instance.async_process:
            return
        
        agent_id = agent_instance.info.agent_id
        
        try:
            # Wait for process to complete
            exit_code = await agent_instance.async_process.wait()
            
            # Store exit code
            agent_instance.exit_code = exit_code
            
            # Update status based on exit code
            if exit_code != 0:
                agent_instance.status = "error"
                agent_instance.error_message = f"Process exited with code {exit_code}"
                logger.error(f"Agent '{agent_id}' process exited with code {exit_code}")
                
                # Add error message to log
                error_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [ERROR] Process terminated with exit code {exit_code}"
                agent_instance.log_buffer.append(error_msg)
                try:
                    agent_instance.log_queue.put_nowait(error_msg)
                except asyncio.QueueFull:
                    pass
            else:
                agent_instance.status = "stopped"
                logger.info(f"Agent '{agent_id}' process ended normally")
                
                # Add stop message to log
                stop_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [INFO] Process stopped (exit code 0)"
                agent_instance.log_buffer.append(stop_msg)
                try:
                    agent_instance.log_queue.put_nowait(stop_msg)
                except asyncio.QueueFull:
                    pass
        
        except Exception as e:
            logger.error(f"Error monitoring process for agent '{agent_id}': {e}")
            agent_instance.status = "error"
            agent_instance.error_message = f"Process monitoring error: {e}"
            agent_instance.exit_code = -1
    
    async def start_all_agents(
        self,
        connection_override: Optional[Dict] = None,
        max_concurrent: int = 3  # Reduced default to minimize gRPC resource contention
    ) -> Dict[str, bool]:
        """Start all agents concurrently with gRPC error handling.
        
        Args:
            connection_override: Optional connection settings to override all agent configs
            max_concurrent: Maximum number of agents to start concurrently (reduced default)
            
        Returns:
            Dictionary mapping agent_id to success status
        """
        if not self.agents:
            logger.warning("No agents to start")
            return {}
        
        self.running = True
        
        # Reduce concurrency further for gRPC stability
        effective_max_concurrent = min(max_concurrent, 2)
        logger.info(f"Starting agents with max concurrency: {effective_max_concurrent}")
        
        # Create semaphore to limit concurrent startups
        semaphore = asyncio.Semaphore(effective_max_concurrent)
        
        async def start_single_agent(agent_id: str) -> Tuple[str, bool]:
            async with semaphore:
                # Add delay between agent starts to prevent resource conflicts
                await asyncio.sleep(1.0)
                success = await self.start_agent(agent_id, connection_override)
                # Add delay after startup to allow stabilization
                await asyncio.sleep(2.0)
                return agent_id, success
        
        # Start all agents concurrently
        tasks = [
            start_single_agent(agent_id) 
            for agent_id in self.agents.keys() 
            if self.agents[agent_id].info.is_valid
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        success_map = {}
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Error in agent startup: {result}")
                continue
            agent_id, success = result
            success_map[agent_id] = success
        
        return success_map
    
    async def stop_agent_async(self, agent_id: str) -> bool:
        """Stop a single agent subprocess asynchronously (graceful shutdown).
        
        Args:
            agent_id: ID of the agent to stop
            
        Returns:
            True if agent stopped successfully, False otherwise
        """
        if agent_id not in self.agents:
            logger.error(f"Agent '{agent_id}' not found")
            return False
        
        agent_instance = self.agents[agent_id]
        
        if agent_instance.status not in ["running", "starting"]:
            logger.warning(f"Agent '{agent_id}' is not running (status: {agent_instance.status})")
            return True
        
        try:
            agent_instance.status = "stopping"
            
            # Stop async process (preferred)
            if agent_instance.async_process:
                logger.info(f"Terminating agent '{agent_id}' with PID {agent_instance.async_process.pid}")
                
                # Close pipes first to prevent resource warnings on Windows
                try:
                    if agent_instance.async_process.stdout:
                        agent_instance.async_process.stdout.close()
                    if agent_instance.async_process.stderr:
                        agent_instance.async_process.stderr.close()
                except Exception:
                    pass  # Ignore errors closing pipes
                
                # Try graceful SIGTERM first
                agent_instance.async_process.terminate()
                
                # Wait for graceful termination (5 seconds)
                try:
                    await asyncio.wait_for(agent_instance.async_process.wait(), timeout=5.0)
                    logger.info(f"Agent '{agent_id}' terminated gracefully")
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    logger.warning(f"Agent '{agent_id}' didn't terminate gracefully, sending SIGKILL")
                    agent_instance.async_process.kill()
                    await agent_instance.async_process.wait()
                
                agent_instance.async_process = None
                agent_instance.pid = None
            
            # Also stop runner if it exists (backward compatibility)
            if agent_instance.runner:
                agent_instance.runner.stop()
                agent_instance.runner = None
            
            agent_instance.status = "stopped"
            logger.info(f"Agent '{agent_id}' stopped successfully")
            return True
            
        except Exception as e:
            import traceback
            traceback.print_exc()

            logger.error(f"Error stopping agent '{agent_id}': {e}")
            agent_instance.status = "error"
            agent_instance.error_message = str(e)
            return False
    
    def stop_agent(self, agent_id: str) -> bool:
        """Stop a single agent subprocess (synchronous wrapper).
        
        Args:
            agent_id: ID of the agent to stop
            
        Returns:
            True if agent stopped successfully, False otherwise
        """
        # Try to get the current event loop
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - cannot block, just create task
            task = asyncio.create_task(self.stop_agent_async(agent_id))
            # Return True immediately - actual stop is async
            return True
        except RuntimeError:
            # Not in async context - safe to create new event loop
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(self.stop_agent_async(agent_id))
            except Exception as e:
                logger.error(f"Error in stop_agent: {e}")
                return False
    
    async def stop_all_agents_async(self) -> Dict[str, bool]:
        """Stop all running agents asynchronously.
        
        Returns:
            Dictionary mapping agent_id to success status
        """
        self.running = False
        self._shutdown_event.set()
        
        # Stop all agents concurrently
        tasks = []
        agent_ids = list(self.agents.keys())
        
        for agent_id in agent_ids:
            task = self.stop_agent_async(agent_id)
            tasks.append((agent_id, task))
        
        results = {}
        if tasks:
            # Wait for all stop operations to complete
            stop_results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            
            for i, (agent_id, _) in enumerate(tasks):
                if isinstance(stop_results[i], Exception):
                    logger.error(f"Error stopping agent '{agent_id}': {stop_results[i]}")
                    results[agent_id] = False
                else:
                    results[agent_id] = stop_results[i]
        
        return results
    
    def stop_all_agents(self) -> Dict[str, bool]:
        """Stop all running agents (synchronous wrapper).
        
        Returns:
            Dictionary mapping agent_id to success status
        """
        self.running = False
        self._shutdown_event.set()
        
        # Try to use async version if possible
        try:
            loop = asyncio.get_running_loop()
            # In async context - create task but can't wait for results
            asyncio.create_task(self.stop_all_agents_async())
            # Return optimistic results
            return {agent_id: True for agent_id in self.agents.keys()}
        except RuntimeError:
            # Not in async context - safe to run async code
            try:
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                return loop.run_until_complete(self.stop_all_agents_async())
            except Exception as e:
                logger.error(f"Error in stop_all_agents: {e}")
                return {agent_id: False for agent_id in self.agents.keys()}
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict]:
        """Get status information for an agent.
        
        Args:
            agent_id: ID of the agent
            
        Returns:
            Dictionary with agent status information, None if agent not found
        """
        if agent_id not in self.agents:
            return None
        
        agent_instance = self.agents[agent_id]
        
        status = {
            "agent_id": agent_id,
            "config_path": str(agent_instance.info.config_path),
            "agent_type": agent_instance.info.agent_type,
            "file_type": agent_instance.info.file_type,
            "status": agent_instance.status,
            "is_valid": agent_instance.info.is_valid,
            "error_message": agent_instance.error_message,
            "start_time": agent_instance.start_time,
            "uptime": time.time() - agent_instance.start_time if agent_instance.start_time else None,
            "pid": agent_instance.pid,
            "exit_code": agent_instance.exit_code  # Exit code when process stopped
        }
        
        return status
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status information for all agents.
        
        Returns:
            Dictionary mapping agent_id to status information
        """
        return {
            agent_id: self.get_agent_status(agent_id)
            for agent_id in self.agents.keys()
        }
    
    def get_running_agents(self) -> List[str]:
        """Get list of currently running agent IDs.
        
        Returns:
            List of agent IDs with status 'running'
        """
        return [
            agent_id for agent_id, instance in self.agents.items()
            if instance.status == "running"
        ]
    
    def get_agent_logs(self, agent_id: str, max_lines: int = 100) -> List[str]:
        """Get recent log entries for an agent.
        
        Args:
            agent_id: ID of the agent
            max_lines: Maximum number of log lines to return
            
        Returns:
            List of log lines, empty if agent not found
        """
        if agent_id not in self.agents:
            return []
        
        agent_instance = self.agents[agent_id]
        return agent_instance.log_buffer[-max_lines:] if agent_instance.log_buffer else []
    
    def shutdown(self) -> None:
        """Shutdown the bulk agent manager and clean up resources."""
        logger.info("Shutting down BulkAgentManager...")
        
        # Stop all agents
        self.stop_all_agents()
        
        # Shutdown executor
        self._executor.shutdown(wait=True)
        
        logger.info("BulkAgentManager shutdown complete")