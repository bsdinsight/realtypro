/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { RpGanttAction } from "@rp_schedule/js/rp_gantt";

// Nhúng Gantt lịch thi công vào tab trên form hợp đồng.
//
// Gantt của Syncfusion ĐÃ LÀ TreeGrid bên trái + biểu đồ bên phải, kéo
// thanh chia là thu gọn phần biểu đồ — nên thu/bung theo nhánh đã có
// sẵn ở đó. Dựng thêm một TreeGrid riêng chỉ để có cái cây là đẻ ra bộ
// thứ hai phải nuôi song song: hai nơi đọc dữ liệu, hai cách tô đường
// găng, hai chỗ phải sửa mỗi lần đổi cột.
//
// Lớp này KHÔNG vẽ gì — nó chỉ dựng lại cái prop `action` mà
// `RpGanttAction` vốn nhận khi mở bằng ir.actions.client, rồi giao việc
// cho chính component đó. Mọi thứ đi kèm (baseline, đường găng, zoom,
// nhãn mốc) theo luôn, miễn phí.
export class RpGanttEmbed extends Component {
    static template = "rp_schedule.RpGanttEmbed";
    static components = { RpGanttAction };
    static props = ["*"];

    get resId() {
        return this.props.record && this.props.record.resId;
    }

    // Hình dạng y như ctx mà `action_open_gantt` trả về, để
    // RpGanttAction không phải biết nó đang nằm trong form hay trong
    // action riêng.
    get ganttAction() {
        return {
            context: {
                default_rp_contract_id: this.resId,
                active_id: this.resId,
            },
            params: {},
        };
    }
}

registry.category("fields").add("rp_gantt_embed", {
    component: RpGanttEmbed,
    supportedTypes: ["one2many"],
});
