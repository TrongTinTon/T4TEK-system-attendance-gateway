# -*- coding: utf-8 -*-
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def post_init_hook(env, registry=None):
    """Create Device Users from existing Employees after module installation.

    Installing this module depends on hr/hr_attendance, so hr.employee is
    available.  Existing Employees that already have a unique PIN are mirrored
    to entry.control.user.  Duplicate/blank PINs are deliberately skipped so
    installation never creates invalid duplicate Device Users.
    """
    if not hasattr(env, 'registry'):
        env = api.Environment(env, SUPERUSER_ID, {})

    Employee = env['hr.employee'].sudo()
    DeviceUser = env['entry.control.user'].sudo()
    pin_field = 'pin' if 'pin' in Employee._fields else False
    if not pin_field:
        _logger.warning('[ENTRY CONTROL] hr.employee has no PIN field; skip initial Device User generation.')
        return

    employees = Employee.search([])
    if not employees:
        _logger.info('[ENTRY CONTROL] No Employee data found; skip initial Device User generation.')
        return

    seen = set()
    created = updated = skipped_duplicate = skipped_blank = 0
    for employee in employees:
        pin = str(employee[pin_field] or '').strip()
        if not pin:
            skipped_blank += 1
            continue
        if pin in seen:
            skipped_duplicate += 1
            _logger.warning('[ENTRY CONTROL] Duplicate Employee PIN %s skipped for employee id=%s.', pin, employee.id)
            continue
        seen.add(pin)

        existing = DeviceUser.search([('pin', '=', pin)], limit=1)
        vals = {
            'employee_id': employee.id,
            'pin': pin,
            'name': employee.name or employee.display_name or pin,
            'is_active': bool(getattr(employee, 'active', True)),
            'is_deleted': False,
        }
        if existing:
            if existing.employee_id and existing.employee_id.id != employee.id:
                skipped_duplicate += 1
                _logger.warning('[ENTRY CONTROL] PIN %s already linked to employee id=%s; employee id=%s skipped.', pin, existing.employee_id.id, employee.id)
                continue
            existing.write(vals)
            updated += 1
        else:
            DeviceUser.create(vals)
            created += 1

    _logger.info('[ENTRY CONTROL] Initial Employee -> Device User sync done: employees=%s created=%s updated=%s skipped_blank=%s skipped_duplicate=%s', len(employees), created, updated, skipped_blank, skipped_duplicate)
