/** @odoo-module **/

import { BSDGanttAdapter } from "./bsd_gantt_adapter";

/**
 * BSDSyncfusionGanttAdapter — Syncfusion EJ2 Gantt implementation
 *
 * Lib: ej2-gantt v33.1.44 (global build, self-contained UMD).
 * Lib expose globals: window.ej (namespace) → ej.gantt.Gantt, ej.base.
 *
 * License Mode:
 *   - Community / Paid license: gọi ej.base.registerLicense(key) trước
 *     khi render. Nếu KHÔNG register → component vẫn render nhưng kèm
 *     watermark "Trial" + console warning.
 *   - Key fetch từ controller /rp_progress/syncfusion/license_key
 *     (xem bsd_gantt_view.js).
 *
 * Field mapping (frappe-gantt task → ej2 task):
 *   id           → TaskID
 *   name         → TaskName
 *   start        → StartDate
 *   end          → EndDate
 *   progress     → Progress
 *   dependencies → Predecessor (str format "1FS,2FS")
 *   custom_class → cssClass (custom field, dùng cho rowDataBound styling)
 *   _isContract  → preserved cho callbacks
 *   _contractId  → preserved cho callbacks
 */
export class BSDSyncfusionGanttAdapter extends BSDGanttAdapter {
    static _licenseRegistered = false;

    /**
     * Register license 1 lần / page load. Safe re-call (idempotent
     * theo flag).
     */
    static registerLicense(key) {
        if (this._licenseRegistered) {
            return;
        }
        if (!window.ej || !window.ej.base || !window.ej.base.registerLicense) {
            throw new Error(
                "Syncfusion ej2-gantt.min.js chưa load — kiểm tra " +
                "rp_progress/static/lib/syncfusion/ + assets manifest"
            );
        }
        if (key) {
            window.ej.base.registerLicense(key);
        }
        this._licenseRegistered = true;
    }

    async render(container, tasks, opts = {}) {
        const ej = window.ej;
        if (!ej || !ej.gantt || !ej.gantt.Gantt) {
            throw new Error(
                "Syncfusion ej.gantt.Gantt không tồn tại — bundle chưa " +
                "load hoặc broken."
            );
        }
        if (opts.licenseKey) {
            BSDSyncfusionGanttAdapter.registerLicense(opts.licenseKey);
        }
        this.opts = opts;
        // Container phải có id để ej2 attach
        if (!container.id) {
            container.id = "bsd_syncfusion_gantt_" + Date.now();
        }

        // Map tasks → ej2 format. ej2 dùng Date objects, không phải
        // ISO string → parse trước.
        const ejTasks = tasks.map((t) => ({
            TaskID: t.id,
            TaskName: t.name,
            StartDate: this._parseDate(t.start),
            EndDate: this._parseDate(t.end),
            Progress: Math.round(t.progress || 0),
            Predecessor: t.dependencies || "",
            ParentID: t.parent || null,
            // Preserve custom fields cho callbacks
            _cssClass: t.custom_class || "",
            _isContract: !!t._isContract,
            _contractId: t._contractId || null,
            // Field tuỳ biến cho cột riêng của caller (vd WBS)
            ...(t.extraFields || {}),
        }));

        this.gantt = new ej.gantt.Gantt({
            dataSource: ejTasks,
            taskFields: {
                id: "TaskID",
                name: "TaskName",
                startDate: "StartDate",
                endDate: "EndDate",
                progress: "Progress",
                dependency: "Predecessor",
                parentID: "ParentID",
            },
            // View mode
            viewType: "ProjectView",
            // Toolbar built-in: zoom in/out, search, expand/collapse
            toolbar: [
                "ZoomIn", "ZoomOut", "ZoomToFit", "ExpandAll", "CollapseAll",
            ],
            // Column panel bên trái — minimal, business view ở Odoo panel
            treeColumnIndex: opts.treeColumnIndex || 1,
            // Optional: caller truyền bộ cột riêng (rp_schedule cần cột ID);
            // default giữ nguyên bộ cột rp_progress.
            columns: opts.columns || [
                { field: "TaskID", headerText: "ID", width: 70,
                  visible: false },
                { field: "TaskName", headerText: "Hạng mục / HĐ",
                  width: 280 },
                { field: "StartDate", headerText: "Bắt đầu",
                  format: "dd/MM/yyyy", width: 110 },
                { field: "EndDate", headerText: "Kết thúc",
                  format: "dd/MM/yyyy", width: 110 },
                { field: "Progress", headerText: "%", width: 70,
                  textAlign: "Right" },
            ],
            // Time zoom — map view mode frappe → ej2 timelineViewMode
            timelineSettings: {
                timelineViewMode: this._mapViewMode(
                    opts.viewMode || "Month"),
            },
            // Bar styling
            rowHeight: opts.rowHeight || 46,
            taskbarHeight: 28,
            // Locale: ej2 hỗ trợ nhiều locale, mặc định en. Để vi-VN
            // mặc định format date qua column format.
            // Editing:
            //  - allowEditing=false → KHÔNG cho sửa inline cell trong
            //    treegrid (double click không trigger edit)
            //  - allowTaskbarEditing=true → vẫn cho drag/resize bar
            //    để update ngày
            editSettings: {
                allowEditing: false,
                allowTaskbarEditing: true,
                // Optional (rp_schedule): thêm/xoá task qua context menu.
                // Mặc định false → hành vi rp_progress không đổi.
                allowAdding: !!opts.allowAdding,
                allowDeleting: !!opts.allowDeleting,
                showDeleteConfirmDialog: !!opts.allowDeleting,
            },
            // Optional: context menu chuột phải built-in EJ2 — chỉ bật
            // khi caller yêu cầu (rp_schedule).
            ...(opts.enableContextMenu ? {
                enableContextMenu: true,
                contextMenuItems: opts.contextMenuItems
                    || ["AutoFit", "TaskInformation", "Add", "DeleteTask"],
            } : {}),
            // Optional: 'Manual' = không auto-reschedule theo predecessor
            // (giữ đúng ngày import từ MS Project); default 'Auto' như cũ.
            taskMode: opts.taskMode || "Auto",
            allowResizing: true,
            allowSorting: true,
            // Splitter mặc định show 4 cột (TaskName + StartDate +
            //   EndDate + Progress). Set columnIndex để Syncfusion
            //   tính position theo số cột muốn hiện.
            splitterSettings: {
                columnIndex: opts.splitterColumnIndex || 4,
            },
            // Tooltip custom — KHÔNG dùng custom template, để Syncfusion
            // tự render default tooltip với TaskName/StartDate/EndDate
            // /Progress. Custom template trigger SyntaxError ở compile
            // engine (new Function) khi có optional chaining.
            tooltipSettings: {
                showTooltip: true,
            },
            // Events
            // Khi resize/kéo bar CÓ predecessor: EJ2 mặc định bật dialog
            // validate link — dialog compile template (new Function) gây
            // crash trong Odoo (cùng lý do bỏ custom tooltip). Optional
            // preserveLinks: giữ link + bỏ dialog.
            actionBegin: (args) => {
                if (opts.preserveLinks
                        && args.requestType === "validateLinkedTask"
                        && args.validateMode) {
                    args.validateMode.preserveLinkWithEditing = true;
                }
            },
            actionComplete: (args) => this._handleActionComplete(args, opts),
            // Optional hooks style theo hàng/thanh (caller tự quyết)
            ...(opts.onRowDataBound ? {
                rowDataBound: (args) => opts.onRowDataBound(args),
            } : {}),
            ...(opts.onQueryTaskbarInfo ? {
                queryTaskbarInfo: (args) => opts.onQueryTaskbarInfo(args),
            } : {}),
            // Click trên bar (chart bên phải) → mở form
            taskbarClick: (args) => {
                const cb = opts.onBarClick === false
                    ? null : (opts.onBarClick || opts.onClick);
                if (args.data && cb) {
                    cb({
                        id: args.data.TaskID,
                        _isContract: args.data._isContract,
                        _contractId: args.data._contractId,
                    });
                }
            },
            // Double click row trong treegrid (panel trái) → mở form.
            // Single click chỉ select row, double click trigger open
            // (UX nhất quán với Odoo list view, tránh accidental open).
            recordDoubleClick: (args) => {
                const data = args.rowData || args.data;
                if (data && opts.onClick) {
                    opts.onClick({
                        id: data.TaskID,
                        _isContract: data._isContract,
                        _contractId: data._contractId,
                    });
                }
            },
            // Height tự fit
            height: "100%",
            width: "100%",
        });
        this.gantt.appendTo(container);
    }

    /**
     * Map frappe view mode names → ej2 timelineViewMode.
     */
    _mapViewMode(mode) {
        const map = {
            "Quarter Day": "Hour",
            "Half Day": "Hour",
            "Day": "Day",
            "Week": "Week",
            "Month": "Month",
            "Year": "Year",
        };
        return map[mode] || "Month";
    }

    _parseDate(d) {
        if (!d) return null;
        if (d instanceof Date) return d;
        // ISO "YYYY-MM-DD" or "YYYY-MM-DD HH:MM:SS"
        return new Date(d);
    }

    _handleActionComplete(args, opts) {
        // Drag/resize taskbar → requestType = "save" với action = "TaskbarEditing"
        if (args.requestType === "save"
                && (args.action === "TaskbarEditing"
                    || args.action === "DrawConnectorLine"
                    || args.taskBarEditAction)) {
            if (opts.onDateChange && args.data) {
                opts.onDateChange(
                    {
                        id: args.data.TaskID,
                        _isContract: args.data._isContract,
                        _contractId: args.data._contractId,
                    },
                    args.data.StartDate,
                    args.data.EndDate,
                );
            }
        }
        // Optional: Add/Delete từ context menu EJ2 (rp_schedule) —
        // caller tự ghi Odoo rồi reload để đồng bộ ID thật.
        if (args.requestType === "add" && opts.onAdd && args.data) {
            opts.onAdd(args.data);
        }
        if (args.requestType === "delete" && opts.onDelete && args.data) {
            const rows = Array.isArray(args.data) ? args.data : [args.data];
            opts.onDelete(rows);
        }
    }

    changeViewMode(mode) {
        if (this.gantt) {
            this.gantt.timelineSettings.timelineViewMode = this._mapViewMode(mode);
            this.gantt.refresh();
        }
    }

    refresh(tasks) {
        if (this.gantt && tasks) {
            const ejTasks = tasks.map((t) => ({
                TaskID: t.id,
                TaskName: t.name,
                StartDate: this._parseDate(t.start),
                EndDate: this._parseDate(t.end),
                Progress: Math.round(t.progress || 0),
                Predecessor: t.dependencies || "",
                ParentID: t.parent || null,
                _cssClass: t.custom_class || "",
                _isContract: !!t._isContract,
                _contractId: t._contractId || null,
            }));
            this.gantt.dataSource = ejTasks;
        }
    }

    destroy() {
        if (this.gantt) {
            try {
                this.gantt.destroy();
            } catch (e) {
                // ignore — already detached
            }
            this.gantt = null;
        }
    }
}
