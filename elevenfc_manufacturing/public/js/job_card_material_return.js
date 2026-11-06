/* 11FC: Job Card -> Return Materials, no original Stock Entry selection.
 * Discover all eligible material transfers and preserve their origins internally.
 * Creates draft(s) only; user reviews and submits through Stock Entry.
 */
(function () {
    const api = "elevenfc_manufacturing.api.job_card_material_return";

    async function show_materials(frm) {
        const response = await frappe.call({
            method: api + ".get_job_card_returnable_rows",
            args: { job_card: frm.doc.name },
            freeze: true,
        });
        const rows = response.message || [];
        if (!rows.length) {
            frappe.msgprint(__("There are no eligible unconsumed materials to return for this Job Card. Serial/batch-tracked items are excluded from this initial workflow."));
            return;
        }

        const dialog = new frappe.ui.Dialog({
            title: __("Return Materials"),
            size: "extra-large",
            fields: [
                {
                    fieldtype: "HTML",
                    options: "<p>" + __("Select the quantities to return. The source transfers are linked automatically. The return Stock Entry will remain a draft until reviewed and submitted.") + "</p>",
                },
                {
                    fieldtype: "Table",
                    fieldname: "materials",
                    label: __("Materials"),
                    cannot_add_rows: true,
                    cannot_delete_rows: true,
                    in_place_edit: true,
                    data: rows.map(row => ({
                        original_entry: row.original_entry,
                        source_detail: row.source_detail,
                        item_code: row.item_code,
                        stock_uom: row.stock_uom,
                        maximum_qty: row.maximum_qty,
                        qty: 0,
                    })),
                    fields: [
                        { fieldtype: "Data", fieldname: "original_entry", label: __("Original Transfer"), hidden: 1, read_only: 1 },
                        { fieldtype: "Data", fieldname: "source_detail", label: __("Original Row"), hidden: 1, read_only: 1 },
                        { fieldtype: "Data", fieldname: "item_code", label: __("Material"), read_only: 1, in_list_view: 1, columns: 3 },
                        { fieldtype: "Data", fieldname: "stock_uom", label: __("UOM"), read_only: 1, in_list_view: 1, columns: 1 },
                        { fieldtype: "Float", fieldname: "maximum_qty", label: __("Available to Return"), read_only: 1, in_list_view: 1, columns: 3 },
                        { fieldtype: "Float", fieldname: "qty", label: __("Return Qty"), in_list_view: 1, columns: 3 },
                    ],
                },
            ],
            primary_action_label: __("Create Draft Return"),
            async primary_action() {
                const selected = (dialog.get_value("materials") || [])
                    .filter(row => flt(row.qty) > 0)
                    .map(row => ({
                        original_entry: row.original_entry,
                        source_detail: row.source_detail,
                        qty: flt(row.qty),
                    }));

                if (!selected.length) {
                    frappe.msgprint(__("Enter a positive return quantity for at least one material."));
                    return;
                }

                for (const entry of selected) {
                    const source = rows.find(row =>
                        row.original_entry === entry.original_entry &&
                        row.source_detail === entry.source_detail
                    );
                    if (!source || entry.qty > flt(source.maximum_qty)) {
                        frappe.msgprint(__("A return quantity exceeds the allowable balance."));
                        return;
                    }
                }

                const result = await frappe.call({
                    method: api + ".create_draft_returns",
                    args: { job_card: frm.doc.name, quantities: selected },
                    freeze: true,
                });
                const names = result.message?.names || [];
                if (!names.length) return;

                dialog.hide();
                if (names.length === 1) {
                    frappe.set_route("Form", "Stock Entry", names[0]);
                } else {
                    const message = names.map(name =>
                        '<li><a href="/app/stock-entry/' +
                        encodeURIComponent(name) + '">' +
                        frappe.utils.escape_html(name) + '</a></li>'
                    ).join("");
                    frappe.msgprint({
                        title: __("Draft Return Stock Entries Created"),
                        message: "<p>" + __("Your selected materials came from multiple original transfers, so separate traceable draft Stock Entries were created. Review and submit each draft.") + "</p><ul>" + message + "</ul>",
                        indicator: "blue",
                    });
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
                () => show_materials(frm),
                __("Create")
            );
        },
    });
})();
