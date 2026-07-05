from datetime import datetime, timezone

from src.database import db

tag_task_association = db.Table(
    "tag_task_association",
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
    db.Column("task_id", db.Integer, db.ForeignKey("tasks.id"), primary_key=True),
)


class Project(db.Model):
    """Top-level project."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    subprojects = db.relationship(
        "Subproject", backref="project", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Project {self.id}: {self.title}>"


class Subproject(db.Model):
    """Mid-level subproject under a project."""

    __tablename__ = "subprojects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tasks = db.relationship(
        "Task", backref="subproject", lazy="dynamic", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Subproject {self.id}: {self.title}>"


class Task(db.Model):
    """Bottom-level task under a subproject."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    completed = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=0)
    complexity = db.Column(db.Integer, default=0)
    deadline = db.Column(db.DateTime, nullable=True)
    subproject_id = db.Column(
        db.Integer, db.ForeignKey("subprojects.id"), nullable=False
    )
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tags = db.relationship("Tag", secondary=tag_task_association, lazy="subquery")

    def __repr__(self):
        return f"<Task {self.id}: {self.title}>"


class Tag(db.Model):
    """Tags for tasks."""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Tag {self.id}: {self.name}>"
