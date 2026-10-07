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
            showBaseline: true,
            showCriticalPath: true,
            hasBaseline: false,
            isProject: false,
            critCount: 0,
            worstFloat: 0,
            // Dải số liệu cố định của màn mốc (xem rp_milestone_brief)
            brief: null,
        });
        const ctx = (this.props.action && this.props.action.context) || {};
        const params = this.props.action.params || {};
        // Hai chế độ: lịch của MỘT hợp đồng (như trước), hoặc lịch TOÀN
        // DỰ ÁN gom mọi hợp đồng. Chế độ dự án mở từ nút trên form dự án
        // và truyền rp_project_id; lúc đó active_id là id dự án nên phải
        // đọc project TRƯỚC, không thì nó bị hiểu nhầm thành id hợp đồng.
        this.projectId = ctx.rp_project_id || params.project_id || false;
        // Chế độ "mốc": chỉ lấy công việc được đánh dấu là mốc, và xếp
        // hàng theo Dự án → Gói thầu → Hợp đồng thay vì theo cây WBS.
        // Mốc là ĐIỂM thời gian; đọc chúng trên một trục chung thì thấy
        // ngay cái nào đã trễ và cái nào dồn cục, điều mà danh sách bắt
        // người đọc tự sắp trong đầu.
        this.mode = params.mode || ctx.rp_gantt_mode || "full";
        this.contractId = this.projectId
            ? false
            : (ctx.default_rp_contract_id || ctx.active_id ||
               params.contract_id || false);
        this.state.isProject = !!this.projectId;
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
        } else if (this.projectId) {
            const p = await this.orm.read(
                "re.project", [this.projectId],
                ["display_name", "schedule_contract_count"]);
            this.state.title = p[0]
                ? _t("%s — tiến độ toàn dự án (%s hợp đồng)",
                     p[0].display_name, p[0].schedule_contract_count || 0)
                : "";
        }
        const domain = this.contractId
            ? [["rp_contract_id", "=", this.contractId]]
            : (this.projectId ? [["rp_project_id", "=", this.projectId]] : []);
        if (this.mode === "milestone") {
            domain.push(["is_milestone", "=", true]);
        }
        const recs = await this.orm.searchRead(
            "project.task", domain,
            ["name", "wbs_code", "wbs_seq", "planned_start", "planned_end",
             "progress_percent", "is_milestone",
             "project_id", "user_ids", "baseline_start", "baseline_end",
             "baseline_slip_days", "rp_contract_id", "rp_project_id",
             "exec_status"],
            { order: "id asc" }
        );
        this.state.hasBaseline = recs.some((r) => r.baseline_start);
        // Dự án HIỆU LỰC của màn hình. Mở từ nút trên form dự án thì đã
        // có sẵn; mở từ menu thì suy ra từ chính các việc đang xem, và
        // chỉ nhận khi cả màn hình thuộc đúng MỘT dự án — hai dự án thì
        // mốc vạch dọc lẫn đường găng đều không còn nghĩa.
        if (this.projectId) {
            this._pid = this.projectId;
        } else {
            const pids = [...new Set(
                recs.map((r) => r.rp_project_id && r.rp_project_id[0])
                    .filter(Boolean))];
            this._pid = pids.length === 1 ? pids[0] : false;
        }
        // Mốc vạch dọc (ngày phải xong, hôm nay, đóng điện…). Ở chế độ
        // hợp đồng vẫn lấy mốc của dự án chứa hợp đồng — nhà thầu cần
        // thấy mình đang chạy đua với mốc nào. Nạp SAU khi có việc để
        // màn mở từ menu (không mang id dự án) còn suy ra được dự án.
        await this._loadMarkers();
        // Dải số liệu cố định — chỉ màn mốc. Gọi luôn CPM bên trong nên
        // bên dưới khỏi gọi lại lần hai.
        if (this.mode === "milestone" && this._pid) {
            try {
                this.state.brief = await this.orm.call(
                    "re.project", "rp_milestone_brief", [this._pid]);
            } catch {
                this.state.brief = null;
            }
            const b = this.state.brief;
            if (b) {
                this.state.title = b.project || this.state.title;
                this.state.critCount = b.gang || 0;
                this.state.worstFloat = b.du_dia || 0;
            }
        }
        // Tên người được giao (user_ids là m2m → chỉ trả ids)
        const userIds = [...new Set(recs.flatMap((r) => r.user_ids || []))];
        const userName = new Map();
        if (userIds.length) {
            const users = await this.orm.read(
                "res.users", userIds, ["name"]);
            users.forEach((u) => userName.set(u.id, u.name));
        }
        // Gói thầu + hợp đồng của từng việc. Đọc BẤT KỂ chế độ xem: màn
        // "Mốc chính" mở từ menu nên không mang theo id dự án, mà nó vẫn
        // phải xếp mốc theo gói thầu. Trước đây khối này nằm trong nhánh
        // `if (this.projectId)` nên mở từ menu là mọi mốc đều rơi vào
        // "chưa gắn gói thầu".
        const cids = [...new Set(
            recs.map((r) => r.rp_contract_id && r.rp_contract_id[0])
                .filter(Boolean))];
        const contracts = cids.length ? await this.orm.read(
            "rp.contract", cids,
            ["display_name", "tender_package_id"]) : [];
        this._contractInfo = new Map();
        const pkgOrder = new Map();
        contracts.forEach((c) => {
            const pkg = c.tender_package_id
                ? c.tender_package_id[1] : "";
            if (!pkgOrder.has(pkg)) pkgOrder.set(pkg, pkgOrder.size);
            this._contractInfo.set(c.id, {
                name: c.display_name || "",
                pkg,
                // Số thứ tự gói — dùng làm KHOÁ dòng làn, xem ghi chú
                // trong _milestoneRows (khoá không được chứa dấu cách).
                pkgKey: pkgOrder.get(pkg),
                rank: [pkgOrder.get(pkg), c.id],
            });
        });
        if (this.projectId) {
            // Mã WBS được đánh theo từng GÓI THẦU, nên hai gói khác nhau
            // đều có "1", "2"… Xếp thuần theo WBS thì ba gói cài răng
            // lược vào nhau, không ai đọc được. Gom theo hợp đồng trước
            // (thứ tự: gói thầu rồi hợp đồng), trong mỗi hợp đồng mới
            // xếp theo WBS.
            const rank = (r) => {
                const info = r.rp_contract_id
                    && this._contractInfo.get(r.rp_contract_id[0]);
                return info ? info.rank : [9999, 0];
            };
            recs.sort((a, b) => {
                const ra = rank(a), rb = rank(b);
                return (ra[0] - rb[0]) || (ra[1] - rb[1])
                    || this._wbsCompare(a, b);
            });
        } else {
                recs.sort((a, b) => this._wbsCompare(a, b));
        }
        // Mức phóng mặc định theo ĐỘ DÀI lịch: xem 18 tháng ở mức Tuần
        // thì trục thời gian phải vẽ hơn 500 ô ngày cho mỗi dòng — trình
        // duyệt treo hàng chục giây mà người xem cũng chẳng đọc được gì.
        // Người dùng tự bấm đổi mức thì tôn trọng lựa chọn đó.
        if (!this._viewModeTouched) {
            const ds = recs.map((r) => r.planned_start).filter(Boolean);
            const de = recs.map((r) => r.planned_end).filter(Boolean);
            if (ds.length && de.length) {
                const span = (new Date(de.sort().at(-1))
                    - new Date(ds.sort()[0])) / 86400000;
                this.state.viewMode = span > 180
                    ? "Month" : (span > 60 ? "Week" : "Day");
            }
        }
        this._recs = recs;
        this.state.count = recs.length;
        this.state.empty = recs.length === 0;

        // map WBS → task id để suy cha ("2.3" → cha là task wbs "2")
        // Khoá theo HỢP ĐỒNG, không chỉ theo mã WBS: ở lịch dự án hai
        // gói thầu đều có "1" nên khoá thuần WBS sẽ nối con của gói này
        // vào cha của gói kia.
        const ckey = (r) => (r.rp_contract_id ? r.rp_contract_id[0] : 0);
        const byWbs = new Map();
        const byWbsAny = new Map();
        recs.forEach((r) => {
            if (r.wbs_code) {
                byWbs.set(`${ckey(r)}|${r.wbs_code}`, r.id);
                byWbsAny.set(r.wbs_code, r.id);
            }
        });
        // Dòng nào THỰC SỰ là dòng tổng: có việc con treo dưới nó.
        // Chỉ dựa vào "mã không có dấu chấm" thì một lịch phẳng (mọi mã
        // đều 1, 2, 3) sẽ bị tô đậm toàn bộ như thể dòng nào cũng là
        // giai đoạn lớn.
        const hasChild = new Set();
        recs.forEach((r) => {
            const w = String(r.wbs_code || "");
            if (w.includes(".")) {
                hasChild.add(`${ckey(r)}|${w.slice(0, w.lastIndexOf("."))}`);
            }
        });
        const idSet = new Set(recs.map((r) => r.id));
        // STT hiển thị kiểu MS Project: đánh 1..n theo thứ tự lịch;
        // nếu dòng đầu là dòng tổng WBS "0" thì nó mang số 0.
        const seqBase =
            recs.length && String(recs[0].wbs_code || "") === "0" ? 0 : 1;
        // STT lấy từ máy chủ (wbs_seq) để Gantt, danh sách và bản xuất
        // Excel nói CÙNG một con số. Lịch chưa đánh số thì tạm dùng thứ
        // tự nạp, nhưng lúc đó hai màn hình có thể lệch nhau — bấm
        // "Đánh số lại công việc" trên dự án là hết.
        const stt = (r, i) => r.wbs_seq || i + seqBase;
        const seqById = new Map(recs.map((r, i) => [r.id, stt(r, i)]));
        // Quan hệ trước-sau: đọc riêng từ rp.task.link vì mỗi quan hệ có
        // LOẠI (FS/SS/FF/SF) và ĐỘ LỆCH — hai thứ m2m phẳng không chở
        // được. Lịch fast-track sống bằng SS+lag, vẽ hết thành FS là vẽ
        // sai mũi tên.
        const linkRecs = recs.length
            ? await this.orm.searchRead(
                "rp.task.link",
                [["task_id", "in", [...idSet]],
                 ["predecessor_id", "in", [...idSet]]],
                ["task_id", "predecessor_id", "link_type", "lag_days"])
            : [];
        const lagTag = (n) => (n > 0 ? `+${n}` : (n < 0 ? String(n) : ""));
        const linksByTask = new Map();
        for (const l of linkRecs) {
            const tid = l.task_id[0];
            const pid = l.predecessor_id[0];
            if (!linksByTask.has(tid)) {
                linksByTask.set(tid, []);
            }
            linksByTask.get(tid).push({
                pid,
                type: l.link_type || "FS",
                lag: l.lag_days || 0,
            });
        }
        // Đường găng — tính CPM ở backend chỉ khi bật + có HĐ
        let cpMap = {};
        if (this.state.showCriticalPath && this.mode !== "milestone"
                && (this.contractId || this._pid)) {
            try {
                cpMap = await this.orm.call(
                    "project.task",
                    this._pid
                        ? "rp_compute_project_critical_path"
                        : "rp_compute_critical_path",
                    [this._pid || this.contractId]) || {};
            } catch {
                cpMap = {};
            }
        }
        const cpVals = Object.values(cpMap);
        this._critCount = cpVals.filter((v) => v.critical).length;
        this.state.critCount = this._critCount;
        this.state.worstFloat = cpVals.length
            ? Math.min(...cpVals.map((v) => v.tf)) : 0;
        this.tasks = recs.map((r, idx) => {
            const cpv = cpMap[r.id];
            const w = String(r.wbs_code || "");
            let parent = null;
            if (w.includes(".")) {
                const up = w.slice(0, w.lastIndexOf("."));
                // Mã WBS đánh chung toàn dự án thì cha có thể nằm ở hợp
                // đồng khác — tra trong hợp đồng trước, trượt thì tra
                // toàn dự án, nếu không cây Gantt gãy mất một tầng.
                const pw = `${ckey(r)}|${up}`;
                if (byWbs.has(pw)) {
                    parent = String(byWbs.get(pw));
                } else if (byWbsAny.has(up)) {
                    parent = String(byWbsAny.get(up));
                }
            }
            const hasDates = !!r.planned_start;
            return {
                id: String(r.id),
                parent,
                name: r.name,
                extraFields: {
                    TaskWbs: w,
                    TaskSeq: stt(r, idx),
                    // Cột "Depend on" kiểu MS Project: STT + loại + lệch,
                    // ví dụ "12SS+20". FS lệch 0 để trần cho gọn mắt.
                    TaskDeps: (linksByTask.get(r.id) || [])
                        .map((l) => ({ s: seqById.get(l.pid), l }))
                        .filter((x) => x.s !== undefined)
                        .sort((a, b) => a.s - b.s)
                        .map(({ s, l }) => (l.type === "FS" && !l.lag
                            ? String(s)
                            : `${s}${l.type}${lagTag(l.lag)}`))
                        .join(", "),
                    TaskAssign: (r.user_ids || [])
                        .map((uid) => userName.get(uid))
                        .filter(Boolean)
                        .join(", "),
                    _isTop: !!w && !w.includes(".")
                        && hasChild.has(`${ckey(r)}|${w}`),
                    TaskContract: (this._contractInfo
                        && this._contractInfo.get(ckey(r))
                        && this._contractInfo.get(ckey(r)).name) || "",
                    TaskPackage: (this._contractInfo
                        && this._contractInfo.get(ckey(r))
                        && this._contractInfo.get(ckey(r)).pkg) || "",
                    // Đường găng (CPM tự tính)
                    _critical: !!(cpv && cpv.critical),
                    _near: !!(cpv && cpv.near),
                    TaskFloat: cpv ? cpv.tf : "",
                    TaskSlip: r.baseline_slip_days || "",
                    // Trạng thái thực hiện — màn mốc tô hình thoi theo
                    // đây, để nhìn phát biết mốc nào đã trễ.
                    _status: r.exec_status || "",
                },
                start: hasDates ? r.planned_start : null,
                end: hasDates
                    ? (r.planned_end || r.planned_start) : null,
                baselineStart: r.baseline_start || null,
                baselineEnd: r.baseline_end || r.baseline_start || null,
                progress: Math.round(r.progress_percent || 0),
                // taskMode 'Manual': predecessor chỉ VẼ mũi tên, không
                // auto-reschedule → giữ đúng ngày import từ MS Project
                dependencies: (linksByTask.get(r.id) || [])
                    .map((l) => `${l.pid}${l.type}${lagTag(l.lag)}`)
                    .join(","),
                custom_class: r.is_milestone ? "rp-ej2-milestone" : "",
            };
        });
        if (this.mode === "milestone") {
            this.tasks = this._milestoneRows(recs, this.tasks);
        }
    }

    /**
     * Xếp mốc thành ba làn trên CÙNG một trục thời gian:
     * Dự án → Gói thầu → Hợp đồng → mốc.
     *
     * Dòng cha là dòng tổng hợp, không phải việc thật, nên id dùng tiền
     * tố chữ (P/K/H) để không đụng id của project.task. Ngày của dòng cha
     * trải từ mốc sớm nhất tới mốc muộn nhất của nhánh — nhờ vậy nhìn
     * một dòng gói thầu là biết gói đó kéo dài từ đâu tới đâu.
     *
     * KHOÁ DÒNG CHỈ ĐƯỢC CHỨA CHỮ-SỐ. EJ2 nối thẳng id vào tên class của
     * thẻ <tr> ("gridrowtaskId<id>level2") rồi gọi classList.add, nên một
     * dấu cách trong id ném InvalidCharacterError ngay giữa renderChartRows:
     * trục thời gian đã vẽ xong vẫn còn đó, còn TOÀN BỘ hàng thì không
     * hàng nào được vẽ — màn hình trống trơn không kèm thông báo lỗi.
     * Vì vậy làn gói thầu khoá theo SỐ THỨ TỰ gói (pkgKey), không phải
     * theo tên gói. (Cùng một cái bẫy với cssClass của mốc vạch dọc ở
     * _loadMarkers.)
     */
    _milestoneRows(recs, mapped) {
        const byId = new Map(mapped.map((t) => [t.id, t]));
        const lanes = new Map();   // key → row
        const rows = [];
        const touch = (key, name, parentKey, rank, tier) => {
            if (!lanes.has(key)) {
                const row = {
                    id: key, parent: parentKey, name,
                    extraFields: { TaskWbs: "", TaskSeq: "", TaskDeps: "",
                                   TaskAssign: "", _isTop: !parentKey,
                                   TaskContract: "", TaskPackage: "",
                                   TaskFloat: "", TaskSlip: "" },
                    start: null, end: null, progress: 0,
                    dependencies: "", custom_class: "rp-ej2-lane",
                    _rank: rank, _tier: tier,
                };
                lanes.set(key, row);
                rows.push(row);
            }
            return lanes.get(key);
        };
        const stretch = (row, d) => {
            if (!d) return;
            if (!row.start || d < row.start) row.start = d;
            if (!row.end || d > row.end) row.end = d;
        };

        recs.forEach((r) => {
            const t = byId.get(String(r.id));
            if (!t) return;
            const cid = r.rp_contract_id ? r.rp_contract_id[0] : 0;
            const info = this._contractInfo && this._contractInfo.get(cid);
            const pkg = (info && info.pkg) || "Chưa gắn gói thầu";
            // Làn trên cùng theo DỰ ÁN thật, không theo tiêu đề màn hình:
            // mở từ menu thì tiêu đề rỗng, mà danh sách mốc vẫn có thể
            // trải trên nhiều dự án.
            const pid = r.rp_project_id ? r.rp_project_id[0] : 0;
            const pName = (r.rp_project_id && r.rp_project_id[1])
                || this.state.title || "Chưa gắn dự án";
            const pKey = "P" + pid;
            const kKey = "P" + pid + "K"
                + (info ? info.pkgKey : "x");
            const hKey = "H" + cid;
            const du_an = touch(pKey, pName, null, [pid], 0);
            const goi = touch(kKey, pkg, pKey,
                              (info && info.rank) || [9999, 0], 1);
            const hd = touch(hKey, (info && info.name) || "Chưa gắn hợp đồng",
                             kKey, (info && info.rank) || [9999, 0], 2);
            t.parent = hKey;
            t.extraFields._isTop = false;
            // Mốc là ĐIỂM: thời lượng 0 thì EJ2 vẽ hình thoi theo đúng
            // định nghĩa mốc của nó. Để trống, EJ2 suy ra 1 ngày và vẽ
            // thành thanh mảnh — nhìn không ra mốc.
            t.duration = 0;
            [du_an, goi, hd].forEach((l) => {
                stretch(l, t.start);
                stretch(l, t.end);
            });
            rows.push(t);
        });
        // Dòng làn mang thời lượng bằng chính bề rộng nhánh — nếu bỏ
        // trống, EJ2 (đang bật taskFields.duration) hiểu là 0 và biến
        // dòng tổng thành một cái mốc.
        const ngay = (a, b) => Math.max(1, Math.round(
            (new Date(b) - new Date(a)) / 86400000) + 1);
        lanes.forEach((l) => {
            l.duration = (l.start && l.end) ? ngay(l.start, l.end) : 1;
        });
        // Giữ thứ tự: dự án → gói (theo rank) → hợp đồng → mốc theo ngày.
        // Bậc khai tường minh khi dựng dòng, KHÔNG suy từ chữ đầu của
        // khoá: khoá gói nay là "P18K0" nên cũng bắt đầu bằng "P".
        return rows.sort((a, b) => {
            const ta = a._tier === undefined ? 3 : a._tier;
            const tb = b._tier === undefined ? 3 : b._tier;
            const ka = a._rank || [9998, 0], kb = b._rank || [9998, 0];
            return (ta - tb) || (ka[0] - kb[0])
                || String(a.start || "").localeCompare(String(b.start || ""));
        });
    }

    async _loadMarkers() {
        this._markers = [];
        let pid = this.projectId;
        if (!pid && this.contractId) {
            const c = await this.orm.read(
                "rp.contract", [this.contractId], ["project_id"]);
            pid = c[0] && c[0].project_id && c[0].project_id[0];
        }
        if (!pid) {
            // Màn mở từ menu không mang id dự án — dùng dự án hiệu lực
            // suy từ chính các việc đang xem (xem _loadData).
            pid = this._pid;
        }
        if (!pid) {
            return;
        }
        let marks = [];
        try {
            marks = await this.orm.call(
                "re.project", "rp_schedule_markers", [pid]) || [];
        } catch {
            marks = [];
        }
        // cssClass phải là MỘT lớp duy nhất, không khoảng trắng: EJ2 gọi
        // classList.add(cssClass) nên chuỗi hai lớp ném InvalidCharacterError
        // ngay giữa lúc vẽ mốc — chuỗi vẽ đứt ở đó, hideSpinner() không
        // bao giờ chạy, và lớp spinner phủ kín Gantt nuốt mọi cú bấm.
        // KHÔNG truyền `top`. Tài liệu Syncfusion có thuộc tính đó để so
        // le nhãn, nhưng bản EJ2 đang đóng gói ở đây lặng lẽ BỎ HẲN vạch
        // nào mang `top` — đo trên trang thử: 6 vạch, chỉ vạch duy nhất
        // không có `top` được vẽ. Chống nhãn chồng nhau bằng cách đặt
        // nhãn ngắn (xem _rp_schedule_markers) thay vì xếp tầng.
        this._markers = marks.map((m) => ({
            day: new Date(m.date + "T00:00:00"),
            label: m.label,
            cssClass: "rp-marker-"
                + String(m.kind || "other").replace(/[^a-z0-9-]/gi, ""),
        }));
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
        // Màn "Mốc chính" là chỗ các trưởng bộ phận ngồi họp tiến độ: cái
        // họ nhìn là TRỤC THỜI GIAN — mốc nào đã trễ, mốc nào dồn cục,
        // còn bao lâu tới mốc sau. Bảng bên trái chỉ cần đủ gọi tên mốc,
        // nên cắt còn Mốc + Ngày và đẩy con trượt sát trái, nhường gần
        // hết bề ngang cho biểu đồ. Lịch đầy đủ thì ngược lại, vẫn cần
        // đủ cột để tra cứu.
        const chiMoc = this.mode === "milestone";
        await this.adapter.render(this.ganttRef.el, this.tasks, {
            viewMode: this.state.viewMode,
            licenseKey: this._licenseKey,
            rowHeight: chiMoc ? 34 : 42,
            // Mốc: để EJ2 tự nhận ra việc thời lượng 0 và vẽ hình thoi.
            useDuration: chiMoc,
            // Đường nối trước-sau mảnh 1px — lịch 142 quan hệ mà vẽ dày
            // thì mạng dây lấn hết thanh việc.
            connectorLineWidth: 1,
            taskMode: "Manual",
            renderBaseline: this.state.showBaseline,
            baselineColor: "#8a6fb0",
            eventMarkers: this._markers,
            columns: chiMoc ? [
                { field: "TaskID", isPrimaryKey: true, visible: false,
                  width: 1 },
                { field: "TaskName", headerText: "Mốc", width: 250 },
                { field: "EndDate", headerText: "Ngày",
                  format: "dd/MM/yy", width: 84, textAlign: "Right" },
            ] : [
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
                // Lịch dự án trộn việc của nhiều hợp đồng → phải thấy
                // việc này của gói nào, nhà thầu nào.
                ...(this.projectId ? [
                    { field: "TaskPackage", headerText: "Gói thầu",
                      width: 150 },
                    { field: "TaskContract", headerText: "Hợp đồng",
                      width: 200 },
                ] : []),
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
                // Trượt so kế hoạch gốc — chỉ có nghĩa khi đang xem
                // baseline bên cạnh.
                ...(this.state.showBaseline && this.state.hasBaseline ? [{
                    field: "TaskSlip", headerText: "Trễ so gốc",
                    width: 100, textAlign: "Right",
                }] : []),
                // STT các task đứng trước (kiểu Predecessors MS Project)
                { field: "TaskDeps", headerText: "Depend on", width: 100 },
                // Người được giao (assignees Odoo Project — dblclick
                // mở form để phân việc)
                { field: "TaskAssign", headerText: "Phân việc",
                  width: 150 },
            ],
            treeColumnIndex: chiMoc ? 1 : 3,
            splitterColumnIndex: chiMoc ? 2
                : (this.projectId ? 11 : 9)
                + (this.state.showBaseline && this.state.hasBaseline ? 1 : 0),
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
                // Màn mốc: tô hình thoi theo TÌNH TRẠNG, vì cuộc họp
                // tiến độ chỉ hỏi đúng một câu — mốc nào trễ. Đỏ = trễ,
                // xanh = đã xong, hổ phách = chưa tới.
                if (chiMoc) {
                    const st = d._status || td._status || "";
                    args.milestoneColor = st === "late" ? "#c0453b"
                        : (st === "done" ? "#2e8b57"
                           : (st === "in_progress" ? "#0E8C99" : "#e0a460"));
                    return;
                }
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
            // Lịch lớn mở bung hết thì vừa chậm vừa không đọc được:
            // gấp lại, người xem tự mở nhánh cần xem (hoặc Expand all).
            collapseAllParentTasks: this.tasks.length > 150,
            enableVirtualization: this.tasks.length > 150,
            allowAdding: true,
            allowDeleting: true,
            enableContextMenu: true,
            // KHÔNG đưa "TaskInformation" vào: hộp thoại đó sửa bản sao
            // trong bộ nhớ của EJ2 rồi im lặng vứt đi — Odoo không nhận
            // gì cả, người dùng tưởng đã lưu. Sửa chi tiết thì double
            // click để mở form Odoo thật.
            contextMenuItems: ["AutoFit", "Add", "DeleteTask"],
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
        if (this.projectId) {
            // Lịch dự án gom việc của NHIỀU hợp đồng; thêm việc ở đây thì
            // không biết gắn vào hợp đồng nào, mà việc không có hợp đồng
            // sẽ biến mất khỏi chính màn này. Thêm việc làm ở lịch của
            // từng hợp đồng.
            this.notification.add(
                _t("Thêm công việc ở lịch của từng hợp đồng, không thêm "
                   + "ở lịch tổng dự án."), { type: "warning" });
            await this.loadAndRender();
            return;
        }
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
        this._viewModeTouched = true;
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
                    this.projectId
                        ? { project_id: this.projectId }
                        : { contract_id: this.contractId || false });
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
