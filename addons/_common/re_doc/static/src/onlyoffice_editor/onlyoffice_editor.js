/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

/**
 * OnlyOffice Document Editor field widget.
 *
 * Replaces default Binary upload widget on re.doc.template.docx_file —
 * embeds true Word UI iframe (header/footer/page numbering/table-in-table)
 * inside Odoo template form. User edits .docx directly in browser; save flow
 * goes through OnlyOffice callback → Odoo controller → binary field updated.
 *
 * Requires:
 *   - OnlyOffice Document Server reachable at OO_BASE_URL (browser side)
 *   - Backend controller /re_doc/<id>/{config,download,callback}
 *   - JWT_SECRET matching between Odoo and OnlyOffice container
 *
 * Editor only mounts after record saved (needs template_id for config URL).
 * In create mode (no id yet), shows hint to save first.
 */
export class OnlyofficeEditorField extends Component {
    static template = "re_doc.OnlyofficeEditorField";
    static props = { ...standardFieldProps };

    setup() {
        this.containerRef = useRef("editorContainer");
        this.editor = null;          // OnlyOffice DocEditor instance
        this.scriptLoaded = false;   // ds API JS loaded global once
        // Plugin window registry — template_id → {win, lastSeen} cho IPC
        this._pluginWindows = new Map();
        this.state = useState({
            loading: false,
            error: null,
            ready: false,
            // Field picker sidebar state — curated mode (replace raw fields)
            fieldsLoading: false,
            fieldsError: null,
            modelLabel: null,        // VD "zone.contract"
            curatedGroups: [],       // [{label, fields: [{label, snippet}]}]
            expandedGroups: {},      // {groupIdx: bool} — default expanded
            searchQuery: "",
            copiedHint: null,        // text vừa insert/copy — show check icon 2s
            feedbackMode: null,      // "inserted" (xanh) hoặc "copied" (vàng)
        });

        // Global postMessage listener — plugin (chạy inside editor iframe)
        // broadcasts hello tới top/parent/parent.parent khi start + heartbeat
        // 4s. Lưu window reference + lastSeen timestamp để biết plugin alive
        // trước insert.
        this._messageHandler = (e) => {
            try {
                let d = e.data;
                // OnlyOffice plugin protocol có thể JSON-stringify — handle both
                if (typeof d === "string" && d.startsWith("{")) {
                    try { d = JSON.parse(d); } catch (parseErr) { /* not our msg */ }
                }
                if (!d || typeof d !== "object" || !d.reDocPluginHello) return;
                const tid = String(d.template_id);
                const isFirstHello = !this._pluginWindows.has(tid);
                this._pluginWindows.set(tid, {
                    win: e.source,
                    lastSeen: Date.now(),
                });
                if (isFirstHello) {
                    console.log(
                        "[re-doc-oo] plugin connected cho template", tid);
                }
            } catch (err) {
                console.warn("[re-doc-oo] message handler error:", err);
            }
        };
        window.addEventListener("message", this._messageHandler);

        // useEffect runs sau mount + sau mỗi render đổi resId. Đảm bảo
        // mountEditor() chỉ fire khi DOM ref + resId đã sẵn — fix race
        // condition khi save lần đầu (resId null → N) mà editor không
        // tự mount, phải refresh page mới load. Cleanup destroy editor
        // khi unmount hoặc resId đổi.
        useEffect(
            (resId) => {
                if (resId) {
                    this.mountEditor();
                    this.fetchFields();
                }
                return () => this.destroyEditor();
            },
            () => [this.props.record.resId],
        );
        onWillUnmount(() => {
            window.removeEventListener("message", this._messageHandler);
            this.destroyEditor();
        });
    }

    /** Load OnlyOffice DocEditor API JS bundle once per page. */
    async loadOnlyofficeScript() {
        if (window.DocsAPI && window.DocsAPI.DocEditor) {
            this.scriptLoaded = true;
            return;
        }
        // Fetch config first to get OO_BASE_URL — config endpoint also tells
        // us if backend is properly configured (returns 400/500 otherwise)
        const recId = this.props.record.resId;
        if (!recId) {
            return; // create mode — editor will mount after first save
        }

        // Compute OO base URL from window.location relative to the Odoo host's
        // sibling subdomain. Pattern: <whatever>.parkone.{vn|com} → oo.parkone.<tld>
        // Fallback: hardcode 'Document Server' for known production deploy.
        // For multi-tenant we'd inject this from server-side ir.config_parameter.
        const baseUrl = await this.computeOOBaseUrl();
        const apiUrl = `${baseUrl}/web-apps/apps/api/documents/api.js`;

        return new Promise((resolve, reject) => {
            const tag = document.createElement("script");
            tag.src = apiUrl;
            tag.async = true;
            tag.onload = () => {
                this.scriptLoaded = true;
                resolve();
            };
            tag.onerror = () => {
                reject(new Error(_t(
                    "Không tải được OnlyOffice editor từ %s. Kiểm tra CF Tunnel hostname Document Server còn live không.",
                    baseUrl)));
            };
            document.head.appendChild(tag);
        });
    }

    /** URL Document Server do server cap (env OO_BASE_URL). */
    async computeOOBaseUrl() {
        if (this._ooBaseUrl) {
            return this._ooBaseUrl;
        }
        const resp = await fetch("/re_doc/oo-info", {
            credentials: "same-origin",
        });
        if (!resp.ok) {
            throw new Error(_t("Không đọc được cấu hình OnlyOffice từ máy chủ."));
        }
        const info = await resp.json();
        if (!info.configured) {
            throw new Error(_t(
                "Máy chủ chưa cấu hình OO_JWT_SECRET — liên hệ quản trị hệ thống."));
        }
        this._ooBaseUrl = (info.base_url || "").replace(/\/$/, "");
        return this._ooBaseUrl;
    }

    async mountEditor() {
        const recId = this.props.record.resId;
        if (!recId) {
            // Create mode — show hint instead of editor
            this.state.ready = false;
            return;
        }

        this.state.loading = true;
        this.state.error = null;

        try {
            // 1. Load OnlyOffice DocEditor script
            console.log("[re-doc-oo] Loading OnlyOffice script from", await this.computeOOBaseUrl());
            await this.loadOnlyofficeScript();
            console.log("[re-doc-oo] Script loaded, DocsAPI:", !!window.DocsAPI);

            if (!window.DocsAPI || !window.DocsAPI.DocEditor) {
                throw new Error(_t(
                    "OnlyOffice DocsAPI không load được từ %s. " +
                    "Kiểm tra CF Tunnel hostname Document Server live không.",
                    await this.computeOOBaseUrl()));
            }

            // 2. Fetch editor config from backend (signed JWT included)
            console.log(`[re-doc-oo] Fetching /re_doc/${recId}/config`);
            const configResp = await fetch(`/re_doc/${recId}/config`, {
                method: "GET",
                credentials: "same-origin",
            });
            if (!configResp.ok) {
                const txt = await configResp.text();
                throw new Error(_t(
                    "Config endpoint trả status %s: %s",
                    configResp.status, txt));
            }
            const config = await configResp.json();
            console.log("[re-doc-oo] Config received:", {
                ...config,
                token: config.token ? `<${config.token.length} chars>` : null,
            });

            // 3. Wait for container DOM ref + clear any previous editor
            if (!this.containerRef.el) {
                await new Promise(r => setTimeout(r, 50));
            }
            if (!this.containerRef.el) {
                throw new Error(_t("Container DOM ref không sẵn — Owl mount issue"));
            }
            const containerId = `oo-editor-${recId}-${Date.now()}`;
            this.containerRef.el.id = containerId;
            console.log("[re-doc-oo] Mounting DocEditor on", containerId);

            // 4. Init DocEditor with config — this builds the iframe + API
            this.editor = new window.DocsAPI.DocEditor(containerId, {
                ...config,
                events: {
                    onError: (event) => {
                        console.error("[re-doc-oo] OnlyOffice error event:", event);
                        const desc = (event && event.data && event.data.errorDescription)
                            || JSON.stringify(event && event.data)
                            || _t("Lỗi không xác định từ OnlyOffice editor");
                        this.state.error = desc;
                        this.state.loading = false;
                    },
                    onReady: () => {
                        console.log("[re-doc-oo] Editor ready");
                        this.state.loading = false;
                        this.state.ready = true;
                    },
                    onDocumentReady: () => {
                        console.log("[re-doc-oo] Document loaded");
                        this.state.loading = false;
                        this.state.ready = true;
                    },
                    onDocumentStateChange: (event) => {
                        // event.data === true: there are unsaved changes
                    },
                    onRequestSaveAs: () => {
                        // User clicked "Save As" — could implement custom dialog
                    },
                    onWarning: (event) => {
                        console.warn("[re-doc-oo] Warning:", event);
                    },
                },
            });
            console.log("[re-doc-oo] DocEditor instance created");
        } catch (e) {
            console.error("[re-doc-oo] Mount editor failed:", e);
            this.state.loading = false;
            this.state.error = e.message || String(e);
        }
    }

    destroyEditor() {
        if (this.editor) {
            try {
                this.editor.destroyEditor();
            } catch (e) {
                console.warn("destroyEditor failed:", e);
            }
            this.editor = null;
        }
    }

    // ── Field Picker sidebar ──

    /** Fetch curated field groups từ backend; populate this.state.curatedGroups. */
    async fetchFields() {
        const recId = this.props.record.resId;
        if (!recId) return;
        this.state.fieldsLoading = true;
        this.state.fieldsError = null;
        try {
            const resp = await fetch(`/re_doc/${recId}/curated-fields`, {
                method: "GET",
                credentials: "same-origin",
            });
            if (!resp.ok) {
                throw new Error(_t("Curated fields endpoint trả status %s", resp.status));
            }
            const data = await resp.json();
            this.state.modelLabel = data.model || null;
            this.state.curatedGroups = data.groups || [];
        } catch (e) {
            console.error("[re-doc-oo] fetchFields failed:", e);
            this.state.fieldsError = e.message || String(e);
        } finally {
            this.state.fieldsLoading = false;
        }
    }

    /** Filtered groups theo searchQuery — match label của field hoặc group. */
    get filteredGroups() {
        const q = (this.state.searchQuery || "").trim().toLowerCase();
        if (!q) return this.state.curatedGroups;
        return this.state.curatedGroups
            .map((g) => {
                const matchedFields = (g.fields || []).filter((f) =>
                    (f.label || "").toLowerCase().includes(q));
                const groupMatches =
                    (g.label || "").toLowerCase().includes(q);
                if (groupMatches) return g;  // show all fields when group label matches
                if (matchedFields.length) {
                    return { ...g, fields: matchedFields };
                }
                return null;
            })
            .filter(Boolean);
    }

    /** Toggle expanded state cho group. */
    toggleGroup(idx) {
        this.state.expandedGroups[idx] = !this.state.expandedGroups[idx];
    }

    /** Insert exact Jinja snippet vào editor (từ curated config). */
    insertCurated(snippet, fieldLabel) {
        this.insertIntoEditor(snippet, `curated:${fieldLabel}`);
    }

    /** Flash success hint với mode "inserted" (xanh) hoặc "copied" (vàng). */
    _flashHint(label, mode) {
        this.state.copiedHint = label;
        this.state.feedbackMode = mode;
        setTimeout(() => {
            if (this.state.copiedHint === label) {
                this.state.copiedHint = null;
            }
        }, 1800);
    }

    /** Copy text to clipboard + flash hint icon (yellow "copied"). */
    async copyToClipboard(text, hintLabel) {
        try {
            await navigator.clipboard.writeText(text);
            this._flashHint(hintLabel, "copied");
        } catch (e) {
            console.error("[re-doc-oo] clipboard write failed:", e);
            window.prompt(
                _t("Trình duyệt không cho phép tự động copy. Cmd+C để copy:"),
                text);
        }
    }

    /** Insert text vào vị trí con trỏ trong editor.
     *
     * OnlyOffice 9.4 DocEditor parent API KHÔNG expose callCommand/InsertText.
     * Workaround: dùng plugin sidecar (autostart từ editor config) chạy inside
     * editor iframe. Plugin có Asc.plugin.callCommand → InsertContent.
     *
     * IPC qua postMessage (bypass Chrome partitioned storage cho nested
     * cross-origin iframe — plugin iframe inside editor iframe Document Server
     * không share localStorage với Odoo main page dù cùng origin):
     *   1. Plugin postMessage hello tới window.top → Odoo lưu e.source
     *      (plugin Window ref) + lastSeen timestamp
     *   2. Heartbeat hello 4s — Odoo update lastSeen
     *   3. Odoo postMessage insert request ngược lại plugin window ref →
     *      plugin nhận → callCommand insert
     *
     * Nếu plugin chưa hello (vừa load) hoặc stale > 10s → fallback clipboard.
     */
    /** Click handler wrapper — chỉ fire khi e.detail === 1 (click đầu
     * tiên của sequence). e.detail >= 2 → đó là click thứ 2+ của
     * double-click → skip để ngăn duplicate insert.
     */
    onClickInsert(e, fn) {
        if (e && e.detail !== undefined && e.detail !== 1) return;
        fn();
    }

    async insertIntoEditor(text, hintLabel) {
        const recId = this.props.record.resId;
        if (!recId) {
            await this.copyToClipboard(text, hintLabel);
            return;
        }

        // Debounce identical inserts trong 500ms — safety net cho trường hợp
        // 2 click events cách xa > e.detail bị mất. Browser dblclick threshold
        // typically 500ms.
        const now = Date.now();
        if (this._lastInsertText === text &&
            now - (this._lastInsertAt || 0) < 500) {
            return;
        }
        this._lastInsertText = text;
        this._lastInsertAt = now;

        const tid = String(recId);
        const entry = this._pluginWindows.get(tid);
        if (!entry) {
            console.warn(
                "[re-doc-oo] Plugin chưa hello cho template", tid,
                "— fallback clipboard");
            await this.copyToClipboard(text, hintLabel);
            return;
        }

        if (Date.now() - entry.lastSeen > 10000) {
            console.warn(
                "[re-doc-oo] Plugin stale (last hello",
                Date.now() - entry.lastSeen, "ms ago), fallback clipboard");
            await this.copyToClipboard(text, hintLabel);
            return;
        }

        try {
            // Grab focus về editor TRƯỚC khi insert — nếu user vừa click
            // sidebar, focus rời editor → OnlyOffice có thể clear cursor
            // selection state. grabFocus restore selection để plugin
            // GetRangeBySelect() trả range thay vì null.
            if (this.editor && typeof this.editor.grabFocus === "function") {
                try { this.editor.grabFocus(); } catch (e) { /* ignore */ }
            }
            entry.win.postMessage({
                reDocInsert: true,
                template_id: recId,
                text: text,
            }, "*");
            this._flashHint(hintLabel, "inserted");
            console.log("[re-doc-oo] insert posted to plugin:", text);
        } catch (e) {
            console.error("[re-doc-oo] postMessage to plugin failed:", e);
            await this.copyToClipboard(text, hintLabel);
        }
    }

    /** Build path `record.field` hoặc `record.parent.child` */
    _buildPath(parentName, childName) {
        if (childName) {
            return `record.${parentName}.${childName}`;
        }
        return `record.${parentName}`;
    }

    /** Insert `{{ record.field }}` vào cursor position trong editor. */
    insertVariable(parentName, childName) {
        const path = this._buildPath(parentName, childName);
        const snippet = `{{ ${path} }}`;
        this.insertIntoEditor(snippet, `var:${parentName}.${childName || ''}`);
    }

    /** Insert `{% for item in record.o2m %}{{ item.name }}{% endfor %}` */
    insertLoop(parentName) {
        const snippet =
            `{% for item in record.${parentName} %}` +
            ` {{ item.display_name }} ` +
            `{% endfor %}`;
        this.insertIntoEditor(snippet, `loop:${parentName}`);
    }

    /** Insert `{% if record.field %}...{% endif %}` */
    insertConditional(parentName, childName) {
        const path = this._buildPath(parentName, childName);
        const snippet = `{% if ${path} %}${path}{% endif %}`;
        this.insertIntoEditor(snippet, `if:${parentName}.${childName || ''}`);
    }

    /** Insert tự do (cho snippet footer today_full / company.name / user.name) */
    insertSnippet(text, label) {
        this.insertIntoEditor(text, label);
    }

    // ── JS getters cho snippet labels (tránh OWL {{ }} parser quirk) ──
    get jinjaBraces() { return "{{}}"; }
    get snippetTodayLabel() { return "{{ today_full }}"; }
    get snippetCompanyLabel() { return "{{ company.name }}"; }
    get snippetUserLabel() { return "{{ user.name }}"; }
    get snippetToday() { return "{{ today_full }}"; }
    get snippetCompany() { return "{{ company.name }}"; }
    get snippetUser() { return "{{ user.name }}"; }

    /** Icon class hint cho field type — visual cue trong tree. */
    fieldIcon(ftype) {
        const map = {
            char: "fa-font",
            text: "fa-align-left",
            html: "fa-code",
            integer: "fa-hashtag",
            float: "fa-percent",
            monetary: "fa-dollar-sign",
            boolean: "fa-toggle-on",
            date: "fa-calendar",
            datetime: "fa-clock",
            selection: "fa-list",
            many2one: "fa-link",
            one2many: "fa-list-ul",
            many2many: "fa-tags",
        };
        return map[ftype] || "fa-circle";
    }

    /** User clicked "Tải file mới" — re-trigger native file picker on hidden input */
    onUploadClick(ev) {
        const input = this.containerRef.el.parentElement.querySelector('input[type=file]');
        if (input) input.click();
    }

    /** Hidden <input type=file> change handler — uploads new .docx, refreshes editor */
    async onFileChange(ev) {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        if (!file.name.toLowerCase().endsWith('.docx')) {
            this.state.error = _t("File phải là .docx (không nhận .doc hoặc .pdf)");
            return;
        }
        const reader = new FileReader();
        reader.onload = async () => {
            const b64 = reader.result.split(',', 2)[1];
            await this.props.record.update({
                docx_file: b64,
                docx_filename: file.name,
            });
            await this.props.record.save();
            // Remount editor with new doc
            this.destroyEditor();
            this.mountEditor();
        };
        reader.readAsDataURL(file);
    }
}

registry.category("fields").add("re_onlyoffice_editor", {
    component: OnlyofficeEditorField,
    supportedTypes: ["binary"],
    displayName: _t("OnlyOffice Document Editor"),
});
