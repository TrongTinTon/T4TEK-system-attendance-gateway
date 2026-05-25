/** @odoo-module **/

import { CalendarModel } from "@web/views/calendar/calendar_model";
import { CalendarController } from "@web/views/calendar/calendar_controller";
import { calendarView } from "@web/views/calendar/calendar_view";
import { registry } from "@web/core/registry";

/**
 * Custom CalendarModel cho hr.attendance.calendar
 * Override loadFilters để luôn hiển thị tất cả nhân viên trong sidebar
 */
export class AttendanceCalendarModel extends CalendarModel {

    async updateData(data) {
        await super.updateData(data);
        // After data loaded, inject all employees into the filter section
        await this._loadAllEmployeeFilters();
    }

    async _loadAllEmployeeFilters() {
        const colorFieldName = this.meta.colorFieldName;
        if (colorFieldName !== "employee_id") return;

        // Fetch all active employees
        const employees = await this.orm.searchRead(
            "hr.employee",
            [["active", "=", true]],
            ["id", "name", "image_128"],
            { order: "name asc" }
        );

        // Get the filter section for employee_id
        const filterSection = this.filterSections[colorFieldName];
        if (!filterSection) return;

        // Add each employee as an active filter if not already present
        for (const emp of employees) {
            const filterKey = String(emp.id);
            if (!filterSection.filters[filterKey]) {
                filterSection.filters[filterKey] = {
                    type: "dynamic",
                    value: emp.id,
                    label: emp.name,
                    active: true,
                    avatarModel: "hr.employee",
                    hasAvatar: true,
                    colorIndex: emp.id,
                };
            }
        }
    }
}

export class AttendanceCalendarController extends CalendarController { }

AttendanceCalendarController.components = {
    ...CalendarController.components,
};

export const attendanceCalendarView = {
    ...calendarView,
    Model: AttendanceCalendarModel,
    Controller: AttendanceCalendarController,
};

registry.category("views").add("attendance_calendar", attendanceCalendarView);
