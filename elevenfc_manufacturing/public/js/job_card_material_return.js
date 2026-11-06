/* 11FC: create a source-linked draft material return from a Job Card.
 * Does not auto-submit; native Stock Entry permissions, batch/serial, ledger
 * and other validations remain authoritative.
 */
(function () {
    const api = "elevenfc_manufacturing.api.job_card_material_return";

    async function choose_source(frm) {
        try {
            const response = await frappe.call({
                method: api + ".list_original_transfers",
                args: { job_card: frm.doc.name },
                freeze: true,
            });
            const transfers = response.message || [];
            if (!transfers.length) {
                frappe.msgprint(__("No eligible submitted material transfers were found for this Job Card. Serial/batch tracked items require a separate return workflow."));
                return;
            }
            const select_options = transfers.map(x => x.name);
            const dialog = new frappe.ui.Dialog({
                title: __("Return Materials — Select Original Transfer"),
                fields: [
                    {
                        fieldtype: "Select",
                        fieldname: "original_entry",
                        label: __("Original Stock Entry"),
                        options: select_options,
                        default: select_options[0],
                        reqd: 1,
                    },
                    { fieldtype: "HTML", options: "<p>" + __("Only unconsumed materials transferred to this Job Card can be returned.") + "</p>" },
                ],
                primary_action_label: __("Continue"),
                async primary_action(values) {
                    dialog.hide();
                    await choose_items(frm, values.original_entry);
                },
            });
            dialog.show();
        } catch (e) {
            frappe.msgprint(__("Unable to retrieve eligible material transfers. Please check your permissions and try again."));
        }
    }

    async function choose_items(frm, original_entry) {
        const response = await frappe.call({
            method: api + ".get_returnable_rows",
            args: { job_card: frm.doc.name, original_entry },
            freeze: true,
        });
        const rows = response.message || [];
        if (!rows.length) {
            frappe.msgprint(__("There are no remaining returnable quantities for this Stock Entry."));
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Return Materials from {0}", [original_entry]),
            size: "extra-large",
            fields: [
                {
                    fieldtype: "HTML",
                    options: "<p>" + __("Enter the return quantity for each material. A draft Stock Entry will be created for review; it will NOT be automatically submitted.") + "</p>",
                },
                {
                    fieldtype: "Table",
                    fieldname: "materials",
                    label: __("Materials"),
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    in_place_edit: true,
                    data: rows.map(row => ({
                        source_detail: row.source_detail,
                        item_code: row.item_code,
                        stock_uom: row.stock_uom,
                        from_warehouse: row.from_warehouse,
                        to_warehouse: row.to_warehouse,
                        maximum_qty: row.maximum_qty,
                        qty: 0,
                    })),
                    fields: [
                        { fieldtype: "Data", fieldname: "source_detail", label: __("Original Row"), read_only: 1, hidden: 1 },
                        { fieldtype: "Data", fieldname: "item_code", label: __("Material"), read_only: 1, in_list_view: 1, columns: 3 },
                        { fieldtype: "Data", fieldname: "stock_uom", label: __("UOM"), read_only: 1, in_list_view: 1, columns: 1 },
                        { fieldtype: "Float", fieldname: "maximum_qty", label: __("Available to Return"), read_only: 1, in_list_view: 1, columns: 3 },
                        { fieldtype: "Float", fieldname: "qty", label: __("Return Qty"), in_list_view: 1, columns: 3 },
                    ],
                },
            ],
            primary_action_label: __("Create Draft Return"),
            async primary_action() {
                const quantities = (dialog.get_value("materials") || [])
                    .filter(row => flt(row.qty) > 0)
                    .map(row => ({ source_detail: row.source_detail, qty: flt(row.qty) }));
                if (!quantities.length) {
                    frappe.msgprint(__("Enter a positive return quantity for at least one item."));
                    return;
                }
                for (const entry of quantities) {
                    const source = rows.find(row => row.source_detail === entry.source_detail);
                    if (!source || entry.qty > flt(source.maximum_qty)) {
                        frappe.msgprint(__("Return quantity exceeds the available quantity for an item."));
                        return;
                    }
                }
                const result = await frappe.call({
                    method: api + ".create_draft_return",
                    args: { job_card: frm.doc.name, original_entry, quantities },
                    freeze: true,
                });
                if (result.message && result.message.name) {
                    dialog.hide();
                    frappe.set_route("Form", "Stock Entry", result.message.name);
                }
            },
        });
        dialog.show();
    }

    frappe.ui.form.on("Job Card", {
        refresh(frm) {
            if (frm.is_new() || frm.doc.docstatus === 2 || !frm.doc.work_order || frm.doc.is_subcontracted) {
                return;
            }
            if (!frappe.model.can_create("Stock Entry")) return;
            frm.add_custom_button(
                __("Return Materials"),
                () => choose_source(frm),
                __("Create")
            );
        },
    });
})();
