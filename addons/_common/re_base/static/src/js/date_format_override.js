/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DateTimeField, dateTimeField } from "@web/views/fields/datetime/datetime_field";

/**
 * Force numeric date format (dd/MM/yyyy) for the RealtySales context.
 *
 * Real estate transactions span 5-30 years (construction, handover,
 * warranty, maintenance). Dates without year ("May 6") are ambiguous
 * and dangerous in legal contracts.
 *
 * In Odoo 19, the default is numeric=false → renders "May 6" via Luxon
 * localized format. Setting numeric=true → renders "06/05/2026" format
 * matching the current language's date_format setting.
 *
 * Coverage:
 * - Form view date/datetime fields ✓
 * - List view date/datetime columns ✓
 *
 * Does NOT affect:
 * - Discuss "5 minutes ago"     (uses relative time formatter)
 * - Calendar "Tomorrow at 3PM"  (uses different formatter)
 * - Activity timeline           (uses moment.fromNow)
 *
 * Individual fields can still opt-out via:
 *   <field name="X" options="{'numeric': false}"/>
 */

// Force numeric format on DateTimeField default props
patch(DateTimeField, {
    defaultProps: {
        ...DateTimeField.defaultProps,
        numeric: true,
    },
});

// Ensure numeric stays true unless explicitly overridden in XML
patch(dateTimeField, {
    extractProps() {
        const props = super.extractProps(...arguments);
        if (props.numeric === undefined) {
            props.numeric = true;
        }
        return props;
    },
});
