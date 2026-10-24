/* 11FC Job Card: under-transfer (including zero) is permitted.
 * This changes presentation only. Native Job Card time-log rules still apply.
 */
(function () {
    function wrap(frm) {
        if (frm.__elevenfc_v3_wrapped) return;
        frm.__elevenfc_v3_wrapped = true;
        for (const key of ["make_dashboard", "get_job_steps"]) {
            const original = frm.events[key];
            if (typeof original !== "function") continue;
            frm.events[key] = function (...args) {
                const previous = frm.doc.skip_material_transfer;
                frm.doc.skip_material_transfer = 1;
                try { return original.apply(frm.events, args); }
                finally { frm.doc.skip_material_transfer = previous; }
            };
        }
    }
    frappe.ui.form.on("Job Card", {
        setup(frm) { wrap(frm); },
        refresh(frm) {
            wrap(frm);
            if (frm.is_new() || frm.doc.docstatus !== 0) return;
            frm.set_intro(__("11FC: Under-transfer and zero material transfer are allowed. Over-transfers require approval on the Material Transfer Stock Entry."), "blue");
            const hasItems = !!frm.doc.items?.length;
            frm.events.make_dashboard(frm, hasItems);
            frm.events.hold_submit_until_job_is_done(frm, hasItems);
            frm.events.keep_one_primary_button(frm);
        }
    });
})();
