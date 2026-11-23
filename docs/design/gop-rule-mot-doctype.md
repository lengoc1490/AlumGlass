# Gộp 2 DocType rule về một `AL Rule`

> **Trạng thái:** Chặng 2C — **2 doctype cũ ĐÃ XOÁ (2026-11-23)**, `AL Rule`
> là nơi duy nhất còn tồn tại. Dữ liệu rule + version đã chuyển sang
> `AL Rule` / `AL Rule Version`. **Chưa deploy** (chờ lượt migrate có kiểm soát
> + backup). **Chặng 1 (đã xong):** `alumglass/al_formula_rules/rule_engine.py`
> gom phần dùng chung (sort dải ngưỡng, kiểm chồng lấp, cảnh báo khe hở,
> resolve biên nửa mở + lưới tương thích dữ liệu cũ).
> **Chặng 2A (đã xong):** DocType `AL Rule` + `AL Rule Version` + 2 bảng con
> dùng chung; patch `migrate_rules_to_al_rule`; seed demo tạo rule bằng
> `AL Rule`. **Chặng 2B (đã xong):** engine/API/Link field chỉ đọc `AL Rule`.
> **Chặng 2C (đã xong):** patch `delete_legacy_rule_doctypes` xoá DocType cũ
> sau cổng kiểm khớp, gỡ mã nguồn + workflow cũ.

## 1. Vì sao gộp

Hai doctype cũ cùng một khái niệm "quy tắc" (CONSTANT / dải ngưỡng / tra
bảng), chỉ khác **cột kết quả**:

| Doctype cũ | Cột kết quả | Dùng ở đâu |
|---|---|---|
| `AL Calculation Rule` | `result_value` (số) | `lookup_rule()` trong công thức; fallback CONSTANT cho system variable; `price_rule`/`surcharge_rule` (2 Link chết) |
| `AL Dynamic Item Rule` | `result_item` (mã Item) | `AL Bom Item.item_rule` khi `item_selection_mode = Rule` |

Hệ quả của việc tách đôi (đã xảy ra thật):

- **Logic chép đôi rồi trôi khỏi nhau** — một bên từng CẤM khai dải chạm
  biên, bên kia CHO PHÉP; sửa bug dải ngưỡng phải sửa 2 nơi.
- **Không có cổng chặn trùng mã**: cùng một `rule_code` có thể tồn tại ở cả
  hai bảng với hai nghĩa khác nhau (một trả số, một trả mã) — công thức chỉ
  tham chiếu mã nên không ai biết bên nào đang chạy.
- **Người cấu hình phải nhớ chọn đúng bảng**; chọn sai bảng ở ô Link không
  bị chặn (Link chỉ kiểm tồn tại), lỗi chỉ lộ ra khi tính giá — dưới dạng
  dòng hàng mất mã / giá 0.
- Admin phải quản 2 menu, 2 bộ quyền, 2 bộ version.

## 2. Mô hình sau khi gộp

```
AL Rule (autoname = rule_code, unique)
├── rule_type    : CONSTANT | THRESHOLD | LOOKUP
├── result_type  : NUMBER | ITEM           ← quyết định cột kết quả
├── constant_value   (chỉ CONSTANT + NUMBER)
├── is_active        (tắt ⇒ engine cảnh báo, không dùng)
├── current_version → AL Rule Version      (hiện luôn trống — xem §6)
├── threshold_rows → AL Rule Threshold Row (dùng chung)
└── lookup_rows    → AL Rule Lookup Row    (dùng chung)

AL Rule Threshold Row: from_value, to_value, result_value | result_item
AL Rule Lookup Row:    key_field,          result_value | result_item
```

Mỗi dòng con mang **cả hai** cột kết quả; `AL Rule.validate()` bắt buộc
**đúng MỘT** cột có giá trị theo `result_type` (cột còn lại phải trống) và
chặn `CONSTANT + ITEM` (chọn mã phải theo THRESHOLD/LOOKUP).

Đọc dữ liệu: `AL Rule.resolve(input_value)` trả `result_value` khi
`result_type = NUMBER`, trả `result_item` khi `= ITEM`, trả `None` khi rule
tắt / không khớp dòng nào.

**Gác loại ở mọi chỗ đọc (chặng 2B):** một rule sai loại lọt vào đúng ô là
lỗi cấu hình, phải nổi lên chứ không được im lặng:

| Chỗ đọc | Chỉ nhận | Khi sai loại |
|---|---|---|
| `bom_orchestrator._lookup_rule()` (công thức) | `NUMBER` | cảnh báo `lookup_rule_sai_loai:<mã>`, tạm tính 0; rule đang bật mà không dòng nào khớp ⇒ cảnh báo `lookup_rule_khong_khop:<mã>`, tạm tính 0 |
| `bom_orchestrator._resolve_dynamic_item()` (`item_rule` của dòng hàng) | `ITEM` | cảnh báo `dynamic_rule_sai_loai:<mã>`, dòng không có mã |
| fallback CONSTANT cho system variable | `NUMBER` | bỏ qua rule đó |
| `api.resolve_item_rule()` | `ITEM` | `frappe.throw` câu người-đọc-được (nêu tên quy tắc + việc cần làm) |
| `AL Bom Item` validate (lúc Lưu) | `ITEM` | chặn lưu, nêu tên quy tắc + việc cần làm |

**Vì sao `depends_on` của 2 bảng con có nhánh `!parent.result_type`:** biểu
thức `parent.result_type=='NUMBER'` khi parent KHÔNG khai `result_type` cho ra
`undefined == 'NUMBER'` ⇒ false ⇒ **ẩn cột kết quả** (form cũ / bản ghi import
tay mất luôn ô cần sửa). Vì vậy biểu thức là
`!parent || !parent.result_type || parent.result_type=='…'`: parent rỗng hoặc
không khai `result_type` ⇒ **hiện cả hai cột**. Từ 2026-11-23 parent chuẩn chỉ
còn `AL Rule`; nhánh "parent rỗng" giữ làm lưới an toàn cho dữ liệu/form cũ.

## 3. Cổng chặn trùng mã

3 lớp, không lớp nào thay được lớp kia:

1. **Cổng migrate** (`migrate_rules_to_al_rule._assert_no_duplicate_codes`):
   `rule_code` xuất hiện ở **cả hai** bảng nguồn ⇒ `frappe.throw` nêu **danh
   sách mã trùng** + hướng dẫn đổi mã ở một bên rồi chạy lại. Chặn TRƯỚC khi
   ghi dòng nào (lọt là thành 2 bản `AL Rule` khác `result_type`). Patch
   **không tự đổi mã** — `rule_code` là hợp đồng với công thức/BOM đang chạy.
2. **Cổng xung đột khi chạy lại** (idempotent): `AL Rule` đã có cùng
   `rule_code` + cùng `result_type` ⇒ bỏ qua; cùng mã nhưng **khác**
   `result_type` ⇒ throw nêu mã + 2 loại.
3. **Cổng schema**: `rule_code` là `unique` + `autoname = field:rule_code` ⇒
   không thể tạo 2 `AL Rule` cùng mã (một mã chỉ thuộc MỘT loại kết quả).

## 4. Thứ tự deploy

Patch đăng ký ở `alumglass/patches.txt` — khối `[post_model_sync]`, **đúng
thứ tự** dưới đây:

1. `bench migrate` chạy đồng bộ DocType trước (tạo `AL Rule`, `AL Rule
   Version`, 2 bảng con; **chưa có mã nào tạo bản ghi `AL Rule Version` MỚI**
   — xem §6).
2. `[post_model_sync]` chạy `migrate_rules_to_al_rule`: chép dữ liệu 2 bảng
   cũ sang `AL Rule` + chép `AL Dynamic Item Rule Version` sang `AL Rule
   Version` (idempotent; dừng và báo nếu trùng mã). Đọc bằng **SQL thô trên
   bảng thật** (⛔ qua meta DocType) — để chạy được cả khi DocType record đã bị
   xoá ở lượt trước mà bảng còn.
3. `[post_model_sync]` chạy ngay sau: `delete_legacy_rule_doctypes` — **cổng
   kiểm khớp trước, xoá sau**. Cổng: mọi `rule_code` còn ở 2 bảng cũ phải có
   `AL Rule` cùng mã **và cùng `result_type`**; thiếu/lệch ⇒ `throw` nêu danh
   sách, ⛔ xoá gì. Đạt cổng ⇒ xoá DocType record theo thứ tự con/version →
   cha. Patch cũng xoá bản ghi `Workflow` cũ trong DB (nếu có) — gỡ entry khỏi
   `install_workflows.py` chỉ ngăn tạo lại, ⛔ dọn bản ghi đang tồn tại. Patch
   ⛔ DROP bảng dữ liệu cũ (xem §5).
4. Chạy `install_roles.py`/fixture như thường lệ: quyền của `AL Rule` theo
   **module** `AL Formula Rules` (không khai theo tên doctype), nên không
   cần sửa gì.

⚠️ **Backup là điều kiện tiên quyết** — sau bước 3 không còn DocType cũ để
"rollback code" (xem §5).

### 4.1 Kiểm trước khi deploy (bắt buộc)

Patch chạy ở `[post_model_sync]`. Nếu site có `rule_code` trùng giữa 2 bảng
nguồn (hoặc mã đã có trong `AL Rule` nhưng khác `result_type`) thì patch
**`throw` giữa lượt migrate** — trong khi mã mới (engine đọc `AL Rule`) đã
deploy ⇒ site dở dang. Kiểm trước bằng hàm **chỉ đọc**:

```bash
bench --site <site> execute alumglass.patches.v1_0.migrate_rules_to_al_rule.dry_run
```

Kết quả là một dict (bench in ra màn hình):

```python
{'number_rules': 6,                # số bản ghi `AL Calculation Rule`
 'item_rules': 2,                  # số bản ghi `AL Dynamic Item Rule`
 'duplicate_codes': [],            # mã xuất hiện ở CẢ HAI nguồn (cổng chặn)
 'existing_in_al_rule': 0,         # mã đã có trong `AL Rule` (idempotent bỏ qua)
 'conflict_codes': [],             # mã đã có nhưng KHÁC result_type (sẽ throw)
 'version_rows': 2,                # số bản ghi version nguồn đọc được
 'orphan_version_rows': [],        # mã rule của version KHÔNG có `AL Rule` (sẽ bỏ qua)
 'al_rule_ready': True,            # bảng `AL Rule` đã được tạo chưa
 'ok': True}                       # True ⟺ không có mã trùng và không xung đột
```

Cách đọc:

- **`ok: true`** ⇒ migrate an toàn, chạy được.
- **`ok: false`** ⇒ **CHƯA deploy**. Xử lý dữ liệu trước:
  - `duplicate_codes`: cùng một `rule_code` nằm ở cả 2 doctype nguồn ⇒ đổi
    `rule_code` ở một bên (mã rule là hợp đồng với công thức/BOM, ⛔ tự đổi
    máy móc), rồi chạy lại `dry_run`.
  - `conflict_codes`: mã đã có trong `AL Rule` với loại kết quả khác ⇒ cùng
    lý do, đổi mã một bên.
- **`al_rule_ready: false`**: `AL Rule` chưa được tạo (chạy trước lượt
  migrate đầu tiên) ⇒ chưa thể có trùng/xung đột trong `AL Rule`, chỉ cần
  `ok: true` là đủ. Ở trạng thái này chưa phân biệt được version mồ côi nên
  `orphan_version_rows` trả `[]`.
- **`version_rows` / `orphan_version_rows`**: số bản ghi version nguồn đọc
  được và mã rule của các bản ghi đó **KHÔNG có `AL Rule` cùng mã** (patch sẽ
  bỏ qua, ⛔ chép). Có mã trong `orphan_version_rows` ⇒ đối chiếu lại: rule
  tương ứng đã được migrate chưa, hay version đang trỏ vào rule đã xoá.
- Hàm này **không ghi/commit gì** và **không throw** khi có xung đột — nó
  chỉ báo. Nếu bảng 2 nguồn đã bị gỡ (site chạy sau này) ⇒ trả 0/0.

## 5. Rollback

Điều kiện tiên quyết: **backup site/DB trước lượt migrate** (thao tác chuẩn
của mọi deploy — `bench --site <site> backup --with-files`).

- **ĐÃ XOÁ 2 doctype cũ (2026-11-23)** — không còn đường "rollback code về
  chặng trước": hết DocType, hết JSON. **Rollback = RESTORE BACKUP** (DB +
  files) lấy đúng mốc trước lượt migrate.
- Patch `delete_legacy_rule_doctypes` **chỉ xoá sau khi cổng kiểm khớp đạt**
  (mọi rule cũ có `AL Rule` cùng mã + cùng `result_type`) ⇒ xoá DocType không
  làm mất dữ liệu đang dùng.
- Bảng dữ liệu cũ (`tabAL Calculation Rule`, `tabAL Dynamic Item Rule`,
  `tabAL Dynamic Item Rule Threshold Row/Lookup Row/Version`) **vẫn còn** sau
  patch (⛔ DROP) — đường cứu hộ MỘT chu kỳ: còn đọc được bằng SQL thô để đối
  chiếu/khôi phục tay. Dọn bảng (sau khi chắc chắn) bằng `bench --site <site>
  mariadb` + `DROP TABLE` — xem docstring patch xoá.
- Bản ghi tạo **mới trong `AL Rule`** sau deploy không có ở bảng cũ ⇒ restore
  backup là cách duy nhất quay lại đúng trạng thái trước migrate.
- ⛔ KHÔNG dùng rollback để "thử lại": patch đã chạy được ghi vào Patch Log,
  chạy lại phải qua đường `bench execute` có kiểm soát.

## 6. Việc còn treo

1. **Versioning MỚI chưa chạy.** Dữ liệu version cũ đã được patch chép sang
   `AL Rule Version`, nhưng **không có mã nào tạo bản GHI version MỚI** — không
   hook/controller/scheduler nào tự sinh bản ghi khi
   Lưu `AL Rule`; `AL Rule.current_version` luôn trống. Patch **không chép**
   `current_version` (Link đã trỏ sang `AL Rule Version`; chép giá trị cũ là
   tạo Link gãy) — cần mã versioning thật mới điền được field này.
   ⛔ tuyên bố "đã có version" cho tới khi mã đó tồn tại.
2. **2 Link chết** — đã đổi `options` sang `AL Rule` để không treo Link,
   nhưng **không có mã nào đọc**:
   - `AL Bom Item.price_rule` (`price_type = Rule`, field ẩn) — engine không
     có nhánh tra giá theo rule.
   - `AL Color Standard.surcharge_rule` — không chỗ nào đọc; phụ thu giá màu
     đang đi qua Pricing Dimension/Item Price.
   Cần một trong hai: gắn mã thật, hoặc gỡ field trong một đợt dọn riêng.
