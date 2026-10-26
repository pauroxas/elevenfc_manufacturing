/* 11FC: let standard Job Cards start/complete/submit with zero or
 * partial raw material transfers. Does not bypass any server validation
 * except the approved material-transfer prerequisite.
 */
(function () {
    function is_eligible(frm) {
        const doc = frm.doc;
        return doc.docstatus === 0 &&
            !doc.is_subcontracted &&
            !doc.finished_good &&
            !doc.is_corrective_job_card &&
            !doc.skip_material_transfer &&
            !!doc.items?.length;
    }

    function wrap(frm) {
        if (frm.__elevenfc_under_transfer_wrapped) return;
        frm.__elevenfc_under_transfer_wrapped = true;

        // Native v16.52 dashboard + job steps gate actions on materials.
        // Only while drawing these controls, temporarily expose the
        // already-supported skip flag. Never save/change the document.
        for (const action of ["make_dashboard", "get_job_steps"]) {
            const original = frm.events[action];
            if (typeof original !== "function") continue;

            frm.events[action] = function (...args) {
                if (!is_eligible(frm)) return original.apply(this, args);
                const original_flag = frm.doc.skip_material_transfer;
                try {
                    frm.doc.skip_material_transfer = 1;
                    return original.apply(this, args);
                } finally {
                    frm.doc.skip_material_transfer = original_flag;
                }
            };
        }
    }

    frappe.ui.form.on("Job Card", {
        setup(frm) {
            wrap(frm);
        },
        refresh(frm) {
            wrap(frm);
            if (!is_eligible(frm) || frm.is_new()) return;
            // Re-render if native refresh ran before this custom handler.
            const has_items = !!frm.doc.items?.length;
            frm.events.make_dashboard(frm, has_items);
            frm.events.hold_submit_until_job_is_done(frm, has_items);
            frm.events.keep_one_primary_button(frm);
        }
    });
})();
