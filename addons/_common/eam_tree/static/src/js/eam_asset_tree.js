/** @odoo-module **/

import { Component, onMounted, onWillStart, onWillUnmount, useRef, useState }
    from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadEj2WithLicense } from "@bsd_syncfusion/js/ej2_loader";

// Lưới cây sổ tài sản — Syncfusion EJ2 TreeGrid.
//
// Vì sao không dùng kiểu xem `hierarchy` sẵn có của Odoo: kiểu đó vẽ
// THẺ kiểu sơ đồ tổ chức — thấy hình cây nhưng KHÔNG CÓ CỘT. Sổ tài sản
// thì thứ người ta cần là vừa thấy cây vừa thấy số liệu: sê-ri, loại,
// bảo hành còn mấy ngày, mức trọng yếu — bung ra thu vào ngay trên
// lưới, lọc và sắp xếp theo từng cột. Hai kiểu xem bổ cho nhau, không
// thay nhau, nên `hierarchy` vẫn giữ.

// Khoá ghi nhớ bố cục lưới. CÓ SỐ PHIÊN BẢN, và phải tăng mỗi lần đổi
// danh sách cột.
//
// Đây là cái bẫy của `enablePersistence`: EJ2 ghi cả mảng `columns` vào
// localStorage và khi nạp lại thì bản ghi nhớ ĐÈ bản khai trong mã. Thêm
// một cột mới mà không đổi khoá thì người dùng cũ KHÔNG BAO GIỜ thấy cột
// đó — còn lập trình viên thì thấy, vì máy mình chưa có bản ghi nhớ. Lỗi
// kiểu "chỉ xảy ra ở chỗ khách".
const VER = "v1";
const NEN = "eam_asset_tree_";
const KHOA_NM = "eam_tree.plant";

export class EamAssetTree extends Component {
    static template = "eam_tree.AssetTree";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.gridRef = useRef("grid");
        this.state = useState({
            loading: true,
            count: 0,
            plants: [],
            plantCode: null,
            error: null,
            loc: "",
            dem: { bh_het: 0, bh_sap: 0, bt_qua: 0, bt_tre: 0, wo: 0,
                   chua_lap: 0 },
        });
        this._grid = null;
        this._rows = [];

        onWillStart(async () => {
            // Nhà máy xem lần trước. Người vận hành gần như luôn làm ở
            // một nhà máy; bắt chọn lại mỗi lần mở là phí một cú bấm
            // mỗi ngày. Chỉ áp khi KHÔNG neo vào một tài sản cụ thể.
            if (!this.rootId) {
                try {
                    this.state.plantCode =
                        window.localStorage.getItem(KHOA_NM) || null;
                } catch { }
            }
            await loadEj2WithLicense();
            await this._nap();
        });
        onMounted(() => this._dung());
        onWillUnmount(() => {
            if (this._grid) {
                this._grid.destroy();
                this._grid = null;
            }
        });
    }

    get rootId() {
        const p = this.props.action && this.props.action.params;
        return (p && p.root_id) || null;
    }

    async _nap() {
        this.state.loading = true;
        try {
            const d = await this.orm.call("eam.asset", "treegrid_data", [], {
                plant_code: this.state.plantCode,
                root_id: this.rootId,
            });
            this._rows = d.rows;
            this.state.count = d.count;
            this.state.plants = d.plants;
            if (!this.state.plantCode && d.plant_code) {
                this.state.plantCode = d.plant_code;
            }
            this._dem();
        } finally {
            this.state.loading = false;
        }
    }

    // Đếm sẵn trong OWL thay vì dùng `Aggregate` của EJ2.
    //
    // Chân cột tính tổng của EJ2 cộng theo DÒNG, mà số lệnh công việc
    // treo ở VỊ TRÍ: hai tài sản cùng nằm một chỗ thì cộng lên hai lần.
    // Đếm ở đây thì kiểm soát được, và mỗi con số bấm vào được để lọc
    // ngay — thứ chân cột không làm được.
    _dem() {
        const d = { bh_het: 0, bh_sap: 0, bt_qua: 0, bt_tre: 0, wo: 0,
                    chua_lap: 0 };
        const vt = new Set();
        for (const r of this._rows) {
            const v = r.warranty_days;
            if (v !== null && v !== undefined) {
                if (v < 0) { d.bh_het++; } else if (v <= 90) { d.bh_sap++; }
            }
            if (r.pm_key === "overdue") { d.bt_qua++; }
            if (r.pm_key === "wo_late") { d.bt_tre++; }
            if (!r.is_installed) { d.chua_lap++; }
            // Lệnh đang mở đếm theo VỊ TRÍ, mỗi vị trí một lần.
            if (r.wo_open && r.loc_id && !vt.has(r.loc_id)) {
                vt.add(r.loc_id);
                d.wo += r.wo_open;
            }
        }
        Object.assign(this.state.dem, d);
    }

    _dung() {
        if (!window.ej || !window.ej.treegrid || !this.gridRef.el) {
            this.state.error =
                "Không nạp được thư viện lưới. Kiểm tra bundle " +
                "bsd_syncfusion.assets_syncfusion.";
            return;
        }
        const tg = window.ej.treegrid;
        tg.TreeGrid.Inject(tg.Filter, tg.Sort, tg.Toolbar, tg.ExcelExport,
                           tg.ColumnChooser, tg.Resize, tg.Freeze,
                           tg.Selection, tg.ContextMenu, tg.Reorder);

        // id CỐ ĐỊNH, bắt buộc: EJ2 lấy khoá ghi nhớ từ id của thẻ. Để
        // trống thì nó tự sinh id ngẫu nhiên mỗi lần mở, khoá đổi theo,
        // và `enablePersistence` im lặng không bao giờ có tác dụng.
        this.gridRef.el.id = NEN + VER;
        this._donKhoaCu();

        this._grid = new tg.TreeGrid({
            dataSource: this._rows,
            // Dạng PHẲNG có trỏ cha. Khoá là id SỐ của Odoo — EJ2 mất
            // sạch dòng mà khung vẫn vẽ nếu khoá chứa dấu cách.
            idMapping: "id",
            parentIdMapping: "parent_id",
            treeColumnIndex: 0,
            height: "100%",
            gridLines: "Horizontal",
            allowFiltering: true,
            allowSorting: true,
            allowResizing: true,
            allowReordering: true,
            allowExcelExport: true,
            showColumnChooser: true,
            // Nhớ cột nào hiện, rộng bao nhiêu, xếp thứ tự nào, đang lọc
            // và sắp xếp theo gì. Xem bảng chín trăm dòng mà mỗi lần mở
            // lại phải dựng lại bố cục thì không ai dùng lần thứ hai.
            enablePersistence: true,
            // Đóng băng cột MÃ. Kéo ngang xem sê-ri với bảo hành là cột
            // mã trượt khỏi màn hình, và không còn biết đang đọc dòng
            // nào — ở cây thì mất luôn cả manh mối thuộc máy nào.
            frozenColumns: 1,
            // Mở ra THU SẴN, trừ khi đang neo vào một tài sản. Bung hết
            // chín trăm dòng ngay từ đầu thì phải cuộn mới thấy máy thứ
            // hai; thu lại thì thấy trọn bốn mươi hai máy, bung cái cần.
            // Neo vào một máy thì ngược lại — vào đó là để xem ruột nó.
            enableCollapseAll: !this.rootId,
            // Lọc theo nhánh CHA: gõ "hộp số" thì giữ luôn cây dẫn xuống
            // nó, chứ không bày ra một đống dòng mồ côi không biết thuộc
            // máy nào.
            filterSettings: { type: "Menu", hierarchyMode: "Parent" },
            searchSettings: { hierarchyMode: "Parent" },
            toolbar: ["ExpandAll", "CollapseAll", "ColumnChooser",
                      "ExcelExport", "Search"],
            toolbarClick: (args) => {
                if (args.item.id && args.item.id.endsWith("_excelexport")) {
                    this._grid.excelExport();
                }
            },
            contextMenuItems: this._menuChuotPhai(),
            contextMenuClick: (args) => this._bamMenu(args),
            rowDataBound: (args) => this._toDong(args),
            rowSelected: (args) => {
                const r = args.data || {};
                this.state.loc = r.location || "";
            },
            recordDoubleClick: (args) => this._moBanGhi(args.rowData),
            columns: this._cot(),
        });
        this._grid.appendTo(this.gridRef.el);
    }

    // Xoá bản ghi nhớ của các phiên bản cột CŨ. Không dọn thì mỗi lần
    // đổi danh sách cột lại bỏ một mẩu rác vĩnh viễn trong localStorage
    // của người dùng.
    _donKhoaCu() {
        try {
            const ls = window.localStorage;
            const giu = "treegrid" + NEN + VER;
            const xoa = [];
            for (let i = 0; i < ls.length; i++) {
                const k = ls.key(i);
                if (k && k.startsWith("treegrid" + NEN) && k !== giu) {
                    xoa.push(k);
                }
            }
            xoa.forEach((k) => ls.removeItem(k));
        } catch { }
    }

    _cot() {
        return [
            { field: "code", headerText: "Mã tài sản", width: 240 },
            { field: "name", headerText: "Tên", width: 220 },
            { field: "category", headerText: "Loại cấu phần", width: 170 },
            { field: "serial", headerText: "Sê-ri", width: 150 },
            { field: "location", headerText: "Vị trí đang lắp", width: 230 },
            {
                field: "pm", headerText: "Bảo trì phòng ngừa", width: 160,
                // Màu lấy theo pm_key, KHÔNG dò chữ trong nhãn: nhãn là
                // để người đọc, dò chữ thì đổi câu một cái là mất màu.
                template: (d) => {
                    if (!d.pm) { return "—"; }
                    const c = { overdue: "text-danger fw-bold",
                                wo_late: "text-danger fw-bold",
                                due_soon: "text-warning fw-bold",
                                no_data: "text-muted fst-italic",
                                wo_open: "text-info" }[d.pm_key] || "";
                    return `<span class="${c}">${d.pm}</span>`;
                },
            },
            {
                field: "wo_open", headerText: "Lệnh đang mở", width: 130,
                textAlign: "Right",
                template: (d) => (d.wo_open
                    ? `<span class="badge text-bg-warning">${d.wo_open}</span>`
                    : ""),
            },
            {
                field: "warranty_days", headerText: "Bảo hành còn (ngày)",
                width: 160, textAlign: "Right",
                // Hết hạn tô đỏ, sắp hết tô cam. Con số trần không nói
                // lên gì khi đang nhìn chín trăm dòng.
                template: (d) => {
                    const v = d.warranty_days;
                    if (v === null || v === undefined) { return "—"; }
                    const c = v < 0 ? "text-danger fw-bold"
                        : v <= 90 ? "text-warning fw-bold" : "";
                    return `<span class="${c}">${v}</span>`;
                },
            },
            { field: "criticality", headerText: "Mức quan trọng", width: 140 },
            { field: "state", headerText: "Vòng đời", width: 130 },
            { field: "install_count", headerText: "Số lần lắp", width: 120,
              textAlign: "Right" },
            { field: "plant", headerText: "Nhà máy", width: 190,
              visible: false },
            // Các cột khoá, ẩn, CHỈ để nút lọc nhanh có chỗ bám:
            // `filterByColumn` đòi cột phải được khai, nhưng không đòi
            // nó phải hiện ra. Tất cả là CHUỖI và lọc bằng `equal` —
            // một vị từ, một phép so sánh, không có gì để đoán.
            ...["pm_key", "bh_key", "lap_key", "wo_key", "crit_key",
                "state_key"].map((f) => ({
                    field: f, headerText: f, width: 100,
                    visible: false, showInColumnChooser: false,
                })),
        ];
    }

    _toDong(args) {
        const r = args.data || {};
        const el = args.row;
        if (!el || !el.classList) { return; }
        if (r.state_key === "scrapped") {
            el.classList.add("eam-row-mo");
        }
        if (r.pm_key === "overdue" || r.pm_key === "wo_late") {
            el.classList.add("eam-row-qua");
        }
    }

    // ── Menu chuột phải: biến lưới từ chỗ NGẮM thành chỗ LÀM VIỆC.
    //
    // Câu hỏi thường gặp nhất khi đứng trước một dòng trong sổ tài sản
    // không phải "thông số nó là gì" mà "nó đã xảy ra chuyện gì" — lịch
    // sử lắp đặt, lệnh công việc, lần dừng máy, lịch bảo trì. Trước đó
    // mỗi câu là mở hồ sơ rồi lần qua ba bốn màn hình.
    _menuChuotPhai() {
        return [
            { text: "Mở hồ sơ tài sản", target: ".e-content",
              id: "eam_mo", iconCss: "e-icons e-folder-open" },
            { text: "Lịch sử lắp đặt", target: ".e-content",
              id: "eam_ls", iconCss: "e-icons e-history" },
            { separator: true, target: ".e-content" },
            { text: "Lệnh công việc tại vị trí", target: ".e-content",
              id: "eam_wo" },
            { text: "Lần dừng máy tại vị trí", target: ".e-content",
              id: "eam_og" },
            { text: "Lịch bảo trì tại vị trí", target: ".e-content",
              id: "eam_pm" },
            { separator: true, target: ".e-content" },
            { text: "Chỉ xem nhánh này", target: ".e-content",
              id: "eam_neo" },
            "SortAscending", "SortDescending",
        ];
    }

    _bamMenu(args) {
        const id = args.item && args.item.id;
        const r = (args.rowInfo && args.rowInfo.rowData) || null;
        if (!id || !r) { return; }
        if (id === "eam_mo") { return this._moBanGhi(r); }
        if (id === "eam_ls") {
            return this._moDanhSach(
                "eam.installation", "Lịch sử lắp đặt — " + (r.code || ""),
                [["asset_id", "=", r.id]]);
        }
        if (id === "eam_neo") {
            return this.action.doAction({
                type: "ir.actions.client",
                tag: "eam_tree.asset_tree",
                name: "Lưới cây — " + (r.code || ""),
                params: { root_id: r.id },
            });
        }
        // Ba mục còn lại treo ở VỊ TRÍ, không ở tài sản. Tài sản nằm
        // trong kho thì không có vị trí — nói thẳng ra, đừng mở một danh
        // sách rỗng để người dùng tự đoán vì sao trống.
        if (!r.loc_id) {
            return this.notification.add(
                "“" + (r.code || "") + "” hiện không lắp ở vị trí nào, nên " +
                "chưa có lệnh công việc, lần dừng máy hay lịch bảo trì gắn " +
                "theo vị trí.",
                { type: "warning" });
        }
        const bo = {
            eam_wo: ["eam.work.order", "Lệnh công việc"],
            eam_og: ["eam.outage", "Lần dừng máy"],
            eam_pm: ["eam.pm.schedule", "Lịch bảo trì"],
        }[id];
        if (!bo) { return; }
        // `child_of` chứ không phải `=`: đứng ở dòng tua-bin thì muốn
        // thấy cả việc làm trên hộp số bên trong nó.
        return this._moDanhSach(bo[0], bo[1] + " — " + (r.location || ""),
                                [["location_id", "child_of", r.loc_id]]);
    }

    _moDanhSach(model, ten, domain) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: ten,
            res_model: model,
            domain: domain,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
        });
    }

    _moBanGhi(row) {
        if (!row || !row.id) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "eam.asset",
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ── Lọc nhanh. Bấm vào con số là thấy ngay đúng mấy dòng đó.
    _loc(field, op, val) {
        if (!this._grid) { return; }
        this._grid.clearFiltering();
        this._grid.filterByColumn(field, op, val);
    }

    locBhHet() { this._loc("bh_key", "equal", "het"); }
    locBhSap() { this._loc("bh_key", "equal", "sap"); }
    locBtQua() { this._loc("pm_key", "equal", "overdue"); }
    locBtTre() { this._loc("pm_key", "equal", "wo_late"); }
    locWo() { this._loc("wo_key", "equal", "mo"); }
    locChuaLap() { this._loc("lap_key", "equal", "chua"); }
    locTrongYeu() { this._loc("crit_key", "equal", "critical"); }

    boLoc() {
        if (!this._grid) { return; }
        this._grid.clearFiltering();
        this._grid.searchSettings.key = "";
        this._grid.search("");
    }

    // Trả lưới về bố cục gốc. Cần, vì `enablePersistence` nhớ dai: ẩn
    // mất một cột rồi quên là mình đã ẩn thì không có đường nào ra.
    datLaiLuoi() {
        try {
            window.localStorage.removeItem("treegrid" + NEN + VER);
        } catch { }
        window.location.reload();
    }

    async doiNhaMay(ev) {
        this.state.plantCode = ev.target.value || null;
        try {
            if (this.state.plantCode) {
                window.localStorage.setItem(KHOA_NM, this.state.plantCode);
            } else {
                window.localStorage.removeItem(KHOA_NM);
            }
        } catch { }
        await this._nap();
        if (this._grid) {
            this._grid.dataSource = this._rows;
        }
    }

    bungHet() {
        if (this._grid) { this._grid.expandAll(); }
    }

    thuHet() {
        if (this._grid) { this._grid.collapseAll(); }
    }
}

registry.category("actions").add("eam_tree.asset_tree", EamAssetTree);
