/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { InternalResumeLineComponent } from "@hr_skills/components/internal_resume_lines/internal_resume_one2many";
import { onWillUpdateProps, useEffect } from "@odoo/owl";

patch(InternalResumeLineComponent.prototype, {
    setup() {
        super.setup(...arguments);
        
        // Giải pháp an toàn: Dùng OWL useEffect để theo dõi sự thay đổi của version_id
        // Việc này không can thiệp vào Odoo FormController hay fieldDependencies, nên tuyệt đối KHÔNG làm lỗi tính năng Save!
        useEffect(
            (versionField) => {
                // Chỉ chạy nếu đã có resId (nhân viên đã được tạo) và ORM khả dụng
                if (this.orm && this.props && this.props.record && this.props.record.resId) {
                    const context = Object.assign({}, this.props.record.context || {});
                    if (versionField) {
                        context.version_id = Array.isArray(versionField) ? versionField[0] : versionField;
                    }

                    this.orm.call(
                        "hr.employee",
                        "get_internal_resume_lines",
                        [this.props.record.resId, this.props.record.resModel],
                        { context: context }
                    ).then(res => {
                        this.internalResumeLines = res;
                        if (this.env && this.env.isRendered !== false) {
                            this.render(); // Ép Widget vẽ lại dữ liệu mới
                        }
                    });
                }
            },
            () => {
                let v = false;
                if (this.env && this.env.model && this.env.model.root && this.env.model.root.data) {
                    v = this.env.model.root.data.version_id;
                }
                // Convert array to string/id for primitive comparison so useEffect spots the difference
                return [Array.isArray(v) ? v[0] : v];
            }
        );

        onWillUpdateProps(async (nextProps) => {
            const context = Object.assign({}, nextProps.record.context || {});
            
            let versionField = null;
            if (this.env && this.env.model && this.env.model.root && this.env.model.root.data) {
                versionField = this.env.model.root.data.version_id;
            } else {
                versionField = nextProps.record.data.version_id;
            }

            if (versionField) {
                context.version_id = Array.isArray(versionField) ? versionField[0] : versionField;
            }

            this.internalResumeLines = await this.orm.call(
                "hr.employee",
                "get_internal_resume_lines",
                [nextProps.record.resId, nextProps.record.resModel],
                { context: context }
            );
        });
    },

    async getInternalResumeLines(resId, resModel) {
        const context = Object.assign({}, this.props.record.context || {});
        
        let versionField = null;
        if (this.env && this.env.model && this.env.model.root && this.env.model.root.data) {
            versionField = this.env.model.root.data.version_id;
        } else {
            versionField = this.props.record.data.version_id;
        }

        if (versionField) {
            context.version_id = Array.isArray(versionField) ? versionField[0] : versionField;
        }

        const internalResumeLines = await this.orm.call(
            "hr.employee",
            "get_internal_resume_lines",
            [resId, resModel],
            { context: context }
        );
        return internalResumeLines;
    }
});
