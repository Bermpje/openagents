import React, { useState, useEffect, useCallback } from "react";
import { useOpenAgents } from "@/context/OpenAgentsProvider";
import { useIsAdmin } from "@/hooks/useIsAdmin";

interface EventLogEntry {
  timestamp: number;
  direction: "inbound" | "outbound";
  event_name: string;
  source_id: string;
  destination_id: string | null;
  payload: any;
  visibility: string;
  request_id: string;
  response_to?: string | null;
}

interface EventLogViewerProps {
  onExport?: (events: EventLogEntry[]) => void;
}

const EventLogViewer: React.FC<EventLogViewerProps> = ({ onExport }) => {
  const { connector, connectionStatus } = useOpenAgents();
  const { isAdmin, isLoading: isAdminLoading } = useIsAdmin();
  
  const [events, setEvents] = useState<EventLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);
  
  // Filters
  const [sinceTimestamp, setSinceTimestamp] = useState<number | null>(null);
  const [eventNamePattern, setEventNamePattern] = useState<string>("");
  const [sourceId, setSourceId] = useState<string>("");
  const [destinationId, setDestinationId] = useState<string>("");
  const [limit, setLimit] = useState<number>(100);
  const [offset, setOffset] = useState<number>(0);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [hasMore, setHasMore] = useState<boolean>(false);

  // Load event logs from backend
  const loadEventLogs = useCallback(async () => {
    if (!connector || !isAdmin) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const agentId = connectionStatus.agentId || connector.getAgentId();
      
      const payload: any = {
        limit,
        offset,
      };

      if (sinceTimestamp) {
        payload.since_timestamp = sinceTimestamp;
      }
      if (eventNamePattern) {
        payload.event_name_pattern = eventNamePattern;
      }
      if (sourceId) {
        payload.source_id = sourceId;
      }
      if (destinationId) {
        payload.destination_id = destinationId;
      }

      const response = await connector.sendEvent({
        event_name: "system.retrieve_event_log",
        source_id: agentId,
        destination_id: "system",
        payload,
      });

      if (response.success && response.data) {
        setEvents(response.data.events || []);
        setTotalCount(response.data.total_count || 0);
        setHasMore(response.data.has_more || false);
      } else {
        setError(response.message || "Failed to retrieve event logs");
      }
    } catch (err: any) {
      console.error("Failed to load event logs:", err);
      setError(err.message || "Failed to load event logs");
    } finally {
      setLoading(false);
    }
  }, [connector, isAdmin, connectionStatus.agentId, sinceTimestamp, eventNamePattern, sourceId, destinationId, limit, offset]);

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh && isAdmin && !isAdminLoading) {
      // Initial load
      loadEventLogs();
      
      // Set up interval for auto-refresh (every 5 seconds)
      const interval = setInterval(() => {
        loadEventLogs();
      }, 5000);
      
      setRefreshInterval(interval);
      
      return () => {
        clearInterval(interval);
        setRefreshInterval(null);
      };
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, isAdmin, isAdminLoading]);

  // Manual refresh
  const handleRefresh = useCallback(() => {
    setOffset(0);
    loadEventLogs();
  }, [loadEventLogs]);

  // Toggle expand
  const toggleExpand = (requestId: string) => {
    setExpandedIds((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(requestId)) {
        newSet.delete(requestId);
      } else {
        newSet.add(requestId);
      }
      return newSet;
    });
  };

  // Export logs
  const handleExport = useCallback(() => {
    const jsonStr = JSON.stringify(events, null, 2);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `event-logs-${new Date().toISOString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    if (onExport) {
      onExport(events);
    }
  }, [events, onExport]);

  // Format timestamp
  const formatTimestamp = (timestamp: number) => {
    // Timestamp might be in seconds (if < 1e12) or milliseconds (if >= 1e12)
    const date = timestamp < 1e12 
      ? new Date(timestamp * 1000) 
      : new Date(timestamp);
    return date.toLocaleString("en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      fractionalSecondDigits: 3,
    });
  };

  // Format JSON
  const formatJSON = (obj: any) => {
    try {
      return JSON.stringify(obj, null, 2);
    } catch {
      return String(obj);
    }
  };

  // Pagination handlers
  const handlePreviousPage = () => {
    if (offset > 0) {
      setOffset(Math.max(0, offset - limit));
    }
  };

  const handleNextPage = () => {
    if (hasMore) {
      setOffset(offset + limit);
    }
  };

  return (
    <div className="p-6 dark:bg-gray-900 h-full min-h-screen overflow-y-auto">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex-1">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Event Log Viewer
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            View real-time event logs from the network
          </p>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Auto-refresh toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              Auto-refresh (5s)
            </span>
          </label>
          
          {/* Refresh button */}
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className={`w-4 h-4 inline mr-2 ${loading ? "animate-spin" : ""}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Refresh
          </button>
          
          {/* Export button */}
          <button
            onClick={handleExport}
            disabled={events.length === 0}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <svg
              className="w-4 h-4 inline mr-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            Export JSON
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
          Filters
        </h3>
        <div className="flex flex-wrap gap-4">
          {/* Time range */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Since Timestamp
            </label>
            <input
              type="number"
              value={sinceTimestamp || ""}
              onChange={(e) => setSinceTimestamp(e.target.value ? parseFloat(e.target.value) : null)}
              placeholder="Optional"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Event name pattern */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Event Name Pattern
            </label>
            <input
              type="text"
              value={eventNamePattern}
              onChange={(e) => setEventNamePattern(e.target.value)}
              placeholder="e.g.: feed.*"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Source ID */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Source ID
            </label>
            <input
              type="text"
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
              placeholder="e.g.: agent_alice"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Destination ID */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Destination ID
            </label>
            <input
              type="text"
              value={destinationId}
              onChange={(e) => setDestinationId(e.target.value)}
              placeholder="e.g.: mod:feed"
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        <div className="mt-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Items Per Page
              </label>
              <input
                type="number"
                value={limit}
                onChange={(e) => {
                  const newLimit = parseInt(e.target.value) || 100;
                  setLimit(Math.min(500, Math.max(1, newLimit)));
                  setOffset(0);
                }}
                min={1}
                max={500}
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
          
          <button
            onClick={handleRefresh}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          >
            Apply
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="mb-6 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-red-400"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                Load Failed
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                {error}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Currently Showing
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {events.length}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Total
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {totalCount}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Page
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
            {Math.floor(offset / limit) + 1}
          </div>
        </div>
      </div>

      {/* Event List */}
      <div className="space-y-2">
        {loading && events.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400">Loading event logs...</p>
          </div>
        ) : events.length === 0 ? (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-8 text-center">
            <svg
              className="h-12 w-12 text-gray-400 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-gray-600 dark:text-gray-400">
              No event logs found
            </p>
          </div>
        ) : (
          events.map((event) => {
            const isExpanded = expandedIds.has(event.request_id);
            const isInbound = event.direction === "inbound";

            return (
              <div
                key={event.request_id}
                className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
              >
                {/* Event Header */}
                <button
                  onClick={() => toggleExpand(event.request_id)}
                  className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    {/* Direction Icon */}
                    {isInbound ? (
                      <svg
                        className="w-5 h-5 text-blue-500 flex-shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M13 7l5 5m0 0l-5 5m5-5H6"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-5 h-5 text-green-500 flex-shrink-0"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M11 17l-5-5m0 0l5-5m-5 5h12"
                        />
                      </svg>
                    )}

                    {/* Event Info */}
                    <div className="flex-1 min-w-0 text-left">
                      <div className="text-sm font-medium text-gray-900 dark:text-gray-100 truncate">
                        {event.event_name}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        {formatTimestamp(event.timestamp)} • {event.direction} • {event.source_id} → {event.destination_id || "N/A"}
                      </div>
                    </div>
                  </div>

                  {/* Expand Icon */}
                  <svg
                    className={`w-5 h-5 text-gray-400 flex-shrink-0 ml-2 transition-transform ${
                      isExpanded ? "transform rotate-180" : ""
                    }`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </button>

                {/* Event Details */}
                {isExpanded && (
                  <div className="px-4 pb-4 border-t border-gray-200 dark:border-gray-700">
                    <div className="pt-4 space-y-4">
                      {/* Event Metadata */}
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                          Event Metadata
                        </h4>
                        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 overflow-x-auto">
                          <div className="space-y-1 text-xs">
                            <div><span className="font-medium">Timestamp:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.timestamp}</span></div>
                            <div><span className="font-medium">Direction:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.direction}</span></div>
                            <div><span className="font-medium">Source:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.source_id}</span></div>
                            <div><span className="font-medium">Destination:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.destination_id || "N/A"}</span></div>
                            <div><span className="font-medium">Visibility:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.visibility}</span></div>
                            <div><span className="font-medium">Request ID:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.request_id}</span></div>
                            {event.response_to && (
                              <div><span className="font-medium">Response To:</span> <span className="font-mono text-gray-800 dark:text-gray-200">{event.response_to}</span></div>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Payload */}
                      <div>
                        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                          Event Payload
                        </h4>
                        <div className="bg-gray-50 dark:bg-gray-900 rounded-lg p-3 overflow-x-auto">
                          <pre className="text-xs text-gray-800 dark:text-gray-200 whitespace-pre-wrap break-words">
                            {formatJSON(event.payload)}
                          </pre>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Pagination */}
      {(totalCount > limit || offset > 0) && (
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-gray-600 dark:text-gray-400">
            Showing {offset + 1} - {Math.min(offset + events.length, totalCount)} of {totalCount} records
          </div>
          <div className="flex gap-2">
            <button
              onClick={handlePreviousPage}
              disabled={offset === 0}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={!hasMore}
              className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default EventLogViewer;

