/** @odoo-module */

import { registry } from '@web/core/registry';
import { AttendanceDashboard } from './attendance_dashboard';

registry.category('actions').add('attendance_dashboard', AttendanceDashboard);
