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
- ~~Đổi cách engine resolve quy tắc.~~ → **Đã mở ở chặng 3** (§7): quy tắc tự
  khai dữ liệu đem tra; vẫn tương thích ngược cho quy tắc chưa khai.
- Sửa hàng loạt dữ liệu quy tắc cũ (chỉ điền chỗ **chắc chắn** qua patch §7.4;
  còn lại để trống và vẫn chạy).

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

## 7. Chặng 3 — quy tắc tự khai "tra theo cái gì" (2026-11-25)

> **Vì sao có chặng này:** sau khi chặng 2 lên site test, Owner vẫn không hiểu
> *"tại sao từ `glass_thick` lại ra được quy tắc theo độ dày kính"* — vì
> "tra theo gì" đang nằm trong một **biểu thức kỹ thuật trên từng dòng**
> (`rule_input_expr = items.kinh_tren.glass_thick`), không nằm ở quy tắc.
> Đồng thời Owner yêu cầu **không fix cứng** danh sách dữ liệu tra.

### 7.1 Mô hình

| Nơi khai | Field | Ý nghĩa |
|---|---|---|
| `AL Rule` | `input_variable` (Link `AL Variable Library`) | **Quy tắc này tra theo dữ liệu gì** — vd `total_thick_mm` (Độ dày kính), `glass_type` (Loại kính), `H_mm` (Chiều cao) |
| `AL Rule` | `input_scope` (Select `ROW`/`GLOBAL`, read-only) | Máy tự suy từ `AL Variable Library.category`: `Row Literals` ⇒ `ROW`, còn lại ⇒ `GLOBAL` |
| `AL Rule` | `input_label` / `input_unit` | Nhãn + đơn vị hiển thị; **tự điền** từ `var_label` của biến khi để trống, vẫn sửa tay được |
| `AL Bom Item` | `rule_input_row` (Data, chứa slug dòng) | **Lấy số từ dòng nào** — chỉ có nghĩa khi biến của quy tắc là biến theo dòng (vd độ dày/loại kính của dòng kính) |
| `AL Bom Item` | `rule_input_expr` | **Chỉ còn là đường nâng cao/tương thích** — ẩn khỏi giao diện thường khi quy tắc đã khai `input_variable` |

Phân loại biến theo dòng hay toàn cục: đọc `AL Variable Library.category`
(`Row Literals` = theo dòng) — **không hardcode tên field** trong client/server.

### 7.2 Cách engine phân giải (thứ tự)

1. `rule.input_variable` rỗng ⇒ **giữ nguyên hành vi cũ** (`rule_input_expr`).
2. Biến **theo dòng** (`Row Literals`): đọc `glass_data[rule_input_row]`,
   fallback `row_literals[rule_input_row]`. Thiếu `rule_input_row` ⇒ fallback
   `rule_input_expr` cũ (nếu có), không thì không có đầu vào.
   Alias `glass_thick` ↔ `total_thick_mm` giữ nguyên.
3. Biến **toàn cục** (vd `H_mm`, `installation_height_m`): đọc từ inputs của
   lượt tính; dòng BOM **không cần** chọn nguồn.
4. Trong công thức: `lookup_rule('MÃ')` **một tham số** được phép khi quy tắc
   khai biến toàn cục — engine tự chèn biến đó trước khi tính. Quy tắc khai
   biến theo dòng mà gọi một tham số trong công thức ⇒ cảnh báo (không đoán
   dòng nào) và yêu cầu truyền giá trị rõ ràng.

### 7.3 Giao diện

- **Form `AL Rule`**: field *Tra theo* (Link, hiện **nhãn biến** nhờ
  `title_field`) + câu xem trước "Quy tắc này tra theo **Độ dày kính**".
  ⛔ Không hiện tên biến (`total_thick_mm`/`H_mm`); chưa có nhãn ⇒
  "dữ liệu quy tắc đọc".
- **Dòng `AL Bom Item` (mode Rule)**:
  - Quy tắc tra theo biến **dòng** ⇒ hiện *Lấy từ dòng* (chọn trong các dòng
    có biến đó — vd chỉ dòng kính), ẩn biểu thức.
  - Quy tắc tra theo biến **toàn cục** ⇒ không hỏi nguồn, hiện
    "Quy tắc tự lấy **Chiều cao**".
  - Câu tự kể: `Quy tắc khai tra theo **Độ dày kính** · lấy từ dòng
    **Kính trên** · hiện tại **24 mm** → **C3211-20**`.
  - `rule_input_expr` (nếu còn) đặt dưới mục *Nâng cao* cho người kỹ thuật.
- **Hộp "Chọn công thức"**: quy tắc khai biến toàn cục ⇒ **bỏ bước chọn dữ
  liệu**, chèn `lookup_rule('MÃ')`; vẫn cho chọn "nhân với" (`n_panel`).
  Bốn lối tắt (số cố định / số cánh / 2× / tra quy tắc) giữ nguyên.

### 7.4 Tương thích & patch

- Quy tắc chưa khai `input_variable` chạy y như trước — **không phá dữ liệu**.
- Patch `infer_rule_input_variable` (post_model_sync) **chỉ điền khi chắc chắn**:
  - Rule ITEM: quét `AL Bom Item` dùng rule; nếu **mọi** `rule_input_expr`
    dùng cùng một field ⇒ điền `input_variable`; đồng thời điền
    `rule_input_row` từ slug của biểu thức (chỉ khi đang trống).
  - Rule NUMBER: quét công thức (`AL Bom Item.qty`, `AL Accessory
    Item.qty_formula`, `AL Cost Template.calc_formula`, `AL Quantity Calc
    Method.calc_fn`, `Formula Global Variable.formula_expr`) tìm
    `lookup_rule('MÃ', <biến>)`; nếu **mọi** lời gọi dùng cùng một biến đơn
    ⇒ điền `input_variable`. Không chắc ⇒ để trống + ghi log, không đoán.
- Không xoá `rule_input_expr` trong chặng này (đường lùi + trường hợp đặc biệt).

### 7.5 Tiêu chí nghiệm thu

1. `RULE-NEP-GLASSTHICK` hiện *Tra theo: Độ dày kính*; dòng nẹp chỉ hỏi
   *Lấy từ dòng* (chọn Kính trên/Kính dưới), **không** hiện `items.…glass_thick`.
2. Câu trên dòng có giá trị hiện tại + kết quả: `24 mm → C3211-20`.
3. `RULE-BANLE-QTY` khai *Chiều cao*; công thức chèn từ hộp thoại là
   `lookup_rule('RULE-BANLE-QTY') * n_panel`; kết quả tính **không đổi** so với
   `lookup_rule('RULE-BANLE-QTY', H_mm) * n_panel`.
4. Quy tắc chưa khai biến: giữ nguyên hành vi + hiện lối "Nâng cao" cho biểu
   thức cũ; tính tiền không đổi.
5. Patch chạy 2 lần không đổi gì thêm (idempotent); rule mơ hồ ⇒ không điền.
6. Không còn câu/DS cứng nào buộc client biết trước danh sách field hợp lệ của
   từng bảng.

### 7.6 Trạng thái "thiếu nguồn" — ⛔ không được gộp với "không khớp" (2026-11-25)

> **Vì sao có mục này:** vòng UX thứ 2 chấm **CHẶN**. Dòng chọn mã theo quy tắc
> ROW nhưng chưa chọn dòng nguồn bị giải thích *"không có mã nào khớp"* — người
> dùng hiểu là **bảng quy tắc không phủ giá trị**, nên đi sửa bảng quy tắc trong
> khi việc thật là **chưa chọn dòng lấy dữ liệu**. Ba trạng thái khác nhau, ba
> câu khác nhau, ba hành động khác nhau:

| Tình huống | `input_missing` | Câu cho người dùng (rút gọn) | Cảnh báo engine |
|---|---|---|---|
| Quy tắc ROW, chưa chọn dòng nguồn | `no_source_row` | `Chọn mã theo quy tắc "…" nhưng chưa chọn dòng lấy <nhãn> — chọn dòng chứa dữ liệu trong bộ BOM.` | `dynamic_rule_thieu_nguon:<rule>:<slug>` |
| Dòng nguồn đã chọn không còn trong BOM | `row_gone` | `Dòng đã chọn để lấy <nhãn> không còn trong bộ BOM — chọn lại dòng lấy dữ liệu.` | như trên |
| Dòng nguồn có, nhưng không mang dữ liệu đó | `row_no_data` | `Dòng "<tên dòng>" không có <nhãn> — chọn dòng khác hoặc bổ sung dữ liệu cho dòng đó.` | như trên |
| Quy tắc GLOBAL, lượt tính thiếu giá trị | `no_global_value` | `Chưa có <nhãn> cho lượt tính này nên chưa chọn được mã — kiểm tra thông số đầu vào của báo giá.` | như trên |
| **Đã có giá trị**, bảng quy tắc không phủ | `""` | `… → không có mã nào khớp · theo quy tắc "…"` | `dynamic_rule_khong_khop:<rule>` (đã có) |

Quy tắc bất biến:

1. **`input_variable` + `input_scope` KHÔNG được rơi mất** khi phân giải thất bại
   — nếu không, câu sẽ quay về "chưa khai báo quy tắc" (sai: dòng CÓ khai).
2. Cờ kết quả tách đôi: `rule_input_missing` = **chưa khai gì cả**;
   `rule_source_missing` = **đã khai nhưng thiếu nguồn**; kèm
   `rule_missing_reason` để client hiện đúng trạng thái.
3. Dòng không có mã ⇒ `item_code` rỗng. ⛔ slug, ⛔ mã của dòng khác, ⛔ số 0
   giả. Client hiện "Chưa tra được mã" và **vẫn mở được** hộp giải thích.
4. Mọi câu nêu **việc phải làm**, ⛔ tên field kỹ thuật/`items.…`/mã quy tắc.
5. Cùng một lỗi chỉ cảnh báo **một lần cho mỗi dòng** (key có slug), nội dung
   nêu tên dòng và hậu quả tiền ("thành tiền chưa đúng").

**Nghiệm thu bổ sung:** dựng 5 ca trong bảng trên ⇒ câu + cờ + cảnh báo khớp
đúng từng dòng; ca "không khớp" cũ vẫn giữ nguyên câu; không ca nào phơi slug.

### 7.7 Bố cục form `AL Rule` — điều kiện tra nằm NGAY dưới khai báo (2026-11-25)

> **Owner nói:** *"Khi chọn nẹp theo độ dày kính thì phải chuyển danh sách các
> điều kiện công thức tra ra kính lên gần chỗ rule chứ, hiện tại để 1 session
> [section] riêng biệt rất khó hiểu."* Bảng ngưỡng nằm dưới cùng, cách xa ô
> *Tra theo* ⇒ người đọc không nối được "tra theo độ dày kính" với "0–10 → nẹp
> 10". Sửa **bố cục**, không thêm khái niệm mới.

Thứ tự đọc trên form, một mạch:

| # | Vùng | Nội dung |
|---|---|---|
| 1 | **Quy tắc** | mã, tên, mô tả, kiểu quy tắc, loại kết quả, giá trị cố định |
| 2 | **Tra theo dữ liệu nào** | *Tra theo* (biến) → nhãn → đơn vị → nhãn kết quả; câu tự kể + thống kê điều kiện (HTML) |
| 3 | **Điều kiện tra** | bảng ngưỡng (THRESHOLD) hoặc bảng tra (LOOKUP) — **ngay dưới vùng 2**, full width |
| 4 | **Quản trị** | phiên bản hiện tại, đang dùng |

Quy tắc bất biến:

1. Bảng điều kiện **full width**, ⛔ đặt sau Column Break (Frappe sẽ vẽ vào nửa
   cột).
2. Nhãn cột **đổi theo dữ liệu đang tra**: `Từ (Độ dày kính)`, `Đến (Độ dày
   kính) — bỏ trống = trở lên`; LOOKUP: `Giá trị (Loại kính)`. ⛔ giữ nhãn
   chung "From Value/Key Value".
3. Cột kết quả ẩn/hiện theo `result_type` (NUMBER ⇒ ẩn mã vật tư; ITEM ⇒ ẩn số).
4. **Thống kê ngay trên bảng**: số điều kiện + vùng phủ; cảnh báo **khoảng
   trống** ("giá trị rơi vào đây sẽ không chọn được mã") — **chỉ cảnh báo**, và
   **chồng lấn** — **chặn Lưu** (`validate_threshold_rows` throw; lý do: engine
   xếp theo `from` tăng dần, dòng khớp đầu tiên thắng, nên chồng lấn là khai
   nhập nhằng). Câu cảnh báo phải nói đúng **dải có mốc bắt đầu thấp hơn** thắng,
   ⛔ "dải khai trước". Khoảng **chạm biên** (0–10, 10–20) ⛔ phải báo
   trống/chồng.
5. **Mở rộng linh hoạt**: nút "＋ Thêm ngưỡng" nối tiếp `from` = `to` của dòng
   cuối; `to` bỏ trống = "trở lên"; không giới hạn số dòng.
   ⚠ **"Bỏ trống = trở lên" là hành vi THẬT của engine, ⛔ chỉ nhãn:** `to`
   rỗng ⇒ cận trên = **+∞** trong `match_threshold_row`; chỉ **dải cuối**
   (theo `from`) được mở, dải mở không ở cuối ⇒ chặn Lưu; `from` vẫn bắt
   buộc; dò khe hở bỏ qua dải mở. Dữ liệu cũ luôn có `to` ⇒ không đổi kết quả
   tính tiền. ✅[V] 2026-11-25: nhãn từng được đặt trước khi engine hỗ trợ —
   `_num("") = 0` khiến dải hở không khớp gì và còn khớp SAI giá trị 0; đã vá
   cả `validate_threshold_rows`, `match_threshold_row`, `warn_threshold_gaps`,
   `_threshold_miss_message`.
6. Thử ngay tại chỗ ("Thử với giá trị" → kết quả) để đối chiếu bảng, không phải
   mở hộp thoại khác.

**Nghiệm thu:** mở `RULE-NEP-GLASSTHICK` ⇒ thấy liền mạch *Tra theo: Độ dày
kính* → bảng `Từ (Độ dày kính)`; khoảng trống/chồng lấn hiện cảnh báo; thêm
ngưỡng mới nối tiếp khoảng cuối; `result_type` đổi thì cột kết quả đổi theo;
tính tiền không đổi.
