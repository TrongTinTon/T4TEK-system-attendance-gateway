# Employees API pagination

Updated `/api/entry_control/v1/employees` so the Controller does not receive all employees in one response.

## Request

```json
{
  "controller_uid": "CTRL-LOCAL-01",
  "last_sync_at": "2026-05-25 10:00:00",
  "page": 1,
  "page_size": 50,
  "sync_cursor_to": "2026-05-25 11:00:00"
}
```

Supported aliases:
- `page_size`, `pageSize`, or `limit`
- `page` or `pageIndex`
- `offset`
- `sync_cursor_to`, `syncCursorTo`, `snapshot_sync_at`, or `snapshotSyncAt`

`page_size` is capped at 100.

## Response

```json
{
  "ok": true,
  "count": 50,
  "total_count": 1000,
  "page": 1,
  "page_size": 50,
  "offset": 0,
  "has_more": true,
  "next_page": 2,
  "next_offset": 50,
  "sync_cursor_to": "2026-05-25 11:00:00",
  "employees": []
}
```

`sync_cursor_to` creates a stable snapshot for all pages in the same pull cycle. The Controller sends the same cursor back on following pages and only updates its local `last_sync_at` after all pages complete.
