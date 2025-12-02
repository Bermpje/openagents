import React, { useMemo } from "react";
import { EventDefinition } from "@/services/eventExplorerService";

interface EventListProps {
  events: EventDefinition[];
  onEventClick: (event: EventDefinition) => void;
}

const EventList: React.FC<EventListProps> = ({ events, onEventClick }) => {
  // Group events by mod
  const eventsByMod = useMemo(() => {
    const grouped: Record<string, EventDefinition[]> = {};
    events.forEach((event) => {
      if (!grouped[event.mod]) {
        grouped[event.mod] = [];
      }
      grouped[event.mod].push(event);
    });
    return grouped;
  }, [events]);

  const mods = Object.keys(eventsByMod).sort();

  if (events.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500 dark:text-gray-400">
          没有找到匹配的事件
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {mods.map((mod) => (
        <div
          key={mod}
          className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
        >
          <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {mod} ({eventsByMod[mod].length} events)
            </h2>
          </div>
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {eventsByMod[mod].map((event) => (
              <EventListItem
                key={event.address}
                event={event}
                onClick={() => onEventClick(event)}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

interface EventListItemProps {
  event: EventDefinition;
  onClick: () => void;
}

const EventListItem: React.FC<EventListItemProps> = ({ event, onClick }) => {
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

    const badge = badges[type as keyof typeof badges] || badges.operation;
    return badge;
  };

  const badge = getTypeBadge(event.type);

  return (
    <div
      onClick={onClick}
      className="px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 cursor-pointer transition-colors"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-1">
            <span className="text-sm">{badge.icon}</span>
            <h3 className="text-base font-medium text-gray-900 dark:text-gray-100 truncate">
              {event.address}
            </h3>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${badge.className}`}
            >
              {badge.label}
            </span>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
            {event.description}
          </p>
        </div>
        <div className="ml-4 flex-shrink-0">
          <svg
            className="h-5 w-5 text-gray-400"
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
      </div>
    </div>
  );
};

export default EventList;
