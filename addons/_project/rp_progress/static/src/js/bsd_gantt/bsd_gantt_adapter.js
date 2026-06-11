/** @odoo-module **/

/**
 * BSDGanttAdapter — abstract interface
 *
 * Strategy pattern: Community Edition dùng FrappeGanttAdapter (MIT),
 * Enterprise Edition override service `bsd_gantt_adapter` để inject
 * BryntumGanttAdapter (commercial, advanced features).
 *
 * Contract:
 *   - render(container, tasks, opts):  vẽ Gantt vào DOM container
 *   - destroy():                       cleanup khi unmount
 *   - changeViewMode(mode):            'Quarter Day' | 'Half Day' | 'Day' | 'Week' | 'Month' | 'Year'
 *   - refresh(tasks):                  redraw với data mới
 *
 * Tasks format (frappe-gantt compatible):
 *   { id, name, start, end, progress, dependencies, custom_class }
 *
 * opts:
 *   - onClick(task):    callback khi user click task bar
 *   - onDateChange(task, start, end):  callback khi drag/resize
 *   - onProgressChange(task, progress): callback khi đổi progress
 */
export class BSDGanttAdapter {
    constructor(env) {
        this.env = env;
    }

    /** @abstract */
    async render(_container, _tasks, _opts = {}) {
        throw new Error("BSDGanttAdapter.render must be overridden");
    }

    /** @abstract */
    destroy() {}

    /** @abstract */
    changeViewMode(_mode) {}

    /** @abstract */
    refresh(_tasks) {}
}
