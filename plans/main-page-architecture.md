# Main Page (Dashboard) Architecture

## Overview

The main page at `/dashboard` will contain three blocks **side by side in one row**:

```
┌──────────────────┬──────────────────┬──────────────────────────┐
│  BLOCK 1         │  BLOCK 2         │  BLOCK 3                 │
│  PROJECTS        │  WORKFLOW        │  TIMER + STATS + LOG     │
│                  │  (all tasks)     │                          │
│  ┌──────────────┐│  ┌──────────────┐│  ┌──────┬──────┬──────┐ │
│  │ Project card ││  │ Project A    ││  │TIMER │STATS │ LOG  │ │
│  │ Title        ││  │ ├ Sub 1      ││  │25:00 │done:5 │task │ │
│  │ 5 tasks 60%  ││  │ │ ├ Task 1   ││  │[task]│2h 30m │done │ │
│  │ [=====---]   ││  │ │ ├ Task 2   ││  │▶ ⏸ 🔄│streak │proj │ │
│  │              ││  │ │ └ ▶ Start  ││  │      │3d     │crea │ │
│  │ Project card ││  │ ├ Sub 2      ││  │      │       │ted  │ │
│  │ ...          ││  │ │ └ ...      ││  │      │       │     │ │
│  └──────────────┘│  └──────────────┘│  └──────┴──────┴──────┘ │
└──────────────────┴──────────────────┴──────────────────────────┘
```

---

## 1. Files to Create / Modify

### New files:
| File | Purpose |
|------|---------|
| [`src/templates/base.html`](src/templates/base.html) | Base layout: HTML shell, CSS/JS links, nav header |
| [`src/templates/dashboard.html`](src/templates/dashboard.html) | Main page: extends base, 3 blocks |
| [`src/static/css/style.css`](src/static/css/style.css) | All custom styles |
| [`src/static/js/dashboard.js`](src/static/js/dashboard.js) | Timer logic, stats refresh, log updates |
| [`src/routes/dashboard.py`](src/routes/dashboard.py) | Blueprint: GET `/dashboard` + API endpoints |
| [`src/models/timer.py`](src/models/timer.py) | TimerSession model |
| [`src/models/log.py`](src/models/log.py) | ActivityLog model |

### Modified files:
| File | Change |
|------|--------|
| [`src/app.py`](src/app.py:25) | Register dashboard blueprint |
| [`src/database.py`](src/database.py:13) | Import new models so `db.create_all()` picks them up |
| [`src/models/__init__.py`](src/models/__init__.py:1) | Export TimerSession, ActivityLog |

---

## 2. New Models

### TimerSession — [`src/models/timer.py`](src/models/timer.py)

```python
class TimerSession(db.Model):
    __tablename__ = "timer_sessions"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    end_time = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(db.Integer, default=0)  # planned duration
    actual_seconds = db.Column(db.Integer, default=0)     # actual elapsed
    status = db.Column(db.String(20), default="active")   # active | paused | completed | cancelled

    task = db.relationship("Task", backref="timer_sessions")
    user = db.relationship("User", backref="timer_sessions")
```

### ActivityLog — [`src/models/log.py`](src/models/log.py)

```python
class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action_type = db.Column(db.String(50), nullable=False)
    # e.g.: task_completed, task_created, timer_completed, project_created
    description = db.Column(db.String(300), default="")
    related_object_type = db.Column(db.String(50), nullable=True)  # task | project | subproject
    related_object_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", backref="activity_logs")
```

---

## 3. Routes — [`src/routes/dashboard.py`](src/routes/dashboard.py)

### Page Route

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard` | Render the main page with all 3 blocks' data |

### API Endpoints (for dynamic updates via JS)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/projects` | List all projects with subproject/task counts |
| GET | `/api/tasks` | List all tasks (for workflow block) |
| GET | `/api/stats` | Return today's stats (completions, time, streak) |
| GET | `/api/log` | Return recent activity log entries |
| POST | `/api/timer/start` | Start a timer session (optionally linked to a task) |
| POST | `/api/timer/stop` | Stop current active timer session |
| GET | `/api/timer/status` | Get current active timer status |

---

## 4. Data Flow Per Block

### Block 1 — Projects

**Data source**: `Project` model + aggregated counts from `Subproject` and `Task`

**Query** (in route):
```python
projects = Project.query.all()
for p in projects:
    subproject_count = p.subprojects.count()
    task_count = Task.query.join(Subproject).filter(
        Subproject.project_id == p.id
    ).count()
    completed_task_count = Task.query.join(Subproject).filter(
        Subproject.project_id == p.id, Task.completed == True
    ).count()
```

**Template rendering**: Loop over projects, render cards with title, counts, progress bar.

### Block 2 — Workflow

**Data source**: `Task` model joined with `Subproject` and `Project`

**Query**:
```python
tasks = Task.query.options(
    db.joinedload(Task.subproject).joinedload(Subproject.project),
    db.joinedload(Task.tags)
).order_by(Task.priority.desc(), Task.deadline.asc()).all()
```

**Template rendering**: Group tasks by `project > subproject`. Each task shows:
- Title, priority (stars/badge), complexity, deadline (relative time)
- Tags as colored badges
- "Start Timer" button → links to Block 3

### Block 3 — Timer + Stats + Log (3-column sub-layout)

#### Timer (left column)
- **Data source**: `TimerSession` model
- **Display**: Large countdown display (MM:SS), task selector dropdown, Start/Pause/Reset buttons
- **JS behavior**: 
  - On "Start" → POST `/api/timer/start` with optional `task_id` + `duration_seconds`
  - Timer ticks down client-side using JS `setInterval`
  - On "Stop" → POST `/api/timer/stop`, auto-create ActivityLog entry
  - Poll `/api/timer/status` on page load to resume display

#### Stats (center column)
- **Data source**: Aggregated from `Task` + `TimerSession`
- **Query**:
  ```python
  today = datetime.now(timezone.utc).date()
  tasks_completed_today = Task.query.filter(
      Task.completed == True,
      func.date(Task.updated_at) == today
  ).count()
  total_time_today = db.session.query(func.sum(TimerSession.actual_seconds)).filter(
      TimerSession.status == "completed",
      func.date(TimerSession.start_time) == today
  ).scalar() or 0
  ```

#### Log (right column)
- **Data source**: `ActivityLog` model
- **Query**: Last 20 entries, ordered by `created_at DESC`
- **Display**: Chronological feed with icon per action_type

---

## 5. Template Structure

### [`src/templates/base.html`](src/templates/base.html)
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Smorch{% endblock %}</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav class="top-nav">
        <a href="/dashboard" class="logo">Smorch</a>
        <a href="/projects">Projects</a>
        <a href="/dashboard">Dashboard</a>
        <a href="/profile">Profile</a>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
    <script src="{{ url_for('static', filename='js/dashboard.js') }}"></script>
</body>
</html>
```

### [`src/templates/dashboard.html`](src/templates/dashboard.html)
```html
{% extends "base.html" %}
{% block title %}Dashboard — Smorch{% endblock %}
{% block content %}

<div class="dashboard-grid">
    <!-- Block 1: Projects -->
    <section class="block block-projects">
        <h2>Projects</h2>
        <div class="project-list">
            {% for project in projects %}
            <div class="project-card">
                <h3>{{ project.title }}</h3>
                <div class="project-stats">
                    <span>{{ project_counts[project.id].task_count }} tasks</span>
                    <span>{{ project_counts[project.id].completed_pct }}% done</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {{ project_counts[project.id].completed_pct }}%"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </section>

    <!-- Block 2: Workflow -->
    <section class="block block-workflow">
        <h2>Workflow</h2>
        <div class="task-list">
            {% for group in task_groups %}
            <div class="task-group">
                <h4>{{ group.project }} › {{ group.subproject }}</h4>
                {% for task in group.tasks %}
                <div class="task-item" data-task-id="{{ task.id }}">
                    <span class="task-title">{{ task.title }}</span>
                    <span class="task-priority">P{{ task.priority }}</span>
                    <span class="task-deadline">{{ task.deadline|reltime }}</span>
                    <div class="task-tags">
                        {% for tag in task.tags %}
                        <span class="tag">{{ tag.name }}</span>
                        {% endfor %}
                    </div>
                    <button class="btn-start-timer" data-task-id="{{ task.id }}">▶ Start</button>
                </div>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
    </section>

    <!-- Block 3: Timer + Stats + Log (sub-columns) -->
    <section class="block block-timer-stats-log">
        <h2>Session</h2>
        <div class="session-subgrid">
            <!-- Timer -->
            <div class="sub-col col-timer">
                <div class="timer-display" id="timer-display">25:00</div>
                <select id="timer-task-select">
                    <option value="">No task (break)</option>
                    {% for task in all_tasks %}
                    <option value="{{ task.id }}">{{ task.title }}</option>
                    {% endfor %}
                </select>
                <div class="timer-controls">
                    <button id="btn-start">Start</button>
                    <button id="btn-pause">Pause</button>
                    <button id="btn-reset">Reset</button>
                </div>
            </div>
            <!-- Stats -->
            <div class="sub-col col-stats">
                <div class="stat-row">
                    <span class="stat-label">Completed today</span>
                    <span class="stat-value">{{ stats.tasks_completed_today }}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Time tracked</span>
                    <span class="stat-value">{{ stats.time_tracked_today }}</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Streak</span>
                    <span class="stat-value">{{ stats.current_streak }}d</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">Total tasks</span>
                    <span class="stat-value">{{ stats.total_tasks }}</span>
                </div>
            </div>
            <!-- Log -->
            <div class="sub-col col-log">
                <ul class="log-feed">
                    {% for entry in log_entries %}
                    <li class="log-entry log-{{ entry.action_type }}">
                        <span class="log-icon">{{ log_icon(entry.action_type) }}</span>
                        <span class="log-text">{{ entry.description }}</span>
                        <span class="log-time">{{ entry.created_at|reltime }}</span>
                    </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </section>
</div>

{% endblock %}
```

---

## 6. CSS Concept — [`src/static/css/style.css`](src/static/css/style.css)

Key layout decisions:
- **Main layout**: CSS Grid with 3 equal columns (`.dashboard-grid`)
- **Block 3 sub-layout**: Nested CSS Grid with 3 columns for Timer/Stats/Log (`.session-subgrid`)
- **Flexbox** for project cards within Block 1
- Clean, minimal design
- Responsive: all columns stack vertically on mobile

```css
:root {
    --bg: #f5f5f5;
    --card-bg: #ffffff;
    --text: #333333;
    --accent: #4f46e5;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #ef4444;
    --border: #e5e7eb;
}

/* ── Main 3-column layout ── */
.dashboard-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 1.5rem;
    align-items: start;
}

.block {
    background: var(--card-bg);
    border-radius: 8px;
    padding: 1rem;
    border: 1px solid var(--border);
}

.block h2 {
    margin-top: 0;
    font-size: 1.1rem;
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.5rem;
}

/* ── Block 1: Projects ── */
.project-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
}

.project-card {
    padding: 0.75rem;
    background: var(--bg);
    border-radius: 6px;
}

.project-stats {
    display: flex;
    justify-content: space-between;
    font-size: 0.85rem;
    color: #666;
    margin: 0.25rem 0;
}

.progress-bar {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
    overflow: hidden;
}

.progress-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
    transition: width 0.3s;
}

/* ── Block 2: Workflow ── */
.task-list {
    max-height: 60vh;
    overflow-y: auto;
}

.task-group {
    margin-bottom: 0.75rem;
}

.task-group h4 {
    margin: 0 0 0.25rem 0;
    font-size: 0.9rem;
    color: #666;
}

.task-item {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
}

.task-item:hover {
    background: var(--bg);
}

.task-title { flex: 1; min-width: 120px; }

.task-priority {
    font-size: 0.75rem;
    background: #fef3c7;
    color: #92400e;
    padding: 1px 6px;
    border-radius: 3px;
}

.task-deadline {
    font-size: 0.75rem;
    color: #999;
}

.tag {
    background: #e0e7ff;
    color: var(--accent);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 0.75rem;
}

.btn-start-timer {
    background: var(--accent);
    color: white;
    border: none;
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 0.8rem;
    cursor: pointer;
}

.btn-start-timer:hover {
    opacity: 0.9;
}

/* ── Block 3: Timer + Stats + Log sub-grid ── */
.session-subgrid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0.75rem;
}

.sub-col {
    padding: 0.5rem;
}

/* Timer */
.timer-display {
    font-size: 2.5rem;
    font-family: monospace;
    text-align: center;
    padding: 0.5rem 0;
}

#timer-task-select {
    width: 100%;
    padding: 0.4rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    margin-bottom: 0.5rem;
    font-size: 0.85rem;
}

.timer-controls {
    display: flex;
    gap: 0.4rem;
    justify-content: center;
}

.timer-controls button {
    padding: 0.4rem 0.8rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--card-bg);
    cursor: pointer;
    font-size: 0.85rem;
}

.timer-controls button:hover {
    background: var(--bg);
}

#btn-start { background: var(--success); color: white; border-color: var(--success); }
#btn-pause { background: var(--warning); color: white; border-color: var(--warning); }
#btn-reset { background: var(--danger); color: white; border-color: var(--danger); }

/* Stats */
.stat-row {
    display: flex;
    justify-content: space-between;
    padding: 0.3rem 0;
    font-size: 0.85rem;
    border-bottom: 1px solid var(--border);
}

.stat-label { color: #666; }
.stat-value { font-weight: 600; }

/* Log */
.log-feed {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 250px;
    overflow-y: auto;
    font-size: 0.8rem;
}

.log-entry {
    display: flex;
    gap: 0.3rem;
    padding: 0.3rem 0;
    border-bottom: 1px solid var(--border);
}

.log-icon { width: 1.2rem; text-align: center; }
.log-text { flex: 1; }
.log-time { color: #999; white-space: nowrap; }

/* ── Responsive ── */
@media (max-width: 900px) {
    .dashboard-grid {
        grid-template-columns: 1fr;
    }
    .session-subgrid {
        grid-template-columns: 1fr;
    }
}
```

---

## 7. JS Behavior — [`src/static/js/dashboard.js`](src/static/js/dashboard.js)

| Feature | Implementation |
|---------|---------------|
| Timer countdown | `setInterval` every 1s, decrement display, sync with server on start/stop |
| Start timer | POST `/api/timer/start` with `{task_id, duration}`, then begin countdown |
| Pause timer | POST `/api/timer/pause` (optional server-side pause) |
| Stop/Reset | POST `/api/timer/stop`, reset display to default |
| Auto-refresh stats | Poll `/api/stats` every 30s |
| Auto-refresh log | Poll `/api/log` every 30s |
| Start from workflow | Click "Start" button on a task → auto-select in timer + start |

---

## 8. Implementation Order

| Step | Description |
|------|-------------|
| 1 | Create [`src/models/timer.py`](src/models/timer.py) — TimerSession model |
| 2 | Create [`src/models/log.py`](src/models/log.py) — ActivityLog model |
| 3 | Update [`src/models/__init__.py`](src/models/__init__.py) — export new models |
| 4 | Create [`src/templates/base.html`](src/templates/base.html) — base layout |
| 5 | Create [`src/static/css/style.css`](src/static/css/style.css) — styles |
| 6 | Create [`src/routes/dashboard.py`](src/routes/dashboard.py) — dashboard route + API endpoints |
| 7 | Update [`src/app.py`](src/app.py) — register dashboard blueprint |
| 8 | Create [`src/templates/dashboard.html`](src/templates/dashboard.html) — main template |
| 9 | Create [`src/static/js/dashboard.js`](src/static/js/dashboard.js) — interactivity |
| 10 | Add tests for new models, routes, and API endpoints |