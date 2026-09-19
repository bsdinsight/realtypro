/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { DateTimeField } from "@web/views/fields/datetime/datetime_field";
import { formatDate, formatDateTime } from "@web/core/l10n/dates";
import { localization } from "@web/core/l10n/localization";

/**
 * Force numeric date format (dd/MM/yyyy) in Realty.
 *
 * Real estate transactions span 5-30 years (construction, handover,
 * warranty, maintenance). Dates without a year ("May 6") are ambiguous
 * and dangerous in legal contracts.
 *
 * This file used to patch DateTimeField.defaultProps.numeric (Odoo 19).
 * Odoo 17 has no `numeric` prop; setting it makes OWL reject the field
 * and breaks module install / the whole backend. Patch display instead.
 *
 * Coverage: form and list date/datetime widgets (ListDateTimeField
 * extends DateTimeField).
 *
 * Does NOT affect Discuss relative time, calendar labels, or activity
 * "from now" strings.
 */
const NUMERIC_DATE_FORMAT = "dd/MM/yyyy";

patch(DateTimeField.prototype, {
    /**
     * @override
     * @param {number} valueIndex
     */
    getFormattedValue(valueIndex) {
        const value = this.values[valueIndex];
        if (!value) {
            return "";
        }
        if (this.field.type === "date" || !this.props.showTime) {
            return formatDate(value, { format: NUMERIC_DATE_FORMAT });
        }
        const timeFormat = localization.timeFormat || "HH:mm:ss";
        return formatDateTime(value, {
            format: `${NUMERIC_DATE_FORMAT} ${timeFormat}`,
        });
    },
});
