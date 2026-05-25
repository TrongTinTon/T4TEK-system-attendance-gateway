# Fix Expected singleton: res.users() in Attendance Logs

- API routes use auth=none, which may leave request.env.user empty in Odoo 19.
- hr.attendance create/write can access env.user internally and raise `Expected singleton: res.users()`.
- Attendance sync now uses an explicit SUPERUSER_ID environment.
- Authenticated controller API calls also update the request env to SUPERUSER_ID after token validation.
