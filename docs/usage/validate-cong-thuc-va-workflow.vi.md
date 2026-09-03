---
title: "Xác nhận công thức khi lưu + Kính theo vị trí + Workflow phê duyệt (sau vá V6 P10)"
contexts:
  - "Form/AL Bom Set"
  - "Form/AL Accessory Set"
  - "Form/AL Alert Config"
  - "Form/AL BOM Version"
  - "Form/AL Change Order"
  - "Form/AL Design Revision"
  - "Form/Quotation"
tags: [production, sales-crm]
doc_type: doctype
---

# Xác nhận công thức khi lưu + Kính theo vị trí + Workflow phê duyệt

Tài liệu này mô tả các thay đổi hành vi người dùng thấy SAU khi áp gói vá
`alumglass-patch-3-full` (V6 P10) — Phase 0. Chi tiết kỹ thuật tại
`docs/design/p3-quotation-pricing-patch-3-full.md`.

## 1. Validate công thức NGAY khi lưu (chặn cứng ở server)

Trước đây AL Cost Template mới là nơi duy nhất kiểm tra công thức lúc save; AL Bom
Set / AL Accessory Set / AL Alert Config chỉ có autocomplete (hoặc không gì) — lỗi
biến sai chỉ lộ ra lúc tính BOM thật cho khách hàng. Sau vá:

| Nơi gõ | Hành vi khi lưu |
|---|---|
| **AL Bom Set** — field width/height/qty/show_condition/item_condition_formula trên các dòng | Save bị **chặn** nếu biến/hàm sai hoặc không khai báo, kể cả công thức cross-row `items.<slug>.<field>` (đã được chuẩn hóa đúng như engine khi tính). Dòng `rule_input_expr` (mode Rule) phải đúng định dạng `items.<slug>.<field>` |
| **AL Accessory Set** — `qty_formula` (giờ có autocomplete) | Save bị **chặn** nếu biến sai |
| **AL Alert Config** — `trigger_condition` | Save bị **chặn** nếu biến sai |

Nguồn biến hợp lệ là toàn bộ context thật của engine (Cost Bucket, System/User Var,
Formula Global Variable, Formula Variable Binding…) — gõ đúng tên biến dùng được trong
công thức là qua được. Gõ sai chính tả (vd `witdh`) sẽ thấy thông báo
"Công thức không hợp lệ" và KHÔNG lưu được.

## 2. Kính theo vị trí hoạt động thật trong Báo giá

Trong dialog "Nhập thông số" của Quotation (sản phẩm có ≥1 dòng kính), bạn có thể
chọn mã kính RIÊNG cho từng vị trí ("Kính trên", "Kính dưới"...). Sau vá, engine đọc
đúng các lựa chọn này:

- Giá kính của mỗi vị trí tra theo đúng mã kính đã chọn cho vị trí đó.
- Nẹp kính / keo (Dynamic Item Rule theo độ dày kính) resolve theo độ dày của TỪNG vị
  trí — trước đây cả BOM chỉ dùng 1 mã kính global, đổi kính từng vị trí không có tác
  dụng thật.

Các dimension pricing (màu/xuất xứ/độ dày/bề mặt) trong dialog được đánh dấu không
bắt buộc theo cờ `is_pricing_dimension` server trả về từ `AL Variable Dimension
Mapping` — thêm dimension mới (kể cả cho kính) chỉ cần thêm record mapping, không sửa
code dialog.

## 3. Workflow phê duyệt thật (nút theo role)

4 doctype `AL BOM Version`, `AL Change Order`, `AL Dynamic Item Rule Version`,
`AL Design Revision` chuyển từ field `workflow_state` tự sửa bằng tay sang **Workflow
Frappe thật**:

- Form chỉ hiện nút hành động hợp lệ cho trạng thái hiện tại, và chỉ với role được
  phép (vd "Submit for Approval" chỉ AL BOM Manager; "Approve" AL BOM Version chỉ AL
  Technical Admin).
- Người dùng không còn sửa thẳng trạng thái trong 1 dropdown Select như trước.
- **AL Change Order**: nút "Approve" chỉ hiện khi đã tick đủ `customer_approval` +
  `internal_approval` (lớp điều kiện giao diện; logic chặn backend trong code giữ
  nguyên làm lưới an toàn).
- Các hành vi nghiệp vụ cũ giữ nguyên: AL BOM Version sau khi Published không sửa
  snapshot được nữa (phải tạo version mới); AL Design Revision Approve → Implemented
  vẫn tự tạo BOM Version mới.

Muốn chỉnh role/transition: System Manager vào **Workflow** list, sửa trực tiếp —
hiệu lực ngay, không cần deploy code.

## 4. Bảng giá dùng để tính giá

Bảng giá mặc định engine dùng khi tra Item Price (và binding FB-max seed) lấy từ
**Selling Settings → Selling Price List** (không còn hardcode "Standard Selling").
Đổi bảng giá trong Selling Settings → lần migrate kế tiếp (hoặc tính giá sau khi clear
cache) dùng đúng bảng giá mới.
