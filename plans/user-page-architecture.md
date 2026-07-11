# User / Profile Page Architecture

## Overview

A new profile page at `/profile` where the user can edit their personal info and view aggregated statistics. The nav link already exists in [`base.html`](src/templates/base.html:14) (`<a href="/profile">Profile</a>`), but the route returns a 404.

## Layout Concept

```
┌──────────────────────────────────────────────────────────────┐
│  Nav: Smorch | Dashboard | Projects | Profile ← active       │
├──────────────────────────┬───────────────────────────────────┤
│  LEFT: PROFILE FORM      │  RIGHT: STATISTICS                │
│                          │                                   │
│  ┌────────────────────┐  │  ┌─────────────────────────────┐  │
│  │ 👤 Avatar area     │  │  │ 📊 Personal Stats           │  │
│  │                    │  │  │                             │  │
│  │ Name: [______]     │  │  │   Tasks completed   {n}     │  │
│  │ Nickname: [______] │  │  │   Time tracked      {x}h   │  │
│  │ Email: [______]    │  │  │   Current streak    {n}d   │  │
│  │                    │  │  │   Timer sessions    {n}     │  │
│  │ [💾 Save Changes]  │  │  │   Member since      {date} │  │
│  └────────────────────┘  │  │   Total tasks       {n}     │  │
│                          │  └─────────────────────────────┘  │
│                          │                                   │
│                          │  ┌─────────────────────────────┐  │
│                          │  │ ⏱ Recent Activity (log)     │  │
│                          │  │   - Task completed          │  │
│                          │  │   - Timer finished          │  │
│                          │  │   - ...                     │  │
│                          │  └─────────────────────────────┘  │
└──────────────────────────┴───────────────────────────────────┘
```

## 1. Files to Create / Modify

### New files:

| File | Purpose |
|------|---------|
| [`src/routes/user.py`](src/routes/user.py) | New blueprint: profile page, profile API, user stats API |
| [`src/templates/profile.html`](src/templates/profile.html) | Profile page: edit form + stats display |
| [`src/static/js/profile.js`](src/static/js/profile.js) | Inline editing, form submission, stats auto-refresh |
| [`tests/test_user.py`](tests/test_user.py) | Tests for user routes and API endpoints |

### Modified files:

| File | Change |
|------|--------|
| [`src/models/__init__.py`](src/models/__init__.py:1) | Export `User` and `Follow` models (currently missing) |
| [`src/app.py`](src/app.py:28) | Register `user_bp` blueprint |
| [`src/static/css/style.css`](src/static/css/style.css:1) | Add profile page styles |

## 2. Data Model

The existing [`User`](src/models/base.py:111) model has all needed fields:

| Field | Type | Usage |
|-------|------|-------|
| `id` | Integer (PK) | Identifier |
| `name` | String(150) | Full name — editable |
| `nickname` | String(80), unique | Display name — editable |
| `email` | String(254), unique | Email — editable |
| `password_hash` | String(256) | Not editable on this page (no auth yet) |
| `created_dttm` | DateTime | "Member since" date — read-only |
| `is_deleted` | Boolean | Logical deletion — not exposed |

**Note:** `User` and `Follow` are NOT exported from [`src/models/__init__.py`](src/models/__init__.py:1). This must be fixed so the blueprint can import them.

## 3. Routes — [`src/routes/user.py`](src/routes/user.py)

### Blueprint: `user_bp`

### Page Route

| Method | Path | Description |
|--------|------|-------------|
| GET | `/profile` | Render profile page with user data + stats |

### API Endpoints (for dynamic updates via JS)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/user/profile` | Return current user profile data as JSON |
| PUT | `/api/user/profile` | Update profile fields (name, nickname, email) |
| GET | `/api/user/stats` | Return user's aggregated statistics |

### Route Details

#### `GET /profile`
- Fetch user by `_DEFAULT_USER_ID` (currently `1`)
- Fetch aggregated stats (same as below)
- Render `profile.html`

#### `GET /api/user/profile`
- Return JSON: `{id, name, nickname, email, created_dttm}`

#### `PUT /api/user/profile`
- Accept JSON body: `{name, nickname, email}`
- Validate unique constraints on `nickname` and `email`
- Update and commit
- Return updated profile

#### `GET /api/user/stats`
- Aggregate and return:
  - `tasks_completed_total` — COUNT of Task where completed=True
  - `tasks_completed_today` — same, filtered to today
  - `time_tracked_total` — SUM of TimerSession.actual_seconds where status=completed
  - `time_tracked_today` — same, filtered to today
  - `current_streak` — consecutive days with at least 1 completed task
  - `timer_sessions_total` — COUNT of TimerSession
  - `member_since` — user's `created_dttm` formatted
  - `total_tasks` — COUNT of all tasks

### Reusable Helpers

Extract helpers from [`dashboard.py`](src/routes/dashboard.py:16) into shared utility or duplicate minimally:

- `_format_duration(seconds)` — shared via import or duplicate
- `_relative_time(dt)` — shared via import or duplicate

**Recommendation:** Duplicate in `user.py` for now to keep blueprints independent (following current pattern). Refactor into a shared module later.

## 4. Template — [`src/templates/profile.html`](src/templates/profile.html)

```html
{% extends "base.html" %}
{% block title %}Profile — Smorch{% endblock %}
{% block content %}

<div class="profile-layout">

    {# ── Left Column: Edit Profile ── #}
    <section class="profile-card">
        <h2>Edit Profile</h2>

        <div class="avatar-section">
            <div class="avatar-placeholder">{{ user.name[:1] }}</div>
        </div>

        <form id="profile-form">
            <div class="form-group">
                <label for="input-name">Full Name</label>
                <input type="text" id="input-name" name="name"
                       value="{{ user.name }}" required>
            </div>

            <div class="form-group">
                <label for="input-nickname">Nickname</label>
                <input type="text" id="input-nickname" name="nickname"
                       value="{{ user.nickname }}" required>
            </div>

            <div class="form-group">
                <label for="input-email">Email</label>
                <input type="email" id="input-email" name="email"
                       value="{{ user.email }}" required>
            </div>

            <div class="form-actions">
                <button type="submit" class="btn-save">💾 Save Changes</button>
                <span class="save-feedback" id="save-feedback"></span>
            </div>
        </form>

        <div class="member-info">
            Member since: <strong>{{ user.created_dttm.strftime('%B %Y') }}</strong>
        </div>
    </section>

    {# ── Right Column: Statistics ── #}
    <section class="profile-stats">
        <h2>Your Statistics</h2>

        <div class="stats-grid">
            <div class="stat-item">
                <span class="stat-value-lg">{{ stats.tasks_completed_total }}</span>
                <span class="stat-label">Tasks completed</span>
            </div>
            <div class="stat-item">
                <span class="stat-value-lg">{{ stats.time_tracked_total }}</span>
                <span class="stat-label">Total time tracked</span>
            </div>
            <div class="stat-item">
                <span class="stat-value-lg">{{ stats.current_streak }}d</span>
                <span class="stat-label">Current streak</span>
            </div>
            <div class="stat-item">
                <span class="stat-value-lg">{{ stats.timer_sessions_total }}</span>
                <span class="stat-label">Timer sessions</span>
            </div>
        </div>

        <h3>Today</h3>
        <div class="today-stats">
            <div class="stat-row">
                <span class="stat-label">Tasks completed</span>
                <span class="stat-value">{{ stats.tasks_completed_today }}</span>
            </div>
            <div class="stat-row">
                <span class="stat-label">Time tracked</span>
                <span class="stat-value">{{ stats.time_tracked_today }}</span>
            </div>
        </div>

        <h3>Recent Activity</h3>
        <ul class="log-feed">
            {% for entry in log_entries %}
            <li class="log-entry">
                <span class="log-icon">{{ log_icon(entry.action_type) }}</span>
                <span class="log-text">{{ entry.description }}</span>
                <span class="log-time">{{ entry.created_at|reltime }}</span>
            </li>
            {% else %}
            <li class="log-entry">
                <span class="log-text">No activity yet</span>
            </li>
            {% endfor %}
        </ul>
    </section>

</div>

{% endblock %}
```

Uses existing [`log_icon()`](src/routes/dashboard.py:68) global and [`reltime`](src/routes/dashboard.py:63) filter from dashboard blueprint.

**Note:** Jinja2 template globals/filters registered on `dashboard_bp` are NOT automatically available to `user_bp`. The `log_icon()` global and `reltime` filter must either be:
- Registered on the app directly in [`app.py`](src/app.py:15) (recommended fix)
- Or duplicated in `user.py` (simpler for now)

**Decision:** Duplicate the filter/global registration in `user.py` to keep changes minimal and independent.

## 5. JavaScript — [`src/static/js/profile.js`](src/static/js/profile.js)

### Features

| Feature | Implementation |
|---------|---------------|
| Form submission | Intercept `submit` event, PUT JSON to `/api/user/profile`, show feedback |
| Validation feedback | Show success/error message near save button |
| Auto-refresh stats | Poll `/api/user/stats` every 30 seconds |
| Inline feedback | Highlight saved fields briefly |

### Pseudo-code

```javascript
(function () {
  "use strict";

  const form = document.getElementById("profile-form");
  const feedback = document.getElementById("save-feedback");

  // ── Form submission ──
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const data = {
      name: document.getElementById("input-name").value,
      nickname: document.getElementById("input-nickname").value,
      email: document.getElementById("input-email").value,
    };

    try {
      const resp = await fetch("/api/user/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!resp.ok) {
        const err = await resp.json();
        feedback.textContent = err.error || "Failed to save";
        feedback.className = "save-feedback error";
        return;
      }
      feedback.textContent = "✅ Changes saved!";
      feedback.className = "save-feedback success";
      setTimeout(() => { feedback.textContent = ""; }, 3000);
    } catch (err) {
      feedback.textContent = "❌ Network error";
      feedback.className = "save-feedback error";
    }
  });

  // ── Auto-refresh stats ──
  async function refreshStats() {
    try {
      const data = await fetch("/api/user/stats").then(r => r.json());
      // Update DOM elements...
    } catch (err) {
      console.error("Failed to refresh stats:", err);
    }
  }

  setInterval(refreshStats, 30000);
})();
```

## 6. CSS Additions — [`src/static/css/style.css`](src/static/css/style.css)

```css
/* ── Profile Page ── */

.profile-layout {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    align-items: start;
}

.profile-card,
.profile-stats {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 1.5rem;
    border: 1px solid var(--border);
}

.profile-card h2,
.profile-stats h2 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
}

/* Avatar */
.avatar-section {
    display: flex;
    justify-content: center;
    margin-bottom: 1.5rem;
}

.avatar-placeholder {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    font-size: 2rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
}

/* Form */
.form-group {
    margin-bottom: 1rem;
}

.form-group label {
    display: block;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 0.25rem;
}

.form-group input {
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-size: 0.9rem;
    transition: border-color 0.15s;
}

.form-group input:focus {
    outline: none;
    border-color: var(--accent);
}

.form-actions {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1rem;
}

.btn-save {
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 0.5rem 1.25rem;
    font-size: 0.9rem;
    cursor: pointer;
    transition: opacity 0.15s;
}

.btn-save:hover {
    opacity: 0.9;
}

.save-feedback {
    font-size: 0.85rem;
}

.save-feedback.success { color: var(--success); }
.save-feedback.error { color: var(--danger); }

.member-info {
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
    font-size: 0.85rem;
    color: var(--text-muted);
}

/* Stats */
.stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1.5rem;
}

.stat-item {
    text-align: center;
    padding: 1rem;
    background: var(--bg);
    border-radius: 8px;
}

.stat-value-lg {
    display: block;
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--accent);
}

.stat-item .stat-label {
    font-size: 0.8rem;
    color: var(--text-muted);
}

.profile-stats h3 {
    font-size: 0.95rem;
    margin: 1rem 0 0.5rem 0;
    color: var(--text-muted);
}

.today-stats {
    background: var(--bg);
    border-radius: 6px;
    padding: 0.5rem 0.75rem;
}

/* Responsive */
@media (max-width: 768px) {
    .profile-layout {
        grid-template-columns: 1fr;
    }
}
```

## 7. Data Flow

```
User visits /profile
       │
       ▼
user_bp.dashboard() route
       │
       ├── Fetch User by _DEFAULT_USER_ID (1)
       ├── Fetch aggregated Stats (tasks, time, streak, sessions)
       ├── Fetch recent ActivityLog entries (last 10)
       │
       ▼
   render_template("profile.html", user=user, stats=stats, log_entries=entries)
       │
       ▼
   Browser renders form + stats
       │
       ├── User edits form → PUT /api/user/profile → DB update → JSON response
       │
       └── JS polls GET /api/user/stats every 30s → updates DOM
```

## 8. Implementation Order

| Step | Description |
|------|-------------|
| 1 | Export `User` and `Follow` from [`src/models/__init__.py`](src/models/__init__.py:1) |
| 2 | Create [`src/routes/user.py`](src/routes/user.py) with blueprint, profile page route, and API endpoints |
| 3 | Register `user_bp` in [`src/app.py`](src/app.py:28) |
| 4 | Create [`src/templates/profile.html`](src/templates/profile.html) extending `base.html` |
| 5 | Create [`src/static/js/profile.js`](src/static/js/profile.js) for form interactivity |
| 6 | Add profile CSS to [`src/static/css/style.css`](src/static/css/style.css) |
| 7 | Create [`tests/test_user.py`](tests/test_user.py) with tests for all new routes |
| 8 | Update [`PROJECT_PLAN.md`](PROJECT_PLAN.md) to mark profile/stats items as done |

## 9. Edge Cases & Error Handling

| Case | Handling |
|------|----------|
| User not found (DB missing) | Create default user on first access, or return 404 with friendly message |
| Duplicate nickname/email on update | Return 409 Conflict with error message, show in feedback UI |
| Empty name/nickname/email | Validation at form level (HTML `required`) + server-side check |
| No timer sessions yet | Stats display `0` / `0m` gracefully |
| No activity log entries | Show "No activity yet" empty state |
| Concurrent edits | Not an issue until auth/multi-user is implemented |
