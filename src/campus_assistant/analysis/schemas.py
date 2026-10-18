"""What the LLM returns. Every field is required (nullable where optional) so the
schemas work with strict structured outputs on both Claude and llama.cpp."""

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "action_required",  # official: you must do something (form, payment, registration, reply)
    "deadline",         # dates/schedule changes: exams, submissions, timetable
    "notice",           # official info, nothing to do
    "opportunity",      # events, internships, jobs, competitions, scholarships, talks
    "personal",         # a real person writing to you specifically
    "system",           # automated notifications, receipts, OTPs, LMS copies
    "newsletter",       # marketing, digests, promos
    "other",
]
Priority = Literal["urgent", "soon", "whenever", "ignore"]


class Action(BaseModel):
    what: str = Field(description="Imperative, e.g. 'Submit the consent form'")
    due: str | None = Field(description="ISO 8601 date or datetime with +08:00 offset, or null")


class DatedThing(BaseModel):
    what: str
    when: str = Field(description="ISO 8601 date or datetime with +08:00 offset")
    kind: Literal["deadline", "event", "other"]


class Opportunity(BaseModel):
    kind: Literal["event", "internship", "job", "competition", "scholarship", "talk", "volunteering", "programme", "other"]
    title: str
    deadline: str | None = Field(description="Sign-up/application deadline, ISO 8601, or null")
    eligibility: str | None
    cost: str | None
    link: str | None


class Link(BaseModel):
    label: str
    url: str


class MessageTriage(BaseModel):
    category: Category
    priority: Priority
    summary: str = Field(description="One or two sentences: what it is and what (if anything) to do")
    actions: list[Action]
    dates: list[DatedThing]
    opportunity: Opportunity | None
    links: list[Link] = Field(description="Only links needed to act (forms, registration, submission), max 3")


class PlanStep(BaseModel):
    step: str
    target_date: str | None = Field(description="ISO 8601 date to finish this step by, or null")
    est_hours: float | None


class TaskBrief(BaseModel):
    summary: str = Field(description="What is being asked, in 2-4 sentences")
    deliverables: list[str]
    requirements: list[str] = Field(description="Constraints: format, length, tools, grading criteria")
    submission: str | None = Field(description="How/where to submit, or null if not stated")
    weightage: str | None = Field(description="Marks or % of module grade if stated, else null")
    relevant_files: list[str] = Field(description="Titles of the provided files that describe this task")
    plan: list[PlanStep] = Field(description="3-8 steps ending before the due date")
    open_questions: list[str] = Field(description="Things unclear from the material, worth asking the lecturer")
    confidence: Literal["high", "medium", "low"] = Field(
        description="high: brief/spec found; medium: partial info; low: only the title/dates")
