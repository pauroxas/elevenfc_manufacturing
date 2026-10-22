# 11FC Manufacturing — Material Variance Approval v0.2.0

This upgrades the existing `elevenfc_manufacturing` v0.1.0 app for **Frappe v16 / ERPNext v16.52.x**.

## Purpose

Preserve the original BOM, Work Order, and Job Card Required Qty while allowing authorized material variances.

Example: A Work Order plans **50 units of raw material** to produce **100 FG**. Actual transferred material is **30 units**. Once approved, the Job Card may Start, Complete, and Submit without changing the original required material quantity.

## Approval workflow

1. The application creates the role `11FC Material Variance Approver`; administrators assign it to production approvers. System Managers may also approve.
2. An authorized approver opens a draft Job Card, selects **Material Variance → Approve Material Variance**, and enters a justification of 10–500 characters.
3. The application checks role and write access, valid Work Order quantities, positive submitted raw-material transfers for every originally required component, and FG-equivalent transfer coverage.
4. The Job Card stores read-only approved by, approved on, reason and a fingerprint of the plan and submitted transfer quantities, plus a comment audit trail.
5. If transfer quantities, the Work Order plan, or the FG target change, approval is invalidated and must be renewed.
6. Authorized approvers may revoke approval before submission.

The original BOM, WO, Job Card Required Qty, Stock Entries, and actual material consumption are not automatically changed. The app affects Job Card material-variance validation and its dashboard behavior; normal FG production, stock and other validations still apply.

## Deploy on Frappe Cloud

1. Preserve your v0.1.0 version and deploy the update from a feature branch on a **staging private bench**.
2. Run the site update / migrate so `after_migrate` creates the role and custom fields.
3. Assign `11FC Material Variance Approver` to production approvers.
4. Hard-refresh the Job Card page for updated JavaScript.
5. Test the scenarios below and review the ledger and FG valuation. Merge and deploy to production only after staging checks pass.

## Required staging tests

| Scenario | Expected result |
|---|---|
| WO requires 50, 30 transferred, FG 100, without approval | Block |
| Same Job Card approved | Permit normal actions without editing Required Qty |
| 50 planned and 30 transferred displayed | Preserve both values |
| Unauthorized user attempts API approval | Deny |
| Any required component has zero transfer | Deny approval |
| FG transfer coverage less than FG target | Deny |
| Transfer quantity changes after approval | Approval becomes invalid |
| WO or FG target changes after approval | Approval becomes invalid |
| Correct transfer without variance | Normal ERPNext flow |
| Manufacture consumes actual raw material | Confirm WIP ledger/valuation independently |

This version is not a substitute for Frappe end-to-end testing. Approval allows documented variance; it does not create Stock Entries or automatically complete finished goods.

## Implementation

- `extend_doctype_class` hooks the Job Card controller in v16.
- `after_install` and `after_migrate` create custom fields and the approval role.
- The approval endpoints enforce permissions.
- `doctype_js` enhances Job Card UI after checking saved approval state.
- The approval fingerprint prevents reusing an authorization after specified quantities change.
