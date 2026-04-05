const state = {
  entries: [],
  config: null,
  lastFetchedAt: null,
};

const elements = {
  pageTitle: document.getElementById("page-title"),
  refreshButton: document.getElementById("refresh-button"),
  statusPill: document.getElementById("status-pill"),
  topEmission: document.getElementById("top-emission"),
  totalEmission: document.getElementById("total-emission"),
  validatorCount: document.getElementById("validator-count"),
  minerCount: document.getElementById("miner-count"),
  roleFilter: document.getElementById("role-filter"),
  searchInput: document.getElementById("search-input"),
  limitInput: document.getElementById("limit-input"),
  leaderboardBody: document.getElementById("leaderboard-body"),
  tableMeta: document.getElementById("table-meta"),
};

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function formatDate(epochSeconds) {
  if (!epochSeconds) {
    return "never";
  }
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

function truncateMiddle(value, head = 8, tail = 6) {
  if (!value) {
    return "-";
  }
  if (value.length <= head + tail + 3) {
    return value;
  }
  return `${value.slice(0, head)}...${value.slice(-tail)}`;
}

function applyFilters(entries) {
  const roleFilter = elements.roleFilter.value;
  const search = elements.searchInput.value.trim().toLowerCase();
  const limit = Number(elements.limitInput.value);

  return entries
    .filter((entry) => roleFilter === "all" || entry.role === roleFilter)
    .filter((entry) => {
      if (!search) {
        return true;
      }
      return (
        String(entry.uid).includes(search) ||
        (entry.hotkey || "").toLowerCase().includes(search)
      );
    })
    .slice(0, limit);
}

function renderTable() {
  const filteredEntries = applyFilters(state.entries);

  if (!filteredEntries.length) {
    elements.leaderboardBody.innerHTML =
      '<tr><td colspan="6" class="empty-state">No subnet rows matched the current filters.</td></tr>';
    return;
  }

  elements.leaderboardBody.innerHTML = filteredEntries
    .map(
      (entry, index) => `
        <tr>
          <td><span class="rank-pill">#${index + 1}</span></td>
          <td class="uid-cell">${entry.uid}</td>
          <td><span class="role-pill ${entry.role || "unknown"}">${entry.role || "unknown"}</span></td>
          <td class="emission-cell">${formatNumber(entry.emission, 6)}</td>
          <td>${formatNumber(entry.stake, 4)}</td>
          <td class="hotkey-cell" title="${entry.hotkey || ""}">${truncateMiddle(entry.hotkey)}</td>
        </tr>
      `
    )
    .join("");
}

function renderSummary(summary) {
  elements.topEmission.textContent = formatNumber(summary.top_emission, 6);
  elements.totalEmission.textContent = formatNumber(summary.total_emission, 6);
  elements.validatorCount.textContent = formatNumber(summary.validator_count, 0);
  elements.minerCount.textContent = formatNumber(summary.miner_count, 0);
}

async function loadConfig() {
  const response = await fetch("/api/config");
  const config = await response.json();
  state.config = config;
  if (config.title) {
    elements.pageTitle.textContent = config.title;
    document.title = config.title;
  }
}

async function fetchLeaderboard(forceRefresh = false) {
  elements.statusPill.textContent = forceRefresh ? "Refreshing..." : "Updating...";

  const response = await fetch(
    `/api/subnet-stats?limit=100${forceRefresh ? "&refresh=1" : ""}`
  );
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error || "Failed to load subnet stats.");
  }

  state.entries = payload.entries || [];
  state.lastFetchedAt = payload.fetched_at;
  renderSummary(payload.summary || {});
  renderTable();

  const networkText = [payload.network, payload.netuid ? `netuid ${payload.netuid}` : null]
    .filter(Boolean)
    .join(" • ");
  elements.tableMeta.textContent =
    `${payload.count} rows • ${networkText || "subnet"} • updated ${formatDate(payload.fetched_at)}`;
  elements.statusPill.textContent = `Live • ${formatDate(payload.fetched_at)}`;
}

async function refresh(forceRefresh = false) {
  try {
    await fetchLeaderboard(forceRefresh);
  } catch (error) {
    elements.statusPill.textContent = "Offline";
    elements.tableMeta.textContent = error.message;
    elements.leaderboardBody.innerHTML = `<tr><td colspan="6" class="empty-state">${error.message}</td></tr>`;
  }
}

elements.refreshButton.addEventListener("click", () => refresh(true));
elements.roleFilter.addEventListener("change", renderTable);
elements.searchInput.addEventListener("input", renderTable);
elements.limitInput.addEventListener("change", renderTable);

async function bootstrap() {
  try {
    await loadConfig();
  } catch (error) {
    elements.statusPill.textContent = "Config unavailable";
  }

  await refresh(true);
  window.setInterval(() => refresh(false), 30000);
}

bootstrap();
