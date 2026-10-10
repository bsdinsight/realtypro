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

export class EamAssetTree extends Component {
    static template = "eam_tree.AssetTree";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.gridRef = useRef("grid");
        this.state = useState({
            loading: true,
            count: 0,
            plants: [],
            plantCode: null,
            error: null,
        });
        this._grid = null;

        onWillStart(async () => {
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
        } finally {
            this.state.loading = false;
        }
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
                           tg.Selection, tg.ContextMenu);

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
            allowExcelExport: true,
            showColumnChooser: true,
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
            recordDoubleClick: (args) => this._moBanGhi(args.rowData),
            columns: this._cot(),
        });
        this._grid.appendTo(this.gridRef.el);
    }

    _cot() {
        return [
            { field: "code", headerText: "Mã tài sản", width: 230 },
            { field: "name", headerText: "Tên", width: 230 },
            { field: "category", headerText: "Loại cấu phần", width: 170 },
            { field: "serial", headerText: "Sê-ri", width: 150 },
            { field: "location", headerText: "Vị trí đang lắp", width: 230 },
            { field: "criticality", headerText: "Mức quan trọng", width: 140 },
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
            { field: "state", headerText: "Vòng đời", width: 130 },
            { field: "install_count", headerText: "Số lần lắp", width: 120,
              textAlign: "Right" },
            { field: "plant", headerText: "Nhà máy", width: 190,
              visible: false },
        ];
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

    async doiNhaMay(ev) {
        this.state.plantCode = ev.target.value || null;
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
