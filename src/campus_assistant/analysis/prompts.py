"""Prompts. Bump PROMPT_VERSION when a prompt or schema changes meaningfully:
stored results with an older version are recomputed."""

import os

PROMPT_VERSION = {"triage": 4, "brief": 1}

USER_CONTEXT = os.environ.get(
    "CAMPUS_USER_CONTEXT",
    "a full-time student at Singapore Polytechnic (School of Computing, AI / data science modules)",
)

TRIAGE_SYSTEM = f"""You triage messages for {USER_CONTEXT}. Messages are emails or course announcements.

Choose exactly one category:
- action_required: the student must do something (fill a form, pay, register, reply, attend something mandatory)
- deadline: mainly about dates or schedule changes (exams, submissions, timetable, venue/time changes)
- notice: official information with nothing to do
- opportunity: optional events, internships, jobs, competitions, scholarships, talks, programmes worth considering
- personal: a real person writing to the student specifically (not a mass mailing)
- system: machine-generated notifications only (receipts, one-time codes, LMS/Teams activity copies).
  Announcements written by staff (IT maintenance, service disruptions) are notice, not system.
- newsletter: marketing, product mailings, social-network feeds/digests (e.g. "X recently posted"), promotions
- other: none of the above

Priority:
- urgent: needs attention within ~2 days or has consequences if missed
- soon: needs attention within ~2 weeks
- whenever: worth reading, no time pressure
- ignore: safe to skip

Rules:
- Resolve relative dates ("this Friday", "next week") against the message's sent date. Write dates as ISO 8601 with +08:00 (Singapore). Never invent a year: use the sent date's year unless the text says otherwise.
- Only include dates and actions that the text actually states.
- An action's due is the deadline stated in the text, or null. Never use today's date as a due date, and
  don't turn an event's date into a sign-up deadline unless the text says so.
- Job-alert digests (several listings, no deadline): opportunity with priority whenever; describe the roles
  briefly; no actions.
- opportunity is null unless category is opportunity.
- Keep the summary factual and short; no greetings or filler."""


# Classifier questions. Keys are the stored values; the model only ever sees neutral
# letters next to these definitions (semantically loaded option names bias it).
CATEGORY_QUESTION = "Which category best describes this message for the student?"
CATEGORY_OPTIONS = {
    "action_required": "Official: the student must do something (form, payment, registration, reply, mandatory attendance)",
    "deadline": "Mainly about dates or schedule changes (exams, submissions, timetable, venue/time changes)",
    "notice": "Official information from staff with nothing to do",
    "opportunity": "Optional event, internship, job, competition, scholarship, talk or programme to consider",
    "personal": "A real person writing to the student specifically, not a mass mailing",
    "system": "Machine-generated notification: receipt, one-time code, LMS/Teams activity copy",
    "newsletter": "Marketing, product mailing, social-network feed or digest, promotion",
    "other": "None of the above",
}
PRIORITY_QUESTION = "How soon does the student need to pay attention to this message?"
PRIORITY_OPTIONS = {
    "urgent": "Within about 2 days, or there are consequences if missed",
    "soon": "Within about 2 weeks",
    "whenever": "Worth reading, no time pressure",
    "ignore": "Safe to skip",
}


def triage_user(item: dict, body: str, today: str) -> str:
    d = item["data"]
    kind = item["kind"]
    header = [f"Today: {today}", f"Type: {kind}"]
    if kind == "email":
        header += [f"From: {d.get('from') or '?'}", f"To: {', '.join(d.get('to') or [])[:300]}"]
        if d.get("cc"):
            header.append(f"Cc: {', '.join(d['cc'])[:200]}")
        if d.get("bulk"):
            header.append("Mailing-list/bulk headers: yes")
        if d.get("attachments"):
            header.append("Attachments: " + ", ".join(a.get("name") or "?" for a in d["attachments"])[:300])
    else:
        header.append(f"Course: {item.get('course_name')}")
    header += [f"Sent: {item.get('occurred_at') or '?'}", f"Subject: {item['title']}", "", body]
    return "\n".join(header)


BRIEF_SYSTEM = f"""You help {USER_CONTEXT} understand and plan coursework.

You get one task from the learning management system (assignment or quiz) with its dates, plus text
extracted from course files that may describe it (briefs, specs, rubrics, lecture notes). Some files may
be unrelated: use only those that are clearly about this task and list them in relevant_files.

Write a practical brief:
- summary/deliverables/requirements must come from the material. If the material doesn't describe the
  task, say so in the summary, keep lists short, and set confidence to low. Don't invent requirements.
- plan: 3-8 concrete steps, each with a target date (ISO 8601, +08:00) spaced between today and the due
  date, leaving buffer before the deadline. If the deadline has passed or is unknown, use null dates.
- open_questions: genuine ambiguities only."""


def brief_user(item: dict, files: list[tuple[str, str]], today: str) -> str:
    d = item["data"]
    lines = [
        f"Today: {today}",
        f"Course: {item.get('course_name')}",
        f"Task type: {item['kind']}",
        f"Title: {item['title']}",
        f"Due: {item.get('due_at') or 'not set'}",
        f"Available from: {item.get('starts_at') or '-'}  until: {item.get('ends_at') or '-'}",
    ]
    if d.get("score_out_of"):
        lines.append(f"Marked out of: {d['score_out_of']}")
    if d.get("time_limit_min"):
        lines.append(f"Time limit: {d['time_limit_min']} min; attempts: {d.get('attempts') or 'unlimited'}")
    if "submitted" in d:
        lines.append(f"Already submitted: {'yes' if d['submitted'] else 'no'}")
    lines += ["", "Instructions on the LMS:", item.get("body") or "(none)", ""]
    if files:
        for title, text in files:
            lines += [f'<file title="{title}">', text, "</file>", ""]
    else:
        lines.append("(No related course files found.)")
    return "\n".join(lines)
