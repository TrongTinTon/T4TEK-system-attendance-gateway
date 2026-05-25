/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

async function copyTextToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-1000px";
    textarea.style.left = "-1000px";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand("copy");
    document.body.removeChild(textarea);
}

registry.category("actions").add("t4tek_entry_control.copy_to_clipboard", async (env, action) => {
    const params = action.params || {};
    const text = params.text || "";
    if (!text) {
        env.services.notification.add(_t("Nothing to copy."), { type: "warning" });
        return;
    }
    try {
        await copyTextToClipboard(text);
        env.services.notification.add(params.message || _t("Copied to clipboard."), {
            title: params.title || _t("Copied"),
            type: "success",
        });
    } catch (error) {
        env.services.notification.add(_t("Could not copy to clipboard. Please copy the field manually."), {
            title: params.title || _t("Copy failed"),
            type: "danger",
        });
    }
});
