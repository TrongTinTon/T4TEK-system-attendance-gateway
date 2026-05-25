# Fix menu visibility

- Grant model access to `base.group_system` so Odoo administrators can see actions and menus immediately after install.
- Add `groups="base.group_system"` on root and child menu items for explicit admin visibility.
- Remove missing `web_icon` reference from menu root to avoid icon-path related UI issues.
- Remove missing manifest image reference.
