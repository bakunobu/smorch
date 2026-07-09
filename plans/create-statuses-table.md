# Plan: Create `statuses` Table

## Overview

Create a new `statuses` table to track user role flags (creator, owner, assignee, reviewer, watcher) for projects, subprojects, and tasks.

## Motivation

This table will allow granular permission tracking by linking users to objects and storing which roles they have for each.

## Schema Design

### Table: `statuses`

| Column           | Type     | Constraints                        | Default |
|------------------|----------|------------------------------------|---------|
| `id`             | Integer  | PK, auto-increment                 |         |
| `project_id`     | Integer  | FK → `projects(id)`, nullable      |         |
| `subproject_id`  | Integer  | FK → `subprojects(id)`, nullable   |         |
| `task_id`        | Integer  | FK → `tasks(id)`, nullable         |         |
| `user_id`        | Integer  | FK → `users(id)`, nullable         |         |
| `creator_flag`   | Boolean  | nullable=False                     | `True`  |
| `owner_flag`     | Boolean  | nullable=False                     | `True`  |
| `assignee_flag`  | Boolean  | nullable=False                     | `True`  |
| `reviewer_flag`  | Boolean  | nullable=False                     | `True`  |
| `watcher_flag`   | Boolean  | nullable=False                     | `True`  |

### Default Behavior

When a new record is inserted, all five flag columns will default to `True`. This satisfies the requirement that "the user who created an object has all the flags set to 1."

### Implementation Plan

1.  **Add `Status` model to [`src/models/base.py`](src/models/base.py)**
    - Define new class `Status(db.Model)` with `__tablename__ = "statuses"`
    - Add FK columns: `project_id` → `projects.id`, `subproject_id` → `subprojects.id`, `task_id` → `tasks.id`, `user_id` → `users.id`
    - Add five flag Boolean columns with `default=True`
    - Optionally add a unique constraint on (`project_id`, `subproject_id`, `task_id`, `user_id`) to prevent duplicate role entries
    - Optionally add `__repr__` for readability

2.  **Update [`src/models/__init__.py`](src/models/__init__.py)**
    - Add `Status` to the import line

3.  **Generate Alembic migration**
    - Automatically generate a migration script to create the `statuses` table

4.  **Verify**
    - Run the migration
    - Confirm the table was created
    - Test default values

## Files to Modify

| File                                  | Action             |
|---------------------------------------|--------------------|
| [`src/models/base.py`](src/models/base.py)   | Add `Status` model |
| [`src/models/__init__.py`](src/models/__init__.py) | Add import         |
| `migrations/versions/`                | New migration file |