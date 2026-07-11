/**
 * Smorch Profile — Edit profile form and stats auto-refresh.
 */

(function () {
  "use strict";

  // ── DOM refs ──

  const form = document.getElementById("profile-form");
  const feedback = document.getElementById("save-feedback");

  // ── Helpers ──

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // ── Form submission ──

  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();

      const data = {
        name: document.getElementById("input-name").value.trim(),
        nickname: document.getElementById("input-nickname").value.trim(),
        email: document.getElementById("input-email").value.trim(),
      };

      feedback.textContent = "Saving…";
      feedback.className = "save-feedback";

      try {
        const resp = await fetch("/api/user/profile", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });

        if (!resp.ok) {
          const err = await resp.json();
          feedback.textContent = err.error || "Failed to save changes";
          feedback.className = "save-feedback error";
          return;
        }

        feedback.textContent = "✅ Changes saved!";
        feedback.className = "save-feedback success";

        // Clear feedback after 3 seconds
        setTimeout(() => {
          feedback.textContent = "";
          feedback.className = "save-feedback";
        }, 3000);
      } catch (err) {
        feedback.textContent = "❌ Network error — could not save";
        feedback.className = "save-feedback error";
        console.error("Profile save error:", err);
      }
    });
  }

  // ── Auto-refresh stats ──

  async function refreshStats() {
    try {
      const resp = await fetch("/api/user/stats");
      if (!resp.ok) return;
      const data = await resp.json();

      // Update stat cards
      const elTasksTotal = document.getElementById("stat-tasks-total");
      const elTimeTotal = document.getElementById("stat-time-total");
      const elStreak = document.getElementById("stat-streak");
      const elSessions = document.getElementById("stat-sessions");
      const elTasksToday = document.getElementById("stat-tasks-today");
      const elTimeToday = document.getElementById("stat-time-today");

      if (elTasksTotal) elTasksTotal.textContent = data.tasks_completed_total;
      if (elTimeTotal) elTimeTotal.textContent = data.time_tracked_total;
      if (elStreak) elStreak.textContent = data.current_streak + "d";
      if (elSessions) elSessions.textContent = data.timer_sessions_total;
      if (elTasksToday) elTasksToday.textContent = data.tasks_completed_today;
      if (elTimeToday) elTimeToday.textContent = data.time_tracked_today;
    } catch (err) {
      console.error("Failed to refresh stats:", err);
    }
  }

  // Refresh every 30 seconds
  setInterval(refreshStats, 30000);
})();