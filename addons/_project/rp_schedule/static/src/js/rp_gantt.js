/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { ConfirmationDialog }
    from "@web/core/confirmation_dialog/confirmation_dialog";
import { BSDSyncfusionGanttAdapter }
    from "@rp_progress/js/bsd_gantt/bsd_syncfusion_gantt_adapter";

// Gantt lịch thi công theo HĐ nhà thầu — dùng Syncfusion EJ2 (bản quyền
// BSD, license param `syncfusion.license_key`, đã triển khai ở
// rp_progress/frm_gantt). Tái dùng BSDSyncfusionGanttAdapter:
// EJ2 tự có TreeGrid trái + splitter + zoom + context menu + drag bar.
//
// Hierarchy suy từ WBS chấm ("1.2" là con "1"); ngày trống → EJ2 tự
// aggregate summary; milestone (start=end) → EJ2 vẽ hình thoi.
export class RpGanttAction extends Component {
    static template = "rp_schedule.RpGantt";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.dialog = useService("dialog");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            viewMode: "Week",
            count: 0,
            title: "",
            empty: false,
            loading: true,
            error: null,
            showBaseline: false,
            showCriticalPath: false,
            hasBaseline: false,
        });
        const ctx = (this.props.action && this.props.action.context) || {};
        this.contractId =
            ctx.default_rp_contract_id || ctx.active_id ||
            (this.props.action.params && this.props.action.params.contract_id) || false;
        this.adapter = null;
        this._licenseKey = null;

        onMounted(async () => {
            await this.loadAndRender();
        });
        onWillUnmount(() => {
            if (this.adapter) this.adapter.destroy();
        });
    }

    _iso(d) {
        if (!d) return false;
        const dd = d instanceof Date ? d : new Date(d);
        const mm = String(dd.getMonth() + 1).padStart(2, "0");
        const day = String(dd.getDate()).padStart(2, "0");
        return `${dd.getFullYear()}-${mm}-${day}`;
    }

    // WBS "1.10.2" → [1,10,2] để sort số tự nhiên
    _wbsKey(w) {
        return String(w || "").split(".").map((s) => {
            const n = parseInt(s, 10);
            return isNaN(n) ? s : n;
        });
    }

    _wbsCompare(a, b) {
        const ka = this._wbsKey(a.wbs_code), kb = this._wbsKey(b.wbs_code);
        const len = Math.max(ka.length, kb.length);
        for (let i = 0; i < len; i++) {
            if (ka[i] === undefined) return -1;
            if (kb[i] === undefined) return 1;
            if (ka[i] !== kb[i]) {
                if (typeof ka[i] === "number" && typeof kb[i] === "number") {
                    return ka[i] - kb[i];
                }
                return String(ka[i]) < String(kb[i]) ? -1 : 1;
            }
        }
        return a.id - b.id;
    }

    async loadAndRender() {
        this.state.loading = true;
        this.state.error = null;
        try {
            await this._loadData();
            if (!this.state.empty) {
                await this._render();
            }
        } catch (err) {
            this.state.error = err.message || String(err);
        }
        this.state.loading = false;
    }

    async _loadData() {
        if (this.contractId) {
            const c = await this.orm.read(
                "rp.contract", [this.contractId], ["name"]);
            this.state.title = (c[0] && c[0].name) || "";
        }
        const domain = this.contractId
            ? [["rp_contract_id", "=", this.contractId]] : [];
        const recs = await this.orm.searchRead(
            "project.task", domain,
            ["name", "wbs_code", "planned_start", "planned_end",
             "progress_percent", "is_milestone", "predecessor_ids",
             "project_id", "user_ids", "baseline_start", "baseline_end"],
            { order: "id asc" }
        );
        this.state.hasBaseline = recs.some((r) => r.baseline_start);
        // Tên người được giao (user_ids là m2m → chỉ trả ids)
        const userIds = [...new Set(recs.flatMap((r) => r.user_ids || []))];
        const userName = new Map();
        if (userIds.length) {
            const users = await this.orm.read(
                "res.users", userIds, ["name"]);
            users.forEach((u) => userName.set(u.id, u.name));
        }
        recs.sort((a, b) => this._wbsCompare(a, b));
        this._recs = recs;
        this.state.count = recs.length;
        this.state.empty = recs.length === 0;

        // map WBS → task id để suy cha ("2.3" → cha là task wbs "2")
        const byWbs = new Map();
        recs.forEach((r) => {
            if (r.wbs_code) byWbs.set(String(r.wbs_code), r.id);
        });
        const idSet = new Set(recs.map((r) => r.id));
        // STT hiển thị kiểu MS Project: đánh 1..n theo thứ tự lịch;
        // nếu dòng đầu là dòng tổng WBS "0" thì nó mang số 0.
        const seqBase =
            recs.length && String(recs[0].wbs_code || "") === "0" ? 0 : 1;
        // map id → STT để cột "Depend on" hiện số STT (kiểu Predecessors
        // của MS Project), không lộ ID database
        const seqById = new Map(recs.map((r, i) => [r.id, i + seqBase]));
        // Đường găng — tính CPM ở backend chỉ khi bật + có HĐ
        let cpMap = {};
        if (this.state.showCriticalPath && this.contractId) {
            try {
                cpMap = await this.orm.call(
                    "project.task", "rp_compute_critical_path",
                    [this.contractId]) || {};
            } catch {
                cpMap = {};
            }
        }
        this._critCount = Object.values(cpMap).filter((v) => v.critical).length;
        this.tasks = recs.map((r, idx) => {
            const cpv = cpMap[r.id];
            const w = String(r.wbs_code || "");
            let parent = null;
            if (w.includes(".")) {
                const pw = w.slice(0, w.lastIndexOf("."));
                if (byWbs.has(pw)) parent = String(byWbs.get(pw));
            }
            const hasDates = !!r.planned_start;
            return {
                id: String(r.id),
                parent,
                name: r.name,
                extraFields: {
                    TaskWbs: w,
                    TaskSeq: idx + seqBase,
                    TaskDeps: (r.predecessor_ids || [])
                        .filter((pid) => idSet.has(pid))
                        .map((pid) => seqById.get(pid))
                        .sort((a, b) => a - b)
                        .join(", "),
                    TaskAssign: (r.user_ids || [])
                        .map((uid) => userName.get(uid))
                        .filter(Boolean)
                        .join(", "),
                    _isTop: !!w && !w.includes("."),
                    // Đường găng (CPM tự tính)
                    _critical: !!(cpv && cpv.critical),
                    _near: !!(cpv && cpv.near),
                    TaskFloat: cpv ? cpv.tf : "",
                },
                start: hasDates ? r.planned_start : null,
                end: hasDates
                    ? (r.planned_end || r.planned_start) : null,
                baselineStart: r.baseline_start || null,
                baselineEnd: r.baseline_end || r.baseline_start || null,
                progress: Math.round(r.progress_percent || 0),
                // taskMode 'Manual': predecessor chỉ VẼ mũi tên, không
                // auto-reschedule → giữ đúng ngày import từ MS Project
                dependencies: (r.predecessor_ids || [])
                    .filter((pid) => idSet.has(pid))
                    .map((pid) => `${pid}FS`).join(","),
                custom_class: r.is_milestone ? "rp-ej2-milestone" : "",
            };
        });
    }

    async _render() {
        // License key — cùng nguồn rp_progress (param syncfusion.license_key)
        if (!this._licenseKey) {
            const resp = await rpc("/rp_progress/syncfusion/license_key", {});
            if (!resp.configured) {
                this.state.error = _t(
                    "Syncfusion license key chưa cấu hình — Settings → "
                    + "Technical → System Parameters → 'syncfusion.license_key'.");
                return;
            }
            this._licenseKey = resp.key;
        }
        if (this.adapter) this.adapter.destroy();
        this.adapter = new BSDSyncfusionGanttAdapter(this.env);
        // Đường găng: tính CPM ở backend (rp_compute_critical_path) rồi tô
        // ĐỎ leaf-task găng + CAM cận-găng qua queryTaskbarInfo. KHÔNG dùng
        // EJ2 enableCriticalPath (không tính được trên WBS lồng + predecessor
        // của ta). Giữ Manual + ngày import gốc.
        await this.adapter.render(this.ganttRef.el, this.tasks, {
            viewMode: this.state.viewMode,
            licenseKey: this._licenseKey,
            rowHeight: 42,
            taskMode: "Manual",
            renderBaseline: this.state.showBaseline,
            baselineColor: "#8a6fb0",
            columns: [
                // TaskID (id database) ẨN nhưng PHẢI có: là primary key
                // của TreeGrid — thiếu nó saveSuccess→setRowData crash
                // (undefined.replace) trước khi bắn actionComplete → mất
                // luôn write onDateChange.
                { field: "TaskID", isPrimaryKey: true, visible: false,
                  width: 1 },
                // STT 0..n theo HĐ (TaskSeq) — không lộ ID database
                { field: "TaskSeq", headerText: "ID", width: 70,
                  textAlign: "Right" },
                { field: "TaskWbs", headerText: "WBS", width: 70 },
                { field: "TaskName", headerText: "Công việc", width: 280 },
                { field: "StartDate", headerText: "Bắt đầu",
                  format: "dd/MM/yyyy", width: 110 },
                { field: "EndDate", headerText: "Kết thúc",
                  format: "dd/MM/yyyy", width: 110 },
                { field: "Progress", headerText: "%", width: 60,
                  textAlign: "Right" },
                // Tổng dự trữ (Total Float) — chỉ hiện khi bật đường găng
                ...(this.state.showCriticalPath ? [{
                    field: "TaskFloat", headerText: "Dự trữ (ngày)",
                    width: 100, textAlign: "Right",
                }] : []),
                // STT các task đứng trước (kiểu Predecessors MS Project)
                { field: "TaskDeps", headerText: "Depend on", width: 100 },
                // Người được giao (assignees Odoo Project — dblclick
                // mở form để phân việc)
                { field: "TaskAssign", headerText: "Phân việc",
                  width: 150 },
            ],
            treeColumnIndex: 3,
            splitterColumnIndex: 9,
            preserveLinks: true,
            // KHÔNG auto-reschedule (giữ ngày import, tránh crash
            // validateTypes khi allowEditing=false + có predecessor).
            autoCalculateDateScheduling: false,
            onBarClick: false,
            // Tô đậm task level 1 (WBS không chấm — giai đoạn lớn)
            onRowDataBound: (args) => {
                const d = args.data || {};
                const top = d._isTop
                    || (d.taskData && d.taskData._isTop);
                if (top && args.row) {
                    args.row.classList.add("rp-ej2-level1");
                }
            },
            onQueryTaskbarInfo: (args) => {
                const d = args.data || {};
                const td = d.taskData || {};
                const top = d._isTop || td._isTop;
                if (top) {
                    args.taskbarBgColor = "#0a3d47";
                    args.progressBarBgColor = "#062a31";
                } else if (this.state.showCriticalPath) {
                    // Tô đường găng (CPM tự tính): đỏ = găng, cam = cận găng
                    if (d._critical || td._critical) {
                        args.taskbarBgColor = "#c0453b";
                        args.progressBarBgColor = "#8e2f27";
                    } else if (d._near || td._near) {
                        args.taskbarBgColor = "#d98b3d";
                        args.progressBarBgColor = "#b06f28";
                    }
                }
            },
            allowAdding: true,
            allowDeleting: true,
            enableContextMenu: true,
            onClick: (task) => this._openTaskForm(parseInt(task.id, 10)),
            onDateChange: (task, start, end) =>
                this._onDateChange(task, start, end),
            onProgressChange: (task, progress) =>
                this._onProgressChange(task, progress),
            onAdd: (data) => this._onAdd(data),
            onDelete: (rows) => this._onDelete(rows),
        });
    }

    _openTaskForm(id) {
        if (!id || isNaN(id)) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "new",
        }, { onClose: () => this.loadAndRender() });
    }

    async _onDateChange(task, start, end) {
        const id = parseInt(task.id, 10);
        if (!id || isNaN(id)) return;
        const s = this._iso(start);
        const e = this._iso(end) || s;
        if (!s) return;
        try {
            // Đổi ngày + dây chuyền dời task phụ thuộc (server-side)
            const changed = await this.orm.call(
                "project.task", "rp_shift_schedule", [[id], s, e]);
            const others = (changed || []).filter((x) => x !== id);
            if (others.length) {
                this.notification.add(
                    _t("Đã lưu — dời theo %s công việc phụ thuộc.",
                       others.length),
                    { type: "success" });
                await this.loadAndRender();   // vẽ lại cả chuỗi bar
            } else {
                this.notification.add(
                    _t("Đã lưu ngày kế hoạch."), { type: "success" });
            }
        } catch {
            this.notification.add(
                _t("Không lưu được thay đổi ngày."), { type: "danger" });
            await this.loadAndRender();   // hoàn tác hiển thị
        }
    }

    async _onProgressChange(task, progress) {
        const id = parseInt(task.id, 10);
        if (!id || isNaN(id)) return;
        try {
            // Ghi % + cuộn % lên các task cha (server-side)
            const changed = await this.orm.call(
                "project.task", "rp_update_progress",
                [[id], Math.round(progress || 0)]);
            this.notification.add(
                _t("Đã cập nhật % hoàn thành."), { type: "success" });
            if ((changed || []).length > 1) {
                await this.loadAndRender();   // % cha cuộn lại
            }
        } catch {
            this.notification.add(
                _t("Không lưu được % hoàn thành."), { type: "danger" });
            await this.loadAndRender();
        }
    }

    // Context menu EJ2 "Add" → tạo record thật trong Odoo rồi reload
    async _onAdd(data) {
        const base = this._recs && this._recs[0];
        try {
            await this.orm.create("project.task", [{
                name: data.TaskName || _t("Công việc mới"),
                rp_contract_id: this.contractId || false,
                project_id: base && base.project_id
                    ? base.project_id[0] : false,
                planned_start: this._iso(data.StartDate) || false,
                planned_end: this._iso(data.EndDate) || false,
            }]);
            this.notification.add(
                _t("Đã thêm công việc."), { type: "success" });
        } catch {
            this.notification.add(
                _t("Không thêm được công việc."), { type: "danger" });
        }
        await this.loadAndRender();
    }

    async _onDelete(rows) {
        const ids = rows.map((r) => parseInt(r.TaskID, 10))
            .filter((i) => i && !isNaN(i));
        if (!ids.length) return;
        try {
            await this.orm.unlink("project.task", ids);
            this.notification.add(
                _t("Đã xoá %s công việc.", ids.length), { type: "success" });
        } catch {
            this.notification.add(
                _t("Không xoá được (kiểm tra quyền/ràng buộc)."),
                { type: "danger" });
        }
        await this.loadAndRender();
    }

    setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.adapter) this.adapter.changeViewMode(mode);
    }

    // Hiện/ẩn baseline (kế hoạch gốc) — vẽ lại Gantt với renderBaseline mới
    async toggleBaseline() {
        this.state.showBaseline = !this.state.showBaseline;
        await this.loadAndRender();
    }

    // Bật/tắt tô đường găng (critical path)
    async toggleCriticalPath() {
        this.state.showCriticalPath = !this.state.showCriticalPath;
        await this.loadAndRender();
    }

    // Chốt baseline = copy lịch kế hoạch hiện hành làm mốc gốc.
    // Re-baseline (đã có baseline) yêu cầu xác nhận — tránh che giấu trượt.
    setBaseline() {
        const doSet = async () => {
            try {
                const n = await this.orm.call(
                    "project.task", "rp_set_baseline", [],
                    { contract_id: this.contractId || false });
                this.notification.add(
                    _t("Đã chốt baseline cho %s công việc.", n),
                    { type: "success" });
                this.state.showBaseline = true;
                await this.loadAndRender();
            } catch {
                this.notification.add(
                    _t("Không chốt được baseline."), { type: "danger" });
            }
        };
        if (this.state.hasBaseline) {
            this.dialog.add(ConfirmationDialog, {
                title: _t("Cập nhật baseline"),
                body: _t(
                    "Baseline hiện tại sẽ bị GHI ĐÈ bằng lịch kế hoạch hiện "
                    + "hành — mọi số đo trượt tiến độ sẽ tính lại từ mốc mới. "
                    + "Re-baseline nên có chủ đích (qua kiểm soát thay đổi). "
                    + "Tiếp tục?"),
                confirmLabel: _t("Chốt lại baseline"),
                confirm: doSet,
                cancel: () => {},
            });
        } else {
            doSet();
        }
    }
}

registry.category("actions").add("rp_schedule.gantt", RpGanttAction);
