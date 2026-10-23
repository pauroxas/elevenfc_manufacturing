/* 11FC over-transfer approval controls live on a saved draft Stock Entry. */
frappe.ui.form.on("Stock Entry", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.docstatus !== 0 ||
            frm.doc.purpose !== "Material Transfer for Manufacture" || frm.doc.is_return) return;
        const name = frm.doc.name;
        frappe.call({
            method: "elevenfc_manufacturing.over_transfer_api.get_over_transfer_status",
            type: "GET", args: {stock_entry: name}
        }).then(({message}) => {
            if (!message || frm.doc.name !== name || frm.doc.docstatus !== 0) return;
            if (!message.has_over_transfer) return;
            if (message.approval_valid) {
                frm.set_intro(__("11FC over-transfer approved by {0}. Reapproval is required if quantities change.", [message.approved_by]), "green");
                if (message.can_approve) {
                    frm.add_custom_button(__("Revoke Over-Transfer Approval"), () => {
                        frappe.confirm(__("Revoke approval?"), () =>
                            frappe.call({method: "elevenfc_manufacturing.over_transfer_api.revoke_over_transfer",
                                         type: "POST", args: {stock_entry: name}}).then(() => frm.reload_doc()));
                    }, __("Over-Transfer"));
                }
            } else {
                frm.set_intro(__("This material transfer exceeds its Work Order/Job Card allowance and requires authorized approval before submission."), "orange");
                if (message.can_approve) {
                    frm.add_custom_button(__("Approve Over-Transfer"), () => {
                        frappe.prompt([{fieldname: "reason", fieldtype: "Small Text",
                            label: __("Justification"), reqd: 1}], values => {
                            frappe.call({
                                method: "elevenfc_manufacturing.over_transfer_api.approve_over_transfer",
                                type: "POST", args: {stock_entry: name, reason: values.reason},
                                freeze: true
                            }).then(() => frm.reload_doc());
                        }, __("Approve Over-Transfer"), __("Approve"));
                    }, __("Over-Transfer"));
                }
            }
        });
    }
});
