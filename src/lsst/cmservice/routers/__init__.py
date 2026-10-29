"""FastAPI routers"""

tags_metadata = [
    {
        "name": "audit",
        "description": "Operations with audit log entries, which may be generated "
        "by other routes if they define and attach a log entry to the `Response` object.",
    },
    {
        "name": "campaigns",
        "description": "Operations with `campaign`s. A `campaign` is a namespace that "
        "may include `node`, `edge`, and `manifest` objects the define the execution order "
        "and compound configuration for a `campaign`.",
    },
    {
        "name": "edges",
        "description": "Operations with `edge`s within a `campaign` graph.",
    },
    {
        "name": "health",
        "description": "Operations that check or report on the health of the application",
    },
    {
        "name": "internal",
        "description": "Operations that are used by processes that are internal to the application",
    },
    {
        "name": "logs",
        "description": "Operations on activity log resources. Activity logs are "
        "produced by campaign graph operations during state changes and may be "
        "used to trigger notifications.",
    },
    {
        "name": "manifests",
        "description": "Operations on manifests.",
    },
    {
        "name": "nodes",
        "description": "Operations on campaign graph nodes.",
    },
    {
        "name": "notifications",
        "description": "Operations on notification label resources.",
    },
    {
        "name": "rpc",
        "description": "Executive operations not associated with specific resources.",
    },
    {
        "name": "schedules",
        "description": "Operations on schedule resources.",
    },
    {
        "name": "templates",
        "description": "Operations on schedule-related template resources.",
    },
    {
        "name": "v2",
        "description": "Operations associated with the v2 application",
    },
]
