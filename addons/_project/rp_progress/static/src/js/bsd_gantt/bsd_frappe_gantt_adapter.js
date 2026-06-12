/** @odoo-module **/

import { BSDGanttAdapter } from "./bsd_gantt_adapter";

/**
 * BSDFrappeGanttAdapter — Community Edition implementation
 *
 * Wrapper quanh frappe-gantt (MIT). Library expose `window.Gantt`
 * sau khi file static/lib/frappe-gantt/frappe-gantt.js load.
 *
 * Limitation Community: cap 500 tasks (enforce ở BSDGanttView level).
 */
export class BSDFrappeGanttAdapter extends BSDGanttAdapter {
    async render(container, tasks, opts = {}) {
        const Gantt = window.Gantt;
        if (!Gantt) {
            throw new Error(
                "frappe-gantt library chưa load — kiểm tra " +
                "rp_progress/static/lib/frappe-gantt/ + assets manifest"
            );
        }
        this.opts = opts;
        // Note: frappe-gantt v0.6 supports: en, es, fr, ptBr, ru, zh, ko,
        // tr — KHÔNG có 'vi'. Pass locale không support → crash khi đọc
        // month_names[locale][0]. Default sang 'en'; UI vẫn show ngày
        // Vietnamese qua custom popup.
        const SUPPORTED_LOCALES = ['en', 'es', 'fr', 'ptBr', 'ru', 'zh', 'ko', 'tr'];
        const locale = SUPPORTED_LOCALES.includes(opts.locale)
            ? opts.locale : 'en';
        this.gantt = new Gantt(container, tasks, {
            view_mode: opts.viewMode || "Month",
            language: locale,
            popup_trigger: "mouseover",
            bar_height: 28,
            bar_corner_radius: 4,
            padding: 18,
            header_height: 50,
            on_click: (task) => opts.onClick && opts.onClick(task),
            on_date_change: (task, start, end) =>
                opts.onDateChange && opts.onDateChange(task, start, end),
            on_progress_change: (task, progress) =>
                opts.onProgressChange && opts.onProgressChange(task, progress),
            custom_popup_html: (task) =>
                this._renderPopup(task, opts.formatCurrency),
        });
    }

    _renderPopup(task, formatCurrency) {
        const fmtDate = (d) => {
            if (!d) return "—";
            const dt = new Date(d);
            return dt.toLocaleDateString("vi-VN");
        };
        if (task._isContract) {
            const cprogress = Math.round(task.progress || 0);
            return `
              <div class="bsd_gantt_popup">
                <h5>📄 ${task.name}</h5>
                <div><b>Khởi công:</b> ${fmtDate(task.start)}</div>
                <div><b>Hoàn thành DK:</b> ${fmtDate(task.end)}</div>
                <div><b>% nghiệm thu:</b> ${cprogress}%</div>
              </div>
            `;
        }
        const progress = Math.round(task.progress || 0);
        const value = task._estimateValue
            ? `<div><b>Giá trị:</b> ${
                  formatCurrency
                      ? formatCurrency(task._estimateValue)
                      : task._estimateValue.toLocaleString("vi-VN")
              }</div>`
            : "";
        return `
          <div class="bsd_gantt_popup">
            <h5>${task.name}</h5>
            <div><b>Bắt đầu:</b> ${fmtDate(task.start)}</div>
            <div><b>Kết thúc:</b> ${fmtDate(task.end)}</div>
            <div><b>Tiến độ:</b> ${progress}%</div>
            ${value}
          </div>
        `;
    }

    changeViewMode(mode) {
        if (this.gantt) {
            this.gantt.change_view_mode(mode);
        }
    }

    refresh(tasks) {
        if (this.gantt) {
            this.gantt.refresh(tasks);
        }
    }

    destroy() {
        // frappe-gantt không có destroy method; clear container
        if (this.gantt && this.gantt.$svg && this.gantt.$svg.parentNode) {
            this.gantt.$svg.parentNode.innerHTML = "";
        }
        this.gantt = null;
    }
}
