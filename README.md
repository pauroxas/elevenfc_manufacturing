# 11FC Manufacturing v0.3.0 — Under-Transfer and Over-Transfer

**Development-only candidate for ERPNext/Frappe v16.52.x. Do not deploy to production before QA.**

## Policy

- Zero, partial and exact raw material **transfers** can proceed with no approval.
- Transfers above original Work Order requirements require approval from a user assigned **11FC Over-Transfer Approver** plus Stock Entry write permission.
- Rules apply to **Material Transfer for Manufacture Stock Entries**, whether created from Work Orders or Job Cards.
- Uses **cumulative submitted transfers** in Stock UOM, net of submitted returns, grouped by Work Order and (when linked) Job Card. Multiple line items per same code are combined.
- Extra/unplanned materials exceed a zero planned quantity and require approval.
- Approval is given on a saved **draft Stock Entry**, includes a reason, approver and timestamp, and is bound to a fingerprint of its proposed stock movement, Work Order plan, Job Card plan, and earlier submitted transfers.
- If quantities or preceding transfers change, the approval becomes invalid at submission.
- These rules govern **transfer to WIP, not actual material consumption**. Manufacture Stock Entries retain ERPNext's standard consumption and valuation rules.
- Original BOM, Work Order and Job Card material requirements are never rewritten.

## Migration from v0.2.0

The new **11FC Over-Transfer Approver** role and Stock Entry approval fields are created during migration. Previous v0.2.0 Job Card approval fields and audit history are preserved but are no longer used to authorize under-transfers. Assign the new role only to the correct users. Old material variance role is not sufficient to approve over-transfers.

## Testing before merging

1. Install on separate Frappe Cloud dev/staging bench, run the site migrate, and refresh browser assets.
2. Verify Job Card can Start/Complete/Submit with Required Qty=50, Transferred Qty=30 and actual FG count per Work Order; time logs must still be complete.
3. Verify a Job Card with **zero** raw material transfer can complete when all other required workflow steps and ERPNext constraints are met; confirm stock and costing treatment.
4. With WO item planned 50, transfer 30 then 20 (no approval) then another 10 (requires approval).
5. Test 60 units in one transfer with an approved reason, and reject without approval.
6. Test approved transfer edited afterward and another submitted transfer before submission: both must invalidate approval.
7. Test two Job Cards sharing a Work Order, duplicate item lines, UOM conversion, and returns.
8. Test an item not on the Work Order and a normal Stock Entry without manufacturing purpose.
9. Verify unauthorized users cannot call the approval endpoint. Verify the role is assigned to named approvers.
10. Check submitted ledger entries, actual WIP consumption, finished goods valuation, and standard Job Card Time Log requirements.
11. Test concurrent submissions referencing one WO before production deployment.

## Constraints

The over-transfer threshold is derived from Work Order required raw materials in Stock UOM. When attached to a Job Card, a proportional Job Card threshold is also applied. The approval is per Stock Entry, not a permanent unlimited permission for the Work Order.

Known limitation: ERPNext's native creation screen may not offer an additional transfer line when the Job Card appears fully transferred. Such extra transfers should be drafted via a supported workflow and linked to the correct WO/JC with ERPNext's own validations intact.

GitHub changes alone do not deploy to Frappe Cloud. Merge after code review, then have the admin deploy/migrate and QA on dev before production.
