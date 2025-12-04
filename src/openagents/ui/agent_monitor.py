#!/usr/bin/env python3
"""
Agent Monitor - Textual-based tabbed interface for monitoring multiple agents

This module provides a beautiful terminal UI for monitoring multiple agent logs
in real-time using tabs, with keyboard navigation and search capabilities.
"""
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
import asyncio
import logging
import sys
from datetime import datetime
from typing import Dict, List, Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    TabbedContent, TabPane, Header, Footer, Static, 
    Log, Button, Input, Label, DataTable
)
from textual.reactive import reactive
from textual.message import Message
from textual.binding import Binding

from openagents.utils.bulk_agent_manager import BulkAgentManager, AgentInstance


class AgentLogWidget(Log):
    """Enhanced log widget for displaying agent logs with color coding."""
    
    # Store agent_id and auto_scroll as class attributes to avoid initialization issues
    agent_id: str = ""
    auto_scroll: bool = True
    
    def write_agent_log(self, message: str, level: str = "INFO"):
        """Write a log message with appropriate color coding."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Color code by log level
        if level == "ERROR":
            styled_message = f"[red]{timestamp}[/red] [bold red]ERROR[/bold red] {message}"
        elif level == "WARNING" or level == "WARN":
            styled_message = f"[yellow]{timestamp}[/yellow] [bold yellow]WARN[/bold yellow] {message}"
        elif level == "DEBUG":
            styled_message = f"[dim]{timestamp} DEBUG {message}[/dim]"
        else:  # INFO or default
            styled_message = f"[dim]{timestamp}[/dim] [green]INFO[/green] {message}"
        
        self.write_line(styled_message)
        
        if self.auto_scroll:
            self.scroll_end()


class StatusWidget(Static):
    """Widget displaying overall agent status summary."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_count = 0
        self.running_count = 0
        self.error_count = 0
    
    def update_status(self, agent_statuses: Dict[str, Dict]):
        """Update status display with current agent information."""
        self.agent_count = len(agent_statuses)
        self.running_count = sum(1 for s in agent_statuses.values() if s.get('status') == 'running')
        self.error_count = sum(1 for s in agent_statuses.values() if s.get('status') == 'error')
        
        status_text = (
            f"[bold blue]Agents:[/bold blue] {self.agent_count} | "
            f"[bold green]Running:[/bold green] {self.running_count} | "
            f"[bold red]Errors:[/bold red] {self.error_count}"
        )
        
        self.update(status_text)


class AgentMonitorApp(App):
    """Main application for monitoring multiple agents with tabbed interface."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #main_container {
        height: 100%;
    }
    
    #status_bar {
        height: 1;
        background: $surface;
        color: $text;
        text-align: center;
    }
    
    TabbedContent {
        height: 100%;
    }
    
    TabPane {
        height: 100%;
        padding: 0;
    }
    
    AgentLogWidget {
        height: 100%;
        border: solid $primary;
    }
    
    #overview_table {
        height: 100%;
    }
    
    .status_running {
        background: $success;
        color: $text;
    }
    
    .status_error {
        background: $error;
        color: $text;
    }
    
    .status_starting {
        background: $warning;
        color: $text;
    }
    
    .status_stopped {
        background: $surface;
        color: $text-muted;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "show_overview", "Overview"),
        Binding("f", "toggle_autoscroll", "Auto-scroll"),
        Binding("c", "clear_current_log", "Clear Log"),
        ("tab", "next_tab", "Next Tab"),
        ("shift+tab", "prev_tab", "Previous Tab"),
    ]
    
    def __init__(self, bulk_manager: BulkAgentManager, **kwargs):
        super().__init__(**kwargs)
        self.bulk_manager = bulk_manager
        self.agent_logs: Dict[str, AgentLogWidget] = {}
        self.status_widget: Optional[StatusWidget] = None
        self.overview_table: Optional[DataTable] = None
        self.refresh_timer = None
        self.auto_refresh_interval = 2.0  # seconds
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header()
        
        with Container(id="main_container"):
            # Status bar
            self.status_widget = StatusWidget(id="status_bar")
            yield self.status_widget
            
            # Tabbed content for agent logs
            with TabbedContent():
                # Overview tab
                with TabPane("📊 Overview", id="overview"):
                    self.overview_table = DataTable(id="overview_table")
                    self.overview_table.add_columns("Agent ID", "Status", "File", "Type", "PID", "Uptime", "Config")
                    yield self.overview_table
                
                # Individual agent tabs
                for agent_id, agent_instance in self.bulk_manager.agents.items():
                    with TabPane(f"🤖 {agent_id}", id=f"tab_{agent_id}"):
                        log_widget = AgentLogWidget(id=f"log_{agent_id}")
                        log_widget.agent_id = agent_id  # Set agent_id after creation
                        log_widget.auto_scroll = True
                        self.agent_logs[agent_id] = log_widget
                        yield log_widget
        
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.title = "OpenAgents Monitor"
        self.sub_title = f"Monitoring {len(self.bulk_manager.agents)} agents"
        
        # Start auto-refresh timer
        self.refresh_timer = self.set_interval(self.auto_refresh_interval, self.refresh_display)
        
        # Start log streaming background task
        # asyncio.create_task(self.stream_logs_to_ui())
        self.run_worker(self.stream_logs_to_ui(), exclusive=False)

        # Initial refresh
        self.refresh_display()
    
    def on_unmount(self) -> None:
        """Called when the app is unmounted."""
        if self.refresh_timer:
            self.refresh_timer.stop()
    
    def refresh_display(self) -> None:
        """Refresh all display components with latest data."""
        try:
            # Update status bar
            if self.status_widget:
                agent_statuses = self.bulk_manager.get_all_status()
                self.status_widget.update_status(agent_statuses)
            
            # Update overview table
            self.refresh_overview_table()
            
            # Update agent logs (this would need integration with actual log capture)
            # For now, we'll just show status updates
            for agent_id in self.bulk_manager.agents.keys():
                self.update_agent_logs(agent_id)
                
        except Exception as e:
            # Log errors but don't crash the UI
            if "overview" in self.agent_logs:
                self.agent_logs["overview"].write_agent_log(f"Monitor error: {e}", "ERROR")
    
    def refresh_overview_table(self) -> None:
        """Refresh the overview table with current agent statuses.
        
        Displays comprehensive information including status, PID, uptime,
        file type, agent type, and config file. Status is color-coded:
        - Green: running
        - Yellow: starting
        - Red: error
        - Gray: stopped
        """
        if not self.overview_table:
            return
        
        # Clear existing rows
        self.overview_table.clear()
        
        # Add current agent data
        agent_statuses = self.bulk_manager.get_all_status()
        for agent_id, status in agent_statuses.items():
            if not status:
                continue
            
            # Format uptime
            uptime_str = "—"
            if status.get('uptime'):
                uptime = status['uptime']
                if uptime > 3600:
                    uptime_str = f"{uptime//3600:.0f}h {(uptime%3600)//60:.0f}m"
                elif uptime > 60:
                    uptime_str = f"{uptime//60:.0f}m {uptime%60:.0f}s"
                else:
                    uptime_str = f"{uptime:.0f}s"
            
            # Style status with color coding
            status_text = status.get('status', 'unknown')
            exit_code = status.get('exit_code')
            
            if status_text == 'running':
                status_display = f"[green]●[/green] running"
            elif status_text == 'error':
                if exit_code is not None:
                    status_display = f"[red]●[/red] error (exit: {exit_code})"
                else:
                    status_display = f"[red]●[/red] error"
            elif status_text == 'starting':
                status_display = f"[yellow]●[/yellow] starting"
            elif status_text == 'stopping':
                status_display = f"[yellow]●[/yellow] stopping"
            elif status_text == 'stopped':
                if exit_code is not None and exit_code != 0:
                    status_display = f"[dim]●[/dim] stopped (exit: {exit_code})"
                else:
                    status_display = f"[dim]●[/dim] stopped"
            else:
                status_display = f"[dim]●[/dim] {status_text}"
            
            # File type with icon
            file_type = status.get('file_type', 'yaml')
            file_icon = "🐍" if file_type == "python" else "📄"
            file_display = f"{file_icon} {file_type}"
            
            # PID display
            pid = status.get('pid')
            pid_display = str(pid) if pid else "—"
            
            # Config filename (extract just the filename from full path)
            config_path = status.get('config_path', '')
            if config_path:
                # Handle both Windows and Unix paths
                config_file = config_path.replace('\\', '/').split('/')[-1]
            else:
                config_file = "—"
            
            # Add row
            self.overview_table.add_row(
                agent_id,
                status_display,
                file_display,
                status.get('agent_type', 'unknown'),
                pid_display,
                uptime_str,
                config_file
            )
    
    def update_agent_logs(self, agent_id: str) -> None:
        """Update logs for a specific agent."""
        if agent_id not in self.agent_logs:
            return
        
        log_widget = self.agent_logs[agent_id]
        status = self.bulk_manager.get_agent_status(agent_id)
        
        if not status:
            return
        
        # Add status updates as log entries (in a real implementation, 
        # this would be actual log streaming from the agent)
        current_status = status.get('status', 'unknown')
        
        # Only log status changes to avoid spam
        if not hasattr(log_widget, '_last_status'):
            log_widget._last_status = None
        
        if current_status != log_widget._last_status:
            log_widget._last_status = current_status
            
            if current_status == 'starting':
                log_widget.write_agent_log("Agent startup initiated", "INFO")
            elif current_status == 'running':
                log_widget.write_agent_log("Agent is now running", "INFO")
            elif current_status == 'error':
                error_msg = status.get('error_message', 'Unknown error')
                exit_code = status.get('exit_code')
                if exit_code is not None:
                    log_widget.write_agent_log(f"Agent error: {error_msg} (exit code: {exit_code})", "ERROR")
                else:
                    log_widget.write_agent_log(f"Agent error: {error_msg}", "ERROR")
            elif current_status == 'stopped':
                exit_code = status.get('exit_code')
                if exit_code is not None and exit_code != 0:
                    log_widget.write_agent_log(f"Agent stopped (exit code: {exit_code})", "WARN")
                else:
                    log_widget.write_agent_log("Agent stopped", "INFO")
    
    async def stream_logs_to_ui(self) -> None:
        """Background task to stream logs from agent log queues to UI widgets.
        
        Continuously reads from each agent's log_queue and writes to the
        corresponding log widget. Handles auto-scroll and UI crashes gracefully.
        """
        try:
            while True:
                # Process logs for each agent
                for agent_id, agent_instance in self.bulk_manager.agents.items():
                    if agent_id not in self.agent_logs:
                        continue
                    
                    log_widget = self.agent_logs[agent_id]
                    
                    # Check if agent has log queue
                    if not agent_instance.log_queue:
                        continue
                    
                    # Read all available logs from queue (non-blocking)
                    logs_processed = 0
                    while not agent_instance.log_queue.empty() and logs_processed < 50:
                        # print(f"[DEBUG STREAM] {agent_id}: {log_line}")
                        # import sys
                        # sys.stdout.write(f"[RAW_LOG] {agent_id}: {log_line}\n")
                        try:
                            # log_line = agent_instance.log_queue.get_nowait()
                            log_line = agent_instance.log_queue.get_nowait()

                            print(f"[DEBUG STREAM] {agent_id}: {log_line}")
                            sys.stdout.write(f"[RAW_LOG] {agent_id}: {log_line}\n")
                            # Detect log level from line content
                            level = "INFO"
                            if "[STDERR]" in log_line or "[ERROR]" in log_line or "ERROR" in log_line:
                                level = "ERROR"
                            elif "[WARN]" in log_line or "WARNING" in log_line:
                                level = "WARN"
                            elif "[DEBUG]" in log_line:
                                level = "DEBUG"
                            
                            # Write to log widget (strip timestamp since widget adds its own)
                            # Remove our timestamp prefix to avoid duplication
                            display_line = log_line
                            if log_line.startswith("["):
                                # Remove timestamp: [YYYY-MM-DD HH:MM:SS]
                                close_bracket = log_line.find("]")
                                if close_bracket > 0 and close_bracket < 25:
                                    display_line = log_line[close_bracket + 1:].lstrip()
                            
                            log_widget.write_line(display_line)
                            
                            if log_widget.auto_scroll:
                                log_widget.scroll_end()
                            
                            logs_processed += 1
                            
                        except asyncio.QueueEmpty:
                            break
                        except Exception as e:
                            # Log error but don't crash
                            logging.error(f"Error processing log for agent '{agent_id}': {e}")
                            break
                
                # Sleep briefly to avoid busy-waiting
                await asyncio.sleep(0.1)
                
        except Exception as e:
            # UI task crashed - log but don't bring down the application
            logging.error(f"Log streaming task crashed: {e}")
            # Try to restart after a delay
            await asyncio.sleep(5.0)
            asyncio.create_task(self.stream_logs_to_ui())
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
    
    def action_refresh(self) -> None:
        """Manually refresh the display."""
        self.refresh_display()
    
    def action_show_overview(self) -> None:
        """Switch to the overview tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.active = "overview"
    
    def action_toggle_autoscroll(self) -> None:
        """Toggle auto-scroll for all log widgets."""
        for log_widget in self.agent_logs.values():
            log_widget.auto_scroll = not log_widget.auto_scroll
        
        # Show notification
        auto_scroll_status = "enabled" if list(self.agent_logs.values())[0].auto_scroll else "disabled"
        self.notify(f"Auto-scroll {auto_scroll_status}")
    
    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.action_next_tab()
    
    def action_prev_tab(self) -> None:
        """Switch to the previous tab."""
        tabbed_content = self.query_one(TabbedContent)
        tabbed_content.action_previous_tab()
    
    def action_clear_current_log(self) -> None:
        """Clear the log buffer for the currently active agent tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_tab = tabbed_content.active
            
            # Don't clear overview tab
            if active_tab == "overview":
                self.notify("Cannot clear overview tab", severity="warning")
                return
            
            # Extract agent_id from tab id (format: "tab_<agent_id>")
            if active_tab and active_tab.startswith("tab_"):
                agent_id = active_tab[4:]  # Remove "tab_" prefix
                
                if agent_id in self.bulk_manager.agents:
                    # Clear agent's log buffer
                    agent_instance = self.bulk_manager.agents[agent_id]
                    agent_instance.log_buffer.clear()
                    
                    # Clear log widget display
                    if agent_id in self.agent_logs:
                        log_widget = self.agent_logs[agent_id]
                        log_widget.clear()
                        log_widget.write_agent_log(f"Log cleared for agent '{agent_id}'", "INFO")
                    
                    self.notify(f"Cleared log for agent '{agent_id}'")
                else:
                    self.notify(f"Agent '{agent_id}' not found", severity="error")
            else:
                self.notify("No agent tab selected", severity="warning")
                
        except Exception as e:
            self.notify(f"Error clearing log: {e}", severity="error")
            logging.error(f"Error in action_clear_current_log: {e}")


async def run_agent_monitor_async(bulk_manager: BulkAgentManager) -> None:
    """Run the agent monitor application asynchronously.
    
    Args:
        bulk_manager: BulkAgentManager instance to monitor
    """
    app = AgentMonitorApp(bulk_manager)
    await app.run_async()


def run_agent_monitor(bulk_manager: BulkAgentManager) -> None:
    """Run the agent monitor application (synchronous wrapper).

    Args:
        bulk_manager: BulkAgentManager instance to monitor
    """
    import sys, asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    app = AgentMonitorApp(bulk_manager)
    # Try to detect if we're in an async context
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        # In async context - this shouldn't be called, but handle it gracefully
        raise RuntimeError("run_agent_monitor() should not be called from async context. Use run_agent_monitor_async() instead.")
    except RuntimeError as e:
        if "no running event loop" in str(e).lower():
            # No event loop - safe to run normally
            app.run()
        else:
            # Re-raise other runtime errors
            raise


# For standalone testing
if __name__ == "__main__":
    from openagents.utils.bulk_agent_manager import BulkAgentManager
    
    # Create a test manager (normally this would be populated with real agents)
    manager = BulkAgentManager()
    
    # Run the monitor
    run_agent_monitor(manager)