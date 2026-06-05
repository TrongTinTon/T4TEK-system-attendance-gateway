# Fix groups.xml ParseError

This build fixes module loading failure in `security/groups.xml` by using a module-owned Gatekeeper permission category instead of referencing `base.module_category_human_resources`.

It also keeps Gatekeeper groups independent from `base.group_system`, so Gatekeeper Administrator does not automatically grant Odoo Settings/System Administrator permissions.
