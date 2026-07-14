/** @odoo-module **/

import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { BSDSyncfusionGanttAdapter } from "./bsd_syncfusion_gantt_adapter";

const COMMUNITY_TASK_CAP = 500;
const ROW_HEIGHT = 46; // bar_height (28) + padding (18) — phải khớp frappe-gantt
const HEADER_HEIGHT = 60; // frappe-gantt header_height (50) + padding/2 (9) ≈ 60

export class BSDGanttView extends Component {
    static template = "rp_progress.BSDGanttView";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.ganttRef = useRef("gantt");
        this.state = useState({
            loading: true,
            error: null,
            licenseError: false,
            noDates: false,
            taskCount: 0,
            viewMode: "Month",
            projectName: "",
        });
        this.adapter = null;
        this._licenseKey = null;

        onMounted(async () => {
            await this._load();
        });
        onWillUnmount(() => {
            if (this.adapter) this.adapter.destroy();
        });
    }

    get projectId() {
        const ctx = this.props.action?.context || {};
        return ctx.default_project_id || ctx.active_id;
    }

    async _load() {
        const projectId = this.projectId;
        if (!projectId) {
            this.state.error = _t("Không có ID dự án trong context.");
            this.state.loading = false;
            return;
        }

        const [project] = await this.orm.read("re.project", [projectId], [
            "name",
        ]);
        this.state.projectName = project?.name || "";

        // Fetch ALL hạng mục (mọi cấp) — không filter level
        const structures = await this.orm.searchRead(
            "rp.structure",
            [["project_id", "=", projectId]],
            [
                "id",
                "name",
                "code",
                "structure_level",
                "subzone_id",
                "parent_id",
                "date_planned_start",
                "date_planned_end",
                "progress_percent",
                "status",
                "is_delayed",
                "sequence",
            ],
            { order: "sequence asc, id asc" },
        );

        this.state.taskCount = structures.length;
        if (structures.length > COMMUNITY_TASK_CAP) {
            this.state.error = _t(
                "Dự án có %s hạng mục — vượt giới hạn Community Edition " +
                    "(%s tasks). Liên hệ sales@bsdinsight.com nâng cấp " +
                    "Realty Pro Enterprise.",
                structures.length,
                COMMUNITY_TASK_CAP,
            );
            this.state.loading = false;
            return;
        }

        // Sắp xếp theo phân cấp: subzone → item → sub_item
        const ordered = this._buildHierarchy(structures);

        // Fetch HĐ nhà thầu của dự án (date_start/end populated)
        // → render dưới mỗi hạng mục mà HĐ cover
        let contracts = [];
        try {
            contracts = await this.orm.searchRead(
                "rp.contract",
                [
                    ["project_id", "=", projectId],
                    ["date_start", "!=", false],
                    ["date_end", "!=", false],
                ],
                [
                    "id", "name", "contractor_id", "structure_ids",
                    "date_start", "date_end", "state",
                    "contract_value_total",
                    "acceptance_progress_percent",
                ],
                { order: "date_start asc, id asc" },
            );
        } catch (err) {
            // rp.contract chưa cài hoặc structure_ids field chưa có
            // → bỏ qua, Gantt chỉ render hạng mục
            contracts = [];
        }
        // Lịch thi công (rp_schedule): lấy CÔNG VIỆC LEVEL 1 (WBS không
        // chấm, bỏ dòng tổng "0") của từng HĐ → tổng dự án chỉ thấy các
        // GIAI ĐOẠN, chi tiết xem ở Gantt của từng HĐ. Ngày level 1 đã
        // được rollup từ con khi import.
        const level1ByContract = new Map();
        if (contracts.length) {
            try {
                const schedTasks = await this.orm.searchRead(
                    "project.task",
                    [["rp_contract_id", "in", contracts.map((c) => c.id)],
                     ["wbs_code", "!=", false]],
                    ["name", "wbs_code", "planned_start", "planned_end",
                     "progress_percent", "rp_contract_id"],
                    { order: "id asc" },
                );
                for (const t of schedTasks) {
                    const w = String(t.wbs_code || "").trim();
                    if (!w || w.includes(".") || w === "0") continue;
                    const cid = t.rp_contract_id && t.rp_contract_id[0];
                    if (!cid) continue;
                    if (!level1ByContract.has(cid)) {
                        level1ByContract.set(cid, []);
                    }
                    level1ByContract.get(cid).push(t);
                }
                level1ByContract.forEach((list) => list.sort((a, b) =>
                    (parseInt(a.wbs_code, 10) || 0)
                    - (parseInt(b.wbs_code, 10) || 0)));
            } catch (err) {
                // rp_schedule chưa cài (field wbs_code/rp_contract_id
                // không tồn tại) → Gantt giữ nguyên 2 lớp cũ
            }
        }
        // Index: structureId → [contracts]
        const contractsByStructure = new Map();
        for (const c of contracts) {
            for (const sid of (c.structure_ids || [])) {
                if (!contractsByStructure.has(sid)) {
                    contractsByStructure.set(sid, []);
                }
                contractsByStructure.get(sid).push(c);
            }
        }
        // Insert contract sau mỗi structure. Track parent_structure_id
        // cho contract row → Syncfusion hierarchy (HĐ là con của hạng mục).
        const orderedWithContracts = [];
        // Counter để contract xuất hiện nhiều lần (cover multi-structure)
        // có ID unique mỗi instance.
        let contractRowSeq = 0;
        // HĐ cover nhiều hạng mục xuất hiện nhiều lần — chỉ gắn giai
        // đoạn dưới instance ĐẦU TIÊN (tránh nhân đôi số dòng).
        const seenContracts = new Set();
        for (const s of ordered) {
            orderedWithContracts.push(s);
            const cs = contractsByStructure.get(s.id) || [];
            for (const c of cs) {
                contractRowSeq++;
                const rowId = `c${c.id}_${contractRowSeq}`;
                orderedWithContracts.push({
                    _isContract: true,
                    _depth: (s._depth || 0) + 1,
                    _parent_structure_id: s.id,
                    _row_seq: contractRowSeq,
                    id: rowId,
                    contract_id: c.id,
                    name: c.contractor_id
                        ? `${c.name} — ${c.contractor_id[1]}`
                        : c.name,
                    code: c.name,
                    date_planned_start: c.date_start,
                    date_planned_end: c.date_end,
                    progress_percent: c.acceptance_progress_percent || 0,
                    status: c.state,
                    is_delayed: false,
                    structure_level: 'contract',
                    _contract_value: c.contract_value_total,
                });
                if (!seenContracts.has(c.id)) {
                    seenContracts.add(c.id);
                    for (const t of (level1ByContract.get(c.id) || [])) {
                        orderedWithContracts.push({
                            _isTask: true,
                            _depth: (s._depth || 0) + 2,
                            _parent_row: rowId,
                            id: `t${t.id}`,
                            name: `${t.wbs_code} · ${t.name}`,
                            code: false,
                            date_planned_start: t.planned_start,
                            date_planned_end:
                                t.planned_end || t.planned_start,
                            progress_percent: t.progress_percent || 0,
                            structure_level: 'task',
                        });
                    }
                }
            }
        }

        // Reference date: earliest valid start. Syncfusion bỏ qua
        // rows không có ngày — chỉ pass rows hasDates.
        const validStarts = orderedWithContracts
            .filter((s) => s.date_planned_start)
            .map((s) => s.date_planned_start)
            .sort();
        const refDate = validStarts[0];

        if (!refDate) {
            this.state.noDates = true;
            this.state.loading = false;
            return;
        }

        // Build tasks cho Syncfusion với hierarchy parentID:
        //   - structure level 'item' (depth 0): parentID = null
        //   - structure level 'sub_item' (depth 1): parentID = parent
        //     structure id (s.parent_id[0])
        //   - contract: parentID = structure id mà HĐ đang insert dưới
        //     (_parent_structure_id) → HĐ thành child của hạng mục
        // GIỮ TẤT CẢ rows kể cả không có ngày — nếu filter sẽ làm
        // children orphan parent → Syncfusion auto-hide. Cho parent
        // không có ngày: Syncfusion tự aggregate từ children.
        const tasks = orderedWithContracts.map((s) => {
            let parentId = null;
            if (s._isTask) {
                parentId = s._parent_row;
            } else if (s._isContract) {
                parentId = String(s._parent_structure_id);
            } else if (s.parent_id && s.parent_id[0]) {
                parentId = String(s.parent_id[0]);
            }
            const hasDates = s.date_planned_start
                && s.date_planned_end;
            return {
                id: s._isContract
                    ? `c${s.contract_id}_${s._row_seq}`
                    : String(s.id),
                // Level gốc TOÀN DỰ ÁN: mọi row chưa có cha treo vào
                // "proot" — EJ2 tự cuộn ngày/% từ toàn bộ cây.
                parent: parentId || "proot",
                name: s.code ? `[${s.code}] ${s.name}` : s.name,
                // Pass null nếu không có ngày — Syncfusion sẽ tự
                // compute từ children (summary task) hoặc render
                // placeholder không bar.
                start: hasDates ? s.date_planned_start : null,
                end: hasDates ? s.date_planned_end : null,
                progress: Math.min(
                    100, Math.max(0, s.progress_percent || 0)),
                dependencies: "",
                custom_class: s._isTask
                    ? "bsd_gantt_bar_schedule"
                    : (s._isContract
                        ? "bsd_gantt_bar_contract"
                        : "bsd_gantt_bar_structure"),
                _isContract: s._isContract,
                _contractId: s.contract_id,
            };
        });
        // Dòng gốc TOÀN DỰ ÁN trên cùng — không ngày (EJ2 tự aggregate
        // min/max từ toàn bộ hạng mục/HĐ/giai đoạn bên dưới).
        tasks.unshift({
            id: "proot",
            parent: null,
            name: this.state.projectName || _t("Toàn dự án"),
            start: null,
            end: null,
            progress: 0,
            dependencies: "",
            custom_class: "bsd_gantt_bar_project",
            _isContract: false,
            _contractId: null,
        });

        // Fetch Syncfusion license key 1 lần / view session
        if (!this._licenseKey) {
            try {
                const resp = await rpc(
                    "/rp_progress/syncfusion/license_key", {});
                if (!resp.configured) {
                    this.state.licenseError = true;
                    this.state.error = _t(
                        "Syncfusion license key chưa được cấu hình. " +
                        "Admin vào Settings → Technical → Parameters → " +
                        "System Parameters → set key 'syncfusion.license_key'.");
                    this.state.loading = false;
                    return;
                }
                this._licenseKey = resp.key;
            } catch (err) {
                this.state.licenseError = true;
                this.state.error = _t(
                    "Lỗi tải license key: ") + (err.message || String(err));
                this.state.loading = false;
                return;
            }
        }

        this.adapter = new BSDSyncfusionGanttAdapter(this.env);
        try {
            await this.adapter.render(this.ganttRef.el, tasks, {
                viewMode: this.state.viewMode,
                licenseKey: this._licenseKey,
                locale: "vi",
                rowHeight: ROW_HEIGHT,
                headerHeight: HEADER_HEIGHT,
                onClick: (task) => this._openRow(task),
                onDateChange: (task, start, end) =>
                    this._onDateChange(task, start, end),
                onProgressChange: (task, progress) =>
                    this._onProgressChange(task, progress),
            });
        } catch (err) {
            this.state.error = err.message || String(err);
        }
        this.state.loading = false;
    }

    /**
     * Retry button handler — clear error, force re-fetch license.
     */
    async retry() {
        this._licenseKey = null;
        this.state.error = null;
        this.state.licenseError = false;
        await this._reload();
    }

    /**
     * Tổ chức flat list → cây phân cấp:
     *   subzone (depth 0) → item (depth 1) → sub_item (depth 2)
     * Trả về flat list đã sắp xếp DFS với property _depth.
     */
    _buildHierarchy(structures) {
        const byId = new Map();
        structures.forEach((s) => byId.set(s.id, { ...s, _children: [] }));

        // Group items theo subzone, sub_items theo parent
        const subzoneItems = new Map(); // subzone_id → [items]
        const orphans = [];

        structures.forEach((s) => {
            const node = byId.get(s.id);
            if (s.structure_level === "sub_item" && s.parent_id) {
                const parent = byId.get(s.parent_id[0]);
                if (parent) {
                    parent._children.push(node);
                    return;
                }
            }
            if (s.structure_level === "item" && s.subzone_id) {
                const k = s.subzone_id[0];
                if (!subzoneItems.has(k)) subzoneItems.set(k, []);
                subzoneItems.get(k).push(node);
                return;
            }
            orphans.push(node);
        });

        // Tạo virtual subzone row chỉ trong panel (nhưng không có dates →
        // không lên gantt). Thay vào đó: items dưới cùng subzone được group
        // bằng cách đánh dấu depth=0 cho item đầu tiên của subzone? Không —
        // đơn giản: items = depth 0, sub_items = depth 1. Subzone hiển thị
        // qua subzone_id name trong tooltip future.
        const result = [];
        for (const [subzoneId, items] of subzoneItems) {
            items.sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
            for (const item of items) {
                item._depth = 0;
                result.push(item);
                item._children.sort((a, b) =>
                    (a.sequence || 0) - (b.sequence || 0));
                for (const child of item._children) {
                    child._depth = 1;
                    result.push(child);
                }
            }
        }
        for (const o of orphans) {
            o._depth = 0;
            result.push(o);
        }
        return result;
    }

    _fmtDate(d) {
        if (!d) return "—";
        const [y, m, day] = d.split("-");
        return `${day}/${m}/${y}`;
    }

    _statusClass(status, isDelayed) {
        if (isDelayed) return "delayed";
        switch (status) {
            case "completed": return "completed";
            case "in_progress": return "in_progress";
            case "paused": return "paused";
            default: return "not_started";
        }
    }

    _contractStatusClass(state) {
        switch (state) {
            case "signed": return "signed";
            case "executing": return "executing";
            case "completed": return "completed";
            case "terminated": return "terminated";
            default: return "draft";
        }
    }

    _openStructure(taskId) {
        const id = parseInt(taskId, 10);
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "rp.structure",
            res_id: id,
            views: [[false, "form"]],
            target: "new",  // dialog modal — đỡ click back
        });
    }

    _openContract(contractId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "rp.contract",
            res_id: contractId,
            views: [[false, "form"]],
            target: "new",  // dialog modal — đỡ click back
        });
    }

    /**
     * Click bar SVG (frappe-gantt): task có _isContract → open contract,
     * else → open structure.
     */
    _openRow(task) {
        if (String(task.id) === "proot") {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "re.project",
                res_id: this.projectId,
                views: [[false, "form"]],
                target: "new",
            });
        } else if (task._isContract) {
            this._openContract(task._contractId);
        } else if (String(task.id).startsWith("t")) {
            // Giai đoạn (project.task level 1) → mở form công việc
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "project.task",
                res_id: parseInt(String(task.id).slice(1), 10),
                views: [[false, "form"]],
                target: "new",
            });
        } else {
            this._openStructure(task.id);
        }
    }

    async _onDateChange(task, start, end) {
        const isoStart = start.toISOString().slice(0, 10);
        const isoEnd = end.toISOString().slice(0, 10);
        if (String(task.id) === "proot"
            || String(task.id).startsWith("t")) {
            // Toàn dự án / giai đoạn = ngày cuộn từ cấp dưới — không
            // sửa ở đây
            this.notification.add(
                _t("Ngày dòng này cuộn từ cấp chi tiết — sửa trong "
                   + "Gantt của HĐ nhà thầu."),
                { type: "warning" });
            await this._reload();
            return;
        }
        try {
            if (task._isContract) {
                await this.orm.write("rp.contract",
                    [task._contractId],
                    {
                        date_start: isoStart,
                        date_end: isoEnd,
                    });
                this.notification.add(
                    _t("Đã cập nhật ngày HĐ."),
                    { type: "success" },
                );
            } else {
                await this.orm.write("rp.structure",
                    [parseInt(task.id, 10)],
                    {
                        date_planned_start: isoStart,
                        date_planned_end: isoEnd,
                    });
                this.notification.add(
                    _t("Đã cập nhật ngày kế hoạch."),
                    { type: "success" },
                );
            }
            // KHÔNG reload — Syncfusion đã update UI bar position
            // ngay khi drag/resize. Backend save chỉ persist data, UI
            // không cần rebuild.
        } catch (err) {
            // Chỉ reload khi LỖI để rollback bar về vị trí cũ
            // (data backend không thay đổi).
            this.notification.add(_t("Lỗi cập nhật: ") + err.message, {
                type: "danger",
            });
            await this._reload();
        }
    }

    async _onProgressChange(task, progress) {
        this.notification.add(
            _t(
                "% tiến độ được tính từ BBNT — không sửa tay trên Gantt. " +
                    "Sửa qua BBNT của hạng mục.",
            ),
            { type: "warning" },
        );
        await this._reload();
    }

    async _reload() {
        if (this.adapter) {
            this.adapter.destroy();
            this.adapter = null;
        }
        this.state.loading = true;
        this.state.error = null;
        this.state.noDates = false;
        await this._load();
    }

    async setViewMode(mode) {
        this.state.viewMode = mode;
        if (this.adapter) {
            this.adapter.changeViewMode(mode);
        }
    }
}

registry.category("actions").add("bsd_gantt_view", BSDGanttView);
