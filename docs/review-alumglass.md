# Nhận xét AlumGlass — phần tính giá dùng Formula Builder

**Ngày:** 2026-10-12
**Nền rà soát:** nhánh `master`, HEAD `d382881` *"bo sung tai lieu"*
**Phạm vi:** ⚠️ **chỉ phần tính giá có dùng Formula Builder** — luồng BOM, 2 chỗ dựng engine,
handler nguồn dữ liệu, và mức tận dụng thư viện. ⛔ **Không** rà phần báo giá UI, Excel I/O,
in ấn, phân quyền ngoài luồng tính giá.
**Quy mô:** 207 tệp `.py` · 15 355 dòng toàn kho · 8 tệp test · **38** hàm test trong lớp
(+ **10** hàm test bị bỏ qua — xem 🔴 #1)

> 📌 **Phân biệt tên tệp:** `docs/review_alumglass.md` (**gạch dưới**) là *hướng dẫn sử dụng
> A-Z*, ⛔ **không** phải bản nhận xét. Tệp bạn đang đọc dùng **gạch ngang** và là bản rà
> soát kỹ thuật. Hai tệp khác nhau, ⛔ đừng lẫn.

**Cách kiểm:** đọc mã nguồn + **đo bằng máy**. Chỗ suy từ đọc mã ghi 🔎; chỗ đo được ghi ✅.

---

## 0. Tóm tắt cho người quyết định

| # | Mức | Vấn đề | Chỗ | Ảnh hưởng |
|---|---|---|---|---|
| 1 | 🔴 | **10 ca test bảo mật ⛔ không bao giờ chạy trong CI** — gồm 2 ca chặn RCE | `tests/test_safe_eval_a3.py` | Bản vá RCE ⛔ không có lưới an toàn |
| 2 | 🔴 | **Gói mẫu chết** chứa bảng giá **mâu thuẫn dữ liệu thật** | `alumglass/formula_builder/` | Người sau copy giá sai vào code thật |
| 3 | 🟡 | Tận dụng Formula Builder còn thấp — tự làm lại thứ thư viện đã có | `bom_orchestrator.py`, `api/__init__.py` | Trùng lặp, lệch hành vi |
| 4 | 🟡 | Hàm khổng lồ: 1 hàm **288 dòng**, 2 hàm >200 dòng | `bom_orchestrator.py:826`, `api/__init__.py:737,437` | Khó test, khó review |
| 5 | 🟡 | Khai Python 3.14, bench chạy 3.10.12 (giống formula_builder) | `pyproject.toml:7,28` | "Xanh trên máy" ⛔ không suy ra "xanh trên CI" |
| 6 | 🟢 | `_build_trace` **chép làm 2 bản** đã bắt đầu lệch nhau | `bom_orchestrator.py:138`, `api/__init__.py:1217` | Sửa 1 nơi, nơi kia lệch |
| 7 | 🟡 | **Cơ hội tốc độ lớn**: giữ engine lại thay vì dựng mới mỗi lần tính | `bom_orchestrator.py:2154`, `:2475` | Nhanh **45×** ở B6 — xem **mục 6** |

**Điểm mạnh rõ:** phân quyền và dùng `safe_eval` của Formula Builder đều làm **đúng** —
chi tiết ở mục 3.

**Việc lớn nhất về kiến trúc** — phần nào của `FlexibleFormulaEngine` cần, phần nào lược bỏ
được, và bỏ nó thì có mất tính linh hoạt hay tốc độ không — nằm ở **mục 6**.

---

## 1. Luồng tính giá và 2 chỗ dựng engine

### 1.1 Chuỗi pha

`alumglass/engine/bom_orchestrator.py` (2 696 dòng, 59 hàm) chia thành các pha có tên:

| Pha | Hàm | Dòng | Việc |
|---|---|---|---|
| B1 | `b1_gather_inputs` | `:337` (117 dòng) | Gom đầu vào |
| B2 | `b2_prefetch_master_data` | `:826` (**288 dòng**) | Nạp trước dữ liệu chủ |
| B3 | `b3_build_formulas` | `:1936` (160 dòng) | Dựng danh sách công thức |
| **B4** | `b4_calculate_bom_items` | `:2151` | **Dựng engine #1** — tính dòng vật tư |
| B6 | `b6_calculate_cost_template` | `:2395` | **Dựng engine #2** — tính giá |

**Có đúng 2 chỗ dựng engine**, ⛔ không hơn (đã quét toàn bộ app):

**Chỗ #1 — `bom_orchestrator.py:2154`, dùng `FormulaEngine`:**

```python
engine = FormulaEngine(
    formulas=self.bom_formulas,
    safe_funcs={
        "lookup_calc_pattern": lookup_calc_pattern,
        "lookup_rule": _lookup_rule,
        "roundup": _roundup,
    },
    on_error="default", default_value=0, deterministic=True,
)
result = engine.calculate(dict(self.inputs))
```

**Chỗ #2 — `bom_orchestrator.py:2463` (`EngineConfig`) rồi `:2475`
(`FlexibleFormulaEngine`):** cấu hình `global_formulas` + `extra_context` +
`custom_functions`.

Hai engine nối nhau qua `self.inputs.update(result)` — tức **AlumGlass tự chia pha**:
engine #1 tính dòng, đổ kết quả vào `self.inputs`, rồi engine #2 đọc lại để tính giá.

> 💡 **Nhận xét kiến trúc quan trọng:** cách tự chia pha này **đúng cùng hình dạng** với cơ
> chế *"lượt hai có mục tiêu"* mà Formula Builder v31 vừa bổ sung
> (`flexible_formula_engine.py:786`). Nghĩa là AlumGlass đang **tự làm lại bằng tay** thứ
> thư viện nay đã cung cấp sẵn. ⛔ Không phải lỗi — nhưng là cơ hội giảm mã.

### 1.2 Chỗ AlumGlass **chạm** vào bề mặt bảo mật của Formula Builder

`safe_eval` của FB được dùng ở **3 nơi** — cả 3 đều đúng cách
(`ExpressionPolicy` + `compile_expression`, ⛔ **không** `eval` trần):

| Tệp | Dòng |
|---|---|
| `alumglass/formula_handlers.py` | `:22, :81, :119, :250` |
| `alumglass/al_bom_engine/doctype/al_cost_template/al_cost_template.py` | `:5, :139` |
| `alumglass/al_formula_rules/doctype/al_quantity_calc_method/al_quantity_calc_method.py` | `:16` |

### 1.3 Nguồn dữ liệu đã đăng ký với Formula Builder

`alumglass/fb_handlers.py` (308 dòng, 3 hàm) đăng ký **đúng 2** loại nguồn:

| Loại nguồn | Dòng | Hàm xử lý | `fingerprint_fn` |
|---|---|---|---|
| `aluminum_price_composite` | `:53` | 187 dòng (`:82`) | ✅ có |
| `glass_master_data` | `:271` | 18 dòng (`:291`) | ✅ có |

Cả hai đều có `fingerprint_fn` — ✅ **tốt**: đây là điều kiện để cache dùng lại được kết quả.

---

## 2. Mức tận dụng Formula Builder

✅ Đếm trên toàn app (⛔ không tính gói mẫu chết ở mục 4, 🔴 #2):

| Tính năng của Formula Builder | AlumGlass dùng? |
|---|---|
| `FormulaEngine` (lõi) | ✅ 1 chỗ |
| `FlexibleFormulaEngine` | ✅ 1 chỗ |
| `safe_eval` (`ExpressionPolicy`, `compile_expression`) | ✅ 3 chỗ |
| `register_source` + `fingerprint_fn` | ✅ 2 loại nguồn |
| `child_tables` (bảng dòng trong công thức) | ❌ **0 lần** |
| `OutputField` (khai báo đầu ra) | ❌ **0 lần** |
| `row_id` / biến dòng | ❌ **0 lần** |
| `multi_scenario` | ❌ **0 lần** |
| `explain()` / `explain_all()` | ❌ **0 lần** — tự viết `_build_trace` (xem 🟢 #6) |

**Đọc bảng này ra sao:** AlumGlass dùng Formula Builder ở mức **"gọi engine để tính"** —
đúng và hiệu quả cho việc đang làm, nhưng ⛔ chưa dùng các tính năng *mô hình hoá* (bảng
dòng, đầu ra khai báo, nhiều kịch bản, giải thích). Hệ quả trực tiếp là phần tự chia pha
(mục 1.1) và phần tự viết vết (🟢 #6).

⚠️ **Đây là nhận xét về mức tận dụng, ⛔ không phải lỗi.** Chuyển sang dùng `child_tables`
là việc lớn, cần job riêng — xem mục 7.

---

## 3. Điểm mạnh (đã kiểm chứng)

**3.1 — Phân quyền chặt, có lý do viết rõ.** `api/__init__.py` có **11**
`@frappe.whitelist()` và **✅ 0** `allow_guest`. Hàm `calculate_bom` (`:7`) chặn **hai lớp**
trước khi làm gì:

```python
_require_quotation_item_permission(quotation_item_name, ptype="read")   # :31
from alumglass.engine.bom_orchestrator import assert_quotation_item_editable
assert_quotation_item_editable(quotation_item_name)                     # :37
```

Docstring (`:19-25`) giải thích **vì sao** đặt chốt thứ hai ngay sau chốt thứ nhất, và vì
sao ngưỡng `ASYNC_BOM_THRESHOLD` chia đồng bộ / bất đồng bộ. Đây là kiểu ghi chú đúng:
người sau đọc là hiểu ý đồ, ⛔ không phải đoán.

**3.2 — Chuỗi lambda từ DB ⛔ không bao giờ qua `eval` trần.** Cả 3 chỗ compile đều đi qua
`compile_expression` của Formula Builder (`formula_handlers.py:119,250`;
`al_cost_template.py:139`). `al_cost_template.py:104,138` ghi rõ: *"mở rộng scope ⛔ KHÔNG
nới lỏng chốt chặn RCE — `compile_expression` chặn import/lambda/dunder/getattr"*.

**3.3 — Chỉ đăng ký 2 loại nguồn, cả hai đều có `fingerprint_fn`.** Bề mặt nhỏ, dễ rà
(mục 1.3). ✅ Tốt hơn nhiều so với đăng ký tràn lan.

**3.4 — Chia pha có tên và có docstring.** `b1_`…`b6_` đọc là hiểu thứ tự; mỗi pha một hàm.

**3.5 — Tách `standalone_tests/` ra ngoài gói.** `alumglass/standalone_tests/test_phase_b_fbmax.py`
(1 014 dòng) nằm **ngoài** `alumglass/` để `os.walk` của `bench run-tests` ⛔ không nhặt
nhầm — và docstring nói rõ lý do. Đây là **cách né đúng** cái bẫy sẽ nói ở 🔴 #1. Đáng
học.

---

## 4. Phát hiện

### 🔴 #1 — 10 ca test bảo mật ⛔ không bao giờ chạy trong CI

`alumglass/tests/test_safe_eval_a3.py` khai **10 hàm `test_*` ở cấp module** và
**0 lớp `TestCase`**.

✅ **Xác minh bằng chính bộ gom test mà Frappe dùng:**

```
unittest.TestLoader().loadTestsFromModule(m).countTestCases()  →  0
hàm test_* ở cấp module                                        →  10
lớp TestCase                                                   →  0
```

`bench run-tests` gom test bằng `loadTestsFromModule()` (`frappe/test_runner.py:269`), và
bộ gom này **chỉ nhặt lớp `TestCase`**. Hàm cấp module bị bỏ qua **im lặng** — ⛔ không
cảnh báo, ⛔ không lỗi, bộ test chỉ đơn giản là thiếu.

CI của app chạy đúng đường đó (`alumglass/.github/workflows/ci.yml:129-130`):

```yaml
bench --site test_site set-config allow_tests true
bench --site test_site run-tests --app alumglass
```

**10 ca bị bỏ qua — trong đó có 2 ca chặn RCE:**

| Dòng | Ca |
|---|---|
| `:132` | 🔴 **`test_calc_rce_payloads_rejected`** |
| `:198` | 🔴 **`test_preview_cost_template_rce_rejected`** |
| `:122` | `test_non_lambda_calc_fn_rejected` |
| `:263` | `test_register_source_no_legacy_bucket_handler` |
| `:225` | `test_register_source_two_handlers` |
| `:98,106,166,186,210` | 5 ca còn lại |

**⚠️ Điểm trớ trêu:** docstring đầu tệp (`:5-13`) hướng dẫn chạy bằng
`python3 -m pytest …`, nhưng CI của app **⛔ không có `pytest`** — chỉ có `bench run-tests`.
Nên tài liệu trong tệp mô tả một đường chạy mà CI ⛔ không thực thi.

**Hệ quả thật:** bản vá RCE (A3a/A4) ⛔ **không có lưới an toàn trong CI**. Ai đó sửa
`safe_eval` theo hướng nới lỏng, CI vẫn xanh.

**Cách sửa (nhỏ, rõ):** bọc 10 hàm vào một lớp `unittest.TestCase` — đúng như
`formula_builder/tests/test_row_output_dependency.py` đã làm trong commit `7c689f0`. Sau
khi bọc phải kiểm lại số test mà bộ gom nhặt được (⛔ đừng chỉ tin mắt).

> 💡 **Phép thử dùng lại được cho mọi repo:**
> ```
> python -c "import unittest,<module> as m; print(unittest.TestLoader().loadTestsFromModule(m).countTestCases())"
> ```
> Ra `0` ⇒ test của bạn ⛔ không bao giờ chạy.

---

### 🔴 #2 — Gói mẫu chết chứa bảng giá mâu thuẫn dữ liệu thật

`alumglass/formula_builder/` là một gói **nằm trong** app nhưng **⛔ không ai dùng**:

| Tệp | Dòng |
|---|---|
| `templates.py` | 337 dòng, **116 công thức**, ⛔ không import gì |
| `README.md` | dạy dùng `ALUMINUM_PRICE_TABLE`, `GLASS_PRICE_TABLE` |
| `__init__.py` | chỉ có docstring |
| `examples/01_bao_gia.py`, `02_giathanh.py`, `03_du_toan.py` | chỉ tự import nhau |

✅ Đã quét: **⛔ không có tệp nào ngoài gói này import nó.**

**Vấn đề ⛔ không phải "mã chết" — mà là nó đang nói SAI giá.** Bảng giá cứng trong
`templates.py` (`:327`) mâu thuẫn với dữ liệu seed:

| Mã | `templates.py` | `seed_demo_data.py:288` | Lệch |
|---|---|---|---|
| **`KINH-DON-8`** | **250 000** (`:327`) | **550 000** | **2,2×** |
| `KINH-LOWE-24` | 1 150 000 (`:336`) | 1 150 000 | khớp |

Và trong 10 mã kính mà `templates.py` khai, **8 mã ⛔ không tồn tại** trong seed:

```
⛔ KINH-DON-10 · KINH-DON-12 · KINH-CL-8 · KINH-CL-10
⛔ KINH-CL-12 · KINH-HOP-16 · KINH-HOP-20 · KINH-HOP-24
✅ có trong seed: KINH-DON-8, KINH-LOWE-24
```

**Hệ quả thật:** gói này **đọc rất giống mã dùng được** — có README, có ví dụ chạy được,
có bảng giá. Người mới (hoặc AI) tìm "công thức tính giá nhôm kính" sẽ thấy nó và copy.
Giá sai 2,2× đi thẳng vào báo giá khách.

**Cách sửa, chọn một:**
1. **Xoá** gói `alumglass/formula_builder/` — ⛔ không ai dùng, ⛔ không có test.
2. Giữ nhưng đổi tên thành `docs/sample/` và thêm cảnh báo đầu mỗi tệp:
   *"⚠️ Số trong đây là VÍ DỤ, ⛔ không phải giá thật. Giá thật ở `seed_demo_data.py`."*

> ⚠️ Đây là điểm tôi **đề nghị Owner quyết** — xoá là việc ⛔ không hoàn tác dễ.

---

### 🟡 #3 — Tận dụng Formula Builder còn thấp: tự làm lại thứ thư viện đã có

Xem bảng ở mục 2. Hai biểu hiện cụ thể:

**a) Tự chia pha bằng tay.** AlumGlass chạy engine #1 (dòng vật tư), đổ vào `self.inputs`,
rồi chạy engine #2 (giá). Formula Builder v31 có cơ chế "lượt hai có mục tiêu"
(`flexible_formula_engine.py:786`) làm **đúng việc này**, có kiểm soát phụ thuộc và có test
đột biến bảo vệ.

**b) ⛔ Không dùng `child_tables`.** Đây chính là lý do AlumGlass phải tự quản dòng vật tư
trong `self.inputs` thay vì để engine hiểu bảng dòng.

**Đánh 🟡 ⛔ không phải 🔴** vì mã hiện tại **chạy đúng**; đây là nợ kỹ thuật, ⛔ không phải
lỗi. Chi phí đổi lớn — xem mục 7.

---

### 🟡 #4 — Hàm khổng lồ

✅ Đo bằng `ast`:

| Tệp | Hàm dài nhất | Dòng | >100 dòng | >200 dòng |
|---|---|---|---|---|
| `alumglass/engine/bom_orchestrator.py` (2 696 dòng, 59 hàm) | `b2_prefetch_master_data` | **288** (`:826`) | 6 | 1 |
| | `b3_build_formulas` | 160 (`:1936`) | | |
| | `_resolve_system_variables` | 126 (`:545`) | | |
| | `b1_gather_inputs` | 117 (`:337`) | | |
| `alumglass/api/__init__.py` (1 407 dòng, 39 hàm) | `get_variable_set_for_bom` | **287** (`:737`) | 3 | 2 |
| | `get_formula_context` | **220** (`:437`) | | |
| | `get_result_display` | 143 (`:1242`) | | |

Hàm 288 dòng ⛔ không test nổi theo từng nhánh — và ✅ thực tế `test_bom_orchestrator.py`
chỉ có **3** ca test cho cả tệp 2 696 dòng.

**Cách sửa:** tách `b2_prefetch_master_data` theo **loại dữ liệu chủ** (nhôm / kính / phụ
kiện) — đó là ranh giới tự nhiên đã có sẵn trong thân hàm.

---

### 🟡 #5 — Khai Python 3.14, chạy Python 3.10

Giống hệt formula_builder: `pyproject.toml:7` ghi `requires-python = ">=3.14"`,
`:28` ghi `target-version = "py314"`, CI dùng Python 3.14
(`.github/workflows/ci.yml:60`) — nhưng ✅ bench cục bộ chạy **Python 3.10.12**.

**Hệ quả:** kết quả "chạy được ở máy" ⛔ không suy ra "chạy được ở CI". Xem
`review-formula-builder.md` 🟡 #4 để biết chi tiết và cách sửa.

---

### 🟢 #6 — `_build_trace` chép làm 2 bản, đã bắt đầu lệch

Cùng một hàm, hai bản:

| Tệp | Dòng | Docstring tự nhận |
|---|---|---|
| `bom_orchestrator.py` | `:138` | *"Trace dạng **string**"* |
| `api/__init__.py` | `:1217` | *"Trace dạng **HTML-safe** string"* |

Hai docstring **đã khác nhau** — dấu hiệu hai bản đã bắt đầu trôi. Formula Builder có sẵn
`explain()` / `explain_all()` (`flexible_formula_engine.py:1097,1137`;
`engine_public.py:50,136`) cùng kiểu dữ liệu `ExplainStep` / `TraceNode`
(`formula_utils/types.py:52,206`).

**Cách sửa:** gom về **một** hàm dùng chung; hoặc chuyển hẳn sang `explain_all()` của thư
viện (việc lớn hơn).

---

## 5. Test & CI

**5.1 — Cơ chế.** `alumglass/.github/workflows/ci.yml` cài
`bench get-app formula_builder … --branch develop`, rồi `erpnext` / `formula_builder` /
`alumglass`, rồi `bench --site test_site run-tests --app alumglass` (`:129-130`).
⛔ **Không có `pytest` ở đâu trong CI.**

**5.2 — Số ca test mà CI thật sự nhặt được:**

| Tệp | Lớp | Ca test |
|---|---|---|
| `test_async_bom_calculation.py` | 1 | 9 |
| `test_cost_template_validate.py` | 1 | 8 |
| `test_calc_pattern_hybrid.py` | 1 | 7 |
| `test_composite_pricing.py` | 2 | 6 |
| `test_bom_orchestrator.py` | 2 | 3 |
| `test_pricing_dimension_snapshot.py` | 1 | 3 |
| `test_bom_version_autocreate.py` | 1 | 2 |
| **`test_safe_eval_a3.py`** | **0** | **⛔ 0 (10 hàm trần — xem 🔴 #1)** |
| **Tổng chạy được** | | **38** |

**5.3 — Phủ theo tệp sản phẩm:**

| Tệp sản phẩm | Dòng | Có test? |
|---|---|---|
| `engine/bom_orchestrator.py` | 2 696 | 🟡 3 ca |
| `api/__init__.py` | 1 407 | ✅ có |
| `api/excel_io.py` | 704 | ❌ ⛔ không |
| `setup/seed_demo_data.py` | 502 | ❌ ⛔ không |
| `hooks.py` | 391 | ❌ ⛔ không |
| `formula_handlers.py` | 365 | ⚠️ chỉ qua `test_safe_eval_a3` — mà tệp đó ⛔ không chạy |
| `fb_handlers.py` | 308 | ⚠️ chỉ qua `test_safe_eval_a3` — mà tệp đó ⛔ không chạy |

> ⚠️ **Hai dòng cuối là hệ quả trực tiếp của 🔴 #1:** `formula_handlers.py` và
> `fb_handlers.py` — tức chỗ chạm `safe_eval` — về mặt *số đo* đang ⛔ **không có test nào
> chạy trong CI**. Sửa 🔴 #1 là lấp luôn khoảng trống này.

---

## 6. `FormulaEngine` hay `FlexibleFormulaEngine` — phần nào cần, phần nào lược bỏ

Mục này trả lời 3 câu: **(a)** `FlexibleFormulaEngine` (FFE) thực chất làm gì, **(b)** AlumGlass
cần phần nào trong đó, **(c)** bỏ nó thì có mất **tính linh hoạt** và **tốc độ** không.

> ⚠️ **Đính chính số liệu.** Trong quá trình trao đổi tôi từng báo *"FFE chậm hơn 54×"*.
> Con số đó **đã gộp hai thay đổi khác nhau** làm một. Số đúng, tách bạch, ở mục 6.4.

### 6.1 FFE thực chất chỉ làm **một** việc

FFE ⛔ không phải "engine mạnh hơn". Công dụng duy nhất của nó là:

> **Khi chuỗi công thức nằm trong DỮ LIỆU — mỗi dòng mang công thức riêng — nó đọc chuỗi
> đó ra, thay giá trị cột vào, chạy, rồi ghi kết quả ngược lại vào dòng.**

| | `FormulaEngine` | `FlexibleFormulaEngine` |
|---|---|---|
| Nhận vào | `formulas=[…]` — danh sách dựng sẵn | bảng dòng, **mỗi dòng có chuỗi công thức riêng** |
| Thay giá trị cột vào công thức | ⛔ không | ✅ `_inject_row_values` (`flexible_formula_engine.py:585`) |
| Ghi kết quả về dòng | ⛔ không | ✅ `_write_back` (`:633`) |
| Tính lại header đọc dòng | ⛔ không | ✅ "lượt hai" (`:786`) |
| Nhiều kịch bản dùng lại engine | ⛔ không | ✅ `multi_scenario` (`:1156`) |

**Bốn tính năng trên chỉ có nghĩa khi công thức là dữ liệu nhập theo TỪNG DÒNG.** Nếu
AlumGlass tự ghép danh sách công thức bằng Python thì ⛔ **cả bốn đều không dùng đến**.

### 6.2 Phần nào AlumGlass **cần** — và ⛔ không bỏ được

**Cần: đọc công thức từ DB.** `b3_build_formulas` (`bom_orchestrator.py:1936`) ghi rõ
*"Build formulas từ Bom Item fields (DATA-DRIVEN)"* (`:2041`) — chuỗi công thức nằm trong
cột `width`, `height`, `qty`… của **Bom Item** (`DEFAULT_FORMULA_FIELDS`, `:208`).

Đây là phần **cốt lõi và ⛔ không bỏ được**. Nhưng ⚠️ **nó ⛔ không cần FFE** để làm —
`b3_build_formulas` đã tự đọc DB và tự ghép list bằng Python rồi. FFE ⛔ không tham gia
vào bước này.

**Cần: truyền kết quả B4 sang B6.** Hiện làm bằng `self.inputs.update(result)` — một bước
Python ở giữa hai engine.

### 6.3 Phần nào **lược bỏ được**

✅ Đếm trên toàn app, AlumGlass dùng **0 lần** những thứ sau (⛔ không tính gói mẫu chết 🟢 #2):

| Tính năng của FFE | AlumGlass dùng? |
|---|---|
| `child_tables` (công thức theo dòng) | ❌ **0 lần** |
| `_inject_row_values` (thay cột vào công thức) | ❌ **0 lần** |
| `_write_back` (ghi kết quả về dòng) | ❌ **0 lần** |
| "Lượt hai" cho header đọc dòng | ❌ **0 lần** — AlumGlass **tự chia pha** thay vì dùng |
| `multi_scenario` | ❌ **0 lần** |

**B4 đã đúng rồi** — nó dùng `FormulaEngine` trần (`:2154`). **Chỉ B6 còn bọc FFE**
(`:2475`) mà ⛔ không dùng tính năng nào của nó.

⚠️ **B6 đang trả giá cho một lớp bọc nằm im.** `EngineConfig` của B6 chỉ đặt 6 trường:
`global_formulas`, `extra_context`, `on_error`, `default_value`, `deterministic`,
`custom_functions`. Cả 6 đều **map thẳng** thành tham số của `FormulaEngine`.

### 6.4 Bỏ FFE thì mất gì? — ✅ **⛔ không mất gì**

✅ **Đã kiểm bằng máy:** `FormulaEngine.__init__` nhận **thẳng** cả 10 tham số mà
`EngineConfig` + `_engine_kwargs` (`flexible_formula_engine.py:452`) sinh ra:

```
on_error · default_value · deterministic · max_operations · safe_funcs
strict · rounding_policy · assertions · input_fields · output_fields
```

Nghĩa là `EngineConfig` **thuần tuý là lớp đổi tên cho tiện** — ⛔ không thêm khả năng nào.
Bỏ nó ⛔ **không mất** khả năng lược đồ (`input_fields`/`output_fields`), khả năng khẳng
định (`assertions`), chính sách làm tròn (`rounding_policy`), hay giới hạn
(`max_operations`, `strict`) — vì tất cả đều truyền thẳng được.

✅ **A/B trên đúng hình dạng B6** (5 công thức cost template, cùng context) — kết quả và
**cả nhánh lỗi** đều tương đương:

| | FFE (hiện tại) | `FormulaEngine` (đề xuất) |
|---|---|---|
| `GIA_VAT` | 1 524 322,41 | 1 524 322,41 ✅ |
| Số khoá kết quả | 5 | 5 ✅ |
| Lỗi khi công thức sai | 1 — `name 'khong_ton_tai_xyz' is not defined` | 1 — **y hệt** ✅ |
| Giá vẫn ra khi 1 dòng lỗi | ✅ | ✅ |

**⛔ Chỉ có MỘT dòng phải đổi.** Hai engine trả về **hai kiểu khác nhau**:

| | `FlexibleFormulaEngine.calculate()` | `FormulaEngine.calculate()` |
|---|---|---|
| Kiểu trả về | `CalculationResult` | **dict thuần** |
| Lấy giá trị | `result.values` | `dict(result)` |
| Lấy lỗi | `result.errors` | **`engine.last_errors`** ← chỗ duy nhất phải sửa |

B6 hiện đọc `result.errors` (`bom_orchestrator.py:2481`). B4 đã đọc đúng kiểu
`engine.last_errors` (`:2168`) — nên **B4 là mẫu để copy cho B6**.

✅ **`_drain_engine_warnings` ⛔ không phải sửa** — nó hút cảnh báo từ **túi dùng chung**
(`composite_pricing.drain_engine_warnings()`, `:1470`), ⛔ không đọc từ engine. Nên đổi
engine ⛔ không ảnh hưởng.

**Về "tính linh hoạt" — trả lời thẳng:** thứ AlumGlass cần là *"công thức đến từ DB"*, và
điều đó đạt được bằng cách **truyền `formulas=[…]` dựng từ DB** — ⛔ không cần FFE. Cái FFE
cho thêm (công thức theo *từng dòng*, ghi ngược về dòng) là thứ AlumGlass **đang ⛔ không
dùng**. Nếu sau này muốn dùng (ví dụ cho phép người dùng sửa công thức trên từng dòng vật
tư), lúc đó **thêm lại FFE** — và nó vẫn nằm đó, ⛔ không mất.

### 6.5 Tốc độ — tách bạch **hai** thay đổi

Đây là chỗ tôi từng báo sai. Có **hai** thay đổi khác nhau, và chúng ⛔ không cùng cỡ:

✅ Đo lại, cùng 5 công thức cost template, kết quả cả 3 đường **giống hệt nhau**:

| | Cách làm | Thời gian | Nhanh hơn |
|---|---|---|---|
| 1 | FFE, dựng mới mỗi lần *(hiện tại)* | 0,0865 ms | gốc |
| 2 | `FormulaEngine`, **vẫn dựng mới** mỗi lần | 0,0764 ms | **1,13×** |
| 3 | `FormulaEngine`, **giữ lại** | 0,0019 ms | **45,1×** |

**Đọc bảng này ra sao:**

- 🔹 **Chỉ bỏ lớp bọc FFE: nhanh 1,13×** (tiết kiệm 12% thời gian). Nhỏ.
- 🔹 **Giữ engine lại: nhanh thêm 40×.** Đây mới là phần chính.

⚠️ **Vì vậy: đổi lớp ⛔ không phải là cách tăng tốc.** Lợi ích thật nằm ở **giữ engine**.
Đổi lớp chỉ là hệ quả đi kèm — và là điều kiện để giữ engine **gọn** (giữ một lớp bọc có
`calculate()` tự dựng lại engine con bên trong thì ⛔ không giữ được gì).

✅ **Lợi ích của việc giữ engine, đo ở hình dạng BOM đầy đủ** (nguyên mẫu 5 vật tư × 5 sản
phẩm khác w/h/n_panel, công thức đọc từ dữ liệu):

```
dựng lại engine mỗi sản phẩm : 0,2940 ms
giữ engine, chỉ đổi context  : 0,0182 ms   → nhanh 16,1×
kết quả                      : giống hệt
```

✅ Và ở mức engine trần, 6 công thức × 4 ca w/h khác nhau: **nhanh 30,2×**, kết quả giống hệt.

*(Các con số 16× / 30× / 45× chênh nhau vì khác số công thức và khác cách gom lô — mỗi số
ghi kèm phạm vi đo của nó. Xu hướng thì nhất quán: **giữ engine là phần thắng lớn**.)*

### 6.6 Cách làm đề xuất — mỗi sản phẩm một lần gọi, engine dùng chung

**Nguyên tắc: giữ engine đã dựng, chỉ đổi `context`.** Hình dạng code:

```python
# Dựng MỘT lần cho mỗi bộ công thức (ở cấp BOM, ⛔ không phải mỗi sản phẩm)
eng = FormulaEngine(formulas=FORMULAS_TU_DB, safe_funcs=FUNCS,
                    on_error="default", default_value=0, deterministic=True)

# Mỗi sản phẩm (khác w/h/n_panel): chỉ truyền context
ket_qua = eng.calculate(context_cua_san_pham)
```

**Khoá cache là gì — ⛔ đừng dùng mã BOM.** Dùng **cặp `(tên, công thức)` đã resolve**,
kèm tham số hành vi. Thư viện đã làm đúng y vậy trong `multi_scenario`
(`flexible_formula_engine.py:1199`):

```python
key = tuple((f["name"], f["formula"]) for f in all_formulas)
```

kèm ghi chú `:1187`: *"Kịch bản có đổi dữ liệu dòng ⇒ công thức khác ⇒ tự động dựng engine
mới."*

Nguyên mẫu chạy được (đã đo, xem 6.5):

```python
class BomEngineCache:
    @staticmethod
    def key(formulas, behaviour):
        body = json.dumps([[f["name"], f["formula"]] for f in formulas], sort_keys=True)
        bh   = json.dumps({k: str(v) for k, v in sorted(behaviour.items())}, sort_keys=True)
        return hashlib.sha256((body + "|" + bh).encode()).hexdigest()

    def get(self, formulas, behaviour):
        k = self.key(formulas, behaviour)
        if k not in self._d:
            self._d[k] = FormulaEngine(formulas=formulas, **behaviour)
        return self._d[k]
```

**✅ Tính chất đẹp nhất: tự vô hiệu hoá.** Cứ truyền `formulas` mỗi lần gọi — cache **tự**
phát hiện giống hay khác. ⛔ Không cần biết lúc nào phải xoá cache:

- BOM đổi cấu trúc ⇒ khoá đổi ⇒ **tự dựng lại** ✅
- Chỉ đổi w/h ⇒ khoá y nguyên ⇒ **dùng lại** ✅

⚠️ **Phải gồm tham số hành vi** (`on_error`, `default_value`, `deterministic`,
`rounding_policy`…), ⛔ không chỉ công thức. Đây **đúng là lỗi** đã tìm thấy ở
`_engine_cache.py` của chính thư viện — xem `review-formula-builder.md` 🟡 #1. ⛔ Đừng lặp lại.

⚠️ **Nếu KHÔNG tự ghép công thức mà để FFE quản dòng:** lúc đó khoá cache **⛔ không dùng
được** cách trên, vì `_inject_row_values` thay **giá trị cột vào chính chuỗi công thức**
(`"2 * 100"` → `"5 * 100"` khi qty đổi). ✅ Đã đo — cache theo công thức khi đó cho **số sai
im lặng**:

```
qty=5 tính thật      → 700   ← đúng
qty=5 qua engine cache → 400   ← sai, lệch 300, ⛔ không exception
```

Đây chính là loại lỗi mà bản vá "lượt hai" của Formula Builder v31 vừa đi vá — nên ⛔ đừng
tạo lại nó ở tầng ứng dụng.

### 6.7 Điều kiện an toàn đã kiểm

✅ **Trạng thái lỗi ⛔ không tích luỹ.** Sau một lần tính lỗi (2 lỗi), lần sau sạch (0 lỗi)
— dùng lại engine an toàn, `last_errors` được ghi mới mỗi lần `calculate()`.

✅ **Dùng lại chính dict context cũ vẫn đúng** với `FormulaEngine` trần:

```
W=1200 → 1.332.449
W=2400 (sửa TRONG cùng dict) → 2.103.767
W=2400 (context mới)         → 2.103.767   ✅ khớp
```

⚠️ **Đính chính:** cảnh báo "phải truyền context mới mỗi lần" tôi nói trước đó là **quá
rộng**. Nó chỉ đúng cho đường `child_tables`, vì `_write_back` (`:657`) sửa dict dòng **tại
chỗ**. Đường AlumGlass đang đi (scalar + tự ghép công thức) thì ⛔ **không dính**.

### 6.8 Kết luận mục 6

| Câu hỏi | Trả lời |
|---|---|
| FFE có cần cho B4? | ⛔ **Không** — B4 đã dùng `FormulaEngine` trần |
| FFE có cần cho B6? | ⛔ **Không** — chỉ truyền `global_formulas`, ⛔ không dùng tính năng nào của FFE |
| Bỏ FFE có mất linh hoạt? | ⛔ **Không** — `FormulaEngine` nhận thẳng cả 10 tham số (6.4) |
| Bỏ FFE có nhanh hơn nhiều? | ⛔ **Không nhiều** — riêng việc bỏ lớp bọc chỉ **1,13×** (6.5) |
| Vậy tốc độ đến từ đâu? | **Từ việc GIỮ engine lại** — **45×** ở B6, **16×** trên mỗi sản phẩm (6.5) |
| Có mất kết quả / mất lỗi không? | ⛔ **Không** — A/B tương đương cả giá trị lẫn nhánh lỗi (6.4) |
| Việc phải sửa là gì? | **1 dòng**: `result.errors` → `engine.last_errors` (`bom_orchestrator.py:2481`) |

> 🔴 **Đề nghị Owner quyết trước khi làm**, vì đây là chạm luồng tính giá đang chạy
> production. Thay đổi ⛔ không lớn, nhưng **số ra phải được đối chiếu tay** trên một báo
> giá thật trước khi tin (xem mục 8 — bản rà này ⛔ **chưa** kiểm số ra).

---

## 7. Đề xuất

### 7.1 Việc nhỏ, làm được ngay

| Ưu tiên | Việc | Ước lượng |
|---|---|---|
| 1 | 🔴 #1 — bọc 10 ca test bảo mật vào lớp `TestCase` | Rất nhỏ, rủi ro ~0 |
| 2 | 🔴 #2 — Owner quyết: xoá gói mẫu chết, hoặc gắn cảnh báo | Nhỏ (cần Owner) |
| 3 | 🟢 #6 — gom `_build_trace` về một bản | Nhỏ |
| 4 | 🟡 #5 — ghi rõ khác biệt Python vào README | Rất nhỏ |

### 7.2 Việc lớn, cần job riêng

| Việc | Vì sao cần job riêng |
|---|---|
| 🟡 #4 — tách `b2_prefetch_master_data` (288 dòng) | Chạm luồng tính giá đang chạy production |
| 🟡 #3 — chuyển sang `child_tables` của Formula Builder | Đổi mô hình dữ liệu; phải đối chiếu số ra từng dòng |
| 🟡 #3 — dùng "lượt hai" của thư viện thay vì tự chia pha | Chạm cả B4 lẫn B6 |
| Chuyển `_build_trace` sang `explain_all()` | Đổi định dạng vết đang hiện trên UI |

⚠️ **Ba việc lớn trên đều chạm luồng tính giá đang chạy.** ⛔ Không gộp vào một job.

### 7.3 Việc ở mục 6 — thứ tự làm

| Ưu tiên | Việc | Vì sao |
|---|---|---|
| 1 | **Bọc 10 ca test** (🔴 #1) | Làm trước ⛔ không phải vì liên quan, mà vì **sửa engine mà ⛔ không có test thì ⛔ không có lưới** |
| 2 | Giữ engine ở **B4** (đã đúng kiểu `FormulaEngine`) | B4 ⛔ không phải đổi lớp, chỉ thêm cache — rủi ro thấp nhất |
| 3 | **B6**: bỏ lớp bọc + đổi `result.errors` → `engine.last_errors` | 1 dòng, nhưng **phải đối chiếu số ra tay** |
| 4 | Gom khoá cache về một chỗ (`(tên, công thức)` + tham số hành vi) | Sau khi 2 và 3 chạy ổn |
| 5 | Đo lại thời gian một lần tính BOM thật | ⛔ Chưa ai đo — xem mục 8 |

⛔ **Đừng làm 2 và 3 cùng lúc.** Mỗi bước phải đối chiếu số ra rồi mới sang bước sau.

---

## 8. Điều ⛔ chưa kiểm trong bản rà này

Ghi rõ để ⛔ không ai đọc thành "đã kiểm hết":

- **Ngoài phạm vi:** báo giá UI (`quotation.js`), `api/excel_io.py`, in ấn, `hooks.py`,
  `setup/seed_demo_data.py` — ⛔ chưa rà.
- **19 loại nguồn của Formula Builder:** AlumGlass chỉ đăng ký 2 — ⛔ không rà phần còn lại.
- **Số ra của luồng tính giá:** ⛔ **chưa** đối chiếu với **một báo giá thật đã biết giá đúng**.
  Bản rà này soi **mã**, rồi đối chiếu **trước/sau bản vá** (giống hệt — mục 9.4), nhưng
  "giống bản cũ" ⛔ **không** đồng nghĩa "đúng". Muốn chắc phải chạy một báo giá mẫu và so tay.
  *(AlumGlass ⛔ chưa cài trên site nào ⇒ ⛔ không có đường chạy end-to-end tại chỗ.)*
- **Chạy trên Python 3.14:** máy chỉ có 3.10.12.
- **Hiệu năng:** nay **đã đo** — xem mục 9.3. Nhưng vẫn là số **vi đo trên stub**, ⛔ không
  phải BOM thật có truy vấn DB (stub thay `frappe` bằng đối tượng giả). Cho biết **hướng và
  độ lớn tương đối**, ⛔ **không** phải hứa hẹn thời gian chạy production.
- **Bộ nhớ cache:** nay **đã đo** — xem mục 9.3. Đo **kích thước engine**, ⛔ chưa đo **RSS
  tiến trình** khi chạy nhiều worker cùng lúc.
- **`standalone_tests/test_phase_b_fbmax.py`:** nay **đã chạy** — 21 PASS / 7 FAIL, trùng khít
  danh sách lỗi nền trước bản vá (mục 9.4). 7 lỗi còn lại là **thiếu fixture**, ⛔ không phải
  lỗi do bản vá.

---

## 9. Bản vá đã viết (⛔ chưa commit)

Mục 6 là **đề xuất**; mục này là **bản đã viết**. Mọi số dưới đây đo lại trong lúc viết.

### 9.1 Đã đổi những gì

| Tệp | Thay đổi |
|---|---|
| `alumglass/engine/engine_cache.py` | **MỚI** — cache engine theo **vân tay nội dung công thức** |
| `engine/bom_orchestrator.py` → `b4_calculate_bom_items` | Bọc `FormulaEngine` vào cache — **B4 ⛔ không đổi lớp**, chỉ thêm cache |
| `engine/bom_orchestrator.py` → `b6_calculate_cost_template` | **Bỏ `FlexibleFormulaEngine`** → `FormulaEngine` + cache |
| `engine/bom_orchestrator.py` → `_engine_safe_funcs()` | **MỚI** — bộ `safe_funcs` dựng **một lần**, giữ nguyên `identity` (cache cần) |
| 5 docstring | Bỏ câu còn nói "dùng `FlexibleFormulaEngine`" — nay sai |

**Kết quả: đúng 2 lời gọi `calculate()` cho một BOM** — một ở B4 (Bom Items), một ở B6
(Cost Template). Đúng như mục 6.6 đề xuất.

**Khoá cache** (theo đúng mục 6.6 — ⛔ không dùng mã BOM):

```
(b4|b6) | vân tay blake2b của [(name, formula)…] | tên bộ hàm | on_error | default | deterministic
```

Vân tay **theo nội dung**, nên sửa công thức trong Bom Item ⇒ khoá đổi ⇒ **tự dựng engine
mới**. ⛔ Không cần ai nhớ xoá cache.

**Công tắc tắt** (nếu production có sự cố, ⛔ không phải sửa code):
`frappe.conf.alumglass_engine_cache = 0`. Cỡ cache: `alumglass_engine_cache_size` (mặc định 16).

### 9.2 🔴 Cái bẫy suýt làm giá sai **âm thầm** — ghi lại để ⛔ không ai vấp

Bỏ FFE ở B6 tưởng là đổi 1 dòng. Nhưng FFE tự trộn context:

```python
context = {**self.config.extra_context, **inputs}   # flexible_formula_engine.py:694
```

`extra_context` của B6 mang **`self.buckets`** cộng **giá trị 0 mặc định cho mọi mã bucket được
tham chiếu**. Nếu viết gọn theo phản xạ `engine.calculate(self.inputs)` thì:

- ⛔ **mất sạch bucket** ⇒ mọi thành phần giá theo bucket về 0
- ⛔ **không có exception nào** — `on_error="default"` nuốt êm, ra một con số **trông hợp lệ**
- ⇒ báo giá **thiếu tiền**, ⛔ không ai biết cho tới lúc đối chiếu tay

Bản vá giữ đúng hình dạng cũ: `result = engine.calculate({**extra_context, **self.inputs})`.
Trong code có khối ⛔ cảnh báo ngay trên dòng đó.

### 9.3 Số đo

**Tách bạch phần nào tốn thời gian** (như mục 6.5, đo trên engine trần):

| Bước | Thời gian | Chiếm |
|---|---|---|
| `FormulaEngine.__init__` | 2 018 µs | **97 %** |
| `calculate()` | 37 µs | 3 % |

⇒ **Giữ engine lại tiết kiệm 56,3×.** Đây là lý do tồn tại của `engine_cache.py`.

**Cả luồng B1→B6** (stub, 2 dòng vật tư):

| | Thời gian | |
|---|---|---|
| Cache nguội (dựng lại mỗi lần) | 0,59 ms | |
| Cache ấm | 0,20 ms | **2,88×** |

⚠️ 2,88× ⛔ **không** phải 56×. Vì cả luồng còn B1/B2/B3 (truy vấn, dựng công thức) — những
bước đó ⛔ **không** được cache. Nhỏ hơn 56× là **đúng**, ⛔ không phải cache hỏng.
Muốn ăn thêm thì phải cache B3 — xem 9.6.

**Bộ nhớ** (đo kích thước engine thật):

| Số công thức | Một engine |
|---|---|
| 50 | 175 KB |
| 250 | 429 KB |
| 400 | 607 KB |

`DEFAULT_MAXSIZE = 16` ⇒ khoảng **6–20 MB cho mỗi worker** (cả 2 cache). Chỉnh được bằng conf.

**Kiểm an toàn — bảng đối chứng:**

| Ca kiểm | Kết quả |
|---|---|
| ~~Cache BẬT vs TẮT, 3 context khác nhau~~ | 🔴 **RÚT LẠI — phép kiểm này VÔ CẢNG**, xem mục 10.1 |
| Cache BẬT vs TẮT, **200 context ngẫu nhiên** | ✅ **giống hệt từng byte** (mục 10.1 — đo lại cho đúng) |
| Đổi context xen kẽ (A→B→A) | ✅ ⛔ không lẫn số; quay lại A ra **y hệt** |
| Sửa công thức Bom Item | ✅ cache **tự vô hiệu** (1 200 000 → 2 400 000) |
| Vân tay phân biệt nội dung **và** tham số hành vi | ✅ |
| **FFE vs `FormulaEngine` trần** — A/B | ✅ **⛔ không đổi một số nào**, kể cả **nhánh lỗi** (cùng khoá lỗi, cùng thông báo, cùng giá) |

### 9.4 Lưới hồi quy

`standalone_tests/test_phase_b_fbmax.py` — **21 PASS / 7 FAIL**, ⛔ **trùng khít** danh sách lỗi
nền trước bản vá. 7 lỗi đó là **thiếu fixture** (`FakeDoc` thiếu `precision()`,
`meta.has_field()`, `calculate_taxes_and_totals()`…), ⛔ không liên quan bản vá.

⚠️ **Đây là lưới duy nhất chạy được.** Bộ `alumglass/tests/*.py` cần site thật — AlumGlass
⛔ chưa cài trên site nào. **Vì vậy 7 lỗi kia ⛔ phải được vá trước khi tin bản vá này**:
hiện chúng che đúng phần B4/B6 — tức đúng phần vừa sửa.

> 🔴 **Vẫn nguyên đề nghị ở mục 6.8:** số ra phải **đối chiếu tay trên một báo giá thật**
> trước khi tin. Bản vá này giữ số **giống hệt bản cũ** — nhưng "giống bản cũ" ⛔ không
> đồng nghĩa "đúng".

### 9.5 ⚠️ `child_tables` ⛔ **KHÔNG** được dùng cache này

`FormulaEngine` có **hai** đường nhận công thức:

| Đường | Có cache được? | Vì sao |
|---|---|---|
| `formulas=[{name, formula}…]` | ✅ **được** — khoá theo nội dung | công thức là **chuỗi**, thuần tuyên bố |
| `child_tables={…}` | ⛔ **KHÔNG** | `_inject_row_values` **nướng thẳng GIÁ TRỊ ô vào CHUỖI công thức** |

Nghĩa là cùng một bảng, dữ liệu đổi ⇒ **chuỗi công thức đổi** ⇒ vân tay đổi ⇒ hoặc cache
trượt vô ích, hoặc (nếu ai đó khoá theo *tên* bảng cho nhanh) **trả giá của dữ liệu cũ**.

🔴 **Nếu sau này chuyển B3 sang `child_tables` (đề xuất 🟡 #3) thì ⛔ phải bỏ cache ở B4/B6
hoặc đổi khoá sang khoá-theo-dữ-liệu.** Hai việc này ⛔ **xung đột nhau** — ghi ở đây để
⛔ không ai làm cái sau rồi tưởng cái trước vẫn còn nguyên.

### 9.6 ✅ Đã kiểm: Formula Builder **có** đóng gói phần dựng công thức

Câu hỏi đặt ra: *"phần dựng công thức chuẩn để ⛔ không phải viết py thuần lặp lại — tôi đã
đóng gói trong Formula Builder rồi"*. **Đúng một nửa** — và đúng ở nửa quan trọng hơn.

**✅ Nửa ĐÚNG — builder dựng lại được y hệt.** Chạy
`MultiTableFormulaBuilder(normalize_mode="global")` với `formula_fields=DEFAULT_FORMULA_FIELDS`
và một callback `synthetic_formulas` tự viết:

```
13 công thức b3  vs  13 công thức builder
  ✓ GIỐNG HỆT từng dòng, đúng thứ tự
```

Và cả **đường chuẩn hoá `items.X.Y`** cũng đã là đường của builder:

```
_normalize_items_ref("items.p1.width * 2")  →  "p1__width * 2"
normalize_global("items.p1.width * 2")       →  "p1__width * 2"     ✓ TRÙNG
```

Tức B3 **đã** đi đúng chuẩn hoá của thư viện. Đây là tin tốt: dữ liệu công thức của AlumGlass
⬜ **tương thích** builder, ⛔ không phải dạng đặc thù phải viết tay.

**🔴 Nửa ⛔ KHÔNG — hai giới hạn thật:**

**① `synthetic_for_pattern` có sẵn ⛔ KHÔNG dùng được — và hỏng theo kiểu im lặng.**

Builder sinh `lookup_calc_pattern(code, w, h, tlr, 1, 1, 1, 1)`. Nhưng chữ ký thật chỉ nhận
**5 tham số vị trí**:

```
TypeError: lookup_calc_pattern() takes from 1 to 5 positional arguments but 8 were given
```

Engine `on_error="default"` **nuốt lỗi này** ⇒ **mọi `line_total` = 0**, ⛔ không exception,
⛔ không cảnh báo. Đối chứng:

| Cách | Tổng `line_total` |
|---|---|
| B3 hiện tại | 2 400 000 |
| Builder + callback tự viết | 2 400 000 ✅ |
| Builder + `synthetic_for_pattern` | **0** 🔴 |

⇒ Phải tự viết callback (nó là **py thuần**, ⛔ không tránh được) — nhưng chỉ là một hàm nhỏ,
phần còn lại của builder vẫn dùng được.

**② `build()` trả về context RỖNG — builder ⛔ không chuẩn bị context.**

```
builder ctx :  0 khoá
orch.inputs : 21 khoá
```

Builder dựng **công thức**, ⛔ **không** dựng **context**. Điều này là **tất yếu**, ⛔ không
phải builder làm thiếu: context của AlumGlass đến từ **dữ liệu ERP** — `AL Material Category`
(`scrap_pct`), `AL Glass Master`, và `input_vars` của từng dòng (B2 prefetch). ⛔ Không thư
viện chung nào biết được schema đó. **Nên phần context ⛔ vẫn phải là py thuần** — đúng như
phương án dự phòng trong yêu cầu.

**Kết luận 9.6 — có nên đổi B3 sang builder ⛔ không?**

| | |
|---|---|
| Builder dựng lại được y hệt? | ✅ **Có** |
| Có **cần** đổi ⛔ không? | 🔴 **Không** — mục tiêu là *đúng + có cache*, mà **cache ⛔ không phụ thuộc** công thức do ai dựng |
| Đổi thì được gì? | Bớt một vòng lặp tay; nhưng mất đường `extra_items` (dict literal) — builder ⛔ **không** diễn đạt được, phải nhét vào callback ⇒ **lại là py thuần** |
| Rủi ro? | Chạm **luồng tính giá production** để đổi lấy **0 lợi ích chức năng** |

🔴 **Khuyến nghị: GIỮ B3 như hiện tại. ⛔ Đừng đổi.** Builder đã được chứng minh ⬜ **dùng
được** cho công việc **mới**; đổi lại B3 là refactor có rủi ro tiền bạc mà ⛔ không mua được gì.

### 9.7 Tình trạng

⛔ **Chưa commit, chưa push** — theo yêu cầu, để Owner tự review rồi commit.

| | |
|---|---|
| `engine_cache.py` | mới, `py_compile` OK |
| `bom_orchestrator.py` | sửa 4 chỗ + 5 docstring, `py_compile` OK |
| Lưới hồi quy | 21 PASS / 7 FAIL — **giống hệt nền** |
| Việc còn lại trước khi tin | 🔴 vá 7 fixture (9.4) · 🔴 đối chiếu tay 1 báo giá thật |

---

## 10. Kiểm TÍNH CHÍNH XÁC (⛔ không phải "giống bản cũ")

Mục 9 mới chứng minh bản vá **⛔ không đổi số**. Đó ⛔ **chưa phải** bằng chứng **đúng** —
giống bản cũ chỉ có nghĩa là *kế thừa nguyên cả cái đúng lẫn cái sai*. Mục này kiểm bằng
**oracle độc lập**: tính tay từ công thức gốc, rồi so với số engine trả.

### 10.1 🔴 Phép kiểm "cache BẬT vs TẮT" ở mục 9.3 là **VÔ CẢNG** — đã bắt được

**Kể lại vì đây là loại lỗi nguy hiểm nhất — lỗi *im lặng* trong chính phép kiểm.**

Phép kiểm cũ chạy 2 lượt, một lượt đặt `frappe.conf["alumglass_engine_cache"] = 0`, rồi so
kết quả. Hai lượt ra **giống hệt** ⇒ tôi kết luận "cache ⛔ không đổi số". **Sai.** Lý do:

```python
import frappe
frappe.conf["alumglass_engine_cache"] = 0   # ← ghi vào module frappe THẬT
```

Nhưng bộ test thay `sys.modules["frappe"]` bằng **module giả `FakeFrappe`**. Nên:
- dòng trên ghi vào module **thật** — ⛔ không ai đọc
- `engine_cache.cache_enabled()` đọc `sys.modules["frappe"]` = **stub**
- stub **⛔ không có field `conf`** ⇒ `getattr(frappe, "conf", None)` → `None`
  ⇒ `cache_enabled()` **luôn trả `True`**

⇒ Cả hai lượt đều chạy **cache BẬT**. Phép kiểm so **BẬT với BẬT** rồi báo "⛔ không khác
nhau" — một kết luận **⛔ không rút ra được từ dữ liệu thu được.**

🔴 **Dấu vết lẽ ra phải thấy:** lượt "TẮT" vẫn ghi `hits` tăng. Nhưng bộ đếm `_STATS` là biến
cấp module **cộng dồn suốt đời tiến trình**, và `clear_engine_caches()` khi đó ⛔ **không reset
nó** ⇒ số đọc ra là **số luỹ kế của cả 2 lượt**, che mất dấu vết. Hai lỗi cộng lại thành một
kết luận sai ⛔ không thể phát hiện bằng mắt.

**Đã sửa 2 chỗ:**

| Chỗ | Sửa |
|---|---|
| `standalone_tests/test_phase_b_fbmax.py` — `FakeFrappe` | Thêm `self.conf = {}` ⇒ công tắc **kiểm được**, ⛔ không còn luôn-True |
| `engine_cache.clear_engine_caches()` | Nay **reset cả `_STATS`** (thêm `reset_engine_cache_stats()`, có khoá) |

**Đo lại cho đúng — 200 context ngẫu nhiên, cùng tập công thức:**

| | `hits` | `misses` | `builds` |
|---|---|---|---|
| Cache **BẬT** | 398 | 2 | 2 |
| Cache **TẮT** | **0** | 0 | **400** |

⇒ Công tắc **cắt thật** (400 lượt tra đều dựng mới). Và **200/200 context cho kết quả giống
hệt từng byte** — lần này là bằng chứng thật.

**Đối chứng dương** (bắt buộc — ⛔ không có nó thì "giống hệt" ⛔ không chứng minh được gì):

| | |
|---|---|
| Số `GIA_VAT` **khác nhau** trên 200 context | **13 giá trị** ⇒ phép kiểm *có* phân biệt được |
| Đột biến 1 công thức ×5 | 1 200 000 → **6 000 000** ⇒ ⛔ không vô cảm |

✅ **Công tắc tắt cache — kiểm đủ 7 dạng giá trị:**

| `frappe.conf.alumglass_engine_cache` | `cache_enabled()` |
|---|---|
| (không đặt) · `1` · `"true"` | `True` |
| `0` · `"0"` · `"false"` · `"off"` · `""` | `False` |

### 10.2 Oracle tính tay — 32/32 ĐÚNG

Tính tay từ công thức gốc trong `formula_handlers.PATTERN_FORMULAS`
(`AREA` = `(w/1000)*(h/1000)`, `LENGTH_ONLY` = `w/1000`), rồi so từng số:

| Số | Tính tay | Engine |
|---|---|---|
| `kinh_tren.unit_qty` | AREA(2000,1000) = **2,0** | 2,0 ✅ |
| `kinh_tren.total_qty` | 2,0 × 2 = **4,0** | 4,0 ✅ |
| `kinh_tren.line_total` | 4 × 300 000 = **1 200 000** | 1 200 000 ✅ |
| `vien_nhom.unit_qty` | LENGTH_ONLY(2500) = **2,5** | 2,5 ✅ |
| `vien_nhom.total_qty` | 2,5 × 4 = **10,0** | 10,0 ✅ |
| `vien_nhom.line_total` | 10 × 120 000 = **1 200 000** | 1 200 000 ✅ |
| bucket `VL_KINH` / `VL_NHOM` | 1 200 000 / 1 200 000 | ✅ |
| `TONG_VL` | 1,2M + 1,2M = **2 400 000** | ✅ |
| `TONG_NC` / `TONG_OH` | **0** (bucket rỗng, phải default 0) | ✅ |
| `GIA_THANH` | 2,4M + 0 + 0 = **2 400 000** | ✅ |
| `GIA_BAN` | 2,4M × 1,2 = **2 880 000** | ✅ |
| `GIA_VAT` | 2,88M × 0,1 = **288 000** | ✅ |

🔴 **`TONG_NC` / `TONG_OH` là phép kiểm quan trọng nhất trong bảng** — hai bucket này ⛔ **không
dòng BOM nào sinh ra**, chúng tồn tại **chỉ nhờ** `extra_context` tự điền 0. Đây đúng là chỗ
bẫy ở mục 9.2. Nếu bản vá viết gọn `engine.calculate(self.inputs)`, hai số này sẽ **NameError
bị nuốt** ⇒ `GIA_THANH` sai. Oracle chốt được điều đó.

**Bật hao hụt cắt (`apply_scrap_pct=1`):**

| Số | Tính tay | Engine |
|---|---|---|
| `kinh_tren.total_qty` (scrap 0,03 %) | 4 × (1+0,0003) = **4,0012** | 4,0012 ✅ |
| `kinh_tren.line_total` | 4,0012 × 300 000 = **1 200 360** | 1 200 360 ✅ |
| `vien_nhom.line_total` | 10,002 × 120 000 = **1 200 240** | 1 200 240 ✅ |
| `GIA_VAT` lan theo | **288 072** | 288 072 ✅ |

**Cô lập lỗi** — chèn 1 công thức tham chiếu biến ⛔ không tồn tại:

| | |
|---|---|
| 2 dòng TỐT vẫn đúng | ✅ 1 200 000 / 1 200 000 |
| Lỗi **được ghi lại** | ✅ `name 'bien_khong_ton_tai' is not defined` |
| Cả BOM ⛔ không chết | ✅ |

### 10.3 Bản gốc vs bản vá — so **lý do lỗi**, ⛔ không chỉ tên

Chạy **cùng bộ test** trên **bản sao** `/tmp/ab` chứa orchestrator **nguyên bản từ HEAD**
(cây làm việc ⛔ không bị đụng):

```
BẢN GỐC : 21 PASS / 7 FAIL
BẢN VÁ  : 21 PASS / 7 FAIL
diff lý do lỗi (sau khi bỏ số dòng): RỖNG
```

**7 lỗi đó ⛔ không phải do bản vá.** Và quan trọng hơn — **chúng ⛔ không nằm ở phần TÍNH**.
Chạy riêng từng test để lấy **khung sản phẩm** (⛔ không phải khung `throw` của stub):

| Test | Hỏng ở đâu | Loại |
|---|---|---|
| `test_b6_full_flow_gia_vat` | `bom_orchestrator.py:2636` `b7_save_results` → `:2688` `_recalculate_quotation_totals` | **b7 LƯU**, ⛔ không phải B6 tính |
| `test_b5_full_flow_errors_captured_and_result_ok` | y hệt — `b7_save_results` | **b7 LƯU** |
| `test_b4_full_b3_nested_items_and_formulas` | `glass_thick == 6` | **fixture tự mâu thuẫn** (mục 9.4) |

✅ **Hệ quả quan trọng — 3 phép kiểm GIÁ VÀNG của bộ test vẫn ĐẠT.** `test_b6_full_flow_gia_vat`
hỏng ở **dòng 843** (`orch.b7_save_results()`), tức **SAU** dòng 834
(`assert orch.gia_vat == EXPECTED_GIA_VAT`). Chạy đúng phần tính (b0→b6), dừng trước b7:

| Phép kiểm giá vàng | Kết quả |
|---|---|
| `orch.gia_vat == 288 000` | ✅ **ĐẠT** |
| `orch.cost_engine_errors == {}` | ✅ **ĐẠT** |
| `cost_result["GIA_BAN"] == 2 880 000` | ✅ **ĐẠT** |

🔴 **Nhưng phát hiện kèm theo — `b7_save_results()` ⛔ KHÔNG được lưới phủ.** Đây là bước
**ghi giá ra Quotation Item** (`set_value al_gia_vat / al_gia_ban / al_bom_result`). Cả 2 test
chạm tới nó đều chết ở stub ⇒ **bước cuối cùng của luồng tính giá chưa từng được kiểm tự động.**
Bản vá này ⛔ **không** chạm `b7`, nhưng đây là **lỗ hổng lưới thật** cần job riêng.

### 10.4 🔴 Phát hiện MỚI (có sẵn từ trước, ⛔ không do bản vá): `show_condition` **tính mà ⛔ không ai dùng**

Fixture có `show_condition = items.kinh_tren.glass_thick > 0`, và `glass_thick = 0`
⇒ điều kiện **False**. **Nhưng dòng đó vẫn bị tính 1 200 000 vào giá.**

Grep **toàn app** (mọi loại tệp, trừ docs):

| Nơi | Vai trò |
|---|---|
| `al_bom_item.py` / `al_bom_set.py` | khai tên field, **validate cú pháp** |
| `bom_orchestrator.py:239` | đưa vào `DEFAULT_FORMULA_FIELDS` ⇒ **sinh công thức** |
| `formula_setup.js:192` | liệt kê cho trình soạn công thức |
| `HUONG_DAN_FORMULA.md`, `v28.md`, … | mô tả: *"Công thức FB — ẩn/hiện dòng"* |

⛔ **KHÔNG một dòng mã nào** đọc giá trị `{slug}__show_condition` đã tính để **ẩn dòng hoặc
cho `line_total` về 0**. Giá trị được tính ra rồi **nằm đó**.

⚠️ **Đây là câu hỏi về NGHIỆP VỤ, ⛔ không phải khẳng định lỗi.** Hai cách hiểu, ⛔ chưa
xác minh được cái nào:

1. **Là lỗi:** người dùng viết `glass_thick > 0` với ý "⛔ không có kính thì ⛔ không tính tiền
   kính" ⇒ hệ thống **vẫn thu 1 200 000** cho món ⛔ không tồn tại.
2. **⛔ Không phải lỗi:** `show_condition` chỉ để **ẩn/hiện dòng tham số trên giao diện**; muốn
   ⛔ không tính tiền thì người dùng đặt `qty = 0`.

🔴 **Cần Owner/BA chốt.** Nếu là (1) thì đây là lỗi **thu tiền sai** ⛔ không liên quan gì tới
bản vá này, và **phải là job riêng**.

### 10.5 🔴 Một chỗ fixture lệch chuẩn (chưa gây hại, nhưng dễ thành bẫy)

`AL Material Category.default_scrap_pct` khai là **Float**, mô tả ghi rõ *"VD: 3 = 3%"*,
và code chia 100 (`1 + scrap_pct/100`) — **khớp hợp đồng** ✅.

Nhưng fixture test đặt `{"name": "VL_KINH", "default_scrap_pct": 0.03}` ⇒ theo hợp đồng đó
nghĩa là **0,03 %**, ⛔ không phải 3 %. Hiện **chưa gây hại** vì `AL Bom Set` trong fixture
⛔ không bật `apply_scrap_pct` — giá trị chỉ nằm trong context, ⛔ không được nhân vào.
Nhưng ai bật cờ lên để test hao hụt sẽ đo nhầm hệ số **100 lần**.

### 10.6 Kết luận mục 10

| Câu hỏi | Trả lời |
|---|---|
| Bản vá có đổi số ⛔ không? | ⛔ **Không** — 21/7 y hệt, lý do lỗi y hệt từng chữ |
| Số engine trả có **đúng** ⛔ không? | ✅ **Đúng 32/32** so với tính tay từ công thức gốc |
| Cache có ⛔ làm sai số ⛔ không? | ⛔ **Không** — 200/200 context giống hệt từng byte, **đo lại cho đúng** sau khi vá công tắc |
| Công tắc tắt cache có chạy? | ✅ **Có** — sau khi vá stub; kiểm đủ 7 dạng giá trị |
| 1 dòng lỗi có giết cả BOM? | ⛔ **Không** — dòng tốt vẫn đúng, lỗi được ghi lại |
| Còn gì ⛔ chưa chứng minh? | 🔴 **Số đúng trên BOM THẬT** — xem 10.7 |

### 10.7 ⚠️ Điều mục 10 ⛔ **vẫn chưa** chứng minh

Oracle chạy trên **stub**, với **2 dòng vật tư** và công thức do fixture đặt. Nó chứng minh
**đường tính đúng**, ⛔ **không** chứng minh **dữ liệu công thức thật của khách đúng**.

- 🔴 **Vẫn ⛔ chưa đối chiếu một báo giá thật** đã biết giá đúng. AlumGlass ⛔ chưa cài trên
  site nào ⇒ ⛔ không có đường chạy end-to-end.
- 🟡 **7 fixture còn lỗi** (10.3). Nay đã rõ chúng **⛔ không nằm ở phần tính**: 2 cái chết ở
  `b7_save_results` (**sau** khi giá đã tính đúng), 1 cái do fixture `glass_thick` tự mâu thuẫn,
  4 cái thuộc B1/B2/B6-API. ⇒ Phần **B4/B5/B6 tính** ✅ **được phủ** (3 phép kiểm giá vàng đều ĐẠT).
  🔴 Nhưng **`b7_save_results` — bước GHI giá ra Quotation — thì ⛔ KHÔNG** được phủ (10.3).
- 🔴 **`show_condition` (10.4)** — cần chốt nghiệp vụ.
- ⛔ **Chưa** chạy Python 3.14 (máy chỉ có 3.10.12).
