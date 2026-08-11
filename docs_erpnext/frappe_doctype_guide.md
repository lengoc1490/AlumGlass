# Hướng Dẫn Toàn Diện Custom DocType trong Frappe/ERPNext

> **Phiên bản:** Frappe v14/v15 – ERPNext v14/v15  
> **Mục đích:** Tài liệu tham chiếu khi thiết lập, tùy chỉnh DocType mới hoặc hiện có

---

## Mục lục

1. [Tổng quan về DocType](#1-tổng-quan-về-doctype)
2. [Settings cấp DocType](#2-settings-cấp-doctype)
   - 2.1 [Nhận dạng & Phân loại](#21-nhận-dạng--phân-loại)
   - 2.2 [Đặt tên bản ghi (Naming)](#22-đặt-tên-bản-ghi-naming)
   - 2.3 [Sắp xếp & Tìm kiếm](#23-sắp-xếp--tìm-kiếm)
   - 2.4 [Theo dõi & Lịch sử](#24-theo-dõi--lịch-sử)
   - 2.5 [Thao tác người dùng](#25-thao-tác-người-dùng)
   - 2.6 [Hiển thị giao diện](#26-hiển-thị-giao-diện)
   - 2.7 [States (Trạng thái)](#27-states-trạng-thái)
   - 2.8 [Links (Liên kết ngược)](#28-links-liên-kết-ngược)
   - 2.9 [Permissions (Phân quyền)](#29-permissions-phân-quyền)
   - 2.10 [Database Engine](#210-database-engine)
3. [Settings cấp Field (Trường dữ liệu)](#3-settings-cấp-field-trường-dữ-liệu)
   - 3.1 [Nhận dạng Field](#31-nhận-dạng-field)
   - 3.2 [Loại Field (Field Type)](#32-loại-field-field-type)
   - 3.3 [Bắt buộc & Ràng buộc](#33-bắt-buộc--ràng-buộc)
   - 3.4 [Giá trị mặc định & Fetch](#34-giá-trị-mặc-định--fetch)
   - 3.5 [Hiển thị & Ẩn](#35-hiển-thị--ẩn)
   - 3.6 [Phân quyền cấp Field](#36-phân-quyền-cấp-field)
   - 3.7 [Tìm kiếm & Danh sách](#37-tìm-kiếm--danh-sách)
   - 3.8 [In ấn](#38-in-ấn)
   - 3.9 [Giao diện & Định dạng](#39-giao-diện--định-dạng)
   - 3.10 [Depends On (Hiển thị có điều kiện)](#310-depends-on-hiển-thị-có-điều-kiện)
4. [Tham chiếu nhanh theo Field Type](#4-tham-chiếu-nhanh-theo-field-type)
5. [Các pattern thường gặp khi Custom](#5-các-pattern-thường-gặp-khi-custom)
6. [Checklist trước khi lưu DocType](#6-checklist-trước-khi-lưu-doctype)

---

## 1. Tổng quan về DocType

DocType là đơn vị cơ bản nhất trong Frappe Framework — tương đương một **bảng trong database** kèm theo toàn bộ logic hiển thị, phân quyền, và hành vi. Mỗi DocType bao gồm:

- **Metadata**: tên, module, loại, cách đặt tên
- **Fields**: danh sách các trường dữ liệu
- **Permissions**: quyền theo role
- **Controller**: code Python/JS xử lý logic nghiệp vụ

```
DocType
├── Settings (cấu hình tổng thể)
├── Fields (danh sách trường)
│   ├── Layout Fields (Section Break, Column Break, Tab Break)
│   ├── Data Fields (Data, Int, Float, Currency, Date...)
│   └── Relation Fields (Link, Table, Dynamic Link...)
├── Permissions (phân quyền theo role)
├── States (màu trạng thái)
└── Links (liên kết ngược)
```

---

## 2. Settings cấp DocType

### 2.1 Nhận dạng & Phân loại

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Name** | Data | *(bắt buộc)* | Tên định danh duy nhất của DocType. Dùng để tham chiếu qua code, API, URL. Không thể thay đổi sau khi có dữ liệu. Dùng PascalCase (vd: `Sales Invoice`, `Leave Application`). |
| **Module** | Link | *(bắt buộc)* | Module chứa DocType. Ảnh hưởng đến vị trí lưu file trong apps, menu sidebar. |
| **Is Submittable** | Check | `0` | Kích hoạt vòng đời **Draft → Submitted → Cancelled**. Khi submit, bản ghi bị khóa (không sửa trực tiếp). Muốn sửa phải Cancel → Amend (tạo phiên bản mới). Dùng cho chứng từ tài chính, phê duyệt. |
| **Is Child Table** (`istable`) | Check | `0` | Đánh dấu DocType là **bảng con**. Chỉ tồn tại bên trong DocType cha thông qua field loại `Table`. Không có List View, form riêng, hoặc URL độc lập. Không cần định nghĩa Permissions riêng. |
| **Is Tree** | Check | `0` | Cấu trúc **phân cấp cha–con** (Nested Set Model). Hiển thị Tree View. Tự động thêm các trường `parent_<doctype>`, `is_group`, `lft`, `rgt`. Ví dụ: Account, Territory, Cost Center. |
| **Is Virtual** | Check | `0` | DocType **không tạo bảng trong database**. Toàn bộ CRUD xử lý qua Python controller (`get_list`, `get_doc`, `db_insert`...). Dùng để wrap API bên ngoài hoặc computed data. |
| **Is Single** | Check | `0` | DocType chỉ có **một bản ghi duy nhất** (lưu trong `tabSingles`). Thường dùng cho trang cấu hình (System Settings, HR Settings...). Không có List View, không cần Naming. |
| **Is Calendar and Gantt** | Check | `0` | Hiển thị thêm chế độ xem **Calendar** và **Gantt Chart** trong List View. Yêu cầu có trường ngày bắt đầu (`start_date`) và kết thúc (`end_date`). |
| **Beta** | Check | `0` | Đánh dấu DocType đang trong giai đoạn thử nghiệm. Hiển thị badge "Beta" trên UI. |

---

### 2.2 Đặt tên bản ghi (Naming)

Cách hệ thống sinh giá trị `name` (primary key) cho mỗi bản ghi.

| Setting | Kiểu | Mô tả chi tiết |
|---------|------|----------------|
| **Naming Rule** | Select | Quy tắc sinh tên. Xem bảng bên dưới. |
| **Autoname** | Data | Cú pháp cụ thể, phụ thuộc vào Naming Rule được chọn. |
| **Title Field** | Select | Trường dùng làm **tiêu đề hiển thị** thay cho `name` ở breadcrumb, link field, list view title. Thường dùng khi `name` là mã số tự động, không thân thiện. |
| **Show Title Field in Link** | Check | Khi bật, Link Field đến DocType này hiển thị cả `name` lẫn giá trị `title_field`. |

**Các Naming Rule:**

| Rule | Autoname mẫu | Kết quả |
|------|-------------|---------|
| **By Naming Series** | `naming_series:` | Dùng giá trị từ field `naming_series` (Select field). Ví dụ series `SINV-.YYYY.-` → `SINV-2024-0001`. |
| **Expression** | `PROJ-.MM.-.{project_name}.-` | Kết hợp text tĩnh, biến thời gian, giá trị field. |
| **Expression (Old Style)** | `field:customer_name` | Lấy giá trị từ một field làm name. |
| **Autoincrement** | `autoincrement` | Số nguyên tự tăng (1, 2, 3...). |
| **UUID** | `UUID` | Chuỗi UUID ngẫu nhiên. |
| **By Field** | `field:fieldname` | Dùng giá trị của field cụ thể làm name. |
| **Set by user** | *(để trống)* | Người dùng tự nhập `name`. |
| **Random** | `hash` | Chuỗi hash ngẫu nhiên. |

**Biến thời gian trong Expression:**

| Biến | Ý nghĩa |
|------|---------|
| `.YYYY.` | Năm 4 chữ số (2024) |
| `.YY.` | Năm 2 chữ số (24) |
| `.MM.` | Tháng 2 chữ số (01–12) |
| `.DD.` | Ngày 2 chữ số (01–31) |
| `.FY.` | Fiscal Year (vd: 2024-2025) |
| `.######.` | Số tự tăng với số chữ số tương ứng |

---

### 2.3 Sắp xếp & Tìm kiếm

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Sort Field** | Select | `modified` | Trường dùng để sắp xếp mặc định trong List View. Nên chọn trường có index để tối ưu hiệu năng. |
| **Sort Order** | Select | `DESC` | `ASC` = tăng dần (cũ → mới), `DESC` = giảm dần (mới → cũ). |
| **Search Fields** | Data | *(trống)* | Danh sách trường được tìm kiếm khi gõ vào Link Field hoặc ô tìm kiếm, ngoài `name`. Phân cách bằng dấu phẩy. Ví dụ: `customer_name, mobile_no, email`. Các trường này nên có `search_index = 1` để tối ưu. |
| **Show Name in Global Search** | Check | `0` | Bản ghi xuất hiện trong kết quả **Global Search** (thanh tìm kiếm trên cùng của hệ thống). |
| **Index Web Pages for Search** | Check | `0` | Lập chỉ mục trang web của bản ghi cho Web Search (chỉ dùng khi có `Has Web View`). |

---

### 2.4 Theo dõi & Lịch sử

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Track Changes** | Check | `0` | Lưu **Version** mỗi khi bản ghi được sửa. Ghi lại: trường nào thay đổi, từ giá trị cũ sang giá trị mới, ai sửa, lúc nào. Xem lịch sử qua nút "..." → "Versions" trên form. Tốn thêm storage. |
| **Track Views** | Check | `0` | Tạo bản ghi `View Log` mỗi khi có người mở bản ghi. Có thể dùng để analytics. |
| **Track Seen** | Check | `0` | Đánh dấu bản ghi là "đã đọc" cho từng user. Hiển thị indicator màu xanh "New" trên bản ghi chưa xem. |
| **Timeline Field** | Link | *(trống)* | Link đến một DocType khác (thường Customer/Supplier). Bản ghi sẽ xuất hiện trong **timeline** của đối tượng được link. Ví dụ: Sales Invoice có `timeline_field = customer` → invoice xuất hiện trong timeline của Customer. |

---

### 2.5 Thao tác người dùng

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Allow Import** | Check | `0` | Cho phép nhập dữ liệu hàng loạt từ **CSV/Excel** qua menu Data Import. Chỉ nên bật cho DocType không phức tạp về validation. |
| **Allow Copy** | Check | `0` | Hiển thị nút **Duplicate** trên form, tạo bản ghi mới từ bản hiện tại. Các field có `no_copy = 1` sẽ bị bỏ qua khi copy. |
| **Allow Rename** | Check | `0` | Cho phép đổi giá trị `name` sau khi tạo (qua menu "..." → "Rename"). Hệ thống tự cập nhật tất cả reference. Cẩn thận khi bật vì có thể gây lỗi với dữ liệu liên quan. |
| **Allow Events in Timeline** | Check | `0` | Hiển thị **Calendar Events** được gắn với bản ghi trong timeline của form. |
| **Allow Auto Repeat** | Check | `0` | Cho phép cài đặt **Auto Repeat** — tự động tạo bản ghi mới theo lịch (hàng ngày/tuần/tháng). Dùng cho invoice định kỳ, task lặp lại. |
| **Allow Guest to View** | Check | `0` | Người dùng **chưa đăng nhập** có thể xem bản ghi qua web URL. Chỉ có tác dụng khi `Has Web View = 1`. |
| **Quick Entry** | Check | `0` | Bật **Quick Entry Dialog** — form nhỏ gọn để tạo nhanh bản ghi. Chỉ hiển thị các field có `allow_in_quick_entry = 1`. Tiện khi cần tạo nhanh từ Link Field. |
| **Max Attachments** | Int | `0` | Số lượng file đính kèm tối đa. `0` = không giới hạn. Khi đạt giới hạn, nút Attach bị vô hiệu. |
| **Make Attachments Public** | Check | `0` | File đính kèm có URL công khai, không cần đăng nhập để tải. Mặc định file là private (cần session). |

---

### 2.6 Hiển thị giao diện

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Icon** | Data | *(trống)* | Class icon hiển thị trên menu sidebar và module page. Dùng Frappe icon set hoặc FontAwesome (vd: `fa fa-file-text`, `octicon octicon-file`). |
| **Editable Grid** | Check | `0` | Cho phép chỉnh sửa trực tiếp trong **Grid View** (dạng bảng) của Child Table mà không cần mở dialog. Tiện lợi nhưng hạn chế không gian hiển thị. |
| **Has Web View** | Check | `0` | Mỗi bản ghi có **trang web riêng** (portal page) với URL dạng `/doctype-name/record-name`. Cần tạo template HTML tương ứng. |
| **Show Preview Popup** | Check | `0` | Hiển thị **popup xem trước** khi hover chuột vào link đến bản ghi. Hiển thị một số field quan trọng. |
| **Force Re-route to Default View** | Check | `0` | Ép chuyển hướng về List View mặc định thay vì nhớ view cuối cùng (Report View, Kanban...). |
| **Hide Toolbar** | Check | `0` | Ẩn toàn bộ thanh toolbar (Save, Submit, Cancel, Amend...) trên form. |
| **Read Only** | Check | `0` | Toàn bộ form **chỉ đọc** bất kể quyền write. Thường dùng cho DocType hiển thị dữ liệu tổng hợp. |
| **In Create** | Check | `0` | Không thể tạo bản ghi mới từ giao diện (nút New bị ẩn). Chỉ tạo qua code. |
| **Translated DocType** | Check | `0` | Đánh dấu DocType đã có bản dịch tích hợp sẵn trong hệ thống. |
| **Show Dashboard** | *(trong field)* | `0` | Trường có `show_dashboard = 1` sẽ hiển thị widget dashboard (biểu đồ, số liệu tổng hợp) ở đầu form. |

---

### 2.7 States (Trạng thái)

States dùng để **tô màu** indicator trên List View theo giá trị của một field (thường là `status`). Không ảnh hưởng đến logic, chỉ là cấu hình hiển thị.

**Cách thiết lập:**

```
Field: status
Value: "Submitted" → Color: Blue
Value: "Paid"      → Color: Green
Value: "Overdue"   → Color: Red
Value: "Draft"     → Color: Light (mặc định)
```

**Các màu hỗ trợ:**

| Màu | Mã | Ý nghĩa thường dùng |
|-----|----|---------------------|
| Green | `green` | Hoàn thành, đã thanh toán |
| Blue | `blue` | Đang xử lý, đã submit |
| Red | `red` | Quá hạn, từ chối, lỗi |
| Orange | `orange` | Cảnh báo, chờ xử lý |
| Yellow | `yellow` | Cần chú ý |
| Grey | `grey` | Đã hủy, không hoạt động |
| Purple | `purple` | Trạng thái đặc biệt |

---

### 2.8 Links (Liên kết ngược)

Định nghĩa DocType nào **có field Link trỏ đến** DocType này, để hệ thống hiển thị danh sách liên quan trong tab "Connections" hoặc dashboard.

| Cột | Mô tả |
|-----|-------|
| **Link DocType** | DocType có field trỏ ngược lại DocType hiện tại. |
| **Link Fieldname** | Tên field trong Link DocType chứa reference. |
| **Group** | Nhóm hiển thị trong dashboard (vd: "Reference", "Payment"). |
| **Hidden** | Ẩn liên kết này khỏi dashboard. |
| **Is Child Table** | Link DocType là child table. |

**Ví dụ:** Sales Invoice định nghĩa link:
- Link DocType: `POS Invoice`
- Link Fieldname: `consolidated_invoice`

→ Khi xem Sales Invoice, tab Connections hiển thị danh sách POS Invoice liên quan.

---

### 2.9 Permissions (Phân quyền)

Phân quyền theo **Role** (nhóm người dùng). Có thể có nhiều dòng permission cho nhiều role khác nhau.

#### Các loại quyền:

| Quyền | Mô tả |
|-------|-------|
| **Read** | Xem danh sách và chi tiết bản ghi. |
| **Write** | Chỉnh sửa bản ghi ở trạng thái Draft. |
| **Create** | Tạo bản ghi mới. |
| **Delete** | Xóa bản ghi (thường chỉ Draft). |
| **Submit** | Submit bản ghi (chuyển sang Submitted). Chỉ có tác dụng khi `Is Submittable = 1`. |
| **Cancel** | Hủy bản ghi đã Submit. |
| **Amend** | Tạo phiên bản sửa đổi từ bản đã Cancel. |
| **Report** | Xem Report liên quan đến DocType này. |
| **Import** | Dùng Data Import để nhập dữ liệu. |
| **Export** | Xuất dữ liệu ra CSV/Excel. |
| **Print** | In bản ghi. |
| **Email** | Gửi email từ bản ghi. |
| **Share** | Chia sẻ bản ghi với user khác. |
| **Set User Permissions** | Thiết lập User Permissions cho DocType này. |

#### Permission Level (permlevel):

Cơ chế **bảo mật cấp field**. Mỗi field có `permlevel` (0, 1, 2...). Một role chỉ thấy/sửa được field khi có permission tương ứng ở level đó.

```
permlevel = 0  → Tất cả user có Read đều thấy
permlevel = 1  → Chỉ role có permission level 1 mới thấy
permlevel = 2  → Chỉ role có permission level 2 mới thấy
```

Dùng để ẩn các field nhạy cảm (salary, cost price...) khỏi một số role.

#### If Owner:

Khi `if_owner = 1`, permission chỉ áp dụng nếu user là **người tạo** bản ghi. Dùng cho trường hợp: user chỉ được sửa bản ghi do chính mình tạo.

---

### 2.10 Database Engine

| Setting | Mô tả |
|---------|-------|
| **InnoDB** *(mặc định)* | Hỗ trợ transaction, foreign key, row-level locking. **Luôn dùng InnoDB.** |
| **MyISAM** | Không hỗ trợ transaction. Không nên dùng trong Frappe. |

---

## 3. Settings cấp Field (Trường dữ liệu)

### 3.1 Nhận dạng Field

| Setting | Kiểu | Mô tả chi tiết |
|---------|------|----------------|
| **Label** | Data | Nhãn hiển thị trên form. Có thể chứa khoảng trắng và ký tự đặc biệt. Được dịch theo ngôn ngữ hệ thống. |
| **Fieldname** | Data | Tên kỹ thuật, là **tên cột trong database**. Chỉ dùng chữ thường, số, dấu gạch dưới. Không đổi sau khi có dữ liệu (trừ khi migrate). Không có khoảng trắng. Ví dụ: `customer_name`, `posting_date`. |
| **Fieldtype** | Select | Loại dữ liệu. Xem chi tiết ở mục 3.2. |
| **Options** | Text | Ý nghĩa thay đổi tùy theo Fieldtype. Xem mục 3.2. |

---

### 3.2 Loại Field (Field Type)

#### Nhóm Layout (Không lưu dữ liệu)

| Fieldtype | Mô tả |
|-----------|-------|
| **Section Break** | Tạo **vùng mới** với đường kẻ ngang phân cách. Có thể có Label (tiêu đề vùng), Icon, và thuộc tính `collapsible`. Các field phía sau thuộc section này cho đến khi gặp Section Break mới. |
| **Column Break** | Chia layout thành **cột**. Các field sau Column Break xuất hiện ở cột tiếp theo (thường là 2 cột). |
| **Tab Break** | Tạo **tab mới** trên form (Frappe v14+). Label của field chính là tên tab. |
| **Fold** | Gấp/ẩn các field bên dưới cho đến cuối form (ít dùng). |
| **Heading** | Hiển thị text làm **tiêu đề** trong form, không lưu dữ liệu. |
| **HTML** | Nhúng HTML tĩnh vào form (hướng dẫn, thông báo). |

#### Nhóm Text

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Data** | `VARCHAR(140)` | Chuỗi văn bản ngắn (tối đa 140 ký tự). Dùng cho tên, mã số, email, phone... Hỗ trợ `options` để validate định dạng: `Email`, `Phone`, `URL`, `Name`, `Barcode`. |
| **Small Text** | `TEXT` | Văn bản ngắn hơn Long Text, hiển thị dưới dạng textarea nhỏ. |
| **Text** | `LONGTEXT` | Văn bản dài không định dạng. |
| **Long Text** | `LONGTEXT` | Tương tự Text. |
| **Text Editor** | `LONGTEXT` | Trình soạn thảo **WYSIWYG** (rich text). Lưu HTML. Dùng cho mô tả, nội dung email, terms. |
| **Markdown Editor** | `LONGTEXT` | Soạn thảo **Markdown**, render thành HTML khi hiển thị. |
| **Code** | `LONGTEXT` | Editor code với syntax highlighting. `options` = ngôn ngữ (`Python`, `JavaScript`, `HTML`, `JSON`...). |
| **Password** | `TEXT` | Ô nhập mật khẩu. Giá trị được mã hóa khi lưu. |

#### Nhóm Số

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Int** | `INT(11)` | Số nguyên. |
| **Float** | `DECIMAL(21,9)` | Số thực, độ chính xác tùy setting `precision`. |
| **Currency** | `DECIMAL(21,9)` | Số tiền. `options` = tên field chứa mã tiền tệ (vd: `currency`). Tự động format theo locale. |
| **Percent** | `DECIMAL(21,9)` | Phần trăm. Hiển thị ký hiệu `%`. |
| **Rating** | `DECIMAL(3,1)` | Đánh giá sao (0–5). |
| **Duration** | `VARCHAR(18)` | Khoảng thời gian (giờ:phút:giây). |

#### Nhóm Ngày & Giờ

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Date** | `DATE` | Ngày (YYYY-MM-DD). `default = Today` để mặc định hôm nay. |
| **Time** | `TIME` | Giờ (HH:MM:SS). |
| **Datetime** | `DATETIME` | Ngày giờ đầy đủ. |

#### Nhóm Lựa chọn

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Select** | `VARCHAR(140)` | Dropdown. `options` = danh sách các lựa chọn, mỗi dòng một giá trị. Dòng đầu trống = không bắt buộc chọn. |
| **Autocomplete** | `VARCHAR(140)` | Ô nhập có gợi ý từ `options`. Vẫn cho phép nhập giá trị tùy ý. |
| **Check** | `INT(1)` | Checkbox. Giá trị `0` hoặc `1`. `default = 0` hoặc `1`. |
| **Color** | `VARCHAR(140)` | Bộ chọn màu, lưu mã hex (vd: `#FF0000`). |

#### Nhóm File & Hình ảnh

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Attach** | `TEXT` | Upload file. Lưu URL của file. |
| **Attach Image** | `TEXT` | Upload ảnh. Hiển thị thumbnail trong form và list view. |
| **Image** | `VARCHAR(140)` | Hiển thị ảnh từ URL (không upload). `options` = tên field chứa URL ảnh. |
| **Signature** | `LONGTEXT` | Ký tên điện tử. Lưu dạng base64 image. |
| **Barcode** | `LONGTEXT` | Hiển thị và quét barcode/QR code. |

#### Nhóm Quan hệ

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Link** | `VARCHAR(140)` | Liên kết đến một DocType khác. `options` = tên DocType. Lưu giá trị `name` của bản ghi được chọn. |
| **Dynamic Link** | `VARCHAR(140)` | Link đến DocType được xác định động bởi một field khác. `options` = tên field chứa DocType name. |
| **Table** | — | Nhúng **Child Table** vào form. `options` = tên DocType con (phải là Child Table). |
| **Table MultiSelect** | — | Chọn nhiều bản ghi từ một DocType, lưu dạng bảng con. |

#### Nhóm Địa lý

| Fieldtype | Lưu DB | Mô tả |
|-----------|--------|-------|
| **Geolocation** | `LONGTEXT` | Chọn vị trí trên bản đồ. Lưu GeoJSON. |

#### Đặc biệt

| Fieldtype | Mô tả |
|-----------|-------|
| **Read Only** | Hiển thị giá trị nhưng không cho sửa. Thường dùng với `fetch_from`. |
| **Button** | Nút bấm. `options` = tên JavaScript function sẽ được gọi. |

---

### 3.3 Bắt buộc & Ràng buộc

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Mandatory** (`reqd`) | Check | `0` | Field **bắt buộc nhập**. Không thể lưu nếu để trống. Hiển thị dấu `*` đỏ. |
| **Mandatory Depends On** | JS Expression | *(trống)* | Field chỉ bắt buộc khi điều kiện JS thỏa mãn. Ví dụ: `eval: doc.is_return == 1`. |
| **Unique** | Check | `0` | Giá trị phải **duy nhất** trong toàn bảng. Tạo UNIQUE INDEX trong DB. Cẩn thận khi dùng với field có thể null. |
| **Non Negative** | Check | `0` | Giá trị không được âm (áp dụng cho Int, Float, Currency). |
| **Set only once** | Check | `0` | Chỉ có thể nhập giá trị **một lần khi tạo mới**. Sau khi lưu lần đầu, field bị khóa. |
| **No Copy** | Check | `0` | Field bị **bỏ qua khi Duplicate** (copy) bản ghi. Dùng cho các field như `status`, `posting_date`, `name`. |
| **Ignore XSS Filter** | Check | `0` | Bỏ qua lọc XSS cho field này. Dùng khi cần lưu HTML từ trusted source. **Cẩn thận bảo mật.** |
| **Ignore User Permissions** | Check | `0` | Field Link này không bị lọc theo User Permissions. |
| **Length** | Int | `0` | Giới hạn độ dài tối đa cho field Data (mặc định 140). `0` = dùng mặc định. |

---

### 3.4 Giá trị mặc định & Fetch

| Setting | Kiểu | Mô tả chi tiết |
|---------|------|----------------|
| **Default** | Data | Giá trị mặc định khi tạo bản ghi mới. Các giá trị đặc biệt: `Today` (ngày hôm nay), `Now` (datetime hiện tại), `__user` (user hiện tại), `{fieldname}` (giá trị từ field khác). |
| **Fetch From** | Data | Tự động **lấy giá trị từ field của DocType được Link**. Cú pháp: `link_fieldname.target_fieldname`. Ví dụ: `customer.customer_name` — khi chọn customer, tự điền customer_name. |
| **Fetch If Empty** | Check | `0` | Chỉ fetch nếu field hiện đang trống. Khi `0`, luôn ghi đè giá trị mỗi khi Link thay đổi. |
| **Translatable** | Check | `0` | Giá trị của field có thể được dịch sang ngôn ngữ khác qua Translation tool. |

---

### 3.5 Hiển thị & Ẩn

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Hidden** | Check | `0` | Ẩn hoàn toàn field khỏi form. Vẫn tồn tại trong DB và có thể đọc qua code. |
| **Depends On** | JS Expression | *(trống)* | Field chỉ **hiển thị** khi điều kiện thỏa mãn. Ví dụ: `eval: doc.is_return == 1` hoặc `fieldname` (hiển thị khi field có giá trị). Hỗ trợ `eval:` cho biểu thức phức tạp. |
| **Read Only** | Check | `0` | Field chỉ đọc, không thể sửa. Vẫn hiển thị giá trị. |
| **Read Only Depends On** | JS Expression | *(trống)* | Field chỉ đọc khi điều kiện JS thỏa mãn. |
| **Allow on Submit** | Check | `0` | Cho phép chỉnh sửa field sau khi bản ghi đã được **Submit**. Dùng cho các field vẫn cần cập nhật sau submit (letter_head, remarks...). |
| **Bold** | Check | `0` | Hiển thị giá trị **in đậm** trong List View (làm nổi bật cột). |
| **Collapsible** | Check | `0` | Áp dụng cho **Section Break**: Section có thể thu gọn/mở rộng. Mặc định mở. |
| **Collapsible Depends On** | JS Expression | *(trống)* | Section thu gọn trừ khi điều kiện thỏa. Ví dụ: `eval: doc.advances.length > 0`. |
| **Hide Border** | Check | `0` | Áp dụng cho Section Break: ẩn đường kẻ phân cách. |
| **Hide Days** | Check | `0` | Áp dụng cho Duration field: ẩn phần "ngày". |
| **Hide Seconds** | Check | `0` | Áp dụng cho Time/Duration: ẩn phần "giây". |

---

### 3.6 Phân quyền cấp Field

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Permlevel** | Int | `0` | Cấp phân quyền của field. Field chỉ hiển thị/chỉnh sửa được với role có permission tương ứng ở permlevel này. Ví dụ: field lương đặt `permlevel = 1`, chỉ HR Manager có Read/Write level 1 mới thấy. |
| **Ignore User Permissions** | Check | `0` | Bỏ qua User Permissions cho Link Field này. Ví dụ: field `company` có thể bỏ qua user permission để user thấy tất cả company. |

---

### 3.7 Tìm kiếm & Danh sách

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **In List View** | Check | `0` | Hiển thị field như một **cột** trong List View mặc định. Nên giới hạn 3–5 field để tránh quá tải. |
| **In Filter** | Check | `0` | Field có thể dùng làm **điều kiện lọc** trong List View (Filter panel). |
| **In Standard Filter** | Check | `0` | Hiển thị field như một ô lọc **ngay trên List View** (Standard Filter bar), không cần mở Filter panel. |
| **In Global Search** | Check | `0` | Giá trị của field được đưa vào index **Global Search**. Dùng cho các field định danh quan trọng. |
| **In Preview** | Check | `0` | Hiển thị field trong **popup xem trước** khi hover vào link (yêu cầu `Show Preview Popup = 1` ở DocType). |
| **Search Index** | Check | `0` | Tạo **database index** cho field này. Bắt buộc cho các field thường xuyên dùng trong WHERE, ORDER BY, JOIN. Tăng hiệu năng nhưng tốn thêm dung lượng. |
| **Remember Last Selected Value** | Check | `0` | Hệ thống nhớ giá trị cuối cùng user chọn cho field này, tự điền khi tạo bản ghi mới. Hữu ích cho field như `company`, `warehouse`. |

---

### 3.8 In ấn

| Setting | Kiểu | Mặc định | Mô tả chi tiết |
|---------|------|----------|----------------|
| **Print Hide** | Check | `0` | Ẩn field trên **Print Format** (bản in). Field vẫn hiển thị trên form. Dùng cho các field nội bộ không cần in. |
| **Print Hide If No Value** | Check | `0` | Ẩn trên bản in **chỉ khi** field không có giá trị. Nếu có giá trị thì vẫn in. |
| **Report Hide** | Check | `0` | Ẩn field trong **Report View** (xem dạng bảng tổng hợp). |
| **Allow Bulk Edit** | Check | `0` | Cho phép chỉnh sửa field này cho **nhiều bản ghi cùng lúc** từ List View (Bulk Edit). |
| **Precision** | Select | *(trống)* | Số chữ số thập phân cho Float/Currency (0–9). Ghi đè setting precision mặc định của hệ thống. |

---

### 3.9 Giao diện & Định dạng

| Setting | Kiểu | Mô tả chi tiết |
|---------|------|----------------|
| **Description** | Small Text | Mô tả ngắn hiển thị **dưới field** trên form, dạng text màu xám. Dùng để hướng dẫn người dùng. |
| **Documentation URL** | Data | URL liên kết đến tài liệu hướng dẫn, hiển thị kèm field (icon `?`). |
| **Width** | Data | Độ rộng của field trong grid/inline form (vd: `150px`, `50%`). |
| **Columns** | Int | Số cột chiếm trong Grid View (Child Table). Tổng các cột nên ≤ 10. `0` = tự động. |
| **Max Height** | Data | Chiều cao tối đa của field (áp dụng cho Text, Long Text). Ví dụ: `300px`. |
| **Allow in Quick Entry** | Check | `0` | Field hiển thị trong **Quick Entry Dialog**. Cần bật `Quick Entry = 1` ở DocType level. |
| **Sort Options** | Check | `0` | Áp dụng cho Link Field: cho phép sort danh sách gợi ý. |
| **Show Dashboard** | Check | `0` | Hiển thị widget dashboard cho field này ở đầu form. |

---

### 3.10 Depends On (Hiển thị có điều kiện)

Field `Depends On` và `Mandatory Depends On` nhận biểu thức JavaScript:

#### Cú pháp đơn giản (chỉ tên field):
```
fieldname
```
Field hiển thị khi `fieldname` có giá trị truthy.

#### Cú pháp eval:
```javascript
eval: doc.fieldname == "value"
eval: doc.fieldname != "" && doc.other_field > 0
eval: !doc.is_return
eval: doc.docstatus == 0
eval: doc.items && doc.items.length > 0
```

#### Các biến có sẵn trong eval:
| Biến | Ý nghĩa |
|------|---------|
| `doc` | Đối tượng document hiện tại |
| `doc.docstatus` | `0` = Draft, `1` = Submitted, `2` = Cancelled |
| `doc.is_new()` | `true` nếu bản ghi chưa được lưu |
| `frappe.session.user` | User đang đăng nhập |
| `frappe.boot.sysdefaults` | Cấu hình hệ thống |

#### Ví dụ thực tế:
```javascript
// Hiển thị khi là Credit Note
eval: doc.is_return && doc.return_against

// Chỉ hiển thị khi chưa submit
eval: doc.docstatus == 0

// Hiển thị khi chọn loại khách hàng cụ thể
eval: doc.customer_type == "Individual"

// Hiển thị khi bảng con có dữ liệu
eval: doc.items && doc.items.length > 0
```

---

## 4. Tham chiếu nhanh theo Field Type

### Field Type → Options

| Fieldtype | Options chứa gì | Ví dụ |
|-----------|----------------|-------|
| **Link** | Tên DocType | `Customer`, `Item`, `Account` |
| **Dynamic Link** | Tên field chứa DocType | `reference_doctype` |
| **Select** | Danh sách lựa chọn (mỗi dòng một giá trị) | `Draft\nSubmitted\nCancelled` |
| **Table** | Tên Child DocType | `Sales Invoice Item` |
| **Table MultiSelect** | Tên Child DocType | `Sales Team` |
| **Currency** | Tên field chứa mã tiền (hoặc `Company:company:default_currency`) | `currency` |
| **Data** | Loại validation | `Email`, `Phone`, `URL`, `Name` |
| **Code** | Ngôn ngữ | `Python`, `JavaScript`, `HTML`, `JSON` |
| **Image** | Tên field chứa URL ảnh | `image` |
| **Button** | Tên JS function | `calculate_total` |
| **Section Break** | Class icon | `fa fa-user` |

---

### Khi nào dùng loại Field nào?

| Nhu cầu | Field Type nên dùng |
|---------|-------------------|
| Tên người, địa chỉ ngắn | `Data` |
| Mô tả dài | `Text Editor` hoặc `Long Text` |
| Email | `Data` với `options = Email` |
| Số điện thoại | `Data` với `options = Phone` |
| Số tiền | `Currency` |
| Số lượng | `Float` hoặc `Int` |
| Ngày tháng | `Date` |
| Trạng thái cố định | `Select` |
| Trạng thái linh động | `Link` đến master DocType |
| Link đến bản ghi | `Link` |
| Link động (nhiều DocType) | `Dynamic Link` |
| Bảng con | `Table` |
| Có/Không | `Check` |
| Ảnh đại diện | `Attach Image` |
| File đính kèm | `Attach` |
| Cấu hình layout | `Section Break`, `Column Break`, `Tab Break` |

---

## 5. Các Pattern Thường Gặp Khi Custom

### Pattern 1: Auto-fetch từ Link Field

```
Tình huống: Chọn Customer → tự điền Customer Name, Tax ID

customer        [Link → Customer]
customer_name   [Data, fetch_from = "customer.customer_name", read_only = 1]
tax_id          [Data, fetch_from = "customer.tax_id", read_only = 1]
```

### Pattern 2: Field hiển thị có điều kiện

```
Tình huống: Chỉ hiển thị "Return Against" khi là Credit Note

is_return         [Check]
return_against    [Link → Sales Invoice, depends_on = "eval: doc.is_return == 1"]
```

### Pattern 3: Mandatory theo điều kiện

```
Tình huống: PO Number bắt buộc khi Customer Type là Company

customer_type   [Select: Individual / Company]
po_number       [Data, mandatory_depends_on = "eval: doc.customer_type == 'Company'"]
```

### Pattern 4: Quick Entry Form

```
Bước 1: Bật Quick Entry ở DocType settings
Bước 2: Đánh dấu allow_in_quick_entry = 1 cho các field cần thiết

Ví dụ Customer quick entry:
- customer_name  [allow_in_quick_entry = 1]
- customer_type  [allow_in_quick_entry = 1]
- mobile_no      [allow_in_quick_entry = 1]
```

### Pattern 5: Field nhạy cảm (permlevel)

```
Tình huống: Chỉ Finance Manager mới xem được giá vốn

base_rate  [Currency, permlevel = 1]

→ Thêm Permission cho Finance Manager với Read/Write level 1
→ Các role khác chỉ có level 0, không thấy field này
```

### Pattern 6: Status với States

```
status [Select]:
  Draft
  Pending Approval
  Approved
  Rejected
  Cancelled

States:
  Draft         → Grey
  Pending       → Orange
  Approved      → Green
  Rejected      → Red
  Cancelled     → Grey
```

### Pattern 7: Child Table

```
DocType cha: Work Order
  items [Table → Work Order Item]

DocType con: Work Order Item  (Is Child Table = 1)
  item_code    [Link → Item]
  qty          [Float]
  uom          [Link → UOM]
  rate         [Currency]
```

### Pattern 8: Naming Series

```
Naming Rule: By Naming Series
Autoname: naming_series:

Field naming_series [Select]:
  WO-.YYYY.-
  WO-INT-.YYYY.-
  WO-EXT-.YYYY.-

→ WO-2024-0001, WO-INT-2024-0001
```

---

## 6. Checklist Trước Khi Lưu DocType

### ✅ Cấp DocType

- [ ] Tên DocType đặt đúng PascalCase, không xung đột với DocType có sẵn
- [ ] Module chọn đúng
- [ ] Naming Rule phù hợp với yêu cầu nghiệp vụ
- [ ] `Is Submittable` chỉ bật khi thực sự cần vòng đời submit
- [ ] `Is Child Table` chỉ bật cho bảng con, không có logic độc lập
- [ ] Search Fields chứa các field người dùng hay tìm kiếm
- [ ] Sort Field có index
- [ ] `Track Changes` bật cho DocType quan trọng cần audit trail
- [ ] Permission đã thiết lập đủ cho các role liên quan

### ✅ Cấp Field

- [ ] Fieldname đặt đúng: chữ thường, không dấu, không khoảng trắng
- [ ] Fieldtype phù hợp với dữ liệu lưu trữ
- [ ] Field Link đã có `options` là DocType đúng
- [ ] Field Select đã điền `options` đầy đủ
- [ ] Field Currency đã có `options` trỏ đến field mã tiền
- [ ] Field quan trọng bật `search_index`
- [ ] Field dùng trong List View bật `in_list_view` (tối đa 5 field)
- [ ] Field `fetch_from` dùng đúng cú pháp `link_field.target_field`
- [ ] `Mandatory` field có `default` hoặc hướng dẫn rõ ràng
- [ ] Field nhạy cảm đã set `permlevel` phù hợp
- [ ] Layout có Section Break / Column Break hợp lý
- [ ] `Depends On` dùng đúng cú pháp `eval:`
- [ ] Field không cần in đã bật `print_hide`
- [ ] Field `no_copy` bật cho các field không nên copy (date, status, series)

### ✅ Kiểm tra sau khi lưu

- [ ] Migrate database: `bench migrate`
- [ ] Reload browser (Ctrl+Shift+R)
- [ ] Tạo thử bản ghi mới — kiểm tra form hiển thị đúng
- [ ] Test fetch_from hoạt động khi chọn Link
- [ ] Test Depends On hiển thị/ẩn đúng điều kiện
- [ ] Test permission với từng role
- [ ] Test Quick Entry (nếu bật)
- [ ] Kiểm tra List View hiển thị đúng cột

---

## Phụ lục: Các lệnh hữu ích

```bash
# Migrate sau khi thay đổi DocType
bench --site [sitename] migrate

# Export DocType ra file JSON (để version control)
bench --site [sitename] export-fixtures

# Reload DocType cache
bench --site [sitename] clear-cache

# Xem log lỗi
bench --site [sitename] tail-logs
```

---

*Tài liệu này được tổng hợp cho Frappe v14/v15. Một số setting có thể khác biệt ở phiên bản cũ hơn.*
