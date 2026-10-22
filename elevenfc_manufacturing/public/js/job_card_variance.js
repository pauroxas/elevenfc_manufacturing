/* 11FC Job Card material variance UX for ERPNext v16.52.x.
 * Does not change any BOM, Job Card quantities, or saved skip_material_transfer flag.
 */
(function () {
    "use strict";
    function withApprovedDashboardView(frm, fn) {
        if (!frm.__elevenfc_variance_status?.approval_valid) return fn();
        const original = frm.doc.skip_material_transfer;
        frm.doc.skip_material_transfer = 1;
        try { return fn(); } finally { frm.doc.skip_material_transfer = original; }
    }
    function wrapDashboard(frm) {
        if (frm.__elevenfc_dashboard_wrapped) return;
        frm.__elevenfc_dashboard_wrapped = true;
        for (const methodName of ["make_dashboard", "get_job_steps"]) {
            const original = frm.events[methodName];
            if (typeof original !== "function") continue;
            frm.events[methodName] = function (...args) {
                return withApprovedDashboardView(frm, () => original.apply(frm.events, args));
            };
        }
    }
    function approve(frm) {
        frappe.prompt(
            [{fieldname: "reason", fieldtype: "Small Text", label: __("Reason for Material Variance"), reqd: 1}],
            (values) => {
                frappe.call({
                    method: "elevenfc_manufacturing.api.approve_material_variance",
                    type: "POST",
                    args: {job_card: frm.doc.name, reason: values.reason},
                    freeze: true,
                }).then(() => frm.reload_doc());
            },
            __("Approve Material Variance"),
            __("Approve")
        );
    }
    frappe.ui.form.on("Job Card", {
        setup(frm) { wrapDashboard(frm); },
        refresh(frm) {
            if (frm.is_new() || frm.doc.docstatus !== 0) return;
            wrapDashboard(frm);
            frm.__elevenfc_variance_status = null;
            const jobCard = frm.doc.name;
            frappe.call({
                method: "elevenfc_manufacturing.api.get_material_variance_status",
                args: {job_card: jobCard},
            }).then(({message}) => {
                if (!message || frm.doc.name !== jobCard || frm.doc.docstatus !== 0) return;
                frm.__elevenfc_variance_status = message;
                if (!message.has_variance) return;
                if (message.approval_valid) {
                    frm.set_intro(__("Material variance approved by {0}. Original BOM/WO requirements are unchanged.", [message.approved_by]), "green");
                    if (message.can_approve) {
                        frm.add_custom_button(__("Revoke Variance Approval"), () => {
                            frappe.confirm(__("Revoke this Job Card's material variance approval?"), () => {
                                frappe.call({
                                    method: "elevenfc_manufacturing.api.revoke_material_variance",
                                    type: "POST", args: {job_card: jobCard}, freeze: true,
                                }).then(() => frm.reload_doc());
                            });
                        }, __("Material Variance"));
                    }
                } else {
                    frm.set_intro(__("Transferred materials differ from the Work Order plan. Approval is required to proceed without editing Required Qty."), "orange");
                    if (message.can_approve) {
                        frm.add_custom_button(__("Approve Material Variance"), () => approve(frm), __("Material Variance"));
                    }
                }
                frm.events.make_dashboard(frm, !!frm.doc.items?.length);
                frm.events.hold_submit_until_job_is_done(frm, !!frm.doc.items?.length);
                frm.events.keep_one_primary_button(frm);
            });
        },
    });
})();