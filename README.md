# 11FC Manufacturing - ERPNext v16.52 Job Card workaround

## Scope

This package extends `Job Card.has_short_transferred_material()` using Frappe v16's
`extend_doctype_class` hook. ERPNext v16.52 checks actual Job Card transfers against
original Work Order material requirements. This extension instead evaluates the
Job Card's current Required Qty vs Transferred Qty item by item.

It does NOT:
- Create stock entries or raw material movement.
- Automatically change Job Card required quantities.
- Bypass ERPNext's overall FG-equivalent transfer coverage check.
- Automatically adjust actual material consumption or finished-good valuation.

This override **will** allow a user who can change Job Card Required Qty to lower
that requirement. Limit edit permissions and audit material variances as needed.

## Deployment on Frappe Cloud

1. Review the code and test on a staging copy of the 11FC site first.
2. Create a PRIVATE GitHub repository. Upload the CONTENTS of this folder to the
   repository root. Do not upload this ZIP as the application.
3. Open Frappe Cloud > Private Bench > Apps > Add App > Add from GitHub.
4. Connect GitHub, select the private repo and branch, validate, and Add App.
5. Deploy the updated bench group.
6. On the STAGING site's dashboard, Apps > Install App > 11FC Manufacturing.
7. Test Job Card: WO BOM planned material 50; confirmed WIP transfer 30;
   Job Card item Required Qty 30 and Transferred Qty 30; for_quantity 100;
   Job Card-level transferred_qty 100. The Job Card should pass this particular
   material shortage check.
8. Confirm FG stock entry consumes 30 from the correct WIP location and FG=100.
9. Repeat deployment/install for the production site after testing and backup.

## Code compatibility

Tested for syntax only, not against a live Frappe instance. The override targets
method names and behavior verified in ERPNext tag v16.52.0. Re-test before any
future major or minor ERPNext update.

## Rollback

Restore the old bench version or remove/disable this app through the managed
site/bench process. Do not delete repository or bench app while still installed
on the site. Restore a site backup if a migration changes data unexpectedly.
