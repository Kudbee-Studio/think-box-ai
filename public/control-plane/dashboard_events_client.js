/**
 * Dashboard Events Client — paginated event fetching with backpressure awareness.
 *
 * Handles cursor-based pagination (offset/limit) and tracks dropped events
 * due to subscriber queue backpressure at the server.
 */

const DASHBOARD_API_BASE = "/api/v1/control-plane";

/**
 * Fetch paginated dashboard events.
 *
 * @param {Object} options
 * @param {string} options.token - governance token (required)
 * @param {number} options.limit - items per page (default 100, max 1000)
 * @param {number} options.offset - items to skip from start (default 0)
 * @returns {Promise<Object>} - {events, total, offset, limit, has_more, next_offset}
 */
async function fetchDashboardEvents(options = {}) {
  const { token, limit = 100, offset = 0 } = options;

  if (!token) {
    throw new Error("governance token required");
  }

  const url = new URL(`${DASHBOARD_API_BASE}/dashboard/events`, window.location.origin);
  url.searchParams.set("limit", Math.min(Math.max(1, limit), 1000));
  url.searchParams.set("offset", Math.max(0, offset));

  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard events: ${response.statusText}`);
  }

  const data = await response.json();
  return data.data || data;
}

/**
 * Fetch event drop count (subscriber queue backpressure).
 *
 * @param {string} token - governance token (required)
 * @returns {Promise<number>} - count of dropped events
 */
async function fetchEventDropCount(token) {
  if (!token) {
    throw new Error("governance token required");
  }

  const url = `${DASHBOARD_API_BASE}/dashboard/events/drops`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch event drops: ${response.statusText}`);
  }

  const data = await response.json();
  return data.data?.dropped_events || 0;
}

/**
 * Fetch lightweight dashboard summary (counts only, no event data).
 *
 * @param {string} token - governance token (required)
 * @returns {Promise<Object>} - dashboard summary
 */
async function fetchDashboardSummary(token) {
  if (!token) {
    throw new Error("governance token required");
  }

  const url = `${DASHBOARD_API_BASE}/dashboard/summary`;
  const response = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch dashboard summary: ${response.statusText}`);
  }

  const data = await response.json();
  return data.data || data;
}

/**
 * Paginator helper to manage offset-based pagination.
 */
class EventPaginator {
  constructor(options = {}) {
    this.token = options.token;
    this.limit = options.limit || 100;
    this.offset = 0;
    this.total = 0;
    this.events = [];
    this.has_more = false;
  }

  /**
   * Fetch the next page of events.
   *
   * @returns {Promise<Object>} - page result {events, total, has_more}
   */
  async fetchNext() {
    const result = await fetchDashboardEvents({
      token: this.token,
      limit: this.limit,
      offset: this.offset,
    });

    this.offset = result.offset;
    this.total = result.total;
    this.has_more = result.has_more;
    this.events = result.events || [];

    return {
      events: this.events,
      total: this.total,
      has_more: this.has_more,
      offset: this.offset,
    };
  }

  /**
   * Fetch the previous page of events.
   *
   * @returns {Promise<Object>} - page result {events, total, has_more}
   */
  async fetchPrev() {
    this.offset = Math.max(0, this.offset - this.limit);
    return this.fetchNext();
  }

  /**
   * Jump to a specific offset.
   *
   * @param {number} offset
   * @returns {Promise<Object>} - page result
   */
  async jumpTo(offset) {
    this.offset = Math.max(0, offset);
    return this.fetchNext();
  }

  /**
   * Fetch all events (may be memory-intensive for large datasets).
   *
   * @returns {Promise<Array>} - all events
   */
  async fetchAll() {
    const allEvents = [];
    let offset = 0;
    let hasMore = true;

    while (hasMore) {
      const result = await fetchDashboardEvents({
        token: this.token,
        limit: 1000, // fetch max per request
        offset,
      });

      allEvents.push(...result.events);
      offset = result.next_offset || offset + this.limit;
      hasMore = result.has_more;
    }

    return allEvents;
  }
}

// Export for use in HTML
if (typeof window !== "undefined") {
  window.DashboardEventsClient = {
    fetchDashboardEvents,
    fetchEventDropCount,
    fetchDashboardSummary,
    EventPaginator,
  };
}
