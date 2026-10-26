# 11FC Manufacturing v0.3.1 — Limited client-approved DEV release

**Scope: Under-transfer and zero material transfer at Job Card only.**

## Client-approved changes

- A standard Job Card is not blocked at Start/Complete/Submit just because
  fewer raw materials were transferred to WIP than the original requirement.
- The same applies when **zero** materials were transferred.
- BOM, Work Order and Job Card required quantities remain unchanged.
- Native time logs, completed quantity, Work Order, sequence, inspection,
  manufacturing output, stock ledger and accounting validations remain active.

## Explicitly excluded from this release

- No new over-transfer approval role or approval API.
- No new Stock Entry hooks or cumulative transfer validation.
- No consumption / overconsumption change.
- No BOM substitution change.
- No change to Manufacturing Settings or native excess-transfer limits.
- Existing v0.2.0/v0.3.0 approval custom field values remain in the database
  for history but approval controls are hidden during migration.

If approval of over-transfers is required in a future phase, design/review
that as a separate, explicitly authorized release.

## DEV deployment

1. Keep PROD unchanged. Make a DEV database/files backup.
2. Deploy this repository's `main` at v0.3.1 to the DEV bench and migrate site.
3. Build assets / restart / clear cache according to Frappe Cloud workflow.
4. Verify Installed Apps version 0.3.1.
5. Ensure **Manufacturing Settings → Allow Excess Material Transfer** is OFF
   unless DEV already depends on it for another approved use case.
6. Complete and sign off DEV manufacturing + accounting tests before PROD.

## Test scenarios

- WO requires 50 units: Job Card with 0 and with 30 material transferred can
  Start, Complete and Submit with valid time logs and completed quantity.
- WO requires 50 units: exact transfer of 50 behaves normally.
- Transfer of 60 against 50: ERPNext's standard over-transfer restriction still
  applies; 11FC does not add an approval mechanism.
- Submitted non-Job-Card manufacturing transfers remain unchanged.
- Subcontracted / corrective / finished-good Job Cards keep their native rules.
- Manufacturing Stock Entry creation, returned components, stock and GL
  valuation are unchanged; verify these end to end on DEV.
- A submitted Job Card must still require valid time logs, quantity completion,
  quality/sequence rules and other ERPNext built-in checks.

Source compatibility was reviewed against ERPNext v16.52.0. This release has
not been deployed to a live Frappe/ERPNext instance for end-to-end QA.
