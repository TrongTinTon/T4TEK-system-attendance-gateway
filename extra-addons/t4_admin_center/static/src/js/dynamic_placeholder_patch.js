/** @odoo-module **/

import { DynamicPlaceholderPopover } from "@web/views/fields/dynamic_placeholder_popover";
import { patch } from "@web/core/utils/patch";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";

patch(DynamicPlaceholderPopover.prototype, {
    setup() {
        super.setup(...arguments);
        // After parent setup (which sets isTemplateEditor via onWillStart),
        // add another onWillStart to also grant access to group_admin_center.
        onWillStart(async () => {
            if (!this.isTemplateEditor) {
                this.isTemplateEditor = await user.hasGroup("t4_admin_center.group_admin_center");
            }
        });
    },

    filter(fieldDef, path) {
        // Nếu isTemplateEditor = true (kể cả group_admin_center) → bỏ qua allowedQwebExpressions
        if (this.isTemplateEditor) {
            return !["one2many", "boolean", "many2many"].includes(fieldDef.type) && fieldDef.searchable;
        }
        return super.filter(fieldDef, path);
    },
});
