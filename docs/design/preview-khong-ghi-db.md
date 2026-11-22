# Preview tính giá KHÔNG ghi DB — thiết kế

> **Tài liệu người dùng (đọc trước khi sửa câu chữ UI):**
> `docs/usage/tinh-gia-bao-gia.vi.md` — tệp chuẩn duy nhất cho luồng tính giá.
> Mọi nhãn nút / câu thông báo ở đây phải khớp tệp đó.
>
> **Trạng thái:** Phase 1 ĐÃ TRIỂN KHAI (2026-11-21) — Owner duyệt 5 quyết định ở §9.1.
> **Người viết:** SA1 · **Ngày:** 2026-11-21 · **Người triển khai:** DEV1
> **Phạm vi:** app `alumglass`, nhánh `main`, đường giá của **Quotation Item**
> **Mục tiêu:** *Preview* (kể cả auto-preview 700 ms sau mỗi lần sửa tham số)
> **không ghi một byte nào** xuống DB. DB chỉ đổi khi người dùng bấm **Lưu** báo giá.
> **Nguyên tắc:** thứ người dùng nhìn thấy ⛔ không được phụ thuộc một tiến trình
> nền, và ⛔ không có hai chỗ cùng giữ một con số.

---

## 0. Cách đọc tài liệu này

Line number trong `quotation.js` **đang trôi** — lúc tôi đo, tệp vừa được sửa
14:32 (tăng từ 3 688 lên 3 834 dòng trong ~15 phút). Vì vậy:

- Tài liệu dẫn bằng **tên hàm + hành vi**; số dòng chỉ là gợi ý "đo tại thời điểm".
- `api/__init__.py` và `engine/bom_orchestrator.py` chưa trôi trong lúc đo → số
  dòng đúng tại 14:2x.

Ba mục đánh dấu rõ: **✅[Đo]** = đọc mã và đối chiếu được; **🔶[Suy luận]** =
suy ra từ mã nhưng chưa chạy; **⛔[Chưa đo]** = cần site/DB mới chốt được
(liệt kê ở §10).

---

## 1. Hiện trạng (đo trên working tree, 2026-11-21)

### 1.1 Đường đi hiện tại

```
ItemParamDialog (auto-preview 700 ms)
  _run_preview()  ──▶ _save()  (chỉ sửa dòng TRÊN FORM)
        │
        └─▶ _sync_row_to_db()  ──▶ frappe.client.set_value  (GHI DB #1)
              │                    dòng cũ: set_value → load + save CẢ Quotation
              │                    dòng mới: frm.save() cả báo giá
              └─▶ _exec_calculate_bom()
                    └─▶ alumglass.api.calculate_bom(quotation_item_name)
                          ├─ permission read trên Quotation
                          ├─ assert_quotation_item_editable
                          ├─ frappe.get_doc("Quotation Item", name)
                          └─ BomOrchestrator(name).run()
                               B0..B6  (đọc DB theo BOM/version, KHÔNG theo tên dòng)
                               B7      (GHI DB #2: 4 field dòng + tổng tiền cha + commit)
                    └─▶ alumglass.api.get_result_display(name)   (đọc DB #3)
```

- ✅[Đo] `alumglass/api/__init__.py:16` `calculate_bom(quotation_item_name)`;
  cổng quyền `:40`; `assert_quotation_item_editable` `:46`;
  `frappe.get_doc` `:48`; sync `:56`; enqueue `:60`.
- ✅[Đo] `engine/bom_orchestrator.py:375` `run()` = B0→B6 → `b7_save_results()` → `_build_response()`.
- ✅[Đo] `engine/bom_orchestrator.py:389-392` `b0_version_pinning` là **chỗ duy nhất**
  nạp dòng từ DB: `self._qi_doc = frappe.get_doc("Quotation Item", ...)`.
- ✅[Đo] `engine/bom_orchestrator.py:446-458` B1 đọc `al_bom_vars` **từ `_qi_doc`**
  (đã nạp ở B0), không đọc lại DB.
- ✅[Đo] `engine/bom_orchestrator.py:3545-3596` `b7_save_results`:
  `assert_quotation_item_editable` (`:3572`) → `frappe.db.set_value(Quotation Item,
  {al_gia_vat, al_gia_ban, al_bom_result, rate})` (`:3582`) →
  `_recalculate_quotation_totals` (`:3593`, ghi tổng cha `:3680`) →
  `frappe.db.commit()` (`:3596`).
- ✅[Đo] Client: `_sync_row_to_db` (≈`quotation.js:789`), `_persist_row` (≈`:737`),
  `_run_preview` (≈`:2725`), `_exec_calculate_bom` (≈`:2810` gọi `calculate_bom`),
  `_write_result_to_row` (≈`:2564`), `_schedule_auto_preview` (`:2054`, debounce 700 ms).
- ✅[Đo] **4 chỗ** buộc `_sync_row_to_db` trước khi hỏi server:
  preview chính (≈`:2773`), preview từ form con của dòng (≈`:3401`),
  mở BOMDialog (≈`:3507`), nút tính nhiều dòng (≈`:3631`).
- ✅[Đo] Bình luận trong mã nói thẳng lý do: *"server đọc `al_bom_vars` từ DB,
  nên PHẢI đồng bộ xuống DB trước"* (≈`quotation.js:2768-2771`).

### 1.2 Hệ quả của hiện trạng (đã xảy ra thật, không phải giả thuyết)

| Việc người dùng làm | Ghi DB xảy ra | Ai biết |
|---|---|---|
| Gõ số W, chờ 700 ms | `frappe.client.set_value` với child table = **nạp cha + `doc.save()` cả Quotation** (`frappe/client.py:186-195`) → chạy **toàn bộ** `validate` + `calculate_taxes_and_totals` của ERPNext, bump `modified`; rồi B7 ghi 4 field + tổng | Không ai — `modified` nhảy, dễ `TimestampMismatchError` lần Save sau (đã có fix ở ≈`:745-762`) |
| Mở dialog dòng mới, gõ 1 số | `frm.save()` **cả báo giá** | Người dùng tưởng mới chỉ xem trước |
| Xem trước 10 lần | 10 lượt save + 10 commit | Audit không có; chỉ giữ kết quả cuối |
| 2 người cùng mở 1 dòng | 2 luồng ghi đè nhau | Không ai — không có khoá |

### 1.3 Đọc DB **theo tên dòng** ở đâu (ngoài B0)

| Chỗ | Đọc gì | Ghi chú |
|---|---|---|
| `engine/bom_orchestrator.py:37-66` `assert_quotation_item_editable` | `parent`, `docstatus` | Chốt nghiệp vụ, phải giữ |
| `api/__init__.py:84-104` `_require_quotation_item_permission` | `parent` + `has_permission` | Cổng quyền duy nhất |
| `engine:813-843` `_resolve_fb_context` | **chỉ khi không có Bom Set**: scope `("Quotation Item", tên dòng)` → `get_live_context` nạp doc từ DB | Xem §2.1 |
| `engine:1736-1746` `_doc_currency` | `self._qi_doc.parent` → `Quotation.currency` | Suy được từ `params.parent` |
| `api:1943-1988` `get_result_display` | `frappe.get_doc("Quotation Item")`, `qi.al_bom_vars`, `_get_cost_template_display(qi)` | Đã có `result_json` (WIP) nhưng **vẫn** nạp `qi` |
| `api:2169-2195` `explain_bom_line` | `al_bom_result` trong DB | Nút "Vì sao ra số này?" |
| `api:1113-1139` `_prepare_glass_price_context` | `BomOrchestrator(name)` → B0 đọc DB | Giá kính cạnh ô chọn trong dialog |
| `api:1237-1248`, `:1274-1486` `get_glass_master_price`, `get_variable_set_for_bom` | `al_bom_vars` trong DB | Trạng thái kính/màu của báo giá |
| `engine:3608-3609`, `:3624` `_recalculate_quotation_totals` | `parent`, dòng trong cha | Chỉ thuộc đường ghi |

Không có chỗ nào **khác** trong engine đọc `Quotation Item` — ✅[Đo] bằng
`grep -n '"Quotation Item"' engine/bom_orchestrator.py` (chỉ ra các dòng trên).

### 1.4 Những gì đã có sẵn — ⛔ không phải làm lại

- ✅[Đo] Response đã có `gia_vat`/`gia_ban` (`engine:3691-3714`, WIP) — client
  đã dùng đúng (`_write_result_to_row` ≈`:2564`).
- ✅[Đo] `get_result_display(name, result_json=None)` (WIP) dựng display từ chuỗi
  client gửi ⇒ mở lại dialog không cần DB cho phần **kết quả**.
- ✅[Đo] `_write_result_to_row` ghi ĐỦ bộ 3 object (`locals` + dòng `frm.doc.items`
  + `child_doc`) — "Lưu báo giá" sau đó không ghi đè kết quả cũ.
- ✅[Đo] Nút chính của dialog (nay là **Áp dụng vào dòng**, trước là 💾 Lưu) **không**
  ghi DB (WIP) — chỉ còn đường preview ghi.
- ✅[Đo] Cache engine theo **nội dung công thức**, ⛔ không theo tên dòng
  (`engine/engine_cache.py:83-93`, dùng ở `bom_orchestrator.py:3050-3062` (B4) và
  `:3423/:3471` (B6)). Preview nhiều lần không phải biên dịch lại DAG.
- ✅[Đo] ConfigSnapshot **chỉ** tạo lúc submit (`hooks.py:64-66`,
  `api/quotation_events.py:21-61`) — không phải lo preview sinh snapshot.

---

## 2. Trả lời 8 câu hỏi thiết kế

### Q1 — Dòng ĐÃ LƯU: engine tính được mà không đọc `al_bom/…/al_bom_vars` từ DB?

**Được.** Chỉ `b0_version_pinning` (`engine:390`) nạp dòng. Mọi bước sau đọc
`self._qi_doc.<field>` (tổng cộng **6** chỗ dùng `_qi_doc`: `:391-392`, `:458`,
`:1743`, `:1935`, `:3373`) — tức chỉ **đọc field**, ⛔ không dùng `name` để tra DB.
Nếu API dựng `_qi_doc` từ `frappe.get_doc` + phủ `params` (hoặc `frappe._dict`),
B1→B6 chạy y hệt.

Phải chạm **5 điểm**:

| # | Điểm | Việc |
|---|---|---|
| 1 | `__init__` | nhận `params`, `persist` |
| 2 | `b0_version_pinning` | `al_bom/al_bom_version` lấy từ `params` (fallback doc) |
| 3 | `b1_gather_inputs` | `al_bom_vars` **đã** đọc từ `_qi_doc` ⇒ chỉ cần `_qi_doc` mang giá trị params |
| 4 | `_doc_currency` | `parent` lấy từ params (hoặc currency truyền thẳng) |
| 5 | `_resolve_fb_context` | scope: chỉ fallback `("Quotation Item", tên)` khi **không** có Bom Set — xem dưới |

**Chỗ không phủ được (và cách xử lý):**

- `_resolve_fb_context` (`engine:842-843`): khi BOM **không có** Bom Set, scope
  là `("Quotation Item", <tên>)`. `get_live_context` (formula_builder/api/formula_builder.py:431-437)
  nạp doc theo tên và `_assert_read_perm` trước đó. Với params:
  - dòng mới (`new-…`): FVB tự bỏ qua doc (`startswith("new-")`) ⇒ chỉ còn
    binding global/không phụ thuộc doc.
  - dòng cũ: doc nạp từ DB **có thể cũ** so với params. Nhưng ✅[Đo] seed FVB
    (`patches/v28_9/seed_fvb_from_variable_library.py:15-26`) **cố ý không** tạo
    binding scope `Quotation Item` (Quotation Item không link tới
    Profile System/Product Type), nên binding áp vào scope này chỉ là global
    constant — không đọc field của doc. **Kết luận: an toàn, nhưng phải có test
    khoá lại** (nếu ai thêm binding scope `Quotation Item` sau này, preview sẽ
    đọc số cũ **im lặng**). ⛔[Chưa đo] binding thật trên site (xem §10).
  - Đề xuất phòng thủ: khi `persist=False`, nếu có Bom Set thì scope như cũ; nếu
    **không** có Bom Set thì truyền `current_docname = ""` (bỏ hẳn doc) thay vì
    tên dòng — đổi hành vi 0 với dữ liệu seed hiện tại, và khoá luôn cái bẫy trên.

**Ước lượng:** 5 điểm sửa trong engine; **0 chỗ không phủ được** ở phần tính.

### Q2 — Dòng MỚI (`new-…`): cái gì thật sự cần một dòng đã lưu?

| Thứ cần "dòng đã lưu" | Có thật sự cần? | Thay bằng |
|---|---|---|
| Cổng quyền (`has_permission` trên Quotation cha) | **Cần**, nhưng chỉ cần **tên cha** | Client gửi `parent`; cha `new-…` ⇒ kiểm `create` trên `Quotation` (docstatus = 0) |
| `assert_quotation_item_editable` | **Cần** docstatus cha | `assert_parent_editable(parent)`; `new-…` ⇒ docstatus 0 ⇒ cho qua |
| `Quotation Item.name` làm **khoá cache** | **Không** | Cache theo nội dung công thức (đã đo §1.4) |
| `name` làm **khoá snapshot** | **Không** | Snapshot chỉ ở submit (`quotation_events.py:52`) |
| `realtime job_id` | **Không** cần dòng, nhưng cần **kênh về đúng người** | `publish_realtime(user=frappe.session.user)`, token do server sinh, client giữ trong bộ nhớ |
| Audit | **Không ai đọc hôm nay** | (câu hỏi Owner #4) |

**Kết luận:** tính trên `frappe._dict` được; **gãy ở 3 chỗ**, cả 3 đều là
"đọc thêm" chứ không phải "tính":
(a) `get_result_display` cần `qi` cho `_get_cost_template_display` + `al_bom_vars`;
(b) `explain_bom_line` đọc `al_bom_result` DB;
(c) `get_glass_master_price`/`get_variable_set_for_bom` đọc `al_bom_vars` DB.
Cả 3 sửa bằng "nhận params" (xem §5).

### Q3 — Đường async (job nền)

Hiện tại job nhận **tên dòng**, rồi `_run_bom_calculation_job` (`api:237-299`)
ghi `Running` → `BomOrchestrator(qi_name)` → ghi `Success`/`Failed` + publish
`user=user` (`:278-299`).

Nếu preview không ghi DB, job **phải** nhận params trong payload. Rủi ro:

| Rủi ro | Mức | Cách chốt |
|---|---|---|
| Client gửi giá trị tuỳ ý | Thấp — params chỉ là **định danh** (al_bom, version, các mã override) + **số đầu vào** (W/H/qty…) ảnh hưởng **đúng kết quả của chính họ** | ⛔ Không nhận giá/đơn giá từ client. Kiểm `read` trên `AL BOM`/`AL BOM Version` (và các doctype override nếu có) — role `AL Sales User` đã có `read` module `AL Bom Engine` (`setup/install_roles.py:43-51`) |
| Params đổi giữa lúc xếp hàng và lúc chạy | Có thật | Params **chụp một lần** ở lúc enqueue (payload bất biến). Kết quả mang `params_hash`; client **bỏ** kết quả nếu hash ≠ trạng thái hiện tại (đã có `_preview_seq`, nay thêm hash) |
| Dữ liệu gốc (bảng giá, version) đổi giữa chừng | Có — **hôm nay cũng có** | Không xử lý (ngang hiện trạng). Ghi `computed_at` để support đối chiếu |
| Mất kết nối / đóng tab khi job đang chạy | Có | Không ghi DB ⇒ không có "kẹt Queued". Kết quả mất, người dùng preview lại. (câu hỏi Owner #1) |
| Người khác đoán `job_id` để nghe lén | Không | Publish theo `user=…`; token thêm hash ngẫu nhiên |

### Q4 — Không ghi DB thì mất gì?

| Thứ | Mất gì | Có chấp nhận? |
|---|---|---|
| Audit mỗi lần tính | **Hôm nay không có** (chỉ giữ kết quả cuối trong `al_bom_result`). Mất: "kết quả cuối" không còn sống qua reload khi chưa Lưu | Chấp nhận — đổi lại là ⛔ không còn ghi ngầm |
| `al_calc_status` sau reload | Hiện chỉ đường async ghi. Nay: đọc được trạng thái **cũ**, dễ hiểu lầm. Kết quả preview nằm ở client | Bắt buộc UI phải nói **"kết quả chưa lưu"** (xem §5.3) |
| Cảnh báo/`errors` của engine | Trả trong response (không mất lúc xem). Không lưu ⇒ reload là mất, cho tới khi Lưu | Chấp nhận; Lưu thì nằm trong `al_bom_result.errors` |
| `ConfigSnapshot` | ✅[Đo] chỉ tạo ở `on_submit` (`hooks.py:65`). Submit = `frm.save('Submit')` ⇒ doc client (có kết quả) được lưu rồi mới submit ⇒ snapshot đúng | Không mất — **nhưng phải test** (§8) |
| In báo giá trước khi Lưu | Print format **chỉ đọc** `al_bom_result`/`al_gia_ban`/`al_gia_vat` trong DB (`templates/print_formats/bao_gia.html:47,142-152`) | ⚠ **Mất mới**: in khi form đang "dirty" sẽ in **giá cũ**; Frappe chỉ toast chung chung (`frappe/public/js/frappe/form/form.js:1224-1232`). Phải thêm cảnh báo riêng về giá + đường sửa (§5.3) |
| `explain_bom_line` ("Vì sao ra số này?") | Đọc DB ⇒ giải thích bản **cũ** | Sửa nhận `result_json` (phase 2) |
| SO/report đọc giá từ Quotation đã lưu | Vẫn giá **đã lưu** | Đúng nghĩa "chưa lưu" — nhưng phải nói cho người dùng biết |

### Q5 — Tổng tiền báo giá

- ✅[Đo] **Client KHÔNG tự tính lại tổng khi `rate` đổi**: `erpnext.TransactionController`
  không có handler `rate(doc, cdt, cdn)` (danh sách handler ở
  `erpnext/public/js/controllers/transaction.js:361-2306`; chỉ có `price_list_rate`,
  `margin_*`, `qty`…). `frappe.model.set_value("rate")` không kéo theo tính tổng.
- ✅[Đo] **Server tính lại khi Save**: `Quotation.validate` → `AccountsController.validate`
  → `self.calculate_taxes_and_totals()` (`erpnext/controllers/accounts_controller.py:229-231`).
  `set_missing_item_details` chỉ ghi đè field `None`/`force_item_fields`, mà `rate`
  **không** nằm trong `force_item_fields` (`:82-88`, `:795-799`) ⇒ rate client gửi
  được giữ nguyên. *(Đo trên v14 cục bộ — đích v16 phải xác nhận lại, xem §10.)*
- ⇒ Hôm nay: `b7` ghi tổng xuống DB, nhưng **form đang mở vẫn hiện tổng cũ**
  (không refresh). Nếu bỏ `b7`, tổng trên màn hình sẽ cũ cho tới khi Save.
- **Chỗ cần chạm:** sau khi ghi `rate` vào dòng (trong `_write_result_to_row`,
  nhánh `gia_ban > 0`), gọi **một lần** `this.frm.cscript.calculate_taxes_and_totals()`
  (`frm.cscript` là controller instance — `frappe/public/js/frappe/form/script_manager.js:84`),
  debounce theo lô khi tính nhiều dòng. Đây là **cải thiện** so với hiện trạng.

### Q6 — Phương án: xem §3, khuyến nghị §4, điểm sửa §5.

### Q7 — Rủi ro: xem §7.

### Q8 — Kế hoạch test: xem §8.

---

## 3. Phương án

### A. `preview_bom(params)` + engine `persist=False` *(khuyến nghị, có bổ sung)*

API mới, engine dựng doc từ params, chạy B0→B6, **bỏ B7**, trả
`{…kết quả, display, calc_meta}`. Client ghi kết quả vào dòng trên form; DB chỉ
đổi khi Lưu.

- **Được:** đúng yêu cầu; bỏ 4 chỗ `_sync_row_to_db` + 1 `frm.save()` ngầm;
  `modified` của cha không bị đẩy lên mỗi lần gõ; 2 người preview không đụng nhau;
  bỏ `commit()` trong request đọc.
- **Mất:** kết quả không sống qua reload; in khi dirty in giá cũ; phải tự tính
  tổng phía client; phải làm `explain`/`get_result_display` nhận params.
- **Điểm phải giữ chặt:** cổng quyền, chốt docstatus, golden 2C/4C.

### B. Vẫn ghi DB, nhưng ghi vào "nháp" riêng (bảng tạm / `__islocal` row)

- **Được:** hiện trạng gần như không đổi; kết quả sống qua reload.
- **Không nên:**
  1. **Vẫn là ghi DB** — mỗi lần gõ phím vẫn đẻ 1 bản ghi; yêu cầu là **không ghi**.
  2. **Đẻ bảng trạng thái thứ hai** phải có người nuôi (dọn nháp, hết hạn, phân
     quyền, backup…) — người nuôi chết thì bảng **nói dối mà ⛔ không ai biết**
     (luật 4).
  3. **Hai bản của cùng một thứ** (nháp + dòng thật) ⇒ chúng sẽ trôi khỏi nhau
     (luật 1). Ai đọc kết quả? Print? Report? Mỗi chỗ phải quyết đọc bản nào.
  4. Vẫn cần transaction/commit và vẫn bump `modified` nếu không dùng
     `update_modified=False` — tức giữ nguyên phần lớn cái đang đau.
- ⇒ Chỉ hợp lý nếu Owner **cần** kết quả sống qua reload. Đó là câu hỏi #2 cho Owner.

### C. A + "kết quả tự khai nguồn gốc", server kiểm khi Lưu *(khuyến nghị)*

Là A, cộng 2 thứ nhỏ:

1. **`calc_meta`** ghi vào chính `al_bom_result`:
   `{params_hash, computed_at, computed_by, engine}` — `params_hash` =
   SHA-256 của JSON chuẩn hoá `{al_bom, al_bom_version, item_code, al_bom_vars}`
   (sort keys; số chuẩn hoá; **không** gồm `qty`/`rate` vì engine không dùng).
2. **`Quotation.validate` (doc event của app, ⛔ không sửa controller ERPNext)
   kiểm `params_hash`** khi lưu: kết quả đang lưu phải khớp tham số đang lưu.
   Lệch ⇒ **DỪNG + nói rõ** (hoặc tự tính lại — câu hỏi Owner #3). Bản ghi cũ
   (không có `calc_meta`) ⇒ bỏ qua kiểm — tương thích ngược 100%.

Vì sao cần: sau khi bỏ B7, **toàn bộ** giá trị trong DB đến từ client. Hôm nay
client cũng ghi đè được (field là `read_only` chỉ ở UI), nhưng ít ra b7 đã từng
ghi bản máy chủ tính. C kiểm được đúng một câu quan trọng: *"con số đang lưu có
được tính từ đúng tham số đang lưu không?"* — và trả lời được **mà không cần
tính lại** (rẻ).

**Chống giả `calc_meta`:** ký HMAC `params_hash` bằng khoá site
(`frappe.utils.password.get_encryption_key`) ⇒ client không tự chế được. Không
bắt buộc ở phase 1, nhưng nên làm ngay khi bật kiểm ở phase 2.

> **Vì sao ⛔ không chọn "tính lại toàn bộ khi Save":** báo giá 20 dòng = 20 lượt
> B1→B6, mỗi lượt có truy vấn DB + dựng engine — Save sẽ treo. Chỉ tính lại
> **dòng lệch hash**.

---

## 4. Khuyến nghị

**Chọn C** (A + `calc_meta` + kiểm khi Lưu), chia 3 phase ship độc lập:

- **Phase 1** (giá trị lớn nhất, ship được một mình): `preview_bom` **không ghi
  DB** cho cả dòng cũ và dòng mới, cả **sync lẫn async** (BOM lớn) — nếu chỉ làm
  sync thì dòng BOM lớn vẫn ghi ngầm, đúng cái ta đang xoá; client bỏ
  `_sync_row_to_db` khỏi đường preview; ghi kết quả vào dòng; client tự tính
  tổng; UI nói "chưa lưu". Kèm `calc_meta` (chỉ **ghi**, chưa **kiểm**) để
  phase 2 có dữ liệu.
- **Phase 2**: các **bề mặt đọc** hết phụ thuộc DB (`get_result_display`,
  `explain_bom_line`, `get_glass_master_price`, `get_variable_set_for_bom` nhận
  params); `Quotation.validate` kiểm `params_hash`; hoàn thiện luồng
  **Lưu-rồi-in** (phase 1 mới có cảnh báo).
- **Phase 3**: dọn đường cũ — `calculate_bom` giữ làm alias "tính + lưu" cho
  script/bench (`alumglass/run_test.py` dùng), hoặc bỏ hẳn sau khi hết caller.

Lý do xếp phase này: phase 1 chạm **một đường** (sync, ≤ ngưỡng) và gỡ được
đúng cái đau lớn nhất (mỗi 700 ms một lượt save cả Quotation). Phase 2 chạm
nhiều bề mặt đọc (mỗi bề mặt là một chỗ có thể nói dối), nên cần phase 1 chạy
ổn trước để có mốc so.

---

## 5. Điểm sửa theo phase

### 5.1 Hợp đồng API mới (chốt trước khi code)

```
preview_bom(quotation_item_name=None, params=None, signature=None)  # whitelist
  params = {
    "parent": "<tên Quotation hoặc 'new-…'>",
    "al_bom": "...", "al_bom_version": "...",
    "al_bom_vars": "<chuỗi JSON>",
    "item_code": "...", "item_name": "...",
    "currency": "VND",              # tuỳ chọn; thiếu thì đọc từ parent
  }
  trả về:
  {
    "preview": True,
    "result": {buckets, cost_template, lines, gia_vat, gia_ban, errors},
    "display": {…như get_result_display…},   # để client khỏi gọi vòng 2
    "calc_meta": {params_hash, computed_at, engine},
    "signature": "<echo>",                    # client đối chiếu
    "async": True, "job_id": "...",           # nhánh BOM lớn
  }
```

Quy tắc:
- ⛔ Không nhận giá trị tiền từ client (chỉ định danh + số đầu vào).
- Quyền: dòng có tên ⇒ `read` trên Quotation cha; dòng mới ⇒ cha thật ⇒ `read`,
  cha `new-` ⇒ `create` trên Quotation; mã `al_bom`/`al_bom_version` (và mã
  override `_accessory_set/_profile_system/_cost_template`) ⇒ `read` trên
  doctype tương ứng.
- `assert_parent_editable(parent)` — cha đã submit/huỷ ⇒ chặn.

### 5.2 Phase 1 — bảng điểm sửa

| # | Tệp | Hàm / điểm | Việc |
|---|---|---|---|
| 1 | `alumglass/api/__init__.py` | `preview_bom` **(mới)** | endpoint: quyền → dựng params → sync/async → trả `result/display/calc_meta` |
| 2 | 〃 | `_require_quotation_item_permission` | thêm biến thể nhận `parent` (dòng mới) + `create` khi cha `new-` |
| 3 | 〃 | `_assert_preview_target` **(mới)** | `assert_parent_editable` + kiểm `read` AL BOM/Version/override |
| 4 | 〃 | `_estimate_bom_line_count` | nhận `params` (đếm từ `al_bom_version` trong params) |
| 5 | 〃 | `_enqueue_bom_calculation` → `_enqueue_preview` | payload mang params; **⛔ không** `db.set_value(al_calc_*)` |
| 6 | 〃 | `_run_bom_calculation_job` → `_run_preview_job` | `set_user(user)`; chạy `persist=False`; publish `user=…` có `params_hash`; **⛔ không** ghi status |
| 7 | 〃 | `get_result_display` | nhận `params` (bom_code/version/vars) thay vì buộc nạp `qi` |
| 8 | 〃 | `_get_cost_template_display(qi)` | nhận `bom_code/bom_version` tường minh |
| 9 | `alumglass/engine/bom_orchestrator.py` | `__init__` | `params=None, persist=True`; `_qi_doc` có thể là `frappe._dict` |
| 10 | 〃 | `b0_version_pinning` | dựng doc từ params khi `persist=False`; giữ nguyên nhánh đọc DB khi `persist=True` |
| 11 | 〃 | `run` | `if self.persist: self.b7_save_results()` |
| 12 | 〃 | `_resolve_fb_context` | không có Bom Set ⇒ `current_docname=""` khi `persist=False` (khoá bẫy FVB) |
| 13 | 〃 | `_doc_currency` | parent/currency từ params |
| 14 | 〃 | `_build_response` | thêm `calc_meta` (hash + thời điểm + phiên bản app) |
| 15 | 〃 | `assert_quotation_item_editable` | tách lõi `assert_parent_editable(parent, docstatus)` để dùng cho dòng mới |
| 16 | `alumglass/alumglass/doctype/overrides/quotation.js` | `_run_preview` | **bỏ** `_sync_row_to_db`; dựng `params` từ dialog (`_collect_row_values` + `al_bom_vars`) |
| 17 | 〃 | `_exec_calculate_bom` | gọi `preview_bom`; ghi `result/display/calc_meta` |
| 18 | 〃 | `_render_display_model` | ưu tiên `display` trả kèm; chỉ gọi `get_result_display` khi mở lại dialog (đã có `result_json`) |
| 19 | 〃 | `_write_result_to_row` | ghi `al_bom_result` + `al_gia_ban/vat` + `rate`; **⛔ không** ghi `al_calc_status` của preview (tránh lưu "Success" giả khi user Lưu trước khi job xong) |
| 20 | 〃 | **(mới)** `_refresh_totals` | gọi `frm.cscript.calculate_taxes_and_totals()` một lần/lô sau khi ghi `rate` (§Q5) |
| 21 | 〃 | `_notify_params_applied` | câu cố định "Đã tính giá … **chưa lưu** vào báo giá. Bấm Lưu để lưu." — bỏ nhánh `wrote_db` |
| 22 | 〃 | 3 chỗ còn lại của `_sync_row_to_db` (form con ≈`:3401`, BOMDialog ≈`:3507`, nút tính nhiều dòng ≈`:3631`) | chuyển sang `preview_bom` với params |
| 23 | 〃 | `_persist_row` / `_sync_row_to_db` | còn 0 caller ⇒ xoá (hoặc giữ + comment `deprecated`) |
| 24 | `alumglass/tests/js/test_quotation_glass_pick.js` | ca `(5f)`, `(5e)` và nhóm nút 💾 Lưu | đảo kỳ vọng "phải ghi DB trước" → "**không** ghi DB"; thêm ca params |
| 25 | `alumglass/tests/test_preview_bom.py` **(mới)** | pytest/Frappe test | xem §8 |
| 26 | `docs/usage/bom-calculation-dialog.vi.md`, `docs/usage/quotation-pricing.vi.md` | | bỏ mọi câu "phải ghi DB trước khi tính" |

**Ước lượng phase 1: 26 điểm — 3 tệp mã (`api/__init__.py` 8, `bom_orchestrator.py` 7,
`quotation.js` 8, trong đó 3 điểm mới) + 2 điểm test + 2 tệp docs.**
Trong đó **9 điểm là "thêm nhánh"** (giữ đường cũ chạy được), **8 điểm là "đổi
đường"** (client), phần còn lại là test/docs.

### 5.3 Phase 1 — bắt buộc có cùng lúc (⛔ không tách)

Ba thứ sau **phải ship cùng** phase 1, nếu không sẽ tạo đúng lỗi im lặng mà ta
đang muốn xoá:

1. **Trạng thái "chưa lưu"** trên dòng/dialog (badge + câu toast). Nếu không,
   người dùng thấy giá mới, tưởng đã lưu, gửi khách bản cũ.
2. **Tự tính tổng phía client** sau khi ghi `rate`.
3. **Cảnh báo khi In trên form đang dirty**: `frm.print_doc` chỉ toast chung
   (`form.js:1224`). Thêm nhánh cho Quotation: nếu có dòng mang kết quả BOM
   chưa lưu ⇒ hộp thoại *"Bản in sẽ lấy giá đã lưu, không phải giá đang hiện.
   Lưu báo giá rồi in?"* kèm nút **Lưu rồi in**.

### 5.4 Phase 2

| # | Điểm | Việc |
|---|---|---|
| 27 | `alumglass/api/__init__.py:2169` `explain_bom_line` | nhận `result_json` (như `get_result_display` đã làm) |
| 28 | `alumglass/api/__init__.py:1113/1237` `_prepare_glass_price_context`, `get_glass_master_price` | nhận params khi dialog còn mở |
| 29 | `alumglass/api/__init__.py:1274` `get_variable_set_for_bom` | nhận `al_bom_vars` từ client cho dòng mới/chưa lưu |
| 30 | `alumglass/hooks.py` + hàm mới | `doc_events["Quotation"]["validate"]` kiểm `params_hash` |
| 31 | `alumglass/engine/calc_meta.py` **(mới)** | một bản duy nhất cho: chuẩn hoá params, hash, ký/kiểm HMAC |
| 32 | `quotation.js` | khoá/hỏi trước khi Print/Email khi có kết quả chưa lưu |

### 5.5 Phase 3

| # | Điểm | Việc |
|---|---|---|
| 33 | `calculate_bom` | đổi thành alias `preview_bom` + `persist=True`, đánh dấu deprecated; sau khi `run_test.py` chuyển ⇒ xoá |
| 34 | `b7_save_results` | chỉ còn dùng cho alias/bench; hoặc bỏ hẳn nếu không ai gọi |
| 35 | `al_calc_status/job_id/error` | quyết định giữ (tương thích dữ liệu cũ) hay bỏ khỏi form |

---

## 6. Điểm ⛔ không được phép vỡ (kèm phép đo)

| # | Bất biến | Phép đo (chạy được) |
|---|---|---|
| 1 | **Cổng `read` trên Quotation** vẫn là chốt quyền duy nhất | user không có `read` gọi `preview_bom` ⇒ `PermissionError`; test bằng user `AL Site Engineer` trên báo giá của người khác |
| 2 | **Không tính giá lên báo giá đã submit/huỷ** | tạo Quotation `docstatus=1` ⇒ `preview_bom` ném đúng câu; `docstatus=2` tương tự |
| 3 | **Giá đúng — 2C/4C** | `alumglass/tests/test_bom_orchestrator.py:54` (2C = 22 717 289) phải xanh. ⚠ **4C không có số vàng nào được kiểm** (`:112` chỉ `> 0`; con số 47 430 808 chỉ nằm trong bình luận `patches/v28_9/seed_fvb_from_variable_library.py:37`) ⇒ **phải đo và khoá số 4C trước khi sửa**, rồi so `persist=True` vs `persist=False` trên **cùng một dict** |
| 4 | **Submit tạo ConfigSnapshot** | submit 1 báo giá đã Lưu ⇒ có `ConfigSnapshot`, `result_json` khớp `al_bom_result` |
| 5 | **Lưu không ghi đè kết quả vừa tính** | preview → Lưu ⇒ DB `al_bom_result` = JSON vừa preview (so `params_hash`) |
| 6 | **`modified` của cha không nhảy khi preview** | ghi `modified` trước/sau 5 lần preview ⇒ **bằng nhau** |
| 7 | **Không rò dữ liệu qua params** | user gửi `al_bom` không có quyền đọc ⇒ bị chặn, ⛔ không trả cost template |
| 8 | **Mở lại dialog thấy đúng số trên dòng** (không phải số DB) | preview → đóng → mở lại (chưa Lưu) ⇒ summary khớp |

---

## 7. Rủi ro

| Loại | Rủi ro | Mức | Xử lý |
|---|---|---|---|
| Bảo mật | Params cho phép chỉ định `al_bom_version`/mã override bất kỳ ⇒ xem giá thành ngoài phạm vi dòng mình | Trung bình (hôm nay đã có một phần: ai có `read` báo giá bất kỳ gọi `calculate_bom` là thấy cost của dòng đó) | Kiểm `read` trên AL BOM/AL BOM Version/doctype override khi mã **khác** giá trị đã lưu; test #7 |
| Bảo mật | Đọc-only user hôm nay **buộc được** ghi DB qua `calculate_bom` (b7 không kiểm quyền) | **Đang có** | Preview `persist=False` **xoá luôn** lỗ này |
| Toàn vẹn | DB sau Lưu 100% do client gửi (field `read_only` chỉ chặn ở UI) | Cao hơn hiện trạng một chút (b7 từng ghi bản máy chủ) | Phase 2: `params_hash` + HMAC ở `validate` |
| Hiệu năng | Preview lặp 700 ms/lần = 1 lượt B1→B6 | Ngang hiện trạng; **tốt hơn** vì bỏ 1 lần `set_value` (load + save cả cha) + `commit` | Cache engine đã theo nội dung (đo §1.4). Đo thêm nếu cần |
| Đa người dùng | 2 người preview cùng dòng | **Không còn va chạm** (không ghi) | Chỉ còn va chạm ở Lưu — Frappe `modified` chặn |
| Mất kết nối | Sync: không ghi gì ⇒ sạch. Async: kết quả mất nếu đóng tab | Trung bình | Báo rõ "kết quả chạy nền chỉ hiện trong phiên này" (Owner #1) |
| Vận hành | Kết quả không còn sống qua reload ⇒ support không thấy số người dùng đang thấy | Trung bình | `calc_meta.computed_at/computed_by` chỉ có khi Lưu; hướng dẫn support đọc `al_bom_result` = bản đã lưu |
| Vỡ ngầm ⚠ | Mở dialog → sửa tham số → **Lưu báo giá** ngay (không preview): lưu tham số mới với kết quả **cũ**, và `params_hash` cũ ⇒ đây đúng là ca phase 2 phải chặn/tự tính | Cao | Phase 2 `validate` kiểm hash; trước đó: dialog 💾 Lưu **buộc** một lượt preview nếu có thay đổi (`_needs_glass_recalc` đã làm một phần) |

---

## 8. Kế hoạch test (phải có trước khi ship phase 1)

### 8.1 Python (`alumglass/tests/test_preview_bom.py`, mới)

1. **Golden y hệt 2 đường:** cùng row/params, `BomOrchestrator(..., persist=False)`
   và `persist=True` ⇒ `buckets/cost_template/lines/gia_vat/gia_ban` **bằng nhau từng key**.
   *Bước 0 bắt buộc:* đo và ghi lại GIA_VAT **2C** (kỳ vọng 22 717 289) và **4C**
   trên site dev **trước khi sửa** — 4C hiện ⛔ không có số vàng nào được kiểm.
2. **Preview không ghi một byte nào:** chụp `modified`, `al_bom_result`,
   `al_gia_ban`, `al_gia_vat`, `rate` của dòng + `modified` + tổng của Quotation
   trước; gọi `preview_bom` 3 lần với params khác nhau; so lại ⇒ **không đổi**;
   `tabVersion`/`tabComment` không tăng.
3. **Dòng mới:** `quotation_item_name=None` + `parent=new-quotation-1` ⇒ có kết
   quả, ⛔ không dòng nào được tạo; cha chưa submit ⇒ được phép.
4. **Dòng mới, cha thật nhưng chưa lưu dòng:** `parent=SAL-QTN-xxxx` ⇒ không tạo
   dòng; quyền `read` trên cha được kiểm.
5. **Cha đã submit:** `preview_bom` ném `ValidationError` với câu đúng; không
   đọc/tính (chốt sớm).
6. **Không có quyền:** user không `read` Quotation ⇒ `PermissionError`;
   user `read` Quotation nhưng không `read` AL BOM ⇒ bị chặn khi gửi mã lạ.
7. **`params_hash`:** đổi 1 số trong `al_bom_vars` ⇒ hash đổi; thứ tự key đổi,
   số `2400` vs `"2400"` ⇒ hash **không** đổi (chuẩn hoá đúng).
8. **Async preview:** trên ngưỡng ⇒ trả `job_id`; `_run_preview_job` publish đúng
   user, mang `params_hash`; **không** ghi `al_calc_status/job_id`; lỗi ⇒ publish
   `Failed` + câu người đọc được.
9. **Legacy:** dòng cũ không có `calc_meta` ⇒ `validate` **không** chặn.

### 8.2 JS (`alumglass/tests/js/test_quotation_glass_pick.js` — cập nhật)

10. `_run_preview` **không** gọi `_sync_row_to_db` (đảo ca `(5f)`); vẫn chụp
    signature, vẫn bỏ kết quả cũ khi `seq` lệch.
11. Đổi kính → params gửi lên có `glass_master_map` mới; kết quả ghi vào **cả 3
    object** (đã có ca, giữ nguyên).
12. **Kết quả cũ về sau kết quả mới** ⇒ bị bỏ (hash + signature + seq).
13. Tính nhiều dòng ⇒ mỗi dòng 1 lần `preview_bom`, không lần nào `set_value`.
14. Sau khi có `rate` mới, `calculate_taxes_and_totals` được gọi **đúng 1 lần/lô**.

### 8.3 Ca tay (bắt buộc, trước khi báo xong)

15. **Preview xong, KHÔNG bấm Lưu, đóng form ⇒ DB không đổi một byte nào.**
    Đo: `SELECT modified, al_bom_result, al_gia_ban, rate FROM tabQuotationItem WHERE name=…`
    trước/sau; cả `tabQuotation.modified`, `tabQuotation.grand_total`,
    `tabVersion` đếm theo `ref_doctype='Quotation'`.
16. **Lưu báo giá ⇒ DB đúng như kết quả đã preview:** `al_bom_result` =
    JSON đã preview, `al_gia_ban` = summary, `rate` = `al_gia_ban`, tổng cha =
    tổng trên màn hình; `params_hash` khớp tham số đang lưu.
17. **In trước khi Lưu** ⇒ có cảnh báo, và "Lưu rồi in" cho bản in đúng giá mới.
18. **Hai trình duyệt** cùng preview 1 dòng ⇒ không ai thấy `TimestampMismatchError`;
    người Lưu sau thắng (hành vi Frappe chuẩn).
19. **Submit không qua Lưu** (preview → submit) ⇒ `ConfigSnapshot` mang đúng kết
    quả; mở lại báo giá sau submit thấy đúng.
20. **Golden hồi quy:** chạy lại `alumglass/tests/test_bom_orchestrator.py` +
    `run_test.py` (2C/4C) trên site dev — phải cùng số như trước khi sửa.

---

## 9. Câu hỏi cần Owner chốt

### 9.1 Quyết định của Owner (chốt 2026-11-21)

| # | Câu hỏi (§9) | Owner chốt | Hệ quả đã triển khai |
|---|---|---|---|
| 1 | BOM lớn có được ghi 2 field trạng thái để mở lại còn thấy? | **KHÔNG ghi gì**, kể cả `al_calc_status`/job id. Đóng tab giữa chừng ⇒ mất kết quả, mở lại bấm tính lại. | `_enqueue_preview` ⛔ không `set_value`, ⛔ không `commit`. Job preview publish realtime **chỉ cho user đã enqueue**. Trạng thái Queued/Success chỉ nằm trong bộ nhớ client của phiên đang mở. |
| 2 | Có cần kết quả preview sống qua reload/đăng nhập lại? | **KHÔNG** ⇒ giữ phương án A (không bảng nháp). | Không có bảng trạng thái thứ hai. UI phải nói rõ "chưa lưu". |
| 3 | Lưu khi tham số lệch dấu vân tay preview (hoặc chưa từng preview)? | **Tự tính lại dòng lệch rồi mới ghi** (không chặn người dùng). | Phase 2: `Quotation.validate` kiểm `params_hash` + tính lại dòng lệch. Phase 1 chỉ **ghi** `calc_meta` để có dữ liệu. |
| 4 | Có lưu vết MỖI lần preview (ai/lúc nào/tham số) không? | **KHÔNG** — trái mục tiêu, không tạo bảng audit. | Không ghi Version/Comment/Log cho preview. `computed_at` chỉ tồn tại trong response và (khi Lưu) trong `al_bom_result`. |
| 5 | In/gửi email khi đang có kết quả chưa lưu? | **Bắt buộc Lưu trước** bằng nút "Lưu rồi in". | Phase 1 mới có dòng nhắc "chưa lưu"; nút "Lưu rồi in" thuộc phase 2 (§5.3 điểm 3). |

### 9.2 Ghi chú triển khai phase 1 (DEV1, 2026-11-21)

Điểm khác design / chỗ cần biết:

1. **`params_hash` không HMAC.** Design §3 nói ký HMAC là "không bắt buộc ở
   phase 1"; task cũng yêu cầu ⛔ không tự nghĩ cơ chế bảo mật mới. Vì vậy phase
   1 dùng **SHA-256 thường** (`compute_params_hash` trong
   `engine/bom_orchestrator.py`) để **so khớp**, ⛔ không phải lớp chống giả mạo.
   Phase 2 phải thêm HMAC (`get_encryption_key`) trước khi dùng hash để CHẶN.
2. **`params_hash` phân biệt `2400` và `"2400"`** (khác design §8.7). Lý do:
   engine nhận đúng kiểu client gửi; hai kiểu có thể cho kết quả khác nhau, nên
   báo "cùng tham số" sẽ là nói dối. Chuẩn hoá hiện tại chỉ `sort_keys` +
   chuẩn hoá khoảng trắng JSON (yêu cầu của task).
3. **`calc_meta` có thêm khoá `engine`** (`"alumglass.bom_orchestrator"`) theo
   design §5.2 điểm 14; hình dạng chốt:
   `{params_hash, computed_at, preview, engine}`.
4. **Quyền trên `AL BOM`/`AL BOM Version` chỉ kiểm mã CLIENT GỬI.** Mã đọc từ
   DB của dòng đã lưu không kiểm lại — nếu kiểm, các vai trò đang dùng
   `calculate_bom` hôm nay (chỉ cần `read` Quotation) sẽ bị chặn oan.
5. **Dòng mới, cha `new-…` ⇒ kiểm `create` trên Quotation** (design §5.1). Cha
   đã lưu ⇒ kiểm `read` + docstatus = 0.
6. **`_resolve_fb_context`**: preview + KHÔNG có Bom Set ⇒ `current_docname=""`
   (design §2.1) để không đọc field cũ của doc trong DB.
7. **`get_result_display` / `explain_bom_line` / `get_variable_set_for_bom` vẫn
   đọc DB** (phase 2). Client nên dòng mới render từ kết quả trong tay và ⛔
   gắn nút "Vì sao ra số này?" (API giải thích chưa nhận params).
   → **Đã đóng ở phase 1.5 (2026-11-21)**: xem §9.5.
8. **Goldens 2C/4C chưa ĐO được trên máy này** — không có site nào cài
   `alumglass` (site `alumglass-dev` tạo 2026-08-16 nhưng DB user chưa cấp, app
   chưa install). Phase 1 khoá được tính chất "preview và calculate_bom ra
   **cùng số** trên cùng fixture" (12 ca standalone), ⛔ chưa khoá số tuyệt đối.
   Số **tham khảo có sẵn trong repo** (⛔ chưa phải số đo lại): 2C =
   **22 717 289** (`tests/test_bom_orchestrator.py:54`);
   4C = **47 430 808** (`run_test.py:151` + `docs/review_alumglass.md:629`) —
   nhưng `test_bom_orchestrator.py` cho 4C **chỉ kiểm `> 0`**, nên 4C hiện
   ⛔ được bảo vệ bởi test tự động. Cách đo trên site: xem §9.3.

### 9.3 Cách đo golden 2C/4C trên site (chưa chạy được ở máy dev)

```bash
# 1) Đo CẢ HAI đường trên cùng fixture (in ra GIA_VAT 2C + 4C):
bench --site <site> execute alumglass.run_test.test_cdmq_2c   # kỳ vọng 22 717 289
bench --site <site> execute alumglass.run_test.test_cdmq_4c   # ← số vàng 4C CHƯA có, ghi lại số này

# 2) Đối chứng preview vs calculate_bom (persist=False vs True):
bench --site <site> console
>>> from alumglass.engine.bom_orchestrator import BomOrchestrator
>>> qi = "<tên dòng vừa tạo ở bước 1>"
>>> import frappe
>>> p = {f: frappe.db.get_value("Quotation Item", qi, f) for f in
...      ("al_bom","al_bom_version","al_bom_vars","item_code","item_name","qty","uom")}
>>> prev = BomOrchestrator(qi, params=p, persist=False).run()
>>> live = BomOrchestrator(qi).run()
>>> [(k, prev[k] == live[k]) for k in ("buckets","cost_template","lines","gia_vat","gia_ban")]
```

Sau khi có số 4C, **khoá vào `alumglass/tests/test_bom_orchestrator.py`**
(class CDMQ4C đang chỉ kiểm `> 0`) — đó là việc của người chạy được site.

### 9.5 Phase 1.5 — 3 API ĐỌC nhận trạng thái DIALOG (DEV1, 2026-11-21)

Phase 1 bỏ ghi DB ⇒ 3 bề mặt đọc còn đọc bản CŨ/rỗng. Phase 1.5 đóng đúng 3 lỗ
này, **mọi tham số mới đều tuỳ chọn** (⛔ truyền ⇒ hành vi y như trước).

| # | API | Tham số mới | Hành vi khi CÓ tham số |
|---|---|---|---|
| 1 | `get_variable_set_for_bom(bom_code, quotation_item_name=None, params=None)` | `params` (whitelist `_parse_preview_params`) | `saved`/`glass_master`/`effective_*`/giá lấy từ `params.al_bom_vars`; ⛔ đọc DB. Dòng mới ⇒ kiểm `read` trên `parent`. |
| 2 | `get_glass_master_price(quotation_item_name, glass_code, params=None)` | `params` | `_prepare_glass_price_context(..., params=…)` dựng `BomOrchestrator(..., persist=False)` ⇒ giá theo biến đang sửa. |
| 3 | `explain_bom_line(quotation_item_name, slug, result_json=None, parent=None)` | `result_json` (như `get_result_display`), `parent` | Giải thích từ kết quả client gửi. Dòng MỚI (không tên/`new-…`) giải thích được nếu có `result_json` + `parent` (kiểm `read`/`create` trên cha). |

Ràng buộc đã giữ:

- **Bảng giá/tiền tệ vẫn đọc từ Quotation CHA trong DB.** Với dòng ĐÃ LƯU,
  `BomOrchestrator._build_preview_doc` lấy `parent` từ doc DB (params không
  ghi đè được); `_doc_currency` cố ý không đọc params. Params lén
  `currency`/`price_list`/`customer` bị `_parse_preview_params` bỏ.
- **Params không phải đường vòng quyền.** Mã `al_bom`/`al_bom_version` client
  gửi trong params bị kiểm `read` như `preview_bom` (mục c) ở cả 2 API đọc.
  Dòng ĐÃ LƯU luôn kiểm quyền trên cha THẬT của dòng, ⛔ không tin `parent`.
- **JSON hỏng ⇒ câu người-đọc-được** (`ValidationError` = 417). `result_json`
  hỏng dùng chung `_parse_result_json_arg`; `params` hỏng dùng chung
  `_parse_preview_params`.
- Hình dạng response không đổi; ⛔ không ghi DB (test khẳng định
  `set_value_calls == []`).

Phía client (`quotation.js`):

- `glass_pick.build_variable_set_args(bom, row, params)` — gắn `args.params`
  (JSON chuỗi). `_load_variable_set` truyền `_dialog_state_params()`.
- `glass_pick.make_price_requester({..., params})` — `params` là object HOẶC
  hàm; hàm để mỗi lượt hỏi giá lấy trạng thái MỚI NHẤT (requester sống suốt
  dialog). `_glass_price_requester_instance` truyền
  `() => this._dialog_state_params()`.
- `_collect_vars()` tách khỏi `_save()` (thuần đọc) để đường hỏi giá gửi đúng
  biến đang sửa mà ⛔ ghi dòng/DB.
- `explain_bom_line_args(opts)` (hàm thuần) + `register_explain_payload`:
  renderer đăng ký `result_json` đang hiển thị vào kho tạm (khoá `ex-N`, giữ
  100 lượt gần nhất) rồi gắn `data-explain-key` lên nút — ⛔ nhét JSON vào
  attribute. Nhờ vậy **dòng MỚI cũng có nút "Vì sao ra số này?"** khi có kết
  quả trong tay.

Test: `standalone_tests/test_preview_reads_dialog_state.py` (14 ca) +
`alumglass/tests/js/test_quotation_preview_state.js` (17 ca). Đối chứng âm đã
chạy: bỏ nhánh `params`/`result_json` ở từng mục ⇒ ca tương ứng đỏ (mục 1: 3 ca
Python / 2 ca JS; mục 2: 2 / 2; mục 3: 3 / 3).


## 9.6 UX1 gate — CHẶN đóng job phase 1 (2026-11-21): 3 điểm 🔴 + 6 điểm 🟡

UX1 chặn đóng job vì phase 1 làm preview **không ghi DB** nhưng UI vẫn nói
theo kiểu "đã tính xong/đã lưu". Nguyên tắc đã áp: **xanh lá = đã ghi DB thật**
(xanh dương = mới chỉ ở bộ nhớ trình duyệt), **mọi kết quả preview phải nói rõ
"chưa lưu" + việc cần làm**.

### 🔴 Bắt buộc (đã sửa)

| # | Lỗi | Cách xử lý | Test |
|---|---|---|---|
| 🔴1 | Nút 🖥️ (BOMDialog) chỉ hiện giá, không nói gì, ⛔ ghi dòng nào ⇒ người dùng tưởng dòng đã có giá mới. | BOMDialog nhận thêm `frm`; đầu cửa sổ có dòng nhắc *"Kết quả chỉ để xem — chưa ghi vào báo giá."*; 2 nút **Áp dụng vào dòng** (`_apply_to_form_row` → `_apply_result_to_row` + `_refresh_totals` + `frm.dirty()`, rồi đóng) và **Đóng**. Áp dụng xong toast **xanh dương** 7 giây *"Đã áp dụng kết quả vào dòng này — chưa lưu vào báo giá…"*. ⛔ ghi DB. | 13a, 13b |
| 🔴2 | Banner *"Giá vừa tính chưa được lưu"* **không tắt** sau khi Lưu báo giá (dấu bám `WeakSet` theo object, `frappe.model.sync` sửa tại chỗ ⇒ object giữ identity). | `after_save` gọi `_clear_preview_marks(frm)` (đổi `_previewed_rows` = WeakSet mới + xoá `__al_preview_json` từng dòng). **So sánh NỘI DUNG**: `_is_preview_unsaved` chỉ trả true khi `row.al_bom_result` **còn bằng** đúng chuỗi đã ghi ở lượt preview ⇒ dòng bị thay/nạp lại thì dấu hết nghĩa. Dấu `__al_preview_json` là property **⛔ enumerable** nên ⛔ lọt vào payload Lưu. | 13c (+ đối chứng âm cả 2 vế) |
| 🔴3 | Toast *"Đã tính x/y dòng"* / *"Tính giá xong"* màu **xanh lá** trong khi chưa ghi gì ⇒ hiểu là đã lưu. | 3 điểm dùng `_show_preview_toast` / `indicator: "blue"` (đỏ khi `failed`), thêm vế *"chưa lưu vào báo giá"*; toast hàng loạt thêm *"Bấm Lưu để ghi lại."* | 13d |

### 🟡 Sửa luôn (đã sửa)

| # | Lỗi | Cách xử lý | Test |
|---|---|---|---|
| 🟡5 | Banner thiếu hậu quả. | Câu mới: *"Giá vừa tính chưa được lưu vào báo giá. Bấm nút Lưu ở thanh trên để ghi lại — đóng trang hoặc tải lại là mất kết quả này."* | 12d |
| 🟡6 | "Tính giá"/"Preview giá toàn bộ" lọc `!is_new` rồi báo *"Chưa có dòng sản phẩm nào."* trong khi lưới có dòng. | "Tính giá" nhận **cả dòng mới** (`preview_bom` nhận `params` + `parent`); thiếu BOM ⇒ *"Dòng {n} (…) : chưa chọn BOM"*. "Preview giá toàn bộ" (đường ĐỌC DB) ⛔ dựng chi tiết dòng mới ⇒ câu *"{n} dòng chưa lưu trên báo giá nên chưa tính — mở 📐 Tham số BOM để tính."* | 13e |
| 🟡7 | *"kết quả sẽ tự hiện khi xong"* hứa sai khi listener đã bị gỡ. | Câu mới: *"BOM đang xếp hàng tính trong nền. Kết quả chỉ nhận được khi cửa sổ này còn mở — nếu không thấy, bấm 'Preview tính giá' để tính lại."* (BOMDialog: *"…đóng cửa sổ rồi bấm lại 🖥️ Preview tính giá."*) | — (chuỗi UI) |
| 🟡4 | "Preview giá toàn bộ" trộn 2 nguồn số (bảng tổng đọc `rate` trên form, chi tiết đọc DB). | Dòng có dấu preview chưa lưu ⇒ truyền `result_json: row.al_bom_result` cho `get_result_display`; đầu cửa sổ nhắc *"Giá đang hiện chưa lưu vào báo giá."* | — (chuỗi UI) |
| 🟡8 | Nhãn **💾 Lưu** trong dialog trùng chữ "Lưu" với nút lưu báo giá, nghĩa ngược. | Đổi nhãn nút chính thành **Áp dụng vào dòng** (hành vi + toast giữ nguyên). **Thay đổi nhãn do UX1 đề xuất — cần Owner xác nhận.** | 13f |
| 🟡9 | In khi còn kết quả chưa lưu. | **Đã nâng lên phase 2 — xem §9.7:** hộp thoại **"Lưu rồi in"** / **"Huỷ"** (⛔ lối in bản cũ), thay cho cảnh báo cam *"Bản in lấy giá đã lưu…"* của bản 🟡9. | 14a–14f |

### Phát sinh khi sửa 🟡6 (ghi lại để ⛔ tái diễn)

Dòng **chưa lưu** giờ đi được vào nhánh job nền của "Tính giá" hàng loạt, mà
server publish `qi_name = ""` cho dòng chưa có tên trong DB. Handler realtime
cũ dò dòng theo `qi_name` ⇒ **kết quả rơi vào hư không**. Nay `pending_jobs[job_id]`
giữ **chính object dòng** và dùng nó làm đích. Test 13h khoá hành vi này.

### Đối chứng âm (đã chạy — bỏ sửa ⇒ ca tương ứng đỏ)

| Bỏ gì | Ca đỏ |
|---|---|
| Dòng nhắc *"chưa ghi vào báo giá"* của BOMDialog | 13a |
| Lời gọi `_apply_result_to_row` trong `_apply_to_form_row` | 13b |
| `_clear_preview_marks` trong `after_save` | 13c |
| So sánh nội dung trong `_is_preview_unsaved` | 13c |
| 3 toast về `indicator: "green"` + bỏ vế "chưa lưu" | 13d (và 4s) |
| `pending_jobs[job_id] = row` (về lại `true` + dò `qi_name`) | 13h |

Bộ test sau khi sửa: `test_quotation_glass_pick.js` **122 ca** (trước 114; sau
phase 2 §9.7 là **128**), `test_quotation_preview_state.js` **17**,
`test_quotation_display.js` **12**; Python giữ **12 / 14 / 7 / 48** xanh,
`test_phase_b_fbmax.py` đúng **8 ca đỏ sẵn có**.

## 9.7 Phase 2 — "Lưu rồi in" (Owner chốt "bắt Lưu trước") + vá rò timer

### Hành vi

In báo giá khi còn dòng mang kết quả preview **chưa lưu** ⇒ **hộp thoại chặn
mềm** thay cho cảnh báo-rồi-in của 🟡9:

| Thành phần | Nội dung |
|---|---|
| Tiêu đề | báo giá **đã lưu**: *"Báo giá có giá vừa tính chưa lưu"* · báo giá **chưa từng lưu** (`frm.is_new()`): *"Báo giá chưa được lưu"* |
| Nội dung | *"Bạn vừa tính lại giá nhưng chưa lưu báo giá. Lưu báo giá rồi in để bản in chắc chắn khớp số trên màn hình."* |
| Nút chính | **Lưu rồi in** |
| Nút phụ | **Huỷ** |

⛔ **Không** có lối "vẫn in bản cũ". Lý do ⛔ phải "in ra là bản cũ": đường in có
thể lấy **chính document từ trình duyệt** (`frappe/www/printview.py` nhận
`form_dict.doc` khi có) hoặc đọc bản đã lưu — nên chỉ nói được "⛔ chắc khớp",
⛔ khẳng định bản in là bản cũ.

- **Lưu rồi in:** gọi `frm.save(...)`; **chỉ khi lưu THẬT SỰ xong** mới phát lại
  **đúng lệnh in người dùng vừa bấm** (tham số chụp trong closure).
- **Huỷ:** ⛔ lưu, ⛔ in.
- **Lưu thất bại** (validate / `r.exc` / `on_error`): ⛔ in + câu người-đọc-được
  *"Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu lại. Nếu
  chỉ cần in bản đã lưu thì tải lại trang (kết quả vừa tính sẽ mất)."*
  (⛔ traceback, ⛔ thêm nút thứ 3 vào hộp thoại).
  ⚠️ Với báo giá **chưa từng lưu**, câu này ⛔ dùng được — đã tách 2 nhánh, xem
  §9.8 🟡4.
- Báo giá **không còn** dấu preview chưa lưu ⇒ in ngay, ⛔ hộp thoại.
- ⛔ Không chặn ở tầng server (server không biết client còn kết quả chưa lưu).

### Chỗ dễ sai đã xử lý

1. **`frm.save()` của Frappe NUỐT lỗi trong promise** (`save()` bắt `.catch` rồi
   chỉ `console.error`; `validate_form_action` ném cũng đi đường này). Vì vậy
   KHÔNG dựa vào `promise.then` để biết lưu xong: dùng
   `frm.save(undefined, callback, undefined, on_error)`; promise chỉ là
   **backstop** cho trường hợp tài liệu không bẩn (Frappe không gọi callback) —
   và backstop **chỉ coi là xong khi `is_dirty()` hết true**. Một cờ `settled`
   bảo đảm `finish()` chạy đúng MỘT lần ⇒ ⛔ in 2 lần.
2. **Chống đệ quy / đua:** `__al_print_bypass` (lượt in do hộp thoại phát lại),
   `__al_print_dialog_open` (⛔ mở 2 hộp), `__al_print_busy` (đang lưu ⇒ ⛔ nhận
   lượt in mới). Gọi in lần 2/3 trong lúc hộp mở / đang lưu đều bị bỏ qua.
3. **Đóng hộp bằng X/Esc/click nền** ⛔ đi qua `secondary_action` ⇒ phải có
   `onhide` nhả `__al_print_dialog_open`, nếu không mọi lần in sau **chết im
   lặng cả phiên**.
4. **Frappe ⛔ có sự kiện client `before_print`** ⇒ vẫn phải bọc `frm.print_doc`
   (`_attach_print_guard`, gắn 1 lần trong `refresh`).

### ⚠️ Giả định chưa đo trên v16

Design cũ giả định "bản in luôn đọc DB" — **chưa đo trên Frappe/ERPNext v16 của
dự án**. Đọc mã v14 chỉ thấy `printview.py` ưu tiên `form_dict.doc` (document
từ trình duyệt) rồi mới `frappe.get_doc(...)`; luồng thực tế (Print menu, in
hàng loạt, PDF, email) có thể khác. **Việc cần làm trên site:** in một báo giá
vừa sửa giá mà **chưa Lưu** bằng 3 đường (menu Print, in từ List, tải PDF) và
ghi lại bản in mang số nào; nếu máy chủ luôn dùng `form_dict.doc` thì câu chữ
"bản in chắc chắn khớp" vẫn đúng, và có thể siết tiếp (bỏ hẳn hộp thoại?).
Chưa đo ⇒ ⛔ được khẳng định trong tài liệu người dùng rằng bản in là bản cũ.

### Vá rò timer (lỗi thật, không phải test)

`after_save` đặt `setTimeout(() => _attach_row_actions(frm), 600)`. Form đã
đóng/chưa render/ form giả trong test **không có `fields_dict`** ⇒
`frm.fields_dict["items"]` ném TypeError **bên trong timer**. Hệ quả: bộ test in
"ALL TESTS PASSED" nhưng tiến trình **exit 1** và stderr có traceback — tín hiệu
hỏng hoàn toàn bị che. Nay `_attach_row_actions` và `_schedule_row_actions_retry`
chặn `!frm || !frm.fields_dict || !frm.fields_dict["items"]` trước khi đọc.

### Test

| Ca | Nội dung |
|---|---|
| 13i | `_attach_row_actions` với `frm` thiếu `fields_dict`/null ⇒ ⛔ ném |
| 14a | in khi có preview chưa lưu ⇒ hộp thoại đúng tiêu đề/nội dung/2 nhãn, ⛔ in, ⛔ cảnh báo-rồi-in |
| 14b | "Lưu rồi in" ⇒ `save` 1 lần, **sau khi** lưu xong mới in 1 lần, đúng tham số in ban đầu |
| 14c | "Huỷ" ⇒ ⛔ lưu, ⛔ in |
| 14d | không còn preview chưa lưu ⇒ in ngay, ⛔ hộp thoại (kể cả sau khi Lưu xoá dấu) |
| 14e | lưu lỗi (cả `on_error` lẫn `r.exc`) ⇒ ⛔ in + câu người-đọc-được |
| 14f | in 2 lần trong lúc hộp mở / đang lưu ⇒ ⛔ 2 hộp, ⛔ 2 lần lưu, in đúng 1 lần |

Đối chứng âm: bỏ hộp thoại (in thẳng) ⇒ **14a–14c, 14e, 14f đỏ**; bỏ 3 guard
chống đệ quy/đua ⇒ **14f đỏ**; bỏ guard `fields_dict` ⇒ **13i đỏ + exit 1**.

Bộ JS sau phase 2: `test_quotation_glass_pick.js` **128 ca** (122 → 128; thay
13g bằng 13i + 14a–14f), `test_quotation_preview_state.js` 17,
`test_quotation_display.js` 12 — **runner thoát 0, stderr rỗng** (hết lỗi timer).

### Còn hở (⛔ thuộc phase 2 này)

1. **In từ List view / bulk print / Print Format qua API** ⛔ đi qua
   `frm.print_doc` ⇒ ⛔ có hộp thoại; cần lớp kiểm khác nếu Owner muốn phủ.
2. **Gửi email báo giá** chưa có lớp kiểm tương tự (ngoài phạm vi yêu cầu).
3. Báo giá **đang mở ở tab khác** hoặc **đóng tab** thì dấu preview mất theo
   phiên (đúng thiết kế §9.1 câu 2), nên ⛔ hỏi lại — nhưng cũng ⛔ in ra giá
   chưa lưu vì giá đó ⛔ bao giờ được lưu.
4. Server chưa kiểm "bản in khớp preview" — chỉ lớp client chặn. Người dùng in
   bằng URL trực tiếp (`/printview?…`) vẫn in bản đã lưu (đúng số DB, ⛔ sai
   dữ liệu, chỉ ⛔ khớp màn hình).

## 9.8 UX1 chặn tiếp trên lớp in + cửa sổ 🖥️ (2026-11-21)

### 🔴 / 🟡 và cách xử lý

| # | Lỗi | Trước | Sau |
|---|---|---|---|
| 🔴1 | Đóng hộp thoại in bằng **X/Esc/click nền** ⇒ cờ `__al_print_dialog_open` kẹt `true` ⇒ mọi `print_doc()` sau đó `return` im lặng **cả phiên**. | `close()` chỉ chạy khi bấm nút; Frappe ⛔ gọi `secondary_action` cho X/Esc. | Thêm `onhide` vào opts: mọi đường đóng đều nhả cờ (`close()` vẫn idempotent). 15a |
| 🔴2 | Toast kết quả nền của 🖥️ phơi **docname dòng con** (hash `7f3a91c0d2…`) ra người dùng. | `"Tính giá xong cho {0} — chưa lưu vào báo giá."` với `quotation_item_name`. | Dùng đúng câu *"Tính giá xong — chưa lưu vào báo giá."* như dialog 📐; ⛔ dùng `name` để định danh. 15b |
| 🟡1 | Lưu **thất bại** vẫn in bản cũ: `frm.save()` resolve kể cả khi validate ném ⇒ backstop `then(finish(true))` chạy. | Backstop coi mọi resolve là thành công. | Backstop chỉ xong khi `is_dirty()` hết true; câu lỗi mới nêu **lối thoát** (tải lại trang để in bản đã lưu). 15c, 15d |
| 🟡2 | Tiêu đề + nội dung **khẳng định sai**: báo giá chưa từng lưu thì ⛔ có "giá đã lưu"; và `printview` có thể nhận document từ trình duyệt nên ⛔ chắc bản in là bản cũ. | *"Bản in đang là giá đã lưu"* cho mọi trường hợp. | Hai tiêu đề theo `frm.is_new()`; nội dung đổi thành *"…để bản in **chắc chắn** khớp số trên màn hình."* 14a, 15g |
| 🟡3 | Cửa sổ 🖥️: nút **Áp dụng vào dòng** bấm được khi chưa có kết quả (đóng im lặng), và **tự bật lại** khi kết quả nền về sau khi người dùng đã đóng. | Không disable nút; `_set_html` luôn `dialog.show()`. | `disable_primary_action()` khi chưa có kết quả, bật lại khi có; cờ `_dialog_open` + `onhide`; `_set_html` ⛔ gọi `show()` khi cửa sổ đã đóng. 15e, 15f |
| 🟡4 ✅ **đã đóng** (2026-11-21) | Câu lỗi **lưu thất bại** nói sai với báo giá **chưa từng lưu**: *"Nếu chỉ cần in bản đã lưu thì tải lại trang (kết quả vừa tính sẽ mất)"* — phiếu mới ⛔ có "bản đã lưu" nào, và tải lại trang mất **toàn bộ báo giá vừa nhập**, ⛔ phải chỉ "kết quả vừa tính". | Một câu cho mọi trường hợp. | Rẽ nhánh theo `frm.is_new()` qua helper `_al_form_is_new` (không có `is_new` ⇒ coi như **đã lưu**, câu nhẹ hơn): phiếu mới — *"Chưa lưu được báo giá nên chưa in. Sửa lỗi vừa hiện rồi bấm Lưu lại — báo giá chưa được lưu lần nào, tải lại trang sẽ mất toàn bộ nội dung vừa nhập."*; phiếu đã lưu — giữ nguyên câu cũ. 15h, 15i |

### Test

| Ca | Nội dung |
|---|---|
| 15a | đóng hộp in bằng `hide()` (X/Esc/nền) ⇒ cờ nhả, lần in sau **mở lại hộp** |
| 15b | toast 🖥️ ⛔ chứa docname; đúng câu + xanh dương |
| 15c | `on_error` ⇒ ⛔ in, câu lỗi có "tải lại trang" |
| 15d | promise resolve nhưng `is_dirty()` vẫn true ⇒ ⛔ in + báo lỗi |
| 15e | chưa có kết quả ⇒ nút Áp dụng DISABLED, gọi thẳng `_apply_to_form_row` ⛔ đóng cửa sổ, ⛔ ghi dòng; có kết quả ⇒ bật lại |
| 15f | đóng cửa sổ rồi kết quả về muộn ⇒ ⛔ `dialog.show()` lại |
| 15g | báo giá chưa lưu ⇒ tiêu đề *"Báo giá chưa được lưu"* |
| 15h | 🟡4 — báo giá **chưa lưu** + lưu lỗi (`on_error`, và cả `callback` có `exc`) ⇒ câu lỗi **không** có "in bản đã lưu", có "mất toàn bộ nội dung vừa nhập"; ⛔ in |
| 15i | 🟡4 — báo giá **đã lưu** + lưu lỗi ⇒ **đúng nguyên câu cũ** (có "in bản đã lưu", "tải lại trang"); form **thiếu `is_new`** ⇒ guard coi như đã lưu (câu nhẹ) |

Đối chứng âm (đã chạy, khôi phục file sau mỗi lượt):

| Bỏ sửa | Ca đỏ |
|---|---|
| Bỏ `onhide` của hộp thoại in | 15a |
| Trả lại `{0}` docname trong toast | 15b |
| Bỏ "tải lại trang" khỏi câu lỗi | 15c |
| Bỏ kiểm `is_dirty()` ở backstop | 15d |
| Luôn cho phép bấm "Áp dụng" | 15e |
| Bỏ cờ `_dialog_open` trong `_set_html` | 15f |
| Tiêu đề cố định | 14a, 15g |
| 🟡4: câu lỗi cố định (bỏ rẽ nhánh, luôn câu cũ) | 15h |
| 🟡4: câu lỗi luôn là bản của phiếu mới | 15i |

Bộ JS sau lượt này: `test_quotation_glass_pick.js` **137 ca** (135 → 137; thêm
15h, 15i cho 🟡4), `test_quotation_preview_state.js` 17, `test_quotation_display.js` 12,
`test_al_formula_refs.js` 8 — **exit 0, stderr rỗng**. Python giữ 12 / 14 / 7 / 48;
`test_phase_b_fbmax.py` đúng 8 ca đỏ sẵn có.

### Còn hở sau lượt này

- **Giả định "bản in đọc DB" chưa đo trên v16** — xem khối ⚠️ ở §9.7. Cần in thử
  trên site bằng 3 đường (menu Print, in từ List, tải PDF) với báo giá vừa sửa
  giá **chưa Lưu** và ghi lại số trên bản in.
- In hàng loạt / in từ List / `/printview?…` trực tiếp ⛔ đi qua `frm.print_doc`
  ⇒ ⛔ có hộp thoại.
- Gửi email báo giá chưa có lớp kiểm tương tự.

## 9.4 Câu hỏi cần Owner chốt (bản gốc — đã trả lời ở §9.1)

1. **BOM lớn (> ngưỡng) xử lý thế nào khi preview không được ghi DB?** Chấp nhận
   "đóng tab giữa chừng là mất kết quả, tính lại", hay cho phép ghi **2 field
   trạng thái** (`al_calc_job_id` + status) để mở lại còn thấy? (ghi 2 field đó
   là ghi DB, dù `modified` không nhảy.)
2. **Có cần kết quả preview sống qua reload/đăng nhập lại không?** Nếu **có** ⇒
   phải chọn phương án B (bảng nháp) và chấp nhận bảng thứ hai phải nuôi.
3. **Khi Lưu mà tham số đã đổi so với lúc Preview** (hoặc chưa từng Preview):
   **chặn** bắt tính lại, hay **tự tính lại dòng lệch rồi mới lưu**? Chặn = an
   toàn, phiền; tự tính = mượt, Lưu chậm hơn.
4. **Có cần lưu vết MỖI lần preview** (ai, lúc nào, tham số gì) phục vụ đối
   chiếu/support không? Nếu có thì phải ghi DB — trái mục tiêu, nên chốt ngay.
5. **In/gửi email khi đang có kết quả chưa lưu:** bắt buộc **Lưu trước** (một
   nút "Lưu rồi in"), hay chỉ cảnh báo rồi vẫn cho in bản đã lưu?

---

## 10. Những gì tôi **chưa đo được** (cần site/DB mới chốt)

1. **Binding FVB thật trên site** có record nào `applies_to_doctype="Quotation Item"`
   không. Tôi suy từ seed (`patches/v28_9/…:15-26`) — nếu production có binding
   khác thì preview dòng cũ có thể đọc field cũ **im lặng** (§2.1). Đo:
   `SELECT variable_name, applies_to_doctype FROM "tabFormula Variable Binding" WHERE is_active=1 AND applies_to_doctype='Quotation Item'`.
2. **ERPNext v16** có còn giữ `rate` ngoài `force_item_fields` và
   `validate → calculate_taxes_and_totals` như v14 không (§Q5). Đo trên bench đích.
3. **`tabVersion`/`tabComment`** có bị ghi trong lượt `frappe.client.set_value`
   hiện nay không (để ca test "không đổi một byte" có mốc so đúng).
4. **Thời gian 1 lượt preview** (trung vị/p95) trên site thật, để biết bỏ commit
   có cải thiện thật không.
5. **Ai đang gọi `alumglass.api.calculate_bom` ngoài UI** (MCP/tích hợp/script
   ngoài repo) — trước khi đổi chữ ký endpoint.
