# Gộp nơi cấu hình biến và công thức — thiết kế đích

> **Trạng thái:** **bản chốt 2 — 2026-11-27** (thay toàn bộ bản chốt 1)
> · **đang triển khai:** B1 ✅ · B3b ✅ · B3c ✅ · B6 ✅ · B3a 🟡 · B2 🟡 code xong, **chờ đo trên site** (xem §Trạng thái triển khai)
> **Phạm vi sửa:** **chỉ `alumglass`**. `formula_builder` chỉ **đọc và dùng**, ⛔ không sửa (R2).
> **Đã qua 2 vòng phản biện độc lập (SA1 + UX1).** Các con số ở bản 1 đã được đo lại; chỗ
> đính chính ghi ở §1.
> **Hướng dẫn người dùng:** `docs/usage/huong-dan-setting-a-z-cdmq.vi.md` — setting A–Z bằng ví dụ
> CDMQ-2C / CDMQ-4C (16 mục, kèm bảng lỗi và checklist).
> **Liên quan:** `docs/design/tra-cuu-quy-tac-de-hieu.md` (chặng 3, đã chốt 2026-11-25),
> `docs/design/gop-rule-mot-doctype.md` (đã xong), `docs/usage/tinh-gia-bao-gia.vi.md`
> **Yêu cầu Owner:** *"setting biến và cấu hình tính toán quá nhiều nơi, rất phức tạp.
> Đề xuất bỏ bớt nơi setting nhưng vẫn linh hoạt, mở rộng được, không hardcode."*

## Trạng thái triển khai (cập nhật 2026-11-27, cuối phiên)

**Chưa commit, chưa push** — toàn bộ thay đổi nằm trong working tree `apps/alumglass`.

| Bước | Trạng thái | Đã làm gì (chỗ đọc) | Kiểm chứng đã có | Còn thiếu |
|---|---|---|---|---|
| **B1** | ✅ xong | Engine đọc `AL Formula Field` là nguồn duy nhất; danh sách riêng của bộ chỉ còn tương thích + cảnh báo (`engine/bom_orchestrator.py` `_resolve_formula_fieldnames`, `api/formula_registry.get_formula_fieldnames`) | `standalone_tests/test_formula_field_registry.py` **14/14** | Đối chứng dương + 2 mốc giá **trên site** |
| **B3b** | ✅ xong | Patch `patches/v1_0/user_vars_in_default_profiles.py`: mở nguồn `variable_library_user` cho 3 hồ sơ seed + cấp Custom DocPerm `AL BOM Manager` trên `Formula Global Variable` (khai một nguồn `setup/install_roles.py::CONSTANT_PERMISSIONS`) | `alumglass/tests/test_user_vars_in_default_profiles.py` **10/10** | Xác nhận trên form (migrate + mở `AL Bom Set`) |
| **B2** | 🟡 code xong | **(2026-11-27, yêu cầu Owner)** gộp `category` vào `group_label` — một nhóm DUY NHẤT, ô Nhóm hiển thị thành Select; patch `v1_0.unify_variable_group`; 4 field vào `AL Variable Library`; 2 field sang `AL Variable Profile`; patch `patches/v1_0/merge_variable_settings_into_library.py`; **một chỗ đọc** `variable_sources/catalog_rows.py` (chia 3 loại rời nhau); bảng Settings **đã XOÁ HẲN** (patch `v1_0.drop_variable_settings_tables`: cổng chặn + sao lưu JSON + DROP 3 bảng) | patch **9/9** · catalog_rows **9/9** · `test_drop_variable_settings_tables.py` **10/10** · 2 test cross-row đỏ sẵn đã vá (**7/7**, **9/9**) | **Đối chiếu tập tên biến trước/sau migrate + 2 mốc giá trên site** (điều kiện nghiệm thu) |
| **B0** | ⛔ chưa chạy | — | — | Site test + người chạy `bench execute` (chỉ đọc) |
| **B3c** | ✅ xong (phần form) | Ô **"Dùng ở"** (Toàn đơn / Từng dòng / Người dùng nhập) trên `AL Variable Library`; cờ `is_input`/`category` tự suy; patch điền cho biến cũ; cảnh báo biến theo dòng viết trần trong công thức | `alumglass/tests/test_b3c_usage.py` **9/9** | Phần `available_at` suy từ engine (nếu cần) chưa làm — hiện cảnh báo dựa trên `ROW_RESOLVABLE_VARIABLES` |
| **B3a** | 🟡 xong phần "thêm biến là chạy" | `engine/row_literal_loader.py`: điền biến Library còn thiếu theo `source_doctype`+`source_field`, bơm vào `{slug}__*`/`items.*`; ⛔ ghi đè 17 literal lõi | `alumglass/tests/test_row_literal_loader.py` **6/6** | **Chưa bỏ 6 danh sách cứng** trong `bom_orchestrator` — bỏ cần site đối chiếu số |
| **B6a/B6b** | ✅ xong | Gỡ 5 field chết khỏi `AL Bom Item` + `surcharge_rule` khỏi `AL Color Standard`; patch `v1_0.count_dead_fields` **đếm + log**, ⛔ chặn migrate (cột DB giữ nguyên) | `alumglass/tests/test_dead_fields_removed.py` **6/6** | Chạy patch trên site để xem số dòng có dữ liệu cũ (không chặn) |
| **B7 (Đ5)** | ✅ code xong | `AL Quantity Calc Method` +`calc_expr` (cú pháp FB) là **nguồn chính**; `calc_fn` còn là đường lùi + **ghi log 1 lần/code** khi bị dùng; `calc_formula` tự chép lại khi trống hoặc khi công thức đổi; patch `v1_0.backfill_calc_expr` điền 14 seed **chỉ khi `calc_fn` khớp seed**, ⛔ đè công thức riêng của site | `alumglass/tests/test_calc_expr_b7.py` **11/11** — đối chứng 14 cặp expr↔lambda trên 5 bộ số | Chạy patch trên site + so 2 mốc giá |
| **Bảng con `AL Variable Set`** | ✅ xong (2026-11-27, yêu cầu Owner) | Ô giá trị hiện đúng kiểu biến: Select → danh sách đã khai · Link → chọn bản ghi của `link_doctype` · Float/Int/Currency/Percent → ô số · Check → đấu dấu · Data → chữ. `AL Variable Set Item` +`fetch_from` cho `link_doctype`/`select_options`; JS toàn trang `al_variable_set_item.js`; ô Default Value của `AL Variable Library` cũng theo kiểu | `alumglass/tests/js/test_variable_set_widget.js` **20/20** (gồm ca âm: thiếu cấu hình ⇒ ô chữ; ca mở lại bộ biến ⇒ tự bù cấu hình từ Library) | `bench build` + migrate (JSON đổi) |
| **B4** | 🟡 code xong | Danh mục biến (`variable_catalog`) là **đường chính kể cả khi chưa gán hồ sơ** (`all_sources`); đường legacy 8 nhóm chỉ còn chạy khi danh mục **lỗi** (có log). Đồng bộ FVB tách ra `fb_binding_sync.py` (một bản) + API `sync_fb_bindings` (dry-run mặc định) để thêm hằng số/biến hệ là FB resolve được ngay | `alumglass/tests/test_fb_binding_sync.py` **5/5** · `test_b4_b5_one_path.py` **8/8** (phần B4) | **Đối chứng tập tên autocomplete + 2 mốc giá trên site** — ⛔ đo được ở máy không site |
| **B4b** | 🟡 code xong | Lớp resolve biến hệ **luôn** bỏ qua biến đã có giá trị (FB/thứ tự trước) — ⛔ còn ghi đè giá trị FB ở nhánh chạy đầy đủ; override `AL Profile System.system_variables` giữ nguyên và vẫn thắng | `test_b4_b5_one_path.py` (phần B4b) | Đo "tập biến hệ resolve trước/sau bằng nhau" trên site |
| **B5/R6** | 🟡 code xong | Bỏ hẳn fallback "lấy số từ `AL Rule` CONSTANT" khi biến hệ thiếu nguồn; thay bằng cảnh báo `bien_he_chua_co_nguon:<tên>` (chỉ cho biến **có khai** `source_doctype`, tránh ngập cảnh báo) | `test_b4_b5_one_path.py` (phần B5) | **Bắt buộc chạy B0 + so 2 mốc giá trên site trước khi tin** — nếu số đổi ở đâu là chỗ trước đây đang ăn số bịa |
| **B9 (Đ2)** | ✅ code xong | `product_clone.py`: nhân bản **cả bảng con** bằng `frappe.copy_doc` (⛔ map tay), mã mới cho Bộ BOM/Bộ phụ kiện/Bộ biến/Bộ giá, ⛔ tự thêm số khi trùng; ghi `cloned_from`/`cloned_at` trên cả 4 doctype (thiếu cột ⇒ vẫn tạo + cảnh báo); `dry_run` xem trước; `clone_from_version` đọc snapshot, ⛔ rơi về bộ sống. API `preview_product_clone` / `create_product_clone` + nút **"Tạo sản phẩm từ bộ này"** trên form Bộ BOM | `test_product_clone.py` **30/30** | Migrate + thử từ CDMQ-2C trên site: bộ mới ra đúng giá sau khi sửa, bộ gốc ⛔ đổi |
| **B8 (Đ1)** | ✅ code xong | Page `al-product-config` "Cấu hình sản phẩm" (chỉ đọc) + API `api/product_config.py`: 7 khối (Sản phẩm · Bộ BOM · Bộ phụ kiện · Bộ biến · Mẫu tính giá · Hồ sơ biến · Quy tắc đang dùng), **cô lập lỗi từng khối**, nút "Mở" nhảy đúng form; khối lỗi hiện câu tiếng Việt, ⛔ traceback | API **22/22** · JS **17/17** | Mở trang trên site (cần migrate) |
| **B10** | ✅ code xong (menu trên v16 còn thiếu) | Quyền đúng nhân vật: `AL Technical Admin` đọc/ghi/tạo, `AL BOM Manager` **chỉ đọc** trên `AL Variable Profile` + `AL Formula Field` — một bảng `CONFIG_PERMISSIONS` trong `install_roles.py`, patch `v1_0.grant_config_permissions` áp cho site đã cài; lối vào: nút "Cấu hình sản phẩm" trên form **AL BOM** + mục ở sidebar legacy | patch **7/7** | **v16: `Workspace Sidebar` đã bị bỏ** — muốn có mục menu phải export `Sidebar` từ site rồi thêm; hiện lối vào thật là nút trên form AL BOM |

**Cổng trải nghiệm (UX1):** ✅ **PASS-có-🟡** vòng 3 (2026-11-27), và ✅ **PASS** vòng 4 cho hướng dẫn A–Z (3 vòng soi tài liệu: 6 + 2 + 1 điểm chặn câu chữ, đã sửa hết; 🟡 còn lại đã đóng). Vòng 1–2 chặn 6 🔴 (trạng thái "chưa gắn" bị dán "không đọc được", mã nhân bản kẹt ở `…-MOI`, phơi `Duplicate entry`/tên cột ra người dùng, `cloned_from` dạng `DocType:tên`, ô biến Select thiếu lựa chọn không giải thích) — đã sửa hết và có test giữ chỗ. 🟡 còn lại (không chặn): nhãn field bảng biến còn tiếng Anh; tên gọi "Bộ giá" vs "Mẫu tính giá" chưa thống nhất.

**Ba điểm phải nhớ khi đọc tiếp:**

1. **B3b cố ý KHÔNG thêm `row_literal`** vào hồ sơ BOM/Cost Template dù bản chốt ghi vậy — B4/B6
   không có namespace literal trần, thêm vào là mời viết công thức ra 0 âm thầm. Xem §4.3 Đ3.
2. **B2 không đợi B0** nhưng **nghiệm thu B2 cần site**: tập tên biến autocomplete trước/sau phải
   bằng nhau. Code có test thuần, **chưa được coi là đạt** khi chưa đo.
3. **Chưa commit/push** theo luật chung — chỉ commit khi Owner yêu cầu trong phiên.

---

## Ràng buộc Owner đã chốt (2026-11-27)

Bảy ràng buộc dưới đây **thắng** mọi đề xuất trong tài liệu này. Chỗ nào mâu thuẫn thì sửa theo đây.

| # | Ràng buộc | Hệ quả (một dòng) |
|---|---|---|
| **R1** | **Không tùy biến theo khách.** | ⛔ Không bảng / tầng biến theo khách; `AL Bom Version` giữ nguyên hiện trạng. |
| **R2** | **Chỉ sửa `alumglass`; dùng tối đa `formula_builder`** — cái gì FB đã có thì dùng, ⛔ viết lại trong alumglass. | Bổ sung chỉ ở phía alumglass (adapter / `@register_source` / registry / dữ liệu). Buộc sửa FB ⇒ **dừng, báo Owner**. |
| **R3** | **GỘP** `common_variables` + `row_literals` vào `AL Variable Library`; **bỏ màn "Cấu hình chung"**. | 2 bảng con bị BỎ; `AL Variable Settings` (Single) bị BỎ hẳn — 2 field còn lại chuyển sang `AL Variable Profile` (`is_default`, `preview_doctype`). |
| **R4** | **GIỮ `Formula Global Variable` (FB)** là nhà **duy nhất** cho hằng số toàn cục; `AL Variable Library` **chỉ trỏ**, ⛔ khai trùng giá trị. | `default_value` của **mọi** biến hệ bị xoá khỏi Library; 3 biến không nguồn (`VAT_RATE`, `OH_VC_PCT`, `OH_QLY_PCT`) đã có sẵn trong FGV. |
| **R5** | **GỠ cả 6 ô chết**; **chưa nối ô nào** vào engine. | 6 field bị gỡ; tính năng "nhiều cánh" / "giá theo quy tắc" nếu cần sẽ làm sau như **tính năng có thiết kế riêng**. |
| **R6** | **BỎ fallback CONSTANT lấy 48 khi thiếu nguồn**; thiếu nguồn ⇒ **chặn tính + cảnh báo rõ**. | Chỉ bật chặn **sau khi** dữ liệu trên site đã sạch (đo ở B0). |
| **R7** | **Tách vật lý ≠ bắt người dùng đi nhiều màn.** Giữ DocType riêng khi việc tách phục vụ thiết kế thật (vòng đời, quyền, version/audit, tái dùng, khối lượng dữ liệu). Giảm độ phức tạp bằng **UI điều phối** (màn tổng hợp, mẫu, liên kết, mặc định, kiểm lúc lưu). ⛔ **Gộp bảng dữ liệu chỉ để đếm ít.** | Mọi đề xuất "gộp thêm DocType" bị loại trừ mặc định; chỉ số đo là **số màn/số bước của người dùng**, không phải số bảng. |

> Hệ quả của R2 nói riêng: mọi "bản sao" của FB trong alumglass (tự resolve biến hệ, tự dò field
> Link, tự dựng danh sách gợi ý, tự chép biến sang `Formula Variable Binding` bằng patch) là **đối
> tượng phải bỏ**, danh sách đối chiếu ở §2.5.

---

## 0. Đọc 30 giây

| Câu hỏi | Trả lời |
|---|---|
| **Nhà dữ liệu** (số DocType chứa biến/số ảnh hưởng giá) | **19 → 16** (danh sách tên ở §2.4; **cần B0 đếm lại trên site**) |
| **Màn người dùng phải mở — Sales** | **0 → 0** |
| **Màn người dùng phải mở — Quản trị cấu hình** | **10 → 10** nếu chỉ làm R3–R6; **→ 1 màn/sản phẩm + 3 màn toàn hệ** nếu làm thêm Đ1–Đ5 |
| **Màn người dùng phải mở — Kỹ thuật** | **2 → 2** (ẩn khỏi menu nghiệp vụ) |
| Có gộp thêm DocType nào không? | **Không. 0/10 gộp được** (§2.6). Giữ tách theo R7. |
| Có làm mất khả năng mở rộng / thành hardcode không? | Mục tiêu: **giảm từ 11 cụm tên viết cứng xuống 5** ở bước B3; 5 cụm còn lại là hợp đồng engine, phải khai đúng một chỗ. |
| Cái gì không được đánh đổi? | **Số tiền.** Mọi bước có cổng `GIA_VAT = 22.717.289` cho BOM chuẩn CDMQ-2C (±1 đ). |
| Việc gấp nhất (làm trước) | **B0 đo** (1 ngày): đếm dữ liệu, tính lại 2 mốc giá, đếm điều kiện bật R6 — **vẫn là việc chặn duy nhất**, chưa có site. |
| Còn câu hỏi nào? | **0** — Owner đã chốt **làm cả Đ1–Đ5** (2026-11-27, §7). |

**Ba câu chốt:**

1. **Bản 1 trộn hai đơn vị.** "34 → 10" là so **34 nơi khai** với **10 tên DocType**. Bản 2 tách
   thành hai chỉ số riêng: **số nhà dữ liệu** (19 → 16) và **số màn người dùng** (theo 3 nhân vật).
2. **Không gộp DocType nào (R7).** 10 bề mặt hiện tại đều có lý do tách thật; cái giảm được là
   **số màn và số bước**, làm bằng màn tổng hợp + mẫu + mặc định + kiểm lúc lưu (Đ1–Đ5).
3. **Năm việc phải làm để thật sự đơn giản** (Đ1–Đ5, §4.3): màn "Cấu hình sản phẩm"; tạo sản phẩm
   từ mẫu; hồ sơ biến mặc định hiện đủ + cấp quyền đúng người; 4 field mới **tự suy**; `calc_expr`
   làm nguồn duy nhất cho "cách tính".

---

## 1. Đính chính so với bản 1

Mọi dòng dưới đây đo trên mã (`~/myfrappe/apps/alumglass`, nhánh `master`, commit `e767108`) và
`~/myfrappe/apps/formula_builder`. Chỗ nào bản 1 đúng thì giữ nguyên, không nhắc lại.

| # | Bản 1 ghi | Đo lại | Nguồn / cách đo |
|---|---|---|---|
| 1 | "34 → 10" | **Trộn đơn vị.** 34 = 27 nơi dữ liệu + 7 danh sách trong mã (đơn vị "nơi"). 10 = tên DocType. Cùng đơn vị DocType: **19 → 16**. Cùng đơn vị "nơi": **34 → ~18** (ước lượng, cần B0) | đối chiếu §2.4 cũ với §4.2; danh sách tên ở §2.4 bản này |
| 2 | "5/39 ô dữ liệu của một dòng BOM là ô chết — 12,8 % diện tích form là nhiễu" | **Sai.** 39 field dữ liệu, **13 đã `hidden=1`**, còn **26 hiện** (24 ô nhập, 2 ô HTML). **5/6 ô chết đã ẩn sẵn**; chỉ `AL Color Standard.surcharge_rule` còn hiện | đếm `hidden` trong `al_bom_item.json`; `grep -rn "\bsurcharge_rule\b" --include=*.py --include=*.js` = 0 |
| 3 | "Nghiệm thu B6a: form dòng BOM còn 34 ô hiển thị" | **Sai số học.** Hôm nay đã là 26 (24 ô nhập). Pha "ẩn trước" **không đổi gì trên màn hình** | như trên |
| 4 | "12/21 patch = 57 %" | **12/18 = 67 %** | `grep -v '^\[' patches.txt \| grep -v '^$' \| wc -l` = 18 |
| 5 | "sidebar có 12 nhóm menu" | **11 nhóm** | `alumglass_workspace_sidebar.json` (11 phần tử) |
| 6 | "`AL Variable Profile` 10 khối nguồn" | **11 `source_kind`** (`slug_reference` xử lý riêng ở `adapters.build_references`) | `al_variable_profile_rule.json` field `source_kind` |
| 7 | "7 danh sách tên biến cứng trong mã" | **11 cụm.** B3 xoá 6, **còn 5** (bảng ở §3 P5) | quét mã sản xuất, bỏ `patches/`, `tests/` |
| 8 | "`AL Variable Set Item` lặp lại định nghĩa biến" | **Không đúng như bản phản biện nói.** `var_label`/`var_type` có `fetch_from` + `read_only=1`; `link_doctype`/`select_options` `read_only=1`; **chỉ `default_value` là override có chủ đích** | `al_variable_set_item.json` |
| 9 | `Formula Set` (B7) là bảng chết của alumglass | **Sai nguồn gốc.** `Formula Set` + `Formula Set Line` thuộc **app `formula_builder`** (`module: Formula Builder`). ⛔ Không xoá, ⛔ gọi "mồ côi"; chỉ bỏ **field trỏ** `AL Bom Item.formula_set` (R5) | `formula_builder/**/doctype/formula_set/formula_set.json` |
| 10 | "`AL Variable Library` mọi biến hệ bỏ `default_value` (R4)" | Đúng ý, nhưng **hệ quả quyền** bị bỏ sót: `Formula Global Variable` chỉ **System Manager** đọc/ghi ⇒ sau R4 người quản trị nghiệp vụ **không sửa được VAT** nữa (§3 P11, §4.3 Đ3) | `formula_global_variable.json` (permissions) + `setup/install_roles.py` |

> **Số cần B0 xác nhận trên site** (mã có thể khác DB): **19 / 16 / 18**. Tên đã liệt kê đủ ở §2.4,
> B0 chỉ cần đối chiếu sự tồn tại + số bản ghi, không phải suy lại.

---

## 2. Kiểm kê thật — ba tầng

Phân tầng theo yêu cầu: **định nghĩa biến** (catalog) · **quy tắc/giá trị tính** · **nơi dùng**.
Một nơi có thể vừa định nghĩa vừa dùng; bảng ghi theo **vai chính**.

### 2.1 Tầng A — Định nghĩa biến (catalog)

| # | Nơi | Cấu hình cái gì | Ai đọc | Bắt buộc? | Trùng vai với |
|---|---|---|---|---|---|
| A1 | `AL Variable Library` (25 seed: 15 biến người dùng + 10 biến hệ) | tên, nhãn, kiểu, `is_system`, `source_doctype`+`source_field`+`source_link_field`, `default_value` | `system_variable_resolver.py`, `variable_sources/adapters.py`, `al_formula_rules/rule_input.py`, api autocomplete | **Có** | A2, A3, A4, A6 |
| A2 | `AL Variable Settings.common_variables` (8 dòng) | biến gợi ý trong ô công thức | `api:958`, `adapters.common_var` | Không | 7/8 trùng tên A1 |
| A3 | `AL Variable Settings.row_literals` (`AL Row Literal`, 11 dòng) | biến theo dòng BOM + nguồn | `adapters.row_literal`, `api:1288`, `rule_input` | Không | A1, A9 |
| A4 | `Formula Global Variable` (4 seed) | hằng số toàn cục | `bom_orchestrator:745`, `global_variable_cache` | Không | A1 (`VAT_RATE` khai 2 nơi) |
| A5 | `Formula Variable Binding` (FB; được **chép** từ A1+A4 bằng 2 patch) | binding resolve giá trị | `_resolve_fb_context()` | Không | **Bản sao của A1/A4** — không phải nguồn |
| A6 | `AL Variable Set` + `AL Variable Set Item` (2 bộ seed: 11 + 14 dòng) | biến nào sản phẩm hỏi + mặc định + bắt buộc | `adapters.variable_set`, dialog Tham số BOM | Không | A1 (chỉ `default_value` là override thật) |
| A7 | `AL Profile System` (`offset_*` + child `system_variables`) | khe hở khung/cánh/kính + ghi đè biến hệ theo hệ nhôm | `system_variable_resolver` | Không | A1 (`OFFSET_*` có nguồn tại đây), A8 |
| A8 | `AL Rule` kiểu `CONSTANT` có mã = tên biến (`OFFSET-FRAME`…) | giá trị dự phòng cho biến hệ | `bom_orchestrator:1068-1077` | Không | A1, A7 |
| A9 | `field_provenance.ROW_LITERAL_SOURCES` — **9 tên cứng** | nhãn + nguồn mặc định của biến dòng | `adapters.row_literal`, nhãn gợi ý chéo dòng | Không | A3 |
| A10 | `api:919 _LEGACY_ROW_LITERALS` (11) + `:935 _LEGACY_COMMON_VARS` (8) | lưới an toàn khi bảng Settings rỗng | `get_formula_context` | Không | A2, A3 |
| A11 | `rule_input.ROW_RESOLVABLE_VARIABLES` — **17 tên cứng** | biến dòng nào **engine đọc được** ở bước chọn mã | validator `AL Rule` + api | **Có, ngầm** | A3 |

**Nguồn biến đăng ký bằng decorator (mô hình tốt, giữ nguyên):** `variable_sources/registry.py` có
**10 adapter** (`fvb_scope`, `cost_bucket`, `variable_library_system`, `variable_library_user`,
`variable_set`, `cost_template_line`, `formula_global`, `row_literal`, `common_var`,
`doctype_field`). Thêm nguồn mới = 1 decorator + 1 dòng options.

### 2.2 Tầng B — Quy tắc & giá trị tính

| # | Nơi | Cấu hình cái gì | Ai đọc | Ghi chú |
|---|---|---|---|---|
| B1 | `AL Rule` + 2 bảng con | dải ngưỡng / bảng tra / hằng số; tự khai `input_variable` + `input_scope` | `_lookup_rule`, `_resolve_dynamic_item` | **Đã gộp đúng** (2026-11-23) — giữ |
| B2 | `AL Quantity Calc Method` | `calc_fn` (Python lambda), `calc_formula` (chuỗi hiển thị), `input_vars` | `formula_handlers.lookup_calc_pattern` | Cùng 14 pattern tồn tại **3 bản** (P3) |
| B3 | `AL Cost Template Item.calc_formula` | chuỗi công thức dòng chi phí (14 dòng `CT-01-STANDARD`) | engine B6 | Đúng chỗ |
| B4 | `AL Bom Item` — **8 field công thức** | công thức từng dòng nhôm/kính | engine B3 | 2 field chết (P4) |
| B5 | `AL Accessory Item.qty_formula` | công thức số lượng phụ kiện | engine B3 | Đúng chỗ |
| B6 | `Formula Global Variable.formula_expr` | hằng số tính bằng công thức khác | `global_variable_cache` | 4/4 seed là `CONSTANT` — chưa dùng |
| B7 | `Formula Set` + `Formula Set Line` (**app FB**) | bộ công thức đặt tên | **không nơi nào đọc** (link `AL Bom Item.formula_set` chết) | ⛔ Không xoá; R5 bỏ field trỏ |
| B8 | `AL Product Type` (`nc_pct`, `nc_ld_rate`, `profit_margin`) | % nhân công / lợi nhuận theo loại sản phẩm | qua biến hệ `NC_SX_PCT`… | **Nhà giá bị bỏ sót ở bản 1** |
| B9 | `AL Material Category` (`default_calc_pattern`, `default_cost_bucket`, `default_scrap_pct`) | mặc định theo nhóm vật tư | engine B2/B3 | **Nhà giá bị bỏ sót** |
| B10 | `AL Cost Bucket` (`source_type`, `source_config` JSON, `depends_on` JSON) | nhóm chi phí lấy từ đâu | `bom_orchestrator:4303` | **Nhà giá bị bỏ sót**; JSON thô, không có UI kiểm |
| B11 | `AL Bom Set.formula_fieldnames` (JSON 6 tên) | field nào engine đánh giá là công thức | `bom_orchestrator:1712` | Trùng B12 + `DEFAULT_FORMULA_FIELDS` (P1) |
| B12 | `AL Formula Field` (11 bản ghi seed) | cùng việc với B11 nhưng cho editor JS | `api/formula_registry.py`, `formula_setup.js` | Nguồn đúng — nhưng engine **không** đọc |
| B13 | `AL Color Standard.price_multiplier` + `AL Variable Dimension Mapping.price_multiplier` | nhân giá theo màu / theo chiều giá | `bom_orchestrator:2374-2394` | **Hai nhà giá bị bỏ sót**; thứ tự thắng **có trong mã** (`linked_mult` thắng `map_mult`) nhưng **chưa có tài liệu** |

**Giá trị số rời rạc:** 22 field Float/Currency có tên chứa `pct|rate|margin|offset|multiplier|scrap`
trên 14 DocType; **11 field thật sự ảnh hưởng giá**, nằm trên **6 DocType**: `AL Product Type` (3),
`AL Profile System` (4), `AL Material Category` (1), `AL Bom Item` (1), `AL Color Standard` (1),
`AL Variable Dimension Mapping` (1). **5/6 DocType này không có mặt trong danh sách 10 của bản 1.**

### 2.3 Tầng C — Nơi dùng

| # | Nơi | Vai |
|---|---|---|
| C1 | `AL Bom Set` + `AL Bom Item` | chọn biến, công thức, quy tắc, nhóm chi phí |
| C2 | `AL Accessory Set` + `AL Accessory Item` | như trên cho phụ kiện |
| C3 | `AL Cost Template` + `AL Cost Template Item` | chuỗi 14 dòng chi phí |
| C4 | `AL Bom Set.variable_set` / `AL Accessory Set.variable_set` | bộ biến của sản phẩm |
| C5 | `variable_profile` trên 4 DocType | bộ lọc danh sách biến trong autocomplete |
| C6 | `AL BOM` (`bom_set` reqd, `default_cost_template` reqd) + `AL BOM Version` | **nối các mảnh; bắt buộc để bán được — bản 1 bỏ sót** |

### 2.4 Tổng số bề mặt

| Tầng | Nơi là dữ liệu | Danh sách cứng trong mã | Cộng |
|---|---|---|---|
| A — định nghĩa biến | 8 (A1–A8) | 4 (A9, A10 ×2, A11) | **12** |
| B — quy tắc / giá trị tính | 13 (B1–B13) | 3 | **16** |
| C — nơi dùng | 6 | 0 | **6** |
| **Tổng** | **27** | **7** | **34** |

**Danh sách "nhà dữ liệu" (DocType) — 19 hôm nay, 16 sau lộ trình:**

| Nhóm | DocType | Hôm nay | Sau |
|---|---|---|---|
| 10 bề mặt của bản 1 | `AL Variable Library`, `Formula Global Variable`, `AL Variable Set`, `AL Rule`, `AL Quantity Calc Method`, `AL Bom Set`, `AL Accessory Set`, `AL Cost Template`, `AL Formula Field`, `AL Variable Profile` | 10 | 10 |
| 6 nhà giá bị bỏ sót | `AL Product Type`, `AL Profile System`, `AL Material Category`, `AL Cost Bucket`, `AL Color Standard`, `AL Variable Dimension Mapping` | 6 | 6 |
| Bị bỏ / không còn lối vào | `AL Variable Settings` (R3 bỏ), `Formula Variable Binding` (FB sinh tự động, không khai tay), `Formula Set` (FB, không còn field trỏ sau R5) | 3 | 0 |
| **Cộng** | | **19** | **16** |

> `AL BOM` + `AL BOM Version` là nhà **điều phối** (không phải nhà khai giá trị) — không tính vào 16,
> nhưng **phải tính vào số màn người dùng** (§0, §4.3 Đ1).

### 2.5 Đối chiếu FB-first — cái gì `formula_builder` đã có (đọc mã FB, không đoán)

Đo trên `~/myfrappe/apps/formula_builder`: **19 `@register_source`** trong `api/data_source_registry.py`,
`get_live_context` (`api/formula_builder.py:402`), `get_suggestions` (`:45`),
`resolve_all_bindings_batch` (`api/batch_binding_resolver.py:690`), `get_scope_bindings[_multi]`,
`global_variable_cache`, `compile_expression` (`security/safe_eval`).

| # | FB có | alumglass đang làm gì | Đề xuất (theo R2) | Loại |
|---|---|---|---|---|
| F1 | `Formula Variable Binding` + 19 `source_type` | **chép** biến sang FVB bằng 2 patch (`v28_9`, `v28_11`) | FVB là nhà binding duy nhất; alumglass ghi qua API FB khi lưu catalog | **bỏ bản sao** |
| F2 | `linked_doctype_field` + tự dò field Link | `al_bom_engine/system_variable_resolver.py` (215 dòng) tự dò + đọc `system_variables` | ⚠ **Đánh giá lại ở B4b**: module này đang chạy đúng và là **khuôn cho loader biến theo dòng** (B3). Chỉ bỏ phần trùng FB; giữ `AL Profile System.system_variables` làm 1 lớp override sau FB | **bỏ phần trùng** |
| F3 | `Formula Global Variable` + cache Redis | đọc qua FB (**đúng**), nhưng khai trùng `default_value` trong Library | FGV là nhà duy nhất (R4) | **bỏ bản sao dữ liệu** |
| F4 | `get_live_context` + `resolve_all_bindings_batch` | `_resolve_fb_context()` gọi FB (**đúng**), rồi chạy 6 bước fallback riêng | 1 lần gọi FB là nguồn chính; giữ lớp override nghiệp vụ + chuẩn hoá % | **gộp** |
| F5 | `get_suggestions` / `SuggestionsBuilder` (7 nhóm) | `get_formula_context` tự dựng **10 khối** song song | 4 nhóm lấy từ FB; alumglass chỉ giữ nhóm riêng ngành | **gộp** |
| F6 | `aggregate_from_items` | **đã dùng** (`bom_orchestrator:4253`) | Giữ, làm mẫu | **đã đúng** |
| F7 | `range_lookup`/`matrix_lookup`/`composite_key_lookup` | `al_formula_rules/rule_engine.py` (330 dòng) tự cài | Đánh giá thay; không giữ được 3 tiêu chí thì **giữ `rule_engine`** + bọc `@register_source("al_rule")` | **đánh giá / bọc** |
| F8 | `api/settings_cache.get_allowed_funcs()` | **2 định nghĩa mã** cho cùng 3 hàm; `get_allowed_funcs()` **không được gọi ở đâu trong alumglass** (0 hit) | Đọc danh sách từ FB; giữ **1 bảng callable** nghiệp vụ (callable phải là mã) | **gộp** |
| F9 | `normalize_global`, `safe_eval` + `FormulaValidator`, `Formula Column Name` | đã dùng đúng; `AL Formula Field` là siêu tập | Giữ `AL Formula Field` (extension hợp lệ ở phía alumglass) | **giữ extension** |

**Kết luận R2:** 5 chỗ làm lại (F1–F5) + 1 chỗ (F8) → 0; 2 chỗ đã đúng (F6, F9) giữ; 1 chỗ (F7)
đánh giá thay hoặc bọc. **Không cần sửa một dòng nào trong `formula_builder`.**

### 2.6 Bảng "PHẢI TÁCH / GỘP ĐƯỢC" theo R7

Quyền ghi đọc từ `alumglass/setup/install_roles.py` (JSON DocType chỉ giữ System Manager; quyền
nghiệp vụ do `install_roles.py` cấp bằng Custom DocPerm).

| # | Nơi | Nhân vật ghi được | Kết luận | Lý do tách / **nếu gộp thì mất gì** | Tần suất |
|---|---|---|---|---|---|
| 1 | `AL Variable Library` | BOM Manager | **PHẢI TÁCH** | 5 nơi đọc (engine, autocomplete, validator `AL Rule`, Variable Set, con trỏ FGV). Nhúng vào từng nơi = lặp định nghĩa | 1 lần/hệ |
| 2 | `Formula Global Variable` | System Manager (FB) | **PHẢI TÁCH** | Hằng số dùng chéo app + cache Redis TTL 60s + invalidate qua hook của FB. Chép sang library = 2 bản, trôi | 1 lần/hệ |
| 3 | `AL Variable Set` (+Item) | BOM Manager | **PHẢI TÁCH** | Quan hệ nhiều-nhiều; mỗi bộ một `default_value`/`is_required` riêng (`default_value` là **override có chủ đích**). Gộp = mỗi biến chỉ còn 1 mặc định toàn hệ | mỗi nhóm sản phẩm |
| 4 | `AL Rule` (+2 bảng con) | BOM Manager | **PHẢI TÁCH** | 3 loại + **2 bảng con** + `AL Rule Version` + cổng chặn trùng mã + cổng `result_type`; 4 nơi đọc. Gộp = mất bảng dòng + version | khi ngưỡng đổi |
| 5 | `AL Quantity Calc Method` | Technical Admin | **PHẢI TÁCH** | Là **thuật toán**, tái dùng nhiều dòng/nhiều bộ; không phải thuộc tính của một biến. Gộp = nhân bản thuật toán theo từng biến | 1 lần/hệ |
| 6 | `AL Bom Set` (+Item) | BOM Manager | **PHẢI TÁCH** | 14–24 dòng × 39 field dữ liệu; engine đọc từng dòng; `AL BOM Version` snapshot **mọi** field theo meta (`_get_bom_item_data_fields`) | mỗi sản phẩm |
| 7 | `AL Accessory Set` (+Item) | BOM Manager | **PHẢI TÁCH** | Được tái dùng chéo nhiều Bom Set qua `default_accessory_set` | mỗi sản phẩm |
| 8 | `AL Cost Template` (+Item) | BOM Manager | **PHẢI TÁCH** | 14 dòng giá, dùng chung nhiều BOM (`CT-01-STANDARD` cho 2C và 4C), snapshot theo version | 1 lần/hệ |
| 9 | `AL Formula Field` | BOM Manager (⚠ nên là kỹ thuật) | **PHẢI TÁCH** | Metadata `(doctype, child_table, fieldname)` — JSON DocType không thể biết "field nào là công thức"; editor JS đọc qua `api/formula_registry.py` | 1 lần/hệ |
| 10 | `AL Variable Profile` (+2 child) | BOM Manager (⚠ nên là kỹ thuật) | **PHẢI TÁCH về dữ liệu**; ⛔ **không bắt người dùng mở** | Hạt khác: theo *(ngữ cảnh doctype × field × nguồn)*, có regex/prefix/JSON, 11 `source_kind`. Gộp = mỗi biến phải khai lại danh sách doctype ⇒ N×M dòng | 0 nếu suy tự động |

**Kết luận: 0/10 gộp được.** Cái gộp được duy nhất là `AL Variable Settings` (ngoài 10) theo R3.
Việc giảm công sức **phải** làm bằng UI điều phối (§4.3 Đ1–Đ5), không bằng gộp bảng.

---

## 3. Đau thật (đo được)

### P1 — Ba danh sách cùng trả lời "field nào là field công thức"

`AL Formula Field` (11 bản ghi) cho **editor**; `AL Bom Set.formula_fieldnames` (JSON 6 tên) cho
**engine**; `DEFAULT_FORMULA_FIELDS` (6 tên, `bom_orchestrator.py:439`) là dự phòng cứng.
`panel_count_formula` / `qty_per_panel_formula` **không có trong cả ba** ⇒ khai xong engine
**không bao giờ tính**, không cảnh báo. Đây là kiểu hỏng im lặng nặng nhất: *nhập liệu thành công,
số ra sai.*

### P2 — Cùng một con số khai 2–3 nơi, và nơi "trông như đúng" lại không có tác dụng

| Con số | Nơi 1 | Nơi 2 | Nơi 3 |
|---|---|---|---|
| `VAT_RATE = 10` | `AL Variable Library.default_value` | `Formula Global Variable.constant_value` | FVB (sinh từ nơi 2) |
| `NC_SX_PCT = 8` | `AL Variable Library.default_value` | `AL Product Type.nc_pct` | FVB (sinh từ nơi 1) |
| `OFFSET_FRAME` | `AL Profile System.offset_frame` (48 XINGFA_55, **44** ALUMIL_M9560) | `AL Rule` `OFFSET-FRAME = 48` | `AL Profile System.system_variables` |

Thứ tự ghi đè thật (`bom_orchestrator.py:708-855`, **9 bước**): `1.1` user nhập → `1.2` FGV →
`1.4` FVB → `1.3` Library (chỉ điền chỗ thiếu) → `1.4b` child `system_variables` → `1.5` user nhập
(áp lại) → `1.5c` resolve lại theo profile override → `1.6` `default_value` → `1.7` chuẩn hoá %.
Vì `1.4` chạy **trước** `1.3` và FVB đã có `VAT_RATE` (patch `v28_9` seed mọi FGV kiểu `CONSTANT`
→ **đọc mã, chưa đối chứng trên site**), sửa `Library.default_value` của `VAT_RATE` **không làm giá
đổi**, không cảnh báo. ⇒ B0 phải kiểm đúng ca này.

### P3 — Cùng một công thức số lượng tồn tại 3 bản

14 pattern: (1) `AL Quantity Calc Method.calc_fn` (DB, thực thi); (2) `PATTERN_FORMULAS`
(formula_handlers.py:28, **14 lambda viết cứng**); (3) `calc_formula` (chuỗi hiển thị, **gõ tay**,
là **câu tiếng Việt** như `"(Dài mm / 1000) × TLR"` — không chạy được). Sửa (1) quên (3) ⇒ màn
hình giải thích một đằng, máy tính một nẻo. Xoá record ⇒ im lặng rơi về (2): số vẫn ra, nhưng là
công thức **cũ**.

### P4 — Sáu ô chết: hãy gọi đúng tên là **dọn dữ liệu**

| Field | DocType | Số nơi đọc | Đang hiện trên form? |
|---|---|---|---|
| `price_rule` | `AL Bom Item` | 1 (chỉ `set_query`) | **không** (`hidden=1`) |
| `formula_set` | `AL Bom Item` | **0** | **không** |
| `panel_count_formula` | `AL Bom Item` | **0** | **không** |
| `qty_per_panel_formula` | `AL Bom Item` | **0** | **không** |
| `panel_glass_override_allowed` | `AL Bom Item` | **0** | **không** |
| `surcharge_rule` | `AL Color Standard` | **0** | **có** |

5/6 **đã ẩn từ trước** ⇒ R5 là **dọn dữ liệu** (để không ai khai lại vào ô chết), ⛔ **không** được
bán là "giảm 12,8 % nhiễu form". Chỉ `surcharge_rule` là ô chết còn hiện.

### P5 — Thêm một biến theo dòng phải sửa 4 tệp mã; **11 cụm tên cứng**

4 tệp: `b2_prefetch_master_data` (dựng `lit`), `b3_build_formulas` (danh sách inject),
`field_provenance.py`, `rule_input.py`. **11 cụm tên cứng** trong mã sản xuất:

| Cụm | Số tên | Nguồn |
|---|---|---|
| `DEFAULT_FORMULA_FIELDS` | 6 | `bom_orchestrator.py:439` |
| `PATTERN_FORMULAS` | 14 | `formula_handlers.py:28` |
| `ROW_RESOLVABLE_VARIABLES` | 17 | `al_formula_rules/rule_input.py:59` |
| `ROW_LITERAL_SOURCES` | 9 | `variable_sources/field_provenance.py` |
| `_LEGACY_ROW_LITERALS` + `_LEGACY_COMMON_VARS` | 11 + 8 | `api/__init__.py:919,935` |
| 2 danh sách inject trong `b3_build_formulas` | 8 + 10 | `bom_orchestrator.py:3232,3239` |
| **`FORMULA_FIELDS`** | 4 | `al_bom_engine/doctype/al_bom_item/al_bom_item.py:11` |
| **`ENGINE_SYNTHETIC_FIELDS`** (+1 điều kiện) | 3 (+1) | cùng tệp |
| **`_GROUP_BY_KEY`** | 14 mã pattern | `formula_handlers.py:53` |
| **`_DISPLAY_LABELS` / `_DISPLAY_UNITS`** | 8 / 4 | `field_provenance.py` (đang chạy thật: `bom_orchestrator.py:3494,3541,3751,3915`) |

B3 xoá **6** cụm đầu; **5 cụm còn lại** phải khai đúng một chỗ và có lý do (hợp đồng engine).

### P6 — Ba bảng cấu hình biến không có trên menu nào

`alumglass_workspace_sidebar.json` có **11 nhóm**. `AL Variable Settings`, `AL Variable Profile`,
`AL Formula Field`, `Formula Global Variable` **không nằm trong nhóm nào**. Trong khi
`AL Variable Profile` quyết định **biến nào hiện ra** (`default_action = EXCLUDE_ALL`): cấu hình sai
⇒ biến hợp lệ biến mất khỏi gợi ý, không dấu vết.

### P7 — Autocomplete có 2 đường song song

`get_formula_context` (`api/__init__.py:1130`): đường A = `AL Variable Profile` (10 adapter),
đường B = legacy **10 khối đánh số** (`0`–`9`, dòng 1197–1361). Thêm nguồn biến mới phải sửa **cả hai**.

### P8 — 67 % patch là patch cấu hình

**12/18** patch trong `alumglass/patches.txt` liên quan biến/quy tắc/giá thành. Bốn patch
(`v28_9.seed_fvb_*`, `v28_11.seed_fvb_full_*`, `v28_14.seed_variable_catalog`,
`v28_15.sync_variable_sources_and_fields`) tồn tại **chỉ để chép dữ liệu từ bảng này sang bảng kia**.

### P9 — **MỚI:** biến mới tạo **không hiện** trong ô công thức

Hồ sơ mặc định `P_BOM_DEFAULT` (`patches/v28_14/seed_bom_profile.py`) đặt
`default_action = EXCLUDE_ALL` với **6 rule Include** — **không có** `variable_library_user`,
**không có** `row_literal`. Chạy thật `variable_sources/rules.py::select_candidates` với đúng 6 rule
đó (`python3 -I`, không cần site):

```
Trước  : ['NC_SX_PCT', 'n_panel']          ← W_mm BIẾN MẤT
stats  : {'excluded_by_rules': 1}
Sau khi thêm rule Include variable_library_user: ['W_mm','NC_SX_PCT','n_panel']
```

⇒ Tạo biến trong `AL Variable Library` xong, mở `AL Bom Set` **không thấy biến**; muốn thấy phải
thêm vào `AL Variable Set` của từng bộ ⇒ **2 màn, 2 nơi khai**, phá vỡ lời hứa "1 bản ghi".

### P10 — **MỚI:** biến theo dòng chưa có bộ nạp giá trị chung

`bom_orchestrator.py:1663` dựng `lit = {...}` bằng **20 khoá viết tay** (trọng lượng, đơn giá,
kính, màu, vị trí lắp…). B3 chỉ **xoá danh sách**, không có bước **nạp giá trị cho biến mới**.
Kết quả: biến hiện trong gợi ý nhưng engine trả **0 im lặng** — đúng loại hỏng mà
`tra-cuu-quy-tac-de-hieu.md` §7.6 được viết ra để chặn.
Đường đúng đã có sẵn: `AL Variable Library` **đã có** `source_doctype` + `source_field` +
`source_link_field`, và `al_bom_engine/system_variable_resolver.py` **đã** resolve generic theo 3
cột đó (cho biến hệ). Cần **một bộ nạp tương tự cho biến theo dòng** (B3).

### P11 — **MỚI:** R4 + R6 biến hai trường tuỳ chọn thành **bắt buộc**

Hôm nay `AL Bom Set.profile_system` và `.product_type` **không reqd**; để trống vẫn ra giá (nhờ
`Library.default_value` 8/12/16 + fallback `AL Rule` CONSTANT 48). Sau R4 (xoá `default_value` của
biến hệ) + R6 (chặn khi thiếu nguồn), hai trường này **thành bắt buộc trên thực tế**.
⇒ Đây là **thêm việc cho người dùng**, ngược mục tiêu. Cách xử: **điền dữ liệu về đúng nhà trước**
(B0 đếm (a)(b)); và ghi rõ trong tài liệu hướng dẫn rằng thiếu `Profile System` / `Product Type`
thì **không tính được** — kèm câu cảnh báo nêu tên trường và nơi sửa.

---

## 4. Mô hình đích

### 4.1 Nguyên tắc

1. **Một bản.** Một khái niệm chỉ có một nhà. Nhà khác chỉ được **trỏ** hoặc **sinh ra**.
2. **Máy học từ metadata, không học từ danh sách.** Engine đọc `AL Variable Library` +
   `AL Formula Field` để biết có biến gì, field nào là công thức.
3. **Mở rộng bằng dữ liệu.** Thêm biến / quy tắc / cách tính ⇒ thêm bản ghi. Ngoại lệ duy nhất:
   **thuật toán mới** — khai đúng một chỗ và có cổng kiểm.
4. **Thiếu nguồn thì KÊU, không đoán.**
5. **FB-first (R2).** Cơ chế nào FB đã có thì dùng. Phần alumglass được giữ: **catalog nghiệp vụ**
   và **adapter/registry**.
6. **Bản sinh phải tự khai là bản sinh.** FVB read-only + nhãn "tự sinh".
7. **Tách vật lý, gộp trải nghiệm (R7).** Giữ DocType riêng khi tách phục vụ thiết kế; giảm màn
   bằng UI điều phối, ⛔ bằng cách gộp bảng.

### 4.2 Ba tầng sau khi gộp (giữ tách)

| Tầng | Còn | Vai | Ai sở hữu |
|---|---|---|---|
| **Định nghĩa biến** | `AL Variable Library` (duy nhất) | khai biến: tên, nhãn, kiểu, lấy từ đâu, có từ lúc nào, có phải người dùng nhập | alumglass |
| | `Formula Global Variable` | hằng số toàn cục + cache | **FB** |
| | `Formula Variable Binding` | bộ phân giải — chỉ đọc, tự sinh | **FB** |
| | `AL Variable Set` | biến nào sản phẩm này hỏi + mặc định + bắt buộc | alumglass |
| **Quy tắc / giá trị tính** | `AL Rule` | ngưỡng / tra bảng / hằng số | alumglass (bọc thành source type FB — F7) |
| | `AL Quantity Calc Method` | 14 pattern + `calc_expr` (Đ5) | alumglass |
| **Giá trị theo danh mục** | `AL Product Type` · `AL Profile System` · `AL Material Category` · `AL Cost Bucket` · `AL Color Standard` · `AL Variable Dimension Mapping` | % nhân công/lợi nhuận, khe hở, hao hụt, nhóm chi phí, hệ số giá | alumglass |
| **Nơi dùng** | `AL Bom Set`(+item) · `AL Accessory Set`(+item) · `AL Cost Template`(+item) · `AL BOM`(+version) | công thức + tham chiếu; **không** khai lại biến | alumglass |
| **Bộ lọc hiển thị** | `AL Variable Profile` | biến nào hiện trong autocomplete; **không** chứa giá trị | alumglass |

### 4.3 Năm thay đổi ưu tiên UI điều phối (Đ1–Đ5)

> Mỗi mục ghi rõ: **giảm gì · giữ gì · rủi ro · có sửa FB không (⛔ R2)**.

#### Đ1 — Màn "Cấu hình sản phẩm" (Page, ⛔ **không** DocType mới, ⛔ không chứa bản sao dữ liệu)

Một trang tổng hợp cho một sản phẩm: `AL BOM` + `AL Bom Set` + `AL Accessory Set` + `AL Variable Set`
+ `AL Cost Template` + `AL Variable Profile` + các `AL Rule` đang dùng. **Chỉ đọc**, mỗi khối có nút
"Sửa" mở đúng form. Khối nào đọc lỗi thì **hiện "không đọc được khối X"**, ⛔ im lặng.

- **Giảm:** 4–6 màn **xem/định vị** → 1. Số DocType giữ nguyên (đúng R7).
- **Giữ:** mọi DocType tách, mọi quyền, mọi version.
- **Rủi ro:** trang gom nhiều nguồn ⇒ nếu một nguồn lỗi mà trang vẫn hiện bình thường thì nó **nói
  dối**. Bắt buộc: trạng thái lỗi theo từng khối + thời điểm đọc.
- **Sửa FB?** ⛔ Không.

#### Đ2 — "Tạo sản phẩm từ mẫu" (dùng snapshot đã có)

`AL BOM Version.bom_set_snapshot` đã là JSON **đầy đủ mọi field dữ liệu** của mọi dòng Bom Item
(`al_bom_version.py::_get_bom_item_data_fields` đọc theo **meta**). Dùng nó (hoặc một bộ mẫu) để
**nhân bản** ra Bom Set / Accessory Set / Cost Template / Variable Set **mới** (DocType riêng, mã
mới), rồi mở Đ1.

- **Giảm:** ~14–24 dòng × 8 ô gõ tay → 1 lệnh + sửa vài ô.
- **Giữ:** các bộ vẫn **độc lập**; sửa bộ mới không đụng bộ cũ.
- **Rủi ro:** (a) **clone trôi** — nếu chép mà không ghi rõ "được tạo từ mẫu X lúc T" thì sau này
  không ai biết bộ nào là gốc; (b) `autoname = field:set_code` ⇒ phải sinh mã mới, ⛔ chép mã; (c)
  phải chép cả `variable_profile` / `variable_set` đang trỏ.
- **Sửa FB?** ⛔ Không.

#### Đ3 — Hồ sơ biến: mặc định **hiện đủ**, hồ sơ chỉ để **THU HẸP**; cấp quyền đúng người

Hai việc, cùng mục tiêu "thêm biến là thấy":

1. **Patch mới** thêm rule Include `variable_library_user` vào 3 hồ sơ seed
   (không sửa patch đã ghi Patch Log); đồng thời **không có hồ sơ ⇒ hiện đủ** (bỏ `EXCLUDE_ALL`
   ngầm định).
   - ⚠ **`row_literal` TÁCH KHỎI B3b (quyết định khi triển khai 2026-11-27):** chỉ hồ sơ
     `P_ACCESSORY_DEFAULT` dùng được literal trần (context B3 có `{slug}__*`); còn **B4 (BOM) và B6
     (Cost Template) KHÔNG có namespace literal trần** — engine chỉ có `inputs` toàn cục và
     `items.<slug>.<field>`. Thêm `row_literal` vào 2 hồ sơ đó là **mời người ta viết công thức ra
     0 âm thầm**, đúng thứ mà chính `seed_bom_profile.py` đã ghi lý do loại bỏ. `row_literal` chỉ
     được mở lại **sau** B3a (loader generic) và khi B3c đã có cảnh báo `bien_chua_co_o_buoc`.
     → Việc còn lại của Đ3 nằm ở **B3a + B3c**, không phải B3b.
2. **Cấp Custom DocPerm** cho `AL BOM Manager` trên `Formula Global Variable` (là **dữ liệu**,
   ⛔ sửa mã FB), + thêm lối vào menu. Nếu không: R4 giao thuế VAT cho bảng chỉ System Manager mở.

- **Giảm:** bỏ **1 nơi khai** (Variable Set) cho biến người dùng mới; bỏ "tạo xong không thấy".
- **Giữ:** hồ sơ vẫn dùng được để thu hẹp khi cần.
- **Rủi ro:** hiện thêm biến mà engine chưa nạp ⇒ **mời người ta viết công thức ra 0**. Bắt buộc
  làm **cùng B3** (loader + KÊU).
- **Sửa FB?** ⛔ Không (Custom DocPerm là dữ liệu).

#### Đ4 — Bốn field mới của `AL Variable Library`: **TỰ SUY**, chỉ còn 1 ô chọn có nhãn Việt

| Field bản 1 | Bản 2 |
|---|---|
| `scope` Select `GLOBAL/ROW/INPUT` | **suy** từ `category` + `is_input` đã có |
| `source_kind` Select 5 mã | **suy** từ `source_doctype`/`source_field`/`default_value` |
| `available_at` Select 3 mã | **suy từ chính engine**: `b2_prefetch_master_data` xuất tập khoá nó **thực có**; `b3`/`b6` xuất tập sau |
| `is_input` Check | **suy** từ `AL Variable Set` / `is_required` |

Form chỉ hiện **một** ô chọn, nhãn Việt: *"Dùng ở: Toàn đơn / Từng dòng / Người dùng nhập"*.
Engine **KÊU** `bien_chua_co_o_buoc:<tên>:<bước>` khi công thức/rule đọc biến chưa có.

- **Vì sao không khai tay:** `available_at` khai tay là **bảng sự thật thủ công thứ hai về năng lực
  của mã** — đúng loại bảng mà "người nuôi chết thì bảng nói dối". Hồ sơ biến hiện nay **đã là**
  bảng đó (`seed_bom_profile.py` giải thích rõ: cố ý loại `row_literal`/`cost_bucket` vì "gợi ý sẽ
  dẫn tới công thức ra 0"). Bỏ `ROW_RESOLVABLE_VARIABLES` (mã) mà thay bằng `available_at` (tay) là
  **đổi chỗ, không phải bỏ**.
- **Giảm:** 4 ô mã thô → 0; bỏ bảng sự thật thủ công.
- **Giữ:** khả năng khai tường minh khi cần (ô "Nâng cao").
- **Rủi ro:** nếu engine không KÊU thì xoá danh sách chặn sẽ tái sinh đúng lỗi §7.6.
- **Sửa FB?** ⛔ Không.

#### Đ5 — "Cách tính số lượng": `calc_expr` là **nguồn duy nhất**, `calc_formula` **sinh ra**, `calc_fn` = Nâng cao

Thêm `calc_expr` (cú pháp FB) là nguồn duy nhất; `calc_formula` (hiển thị) **sinh từ** `calc_expr`;
`calc_fn` giữ làm van kỹ thuật. `lookup_calc_pattern` **đã** dùng `compile_expression` của FB
(`formula_handlers.py:222-290`), chỉ cần đọc `calc_expr` trước `calc_fn`.

> ⚠ **Khác đề xuất UX1:** `calc_formula` hiện là **câu tiếng Việt** (`"(Dài mm / 1000) × TLR"`).
> Cho nó chạy thẳng bằng `safe_eval` sẽ **bắt người dùng gõ cú pháp** — ngược mục tiêu của
> `tra-cuu-quy-tac-de-hieu.md`. Đúng phải là **field mới**, không tái dùng `calc_formula`.

- **Giảm:** 3 bản công thức → 1 (P3); thêm cách tính = 1 bản ghi, **không cần DEV** cho phép tính thường.
- **Giữ:** `calc_fn` cho trường hợp đặc biệt; 14 pattern seed không đổi số.
- **Rủi ro:** `calc_expr` phải qua `FormulaValidator`; `calc_fn` phải **KÊU** khi bị dùng.
- **Sửa FB?** ⛔ Không (chỉ dùng `compile_expression` đã import sẵn).

##### Đã làm 2026-11-27 (B7)

| Việc | Chỗ đọc |
|---|---|
| `calc_expr` + mô tả tiếng Việt trên form; `calc_fn` đổi nhãn **"Python Lambda (nâng cao)"** + mô tả "chỉ dùng khi không viết được bằng cú pháp Formula Builder" | `al_quantity_calc_method.json` |
| Engine đọc `calc_expr` trước; `calc_fn` chỉ khi ô kia rỗng, mỗi mã **ghi log 1 lần** (⛔ bật hộp thoại giữa lượt tính) | `formula_handlers.py::lookup_calc_pattern`, `_warn_legacy_calc_fn` |
| Biến phụ tuỳ chọn có **mặc định** cho đường `calc_expr` (`piece_length/spacing/area_per_piece = 1`, `depth = 0`) — biểu thức viết thẳng `w / piece_length` không tự có `kw.get(...)`; giá trị `None`/`""` coi như thiếu | `_OPTIONAL_VAR_DEFAULTS` |
| `calc_expr` hỏng ⇒ **ném lỗi**, ⛔ lặng lẽ rơi xuống `calc_fn` (ra số khác mà không ai biết) | như trên |
| `calc_formula` (câu chữ) tự chép từ `calc_expr` khi trống **hoặc khi công thức vừa đổi** mà câu chữ không đổi ⇒ không lệch phép tính; admin vẫn đặt được câu tiếng Việt | `al_quantity_calc_method.py::validate` |
| Đổi `calc_expr` cũng bị khoá theo role như `calc_fn` (đổi công thức = đổi tiền) | như trên |
| Patch `v1_0.backfill_calc_expr`: 14 mã, **chỉ điền khi `calc_fn` khớp seed** (so body đã chuẩn hoá bằng `ast.unparse`); công thức riêng của site ⇒ **bỏ qua + liệt kê** | `patches/v1_0/backfill_calc_expr.py` |
| Bảng biểu thức `CALC_EXPR` đặt **một bản** trong `formula_handlers.py`; seed và patch cùng đọc ⇒ không có bản chép trôi | `formula_handlers.CALC_EXPR` |

### 4.4 Bảng BỎ / GỘP / GIỮ (thêm cột "Người dùng thấy gì đổi")

| Nơi hiện tại | Quyết | Thay bằng | Ai đang dùng | Dữ liệu cũ | **Người dùng thấy gì đổi** | Đường lùi |
|---|---|---|---|---|---|---|
| `AL Variable Settings.common_variables` | **BỎ bảng con** (R3) — ✅ chép 2026-11-27, ✅ **xoá hẳn** (patch `v1_0.drop_variable_settings_tables`) | `AL Variable Library` với `is_input=1` | `catalog_rows.KIND_COMMON` (thay `adapters.common_var` + `api:_settings_variable_entries`) | Patch chép **mọi dòng thật** (giữ `group_label`, `sort_order`); bảng đã DROP | Màn "Cấu hình chung" **không còn**; danh sách biến **không đổi tên** | Restore backup |
| `AL Variable Settings.row_literals` | **BỎ bảng con** (R3) — ✅ chép 2026-11-27, ✅ **xoá hẳn** (cùng patch) | `AL Variable Library` với `category = Row Literals` | `catalog_rows.KIND_ROW` (thay `adapters.row_literal`, `get_row_literal_names`, `api:1288`) | Chép mọi dòng; `source_doctype`/`source_field` đã có | như trên | như trên |
| `AL Variable Settings` (Single) | **BỎ hẳn** (R3) — ✅ 2026-11-27 (bảng + `tabSingles` đã DROP) | `default_profile` → `AL Variable Profile.is_default`; `preview_doctype` → profile | `api/variable_catalog.py::_resolve_profile_doc`, `al_variable_profile.js` | Patch chép 2 giá trị; `_resolve_profile_doc` chỉ còn đọc `is_default` (nhánh Single đã bỏ) | Màn cũ **không còn tồn tại** | Trước khi xoá: JSON trong `private/backups/`; ⛔ không rollback code được |
| `AL Variable Profile` | **GIỮ** (bộ lọc duy nhất) + nhận 2 field (R3); **BỎ đường legacy 10 khối** | — | autocomplete | — | Autocomplete **không đổi tập tên** nếu làm đúng B2 | Giữ legacy sau cờ tới hết B4 |
| `AL Profile System.system_variables` | **GIỮ** nhưng hiện cạnh field gốc + câu "đang ghi đè `offset_frame` (48)" | — | resolve sau FB (1 lớp override) | — | Thấy rõ đang bị ghi đè (trước đây không) | — |
| `AL Rule` CONSTANT trùng tên biến | **BỎ hành vi fallback (R6)** | cảnh báo `thieu_nguon_bien:<tên>` + **chặn** | 4 rule seed | Rule vẫn là dữ liệu hợp lệ | **Có thể bị chặn tính** nếu thiếu `Profile System`/`Product Type` (P11) | Bỏ 8 dòng 1068–1077; revert |
| `Formula Global Variable` | **GIỮ — nhà duy nhất (R4)**; **phải cấp Custom DocPerm cho AL BOM Manager + lối vào menu** | — | B4, FVB, app khác | — | Quản trị **sửa được VAT** (hiện chỉ System Manager) | Thu hồi DocPerm |
| `Formula Variable Binding` | **BỎ bản chép**; alumglass ghi qua API FB, field read-only + nhãn "tự sinh" | 1 hàm `sync_catalog_bindings()` | `_resolve_fb_context` | Patch `v28_9`/`v28_11` giữ để tương thích, **có ngày gỡ**; ⛔ patch chép mới | Binding không còn sửa tay | Binding do app khác tạo **không đụng** |
| `al_bom_engine/system_variable_resolver.py` (215 dòng) | **GIỮ** làm khuôn **bộ nạp generic** cho biến theo dòng (B3); chỉ bỏ phần trùng FB | API FB cho phần trùng | engine B1, autocomplete | Không có dữ liệu riêng | Thêm biến theo dòng **không cần DEV** (sau B3) | Revert tệp |
| `formula_validate.ALUMGLASS_CUSTOM_FUNCS` + `_engine_safe_funcs` | **GỘP còn 1 bảng callable**; danh sách hàm đọc từ FB `get_allowed_funcs()` (F8) | FB settings | engine, api, JS | 3 hàm nghiệp vụ vẫn là mã | Không đổi | — |
| `api::get_formula_context` đường legacy 10 khối | **GỘP** (F5) | FB `get_suggestions` + adapter alumglass | autocomplete | — | Danh sách gợi ý **gọn hơn**, không trùng | Giữ legacy sau cờ tới hết B4 |
| `AL Formula Field` | **GIỮ — nhà duy nhất "field nào là công thức"**; thêm `compute_order` | — | editor + engine | — | Không đổi | — |
| `AL Bom Set.formula_fieldnames` | **BỎ field** | `AL Formula Field` | `bom_orchestrator:1712` | Patch đọc giá trị, so với `AL Formula Field`; lệch ⇒ **throw nêu danh sách** | Ô JSON biến mất khỏi form | Bỏ khỏi JSON là revert được |
| `DEFAULT_FORMULA_FIELDS` + `PATTERN_FORMULAS` | **GIỮ làm lưới an toàn nhưng phải KÊU** | log + warning `dung_luoi_cu:<mã>` | engine | — | Có cảnh báo khi rơi lưới (trước đây im) | — |
| 5 ô chết trên `AL Bom Item` + `AL Color Standard.surcharge_rule` | **BỎ cả 6 (R5)** — **lý do: dọn dữ liệu**, ⛔ không phải giảm nhiễu form (5/6 đã ẩn) | — | 0 nơi đọc | Patch **đếm** bản ghi có giá trị ≠ rỗng rồi mới gỡ; ⛔ DROP cột | **Chỉ 1 ô** biến mất khỏi màn hình (`surcharge_rule`) | Cột còn; hoàn lại JSON |
| `Formula Set` (app FB) | **KHÔNG đụng** — chỉ bỏ **field trỏ** `AL Bom Item.formula_set` (R5) | — | 0 nơi đọc | — | Ô "Formula Set" trên dòng BOM biến mất (đang `hidden=1`) | Hoàn lại field trong JSON alumglass |
| `AL Product Type.nc_pct/nc_ld_rate/profit_margin` | **GIỮ — nhà của giá trị** | — | qua biến hệ | — | Không đổi | — |
| `AL Variable Library.default_value` cho biến **hệ** | **BỎ giá trị (R4)**, chỉ giữ con trỏ (hiện read-only) | — | resolver | Patch xoá `default_value` ở mọi biến `is_system=1` | Ô giá trị **thành read-only** ⇒ người dùng **không sửa VAT ở đây** nữa (phải sang FGV — xem quyền ở trên) | Backup |
| `AL Cost Bucket.source_config` (JSON) | **GIỮ** + thêm câu kiểm khi Lưu (khoá bắt buộc theo `source_type`) | validator | `bom_orchestrator:4303` | — | Lưu sai **bị chặn** kèm câu chỉ chỗ sửa | — |
| `AL Quantity Calc Method.calc_formula` | **GIỮ nhưng thành chuỗi SINH** từ `calc_expr` (Đ5); `calc_fn` = Nâng cao | `calc_expr` | người đọc | Patch sinh `calc_expr` từ `calc_fn` cho 14 seed + so kết quả | Ô hiển thị **không gõ tay được** ⇒ không còn lệch | Giữ `calc_formula` cũ |
| `AL Variable Profile` / `AL Formula Field` **quyền** | **SỬA QUYỀN** (đang ngược nhân vật: BOM Manager ghi, Technical Admin không) | Custom DocPerm: Technical Admin read/write; BOM Manager read | — | — | Quản trị **không sửa nhầm** regex/registry | Thu hồi DocPerm |

### 4.5 Điều gì sẽ **không** làm (theo R1 / R2 / R7)

- ⛔ **Không tùy biến theo khách** (R1).
- ⛔ **Không fork / không sửa `formula_builder`** (R2). Buộc sửa FB ⇒ **dừng, báo Owner**.
- ⛔ **Không dựng lại màn "cấu hình chung"** dưới tên khác.
- ⛔ **Không giữ ô chết "để dành"** (R5).
- ⛔ **Không có giai đoạn chuyển tiếp cho fallback 48** (R6): sửa dữ liệu trước, bật chặn sau.
- ⛔ **Không viết patch mới để chép biến sang bảng thứ hai.**
- ⛔ **Không gộp thêm DocType nào** (R7) — kể cả `AL Variable Profile` vào `AL Variable Library`
  (hạt khác, sẽ thành N×M dòng) hay `AL Quantity Calc Method` vào `AL Variable Library`.
- ⛔ **Không tạo DocType mới chứa bản sao dữ liệu** cho màn "Cấu hình sản phẩm" (Đ1).

---

## 5. Lộ trình (mỗi bước kiểm được)

**Cổng chung, áp cho MỌI bước:** BOM chuẩn CDMQ-2C phải ra `GIA_VAT = 22.717.289` (±1 đ) — mốc ghi
ở `KE_HOACH_TRIEN_KHAI_CHI_TIET.md:41,403`. Lệch ⇒ **dừng**. BOM 4 cánh (`47.430.808`) là mốc **chưa
đối chứng trong đợt này** — phải đo ở B0.

| Bước | Ngày | Làm gì | Kiểm chứng | Điều kiện dừng |
|---|---|---|---|---|
| **B0** | 1 | `bench execute` **chỉ đọc**: đếm `AL Variable Library`, `common_variables`, `row_literals`, FVB, rule, `AL Formula Field`; **đối chiếu 19/16/18 DocType**; kiểm FB đã cài + đếm `source_type` (19); **đếm cho R6**: (a) số `AL Rule` CONSTANT trùng tên biến hệ, (b) số biến hệ **không resolve được** trên các Bom Set thật, (c) số bản ghi có giá trị ở 6 ô chết; tính lại 2 BOM chuẩn | Bảng đếm khớp §2; 19 source type có mặt; **số (a)(b) = 0** là điều kiện bật R6; 2 mốc giá khớp | Lệch ⇒ **làm lại kiểm kê**; (a) hoặc (b) > 0 ⇒ **chưa bật R6** |
| **B1** ✅ 2026-11-27 | 1 | Engine đọc `AL Formula Field` thay `formula_fieldnames` + `DEFAULT_FORMULA_FIELDS`; danh sách riêng của bộ **không đổi số tiền** (được ưu tiên + cảnh báo `formula_fields_legacy_list:<bộ>`), registry thiếu field thì cảnh báo ⛔ tự thêm | Test thuần `standalone_tests/test_formula_field_registry.py` **14/14** (3 đối chứng âm); còn **2 mốc giá + đối chứng dương trên site** | Lệch trên site ⇒ dừng, in danh sách |
| **B2** 🟡 code xong 2026-11-27 | 2–3 | **R3:** 4 field vào Library (`is_input`, `group_label`, `sort_order`, `is_active`); patch `v1_0.merge_variable_settings_into_library` chép **dữ liệu thật** (không cứng 19) + `default_profile`→`is_default`, `preview_doctype`→profile; **một chỗ đọc** `variable_sources/catalog_rows.py` (chia 3 loại RỜI NHAU: common=`is_input`, row=`category=Row Literals`, user=phần còn lại); Settings **đã bị XOÁ HẲN** (patch `v1_0.drop_variable_settings_tables`: cổng chặn + sao lưu JSON + DROP 3 bảng) | Test thuần: patch **9/9**, catalog_rows **9/9**, drop **10/10**; **CHƯA đo trên site** — còn phải đối chiếu tập tên autocomplete trước/sau + 2 mốc giá | Trên site: mất biến ⇒ dừng, in danh sách thiếu |
| **B3a** 🟡 2026-11-27 | 2 | **Bộ nạp generic cho biến theo dòng** (`engine/row_literal_loader.py`): điền tên còn thiếu theo `source_doctype`+`source_field`, bơm vào context; giữ 17 literal lõi làm gốc (⛔ ghi đè) | Thêm 1 biến dòng khai Library (nguồn `AL Bom Item`/`AL Glass Master`/`AL Material Category`/`Item`/`Item Price`) ⇒ engine có giá trị, không sửa `.py`; test 6/6 | Bỏ 6 danh sách cứng ⇒ cần site đối chiếu số (chưa làm) |
| **B3b** ✅ 2026-11-27 | 1 | **Đ3:** patch hồ sơ (`variable_library_user` cho 3 hồ sơ seed; `row_literal` **hoãn** — xem §4.3 Đ3) + Custom DocPerm FGV. Code: `patches/v1_0/user_vars_in_default_profiles.py`; quyền khai 1 nguồn ở `setup/install_roles.py::CONSTANT_PERMISSIONS` | Biến mới tạo trong Library ⇒ **hiện ngay** trong ô công thức của `AL Bom Set`; BOM Manager sửa được `VAT_RATE`. Test: `alumglass/tests/test_user_vars_in_default_profiles.py` (10/10) | Còn phải thêm vào Variable Set ⇒ **chưa đạt Đ3 trọn vẹn** (đúng như dự kiến); phần còn lại ở B2/B3a/B3c |
| **B3c** ✅ 2026-11-27 | 2 | **Đ4:** ô **"Dùng ở"** nhãn Việt duy nhất; `is_input`/`category` tự suy (patch điền biến cũ); cảnh báo biến theo dòng dùng trần (`bien_chua_co_o_buoc` trong thông báo lỗi engine + cảnh báo khi lưu Bom Set) | Test 9/9; form không còn cờ kỹ thuật phải khai tay | `available_at` suy từ engine chưa làm — hiện dùng danh sách `ROW_RESOLVABLE_VARIABLES` |
| **B4** | 1–2 | **FB-first:** `sync_catalog_bindings` ghi FVB qua API FB (read-only); bỏ đường legacy 10 khối, 4 nhóm lấy từ `get_suggestions` | Sửa `VAT_RATE` 1 nơi ⇒ giá đổi sau TTL; tập tên autocomplete **không đổi**; 2 mốc giá khớp | FVB của app khác bị ảnh hưởng ⇒ dừng; buộc sửa FB ⇒ **báo Owner** |
| **B4b** | 0,5 | Bỏ **phần trùng** của `system_variable_resolver` (giữ resolver + `system_variables` làm lớp sau FB) | Tập biến hệ resolve trước/sau **bằng nhau**; 2 mốc giá khớp | Lệch 1 biến ⇒ dừng |
| **B5** | 1 | **R6:** bỏ fallback CONSTANT (`bom_orchestrator:1068-1077`); thiếu nguồn ⇒ cảnh báo + **chặn**. **Chỉ bật sau khi B0 trả (a)=(b)=0** | Dựng ca ALUMIL_M9560 thiếu binding ⇒ **chặn**, câu nêu **tên biến + nhãn + dòng**; ca đủ nguồn ⇒ 2 mốc khớp | (a)/(b) > 0 ⇒ **chưa bật** |
| **B6a** ✅ 2026-11-27 | 0,5 | **R5 — đếm:** patch `v1_0.count_dead_fields` đếm + **ghi log** dữ liệu cũ (⛔ chặn migrate — gỡ field không xoá cột); 5 field vốn `hidden=1` | Test 6/6 | Chạy trên site để xem số (không chặn) |
| **B6b** ✅ 2026-11-27 | 0,5 | **R5 — xoá:** gỡ 6 field khỏi JSON (5 `AL Bom Item` + `surcharge_rule`), bỏ `set_query` chết; ⛔ DROP cột | `git diff` chạm 2 JSON + 1 JS; test 6/6 | — |
| **B7** | 2 | **Đ5:** thêm `calc_expr`, `calc_formula` thành chuỗi sinh, `calc_fn` = Nâng cao; patch sinh `calc_expr` từ `calc_fn` cho 14 seed | Sửa `calc_expr` ⇒ kết quả đổi, `calc_formula` đổi theo; 14 pattern ra **cùng số** như trước; rơi về `PATTERN_FORMULAS` ⇒ **có cảnh báo** | Lệch số 1 pattern ⇒ dừng |
| **B8** | 2–3 | **Đ1:** Page "Cấu hình sản phẩm" (chỉ đọc + nút nhảy), trạng thái lỗi theo khối | 1 sản phẩm: mở **1 màn** thấy đủ 6 khối; tắt 1 nguồn (đổi quyền) ⇒ khối đó **báo lỗi**, không trống | Khối lỗi mà trang vẫn hiện bình thường ⇒ dừng |
| **B9** | 2 | **Đ2:** tạo từ mẫu bằng `AL BOM Version` snapshot | Tạo bộ mới từ CDMQ-2C ⇒ ra giá **đúng** sau khi đổi vài ô; bộ gốc **không đổi**; có ghi "tạo từ X lúc T" | Bộ gốc bị đổi ⇒ dừng |
| **B10** | 1,5 | Menu theo **việc** (không theo bảng), ẩn khái niệm kỹ thuật, sửa quyền Profile/Formula Field, tài liệu người dùng | Đi theo menu làm được 4 việc không cần gõ tên DocType; Sales **0 màn** cấu hình | Còn phải gõ tên bảng để tìm ⇒ chưa đạt |

**Tổng: ~20–24 ngày công · 12–13 lần deploy độc lập** (bản 1 ghi 13–16 ngày / 10 deploy; phần tăng
là B3a loader, B3b–c Đ3–Đ4, B7 Đ5, B8 Đ1, B9 Đ2, B10). Nếu cắt Đ1–Đ5 sang đợt sau: **~11–13 ngày ·
8 deploy**.

---

## 6. Rủi ro & cách làm nó KÊU

| Rủi ro | Mức | Nó sẽ hỏng thế nào | Cách phát hiện (làm nó KÊU) |
|---|---|---|---|
| **R6 làm đổi số tiền** | **Cao** | hệ chưa cấu hình đủ (vd ALUMIL thiếu binding) trước đây ra 48, nay **chặn tính** ⇒ không lưu được báo giá; tệ hơn: chặn không rõ ⇒ tưởng hệ hỏng | Cổng `GIA_VAT` ở mọi bước; **đếm (a)(b) ở B0**; ca thiếu nguồn dựng sẵn ở B5, câu nêu **tên biến + nhãn + dòng** |
| **R4/R6 biến 2 trường tuỳ chọn thành bắt buộc** (P11) | **Cao** | Bom Set thiếu `profile_system`/`product_type` trước đây vẫn ra giá, nay **không tính được** — người dùng thấy "hệ hỏng" | B0 đếm (b) theo **từng Bom Set**; nếu > 0 ⇒ in danh sách Bom Set + trường thiếu, **điền trước** rồi mới bật |
| **Quyền**: BOM Manager không sửa được VAT sau R4; Profile/Formula Field ngược nhân vật | **Cao** | người có trách nhiệm **không mở được** bảng cần sửa ⇒ sửa lách bằng System Manager ⇒ mất phân tách nhiệm vụ | Kiểm quyền ở B10 bằng 1 tài khoản mỗi nhân vật: mỗi vai liệt kê được **đúng** bảng mình cần sửa; thiếu ⇒ chặn đóng |
| **R3 — patch chuyển dữ liệu thiếu dòng** | Trung bình | 19 dòng chép thiếu ⇒ biến mất khỏi autocomplete, công thức cũ ra 0 | So **tập tên** trước/sau + số dòng = 19; cổng chặn trong patch drop (mọi tên phải có trong Library) + sao lưu JSON |
| Đổi thứ tự phân giải ⇒ lệch tiền | Trung bình | lệch vài trăm nghìn, không ai thấy | Cổng golden 2 mốc; so **từng dòng** cost template, không chỉ tổng |
| **B3 xoá danh sách mà thiếu loader** (P10) | **Cao** | biến mới hiện trong gợi ý nhưng engine **trả 0 im lặng** — hỏng nặng nhất | Phép thử B3a là **điều kiện nghiệm thu**: thêm biến dòng bằng UI ⇒ giá trị đúng; nếu 0 ⇒ dừng, **không** vá bằng tuple |
| **Đ1 hub "nói dối"** | Trung bình | một khối không đọc được nhưng trang vẫn hiện ⇒ người dùng sửa sai chỗ | Trạng thái lỗi theo khối + thời điểm đọc; ca test: thu quyền 1 bảng ⇒ khối đó **đỏ** |
| **Đ2 clone trôi** | Trung bình | bộ mới và bộ gốc lệch dần, không ai biết bộ nào là chuẩn | Ghi "tạo từ mẫu <mã> lúc <giờ>" + so khác biệt khi mở trang sản phẩm |
| Patch chép dữ liệu chạy nửa đường | Thấp | site dở dang giữa 2 mô hình | Patch idempotent + `dry_run` chỉ đọc (khuôn `migrate_rules_to_al_rule`) + backup là điều kiện tiên quyết |
| **Phụ thuộc `formula_builder`** | Trung bình | FB đổi chữ ký ⇒ tính giá lỗi hoặc **ra 0** im lặng | Ghim phiên bản FB; B0 ghi lại số `source_type` + tên hàm đang dùng; kiểm khởi động: thiếu `get_live_context`/`resolve_all_bindings_batch` ⇒ **cảnh báo to** trong Error Log |
| FB thiếu năng lực | Trung bình | dễ trượt sang "sửa FB cho nhanh" — trái R2 | Mọi chỗ cần sửa FB ⇒ **dừng, báo Owner** |
| Người dùng quen màn hình cũ | Cao | sửa nhầm chỗ, không thấy tác dụng | DocType đã xoá nên route cũ không mở được — câu chỉ dẫn nằm ở banner tài liệu + hướng dẫn A–Z |

---

## 7. Quyết định

**Đã chốt (R1–R7).** ⛔ Không hỏi lại.

| Quyết định | Việc cụ thể kéo theo | Bước |
|---|---|---|
| **R1** không theo khách | không bảng biến theo khách | — |
| **R2** chỉ sửa alumglass | adapter / `@register_source` / registry / Custom DocPerm / dữ liệu | mọi bước |
| **R3** gộp 2 bảng con, bỏ màn chung | 19 dòng sang Library; 2 field sang Profile; bỏ `SETTINGS_DOCTYPE` | B2 |
| **R4** FGV là nhà hằng số | xoá `default_value` biến hệ; **cấp quyền cho BOM Manager** | B3b + B4 |
| **R5** gỡ 6 ô chết | 2 pha ẩn → xoá; ⛔ DROP cột; ⛔ gọi là giảm nhiễu form | B6a → B6b |
| **R6** bỏ fallback 48 | chặn + cảnh báo; **chỉ sau khi B0 (a)=(b)=0** | B0 → B5 |
| **R7** tách vật lý ≠ nhiều màn | 0/10 gộp; giảm màn bằng Đ1–Đ5 | B3b–B10 |

**Phạm vi Owner đã duyệt (2026-11-27):** ✅ **LÀM CẢ Đ1–Đ5** — màn "Cấu hình sản phẩm",
tạo sản phẩm từ mẫu, hồ sơ hiện đủ + quyền, 4 field tự suy, `calc_expr`.
Tổng **~20–24 ngày, 12–13 deploy**; đích là đạt **C3 + C4**, không chỉ C2.

Thứ tự thi công (mỗi đợt có cổng riêng):

| Đợt | Bước | Việc | Cần site? | Trạng thái 27/11 |
|---|---|---|---|---|
| **1** | B1, B2, B3b, B3c | registry field công thức · gộp 2 bảng con (R3) · hồ sơ hiện đủ + quyền (Đ3) · 4 field tự suy (Đ4) | không (B0 đo song song) | B1 ✅ · B3b ✅ · B2 🟡 code xong (chờ đo) · **B3c chưa làm** |
| **2** | B3a, B4, B5, B6 | loader biến dòng · FB-first · bỏ fallback 48 (R6, sau B0) · gỡ 6 ô (R5) | B0 bắt buộc trước B5 | chưa làm |
| **3** | B7, B8, B9, B10 | `calc_expr` (Đ5) · màn Cấu hình sản phẩm (Đ1) · tạo từ mẫu (Đ2) · menu/quyền/tài liệu | golden trên site | chưa làm |

**B0 (đo, chỉ đọc) chưa chạy** — cần biết site test và người chạy `bench execute`. Đây là **việc chặn
duy nhất** của đợt 2 (R6/B5) và là điều kiện nghiệm thu B1/B2.

---

## 8. Tiêu chí "đơn giản" đo được (từ UX1 — dùng để đóng job)

| # | Tiêu chí | Cách đo | Đạt khi |
|---|---|---|---|
| **C1** | Sales **0 màn** cấu hình | đăng nhập vai `AL Sales User`, đếm màn cấu hình mở được | = 0 |
| **C2** | Đổi ngưỡng nẹp | số màn / số thao tác / số mã phải gõ | **≤1 màn, ≤5 thao tác, 0 mã** |
| **C3** | Thêm biến mới | số màn, và biến có **hiện ngay** trong ô công thức | **≤2 màn**; hiện ngay; **0 field mà người dùng không trả lời được** |
| **C4** | Sản phẩm mới | số màn + số lần xác nhận | **≤1 màn + ≤3 xác nhận** (Đ1 + Đ2) |
| **C5** | Không phơi mã kỹ thuật | quét màn người dùng: `GLOBAL/ROW/INPUT`, `CONSTANT`, `calc_fn`, `items.…`, `rule_code` | **0** mã thô; mọi lỗi có **nút hành động** |

**Cổng cứng chung:** `GIA_VAT = 22.717.289` ±1 đ với CDMQ-2C ở **mọi** bước deploy.

---

## 9. Truy vết linh động (L1–L11)

| # | Yêu cầu linh động gốc | Cơ chế đáp ứng | Bằng chứng kiểm được | **Nếu gộp thì mất gì** |
|---|---|---|---|---|
| L1 | Không hardcode danh sách biến (`tra-cuu §7.1`, `api/formula_registry.py`) | `AL Variable Library` + adapter registry 10 nguồn | `variable_sources/registry.py` decorator; `api/formula_registry.py` | Mất khả năng thêm **nguồn** mới (khác thêm biến) |
| L2 | Thêm biến **không sửa mã** | 1 bản ghi Library + Đ3 + B3a | 2026-11-27: **đã hiện trong gợi ý** (B3b + B2); **chưa đạt trọn**: biến mới vẫn phải gắn `AL Variable Set` mới có giá trị nhập — đo tiếp ở B3c/B3a | — |
| L3 | Thêm quy tắc/ngưỡng không sửa mã (`gop-rule`) | `AL Rule` + 2 bảng con + `input_variable` | `al_rule.py::preview/validate`; patch `infer_rule_input_variable` | Mất bảng ngưỡng/tra + cổng `result_type` + `AL Rule Version` |
| L4 | Chọn quy tắc theo **tên**, không gõ mã (`tra-cuu §3.3`) | picker + `preview_rule` | `api/__init__.py:695`, `al_rule.js:954`, `rule_helper.js:2140` | Không có chỗ đặt form chọn ⇒ buộc nhớ mã |
| L5 | Thử ngay tại chỗ | `AL Rule.preview` | đã có | Mất vòng "sửa → thấy kết quả" |
| L6 | "Thiếu nguồn" ≠ "không khớp" (§7.6, 5 trạng thái) | R6 + cờ `rule_source_missing` | 5 ca ở `tra-cuu` §7.6 | Người dùng đi sửa bảng quy tắc trong khi lỗi là chưa chọn dòng |
| L7 | Không fix cứng "dữ liệu tra" | `input_variable` + `input_scope` suy từ `category` | `al_formula_rules/rule_input.py` | — |
| L8 | Không đổi số tiền | cổng `GIA_VAT` | golden tests | — |
| L9 | Version/audit để tái lập giá | `AL BOM Version` snapshot + `AL Rule Version` | `al_bom_version.py::_take_snapshots` | Mất khả năng tái lập báo giá đã gửi |
| L10 | Mở rộng bằng dữ liệu | adapter + `AL Formula Field` | đã có | — |
| L11 | Biến chỉ hiện khi engine **có** giá trị | **suy tự động** (Đ4) | sẽ đo ở B3c (⚠ hiện là bảng thủ công) | Mất lớp chặn gợi ý sai; **phải thay bằng suy tự động**, không bằng khai tay |

### Ba chỗ **hy sinh** linh động và cách bù

| # | Hy sinh | Vì sao | Cách bù |
|---|---|---|---|
| 1 | **Biến theo dòng**: xoá danh sách mà chưa có bộ nạp | bản 1 chỉ nói xoá | **B3a** thêm bộ nạp generic bằng `source_link_field`; phép thử là điều kiện nghiệm thu |
| 2 | **`available_at` khai tay** = bảng sự thật thủ công về năng lực mã | bản 1 định thêm Select | **Đ4**: suy từ engine + engine **KÊU**; ⛔ không khai tay |
| 3 | **R4/R6 thêm yêu cầu** `profile_system`/`product_type` | bỏ mặc định mà không bù dữ liệu | **B0** đếm + điền dữ liệu về đúng nhà **trước**; câu cảnh báo nêu trường + nơi sửa |

---

## Xem thêm

- Quy tắc tự khai "tra theo dữ liệu gì": `docs/design/tra-cuu-quy-tac-de-hieu.md` §7 (đã chốt 2026-11-25)
- Gộp 2 DocType rule về `AL Rule`: `docs/design/gop-rule-mot-doctype.md`
- Hướng dẫn người dùng: `docs/usage/tinh-gia-bao-gia.vi.md` §10
- Seed tham chiếu: `alumglass/setup/seed_demo_data.py`, `alumglass/setup/install_roles.py`,
  `alumglass/patches/v28_14/seed_variable_catalog.py`, `alumglass/patches/v28_14/seed_bom_profile.py`
- Mã của B1/B3b/B2 (2026-11-27): `alumglass/engine/bom_orchestrator.py` (`_resolve_formula_fieldnames`),
  `alumglass/api/formula_registry.py`, `alumglass/variable_sources/catalog_rows.py`,
  `alumglass/patches/v1_0/user_vars_in_default_profiles.py`,
  `alumglass/patches/v1_0/merge_variable_settings_into_library.py`,
  `alumglass/setup/install_roles.py` (`CONSTANT_PERMISSIONS`)
- Cập nhật mã ngoài app: `docs/ops/cap-nhat-ma-va-cache.md` (mục 2026-11-27 — bắt buộc `bench migrate`)
