# Employee Sync Status: show Employee Code

Changed Employee Sync Status UI to show `Employee Code` (`hr.employee.code`) instead of `Employee Name`.

- Added stored related field `employee_code` on `entry.control.employee.sync`.
- Replaced the displayed `employee_name` column with `employee_code` in Employee Sync Status list/search.
- Replaced the embedded Employees Synced column on Controller form with `employee_code`.
- Kept `employee_name` in the model for backward compatibility/audit data, but it is no longer shown by default.
