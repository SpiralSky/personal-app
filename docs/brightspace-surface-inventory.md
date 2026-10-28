# Brightspace surface inventory (student context)

> **Evidence, not requirements.** This document inventories what a Brightspace
> student can see and which documented APIs can retrieve it. It supports
> [F-019](../specs/features/F-019-brightspace-crawler.md) and must not be read as
> a scope decision. Scope, priority and acceptance criteria belong in the
> feature spec.
>
> Checked against the D2L [Developer Platform reference](https://docs.valence.desire2learn.com/reference.html)
> (October 2026) and public student-facing guides on 2026-10-25. “Documented”
> means a route exists in the Valence reference; it does **not** guarantee that a
> student role, a particular institution, or a browser-session call can use it.

## 1. Access model

There are two different ways to reach the JSON API:

1. **Registered OAuth2 application** — the documented model. The application is
   registered in Brightspace, receives scopes, and acts in a user context.
   Registration usually requires institution administrator approval.
2. **Existing browser session** — what the current `campus-assistant` code does:
   a persistent Playwright profile signs in through institutional SSO/MFA, then
   `APIRequestContext` calls the same `/d2l/api/...` paths with the session
   cookies. This avoids app registration but is an undocumented use of the API
   and can break when D2L changes session handling.

Relevant facts:

- Version discovery: `GET /d2l/api/versions/` returns the latest `lp` and `le`
  product versions. The current client uses this before calling versioned routes.
- Identity: `GET /d2l/api/lp/{lp}/users/whoami` returns the user (the current
  client uses it as the session check).
- Student courses: `GET /d2l/api/lp/{lp}/enrollments/myenrollments/` with
  `orgUnitTypeId=3` (course offerings), paginated with a bookmark.
- Errors are meaningful: `403` usually means the role cannot see that tool;
  `404` can mean the tool is not enabled in the course. Neither means “the
  course is empty.” A crawler must not turn either into a deletion.
- Rate limiting returns `429`; the current client already retries `429`, `502`,
  `503`, `504` with exponential backoff.
- Brightspace timestamps are `UTCDateTime` strings (UTC). A few fields are
  `ISODate` only. Display time zone is a presentation concern.

## 2. Surface matrix

The “API” column uses `{lp}` / `{le}` for the discovered versions and
`{ou}` for the course offering ID.

| Surface | What the student sees | Documented API | What can be retrieved | Limits / notes |
|---|---|---|---|---|
| **Session and identity** | Signed-in user, profile menu | `GET /d2l/api/lp/{lp}/users/whoami`; `GET /d2l/api/lp/{lp}/profile/myProfile`; `GET /d2l/api/lp/{lp}/profile/myProfile/image` | User id, unique name, display name, profile image | No password handling; browser session or OAuth only. |
| **Courses / enrollments** | Course selector, pinned courses, course home | `GET /d2l/api/lp/{lp}/enrollments/myenrollments/`; `GET /d2l/api/lp/{lp}/enrollments/myenrollments/{ou}`; `GET /d2l/api/lp/{lp}/courses/{ou}`; `GET /d2l/api/lp/{lp}/courses/{ou}/image` | Course id, name, code, start/end dates, access, pin state, image | Course role and access flags can hide a course. Some course metadata may be restricted. |
| **Course home / Work To Do** | “Work To Do”, upcoming items, course updates | `GET /d2l/api/le/{le}/content/myItems/`; `.../content/myItems/due/`; `.../content/myItems/completions/`; `GET /d2l/api/le/{le}/updates/myUpdates/` | Scheduled content items with start/end/due dates, completion type, completion date, activity type; update counts | Cross-course routes require an explicit `orgUnitIdsCSV` (≤100). These are derived views; they do not replace the underlying tools. |
| **Announcements (News)** | Course announcements widget and announcement pages | `GET /d2l/api/le/{le}/{ou}/news/`; `GET /d2l/api/le/{le}/{ou}/news/{newsItemId}`; `GET /d2l/api/le/{le}/{ou}/news/{newsItemId}/attachments/{fileId}`; cross-course `GET /d2l/api/le/{le}/news/user/{userId}/` | Title, rich-text body, start/end dates, hidden/published flags, pinned state, attachments | Hidden/unpublished items should be filtered. Cross-course route is subject to user privacy controls and is not the same as reading each course’s news. |
| **Content / course files** | Modules, topics, files, links, HTML pages, LTI/SCORM activities | `GET /d2l/api/le/{le}/{ou}/content/toc`; `GET .../content/topics/{topicId}`; `GET .../content/topics/{topicId}/file`; `GET .../content/userprogress/`; `GET .../content/completions/`; `GET .../content/bookmarks` | Module tree, topic metadata, type (`File`, `Link`, `LTI`, `SCORM`, …), dates, visibility, completion type, file bytes, user progress | `topics/{id}/file` works for file topics and HTML pages. Embedded images and relative links inside HTML are not a separate API; they must be fetched from the same host or rewritten. LTI/SCORM runtime content is not the file endpoint. |
| **Assignments (Dropbox)** | Assignment list, instructions, due dates, submissions, feedback | `GET /d2l/api/le/{le}/{ou}/dropbox/folders/`; `GET .../folders/{folderId}/submissions/mysubmissions/`; `GET .../folders/{folderId}/feedback/{entityType}/{entityId}`; `GET .../folders/{folderId}/attachments/{fileId}`; cross-course `GET /d2l/api/le/{le}/dropbox/orgUnits/feedback/` | Folder name, instructions, due/start/end dates, attachments, score denominator, group flag, submission status/dates, feedback, feedback attachments, rubric associations | `mySubmissions` is the student view. Feedback may be released later than the submission. Group submissions need separate handling. |
| **Quizzes** | Quiz list, availability window, due date, time limit, attempts, feedback | `GET /d2l/api/le/{le}/{ou}/quizzes/`; `GET .../quizzes/{quizId}`; `GET .../quizzes/{quizId}/attempts/`; `GET .../quizzes/{quizId}/attempts/{attemptId}`; `GET .../quizzes/{quizId}/questions/` | Name, active flag, start/end/due dates, attempts allowed, time limit, instructions/description, grade item, attempt score/completion/feedback | Questions are likely permission-restricted and may only be available after an attempt. The quiz list is metadata; it is not the quiz-taking experience. Special access can change dates per user. |
| **Discussions** | Forums, topics, threads, posts, subscriptions, read state | `GET /d2l/api/le/{le}/{ou}/discussions/forums/`; `GET .../forums/{forumId}/topics/`; `GET .../forums/{forumId}/topics/{topicId}/posts/`; `GET .../posts/{postId}/ReadStatus`; `GET .../posts/{postId}/attachments/{fileId}` | Forum/topic metadata, post subject/message, author display name, dates, attachments, read status, ratings/votes | Subscription alerts are surfaced through the alert feed; there is no obvious public “my subscriptions” route in the reference. Attachment download uses the post attachment route. |
| **Grades** | Grades list, released grades, feedback | `GET /d2l/api/le/{le}/{ou}/grades/values/myGradeValues/`; `GET .../grades/final/values/myGradeValue`; `GET .../grades/`; `GET .../grades/{gradeObjectId}/values/myGradeValue`; `GET /d2l/api/le/{le}/grades/final/values/myGradeValues/` | Grade object name, displayed grade, numerator/denominator, weighted values, comments, released date | Only released/visible values should be shown. Grade item definitions may be accessible even when values are not. |
| **Calendar** | Course and personal events, due-date events, occurrences | `GET /d2l/api/le/{le}/{ou}/calendar/events/myEvents/?startDateTime=&endDateTime=`; cross-course `GET /d2l/api/le/{le}/calendar/events/myEvents/`; `GET .../events/myEventsWithOccurrences/`; `GET .../events/myEvents/itemCounts/` | Event id, title, description, start/end, all-day flag, location, associated entity, view URL | Windowed results. Absence outside the window is not deletion. Events associated with an assignment/quiz duplicate that item’s date; standalone events are the ones that add a deadline. |
| **Notification bell / alerts** | Minibar icons for Message alerts, Subscription alerts, Update alerts | `GET /d2l/api/lp/{lp}/alerts/user/{userId}?category=`; course update counts via `GET /d2l/api/le/{le}/{ou}/updates/myUpdates` and `GET /d2l/api/le/{le}/updates/myUpdates/?orgUnitIdsCSV=...` | Alert id, course id, category (`0` subscription, `1` update, `2` message), title, message, message URL, icon URL, alert date/time, subject type/id; update counts for unread discussions, unapproved discussions, unread assignment feedback, unattempted quizzes, ungraded quizzes, unread assignment submissions | This is the best documented match for the bell, but the exact bell list may include UI-only items. Verify against a live session. Message **bodies** are not exposed by a documented Valence route; the alert gives a title/message and a URL. |
| **Notification settings** | Personal notification preferences | `GET /d2l/api/lp/{lp}/notifications/instant/users/{userId}/settings`; `GET /d2l/api/lp/{lp}/notifications/instant/carriers/`; carrier subscriptions | Carriers and per-message-type settings | Settings, not the notification inbox. Useful if the owner wants “do not disturb” or export preferences. |
| **Checklists** | Course checklist and due dates | `GET /d2l/api/le/{le}/{ou}/checklists/`; `GET .../checklists/{checklistId}/categories/`; `GET .../checklists/{checklistId}/items/` | Checklist/category/item names, descriptions, sort order, item due dates | Documented read models do **not** include per-user completion state. The web UI may track completion outside this API; do not assume it is available. |
| **Surveys** | Survey list, availability, attempts | `GET /d2l/api/le/{le}/{ou}/surveys/`; `GET .../surveys/{surveyId}`; `GET .../surveys/{surveyId}/attempts/`; `GET .../surveys/{surveyId}/questions/` | Name, active flag, start/end dates, anonymous flag, attempts allowed, description, attempt started/completed | Survey questions/responses may be restricted. Anonymous surveys intentionally hide user identity. |
| **Self-assessments** | Self-assessment activities inside Content | No dedicated resource page in the Valence reference; the activity is represented as Content activity type `11` (`SelfAssessment`) | Content metadata and link/activity id | Treat as content metadata only unless a live session shows a usable endpoint. |
| **Awards / badges** | Available awards, earned badges, credits | `GET /d2l/api/bas/{version}/associations/availableToEarn/`; `GET /d2l/api/bas/{version}/issued/users/{userId}/`; `GET /d2l/api/bas/{version}/creditSummary`; `GET /d2l/api/bas/{version}/awards/{awardId}` | Award title/description/criteria, issued date, expiry, evidence, credit, certificate/image data | Separate `bas` API version. Student permission is not guaranteed. Certificate/image payloads may be binary. |
| **Groups** | Group membership, group lockers | `GET /d2l/api/lp/{lp}/{ou}/groupcategories/`; `GET .../groupcategories/{id}/groups/`; `GET .../groupcategories/{id}/groups/{groupId}`; `GET .../groups/selfEnrollmentAvailable` | Group categories, groups, membership, self-enrollment availability | Student access depends on course settings. Some group routes are instructor-oriented; verify with a student session. |
| **Locker** | Personal and group files | `GET /d2l/api/le/{le}/locker/myLocker/{path}`; `GET /d2l/api/le/{le}/{ou}/locker/group/{groupId}/{path}` | File listing and bytes | Optional personal storage; not course content. Large/recursive listings need care. |
| **ePortfolio** | Portfolio activity, objects, presentations | `GET /d2l/api/eP/{version}/activity/my/`; `GET /d2l/api/eP/{version}/newsfeed/`; object/collection routes | Activity, objects, presentations, comments | Separate `eP` API. Probably out of scope for a course crawler. |
| **Class progress / Progress** | Progress summary, completion, grades | No single “class progress” endpoint for students; derive from `content/userprogress/`, `content/completions/`, and grade values | Completion counts, visited/read state, grades | This is a derived surface. Do not promise an exact copy of the Progress UI. |
| **Course image / profile image** | Course banner, avatar | `GET /d2l/api/lp/{lp}/courses/{ou}/image`; `GET /d2l/api/lp/{lp}/profile/myProfile/image` | Image bytes | Optional; useful for a UI, not for study data. |
| **Rubrics** | Rubric attached to an assignment/discussion | `GET /d2l/api/le/{le}/{ou}/rubrics/`; `GET .../rubrics/associations/`; `GET .../rubrics/associations/activity/{activityType}/{objectId}` | Rubric definitions and activity associations | Student access is not guaranteed. Feedback often includes the rubric result; the definition may be instructor-only. |
| **Accommodations** | Extra time or other quiz/assignment accommodations | `GET /d2l/api/le/{le}/{ou}/accommodations/myaccommodations` | The calling student’s accommodations | Student-specific. Overlaps with quiz/assignment special access; do not expose to other users. |
| **Competencies / learning outcomes** | Competency and learning-outcome structure, alignments | `GET /d2l/api/le/{le}/{ou}/competencies/structure`; `GET .../lo/outcomeSets/`; `GET .../lo/alignments/` | Structure, outcome sets, alignments | Permission-dependent and often program-level rather than course content. Verify with a student session. |
| **Other institution-enabled tools** | Attendance, Chat, FAQ, Glossary, Scheduler, Virtual Classroom, media/reading-list tools | No documented student API for most; some are LTI or HTML-only | Case-by-case | Enabled per institution. Count them only after checking the specific host; do not promise generic support. |
| **Email / instant messages** | Minibar message alerts, Brightspace Email tool | No documented Valence route for message bodies; `alerts` category `2` can surface message alerts | Alert title/message/URL only | Do not promise full message sync. If the owner needs Outlook mail, the existing mail ingestion is a different feature. |
| **LTI / third-party tools** | Panopto, Zoom, Teams, Turnitin, publisher platforms, external tools | Content topic metadata (`ActivityType` LTI/`LTIAdvantage`); no generic content API | Launch URL, title, tool id, activity id | The actual content lives in another system with its own auth. Crawling it is a separate integration and may violate terms. |
| **SCORM / H5P / package content** | SCORM activities, H5P embeds | Content topic metadata; package files may be downloadable in some cases | Metadata, possibly package files | Runtime state and internal navigation are not exposed by the Valence content API. |
| **Release conditions / adaptive release** | Items appear only when conditions are met | Returned state is already filtered for the calling user; no “all hidden items” view | Only what the user can access | A crawler cannot enumerate content the student cannot see. Absence is not deletion. |
| **Admin / instructor data** | Classlist, all submissions, gradebook setup, intelligent agents, Data Hub | Various admin routes | — | Out of scope for a student crawler. |

## 3. The notification bell in detail

Brightspace’s minibar has three alert icons:

- **Message alerts** — new Brightspace email or instant messages.
- **Subscription alerts** — new posts in subscribed discussions.
- **Update alerts** — new/updated announcements, upcoming due/end dates, new or
  updated grades, and similar course changes.

Sources: [Minnesota State minibar guide](https://servicedesk.minnstate.edu/TDClient/30/Portal/KB/Article/93/Navigate-D2L-Brightspace-using-Homepages-Navbars-and-Minibar?SIDs=87),
[University of Suffolk notifications guide](https://libguides.uos.ac.uk/brightspace-student/notifications),
[University at Buffalo homepage guide](https://www.buffalo.edu/lms/guides-students/brightspacebasics/navigating-brightspace-homepage.html).

The documented API that most closely matches this is:

```text
GET /d2l/api/lp/{lp}/alerts/user/{userId}?category={0|1|2}
```

`Alert` fields: `Id`, `OrgUnitId`, `Category`, `Title`, `Message`,
`MessageURL`, `IconURL`, `AlertDateTime`, `FeedMessageSubjectType`,
`FeedMessageSubjectId`. Categories are `0` Subscription, `1` Update,
`2` Message. Scope listed in the reference: `alerts:alerts:read`.

Course update counts are a different view:

```text
GET /d2l/api/le/{le}/{ou}/updates/myUpdates
GET /d2l/api/le/{le}/updates/myUpdates/?orgUnitIdsCSV=...
```

`OrgUnitUpdates` fields: `UnreadDiscussions`, `UnapprovedDiscussions`,
`UnreadAssignmentFeedback`, `UnattemptedQuizzes`, `UngradedQuizzes`,
`UnreadAssignmentSubmissions`. Update type values are `1` UnreadAssignmentFeedback,
`2` UnapprovedDiscussions, `3` UnattemptedQuizzes, `4` UngradedQuizzes,
`5` UnreadAssignmentSubmissions, `6` UnreadDiscussions.

**Recommendation for the spec:** define the notification-bell contract as
“alerts feed + update counts”, not as “scrape the bell DOM”. Verify the alert
route against a real student session before accepting it; if it is unavailable,
fall back to update counts plus announcements/unread discussion counts and say
so explicitly.

## 4. What is not reachable through the documented API

These are the boundaries that make “fetch everything” impossible as a literal
requirement:

- **LTI and third-party tools** — content is in another product with its own
  authentication and terms.
- **SCORM/H5P runtime** — package metadata may be visible, but runtime state and
  navigation are not a Valence resource.
- **Email / instant-message bodies** — alerts expose a title, message and URL,
  not the mailbox.
- **Self-assessment runtime and some interactive activities** — no dedicated
  documented resource.
- **Quiz-taking, assignment submission, discussion posting** — these are write
  actions, not reads. A crawler should not perform them.
- **Instructor/admin data** — classlist, all submissions, gradebook setup,
  intelligent agents, Data Hub/Data Sets.
- **Content the student is not permitted to see** — release conditions and
  special access mean the API returns only the user-visible subset.

## 5. Data and storage implications

- **Stable identity** varies by surface: course offerings have `OrgUnitId`;
  content has `TopicId`; assignments have folder ids; quizzes have `QuizId`;
  posts have `PostId`; alerts have `Id`. A crawler needs a composite key such as
  `(host, surface, course_id, external_id)`.
- **Raw payloads are large and nested.** Store the raw JSON for fidelity, but do
  not hash every field for change detection. Hash the user-visible fields and
  exclude volatile counters and URLs.
- **Attachments and images** come from different endpoints (news attachments,
  dropbox attachments/feedback, discussion post attachments, content topic file).
  A file table should record the origin endpoint, filename, content type, size,
  source modification time and SHA-256.
- **Embedded images** inside rich text are not separate API objects. Fetching
  them means following same-host URLs from the HTML and rewriting or mapping
  them.
- **Windowed endpoints** (calendar, due items, alerts, update counts) must never
  mark items as removed just because they fell outside the window.
- **Partial failures** are normal (a tool disabled for one course, a 403 on a
  quiz question route). The cache should preserve the last good value and mark
  the surface stale.
- **Offline use** argues for a durable local cache. **History** argues for
  snapshots. Those are different retention decisions and should not be conflated.

## 6. Sources

Valence reference pages:

- [API reference home](https://docs.valence.desire2learn.com/reference.html)
- [HTTP routing table](https://docs.valence.desire2learn.com/http-routingtable.html)
- [Authentication scopes table](https://docs.valence.desire2learn.com/http-scopestable.html)
- [Course content](https://docs.valence.desire2learn.com/res/content.html)
- [Quizzes](https://docs.valence.desire2learn.com/res/quiz.html)
- [Discussions](https://docs.valence.desire2learn.com/res/discuss.html)
- [Announcements / News](https://docs.valence.desire2learn.com/res/news.html)
- [Calendar](https://docs.valence.desire2learn.com/res/calendar.html)
- [Assignments / Dropbox](https://docs.valence.desire2learn.com/res/dropbox.html)
- [Grades](https://docs.valence.desire2learn.com/res/grade.html)
- [Course updates](https://docs.valence.desire2learn.com/res/updates.html)
- [Users, alerts and notifications](https://docs.valence.desire2learn.com/res/user.html)
- [Checklists](https://docs.valence.desire2learn.com/res/checklist.html)
- [Surveys](https://docs.valence.desire2learn.com/res/survey.html)
- [Awards](https://docs.valence.desire2learn.com/res/awards.html)
- [Groups](https://docs.valence.desire2learn.com/res/groups.html)
- [Locker](https://docs.valence.desire2learn.com/res/locker.html)
- [ePortfolio](https://docs.valence.desire2learn.com/res/eport.html)
- [Accommodations](https://docs.valence.desire2learn.com/res/accommodations.html)
- [Competencies](https://docs.valence.desire2learn.com/res/competency.html)
- [Learning outcomes](https://docs.valence.desire2learn.com/res/outcomes.html)
- [Enrollments](https://docs.valence.desire2learn.com/res/enroll.html)
- [Courses](https://docs.valence.desire2learn.com/res/course.html)
- [Org units](https://docs.valence.desire2learn.com/res/orgunit.html)

Student-facing navigation and notification guides:

- [Taylor University — overview of Brightspace tools](https://service.taylor.edu/TDClient/141/Portal/KB/Article/846/Basic-Brightspace-Navigation)
- [Concordia St. Paul — navigating a course as a student](https://helpcenter.csp.edu/kb/article/20-navigating-a-course-as-a-student/)
- [Minnesota State — homepages, navbars and minibar alerts](https://servicedesk.minnstate.edu/TDClient/30/Portal/KB/Article/93/Navigate-D2L-Brightspace-using-Homepages-Navbars-and-Minibar?SIDs=87)
- [University of Suffolk — notifications](https://libguides.uos.ac.uk/brightspace-student/notifications)
- [University at Buffalo — homepage and minibar icons](https://www.buffalo.edu/lms/guides-students/brightspacebasics/navigating-brightspace-homepage.html)
