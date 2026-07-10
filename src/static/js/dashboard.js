/**
 * Smorch Dashboard — Timer, Stats, Log, and Workflow interactivity.
 */

(function () {
  "use strict";

  // ── State ──

  let timerState = {
    active: false,
    paused: false,
    remaining: 1500, // seconds
    duration: 1500,
    sessionId: null,
    taskId: null,
  };

  let timerInterval = null;

  // ── DOM refs ──

  const timerDisplay = document.getElementById("timer-display");
  const taskSelect = document.getElementById("timer-task-select");
  const btnStart = document.getElementById("btn-start");
  const btnPause = document.getElementById("btn-pause");
  const btnReset = document.getElementById("btn-reset");
  const logFeed = document.getElementById("log-feed");

  // ── Display helpers ──

  function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  function updateDisplay() {
    timerDisplay.textContent = formatTime(timerState.remaining);
  }

  // ── API calls ──

  async function postJson(url, data) {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return resp.json();
  }

  async function getJson(url) {
    const resp = await fetch(url);
    return resp.json();
  }

  // ── Timer logic ──

  function stopTimerClient() {
    if (timerInterval) {
      clearInterval(timerInterval);
      timerInterval = null;
    }
    timerState.active = false;
    timerState.paused = false;
  }

  function tick() {
    if (timerState.paused) return;

    if (timerState.remaining <= 0) {
      // Timer completed
      stopTimerClient();
      updateDisplay();
      postJson("/api/timer/stop", { actual_seconds: timerState.duration });
      refreshLog();
      refreshStats();
      btnStart.textContent = "▶ Start";
      return;
    }

    timerState.remaining -= 1;
    updateDisplay();
  }

  function startTimerClient() {
    if (timerInterval) clearInterval(timerInterval);
    timerState.active = true;
    timerState.paused = false;
    timerInterval = setInterval(tick, 1000);
    btnStart.textContent = "▶ Running";
  }

  // ── Button handlers ──

  btnStart.addEventListener("click", async function () {
    if (timerState.active && !timerState.paused) {
      // Pause
      timerState.paused = true;
      btnStart.textContent = "▶ Resume";
      return;
    }

    if (timerState.paused) {
      // Resume
      timerState.paused = false;
      btnStart.textContent = "▶ Running";
      return;
    }

    // Start new timer
    const taskId = taskSelect.value ? parseInt(taskSelect.value) : null;
    const duration = timerState.duration;

    try {
      const data = await postJson("/api/timer/start", {
        task_id: taskId,
        duration: duration,
      });
      timerState.sessionId = data.id;
      timerState.taskId = data.task_id;
      timerState.duration = data.duration;
      timerState.remaining = data.duration;
      timerState.active = true;
      timerState.paused = false;
      updateDisplay();
      startTimerClient();
    } catch (err) {
      console.error("Failed to start timer:", err);
    }
  });

  btnPause.addEventListener("click", function () {
    if (!timerState.active) return;
    timerState.paused = true;
    btnStart.textContent = "▶ Resume";
    // Optionally notify server (not critical for MVP)
  });

  btnReset.addEventListener("click", async function () {
    stopTimerClient();
    timerState.remaining = timerState.duration;
    timerState.sessionId = null;
    timerState.taskId = null;
    updateDisplay();
    btnStart.textContent = "▶ Start";

    // Stop on server if active
    try {
      await postJson("/api/timer/stop", { actual_seconds: 0 });
    } catch (_) {
      // ignore if no active session
    }
  });

  // ── Workflow: Start timer from task ──

  document.querySelectorAll(".btn-start-timer").forEach((btn) => {
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      const taskId = this.dataset.taskId;
      // Select the task in the dropdown
      if (taskSelect) {
        taskSelect.value = taskId;
      }
      // Auto-start timer with default duration
      btnStart.click();
    });
  });

  // ── Duration selector ──
  // Click on timer display cycles through common durations

  timerDisplay.addEventListener("click", function () {
    const presets = [1500, 3000, 600, 900]; // 25min, 50min, 10min, 15min
    const current = timerState.duration;
    let next = presets[0];
    for (const p of presets) {
      if (p !== current) {
        next = p;
        break;
      }
    }
    // Find next different preset
    const idx = presets.indexOf(current);
    if (idx !== -1 && idx < presets.length - 1) {
      next = presets[idx + 1];
    }
    // Rotate
    const nextIdx = presets.indexOf(current) + 1;
    timerState.duration = presets[nextIdx % presets.length];
    if (!timerState.active) {
      timerState.remaining = timerState.duration;
      updateDisplay();
    }
  });

  // ── Auto-refresh stats and log ──

  async function refreshStats() {
    try {
      const data = await getJson("/api/stats");
      const statsCol = document.querySelector(".col-stats");
      if (!statsCol) return;
      const rows = statsCol.querySelectorAll(".stat-row");
      if (rows.length >= 4) {
        rows[0].querySelector(".stat-value").textContent =
          data.tasks_completed_today;
        rows[1].querySelector(".stat-value").textContent =
          data.time_tracked_today;
        rows[2].querySelector(".stat-value").textContent = data.current_streak + "d";
        rows[3].querySelector(".stat-value").textContent = data.total_tasks;
      }
    } catch (err) {
      console.error("Failed to refresh stats:", err);
    }
  }

  async function refreshLog() {
    try {
      const entries = await getJson("/api/log");
      if (!logFeed) return;
      logFeed.innerHTML = entries
        .map(
          (e) =>
            `<li class="log-entry log-${e.action_type}">
              <span class="log-icon">${e.icon}</span>
              <span class="log-text">${escapeHtml(e.description)}</span>
              <span class="log-time">${escapeHtml(e.relative_time)}</span>
            </li>`
        )
        .join("");
    } catch (err) {
      console.error("Failed to refresh log:", err);
    }
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Refresh every 30 seconds
  setInterval(() => {
    refreshStats();
    refreshLog();
  }, 30000);

  // ── Restore active timer on page load ──

  async function restoreTimer() {
    try {
      const data = await getJson("/api/timer/status");
      if (data.active) {
        timerState.active = true;
        timerState.sessionId = data.id;
        timerState.taskId = data.task_id;
        timerState.duration = data.duration;
        timerState.remaining = data.remaining;
        timerState.paused = data.status === "paused";
        updateDisplay();
        if (data.task_id && taskSelect) {
          taskSelect.value = data.task_id;
        }
        if (!timerState.paused) {
          startTimerClient();
          btnStart.textContent = "▶ Running";
        } else {
          btnStart.textContent = "▶ Resume";
        }
      }
    } catch (err) {
      console.error("Failed to restore timer:", err);
    }
  }

  restoreTimer();
})();