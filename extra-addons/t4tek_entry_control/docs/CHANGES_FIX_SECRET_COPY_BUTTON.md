# Fix Secret Key Copy Button

- Made Generate Key and Copy Key buttons visible to Odoo system administrators (`base.group_system`).
- Added an inline `Copy Secret Key` button next to the Secret Key field on the Controller form.
- Added `CopyClipboardChar` widget to the Secret Key field so users can copy the value directly from the field.
- Kept access restricted to system administrators.
