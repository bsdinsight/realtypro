# Đấu nối SharePoint Online — việc cần làm phía Microsoft 365

---

## ✅ Tình trạng thực tế của BSD (cập nhật 08/10/2026)

Bước 1, 2, 3 **đã làm xong**. Giá trị thực:

```
Tenant ID      : 623399a9-16dd-43ba-b733-5c71e7ea004c
Client ID      : 7c896a6b-8d8b-49c6-b0f0-5f71e6e118bf
Tên ứng dụng   : RealtyPro — Hồ sơ dự án
Site URL       : https://bsdinsight0.sharepoint.com/sites/Demo
Graph Site ID  : bsdinsight0.sharepoint.com,8edda0a0-207d-47d0-8424-98b25578b90a,c8b94779-e6cd-45ca-b7bc-7edd0d4507ba
```

`Sites.Selected` đã thêm đúng loại **Application** và đã **Grant admin
consent** (Status: Granted).

**Còn lại hai việc, cả hai đều phải chính anh Đại bấm:**

**(a) Bước 4b** — mở <https://developer.microsoft.com/graph/graph-explorer>
bằng trình duyệt thường (pop-up đăng nhập không chạy được trong pane của
Claude), đăng nhập tài khoản admin, chọn `POST`, dán URL:

```
https://graph.microsoft.com/v1.0/sites/bsdinsight0.sharepoint.com,8edda0a0-207d-47d0-8424-98b25578b90a,c8b94779-e6cd-45ca-b7bc-7edd0d4507ba/permissions
```

Request body:

```json
{
  "roles": ["write"],
  "grantedToIdentities": [
    {
      "application": {
        "id": "7c896a6b-8d8b-49c6-b0f0-5f71e6e118bf",
        "displayName": "RealtyPro — Hồ sơ dự án"
      }
    }
  ]
}
```

Trả về `201 Created` là xong. Bước 4a (lấy Site ID) **bỏ qua** — đã lấy
sẵn ở trên bằng `_api/site/id` và `_api/web/id`.

**(b) Bước 5** — tạo client secret. Chuỗi bí mật không đi qua Claude.

---

Làm một lần cho cả hệ thống. Mất khoảng 15 phút, nhưng **phải có quyền
Global Administrator hoặc SharePoint Administrator** của tenant công ty.

Kết quả cuối cùng là 4 giá trị. Ba cái đầu gửi cho tôi, cái thứ tư anh
tự dán vào Odoo.

---

## 1. Lấy Tenant ID và URL site

**Tenant ID** — vào <https://entra.microsoft.com> → **Overview**.
Chép ô **Tenant ID** (dạng `a1b2c3d4-....`).

**URL site** — mở site SharePoint sẽ dùng để chứa hồ sơ dự án. Chép URL
đến hết tên site, bỏ phần đuôi:

```
https://congty.sharepoint.com/sites/DuAn        ✅
https://congty.sharepoint.com/sites/DuAn/Shared%20Documents/Forms/...   ❌
```

> **Nên tạo một site riêng** cho hồ sơ dự án thay vì dùng site có sẵn
> đang chứa thứ khác. Quyền cấp ở bước 4 là cấp cho cả site — site càng
> gọn thì phạm vi Odoo chạm vào càng hẹp.

---

## 2. Đăng ký ứng dụng

<https://entra.microsoft.com> → **Identity** → **Applications** →
**App registrations** → **New registration**.

| Ô | Điền |
|---|---|
| Name | `RealtyPro — Hồ sơ dự án` |
| Supported account types | **Single tenant** (chỉ tổ chức này) |
| Redirect URI | **để trống** |

Bấm **Register**. Màn hình hiện ra, chép **Application (client) ID**.

> Để trống Redirect URI là đúng: Odoo gọi Graph bằng danh nghĩa ứng
> dụng (client credentials), không có ai đăng nhập, nên không cần chỗ
> quay về.

---

## 3. Cấp quyền `Sites.Selected`

Trong app vừa tạo → **API permissions** → **Add a permission** →
**Microsoft Graph** → **Application permissions** → tìm `Sites.Selected`
→ tick → **Add permissions**.

Rồi bấm **Grant admin consent for \<tên công ty\>** → **Yes**.
Cột Status phải chuyển thành **Granted** màu xanh.

> ⚠️ **Phải chọn "Application permissions", không phải "Delegated".**
> Delegated là quyền thay mặt một người đang đăng nhập — Odoo chạy nền
> không có ai đăng nhập, chọn nhầm thì đến lúc chạy mới báo lỗi quyền.

> **Vì sao `Sites.Selected` chứ không `Files.ReadWrite.All`:**
> `Files.ReadWrite.All` cho ứng dụng đọc ghi **mọi** site SharePoint và
> **mọi** OneDrive của toàn công ty. `Sites.Selected` thì mặc định
> không cho gì cả, phải chỉ đích danh từng site — đó là bước 4.

---

## 4. Cấp quyền cho đúng site đó ⚠️

**Đây là bước ai cũng quên.** Xong bước 3 ứng dụng vẫn **chưa truy cập
được gì** — `Sites.Selected` nghĩa là "chỉ những site được chỉ đích
danh", và chưa ai chỉ cả.

### Cách dễ nhất — Graph Explorer, không cần cài gì

Mở <https://developer.microsoft.com/graph/graph-explorer>, đăng nhập
bằng tài khoản admin.

**4a. Lấy Site ID.** Chọn `GET`, dán URL này (thay `congty` và `DuAn`):

```
https://graph.microsoft.com/v1.0/sites/congty.sharepoint.com:/sites/DuAn
```

Bấm **Run query**. Trong kết quả tìm trường `"id"`, nó dài kiểu:

```
congty.sharepoint.com,8f1c...,3b2a...
```

Chép **nguyên cả chuỗi, kể cả hai dấu phẩy**.

**4b. Cấp quyền ghi.** Chọn `POST`, URL:

```
https://graph.microsoft.com/v1.0/sites/<SITE-ID-vừa-chép>/permissions
```

Tab **Request body**, dán vào (thay client ID ở bước 2):

```json
{
  "roles": ["write"],
  "grantedToIdentities": [
    {
      "application": {
        "id": "<CLIENT-ID>",
        "displayName": "RealtyPro — Hồ sơ dự án"
      }
    }
  ]
}
```

Bấm **Run query**. Trả về `201 Created` là xong.

> Nếu báo lỗi thiếu quyền: bấm **Modify permissions** ngay trong Graph
> Explorer và đồng ý cấp `Sites.FullControl.All` cho phiên làm việc của
> chính anh. Đây là quyền của *tài khoản admin đang đăng nhập Graph
> Explorer*, không phải của ứng dụng.

> `"roles": ["write"]` là bắt buộc. Cấp `read` thì Odoo tạo thư mục
> không được, mà lỗi chỉ hiện ra lúc chạy thật.

### Cách thay thế — PowerShell

```powershell
Install-Module PnP.PowerShell -Scope CurrentUser
Connect-PnPOnline -Url https://congty.sharepoint.com/sites/DuAn -Interactive
Grant-PnPAzureADAppSitePermission `
  -AppId <CLIENT-ID> `
  -DisplayName "RealtyPro — Hồ sơ dự án" `
  -Site https://congty.sharepoint.com/sites/DuAn `
  -Permissions Write
```

> Nếu `Connect-PnPOnline` đòi `-ClientId`: chạy một lần
> `Register-PnPEntraIDAppForInteractiveLogin` rồi dùng ClientId nó trả
> về. Từ tháng 9/2024 PnP bỏ app dùng chung nên mỗi tổ chức phải tự
> đăng ký.

---

## 5. Tạo Client secret

Quay lại app → **Certificates & secrets** → **Client secrets** →
**New client secret**.

| Ô | Điền |
|---|---|
| Description | `Odoo RealtyPro` |
| Expires | **24 months** |

Bấm **Add**. Chép ngay cột **Value** (KHÔNG phải cột *Secret ID*).

> ⚠️ **Chuỗi Value chỉ hiện một lần.** Rời khỏi trang là không xem lại
> được, phải tạo cái mới.

> 📅 **Ghi lại ngày hết hạn vào lịch, nhắc trước 1 tháng.** Secret hết
> hạn thì SharePoint ngừng đồng bộ và thông báo lỗi thường rất khó
> đoán ra nguyên nhân.

---

## 6. Bàn giao

**Gửi cho tôi 3 giá trị này** (không nhạy cảm, chỉ là định danh):

```
Tenant ID  : ........................................
Client ID  : ........................................
Site URL   : https://........sharepoint.com/sites/........
```

**Client secret thì KHÔNG gửi qua chat.** Tôi sẽ dựng màn hình
*Cấu hình → SharePoint* trong Odoo, anh dán thẳng vào đó. Trường lưu
dạng mật khẩu, không hiện lại.

---

## Tự kiểm trước khi bàn giao

| | |
|---|---|
| ☐ | API permissions hiện `Sites.Selected` — loại **Application**, Status **Granted** |
| ☐ | Bước 4 đã chạy và trả về `201 Created` |
| ☐ | Role cấp ở bước 4 là **write**, không phải read |
| ☐ | Đã chép cột **Value** của secret (không phải Secret ID) |
| ☐ | Đã ghi ngày hết hạn secret vào lịch |

---

## Nguồn

- [Configure a connector app for Sites.Selected — UpSlide](https://support.upslide.net/hc/en-us/articles/22770194016540-SharePoint-Configure-a-connector-app-for-Sites-Selected-permissions)
- [Grant Sites.Selected permissions — Progress MOVEit](https://docs.progress.com/bundle/moveit-automation-web-admin-help-2026/page/Grant-Sites.Selected-permissions.html)
- [Granting Site Access to Your SharePoint Integration — Conveyor](https://docs.conveyor.com/docs/granting-site-access-to-your-sharepoint-integration)
- [Controlling app access on specific SharePoint site collections — ESPC](https://espc.tech/learning-hub/blog/controlling-app-access-on-a-specific-sharepoint-site-collections/)

Các nguồn trên là tài liệu của bên thứ ba, không phải của Microsoft.
Giao diện Entra có thể đổi tên nút; các bước và endpoint Graph thì vẫn
đúng.
