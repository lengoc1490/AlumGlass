# AlumGlass ERP — BỔ SUNG v25.1: `AL DESIGN REVISION`

> **Mục đích tài liệu này:** vá khoảng trống đã xác định trong review v25 — hệ thống chưa có nơi ghi nhận chính thức các thay đổi **kỹ thuật/spec** từ CĐT (phụ lục thiết kế) khi thay đổi đó **không nhất thiết có tác động giá**, và chưa có "bản thiết kế cuối cùng" tổng hợp theo dự án.
> **Không phá vỡ** bất kỳ nguyên tắc/quyết định nào của v25 — chỉ thêm 1 DocType Master + 1 Child + 1 Query Report + vài field liên kết.
> **Cách dùng tài liệu này:** mỗi mục dưới đây ghi rõ **chèn vào đâu** trong `AlumGlass_ERP_CANONICAL_v25.md` (theo số mục La Mã đã có), kèm lý do thiết kế. Sau khi chèn xong, gộp thành v25.1.

---

## 0. BẢNG VỊ TRÍ CHÈN (tổng quan)

| # | Nội dung thêm | Vị trí chèn trong v25 |
|---|---|---|
| 1 | Mục lục — cập nhật mô tả mục XXVII | MỤC LỤC, dòng liệt kê Phần F |
| 2 | QĐ-36 (quyết định kiến trúc mới) | Cuối bảng "Quyết định kiến trúc" trong §I, sau QĐ-35 |
| 3 | 2 DocType mới vào danh mục (Tầng 6, nhóm 6E) | §III, bảng "Tầng 6 — Module nghiệp vụ", sau dòng #59 (`AL Handover Acceptance`) |
| 4 | Cập nhật tổng số DocType | §III, dòng "**Tổng: 61 DocType...**" |
| 5 | Field schema đầy đủ `AL Design Revision` + `AL Design Revision Line` | **Mục mới §27.4**, chèn trong §XXVII, ngay sau §27.3 (AL Change Order) và trước §XXVIII |
| 6 | Field mới `source_design_revision` trên `AL Change Order` | §27.3, bảng field `AL Change Order (Master)` |
| 7 | Sửa mô tả Gate của Site Survey | §25.7, đoạn "**Gate:**" |
| 8 | Report "Final Design Register" | §XXIV Reporting |
| 9 | Cập nhật Quy trình đầu-cuối | §XXXI, dòng "Phát sinh nếu có" |
| 10 | Test scenario #11 | §XXXIII, cuối danh sách |
| 11 | Checklist Go-live | §XXXVI, thêm 1 dòng |

---

## 1. LÝ DO THIẾT KẾ (đọc trước khi chèn)

**Vấn đề gốc:** `AL Change Order` (§27.3) hiện tại là **DocType duy nhất** ghi nhận thay đổi sau khi SO đã chốt, và hành vi mặc định của nó là **tạo Sales Order bổ sung**. Điều này đúng khi thay đổi có tác động giá, nhưng sai khi CĐT chỉ đổi spec kỹ thuật thuần túy (đổi màu, đổi mã kính, đổi thương hiệu tay nắm trong cùng nhóm giá đã duyệt) — những thay đổi này **vẫn cần ghi nhận chính thức** (ai yêu cầu, văn bản nào, áp dụng từ khi nào) nhưng không nên bị ép đi qua bộ máy thương mại (SO mới, Payment Schedule mới).

Nếu không tách riêng, chỉ có 2 lựa chọn đều tệ:
- (a) Vẫn tạo Change Order/SO cho mọi thay đổi dù giá = 0 → làm nhiễu dữ liệu thương mại, báo cáo tổng giá trị hợp đồng (§27.3 cuối) bị "rác" bởi các SO giá trị 0.
- (b) Bỏ qua, xử lý ngoài hệ thống (email/Zalo) → mất dấu vết, không thể trả lời "cấu hình kỹ thuật cuối cùng của công trình là gì" khi nghiệm thu hoặc khi có tranh chấp.

**7 quyết định thiết kế cụ thể và lý do:**

| # | Quyết định | Vì sao |
|---|---|---|
| D1 | Tách `AL Design Revision` khỏi `AL Change Order`, liên kết **một chiều, tùy chọn** (`linked_change_order` trên Design Revision — không bắt buộc ngược lại) | Không phải Change Order nào cũng có văn bản CĐT đứng sau (VD Sales tự thương lượng thêm số lượng); không phải Design Revision nào cũng có tác động giá. Ép 1-1 hai chiều sẽ sai trong cả hai hướng. |
| D2 | Cờ `has_price_impact` ở **header**, nhưng cờ `requires_new_bom_version` ở **line** | Một phụ lục CĐT thường gồm nhiều thay đổi cùng lúc: có dòng chỉ đổi biến (đổi màu — dùng ConfigSnapshot mới, không đụng BOM Version), có dòng đổi cấu trúc (thêm thanh ngang — bắt buộc BOM Version mới qua Workflow §8.4). Nếu đặt cờ ở header, buộc cả phụ lục phải đi qua Workflow nặng dù chỉ 1/5 dòng cần. |
| D3 | Không dùng `Workflow` (core) cho trạng thái, dùng `Select` + validate đơn giản (giống `al_discount_approval_ref`, §18) | `Workflow` core phù hợp cho vòng đời **nội bộ nhiều cấp duyệt kỹ thuật** (BOM/Rule Version). Design Revision cần xác nhận **từ bên ngoài** (CĐT ký) — bản chất giống biên bản pháp lý (`AL Handover Acceptance`) hơn là version nội bộ. Dùng Workflow ở đây là over-engineering, vi phạm tinh thần Nguyên tắc #30 (không dùng cơ chế nặng hơn mức cần). |
| D4 | `customer_confirmation` (Attach) copy đúng pattern của `AL Handover Acceptance.customer_signature` | Tái dùng quy ước đã có trong hệ thống thay vì phát minh mới — giảm tải nhận thức cho đội dev, nhất quán về mặt "bằng chứng pháp lý có chữ ký" giữa 2 DocType có bản chất tương tự. |
| D5 | `AL Design Revision Line` dùng `field_changed`/`old_value`/`new_value` dạng Data tự do, không làm schema cứng theo từng loại field | Thay đổi spec trải khắp mọi loại dòng (NHOM/KINH/VTP/PK), mỗi loại có field riêng. Làm schema cứng sẽ phải sửa DocType mỗi khi có loại thay đổi mới. Cách này nhất quán với cách `ConfigSnapshot.drift_details` (§IV.17) đã lưu JSON linh hoạt cho mục đích tương tự (audit). |
| D6 | **Site Survey lệch dung sai cũng phải sinh ra `AL Design Revision`** (không chỉ đi thẳng Change Order/BOM Version như v25 hiện tại) | Nếu không, "Final Design Register" (mục 5 bên dưới) sẽ chỉ thấy thay đổi do CĐT yêu cầu mà bỏ sót thay đổi do thực tế công trình — bản thiết kế cuối cùng sẽ không đầy đủ. Nguyên tắc: **mọi sai lệch so với ConfigSnapshot gốc, bất kể nguồn gốc, đều đi qua 1 điểm ghi nhận duy nhất.** |
| D7 | Không tạo DocType `AL Final Design Register` — dùng **Query Report** | Đúng tinh thần Nguyên tắc #30/§XXIII/§XXIV: dữ liệu này là tổng hợp read-only từ 3 nguồn có sẵn (`Sales Order Item.al_bom_version`, `AL Design Revision Line`, `AL Site Survey Line`) — không cần lưu trữ riêng, không cần DocType mới. |

---

## 2. NỘI DUNG CHÈN VÀO §XXVII — MỤC MỚI **27.4**

*(Chèn nguyên văn phần sau vào tài liệu gốc, ngay sau §27.3 "AL Change Order — Tạo Sales Order bổ sung" và trước §XXVIII "Module kế toán lãi lỗ")*

---

### 27.4 AL DESIGN REVISION — GHI NHẬN THAY ĐỔI THIẾT KẾ/SPEC (KHÔNG NHẤT THIẾT CÓ TÁC ĐỘNG GIÁ)

**Nguyên tắc bổ sung (§27.4):** Mọi sai lệch so với ConfigSnapshot đã chốt — dù xuất phát từ yêu cầu CĐT (phụ lục thiết kế) hay từ thực tế công trình (Site Survey, §25.7) — đều phải có **1 bản ghi `AL Design Revision`** làm điểm sự thật duy nhất, độc lập với việc thay đổi đó có tạo `AL Change Order` hay không.

**AL Design Revision (Master):**

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| project | Link → Project | ✓ | |
| revision_no | Int (auto-tăng theo project) | ✓ | |
| source_type | Select | ✓ | CUSTOMER_REQUEST / SITE_SURVEY_DEVIATION / INTERNAL_CORRECTION |
| source_document | Attach | | Phụ lục/bản vẽ CĐT gửi — bắt buộc nếu `source_type=CUSTOMER_REQUEST` |
| source_site_survey | Link → AL Site Survey | | Bắt buộc nếu `source_type=SITE_SURVEY_DEVIATION` |
| request_date | Date | ✓ | |
| requested_by | Data | | Tên/vai trò phía CĐT yêu cầu |
| change_description | Small Text | ✓ | |
| has_price_impact | Check (default 0) | | |
| linked_change_order | Link → AL Change Order | | **Bắt buộc nếu `has_price_impact=1`** (validate khi Confirm) |
| status | Select | ✓ | Draft / Confirmed / Applied / Rejected |
| customer_confirmation | Attach | | Xác nhận/chữ ký CĐT — bắt buộc trước khi chuyển `Confirmed` nếu `source_type=CUSTOMER_REQUEST` |
| confirmed_date | Date | | |
| applied_date | Date | | Ngày ConfigSnapshot mới thực sự được tính lại cho mọi dòng ảnh hưởng |
| al_design_revision_lines | Table → AL Design Revision Line | | |

**AL Design Revision Line (Child):**

| fieldname | fieldtype | reqd | Mô tả |
|---|---|---|---|
| sales_order_item | Link → Sales Order Item | ✓ | Dòng bị ảnh hưởng |
| field_changed | Data | ✓ | VD `al_mau_nhom`, `kinh_canh.glass_code`, `pk_tay_nam.item_code` |
| old_value | Data | | |
| new_value | Data | ✓ | |
| requires_new_bom_version | Check (default 0) | | Bật nếu thay đổi động chạm cấu trúc Profile Set/PK Set dùng chung, không chỉ giá trị biến |
| new_bom_version | Link → AL BOM Version | | **Bắt buộc nếu `requires_new_bom_version=1`** và version đó phải ở `workflow_state=Published` (§8.4) trước khi Design Revision này chuyển `Applied` |
| note | Small Text | | |

**Quy tắc validate:**

```
on AL Design Revision.validate():
    if has_price_impact and not linked_change_order:
        throw("Thay đổi có tác động giá phải liên kết AL Change Order")
    if source_type == CUSTOMER_REQUEST and status == "Confirmed" and not customer_confirmation:
        throw("Cần đính kèm xác nhận của CĐT trước khi Confirm")
    for line in al_design_revision_lines:
        if line.requires_new_bom_version and not line.new_bom_version:
            throw(f"Dòng {line.sales_order_item} cần chỉ định BOM Version mới")
        if line.new_bom_version and line.new_bom_version.workflow_state != "Published":
            throw("BOM Version tham chiếu chưa Published")

on AL Design Revision.status change to "Applied":
    for line in al_design_revision_lines:
        trigger BomOrchestrator recalculation cho line.sales_order_item
        # dùng new_bom_version nếu có, ngược lại giữ nguyên bom_version hiện hành + giá trị biến mới
        ghi ConfigSnapshot mới, không tạo Sales Order mới (trừ khi has_price_impact=1,
        khi đó việc tạo SO bổ sung do AL Change Order.on_approve() đảm nhiệm như §27.3 — không trùng lặp)
```

**Liên kết ngược từ Site Survey (sửa §25.7):** khi `AL Site Survey Line.within_tolerance=0`, hook tự động tạo `AL Design Revision` với `source_type=SITE_SURVEY_DEVIATION`, `source_site_survey` trỏ về Site Survey đó, ở trạng thái `Draft` — **thay vì** yêu cầu tạo trực tiếp Change Order/BOM Version như mô tả cũ. Kỹ thuật viên xử lý tiếp từ bản ghi này (điền dòng ảnh hưởng, xác định có cần BOM Version mới không, có tác động giá không).

---

## 3. SỬA ĐỔI CÁC MỤC ĐÃ CÓ TRONG v25

### 3.1 §27.3 AL Change Order (Master) — thêm 1 field

Thêm vào bảng field của `AL Change Order (Master)`, ngay sau `original_sales_order`:

| fieldname | fieldtype | Mô tả |
|---|---|---|
| source_design_revision | Link → AL Design Revision | Tùy chọn — trỏ về bản ghi thiết kế gốc nếu Change Order này phát sinh từ 1 phụ lục kỹ thuật đã ghi nhận |

*(Lý do để tùy chọn, không bắt buộc: xem D1 ở mục 1 — Change Order vẫn có thể phát sinh thuần thương mại, không qua Design Revision.)*

### 3.2 §25.7 AL Site Survey — sửa đoạn "Gate"

**Thay:**
> Gate: nếu `within_tolerance=0` cho bất kỳ dòng nào → chặn Cutting Plan Confirm, bắt buộc tạo `AL Change Order` (hoặc BOM Version mới cho dòng đó) — không được sửa tay ConfigSnapshot gốc (Nguyên tắc #26).

**Thành:**
> Gate: nếu `within_tolerance=0` cho bất kỳ dòng nào → chặn Cutting Plan Confirm, tự động tạo `AL Design Revision` (`source_type=SITE_SURVEY_DEVIATION`, §27.4) ở trạng thái Draft. Từ đó mới xác định cần BOM Version mới và/hoặc Change Order hay không — không được sửa tay ConfigSnapshot gốc (Nguyên tắc #26).

### 3.3 §XXIV Reporting — thêm report mới

Thêm dòng: *"Final Design Register — Query Report tổng hợp theo dự án: mỗi Sales Order Item đang active, cùng `al_bom_version` hiện hành, `AL Design Revision` mới nhất đã Applied, và kích thước đo thực tế cuối cùng từ `AL Site Survey Line` (nếu có) — trả lời câu hỏi 'cấu hình kỹ thuật cuối cùng của công trình là gì tại thời điểm hiện tại'. Không lưu trữ số liệu tĩnh, luôn truy vấn trực tiếp 3 nguồn (Nguyên tắc #30)."*

### 3.4 §XXXI Quy trình đầu-cuối — sửa dòng "Phát sinh nếu có"

**Thay:**
> `→ Phát sinh nếu có (Change Order Approved → Sales Order bổ sung)`

**Thành:**
> `→ Phát sinh/thay đổi thiết kế nếu có (AL Design Revision ghi nhận mọi thay đổi kỹ thuật → nếu has_price_impact=1 thì Change Order Approved → Sales Order bổ sung; nếu không, chỉ tính lại ConfigSnapshot)`

---

## 4. CẬP NHẬT DANH MỤC & CHECKLIST

### 4.1 §III Danh mục DocType — thêm vào nhóm 6E (sau dòng #59 `AL Handover Acceptance`)

| # | DocType | Nhóm | Mô tả |
|---|---|---|---|
| 60 | AL Design Revision | 6E | Ghi nhận thay đổi thiết kế/spec — có hoặc không tác động giá, nguồn từ CĐT hoặc Site Survey |
| 61 | AL Design Revision Line | 6E | Child — từng field thay đổi trên 1 Sales Order Item |

*(Renumber `AL AI Suggestion Log`/`AL AI Interaction Log` ở Tầng 7 thành #62-63. Cập nhật dòng "Tổng: 61 DocType..." → "Tổng: 63 DocType...".)*

### 4.2 §I — Bảng "Quyết định kiến trúc" — thêm QĐ-36

| Mã | Quyết định | Vấn đề giải quyết |
|---|---|---|
| **QĐ-36** | **`AL Design Revision` tách khỏi `AL Change Order`** — ghi nhận thay đổi kỹ thuật không nhất thiết có tác động giá; Site Survey deviation cũng sinh Design Revision thay vì đi thẳng Change Order | Tránh vừa làm nhiễu dữ liệu thương mại vừa mất dấu vết thay đổi kỹ thuật thuần túy; tạo 1 điểm sự thật duy nhất cho "bản thiết kế cuối cùng" |

### 4.3 §XXXIII Ví dụ kiểm chứng — thêm kịch bản #11

> 11. `AL Design Revision` với `has_price_impact=0` chạy xong tạo ConfigSnapshot mới cho đúng dòng ảnh hưởng, KHÔNG tạo Sales Order/Change Order mới. Ngược lại, `has_price_impact=1` mà thiếu `linked_change_order` → bị chặn ở validate. Site Survey lệch dung sai tự động sinh đúng 1 `AL Design Revision` nguồn `SITE_SURVEY_DEVIATION`.

### 4.4 §XXXVI Checklist Go-live — thêm 1 dòng

> - [ ] `AL Design Revision`: test đủ 3 `source_type`, test validate `has_price_impact` ↔ `linked_change_order`, test Site Survey deviation tự tạo Design Revision đúng

---

## KẾT LUẬN

Bổ sung này thêm đúng **2 DocType** (1 Master + 1 Child) và **1 Query Report**, không đụng đến Tầng 1-4 (Master Data/Orchestration/Formula Engine — bất biến tuyệt đối theo kiến trúc gốc), không thêm Workflow mới, không phá bất kỳ nguyên tắc nào trong 31 nguyên tắc gốc. Điểm mấu chốt là **tách ghi nhận kỹ thuật khỏi ghi nhận thương mại** trong khi vẫn giữ 1 điểm hội tụ duy nhất (Final Design Register) để trả lời câu hỏi "thiết kế cuối cùng là gì" — đúng tinh thần "minh bạch tuyệt đối" (Nguyên tắc #12) của toàn bộ hệ thống.
