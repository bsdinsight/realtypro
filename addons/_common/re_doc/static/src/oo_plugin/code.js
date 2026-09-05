/**
 * OnlyOffice Plugin Sidecar — Field Picker double-click insert.
 *
 * Chạy inside editor iframe (autostart từ editor config). Expose entry:
 *   window.reDocPluginStart() — gọi từ Asc.plugin.init khi DS load plugin xong
 *
 * IPC với Odoo widget qua postMessage (KHÔNG localStorage vì Chrome
 * partition storage cho nested cross-origin iframe):
 *   - Plugin postMessage hello tới window.top (Odoo main page) → Odoo nhận
 *     được e.source = plugin window reference + lưu lại
 *   - Heartbeat hello mỗi 4s — Odoo update lastSeen timestamp
 *   - Odoo postMessage insert request ngược lại tới plugin window ref →
 *     plugin nhận → Asc.plugin.callCommand insert vào document
 *
 * postMessage bypass partitioned storage vì là direct window-to-window
 * messaging — không phụ thuộc origin storage scope.
 */
(function (window) {
    "use strict";

    var TEMPLATE_ID = window.RE_DOC_TEMPLATE_ID;

    function log() {
        try {
            var args = ["[re-doc-plugin]"].concat([].slice.call(arguments));
            console.log.apply(console, args);
        } catch (e) {}
    }

    /** Insert text vào cursor position trong document via callCommand.
     *
     * Chain logic theo thứ tự:
     *   1. GetRangeBySelect → range.AddText (chèn tại cursor, advance)
     *   2. Last paragraph .AddElement(run) (no selection → append inline cuối doc)
     *   3. Push new paragraph (fallback worst case)
     *
     * Lý do không dùng `InsertContent([run], true)` đơn lẻ: API này expect
     * ARRAY of paragraphs (not runs). Truyền Run vào → silently fail khi
     * không có selection → text "biến mất" mặc dù callCommand trả ok.
     *
     * isCalc=true (3rd param callCommand) → force editor recalc + redraw.
     */
    function insertTextAtCursor(text) {
        if (!window.Asc || !window.Asc.plugin || !window.Asc.plugin.callCommand) {
            log("Asc.plugin.callCommand không có — không insert được:", text);
            return;
        }
        try {
            window.Asc.scope = window.Asc.scope || {};
            window.Asc.scope.reDocInsertText = String(text || "");
            window.Asc.plugin.callCommand(
                function () {
                    var s = Asc.scope.reDocInsertText || "";
                    if (!s) return "empty-text";
                    try {
                        var oDoc = Api.GetDocument();
                        var oRun = Api.CreateRun();
                        oRun.AddText(s);

                        // Try 1: insert tại cursor selection (visible immediate)
                        var oRange = oDoc.GetRangeBySelect();
                        if (oRange && typeof oRange.AddText === "function") {
                            oRange.AddText(s);
                            return "cursor:" + s.length;
                        }

                        // Try 2: append inline run vào last paragraph
                        var nCount = oDoc.GetElementsCount();
                        if (nCount > 0) {
                            var oLast = oDoc.GetElement(nCount - 1);
                            if (oLast && typeof oLast.AddElement === "function") {
                                oLast.AddElement(oRun);
                                return "appended:" + s.length;
                            }
                        }

                        // Try 3: push new paragraph vào cuối doc
                        var oPara = Api.CreateParagraph();
                        oPara.AddText(s);
                        if (typeof oDoc.Push === "function") {
                            oDoc.Push(oPara);
                            return "new_para:" + s.length;
                        }

                        return "NO_API_WORKED";
                    } catch (e) {
                        return "ERR:" + (e && e.message ? e.message : "unknown");
                    }
                },
                false,  // isClose — don't close plugin
                true,   // isCalc — force recalc/redraw sau mutate
                function (result) {
                    console.log("[re-doc-plugin] callCommand result:", result);
                }
            );
            log("Inserted dispatched:", text);
        } catch (e) {
            log("insertTextAtCursor exception:", e);
        }
    }

    /** Post hello tới mọi ancestor window — Odoo top window sẽ nhận và
     * lưu plugin window reference. Broadcast tới top + parent + parent.parent
     * vì nested iframe có thể bị browser sandbox khiến window.top không
     * phải Odoo top thực sự.
     */
    function sendHello() {
        var payload = {
            reDocPluginHello: true,
            template_id: TEMPLATE_ID,
        };
        var targets = [];
        try { if (window.top !== window) targets.push(window.top); } catch (e) {}
        try { if (window.parent !== window) targets.push(window.parent); } catch (e) {}
        try {
            if (window.parent && window.parent.parent && window.parent.parent !== window) {
                targets.push(window.parent.parent);
            }
        } catch (e) {}
        targets.forEach(function (t) {
            try { t.postMessage(payload, "*"); } catch (e) {}
        });
    }

    /** Entry point — gọi từ window.Asc.plugin.init (set ở index.html). */
    window.reDocPluginStart = function () {
        log("started for template_id=" + TEMPLATE_ID);

        // Listen for insert messages từ Odoo widget (e.source = top window)
        window.addEventListener("message", function (e) {
            try {
                var d = e.data;
                if (typeof d === "string" && d.startsWith("{")) {
                    try { d = JSON.parse(d); } catch (pe) {}
                }
                if (!d || typeof d !== "object") return;
                if (!d.reDocInsert) return;
                if (String(d.template_id) !== String(TEMPLATE_ID)) return;
                insertTextAtCursor(d.text);
            } catch (err) {
                log("message handler error:", err);
            }
        });

        // Hello ngay + heartbeat 4s — Odoo dùng để check plugin alive trước insert
        sendHello();
        setInterval(sendHello, 4000);
    };
})(window);
