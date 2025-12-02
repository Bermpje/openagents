import React from "react";
import { useNavigate } from "react-router-dom";
import { EventDefinition, SchemaDefinition } from "@/services/eventExplorerService";
import SchemaViewer from "./SchemaViewer";
import CodeExample from "./CodeExample";

interface EventDetailProps {
  event: EventDefinition;
  allEvents: EventDefinition[];
}

const EventDetail: React.FC<EventDetailProps> = ({ event, allEvents }) => {
  const navigate = useNavigate();

  const getTypeBadge = (type: string) => {
    const badges = {
      operation: {
        label: "operation",
        className: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
        icon: "●",
      },
      response: {
        label: "response",
        className: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
        icon: "→",
      },
      notification: {
        label: "notification",
        className: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
        icon: "📢",
      },
    };

    return badges[type as keyof typeof badges] || badges.operation;
  };

  const badge = getTypeBadge(event.type);

  // Find related events
  const relatedEvents = event.relatedEvents
    ?.map((address) => allEvents.find((e) => e.address === address))
    .filter((e): e is EventDefinition => e !== undefined) || [];

  const handleRelatedEventClick = (address: string) => {
    const encodedName = encodeURIComponent(address);
    navigate(`/events/${encodedName}`);
  };

  return (
    <div className="p-6 dark:bg-gray-900 h-full min-h-screen overflow-y-auto">
      {/* Back Button */}
      <button
        onClick={() => navigate("/events")}
        className="mb-4 flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
      >
        <svg
          className="h-4 w-4 mr-2"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 19l-7-7 7-7"
          />
        </svg>
        返回事件列表
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <span className="text-2xl">{badge.icon}</span>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100">
            {event.address}
          </h1>
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>
        <p className="text-lg text-gray-600 dark:text-gray-400 mt-2">
          {event.description}
        </p>
      </div>

      {/* Metadata */}
      <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            Mod
          </div>
          <div className="text-base text-gray-900 dark:text-gray-100">
            {event.mod}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-1">
            Type
          </div>
          <div className="text-base text-gray-900 dark:text-gray-100">
            {event.type === "operation"
              ? "Operation (request-response)"
              : event.type === "response"
              ? "Response"
              : "Notification"}
          </div>
        </div>
      </div>

      {/* Related Events */}
      {relatedEvents.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            相关事件
          </h2>
          <div className="space-y-2">
            {relatedEvents.map((relatedEvent) => (
              <button
                key={relatedEvent.address}
                onClick={() => handleRelatedEventClick(relatedEvent.address)}
                className="block w-full text-left px-4 py-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
                    {relatedEvent.address}
                  </span>
                  <svg
                    className="h-4 w-4 text-gray-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                </div>
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {relatedEvent.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Request Payload (for operation events) */}
      {event.type === "operation" && event.requestPayload && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Request Payload
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <SchemaViewer schema={event.requestPayload} />
          </div>
        </div>
      )}

      {/* Response Payload (for operation events) */}
      {event.type === "operation" && event.responsePayload && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Response Payload
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <SchemaViewer schema={event.responsePayload} />
          </div>
        </div>
      )}

      {/* Payload (for notification events) */}
      {event.type === "notification" && event.payload && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Payload
          </h2>
          <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
            <SchemaViewer schema={event.payload} />
          </div>
        </div>
      )}

      {/* Examples (for operation events only) */}
      {event.type === "operation" && (
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-3">
            Examples
          </h2>
          <div className="space-y-4">
            {event.requestPayload && (
              <CodeExample
                title="Request Example (Python)"
                schema={event.requestPayload}
                language="python"
              />
            )}
            {event.requestPayload && (
              <CodeExample
                title="Request Example (JavaScript)"
                schema={event.requestPayload}
                language="javascript"
              />
            )}
            {event.responsePayload && (
              <CodeExample
                title="Response Example"
                schema={event.responsePayload}
                language="json"
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default EventDetail;
