/** @odoo-module */

import { Component, onWillStart, useState } from '@odoo/owl';
import { useService } from '@web/core/utils/hooks';
import { sprintf } from '@web/core/utils/strings';

export class AttendanceDashboard extends Component {
    static template = 'SEM.AttendanceDashboard';
    static props = {
        "*": true,
    };

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.action = useService('action');

        this.state = useState({
            stats: {
                present: 0,
                absent: 0,
                late: 0,
                on_leave: 0,
            },
            todayAttendance: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            // Get today's attendance count by status
            const domain = [['check_in', '>=', this.getTodayStart()], ['check_in', '<=', this.getTodayEnd()]];

            const attendances = await this.orm.call(
                'hr.attendance',
                'search_read',
                [domain],
                { fields: ['employee_id', 'check_in', 'check_out', 'department_id'] }
            );

            // Count statistics
            const stats = {
                present: attendances.filter(a => a.check_in && a.check_out).length,
                absent: 0,
                late: 0,
                on_leave: 0,
            };

            this.state.stats = stats;
            this.state.todayAttendance = attendances;
            this.state.loading = false;
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.notification.add('Lỗi tải dữ liệu dashboard', { type: 'danger' });
            this.state.loading = false;
        }
    }

    getTodayStart() {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return today.toISOString();
    }

    getTodayEnd() {
        const today = new Date();
        today.setHours(23, 59, 59, 999);
        return today.toISOString();
    }

    viewAttendanceList() {
        this.action.doAction({
            name: 'Chấm công',
            type: 'ir.actions.act_window',
            res_model: 'hr.attendance',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
        });
    }
}

AttendanceDashboard.components = {};
