import React, { useState, useEffect, useMemo } from "react";
import { Routes, Route, useNavigate, useParams } from "react-router-dom";
import {
  fetchAllEventDefinitions,
  getModsFromEvents,
  filterEventsByMod,
  filterEventsByType,
  searchEvents,
  EventDefinition,
} from "@/services/eventExplorerService";
import EventList from "./components/EventList";
import EventDetail from "./components/EventDetail";

const EventsMainPage: React.FC = () => {
  return (
    <Routes>
      <Route index element={<EventExplorer />} />
      <Route path=":eventName" element={<EventDetailView />} />
    </Routes>
  );
};

/**
 * Main Event Explorer component
 */
const EventExplorer: React.FC = () => {
  const [events, setEvents] = useState<EventDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMod, setSelectedMod] = useState<string>("all");
  const [selectedType, setSelectedType] = useState<string>("all");
  const navigate = useNavigate();

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    try {
      setLoading(true);
      setError(null);
      const allEvents = await fetchAllEventDefinitions();
      setEvents(allEvents);
    } catch (err: any) {
      setError(err.message || "Failed to load events");
      console.error("Failed to load events:", err);
    } finally {
      setLoading(false);
    }
  };

  const mods = useMemo(() => getModsFromEvents(events), [events]);

  const filteredEvents = useMemo(() => {
    let filtered = events;

    // Apply search
    if (searchQuery) {
      filtered = searchEvents(filtered, searchQuery);
    }

    // Apply mod filter
    if (selectedMod !== "all") {
      filtered = filterEventsByMod(filtered, selectedMod);
    }

    // Apply type filter
    if (selectedType !== "all") {
      filtered = filterEventsByType(filtered, selectedType);
    }

    return filtered;
  }, [events, searchQuery, selectedMod, selectedType]);

  const handleEventClick = (event: EventDefinition) => {
    // Encode event name for URL
    const encodedName = encodeURIComponent(event.address);
    navigate(`/events/${encodedName}`);
  };

  if (loading) {
    return (
      <div className="p-6 dark:bg-gray-900 h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">
            正在加载事件定义...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 dark:bg-gray-900 h-full">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
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
            <div className="ml-3 flex-1">
              <h3 className="text-sm font-medium text-red-800 dark:text-red-200">
                加载事件定义失败
              </h3>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">
                {error}
              </p>
              <button
                onClick={loadEvents}
                className="mt-2 text-sm bg-red-100 dark:bg-red-800 text-red-800 dark:text-red-200 px-3 py-1 rounded hover:bg-red-200 dark:hover:bg-red-700 transition-colors"
              >
                重试
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 dark:bg-gray-900 h-full min-h-screen overflow-y-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-2">
          Event Explorer
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          浏览和搜索 OpenAgents 事件系统
        </p>
      </div>

      {/* Search and Filters */}
      <div className="mb-6 space-y-4">
        {/* Search Bar */}
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
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
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
          <input
            type="text"
            placeholder="搜索事件..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md leading-5 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-4">
          {/* Mod Filter */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Mod
            </label>
            <select
              value={selectedMod}
              onChange={(e) => setSelectedMod(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Mods</option>
              {mods.map((mod) => (
                <option key={mod} value={mod}>
                  {mod}
                </option>
              ))}
            </select>
          </div>

          {/* Type Filter */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Type
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Types</option>
              <option value="operation">Operation</option>
              <option value="response">Response</option>
              <option value="notification">Notification</option>
            </select>
          </div>
        </div>

        {/* Results Count */}
        <div className="text-sm text-gray-600 dark:text-gray-400">
          找到 {filteredEvents.length} 个事件
        </div>
      </div>

      {/* Event List */}
      <EventList
        events={filteredEvents}
        onEventClick={handleEventClick}
      />
    </div>
  );
};

/**
 * Event Detail View Component
 */
const EventDetailView: React.FC = () => {
  const { eventName } = useParams<{ eventName: string }>();
  const navigate = useNavigate();
  const [events, setEvents] = useState<EventDefinition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadEvents();
  }, []);

  const loadEvents = async () => {
    try {
      const allEvents = await fetchAllEventDefinitions();
      setEvents(allEvents);
    } catch (err) {
      console.error("Failed to load events:", err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 dark:bg-gray-900 h-full flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  const decodedName = eventName ? decodeURIComponent(eventName) : "";
  const event = events.find((e) => e.address === decodedName);

  if (!event) {
    return (
      <div className="p-6 dark:bg-gray-900 h-full">
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
          <p className="text-yellow-800 dark:text-yellow-200">
            未找到事件: {decodedName}
          </p>
          <button
            onClick={() => navigate("/events")}
            className="mt-2 text-sm bg-yellow-100 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200 px-3 py-1 rounded hover:bg-yellow-200 dark:hover:bg-yellow-700 transition-colors"
          >
            返回事件列表
          </button>
        </div>
      </div>
    );
  }

  return <EventDetail event={event} allEvents={events} />;
};

export default EventsMainPage;
