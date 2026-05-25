/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { HrOrgChart } from "@hr_org_chart/fields/hr_org_chart";
import { onWillUpdateProps, useEffect } from "@odoo/owl";

import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

patch(HrOrgChart.prototype, {
    setup() {
        super.setup(...arguments);

        useEffect(
            (versionField) => {
                // versionField = id thay đổi
                if (this.orm && this.state && this.state.employee_id) {
                    this.fetchEmployeeData(this.state.employee_id, this.lastParent, true);
                }
            },
            () => {
                let v = false;
                if (this.env && this.env.model && this.env.model.root && this.env.model.root.data) {
                    v = this.env.model.root.data.version_id;
                }
                return [Array.isArray(v) ? v[0] : v];
            }
        );
    },

    async fetchEmployeeData(employeeId, newParentId = null, force = false) {
        if (!employeeId) {
            this.managers = [];
            this.children = [];
            if (this.view_employee_id) {
                this.render(true);
            }
            this.view_employee_id = null;
        } else if (employeeId !== this.view_employee_id || force) {
            this.view_employee_id = employeeId;
            
            // Ép version_id vào context trước khi đâm xuống hệ thống RPC
            let context = Object.assign({}, user.context || {});
            
            let versionField = null;
            if (this.env && this.env.model && this.env.model.root && this.env.model.root.data) {
                versionField = this.env.model.root.data.version_id;
            } else if (this.props && this.props.record && this.props.record.data) {
                versionField = this.props.record.data.version_id;
            }

            if (versionField) {
                context.version_id = Array.isArray(versionField) ? versionField[0] : versionField;
            }

            context.max_level = this.max_level;

            let orgData = await rpc(
                '/hr/get_org_chart',
                {
                    employee_id: employeeId,
                    new_parent_id: newParentId,
                    context: context
                }
            );
            
            if (Object.keys(orgData).length === 0) {
                orgData = {
                    managers: [],
                    children: [],
                }
            }
            this.managers = orgData.managers;
            this.children = orgData.children;
            this.managers_more = orgData.managers_more;
            this.self = orgData.self;
            this.render(true);
        }
    }
});
