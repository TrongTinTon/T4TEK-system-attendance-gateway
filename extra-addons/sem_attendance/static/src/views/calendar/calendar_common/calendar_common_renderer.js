/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { getColor } from "../colors";

const { DateTime } = luxon;

export class CalendarCommonRenderer extends Component {
    static template = "sem_attendance.CalendarCommonRenderer";
    static props = {
        model: Object,
        displayName: { type: String, optional: true },
        isWeekendVisible: { type: Boolean, optional: true },
        createRecord: Function,
        editRecord: Function,
        deleteRecord: Function,
        setDate: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            employees: [],
            recordListPopup: null,
        });

        onWillStart(async () => {
            await this.fetchEmployees();
        });
    }

    async fetchEmployees() {
        this.state.employees = await this.orm.searchRead('hr.employee', [], ['id', 'name', 'job_title']);
    }

    getAvatarUrl(employeeId) {
        return `/web/image/hr.employee/${employeeId}/avatar_128`;
    }

    get employees() {
        return this.state.employees;
    }

    get days() {
        const days = [];
        let curr, end;
        if (this.props.model.scale === 'month') {
            curr = this.props.model.date.startOf('month');
            end = this.props.model.date.endOf('month');
        } else if (this.props.model.scale === 'week') {
            curr = this.props.model.rangeStart.startOf('day');
            end = this.props.model.rangeEnd.startOf('day');
        } else {
            curr = this.props.model.date.startOf('day');
            end = this.props.model.date.endOf('day');
        }
        while (curr <= end) {
            days.push(curr);
            curr = curr.plus({ days: 1 });
        }
        return days;
    }

    getShortWeekday(date) {
        const map = {
            1: 'TH 2', 2: 'TH 3', 3: 'TH 4', 4: 'TH 5', 5: 'TH 6', 6: 'TH 7', 7: 'CN'
        };
        return map[date.weekday] || '';
    }

    isToday(date) {
        return date.toISODate() === DateTime.local().toISODate();
    }

    getRecordsForCell(employeeId, date) {
        const dateIso = date.toISODate();
        if (!this.props.model.records) return [];

        return Object.values(this.props.model.records).filter(r => {
            const rEmpId = r.rawRecord.employee_id ? r.rawRecord.employee_id[0] : null;
            if (rEmpId !== employeeId) return false;
            if (!r.start) return false;
            // Chỉ render tại ngày check_in, không render lại ở ngày check_out
            return r.start.toISODate() === dateIso;
        });
    }

    // Trả về số cột mà record span (1 = cùng ngày, 2 = qua đêm)
    getRecordSpan(record) {
        if (!record.end || !record.start) return 1;
        if (record.end.toISODate() === record.start.toISODate()) return 1;
        // Tính số ngày lệch giữa check_out và check_in
        const diff = Math.round(
            DateTime.fromISO(record.end.toISODate())
                .diff(DateTime.fromISO(record.start.toISODate()), 'days').days
        );
        return diff > 0 ? diff + 1 : 1;
    }

    getColor(colorIndex) {
        const color = getColor(colorIndex);
        if (typeof color === 'string') return color;
        const colors = [
            '#e2e2e0', '#f06050', '#f4a460', '#f7cd1f', '#6cc1ed', '#814968', '#eb7e7f', '#2c8397', '#475577', '#d6145f',
            '#30c381', '#9365b8', '#f06050', '#f4a460', '#f7cd1f', '#6cc1ed', '#814968', '#eb7e7f', '#2c8397', '#475577', '#d6145f'
        ];
        return colors[colorIndex % colors.length] || colors[0];
    }

    formatDate(dateIso) {
        return DateTime.fromISO(dateIso).toJSDate().toLocaleDateString();
    }

    formatHours(hours) {
        if (!hours) return '0:00';
        const h = Math.floor(hours);
        const m = Math.round((hours - h) * 60);
        return `${h}:${m.toString().padStart(2, '0')}`;
    }

    // ===== CLICK =====

    onCellClick(employeeId, date) {
        const existingRecords = this.getRecordsForCell(employeeId, date);

        let totalHours = 0;
        let totalDays = 0;
        for (const r of existingRecords) {
            totalHours += (r.rawRecord.worked_hours || 0);
            totalDays += (r.rawRecord.duration_attendance || 0);
        }

        this.state.recordListPopup = {
            employeeId,
            dateIso: date.toISODate(),
            records: existingRecords,
            totalHours,
            totalDays,
        };
    }

    async openCreateForm(employeeId, date) {
        const startLocal = date.set({ hour: 8, minute: 0, second: 0, millisecond: 0 });
        const stopLocal = date.set({ hour: 17, minute: 0, second: 0, millisecond: 0 });
        const startUtc = startLocal.toUTC().toFormat("yyyy-MM-dd HH:mm:ss");
        const stopUtc = stopLocal.toUTC().toFormat("yyyy-MM-dd HH:mm:ss");

        const contextObj = {
            default_employee_id: employeeId,
            default_check_in: startUtc,
            default_check_out: stopUtc,
        };

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Tạo Chấm công",
            res_model: this.props.model.resModel,
            views: [[this.props.model.formViewId || false, "form"]],
            target: "new",
            context: contextObj,
        }, {
            onClose: () => {
                this.props.model.load();
            }
        });
    }

    openRecordEdit(record) {
        this.state.recordListPopup = null;
        this.props.editRecord(record);
    }

    onDeleteRecord(record) {
        this.state.recordListPopup = null;
        this.props.deleteRecord(record);
    }

    closeRecordListPopup() {
        this.state.recordListPopup = null;
    }

    async onAddRecordFromPopup(employeeId, dateIso) {
        this.state.recordListPopup = null;
        const date = DateTime.fromISO(dateIso);
        await this.openCreateForm(employeeId, date);
    }
}
