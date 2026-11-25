# Bước tra cứu quy tắc phải hiểu được — không cần biết code

> **Trạng thái:** thiết kế chốt 2026-11-25 · **chưa triển khai**
> **Phạm vi:** `AL Rule`, `AL Bom Item`, `AL Accessory Item`, dialog báo giá
> **Liên quan:** `docs/design/gop-rule-mot-doctype.md`,
> `docs/usage/tinh-gia-bao-gia.vi.md`

## 1. Vấn đề (người dùng nói gì)

Ba câu hỏi thật, không trả lời được bằng giao diện hiện tại:

1. **"Làm sao biết nẹp này tra theo độ dày kính, và tìm trong `AL Rule` để
   ra mã nẹp?"** — Trên dòng `AL Bom Item`, người dùng chỉ thấy ô Link
   *Item Rule* + ô chữ *Rule Input Expression* chứa
   `items.kinh_tren.glass_thick`. Không có chỗ nào nói ô đó nghĩa là
   "độ dày kính của dòng Kính trên", cũng không nói quy tắc trả ra mã gì.
2. **"`RULE-BANLE-QTY` lấy từ đâu?"** — Công thức số lượng bản lề là
   `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`. Người dùng phải **nhớ
   mã quy tắc bằng trí nhớ**; autocomplete của Formula Builder chỉ biết các
   hàm chuẩn, không biết `lookup_rule` là gì, không gợi ý quy tắc nào.
3. **"Quản trị tự cấu hình được không?"** — `AL Rule` có 2 bảng con
   (ngưỡng / tra bảng) nhưng không có chỗ mô tả quy tắc dùng để làm gì,
   không có nút thử kết quả. Quản trị phải tự suy từ `rule_code` và các con
   số.

Hệ quả: bước tra nẹp/keo chỉ "chạy được" với người viết ra nó; người mới
không đọc ra được, và khi sai thì sửa bằng cách đoán.

## 2. Nguyên tắc

- **Nhìn thấy trước khi bấm**: mỗi dòng dùng quy tắc phải tự kể được
  "tra cái gì → bằng quy tắc nào → ra cái gì" **ngay trên form/dòng**, không
  bắt mở dialog phụ mới biết.
- **Chọn, không gõ**: mã quy tắc không bao giờ phải gõ tay. Người dùng chọn
  quy tắc theo **tên**; hệ thống chèn đúng mã.
- **Thử được ngay**: quản trị nhập một giá trị và thấy kết quả khớp (hoặc
  thấy dải đang trống) mà không cần tính giá cả báo giá.
- **Không đổi số tiền**: đây là lớp hướng dẫn/hỗ trợ nhập liệu; engine tính
  giá giữ nguyên hành vi.

## 3. Giải pháp

### 3.1 `AL Rule` tự mô tả (schema + form)

Thêm 4 field mô tả (chỉ để hiển thị, engine không đọc):

| Field | Kiểu | Nhãn | Ví dụ |
|---|---|---|---|
| `rule_description` | Small Text | Mô tả nghiệp vụ | "Chọn mã nẹp theo độ dày kính" |
| `input_label` | Data | Tên dữ liệu đem tra | "Độ dày kính" |
| `input_unit` | Data | Đơn vị | "mm" |
| `output_label` | Data | Kết quả trả về | "Mã nẹp" |

Kèm `description` (trợ giúp dưới ô) cho `rule_code`, `rule_type`,
`result_type` để quản trị hiểu ngay khi tạo mới. List view hiện
`rule_code · rule_name · rule_type · result_type · input_label →
output_label · is_active`.

Nút **"Thử tra"** trên form `AL Rule`: nhập 1 giá trị → hiện
- dòng khớp (dải `0 – 10,38` hoặc khoá `LOWE`),
- kết quả (số hoặc mã + tên vật tư),
- **cả bảng** với dòng khớp được tô, để thấy ngay mình vừa cấu hình đúng/sai.

### 3.2 API thử tra — `alumglass.api.preview_rule`

```
preview_rule(rule_code, input_value=None) -> {
  success, rule_code, rule_name, rule_description,
  rule_type, result_type, input_label, input_unit, output_label, is_active,
  input_value,
  matched: {kind: "range"|"key"|"constant", from, to, key} | null,
  result:  {value} | {item_code, item_name} | null,
  rows:    [{from, to, key, result_text, is_match}],
  message: "" | "<câu người-đọc-được>"
}
```

- Quyền: đọc `AL Rule`; sai quyền ⇒ `PermissionError` (câu người-đọc-được).
- **Không throw vì trạng thái nghiệp vụ**: quy tắc tắt, không khớp, thiếu
  dòng ⇒ `success: true` + `message` nêu việc cần làm (vd dải trống
  `2100 – 2101`).
- Logic đặt trong `ALRule.preview()` (controller) để form và API dùng chung.

### 3.3 Chọn quy tắc thay vì gõ mã (Formula Builder)

- Đăng ký `lookup_rule` / `lookup_calc_pattern` vào
  `formula_builder.formula.FunctionRegistry` với chữ ký + mô tả tiếng Việt
  + ví dụ ⇒ autocomplete giải thích được hàm.
- Nút **"🧩 Chọn công thức"** cạnh các ô công thức số lượng:
  - `AL Bom Item.qty`
  - `AL Accessory Item.qty_formula` (đây là chỗ công thức bản lề)
- Hộp thoại mở ra **4 lựa chọn không-code** (chọn một, xem ví dụ kết quả):
  1. **Số lượng cố định** — nhập số, chèn đúng số đó.
  2. **Theo số cánh** — chèn `n_panel`.
  3. **2 × số cánh** — chèn `2 * n_panel`.
  4. **Tra quy tắc theo giá trị** — mở 3 bước dưới đây.
- Nhánh tra quy tắc, **không gõ mã**:
  1. **Chọn quy tắc**: chỉ liệt kê `AL Rule` có `result_type = NUMBER`, đang
     bật; hiện `rule_name` + mô tả + "tra theo *Độ dày kính (mm)* → *Số bản
     lề mỗi cánh*". Có nút "Tạo quy tắc mới" cho quản trị.
  2. **Chọn dữ liệu đem tra**: danh sách biến của chứng từ (từ
     `FormulaContext`: `H_mm`, `W_mm`, `n_panel`, …) kèm nhãn; hoặc nhập
     biểu thức tự do.
  3. **Nhân với (tuỳ chọn)**: cùng danh sách biến, vd `n_panel`.
- Hiện **kết quả thử** ngay trong dialog: nếu biến đã có giá trị hiện tại,
  gọi `preview_rule` và hiện "H_mm = 3200 → 4 bản lề/cánh × 2 cánh = 8".
- Chèn đúng chuỗi vào ô đang sửa:
  - không nhân: `lookup_rule('RULE-BANLE-QTY', H_mm)`
  - có nhân: `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`
- Nếu editor Monaco đang mở: cập nhật qua
  `window._afbPatchedEditors["<doctype>::items::<cdn>::<field>"]`; nếu
  không: `frappe.model.set_value` rồi refresh.

### 3.4 `AL Bom Item` — dòng chọn mã theo quy tắc tự giải thích

Một vùng HTML (`rule_help_html`) trong mục *Rule Configuration*, chỉ hiện
khi `item_selection_mode = Rule`:

> Dòng này **lấy mã tự động**: tra **Độ dày kính** của dòng **"Kính trên"**
> → quy tắc **"Chọn nẹp theo độ dày kính"** → ra **mã nẹp**.
> `[Xem quy tắc]` `[Thử tra]` `[Chọn dữ liệu tra]`

- *Chọn dữ liệu tra*: danh sách (dòng × field) với nhãn người đọc —
  "Kính trên — Độ dày kính (mm)" → `items.kinh_tren.total_thick_mm` (ưu
  tiên tên chuẩn, alias `glass_thick` vẫn nhận); "Kính trên — Loại kính" →
  `items.kinh_tren.glass_type`. Không có dòng kính ⇒ nói rõ cần chọn kính
  trước.
  > ⚠️ **Chỉ mời đúng field engine đọc được.** `rule_input_expr` KHÔNG đi
  > qua Formula Engine: `_resolve_rule_input_for_item` chỉ đọc
  > `glass_data[slug]` (`total_thick_mm` / `glass_thick` / `glass_type` /
  > `max_area_m2`) và `row_literals` (không có `width`/`height`/`qty`).
  > Mời "Rộng/Cao" ở đây = giá trị **0 âm thầm** ⇒ dòng không ra mã.
  > Vì vậy danh sách này KHÔNG dùng chung với danh sách của hộp thoại chèn
  > công thức (ô công thức đi qua Formula Engine nên `items.<dòng>.width`
  > hợp lệ).
- *Thử tra*: đọc giá trị hiện tại của dòng được tham chiếu (nếu có) và gọi
  `preview_rule`; chưa có số liệu ⇒ cho nhập tay.
- Dòng chưa cấu hình đủ ⇒ câu hướng dẫn đúng chỗ sửa (chọn quy tắc / chọn
  dữ liệu tra), không phải ô trống.

Với các dòng dùng công thức (`qty` / `qty_formula`): thêm nút **"🧩 Chọn
công thức"** ngay dưới ô công thức.

### 3.5 Dialog báo giá — thấy căn cứ ngay trên bảng

Trong bảng "Chi tiết vật tư" của preview, dưới tên vật tư hiện **một dòng
chữ nhỏ** (tối đa 2 dòng, hover xem đầy đủ), lấy `qty_rule_trace` (dòng số
lượng) hoặc `rule_trace` (dòng chọn mã):

> 10 mm → C3209-20 · theo quy tắc "Chọn nẹp theo độ dày kính"
> Chiều cao = 3200 mm → 4 × số cánh 2 = 8 · "Số bản lề theo chiều cao"

Engine sinh thêm `qty_rule_trace` / `qty_rule_trace_raw` cho dòng có
`qty` là `lookup_rule(...)` — **chỉ khi công thức khớp dạng đơn giản**
`lookup_rule('MÃ', INPUT) [* MULT]`; dạng phức tạp ⇒ để rỗng, ⛔ đoán câu.

Nút `?` ("Vì sao ra số này?") giữ nguyên; dialog giải thích thêm
`rule_description` của quy tắc (nếu có) ở bước "Quy tắc khớp → mã", và thêm
bước **"Quy tắc tính số lượng"** ngay sau "Tính số lượng" khi dòng có
`qty_rule_trace`.

### 3.6 Cảnh báo mã quy tắc sai trong công thức

Khi lưu `AL Bom Set` / `AL Accessory Set` / `AL Cost Template`, quét các
chuỗi `lookup_rule('MÃ', …)` **có mã dạng literal**:

- mã không tồn tại → cảnh báo kèm lối sửa ("bấm *Chèn tra quy tắc* để chọn
  lại");
- quy tắc đang tắt → cảnh báo;
- quy tắc `result_type = ITEM` dùng trong công thức số → cảnh báo (chọn mã
  không trả số).

Chỉ **cảnh báo** (`frappe.msgprint`), không chặn lưu — cùng mức với cảnh
báo `rule_input_expr` hiện có, để không làm hỏng BOM đang chạy.

## 4. Tiêu chí nghiệm thu

1. Mở `AL Rule` `RULE-NEP-GLASSTHICK`: thấy mô tả + "Độ dày kính (mm) →
   Mã nẹp"; *Thử tra* `10` → `C3209-20`, `12` → `C3210-20`, `17` →
   `C3211-20`; `10,385` → câu nêu dải trống, không phải màn hình trống.
2. Dòng `nep_kinh_tren` trong `AL Bom Set`: đọc được câu "tra Độ dày kính
   của dòng Kính trên → quy tắc … → mã nẹp" **không cần bấm gì**; *Thử tra*
   dùng đúng độ dày đang có của dòng kính.
3. Dòng `ban_le` trong `AL Accessory Set`: bấm *Chọn công thức* → *Tra quy
   tắc theo giá trị*, chọn "Số bản lề theo chiều cao", chọn `H_mm`, nhân
   `n_panel` → chèn đúng `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`;
   dialog hiện kết quả thử. Ba lựa chọn còn lại (số cố định / theo số cánh /
   2 × số cánh) chèn đúng chuỗi tương ứng.
4. Hộp *Chọn dữ liệu tra* của dòng chọn mã **không mời** "Rộng/Cao" hay biến
   công thức — chỉ mời độ dày/loại kính của dòng kính (field engine thật sự
   đọc); chọn một nguồn ngoài danh sách đó phải bị chặn kèm lời giải thích.
5. Autocomplete công thức hiện `lookup_rule` kèm chữ ký + mô tả.
6. Gõ sai mã trong công thức rồi Lưu → cảnh báo nêu đúng mã sai + cách sửa.
7. Preview báo giá: dòng nẹp/keo **và dòng bản lề** hiện căn cứ ngay dưới
   tên, không cần bấm `?`; hộp `?` của dòng bản lề có bước "Quy tắc tính số
   lượng" nêu chiều cao đem tra, kết quả mỗi cánh và hệ số nhân.
8. Không có chuỗi kỹ thuật (`items.…`, `rule_code`) trong câu dành cho
   người dùng cuối; trừ form `AL Rule`/ô cấu hình (dành cho quản trị).
9. Số tiền tính ra **không đổi** so với trước bản vá (regression engine).

## 5. Không làm trong đợt này

- Versioning thật cho `AL Rule` (vẫn là chỗ giữ chỗ — xem
  `gop-rule-mot-doctype.md`).
- Đổi cách engine resolve quy tắc.
- Sửa hàng loạt dữ liệu quy tắc cũ (chỉ thêm field mô tả; để trống vẫn chạy).

## 6. Rủi ro / lưu ý triển khai

- Thêm field vào `AL Rule` ⇒ **phải `bench migrate`** trên site trước khi
  form hiện đủ; chưa migrate thì form vẫn chạy (field trống) nhưng nút *Thử
  tra* phải chịu được API trả thiếu khoá.
- `al_rule.js` / helper mới đi qua `app_include_js` hoặc `doctype_js` ⇒ nhớ
  bump `?v=` và `alumglass.__build__` theo `docs/ops/cap-nhat-ma-va-cache.md`.
- Đăng ký hàm vào FunctionRegistry phải **idempotent** (refresh form nhiều
  lần không nhân bản gợi ý).
- Nút chèn phải cập nhật cả editor Monaco đang mở lẫn giá trị field, tránh
  "chèn xong nhưng ô vẫn trống".
- **Script của doctype CON không chạy qua `doctype_js`** (Frappe v14 chỉ
  `eval` `__js` của doctype đang mở form; dòng con dùng `script_manager`
  của form cha). Vì vậy `al_bom_item.js` / `al_accessory_item.js` nạp qua
  `app_include_js` và chỉ đăng ký `frappe.ui.form.on(...)` — cùng cách
  `formula_setup.js` đang làm. Đừng chuyển chúng về `doctype_js`.
