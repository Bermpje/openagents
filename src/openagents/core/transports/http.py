"""
HTTP Transport Implementation for OpenAgents.

This module provides the HTTP transport implementation for agent communication.
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from openagents.config.globals import (
    SYSTEM_EVENT_REGISTER_AGENT,
    SYSTEM_EVENT_HEALTH_CHECK,
    SYSTEM_EVENT_POLL_MESSAGES,
    SYSTEM_EVENT_UNREGISTER_AGENT,
)
from openagents.models.network_management import ImportMode
from openagents.utils.network_export import NetworkExporter
from openagents.utils.network_import import NetworkImporter
from io import BytesIO
from aiohttp import web

# No need for external CORS library, implement manually

from .base import Transport
from openagents.models.transport import TransportType, ConnectionState, ConnectionInfo
from openagents.models.event import Event

logger = logging.getLogger(__name__)


class HttpTransport(Transport):
    """
    HTTP transport implementation.

    This transport implementation uses HTTP to communicate with the network.
    It is used to communicate with the network from the browser and easily obtain claim information.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(TransportType.HTTP, config, is_notifiable=False)
        self.app = web.Application(middlewares=[self.cors_middleware])
        self.site = None
        self.network_instance = None  # Reference to network instance
        self.setup_routes()

    def setup_routes(self):
        """Setup HTTP routes."""
        # Add both /health and /api/health for compatibility
        self.app.router.add_get("/api/health", self.health_check)
        self.app.router.add_post("/api/register", self.register_agent)
        self.app.router.add_post("/api/unregister", self.unregister_agent)
        self.app.router.add_get("/api/poll", self.poll_messages)
        self.app.router.add_post("/api/send_event", self.send_message)
<<<<<<< HEAD
        
=======

>>>>>>> b4aa4418d01afb3b8658e282104d1a8e135f2c9f
        # Network management endpoints (admin only)
        self.app.router.add_get("/api/network/export", self.export_network)
        self.app.router.add_post("/api/network/import/validate", self.validate_import)
        self.app.router.add_post("/api/network/import/apply", self.apply_import)
<<<<<<< HEAD
=======
        # LLM Logs API endpoints
        self.app.router.add_get("/api/agents/service/{agent_id}/llm-logs", self.get_llm_logs)
        self.app.router.add_get("/api/agents/service/{agent_id}/llm-logs/{log_id}", self.get_llm_log_entry)

        # Cache file upload/download endpoints
        self.app.router.add_post("/api/cache/upload", self.cache_upload)
        self.app.router.add_get("/api/cache/download/{cache_id}", self.cache_download)
        self.app.router.add_get("/api/cache/info/{cache_id}", self.cache_info)
        # Agent management endpoints
        self.app.router.add_get("/api/agents/service", self.get_service_agents)
        self.app.router.add_post("/api/agents/service/{agent_id}/start", self.start_service_agent)
        self.app.router.add_post("/api/agents/service/{agent_id}/stop", self.stop_service_agent)
        self.app.router.add_post("/api/agents/service/{agent_id}/restart", self.restart_service_agent)
        self.app.router.add_get("/api/agents/service/{agent_id}/status", self.get_service_agent_status)
        self.app.router.add_get("/api/agents/service/{agent_id}/logs/screen", self.get_service_agent_logs)
        self.app.router.add_get("/api/agents/service/{agent_id}/source", self.get_service_agent_source)
        self.app.router.add_put("/api/agents/service/{agent_id}/source", self.save_service_agent_source)
        self.app.router.add_get("/api/agents/service/{agent_id}/env", self.get_service_agent_env)
        self.app.router.add_put("/api/agents/service/{agent_id}/env", self.save_service_agent_env)

        # Event Explorer API endpoints
        self.app.router.add_get("/api/events/sync", self.sync_events)
        self.app.router.add_get("/api/events", self.list_events)
        self.app.router.add_get("/api/events/mods", self.list_mods)
        self.app.router.add_get("/api/events/search", self.search_events)
        self.app.router.add_get("/api/events/{event_name}", self.get_event_detail)

        # MCP routes (if serve_mcp: true)
        if self._serve_mcp:
            self.app.router.add_post("/mcp", self._handle_mcp_post)
            self.app.router.add_get("/mcp", self._handle_mcp_get)
            self.app.router.add_delete("/mcp", self._handle_mcp_delete)
            self.app.router.add_get("/mcp/tools", self._handle_mcp_tools_list)
            logger.info("HTTP transport: MCP protocol enabled at /mcp")

        # Studio routes (if serve_studio: true)
        if self._serve_studio:
            # Studio static files - catch-all for /studio paths
            self.app.router.add_get("/studio", self._handle_studio_redirect)
            self.app.router.add_get("/studio/{path:.*}", self._handle_studio_static)
            # Also serve /static/* and root-level assets for React app compatibility
            # (React builds reference /static/js/... not /studio/static/js/...)
            self.app.router.add_get("/static/{path:.*}", self._handle_studio_root_static)
            self.app.router.add_get("/favicon.ico", self._handle_studio_root_asset)
            self.app.router.add_get("/manifest.json", self._handle_studio_root_asset)
            self.app.router.add_get("/logo192.png", self._handle_studio_root_asset)
            self.app.router.add_get("/logo512.png", self._handle_studio_root_asset)
            self.app.router.add_get("/robots.txt", self._handle_studio_root_asset)
            logger.info("HTTP transport: Studio frontend enabled at /studio")
>>>>>>> b4aa4418d01afb3b8658e282104d1a8e135f2c9f

    @web.middleware
    async def cors_middleware(self, request, handler):
        """CORS middleware for browser compatibility."""
        # Handle preflight OPTIONS requests
        if request.method == "OPTIONS":
            response = web.Response()
        else:
            response = await handler(request)

        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, Authorization, Accept"
        )
        response.headers["Access-Control-Max-Age"] = "86400"  # 24 hours

        return response

    async def initialize(self) -> bool:
        """Initialize HTTP transport."""
        self.is_initialized = True
        return True

    async def shutdown(self) -> bool:
        """Shutdown HTTP transport."""
        self.is_initialized = False
        self.is_listening = False
        if self.site:
            await self.site.stop()
            self.site = None
        return True

    async def send(self, message: Event) -> bool:
        return True

    async def health_check(self, request):
        """Handle health check requests."""
        logger.debug("HTTP health check requested")

        # Create a system health check event
        health_check_event = Event(
            event_name=SYSTEM_EVENT_HEALTH_CHECK,
            source_id="http_transport",
            destination_id="system:system",
            payload={},
        )

        # Send the health check event and get response using the event handler
        try:
            # Process the health check event through the registered event handler
            event_response = await self.call_event_handler(health_check_event)

            if event_response and event_response.success and event_response.data:
                network_stats = event_response.data
                logger.debug(
                    "Successfully retrieved network stats via health check event"
                )
            else:
                logger.warning(
                    f"Health check event failed: {event_response.message if event_response else 'No response'}"
                )
                raise Exception("Health check event failed")

        except Exception as e:
            logger.warning(f"Failed to process health check event: {e}")
            # Provide minimal stats if health check event fails
            network_stats = {
                "network_id": "unknown",
                "network_name": "Unknown Network",
                "is_running": False,
                "uptime_seconds": 0,
                "agent_count": 0,
                "agents": {},
                "mods": [],
                "topology_mode": "centralized",
                "transports": [],
                "manifest_transport": "http",
                "recommended_transport": "grpc",
                "max_connections": 100,
            }

        return web.json_response(
            {"success": True, "status": "healthy", "data": network_stats}
        )

    async def register_agent(self, request):
        """Handle agent registration via HTTP."""
        try:
            data = await request.json()
            agent_id = data.get("agent_id")
            metadata = data.get("metadata", {})

            if not agent_id:
                return web.json_response(
                    {"success": False, "error_message": "agent_id is required"},
                    status=400,
                )

            logger.info(f"HTTP Agent registration: {agent_id}")

            # Register with network instance if available
            register_event = Event(
                event_name=SYSTEM_EVENT_REGISTER_AGENT,
                source_id=agent_id,
                payload={
                    "agent_id": agent_id,
                    "metadata": metadata,
                    "transport_type": TransportType.HTTP,
                    "certificate": data.get("certificate", None),
                    "force_reconnect": True,
                    "password_hash": data.get("password_hash", None),
                },
            )
            # Process the registration event through the event handler
            event_response = await self.call_event_handler(register_event)

            if event_response and event_response.success:
                # Extract network information from the response
                network_name = (
                    event_response.data.get("network_name", "Unknown Network")
                    if event_response.data
                    else "Unknown Network"
                )
                network_id = (
                    event_response.data.get("network_id", "unknown")
                    if event_response.data
                    else "unknown"
                )

                logger.info(
                    f"✅ Successfully registered HTTP agent {agent_id} with network {network_name}"
                )
                
                # Extract secret from response data
                secret = ""
                if event_response.data and isinstance(event_response.data, dict):
                    secret = event_response.data.get("secret", "")
                
                return web.json_response(
                    {
                        "success": True,
                        "network_name": network_name,
                        "network_id": network_id,
                        "secret": secret,
                    }
                )
            else:
                error_message = (
                    event_response.message
                    if event_response
                    else "No response from event handler"
                )
                logger.error(
                    f"❌ Network registration failed for HTTP agent {agent_id}: {error_message}"
                )
                return web.json_response(
                    {
                        "success": False,
                        "error_message": f"Registration failed: {error_message}",
                    },
                    status=500,
                )

        except Exception as e:
            logger.error(f"Error in HTTP register_agent: {e}")
            return web.json_response(
                {"success": False, "error_message": str(e)}, status=500
            )

    async def unregister_agent(self, request):
        """Handle agent unregistration via HTTP."""
        try:
            data = await request.json()
            agent_id = data.get("agent_id")
            secret = data.get("secret")

            if not agent_id:
                return web.json_response(
                    {"success": False, "error_message": "agent_id is required"},
                    status=400,
                )

            logger.info(f"HTTP Agent unregistration: {agent_id}")

            # Create unregister event with authentication
            unregister_event = Event(
                event_name=SYSTEM_EVENT_UNREGISTER_AGENT,
                source_id=agent_id,
                payload={"agent_id": agent_id},
                secret=secret,
            )

            # Process the unregistration event through the event handler
            event_response = await self.call_event_handler(unregister_event)

            if event_response and event_response.success:
                logger.info(f"✅ Successfully unregistered HTTP agent {agent_id}")
                return web.json_response({"success": True})
            else:
                error_message = (
                    event_response.message
                    if event_response
                    else "No response from event handler"
                )
                logger.error(
                    f"❌ Unregistration failed for HTTP agent {agent_id}: {error_message}"
                )
                return web.json_response(
                    {
                        "success": False,
                        "error_message": f"Unregistration failed: {error_message}",
                    },
                    status=500,
                )

        except Exception as e:
            logger.error(f"Error in HTTP unregister_agent: {e}")
            return web.json_response(
                {"success": False, "error_message": str(e)}, status=500
            )

    async def poll_messages(self, request):
        """Handle message polling for HTTP agents."""
        try:
            agent_id = request.query.get("agent_id")
            secret = request.query.get("secret")

            if not agent_id:
                return web.json_response(
                    {
                        "success": False,
                        "error_message": "agent_id query parameter is required",
                    },
                    status=400,
                )

            logger.debug(f"HTTP polling messages for agent: {agent_id}")

            # Create poll messages event with authentication
            poll_event = Event(
                event_name=SYSTEM_EVENT_POLL_MESSAGES,
                source_id=agent_id,
                destination_id="system:system",
                payload={"agent_id": agent_id},
                secret=secret,
            )

            # Send the poll request through event handler
            response = await self.call_event_handler(poll_event)

            if not response or not response.success:
                logger.warning(
                    f"Poll messages request failed: {response.message if response else 'No response'}"
                )
                return web.json_response(
                    {
                        "success": False,
                        "messages": [],
                        "agent_id": agent_id,
                        "error_message": (
                            response.message
                            if response
                            else "No response from event handler"
                        ),
                    }
                )

            # Extract messages from response data
            messages = []
            if response.data:
                try:
                    # Handle different response data structures
                    response_messages = []

                    if isinstance(response.data, list):
                        # Direct list of messages
                        response_messages = response.data
                        logger.debug(
                            f"🔧 HTTP: Received direct list of {len(response_messages)} messages"
                        )
                    elif isinstance(response.data, dict):
                        if "messages" in response.data:
                            # Response wrapped in a dict with 'messages' key
                            response_messages = response.data["messages"]
                            logger.debug(
                                f"🔧 HTTP: Extracted {len(response_messages)} messages from response dict"
                            )
                        else:
                            logger.warning(
                                f"🔧 HTTP: Dict response missing 'messages' key: {list(response.data.keys())}"
                            )
                            response_messages = []
                    else:
                        logger.warning(
                            f"🔧 HTTP: Unexpected poll_messages response format: {type(response.data)} - {response.data}"
                        )
                        response_messages = []

                    logger.info(
                        f"🔧 HTTP: Processing {len(response_messages)} polled messages for {agent_id}"
                    )

                    # Convert each message to dict format for HTTP response
                    for message_data in response_messages:
                        try:
                            if isinstance(message_data, dict):
                                if "event_name" in message_data:
                                    # This is already an Event structure - use as is
                                    messages.append(message_data)
                                    logger.debug(
                                        f"🔧 HTTP: Successfully included message: {message_data.get('event_id', 'no-id')}"
                                    )
                                else:
                                    # This might be a legacy message format - try to parse it
                                    from openagents.utils.message_util import (
                                        parse_message_dict,
                                    )

                                    event = parse_message_dict(message_data)
                                    if event:
                                        # Convert Event object to dict
                                        event_dict = {
                                            "event_id": event.event_id,
                                            "event_name": event.event_name,
                                            "source_id": event.source_id,
                                            "destination_id": event.destination_id,
                                            "payload": event.payload,
                                            "timestamp": event.timestamp,
                                            "metadata": event.metadata,
                                            "visibility": getattr(
                                                event, "visibility", "network"
                                            ),
                                        }
                                        messages.append(event_dict)
                                        logger.debug(
                                            f"🔧 HTTP: Successfully parsed legacy message to Event: {event.event_id}"
                                        )
                                    else:
                                        logger.warning(
                                            f"🔧 HTTP: Failed to parse message data: {message_data}"
                                        )
                            else:
                                logger.warning(
                                    f"🔧 HTTP: Invalid message format in poll response: {message_data}"
                                )

                        except Exception as e:
                            logger.error(
                                f"🔧 HTTP: Error processing polled message: {e}"
                            )
                            logger.debug(
                                f"🔧 HTTP: Problematic message data: {message_data}"
                            )

                    logger.info(
                        f"🔧 HTTP: Successfully converted {len(messages)} messages for HTTP response"
                    )

                except Exception as e:
                    logger.error(f"🔧 HTTP: Error parsing poll_messages response: {e}")
                    messages = []
            else:
                logger.debug(f"🔧 HTTP: No messages in poll response")
                messages = []

            return web.json_response(
                {"success": True, "messages": messages, "agent_id": agent_id}
            )

        except Exception as e:
            logger.error(f"Error in HTTP poll_messages: {e}")
            return web.json_response(
                {"success": False, "error_message": str(e)}, status=500
            )

    async def send_message(self, request):
        """Handle sending events/messages via HTTP."""
        try:
            data = await request.json()

            # Extract event data similar to gRPC SendEvent
            event_name = data.get("event_name")
            source_id = data.get("source_id")
            target_agent_id = data.get("target_agent_id")
            payload = data.get("payload", {})
            event_id = data.get("event_id")
            metadata = data.get("metadata", {})
            visibility = data.get("visibility", "network")
            secret = data.get("secret")

            if not event_name or not source_id:
                return web.json_response(
                    {
                        "success": False,
                        "error_message": "event_name and source_id are required",
                    },
                    status=400,
                )

            logger.debug(f"HTTP unified event: {event_name} from {source_id}")

            # Create internal Event from HTTP request
            event = Event(
                event_name=event_name,
                source_id=source_id,
                destination_id=target_agent_id,
                payload=payload,
                event_id=event_id,
                timestamp=int(time.time()),
                metadata=metadata,
                visibility=visibility,
                secret=secret,
            )

            # Route through unified handler (similar to gRPC)
            event_response = await self._handle_sent_event(event)

            # Extract response data from EventResponse
            response_data = None
            if (
                event_response
                and hasattr(event_response, "data")
                and event_response.data
            ):
                response_data = event_response.data

            return web.json_response(
                {
                    "success": event_response.success if event_response else True,
                    "message": event_response.message if event_response else "",
                    "event_id": event_id,
                    "data": response_data,
                    "event_name": event_name,
                }
            )

        except Exception as e:
            logger.error(f"Error handling HTTP send_message: {e}")
            return web.json_response(
                {"success": False, "error_message": str(e)}, status=500
            )

    async def _handle_sent_event(self, event):
        """Unified event handler that routes both regular messages and system commands."""
        logger.debug(
            f"Processing HTTP unified event: {event.event_name} from {event.source_id}"
        )

        # Notify registered event handlers and return the response
        response = await self.call_event_handler(event)
        return response

    async def peer_connect(self, peer_id: str, metadata: Dict[str, Any] = None) -> bool:
        """Connect to a peer (HTTP doesn't maintain persistent connections)."""
        logger.debug(f"HTTP transport peer_connect called for {peer_id}")
        return True

    async def peer_disconnect(self, peer_id: str) -> bool:
        """Disconnect from a peer (HTTP doesn't maintain persistent connections)."""
        logger.debug(f"HTTP transport peer_disconnect called for {peer_id}")
        return True

    async def listen(self, address: str) -> bool:
        runner = web.AppRunner(self.app)
        await runner.setup()

        # Use a different port for HTTP (gRPC port + 1000)
        if ":" in address:
            host, port = address.split(":")
        else:
            host = "0.0.0.0"
            port = address
        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"HTTP transport listening on {host}:{port}")
        self.is_listening = True
        self.site = site  # Store the site for shutdown
        return True

    def _require_admin(self, request) -> bool:
        """Check if request is from admin user.
        
        TODO: Integrate with actual authentication/permission system.
        For now, this is a placeholder that always returns True.
        In production, this should:
        1. Extract user credentials from request headers/cookies
        2. Validate against user database
        3. Check admin role/permissions
        
        Args:
            request: aiohttp request object
            
        Returns:
            bool: True if user is admin, False otherwise
        """
        # TODO: Implement actual admin check
        # Example implementation:
        # auth_header = request.headers.get('Authorization')
        # if not auth_header:
        #     return False
        # user = validate_token(auth_header)
        # return user.is_admin if user else False
        
        logger.warning("Admin check not implemented - allowing all requests")
        return True

    async def export_network(self, request):
        """Export network configuration (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )
            
<<<<<<< HEAD
=======
            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )
            
            agent_manager = self.network_instance.agent_manager
            result = await agent_manager.restart_agent(agent_id)
            
            if result["success"]:
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)
        
        except Exception as e:
            logger.error(f"Error restarting service agent: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )
    
    async def get_service_agent_status(self, request):
        """Get status of a specific service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "agent_id is required"},
                    status=400,
                )
            
            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )
            
            agent_manager = self.network_instance.agent_manager
            status = agent_manager.get_agent_status(agent_id)
            
            if status:
                return web.json_response({
                    "success": True,
                    "status": status
                })
            else:
                return web.json_response(
                    {"success": False, "error": "Agent not found"},
                    status=404,
                )
        
        except Exception as e:
            logger.error(f"Error getting service agent status: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )
    
    async def get_service_agent_logs(self, request):
        """Get recent log lines for a specific service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            lines = int(request.query.get("lines", "100"))
            
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "agent_id is required"},
                    status=400,
                )
            
            # Validate lines parameter
            if lines < 1 or lines > 10000:
                return web.json_response(
                    {"success": False, "error": "lines must be between 1 and 10000"},
                    status=400,
                )
            
            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )
            
            agent_manager = self.network_instance.agent_manager
            log_lines = agent_manager.get_agent_logs(agent_id, lines)
            
            if log_lines is not None:
                return web.json_response({
                    "success": True,
                    "logs": log_lines
                })
            else:
                return web.json_response(
                    {"success": False, "error": "Agent not found or no logs available"},
                    status=404,
                )
        
        except ValueError:
            return web.json_response(
                {"success": False, "error": "Invalid lines parameter"},
                status=400,
            )
        except Exception as e:
            logger.error(f"Error getting service agent logs: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    async def get_service_agent_source(self, request):
        """Get the source code of a service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "Agent ID required"},
                    status=400,
                )

            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )

            agent_manager = self.network_instance.agent_manager
            source_info = agent_manager.get_agent_source(agent_id)

            if source_info:
                return web.json_response({
                    "success": True,
                    "source": source_info
                })
            else:
                return web.json_response(
                    {"success": False, "error": "Agent not found or unable to read source"},
                    status=404,
                )

        except Exception as e:
            logger.error(f"Error getting service agent source: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    async def save_service_agent_source(self, request):
        """Save the source code of a service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "Agent ID required"},
                    status=400,
                )

            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )

            # Parse request body
            try:
                data = await request.json()
            except Exception:
                return web.json_response(
                    {"success": False, "error": "Invalid JSON body"},
                    status=400,
                )

            content = data.get("content")
            if content is None:
                return web.json_response(
                    {"success": False, "error": "Content field required"},
                    status=400,
                )

            agent_manager = self.network_instance.agent_manager
            result = agent_manager.save_agent_source(agent_id, content)

            if result["success"]:
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            logger.error(f"Error saving service agent source: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    async def get_service_agent_env(self, request):
        """Get environment variables for a service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "Agent ID required"},
                    status=400,
                )

            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )

            agent_manager = self.network_instance.agent_manager
            env_vars = agent_manager.get_agent_env_vars(agent_id)

            if env_vars is None:
                return web.json_response(
                    {"success": False, "error": f"Agent '{agent_id}' not found"},
                    status=404,
                )

            return web.json_response({
                "success": True,
                "env_vars": env_vars
            })

        except Exception as e:
            logger.error(f"Error getting service agent env vars: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    async def save_service_agent_env(self, request):
        """Save environment variables for a service agent."""
        try:
            agent_id = request.match_info.get("agent_id")
            if not agent_id:
                return web.json_response(
                    {"success": False, "error": "Agent ID required"},
                    status=400,
                )

            if not self.network_instance or not hasattr(self.network_instance, "agent_manager"):
                return web.json_response(
                    {"success": False, "error": "Agent manager not available"},
                    status=503,
                )

            # Parse request body
            try:
                data = await request.json()
            except Exception:
                return web.json_response(
                    {"success": False, "error": "Invalid JSON body"},
                    status=400,
                )

            env_vars = data.get("env_vars")
            if env_vars is None:
                return web.json_response(
                    {"success": False, "error": "env_vars field required"},
                    status=400,
                )

            if not isinstance(env_vars, dict):
                return web.json_response(
                    {"success": False, "error": "env_vars must be an object"},
                    status=400,
                )

            agent_manager = self.network_instance.agent_manager
            result = agent_manager.set_agent_env_vars(agent_id, env_vars)

            if result["success"]:
                return web.json_response(result)
            else:
                return web.json_response(result, status=400)

        except Exception as e:
            logger.error(f"Error saving service agent env vars: {e}")
            return web.json_response(
                {"success": False, "error": str(e)},
                status=500,
            )

    async def sync_events(self, request):
        """Handle event index sync from GitHub."""
        try:
            from openagents.utils.event_indexer import get_event_indexer
            
            indexer = get_event_indexer()
            result = indexer.sync_from_github()
            
            return web.json_response({
                "success": True,
                "data": result
            })
        except Exception as e:
            logger.error(f"Error syncing events: {e}")
            return web.json_response(
                {"success": False, "error_message": str(e)},
                status=500
            )

    async def list_events(self, request):
        """List all indexed events with optional filters."""
        try:
            from openagents.utils.event_indexer import get_event_indexer
            
            indexer = get_event_indexer()
            
>>>>>>> b4aa4418d01afb3b8658e282104d1a8e135f2c9f
            # Get query parameters
            include_passwords = request.query.get("include_password_hashes", "false").lower() == "true"
            include_sensitive = request.query.get("include_sensitive_config", "false").lower() == "true"
            notes = request.query.get("notes")
            
            logger.info(f"Network export requested (passwords={include_passwords}, sensitive={include_sensitive})")
            
            # Get network instance from event handler
            # The network_instance is set when transport is bound to network
            if not self.network_instance:
                return web.json_response(
                    {"success": False, "error_message": "Network instance not available"},
                    status=500
                )
            
            # Export network
            exporter = NetworkExporter(self.network_instance)
            zip_buffer = exporter.export_to_zip(
                include_password_hashes=include_passwords,
                include_sensitive_config=include_sensitive,
                notes=notes
            )
            
            # Generate filename
            filename = f"{self.network_instance.network_name}_export.zip"
            
            # Return as streaming response
            return web.Response(
                body=zip_buffer.getvalue(),
                headers={
                    'Content-Type': 'application/zip',
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"Network export failed: {e}", exc_info=True)
            return web.json_response(
                {"success": False, "error_message": "Export failed"},
                status=500
            )

    async def validate_import(self, request):
        """Validate network import file (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )
            
            logger.info("Import validation requested")
            
            # Read multipart/form-data
            reader = await request.multipart()
            zip_data = None
            
            async for field in reader:
                if field.name == 'file':
                    zip_data = await field.read()
                    break
            
            if not zip_data:
                return web.json_response(
                    {"success": False, "error_message": "No file provided"},
                    status=400
                )
            
            # Validate import
            zip_buffer = BytesIO(zip_data)
            importer = NetworkImporter()
            validation_result = importer.validate(zip_buffer)
            
            # Return validation result
            return web.json_response(validation_result.model_dump())
            
        except Exception as e:
            logger.error(f"Import validation failed: {e}", exc_info=True)
            return web.json_response(
                {
                    "valid": False,
                    "errors": ["Validation error occurred"],
                    "warnings": []
                },
                status=200  # Return 200 with error in body, not 500
            )

    async def apply_import(self, request):
        """Apply network import (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )
            
            logger.info("Import apply requested")
            
            if not self.network_instance:
                return web.json_response(
                    {
                        "success": False,
                        "message": "Network instance not available",
                        "errors": ["Network not initialized"]
                    },
                    status=500
                )
            
            # Read multipart/form-data
            reader = await request.multipart()
            zip_data = None
            mode = ImportMode.OVERWRITE  # Default
            new_name = None
            
            async for field in reader:
                if field.name == 'file':
                    zip_data = await field.read()
                elif field.name == 'mode':
                    mode_str = (await field.read()).decode('utf-8')
                    try:
                        mode = ImportMode(mode_str)
                    except ValueError:
                        logger.warning(f"Invalid import mode: {mode_str}, using OVERWRITE")
                elif field.name == 'new_name':
                    new_name = (await field.read()).decode('utf-8')
            
            if not zip_data:
                return web.json_response(
                    {
                        "success": False,
                        "message": "No file provided",
                        "errors": ["File is required"]
                    },
                    status=400
                )
            
            # Apply import
            zip_buffer = BytesIO(zip_data)
            importer = NetworkImporter(self.network_instance)
            import_result = await importer.apply(
                zip_buffer,
                mode=mode,
                network=self.network_instance,
                new_name=new_name
            )
            
            # Return result
            return web.json_response(import_result.model_dump())
            
        except Exception as e:
            logger.error(f"Import apply failed: {e}", exc_info=True)
            return web.json_response(
                {
                    "success": False,
                    "message": "Import failed",
                    "errors": ["An error occurred during import"]
                },
                status=200  # Return 200 with error in body, not 500
            )

<<<<<<< HEAD
=======
    # ========================================================================
    # Studio Static File Handlers (enabled via serve_studio: true)
    # ========================================================================

    def _find_studio_build_dir(self) -> Optional[str]:
        """Find the studio build directory from the installed package."""
        try:
            from importlib.resources import files
            studio_resources = files("openagents").joinpath("studio", "build")
            if studio_resources.is_dir():
                try:
                    index_file = studio_resources.joinpath("index.html")
                    if index_file.is_file():
                        return str(studio_resources)
                except (AttributeError, TypeError):
                    pass
        except (ModuleNotFoundError, AttributeError, TypeError):
            pass

        # Try to find build directory in multiple locations
        script_dir = os.path.dirname(os.path.abspath(__file__))  # core/transports
        core_dir = os.path.dirname(script_dir)  # core
        package_dir = os.path.dirname(core_dir)  # src/openagents
        src_dir = os.path.dirname(package_dir)  # src
        project_root = os.path.dirname(src_dir)  # actual project root

        possible_paths = [
            # In development: project_root/studio/build
            os.path.join(project_root, "studio", "build"),
            # In installed package (src/openagents/studio/build)
            os.path.join(package_dir, "studio", "build"),
            # Alternative: relative to src
            os.path.join(src_dir, "studio", "build"),
        ]

        for path in possible_paths:
            if path and os.path.exists(path) and os.path.isdir(path):
                index_html = os.path.join(path, "index.html")
                if os.path.exists(index_html):
                    return path

        return None

    async def _handle_studio_redirect(self, request: web.Request) -> web.Response:
        """Redirect /studio to /studio/ for proper relative path handling."""
        return web.HTTPFound("/studio/")

    async def _handle_studio_static(self, request: web.Request) -> web.Response:
        """Handle Studio static file requests with SPA routing support."""
        if not self._studio_build_dir:
            return web.Response(
                status=404,
                text="Studio build directory not found. Run 'npm run build' in the studio directory.",
            )

        # Get the requested path
        path = request.match_info.get("path", "")

        # Handle empty path or just "/" - serve index.html
        if not path or path == "/":
            file_path = os.path.join(self._studio_build_dir, "index.html")
        else:
            # Remove leading slash and construct full path
            path = path.lstrip("/")
            file_path = os.path.join(self._studio_build_dir, path)

        # Security check: ensure the resolved path is within the build directory
        real_build_dir = os.path.realpath(self._studio_build_dir)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_build_dir):
            return web.Response(status=403, text="Forbidden")

        # Check if file exists
        if os.path.exists(file_path) and os.path.isfile(file_path):
            # Serve the actual file
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"

            try:
                with open(file_path, "rb") as f:
                    content = f.read()

                response = web.Response(body=content, content_type=content_type)
                # Add cache headers for static assets
                if any(path.startswith(prefix) for prefix in ["static/", "assets/"]):
                    response.headers["Cache-Control"] = "public, max-age=31536000"
                else:
                    response.headers["Cache-Control"] = "no-cache"
                return response
            except IOError as e:
                logger.error(f"HTTP Studio: Error reading file {file_path}: {e}")
                return web.Response(status=500, text="Internal server error")
        else:
            # For SPA routing: serve index.html for non-existent paths
            # This allows React Router to handle client-side routing
            index_path = os.path.join(self._studio_build_dir, "index.html")
            if os.path.exists(index_path):
                try:
                    with open(index_path, "rb") as f:
                        content = f.read()
                    return web.Response(
                        body=content,
                        content_type="text/html",
                        headers={"Cache-Control": "no-cache"},
                    )
                except IOError as e:
                    logger.error(f"HTTP Studio: Error reading index.html: {e}")
                    return web.Response(status=500, text="Internal server error")
            else:
                return web.Response(status=404, text="Not found")

    async def _handle_studio_root_static(self, request: web.Request) -> web.Response:
        """Handle /static/* requests for React app assets."""
        if not self._studio_build_dir:
            return web.Response(status=404, text="Studio build not found")

        path = request.match_info.get("path", "")
        file_path = os.path.join(self._studio_build_dir, "static", path.lstrip("/"))

        # Security check
        real_build_dir = os.path.realpath(self._studio_build_dir)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_build_dir):
            return web.Response(status=403, text="Forbidden")

        if os.path.exists(file_path) and os.path.isfile(file_path):
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                response = web.Response(body=content, content_type=content_type)
                response.headers["Cache-Control"] = "public, max-age=31536000"
                return response
            except IOError as e:
                logger.error(f"HTTP Studio: Error reading static file {file_path}: {e}")
                return web.Response(status=500, text="Internal server error")
        return web.Response(status=404, text="Not found")

    async def _handle_studio_root_asset(self, request: web.Request) -> web.Response:
        """Handle root-level asset requests (favicon.ico, manifest.json, etc.)."""
        if not self._studio_build_dir:
            return web.Response(status=404, text="Studio build not found")

        # Get filename from request path
        filename = request.path.lstrip("/")
        file_path = os.path.join(self._studio_build_dir, filename)

        # Security check
        real_build_dir = os.path.realpath(self._studio_build_dir)
        real_file_path = os.path.realpath(file_path)
        if not real_file_path.startswith(real_build_dir):
            return web.Response(status=403, text="Forbidden")

        if os.path.exists(file_path) and os.path.isfile(file_path):
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = "application/octet-stream"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                return web.Response(body=content, content_type=content_type)
            except IOError as e:
                logger.error(f"HTTP Studio: Error reading asset {file_path}: {e}")
                return web.Response(status=500, text="Internal server error")
        return web.Response(status=404, text="Not found")

    def _require_admin(self, request) -> bool:
        """Check if request is from admin user.

        TODO: Integrate with actual authentication/permission system.
        For now, this is a placeholder that always returns True.
        In production, this should:
        1. Extract user credentials from request headers/cookies
        2. Validate against user database
        3. Check admin role/permissions

        Args:
            request: aiohttp request object
         Returns:
            bool: True if user is admin, False otherwise
        """
        # TODO: Implement actual admin check
        # Example implementation:
        # auth_header = request.headers.get('Authorization')
        # if not auth_header:
        #     return False
        # user = validate_token(auth_header)
        # return user.is_admin if user else False
        logger.warning("Admin check not implemented - allowing all requests")
        return True

    async def export_network(self, request):
        """Export network configuration (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )

            # Get query parameters
            include_passwords = request.query.get("include_password_hashes", "false").lower() == "true"
            include_sensitive = request.query.get("include_sensitive_config", "false").lower() == "true"
            notes = request.query.get("notes")

            logger.info(f"Network export requested (passwords={include_passwords}, sensitive={include_sensitive})")

            # Get network instance from event handler
            # The network_instance is set when transport is bound to network
            if not self.network_instance:
                return web.json_response(
                    {"success": False, "error_message": "Network instance not available"},
                    status=500
                )

            # Export network
            exporter = NetworkExporter(self.network_instance)
            zip_buffer = exporter.export_to_zip(
                include_password_hashes=include_passwords,
                include_sensitive_config=include_sensitive,
                notes=notes
            )

            # Generate filename
            filename = f"{self.network_instance.network_name}_export.zip"

            # Return as streaming response
            return web.Response(
                body=zip_buffer.getvalue(),
                headers={
                    'Content-Type': 'application/zip',
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )

        except Exception as e:
            logger.error(f"Network export failed: {e}", exc_info=True)
            return web.json_response(
                {"success": False, "error_message": "Export failed"},
                status=500
            )

    async def validate_import(self, request):
        """Validate network import file (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )

            logger.info("Import validation requested")

            # Read multipart/form-data
            reader = await request.multipart()
            zip_data = None

            async for field in reader:
                if field.name == 'file':
                    zip_data = await field.read()
                    break

            if not zip_data:
                return web.json_response(
                    {"success": False, "error_message": "No file provided"},
                    status=400
                )

            # Validate import
            zip_buffer = BytesIO(zip_data)
            importer = NetworkImporter()
            validation_result = importer.validate(zip_buffer)

            # Return validation result
            return web.json_response(validation_result.model_dump())

        except Exception as e:
            logger.error(f"Import validation failed: {e}", exc_info=True)
            return web.json_response(
                {
                    "valid": False,
                    "errors": ["Validation error occurred"],
                    "warnings": []
                },
                status=200  # Return 200 with error in body, not 500
            )

    async def apply_import(self, request):
        """Apply network import (admin only)."""
        try:
            # Check admin permissions
            if not self._require_admin(request):
                return web.json_response(
                    {"success": False, "error_message": "Admin access required"},
                    status=403
                )

            logger.info("Import apply requested")

            if not self.network_instance:
                return web.json_response(
                    {
                        "success": False,
                        "message": "Network instance not available",
                        "errors": ["Network not initialized"]
                    },
                    status=500
                )

            # Read multipart/form-data
            reader = await request.multipart()
            zip_data = None
            mode = ImportMode.OVERWRITE  # Default
            new_name = None

            async for field in reader:
                if field.name == 'file':
                    zip_data = await field.read()
                elif field.name == 'mode':
                    mode_str = (await field.read()).decode('utf-8')
                    try:
                        mode = ImportMode(mode_str)
                    except ValueError:
                        logger.warning(f"Invalid import mode: {mode_str}, using OVERWRITE")
                elif field.name == 'new_name':
                    new_name = (await field.read()).decode('utf-8')

            if not zip_data:
                return web.json_response(
                    {
                        "success": False,
                        "message": "No file provided",
                        "errors": ["File is required"]
                    },
                    status=400
                )

            # Apply import
            zip_buffer = BytesIO(zip_data)
            importer = NetworkImporter(self.network_instance)
            import_result = await importer.apply(
                zip_buffer,
                mode=mode,
                network=self.network_instance,
                new_name=new_name
            )

            # Return result
            return web.json_response(import_result.model_dump())

        except Exception as e:
            logger.error(f"Import apply failed: {e}", exc_info=True)
            return web.json_response(
                {
                    "success": False,
                    "message": "Import failed",
                    "errors": ["An error occurred during import"]
                },
                status=200  # Return 200 with error in body, not 500
            )


def _generate_event_examples(event: Dict[str, Any]) -> Dict[str, str]:
    """Generate code examples for an event."""
    event_name = event.get('event_name', '')
    event_type = event.get('event_type', 'operation')
    request_schema = event.get('request_schema', {})
    
    # Python example
    python_example = f"""# Python example
from openagents import Agent

agent = Agent(agent_id="my_agent")
response = await agent.send_event(
    event_name="{event_name}",
    destination_id="mod:openagents.mods.{event.get('mod_id', 'unknown')}",
    payload={{
        # Add your payload here based on the schema
"""
    
    # Add payload fields from schema
    if request_schema and 'properties' in request_schema:
        for prop_name, prop_info in request_schema['properties'].items():
            if isinstance(prop_info, dict):
                prop_type = prop_info.get('type', 'string')
                is_required = prop_info.get('required', False)
                default = prop_info.get('default')
                
                if default is not None:
                    python_example += f'        "{prop_name}": {repr(default)},  # {prop_type}\n'
                elif is_required:
                    python_example += f'        "{prop_name}": "value",  # {prop_type} (required)\n'
                else:
                    python_example += f'        # "{prop_name}": "value",  # {prop_type} (optional)\n'
    
    python_example += """    }
)
print(response)
"""
    
    # JavaScript example
    js_example = f"""// JavaScript example
const response = await connector.sendEvent({{
    event_name: "{event_name}",
    destination_id: "mod:openagents.mods.{event.get('mod_id', 'unknown')}",
    payload: {{
        // Add your payload here based on the schema
"""
    
    if request_schema and 'properties' in request_schema:
        for prop_name, prop_info in request_schema['properties'].items():
            if isinstance(prop_info, dict):
                prop_type = prop_info.get('type', 'string')
                is_required = prop_info.get('required', False)
                default = prop_info.get('default')
                
                if default is not None:
                    js_example += f'        {prop_name}: {repr(default)},  // {prop_type}\n'
                elif is_required:
                    js_example += f'        {prop_name}: "value",  // {prop_type} (required)\n'
                else:
                    js_example += f'        // {prop_name}: "value",  // {prop_type} (optional)\n'
    
    js_example += """    }
});
console.log(response);
"""
    
    return {
        "python": python_example,
        "javascript": js_example,
    }

>>>>>>> b4aa4418d01afb3b8658e282104d1a8e135f2c9f

# Convenience function for creating HTTP transport
def create_http_transport(
    host: str = "0.0.0.0", port: int = 8080, **kwargs
) -> HttpTransport:
    """Create an HTTP transport with given configuration."""
    config = {"host": host, "port": port, **kwargs}
    return HttpTransport(config)
