# PHƯƠNG ÁN GIÁ THÀNH 3 LỚP — BÁO GIÁ · ĐỊNH MỨC REALTIME · THỰC TẾ KẾ TOÁN

> **Phạm vi:** thiết kế cho `lengoc1490/AlumGlass` (commit `dab66d0`) chạy trên Frappe/ERPNext, tận dụng core (Sales, Manufacturing, Stock, Buying, Accounts, Projects) và Formula Builder.
> **Cách làm:** đọc code repo (engine `BomOrchestrator`, `AL Cost Bucket`, `AL Cost Template`, `ConfigSnapshot`, các DocType sản xuất/kế toán đã có, `custom_fields.py`, `hooks.py`). Phần ERPNext core được mô tả theo hiểu biết về các DocType chuẩn; **những điểm phụ thuộc phiên bản tôi đánh dấu ⚠ "cần xác minh"** vì chưa chạy trên site của bạn.
> **Đây là tài liệu thiết kế**, chưa có code. Các tên DocType/field mới (`AL Cost Profile`, `AL Cost Plan`…) là **đề xuất**. Ví dụ ở §9 là số minh hoạ tự dựng (không phải dữ liệu thật), được sinh bằng script nên các tổng đều khớp.

---

## MỤC LỤC

1. [Bài toán & nguyên tắc thiết kế](#1-bài-toán--nguyên-tắc-thiết-kế)
2. [Hiện trạng: tận dụng gì, thiếu gì](#2-hiện-trạng-tận-dụng-gì-thiếu-gì)
3. [Kiến trúc tổng thể](#3-kiến-trúc-tổng-thể)
4. [Mô hình dữ liệu đề xuất](#4-mô-hình-dữ-liệu-đề-xuất)
5. [Lớp Q & S — giá bán và giá thành định mức dùng chung một engine](#5-lớp-q--s--giá-bán-và-giá-thành-định-mức-dùng-chung-một-engine)
6. [Lớp A — chi phí thực tế kế toán](#6-lớp-a--chi-phí-thực-tế-kế-toán)
7. [Mapping & so sánh 3 lớp](#7-mapping--so-sánh-3-lớp)
8. [Cấu hình bằng Formula Builder](#8-cấu-hình-bằng-formula-builder)
9. [Ví dụ chi tiết (số liệu minh hoạ)](#9-ví-dụ-chi-tiết-số-liệu-minh-hoạ)
10. [Báo cáo, dashboard, phân quyền, kiểm soát](#10-báo-cáo-dashboard-phân-quyền-kiểm-soát)
11. [Lộ trình, rủi ro, quyết định cần chốt](#11-lộ-trình-rủi-ro-quyết-định-cần-chốt)

---

## 1. BÀI TOÁN & NGUYÊN TẮC THIẾT KẾ

### 1.1 Ba lớp giá cần đối chiếu

| Lớp | Tên | Câu hỏi trả lời | Đơn vị dữ liệu | Thời điểm |
|-----|-----|-----------------|----------------|-----------|
| **Q** | Giá bán theo báo giá | "Bán bao nhiêu để có lãi?" | từng dòng Quotation Item | lúc báo giá, **đóng băng** khi Submit |
| **S** | Giá thành định mức (Standard) | "Làm ra sản phẩm này **dự kiến** tốn bao nhiêu? Cần mua gì, bao nhiêu?" | từng dòng Sales Order Item | **realtime**: tự tính lại khi giá/định mức đổi |
| **A** | Chi phí thực tế (Actual) | "Thực tế đã tốn bao nhiêu, ở tài khoản nào, bộ phận nào?" | chứng từ kế toán/kho/sản xuất | phát sinh theo thời gian, đóng kỳ |

### 1.2 Yêu cầu đối chiếu (từ đề bài)

1. Q ≠ S ≠ A là **bình thường** (ước lượng, có phát sinh ngoài kế hoạch) → hệ thống phải **so sánh được chứ không ép bằng nhau**.
2. **Kế toán** so theo **tài khoản/P&L**; **sản xuất, mua hàng, kinh doanh** so theo **Cost Bucket / nhóm báo cáo**; cùng một bộ số, nhiều góc nhìn.
3. Phải **mapping được** giữa các nhóm (bucket ↔ tài khoản ↔ dòng Cost Template ↔ bộ phận), **cấu hình linh hoạt**, không hard-code.
4. Tận dụng tối đa ERPNext core và engine tính giá Quotation sẵn có; công thức cấu hình bằng Formula Builder.

### 1.3 Sáu nguyên tắc

| # | Nguyên tắc | Ý nghĩa thực tế |
|---|------------|-----------------|
| P1 | **Một engine, nhiều profile** | Q và S dùng **cùng** `BomOrchestrator` (cùng BOM động, cùng công thức số lượng); khác nhau ở *nguồn giá, hao hụt, nhân công, cost template* → khai báo trong `AL Cost Profile`. Tránh hai bộ công thức lệch nhau |
| P2 | **Bucket là ngôn ngữ chung, Account là ngôn ngữ kế toán, Mapping là cầu nối** | Q/S sinh số theo **bucket**; A sinh số theo **tài khoản/chứng từ**; bảng mapping cấu hình (nhiều–nhiều, có tỷ trọng) đưa về cùng một lưới so sánh |
| P3 | **Gắn nhãn tại nguồn, không tạo sổ kép thứ hai** | Chi phí thực tế **đọc từ GL Entry / Stock Ledger / Job Card** của ERPNext (nguồn sự thật kế toán). Gắn `Project` + `Cost Bucket` (Accounting Dimension) tại chứng từ; collector chỉ **tổng hợp**, không ghi bút toán |
| P4 | **Mỗi lớp có snapshot bất biến** | Q: `ConfigSnapshot`; S: `AL Cost Plan` có revision + lưu **đầu vào đã resolve và dòng giá đã dùng**; A: `AL Cost Actual Snapshot` theo kỳ. Tái lập được "vì sao số này" |
| P5 | **Đầy đủ và khép kín** | Không để đồng chi phí nào "rơi mất": chi phí không map được vào bucket → vào bucket **`UNMAPPED`** (nhìn thấy ngay); tổng theo bucket **luôn bằng** tổng theo tài khoản (kiểm tra đóng, §7.4) |
| P6 | **Chênh lệch tính bằng công thức cấu hình** | Giá/lượng/hiệu suất, tỷ trọng phân bổ… đều là công thức Formula Builder, không phải code cứng |

---

## 2. HIỆN TRẠNG: TẬN DỤNG GÌ, THIẾU GÌ

### 2.1 ERPNext/Frappe core nên tận dụng

| Nhu cầu | Thành phần core | Dùng để |
|---------|-----------------|---------|
| Chuỗi bán hàng | Quotation → Sales Order → Delivery Note → Sales Invoice | mang `al_bom*`, `project` đi suốt; doanh thu thực tế |
| BOM & sản xuất | **BOM** (items, operations, scrap, `rm_cost_as_per`), **Work Order**, **Job Card** (time log), **Operation**, **Workstation** (`hour_rate`), **Production Plan** | thực thi sản xuất; nguồn giờ công/máy; ⚠ tên field tỷ lệ chi phí máy theo phiên bản |
| Tồn kho & giá vốn | **Stock Entry** (Material Transfer/Consumption for Manufacture, Manufacture; bảng `additional_costs`), **Stock Ledger Entry**, **Bin**, valuation (FIFO/Moving Average), **Landed Cost Voucher** | giá vốn vật tư thực xuất, cộng chi phí mua vào giá trị tồn |
| Mua hàng | Material Request → Purchase Order → Purchase Receipt → Purchase Invoice | kế hoạch mua từ S; giá mua thực tế |
| Kế toán | **Account**, **Cost Center**, **GL Entry**, **Journal Entry**, **Accounting Dimension**, **Period Closing**, báo cáo **Profit and Loss**/Trial Balance/General Ledger (lọc theo Project, Cost Center, Dimension) | nguồn sự thật cho lớp A; xem P&L theo tài khoản |
| Dự án | **Project** (liên kết chứng từ, `project` trên GL Entry) | gom chi phí theo công trình |
| Nền tảng Frappe | `doc_events`, `scheduler_events`, `frappe.enqueue`, `frappe.publish_realtime`, Script Report, Prepared Report, Workspace | tính lại realtime, job nền, báo cáo, dashboard |

> Với Manufacture Stock Entry, ERPNext cộng chi phí vận hành/`additional_costs` vào giá trị thành phẩm và ghi có tài khoản "Expenses Included In Valuation" (mặc định theo Company). ⚠ Cần xác minh trên phiên bản của bạn; cơ chế này là nền tảng cho phần "hấp thụ chi phí" ở §6.4.

### 2.2 Những gì AlumGlass đã có (đọc từ repo)

| Thành phần | Hiện trạng | Dùng cho phương án |
|-----------|-----------|--------------------|
| `BomOrchestrator` B0–B7 (~2.700 dòng) | tính BOM động → bucket → Cost Template → ghi `al_bom_result` | lõi lớp Q và S |
| **`AL Cost Bucket`** | `bucket_code`, `bucket_role` (LEAF/AGGREGATE), `parent_bucket`, `source_type`, `source_config`, **`default_expense_account` (Link Account)**, **`report_group`**, `batch_group`, `sort_order` | đã được thiết kế sẵn để **nối bucket với tài khoản** và gom nhóm báo cáo |
| **`AL Cost Template` / Item** | `line_code`, `calc_formula`, `cost_bucket`, `is_subtotal`, `is_final_price`, `is_pre_vat_price`, `show_on_quotation` | mẫu công thức giá bán (Q) và giá thành (S) |
| `ConfigSnapshot` | `inputs_json`, `result_json`, `bom_version`, `calculation_timestamp` (tạo lúc Submit Quotation) | snapshot lớp Q |
| `AL Cost Variance` | `project`, `cost_bucket`, `period_from/to`, `estimated_amount`, `actual_amount`, `variance_amount`, `variance_pct` | **khung** để mở rộng thành so sánh 3 lớp (hiện controller chỉ 7 dòng, chưa có logic) |
| `AL Project Profitability Snapshot` | `total_revenue`, `total_estimated_cost`, `total_actual_cost`, `gross_profit`, `cost_breakdown_json` | khung báo cáo lợi nhuận dự án (chưa có logic) |
| `AL Production Order Bridge` | `al_bom_version`, `work_order`, `status`, liên kết Cutting Plan nhôm/kính | cầu nối SO ↔ Work Order (cần mở rộng) |
| `AL Cutting Plan Aluminum/Glass`, `AL Cutting Standard` | `waste_pct`, `stock_bar_length_mm`, `saw_kerf_mm`, offcut tái sử dụng | nguồn **hao hụt thực tế** cho lớp S |
| `AL Material Plan` (+Item) | `required_qty`, `stock_qty`, `ordered_qty`, `shortfall_qty`, liên kết PO | kế hoạch mua vật tư (cần cấp số lượng từ S) |
| `AL Installation Cost Actual` | `cost_type`, `amount`, `reference_doctype/name` | nguồn chi phí lắp đặt thực tế |
| Custom field sẵn có | `Journal Entry`: `al_project`, **`al_cost_bucket`**, `al_change_order`; `Work Order`: `al_production_order_bridge`, `al_project`; `Purchase Order`: `al_project`, `al_material_plan`; `Stock Entry`: `al_project`, `al_installation_order` | điểm gắn nhãn sẵn có |
| Formula Builder | FormulaEngine (DAG), Formula Variable Binding, Global Variable, source types (`aggregate_from_items`…), cache engine theo công thức | cấu hình công thức/biến cho cả 3 lớp |

### 2.3 Khoảng trống đã tìm thấy (cần xử lý trước/trong dự án)

| # | Khoảng trống | Hệ quả | Hướng xử lý |
|---|--------------|--------|-------------|
| G1 | `custom_fields.py` có field cho **Quotation Item** nhưng **không có cho Sales Order Item** (`al_bom`, `al_bom_version`, `al_bom_vars`, `al_config_snapshot`…) | Khi tạo SO từ Quotation, ERPNext chỉ map field cùng tên có ở bảng đích → thông tin BOM động có thể **mất** ở SO; `AL Material Plan.aggregate_requirements` đọc `Sales Order Item.al_bom` sẽ rỗng. ⚠ cần xác minh trên site | thêm custom field cho Sales Order Item (và Work Order Item/Job Card nếu cần), có test "tạo SO từ Quotation giữ nguyên `al_bom*`" |
| G2 | `AL Material Plan.aggregate_requirements` cộng **`qty` thô** của dòng trong snapshot × SL | bỏ qua công thức chiều dài/diện tích, hao hụt → số lượng mua **sai** | lấy số lượng từ **AL Cost Plan** (đã gồm công thức + hao hụt), không đọc `qty` thô |
| G3 | `AL Cost Bucket.default_expense_account` chỉ **1 tài khoản/bucket** | không mô tả được "1 bucket ↔ nhiều tài khoản" hay "1 tài khoản ↔ nhiều bucket" (vd `OH_QLY` tách 627/642) | bảng mapping nhiều–nhiều có tỷ trọng (§7) |
| G4 | `Journal Entry.al_cost_bucket` là custom field ở **header** chứng từ | **không** đi vào `GL Entry` nên P&L theo tài khoản không lọc được theo bucket | dùng **Accounting Dimension** gắn lên chi tiết và GL Entry (§6.2) |
| G5 | `AL Cost Variance`, `AL Project Profitability Snapshot` mới là khung dữ liệu | chưa so sánh được | mở rộng theo §4 |
| G6 | Engine B7 **ghi thẳng vào Quotation Item** (`rate`, tổng Quotation) | không dùng lại được cho Sales Order/Cost Plan | tách *compute* khỏi *persist* (§5.2) |
| G7 | `ConfigSnapshot` chỉ lưu `al_bom_vars` + kết quả, không lưu đầu vào đã resolve/dòng Item Price đã chọn | không giải thích được vì sao S/Q lệch khi master data đổi | `AL Cost Plan` lưu `resolved_inputs` + `price_basis` (§5.5) |
| G8 | Lỗi công thức bị đổi thành 0, Submit không chặn | giá thành định mức có thể **thấp giả** | bật chế độ nghiêm ngặt cho profile S (không cho lưu Cost Plan nếu còn lỗi cứng) — xem `ALUMGLASS_REVIEW_TOAN_DIEN.md` F2 |

---

## 3. KIẾN TRÚC TỔNG THỂ

### 3.1 Ba lớp trên một "xương sống chi phí"

```
                       XƯƠNG SỐNG DÙNG CHUNG (khoá nối)
        Project · Sales Order Item · AL BOM Version · Cost Bucket · Cost Center
 ─────────────────────────────────────────────────────────────────────────────────
  LỚP Q (Quotation)        LỚP S (Standard / Định mức)      LỚP A (Actual / Thực tế)
  profile = QUOTATION      profile = STANDARD               nguồn = chứng từ ERPNext
  ┌───────────────┐        ┌──────────────────────┐         ┌─────────────────────────┐
  │BomOrchestrator│        │BomOrchestrator       │         │GL Entry (Project,       │
  │ giá bán        │       │ giá vốn/valuation    │         │  Cost Center, Dimension)│
  │ hao hụt %      │       │ hao hụt Cutting Plan │         │Stock Ledger / Stock Entry│
  │ NC = % VL      │       │ NC = giờ×đơn giá     │         │Job Card · PI · JE       │
  │ + lợi nhuận,VAT│       │ không lợi nhuận/VAT  │         │AL Installation Cost Act.│
  └──────┬────────┘        └──────────┬───────────┘         └──────────┬──────────────┘
         ▼                            ▼                                ▼
   ConfigSnapshot             AL Cost Plan (revision)        AL Cost Actual Snapshot (kỳ)
  (lúc Submit Quotation)     (realtime, lưu price_basis)      (collector, idempotent)
         └──────────────┬─────────────┴───────────────┬─────────────────┘
                        ▼                             ▼
              AL Cost Mapping Set  ───►  AL Cost Comparison (lưới Q·S·A)
          (bucket ↔ dòng template ↔ tài khoản ↔ bộ phận, tỷ trọng, công thức FB)
                        ▼
      Góc nhìn: Kế toán (tài khoản/P&L) · Sản xuất/Mua hàng (bucket, vật tư) · Quản lý (nhóm báo cáo)
```

### 3.2 Luồng chứng từ đầu–cuối và "ghi gì ở lớp nào"

| # | Sự kiện | Chứng từ ERPNext | Lớp Q | Lớp S (Cost Plan) | Lớp A (Cost Fact) |
|---|---------|------------------|-------|-------------------|-------------------|
| 1 | Báo giá | Quotation (+Item `al_bom*`) | tính giá, `al_bom_result` | (tuỳ chọn) Cost Plan **what-if** | — |
| 2 | Chốt báo giá | Quotation **Submit** | `ConfigSnapshot` đóng băng | — | — |
| 3 | Khách đặt hàng | Sales Order (kế thừa `al_bom*`, `project`) | tham chiếu | **tạo Cost Plan rev 1** | — |
| 4 | Lập kế hoạch | AL Material Plan, Material Request, Production Plan | — | cấp **số lượng gồm hao hụt**, giờ công | — |
| 5 | Mua vật tư | Purchase Order / Receipt / Invoice, Landed Cost | — | giá valuation cập nhật → **S tự tính lại** | giá mua thực tế (Cost Fact) |
| 6 | Thả sản xuất | **BOM vật liệu hoá** + Work Order (+ Bridge) | — | khoá rev "released" | — |
| 7 | Sản xuất | Stock Entry (Transfer/Consumption/Manufacture), Job Card | — | so sánh tiến độ | vật liệu, giờ công thực tế |
| 8 | Lắp đặt | AL Installation Order, Installation Cost Actual, PI/JE | — | — | chi phí lắp đặt, phát sinh |
| 9 | Giao hàng, xuất hoá đơn | Delivery Note, Sales Invoice | — | — | **doanh thu**, giá vốn ghi nhận |
| 10 | Cuối kỳ | **Cost Allocation Run** (JE phân bổ), Period Closing | — | — | chi phí chung phân bổ |
| 11 | Đối chiếu | **AL Cost Comparison** | Q | S | A + chênh lệch |

### 3.3 Hai hướng đi dữ liệu

- **Xuôi (kế hoạch):** `Quotation → ConfigSnapshot → Sales Order → Cost Plan → Material Plan/PO → BOM/Work Order`.
- **Ngược (thực tế):** `GL/Stock/Job Card → Cost Fact (gắn bucket, tài khoản, bộ phận) → Actual Snapshot → Comparison`.
  Hai hướng gặp nhau ở **lưới so sánh** theo khoá chung `(project, sales_order_item, bucket, account, cost_center, period)`.

---

## 4. MÔ HÌNH DỮ LIỆU ĐỀ XUẤT

> Tên là đề xuất; DocType hiện có được **mở rộng** thay vì tạo mới khi có thể (đánh dấu 🔧).

### 4.1 `AL Cost Profile` (mới) — "cách tính" của mỗi lớp

| Field | Kiểu | Ý nghĩa |
|-------|------|---------|
| `profile_code` | Data (unique) | `QUOTATION`, `STANDARD`, `STANDARD_QUICK`… |
| `layer` | Select `Q/S` | lớp mà profile phục vụ |
| `cost_template` | Link AL Cost Template | mẫu công thức giá bán/giá thành |
| `price_basis` | Select | `SELLING_PRICE_LIST` (hiện tại) · `BUYING_PRICE_LIST` · `VALUATION_RATE` · `LAST_PURCHASE_RATE` · `SUPPLIER_QUOTE` |
| `price_list` | Link Price List | khi dùng bảng giá |
| `include_landed_cost` | Check | có cộng chi phí mua (Landed Cost) vào giá định mức không |
| `scrap_mode` | Select | `CATEGORY_DEFAULT` (như báo giá) · `CUTTING_PLAN` · `FIXED_PCT` · `NONE` |
| `labor_mode` | Select | `PERCENT_OF_MATERIAL` · `OPERATIONS` (giờ × đơn giá Workstation/Operation) |
| `overhead_mode` | Select | `PERCENT` · `DRIVER_BASED` |
| `strict_errors` | Check | **không cho lưu** nếu còn lỗi cứng (thiếu giá, rule không khớp…) |
| `persist_target` | Select | `QUOTATION_ITEM` · `COST_PLAN` |
| `include_profit_vat` | Check | `true` cho Q, `false` cho S |

### 4.2 `AL Cost Plan` (mới) — giá thành định mức của một dòng Sales Order

Cha: `AL Cost Plan` (một bản ghi cho mỗi **Sales Order Item**, có `revision`).

| Field | Ý nghĩa |
|-------|---------|
| `sales_order`, `sales_order_item`, `project`, `item_code`, `qty` | khoá nối |
| `al_bom`, `al_bom_version`, `config_snapshot` | BOM đã ghim; tham chiếu `ConfigSnapshot` của báo giá (đối chiếu Q) |
| `cost_profile`, `revision`, `status` | `Draft/Active/Released/Superseded` |
| `calculated_on`, `trigger` | `SO_SUBMIT/PRICE_CHANGE/MANUAL/RELEASE` |
| `resolved_inputs` (JSON) | **toàn bộ biến đã resolve** (khắc phục G7) |
| `price_basis_json` (JSON) | mỗi vật tư: `item_code`, đơn giá, nguồn (Item Price name/valuation/PO), ngày |
| `errors_json` | lỗi/cảnh báo của engine |
| `total_cost`, `total_material`, `total_labor`, `total_overhead` | tổng hợp |
| **Bảng `lines`** (`AL Cost Plan Line`) | `slug`, `item_code`, `uom`, `net_qty`, `gross_qty` (gồm hao hụt), `scrap_pct`, `unit_price`, `amount`, `cost_bucket`, `warehouse` (tuỳ chọn); **index theo `item_code`** để tính lại nhanh khi giá đổi |
| **Bảng `buckets`** | `cost_bucket`, `amount` |
| **Bảng `template_lines`** | `line_code`, `value`, `trace` |
| **Bảng `operations`** | `operation`, `workstation`, `hours`, `rate`, `amount`, `cost_bucket` |

### 4.3 `AL Cost Mapping Set` (mới) + `AL Cost Mapping Rule`

Một **bộ mapping** áp cho một công ty/giai đoạn; gồm nhiều quy tắc.

| Field (Rule) | Ý nghĩa |
|--------------|---------|
| `rule_kind` | `TEMPLATE_LINE_TO_BUCKET` · `BUCKET_TO_ACCOUNT` · `ACCOUNT_TO_BUCKET` · `BUCKET_TO_REPORT_GROUP` · `BUCKET_TO_COST_CENTER` |
| `layer` | `Q/S/A/ALL` |
| `source_ref`, `target_ref` | mã nguồn/đích (line_code, bucket, Account, Cost Center, group) |
| `weight_pct` **hoặc** `weight_formula` | tỷ trọng cố định hoặc **công thức Formula Builder** (vd `OH_SX_SHARE`) |
| `pnl_section` | `COGS / SELLING / ADMIN / OTHER` |
| `sign` | `+1/−1` (vd thu hồi phế liệu ghi giảm) |
| `valid_from`, `valid_upto`, `priority` | hiệu lực theo thời gian, ưu tiên |
| `fact_basis` (cho A) | `GL_DEBIT`, `GL_CREDIT`, `GL_NET`, `STOCK_VALUE`, `JOB_CARD_HOURS×RATE` |

### 4.4 `AL Cost Actual Snapshot` (mới) + dòng "Cost Fact"

| Field | Ý nghĩa |
|-------|---------|
| `project`, `sales_order`, `period_from/to`, `mapping_set`, `generated_on`, `checksum` | khoá, để chạy **idempotent** (chạy lại không nhân đôi) |
| Dòng `AL Cost Fact` | `posting_date`, `sales_order_item` (nếu xác định được), `work_order`, `cost_bucket`, `account`, `cost_center`, `item_code`, `qty`, `uom`, `amount`, `fact_type` (`DIRECT/ABSORBED/ALLOCATED/VARIANCE`), `source_doctype`, `source_name`, `gl_entry` |

### 4.5 `AL Cost Comparison` 🔧 (mở rộng `AL Cost Variance`)

Lưới so sánh ở **grain** `(project, sales_order_item, cost_bucket, account, cost_center, period)`:

| Nhóm field | Nội dung |
|-----------|----------|
| Khoá | `project`, `sales_order`, `sales_order_item`, `cost_bucket`, `account`, `cost_center`, `report_group`, `period_from/to` |
| Số tiền | `q_amount`, `s_amount`, `a_amount` + `s_minus_q`, `a_minus_s`, `a_minus_q` + `%` |
| Số lượng | `q_qty`, `s_qty`, `a_qty` (vật tư/giờ công) |
| Phân tích | `price_variance`, `usage_variance`, `rate_variance`, `efficiency_variance`, `unplanned_flag` |
| Tham chiếu | `cost_plan`, `config_snapshot`, `actual_snapshot`, `mapping_set` |

`AL Project Profitability Snapshot` 🔧 thêm `layer_q_cost`, `layer_s_cost`, `layer_a_cost`, `revenue_q`, `revenue_a`, `margin_q/s/a`.

### 4.6 `AL Cost Allocation Rule` / `AL Cost Allocation Run` (mới)

Phân bổ **chi phí chung theo kỳ** (tiền lương gián tiếp, khấu hao, điện…) về dự án/Work Order theo **driver** (giờ công TT, m², % giá trị vật liệu…). Run sinh **Journal Entry** (có `Project`, Dimension bucket) và các `AL Cost Fact` loại `ALLOCATED`.

### 4.7 Mở rộng DocType/Custom Field hiện có 🔧

| Đối tượng | Thêm/sửa | Mục đích |
|-----------|----------|----------|
| **Sales Order Item** | `al_bom`, `al_bom_version`, `al_bom_vars`, `al_config_snapshot`, `al_cost_plan` | giữ BOM động qua SO (G1) |
| `AL Production Order Bridge` | `sales_order_item`, `al_cost_plan`, `erp_bom`, `released_revision` | nối SO ↔ Cost Plan ↔ BOM ↔ Work Order |
| **Accounting Dimension** | `AL Cost Bucket` (gắn lên mọi chứng từ kế toán/kho/mua) | gắn bucket vào **GL Entry** (G4). ⚠ fieldname sinh tự động có thể trùng custom field `Journal Entry.al_cost_bucket` hiện có → cần chiến lược đổi tên/migrate |
| `Stock Entry Detail`, `Purchase Invoice Item`, `Journal Entry Account` | kế thừa dimension bucket; hook tự gán bucket theo `Item → AL Material Category.default_cost_bucket` | gắn nhãn tự động, người dùng chỉ sửa khi ngoại lệ |
| `AL Cost Bucket` 🔧 | `bucket_type` (`MATERIAL/LABOR/OVERHEAD/UNPLANNED/RECOVERY`), `default_cost_center`, `pnl_section`; giữ `default_expense_account` làm mặc định | phân loại bucket |
| `Item` | `al_material_category` (đã có) → bucket mặc định | tự gán bucket |
| `Workstation`/`Operation` | `al_cost_bucket`, `al_labor_hour_rate` (nếu cần tách lương/máy) | NC theo giờ có bucket |

---

## 5. LỚP Q & S — GIÁ BÁN VÀ GIÁ THÀNH ĐỊNH MỨC DÙNG CHUNG MỘT ENGINE

### 5.1 Lớp Q (giữ nguyên, chuẩn hoá nhẹ)

- Vẫn là `BomOrchestrator` với profile `QUOTATION` (`price_basis = SELLING_PRICE_LIST`, `labor_mode = PERCENT_OF_MATERIAL`, có lợi nhuận/VAT).
- **Thay đổi tối thiểu:** (a) `Cost Template` đánh dấu `template_type = QUOTATION`; (b) mọi dòng Cost Template có `cost_bucket` rõ ràng để mapping; (c) lưu thêm vào `ConfigSnapshot` các **đầu vào đã resolve** (khắc phục G7); (d) kết quả Q là **hợp đồng chuẩn hoá** `QuoteCostResult {buckets, template_lines, lines, resolved_inputs, price_basis}`.

### 5.2 Điểm mở rộng của engine (tách *compute* khỏi *persist*)

Hiện B7 ghi `rate`, tổng Quotation. Đề xuất tách thành 3 tầng:

```python
# alumglass/engine/cost_engine.py  (đề xuất)
class CostContext:           # đầu vào đã chuẩn hoá của một dòng cần tính
    source_doctype: str      # "Quotation Item" | "Sales Order Item"
    source_name: str
    qty: float
    profile: CostProfile
    as_of: date

class CostResult:            # đầu ra thuần dữ liệu, không ghi DB
    lines: list; buckets: dict; template_values: dict; trace: dict
    resolved_inputs: dict; price_basis: dict; errors: dict

def compute(ctx: CostContext) -> CostResult:
    o = BomOrchestrator.from_context(ctx)      # B0..B6 như hiện tại
    o.price_resolver = make_price_resolver(ctx.profile)     # B2: chiến lược giá
    o.scrap_resolver = make_scrap_resolver(ctx.profile)     # B2/B3: chiến lược hao hụt
    o.cost_template  = ctx.profile.cost_template            # B6
    return o.run_compute_only()

def persist(result, ctx):   # B7 tách riêng
    {"QUOTATION_ITEM": persist_to_quotation_item,
     "COST_PLAN":      persist_to_cost_plan}[ctx.profile.persist_target](result, ctx)
```

Các điểm hiện có trong code phục vụ việc này: `_fetch_composite_prices` / `_fetch_composite_prices_via_fb` (B2 — giá), `row_literals[slug]["scrap_pct"]` (hao hụt theo category), `b6_calculate_cost_template` (template theo version hoặc override `_cost_template`), `_resolve_final_price` / `_resolve_pre_vat_price` (cờ trên Cost Template Item). Việc cần làm là **bọc chúng sau interface** chứ không viết lại.

### 5.3 Profile `STANDARD` khác `QUOTATION` ở điểm nào

| Hạng mục | `QUOTATION` | `STANDARD` | Thực hiện |
|----------|-------------|-----------|-----------|
| Nguồn giá vật tư | Item Price bảng **giá bán** (composite theo màu…) | **Valuation Rate** (hoặc giá mua gần nhất / bảng giá mua) | `PriceResolver` theo `price_basis`; vẫn dùng composite key cho biến thể màu nếu bảng giá mua có dimension |
| Landed cost | không | tuỳ `include_landed_cost` | cộng bình quân vào giá định mức |
| Hao hụt | `AL Material Category.default_scrap_pct` | **kết quả Cutting Plan** (`waste_pct`) hoặc định mức theo item group | `ScrapResolver` |
| Nhân công SX | `NC_SX_PCT × TONG_VL` | **Σ giờ Operation × đơn giá** | dòng `operations` của Cost Plan |
| Lắp đặt | `NC_LD_PCT × TONG_VL × hệ số rule` | số người × giờ × đơn giá đội (biến `INSTALL_*`) | công thức Cost Template |
| Chi phí chung | % | theo **driver** (m², giờ công TT) | `AL Cost Allocation Rule` cho tỷ lệ chuẩn |
| Lợi nhuận, VAT | có | **không** | Cost Template `STANDARD` không có dòng này |
| Lỗi | cảnh báo | **`strict_errors`**: không lưu nếu còn lỗi cứng | tránh giá thành thấp giả |

### 5.4 Nguồn dữ liệu của từng khối trong S

| Khối | Lấy từ | Ghi chú |
|------|--------|---------|
| Số lượng tịnh | công thức Bom Item (`width/height/qty`) + `lookup_calc_pattern` | **giống hệt** Q (một bộ công thức) |
| Hao hụt | `AL Cutting Plan Aluminum/Glass.waste_pct` của BOM Version/dự án; chưa có Cutting Plan → fallback `AL Cutting Standard`/category | khi Cutting Plan đổi → S tự đổi |
| Giá | `Bin`/`Item.valuation_rate` hoặc Item Price mua | chọn theo profile |
| Giờ công/máy | **BOM Operation** của Operation/Workstation hoặc bảng định mức riêng theo `Bom Set`/product type | bảng `operations` trong Cost Plan |
| Đơn giá giờ | `Workstation.hour_rate` (⚠ cấu phần lương/điện/thuê tuỳ phiên bản) hoặc biến FB | cấu hình bằng Formula Builder |
| Chi phí chung | tỷ lệ chuẩn từ `AL Cost Allocation Rule` / Global Variable | |

### 5.5 `AL Cost Plan` — vòng đời & tính lại **realtime**

**Khi nào tạo/tính lại (trigger):**

| Sự kiện | Hook | Hành động |
|---------|------|-----------|
| Sales Order **Submit** | `doc_events["Sales Order"]["on_submit"]` | tạo `AL Cost Plan` rev 1 cho từng dòng có `al_bom` |
| **Item Price** thay đổi | `Item Price` `on_update` | tìm Cost Plan **Active** chứa item (index `AL Cost Plan Line.item_code`) → đưa vào hàng đợi |
| Giá vốn đổi (nhập kho, Landed Cost, reposting) | `Stock Ledger Entry`/`Bin` | như trên (gộp theo item, **debounce** ~60 giây) |
| Cutting Plan đổi, Workstation/Operation đổi, Global Variable đổi | `on_update` tương ứng | đưa Cost Plan liên quan vào hàng đợi |
| Người dùng bấm "Tính lại" | nút trên Cost Plan/SO | tính ngay |
| Thả sản xuất | nút "Release" | khoá revision `Released` (làm cơ sở đo lường sản xuất) |

**Cơ chế:**
- Hàng đợi `frappe.enqueue(queue="short")` theo lô; engine đã có **cache theo vân tay công thức** nên mỗi dòng tính rất nhanh (thời gian chủ yếu là truy vấn giá).
- Chỉ tạo **revision mới** khi tổng đổi ≥ ngưỡng (vd 0,5% hoặc có lỗi→hết lỗi); còn lại cập nhật tại chỗ. Mọi revision lưu `resolved_inputs` + `price_basis_json` → trả lời được "vì sao S đổi".
- **Realtime UI:** `frappe.publish_realtime("al_cost_plan_updated", {...})` để dashboard/Sales Order tự làm mới.
- Có **cột "độ tươi"** (`calculated_on`, `price_as_of`) và cảnh báo khi Cost Plan lâu chưa tính lại.
- Cùng engine cho **what-if**: tính Cost Plan nháp trên Quotation Item (không ghi SO) để so S với Q ngay lúc báo giá.

### 5.6 Từ Cost Plan sang kế hoạch mua hàng & sản xuất

| Mục tiêu | Cách làm |
|----------|----------|
| **Kế hoạch vật tư** | `AL Material Plan.aggregate_requirements` đọc `AL Cost Plan Line.gross_qty` (đã gồm hao hụt) thay vì `qty` thô (xử lý G2); trừ tồn (`Bin`) và PO đang về → `shortfall_qty` → tạo Material Request/PO |
| **Vật liệu hoá BOM ERPNext** | khi "Release": tạo **BOM** ERPNext cho dòng SO (item thành phẩm = sản phẩm đại diện; `items` = `lines` của Cost Plan với `gross_qty`; `operations` = bảng `operations`; `rm_cost_as_per = Valuation Rate`) → gắn vào `AL Production Order Bridge.erp_bom`. Nhờ vậy dùng được Work Order/Production Plan/MRP native. ⚠ Tránh phình số BOM: chỉ tạo khi release, huỷ khi có revision mới chưa sản xuất |
| **Lệnh sản xuất** | Work Order từ BOM trên (`project`, `al_production_order_bridge` đã có) |
| **Năng lực** | tổng giờ Operation theo Workstation từ Cost Plan → lập lịch |
| **Đơn vị tính** | nhôm tính theo **kg** (UOM kho) nhưng thực tế cắt theo **cây** → cần quy ước UOM/chuyển đổi và `AL Cutting Plan` quy ra số cây; phế liệu cắt ghi vào `scrap_items` |

---

## 6. LỚP A — CHI PHÍ THỰC TẾ KẾ TOÁN

### 6.1 Ba nhóm nguồn thực tế

| Nhóm | Chứng từ | Cách đo | Gắn bucket bằng |
|------|----------|---------|-----------------|
| **Vật tư** | Stock Entry (Material Transfer/Consumption for Manufacture, Manufacture), Delivery Note, Purchase Receipt + Landed Cost | giá trị `Stock Ledger Entry` / `basic_amount` theo valuation | `Item → Material Category → bucket` (tự động) |
| **Nhân công & máy** | **Job Card** (time log), Salary Slip → JE | giờ thực tế × đơn giá (hấp thụ) và/hoặc phân bổ lương thực tế | `Operation/Workstation → bucket`; **Cost Allocation Run** |
| **Chi phí khác** | Purchase Invoice, Journal Entry, `AL Installation Cost Actual`, Expense Claim | số tiền dòng chi phí | `Expense Account → bucket` (mapping) hoặc người dùng chọn dimension; không map được → **`UNMAPPED`** |

### 6.2 Gắn nhãn tại nguồn (Project + Cost Bucket + Cost Center)

- **Project:** field chuẩn trên chứng từ/GL; bắt buộc với chứng từ thuộc dự án.
- **Cost Bucket:** tạo **Accounting Dimension** từ `AL Cost Bucket` → xuất hiện trên chứng từ và **GL Entry** → P&L/General Ledger lọc theo bucket (xử lý G4).
- **Cost Center:** cây theo **bộ phận** (Sản xuất, Lắp đặt, Kinh doanh, Quản lý…); `Workstation`, `Salary Structure/Employee` mặc định cost center.
- **Tự động gán:** hook `before_validate` trên `Stock Entry`, `Purchase Invoice/Receipt`, `Journal Entry`: nếu dòng chưa có bucket → suy từ item/account theo `AL Cost Mapping Rule`; ngoại lệ do người dùng sửa.
- **Chống sót:** bút toán có `Project` nhưng không suy được bucket → bucket `UNMAPPED` (hiện trên báo cáo, có nút "gán bucket").

### 6.3 Collector — tổng hợp chi phí thực tế (không ghi sổ)

```python
# alumglass/al_account/cost_collector.py  (đề xuất)
def collect_actuals(project, period_from, period_to, mapping_set):
    facts = []
    # (1) GL: mọi bút toán ghi nợ tài khoản chi phí/sản xuất dở dang của dự án
    gl = frappe.get_all("GL Entry",
        filters={"project": project, "is_cancelled": 0,
                 "posting_date": ["between", [period_from, period_to]]},
        fields=["name","posting_date","account","cost_center","debit","credit",
                "voucher_type","voucher_no","al_cost_bucket"])   # field dimension
    for g in gl:
        rule = mapping_set.match_account(g.account, g.voucher_type, g.al_cost_bucket)
        facts += rule.split(g)           # chia theo tỷ trọng (1 → nhiều bucket/tài khoản)
    # (2) Stock/Job Card để lấy SỐ LƯỢNG (kg, m², giờ) cho phân tích giá/lượng
    facts += collect_quantities(project, period_from, period_to)
    return upsert_snapshot(project, period_from, period_to, mapping_set, facts)  # idempotent
```

- **Idempotent:** snapshot khoá theo `(project, kỳ, mapping_set)` + `checksum` của tập GL; chạy lại thay thế, không nhân đôi. Khi có chứng từ lùi ngày/reposting → đánh dấu snapshot `Stale` và tính lại.
- **Đọc, không ghi:** collector không tạo bút toán; chỉ `Cost Allocation Run` mới tạo JE (phân bổ).
- **Hai chế độ:** *live* (tính khi mở báo cáo, dự án nhỏ) và *snapshot* theo kỳ (đóng kỳ, dự án lớn, dùng Prepared Report/job nền).

### 6.4 Hấp thụ vs. phân bổ: tránh đếm hai lần

| Loại chi phí | Cách ghi nhận thực tế | `fact_type` | Ghi chú |
|--------------|----------------------|-------------|---------|
| Vật tư | Stock Entry theo valuation | `DIRECT` | đã gồm Landed Cost |
| NC/máy sản xuất | **Hấp thụ**: Manufacture Entry cộng chi phí vận hành vào thành phẩm (đối ứng "Expenses Included In Valuation"); **thực tế** lương ở TK chi phí | `ABSORBED` (theo định mức) + `ALLOCATED` (lương thực tế phân bổ theo giờ Job Card) | chênh lệch = `VARIANCE` (rate/efficiency) |
| Chi phí chung SX | pool TK 627 theo kỳ → **Allocation Run** theo driver | `ALLOCATED` | ví dụ ở §9: 61,4 giờ × 31.000 |
| Chi phí bán hàng/quản lý | TK 641/642 | `DIRECT` hoặc `ALLOCATED` | là **chi phí kỳ**, không vào giá vốn (§7.5) |
| Phát sinh ngoài kế hoạch | PI/JE gắn project | `DIRECT`, bucket `KHAC` hoặc `UNMAPPED` | `unplanned_flag` nếu Q = S = 0 |
| Thu hồi (phế liệu) | bán phế liệu/Stock Entry scrap | `DIRECT`, dấu **âm** | bucket `SCRAP_REC` |

**Quy tắc chống trùng:** một đồng chi phí chỉ được tính **một lần** ở lớp A. Nếu dùng `ABSORBED` để so với định mức thì phần lương thực tế phải đi qua `ALLOCATED` *thay thế* (không cộng thêm); cấu hình bằng `fact_basis` trong mapping rule và kiểm tra đóng ở §7.4.

### 6.5 Doanh thu thực tế & giá vốn ghi nhận

- Doanh thu: `Sales Invoice` (net, trước VAT) theo `sales_order_item`.
- Giá vốn ghi nhận: GL của `Delivery Note` (TK giá vốn) — chỉ phần đã giao.
- **Cầu nối kỳ** (§9.7): `Chi phí thực tế tích luỹ = giá vốn ghi nhận + tồn kho thành phẩm + WIP + chi phí kỳ (bán hàng, quản lý)`.

---

## 7. MAPPING & SO SÁNH 3 LỚP

### 7.1 Vì sao cần mapping nhiều–nhiều

| Hiện tượng | Ví dụ |
|-----------|-------|
| 1 dòng Q → nhiều bucket/tài khoản | `OH_QLY` của báo giá gồm cả chi phí chung SX (627) lẫn quản lý (642) |
| 1 tài khoản → nhiều bucket | TK 621 gồm bucket nhôm, kính, vật tư phụ, phụ kiện |
| Bucket chỉ có ở S/A | `OH_SX` (S, A) không có trong báo giá; `KHAC`, `SCRAP_REC` chỉ có ở A |
| Khác thời điểm ghi nhận | vật tư xuất kho (A) nhưng chưa vào giá vốn vì chưa giao hàng |

### 7.2 Hai tầng mapping

1. **Tầng bucket (so sánh nội bộ):** `TEMPLATE_LINE_TO_BUCKET` đưa mọi dòng Cost Template (Q và S) về bucket chung; `ACCOUNT_TO_BUCKET` đưa chi phí kế toán về bucket.
2. **Tầng tài khoản (so sánh kế toán):** `BUCKET_TO_ACCOUNT` (có tỷ trọng, `pnl_section`) đưa số Q/S về tài khoản để đặt cạnh P&L.

Ví dụ cấu hình (minh hoạ; **tài khoản do bạn chọn**, ở đây theo VAS):

| Bucket | Tài khoản (tỷ trọng) | `pnl_section` | Cost Center mặc định |
|--------|---------------------|---------------|----------------------|
| `VL_NHOM`, `VL_KINH`, `VL_VTP`, `VL_PK` | 621 (100%) | COGS | Sản xuất |
| `SCRAP_REC` | 621 (100%, dấu −) | COGS | Sản xuất |
| `NC_SX` | 622 (100%) | COGS | Sản xuất |
| `NC_LD` | 622 (100%) | COGS | Lắp đặt |
| `OH_SX` | 627 (100%) | COGS | Sản xuất |
| `KHAC` | 627 (100%) | COGS | theo chứng từ |
| `OH_VC` | 641 (100%) | SELLING | Kinh doanh |
| `OH_QLY` — **lớp A, S** | 642 (100%) | ADMIN | Quản lý |
| `OH_QLY` — **lớp Q** | **627 (40%) + 642 (60%)** | COGS / ADMIN | — |

→ Tỷ trọng 40/60 chỉ áp cho lớp Q (vì báo giá gộp), có thể là **công thức FB** lấy từ lịch sử (vd tỷ lệ 627/(627+642) của 6 tháng gần nhất).

### 7.3 Thuật toán quy về lưới so sánh

```
Với mỗi nguồn (dòng Q, dòng S, Cost Fact A):
  1) bucket_weights  = match(TEMPLATE_LINE_TO_BUCKET | ACCOUNT_TO_BUCKET, layer)        # Σ trọng số = 100%
  2) account_weights = match(BUCKET_TO_ACCOUNT, bucket, layer, ngày hiệu lực)            # Σ trọng số = 100%
  3) với mỗi (bucket b, tài khoản a):  amount_ba = amount × w_bucket(b) × w_account(a|b) × sign
  4) bổ sung khoá: cost_center (từ mapping/chứng từ), report_group (từ bucket), sales_order_item (nếu có)
Cộng dồn theo grain  →  AL Cost Comparison.(q_amount | s_amount | a_amount)
```

### 7.4 Kiểm tra đóng (bắt buộc, chạy tự động)

| Kiểm tra | Điều kiện | Nếu sai |
|----------|-----------|---------|
| Trọng số | mỗi nguồn: Σ `weight_pct` = 100% | báo lỗi cấu hình mapping, **không** tạo comparison |
| Bảo toàn tiền | Σ lưới theo bucket = Σ lưới theo tài khoản = tổng nguồn (Q/S/A) | đánh dấu `Out of balance`, liệt kê dòng lệch |
| Phủ A | mọi GL Entry chi phí có `Project` đều nằm trong 1 bucket | phần còn lại vào `UNMAPPED` và **cảnh báo** |
| Trùng | một `gl_entry` chỉ xuất hiện 1 lần trong `AL Cost Fact` | loại bản trùng |
| Hiệu lực | rule còn hiệu lực theo `posting_date` | dùng rule ưu tiên cao nhất còn hiệu lực |

### 7.5 Giá thành sản phẩm ≠ chi phí kỳ: cầu nối với P&L

- **Giá thành sản xuất** (đối chiếu Q/S): vật tư + nhân công + chi phí chung SX (+ phát sinh gắn dự án).
- **Chi phí kỳ**: bán hàng (641), quản lý (642) — nằm ngoài giá vốn trong báo cáo kế toán nhưng **có trong giá bán báo giá** (`OH_VC`, `OH_QLY`).
- Vì vậy bảng so sánh có 2 mức: **"giá thành đầy đủ"** (như báo giá) và **"P&L kỳ"** (giá vốn ghi nhận, tồn kho, chi phí kỳ); `pnl_section` trong mapping quyết định khoản nào vào đâu. Ví dụ đầy đủ ở §9.7.

### 7.6 Bốn góc nhìn từ cùng một lưới

| Bộ phận | Chiều xem | Câu hỏi | Cột chính |
|---------|-----------|---------|-----------|
| **Kế toán** | `account` / `pnl_section` | "Chi phí 621/622/627… Q–S–A thế nào? Khớp P&L không?" | A so với GL/P&L; Q,S quy ra tài khoản bằng mapping |
| **Mua hàng/Kho** | `item_code`, bucket vật tư | "Giá mua và lượng dùng lệch gì?" | `price_variance`, `usage_variance`, `a_qty` vs `s_qty` |
| **Sản xuất** | bucket NC/OH, Operation, Workstation | "Giờ công, hiệu suất, phế liệu?" | `rate_variance`, `efficiency_variance`, giờ thực tế vs định mức |
| **Kinh doanh/BGĐ** | `report_group`, margin | "Báo giá có đủ lãi? Chỗ nào xói mòn biên?" | cầu nối lợi nhuận Q → A (§9.8) |

### 7.7 Phân tích chênh lệch (công thức)

| Loại | Công thức | Ý nghĩa |
|------|-----------|---------|
| Chênh lệch giá vật tư | `(A_giá − S_giá) × A_lượng` | mua đắt/rẻ hơn định mức |
| Chênh lệch lượng (hao hụt) | `(A_lượng − S_lượng) × S_giá` | dùng nhiều/ít hơn định mức |
| Chênh lệch đơn giá giờ | `(A_đơn giá giờ − S_đơn giá giờ) × A_giờ` | lương/tăng ca |
| Chênh lệch hiệu suất | `(A_giờ − S_giờ) × S_đơn giá giờ` | làm lâu/nhanh hơn |
| Chi phí ngoài kế hoạch | `A` khi `Q = S = 0` | `unplanned_flag` |
| Chênh lệch giá bán | `Doanh thu A − Doanh thu Q` | chiết khấu, change order |

Tổng hai thành phần của mỗi cặp **luôn bằng** chênh lệch bucket (kiểm tra đóng).

---

## 8. CẤU HÌNH BẰNG FORMULA BUILDER

> Các đoạn dưới là **ví dụ cấu hình minh hoạ**. Cấu trúc `source_config`/Binding cụ thể cần đối chiếu schema thực tế của Formula Variable Binding trong app Formula-Builder của bạn (⚠). Cú pháp công thức theo FormulaEngine hiện dùng trong `AL Cost Template`.

### 8.1 Cái gì cấu hình ở đâu

| Nội dung | Nơi cấu hình | Ví dụ |
|----------|-------------|-------|
| Hằng/biến toàn cục theo lớp | **Formula Global Variable** | `S_OH_SX_RATE`, `S_OH_QLY_PCT`, `INSTALL_CREW_RATE` |
| Biến lấy từ DB (giá vốn, giờ công, hao hụt) | **Formula Variable Binding** | `ALU_VALUATION`, `CUT_WASTE_PCT`, `OP_ASM_HOURS` |
| Công thức giá thành (S) | **AL Cost Template** `STANDARD` | `NC_SX = OP_CUT_COST + OP_ASM_COST + OP_GLZ_COST` |
| Quy tắc giá/lượng | **AL Cost Template** `VARIANCE` hoặc bảng `AL Cost Variance Rule` | `PRICE_VAR = (A_PRICE - S_PRICE) * A_QTY` |
| Tỷ trọng mapping | `weight_formula` trong `AL Cost Mapping Rule` | `OH_QLY_Q_TO_627 = SAFE_DIV(P627_6M, P627_6M + P642_6M)` |
| Driver phân bổ | `AL Cost Allocation Rule.driver_formula` | `DL_HOURS`, `M2_DELIVERED`, `DIRECT_MATERIAL_COST` |

### 8.2 Cost Template `STANDARD` (rút gọn)

| `line_code` | `calc_formula` | `cost_bucket` | Ghi chú |
|------------|----------------|---------------|---------|
| `TONG_VL` | `VL_NHOM + VL_KINH + VL_VTP + VL_PK` | — | bucket từ B5 (giá theo `STANDARD`) |
| `NC_SX` | `OP_CUT_HOURS*RATE_CUT + OP_ASM_HOURS*RATE_ASM + OP_GLZ_HOURS*RATE_GLZ` | `NC_SX` | giờ từ bảng `operations` |
| `NC_LD` | `INSTALL_CREW * INSTALL_HOURS * INSTALL_CREW_RATE * lookup_rule('RULE-HEIGHT-MULT', installation_height_m)` | `NC_LD` | dùng lại rule báo giá |
| `OH_VC` | `TONG_M2 * S_OH_VC_PER_M2` | `OH_VC` | driver m² |
| `OH_SX` | `DL_HOURS * S_OH_SX_RATE` | `OH_SX` | driver giờ công TT |
| `OH_QLY` | `S_OH_QLY_PCT * (TONG_VL + TONG_NC)` | `OH_QLY` | |
| `GIA_THANH` | `TONG_VL + TONG_NC + TONG_OH` | — | `is_final_price = 1` |

Không có `PROFIT`, `VAT`. Lưu ý: `TONG_M2`, `DL_HOURS`, `INSTALL_*` phải là biến có trong `inputs` (từ `al_bom_vars`, Operation hoặc Global Variable) — thiếu biến sẽ thành lỗi, nên profile `STANDARD` bật `strict_errors`.

### 8.3 Binding minh hoạ

```json
{
  "variable_name": "ALU_VALUATION",
  "source_type": "aggregate_from_items",
  "source_config": {
    "doctype": "Bin", "value_field": "valuation_rate",
    "filters": {"item_code": "{price_base_item}", "warehouse": "{{ default_warehouse }}"}
  },
  "applies_to_doctype": "AL Cost Plan"
}
```

*(Cấu trúc minh hoạ: nếu `aggregate_from_items` chưa hỗ trợ truy vấn Bin, dùng `doctype_query`/viết handler đăng ký `fb_source_types` theo mẫu `aluminum_price_composite` đang có trong `hooks.py`.)*

### 8.4 Quy tắc chênh lệch (dạng công thức)

| `rule_code` | `applies_to_bucket_type` | Công thức |
|-------------|--------------------------|-----------|
| `MAT_PRICE_VAR` | MATERIAL | `(A_AMOUNT / A_QTY - S_AMOUNT / S_QTY) * A_QTY` |
| `MAT_USAGE_VAR` | MATERIAL | `(A_QTY - S_QTY) * (S_AMOUNT / S_QTY)` |
| `LAB_RATE_VAR` | LABOR | `(A_AMOUNT / A_HOURS - S_AMOUNT / S_HOURS) * A_HOURS` |
| `LAB_EFF_VAR` | LABOR | `(A_HOURS - S_HOURS) * (S_AMOUNT / S_HOURS)` |
| `UNPLANNED` | ANY | `IF(AND(Q_AMOUNT = 0, S_AMOUNT = 0), A_AMOUNT, 0)` |

Mỗi rule chạy bằng `FormulaEngine` trên ngữ cảnh `{Q_*, S_*, A_*}` của một dòng lưới. Dùng `SAFE_DIV` để tránh chia 0 (nếu `S_QTY = 0` thì toàn bộ là `UNPLANNED`).

### 8.5 Vì sao cấu hình thay vì code

- Thêm bucket mới (vd `BAO_HANH`) = 1 record bucket + vài dòng mapping, **không sửa code**.
- Đổi cách tính chi phí chung (từ % sang theo m²) = đổi 1 dòng Cost Template `STANDARD` + biến.
- Đổi hệ thống tài khoản (VAS ↔ nội bộ) = đổi `AL Cost Mapping Set`, không đổi engine.
- Có thể tạo **nhiều profile S** (nhanh/chi tiết, theo nhà cung cấp) để so sánh kịch bản.

---

## 9. VÍ DỤ CHI TIẾT (SỐ LIỆU MINH HOẠ)

> Một Sales Order, 2 dòng hàng, đi qua cả 3 lớp: báo giá → định mức → thực tế, kèm mapping sang tài khoản và cầu nối P&L. Số liệu tự dựng để minh hoạ cơ chế (không phải dữ liệu thật); script sinh bảng đã kiểm tra mọi tổng đều khớp (Σ Cost Fact = giá thành A; Σ theo tài khoản = Σ theo bucket; cầu nối lợi nhuận cộng đúng).

### 9.1 Đề bài
**Sales Order `SO-2026-0042`**, dự án `P-HN-0042` (cùng khách), gồm 2 dòng hàng:

| Dòng | BOM động | Kích thước | SL | Ghi chú |
|---|---|---|---:|---|
| L1 | `CDMQ-2C` — cửa đi mở quay 2 cánh Xingfa 55 | 2400×2600 mm, `n_panel=2`, `installation_height_m=3` | 5 bộ | lắp cao 3 m |
| L2 | `VK-FIX` — vách kính cố định | 3000×2200 mm, `installation_height_m=4,5` | 2 bộ | lắp cao 4,5 m (hệ số rule 1,2) |

Bối cảnh thực tế của dự án (dùng ở §9.5 trở đi):
- Mua nhôm 2 lô: 250 kg × 108.000 và 146,2 kg × 112.500, cộng **Landed Cost** vận chuyển 1.950 đ/kg.
- Có **1 tấm kính vỡ khi lắp** (cắt bù 2,1 m²) và **cắt lại 1 thanh nhôm** → thêm giờ công cắt/lắp kính.
- Bán phế liệu nhôm 22,4 kg × 38.000.
- **Thuê cẩu 2.400.000 — không có trong báo giá.**
- Khách thương lượng giảm **1,5%** khi xuất hoá đơn.
- Cuối kỳ giao 5 bộ L1 + 1 bộ L2; còn **1 bộ L2 nằm kho thành phẩm** chưa giao.

### 9.2 Lớp Q — Giá bán theo báo giá (engine Quotation hiện có)
Tham số báo giá (Formula Global Variable / Product Type): hao hụt nhôm 20%, kính 5%; `NC_SX_PCT=8%`, `NC_LD_PCT=6%` × `RULE-HEIGHT-MULT`, `OH_VC_PCT=3%`, `OH_QLY_PCT=3%`, `PROFIT_MARGIN=16%`, `VAT_RATE=10%`.

**Dòng L1 — 1 bộ** (giá nhôm 113.000 đ/kg, kính 725.000 đ/m²):

| Dòng Cost Template | Công thức | Giá trị (đ) |
|---|---|---|
| `VL_NHOM` | 62,70 kg × (1+20%) × 113.000 = 75,24 kg × 113.000 | 8.502.120 |
| `VL_KINH` | 4,20 m² × (1+5%) × 725.000 = 4,41 m² × 725.000 | 3.197.250 |
| `VL_VTP` / `VL_PK` | Σ line_total của bucket | 600.000 / 1.640.000 |
| `TONG_VL` | tổng 4 bucket vật liệu | 13.939.370 |
| `NC_SX` | 8% × TONG_VL | 1.115.150 |
| `NC_LD` | 6% × TONG_VL × `lookup_rule('RULE-HEIGHT-MULT',3)`=1,0 | 836.362 |
| `OH_VC` | 3% × TONG_VL | 418.181 |
| `OH_QLY` | 3% × (TONG_VL + TONG_NC) | 476.726 |
| `GIA_THANH` | TONG_VL + TONG_NC + TONG_OH | 16.785.789 |
| `PROFIT` | 16% × GIA_THANH | 2.685.726 |
| `GIA_BAN` (`is_pre_vat_price`) | GIA_THANH + PROFIT | 19.471.516 |

**Tổng báo giá theo bucket** (L1×5 + L2×2):

| Bucket / dòng | L1 (1 bộ) | L2 (1 bộ) | Tổng SO (đ) |
|---|---:|---:|---:|
| VL_NHOM | 8.502.120 | 2.495.040 | 47.500.680 |
| VL_KINH | 3.197.250 | 4.435.200 | 24.856.650 |
| VL_VTP | 600.000 | 380.000 | 3.760.000 |
| VL_PK | 1.640.000 | 450.000 | 9.100.000 |
| NC_SX | 1.115.150 | 620.819 | 6.817.386 |
| NC_LD | 836.362 | 558.737 | 5.299.286 |
| OH_VC | 418.181 | 232.807 | 2.556.520 |
| OH_QLY | 476.726 | 268.194 | 2.920.020 |
| GIA_THANH | 16.785.789 | 9.440.798 | 102.810.542 |
| PROFIT | 2.685.726 | 1.510.528 | 16.449.687 |
| GIA_BAN | 19.471.516 | 10.951.325 | 119.260.229 |

→ Doanh thu theo báo giá (trước VAT) = **119.260.229 đ**; giá thành theo báo giá = **102.810.542 đ**; lợi nhuận kế hoạch = **16.449.687 đ**.

### 9.3 Lớp S — Giá thành định mức realtime (cùng BOM động, profile `STANDARD`)
Khác báo giá ở **5 điểm** (cấu hình trong `AL Cost Profile`, §5):

| # | Hạng mục | Báo giá (Q) | Định mức (S) |
|---|----------|-------------|--------------|
| 1 | Giá vật tư | Item Price bảng giá bán (113.000 đ/kg nhôm) | **Valuation Rate** bình quân (109.800 đ/kg), chưa gồm Landed Cost |
| 2 | Hao hụt | % theo Material Category (20% / 5%) | **Từ Cutting Plan** (nhôm 11,5% L1 / 8,0% L2; kính 3,8% / 3,0%) |
| 3 | Nhân công SX | 8% × TONG_VL | **Giờ công theo Operation × đơn giá Workstation** |
| 4 | Lắp đặt | 6% × TONG_VL × hệ số | **Số người × giờ × đơn giá đội** |
| 5 | Chi phí chung | OH_VC 3%, OH_QLY 3% | OH_VC theo m² giao; **OH_SX theo giờ công trực tiếp**; OH_QLY 2,5% |
| – | Lợi nhuận, VAT | có | **không có** (giá thành, không phải giá bán) |

**Dòng L1 — 1 bộ:**

| Dòng | Định mức | Giá trị (đ) |
|---|---|---|
| `VL_NHOM` | 62,70 kg × (1+11,5%) = 69,9105 kg × 109.800 | 7.676.173 |
| `VL_KINH` | 4,20 m² × (1+3,8%) = 4,3596 m² × 702.000 | 3.060.439 |
| `VL_VTP` / `VL_PK` | valuation × định mức | 575.000 / 1.598.000 |
| `NC_SX` | cắt 1,2h×95.000 + lắp ráp 5,0h×110.000 + lắp kính 2,4h×105.000 (tổng 8,6 giờ) | 916.000 |
| `NC_LD` | 2 người × 2,5h × 120.000 | 600.000 |
| `OH_VC` | 6,24 m² × 28.000 | 174.720 |
| `OH_SX` | 8,6 giờ công TT × 28.000 | 240.800 |
| `OH_QLY` | 2,5% × (VL + NC) | 360.640 |
| **Giá thành định mức** |  | 15.201.772 |

**Toàn SO** (L1×5 + L2×2): vật liệu 78.926.280 · nhân công 10.360.000 · chung 4.970.557 → **giá thành định mức = 94.256.837 đ**. Giờ công định mức: cắt 7,6 h, lắp ráp 29,8 h, lắp kính 16,0 h (**53,4 giờ**).

**Nhu cầu vật tư phục vụ mua hàng/kế hoạch** (qty **gồm hao hụt**, lấy từ Cost Plan, không phải số lượng tịnh): nhôm **389,30 kg**, kính **35,39 m²** (so với báo giá tính 420,36 kg / 35,91 m²).

### 9.4 Lớp A — Chi phí thực tế (các "Cost Fact" thu thập từ chứng từ ERPNext)

| Chứng từ nguồn | Bucket | TK | Nội dung | Số tiền (đ) |
|---|---|---|---|---:|
| PR-0101 (Purchase Receipt) | VL_NHOM | 621 | Nhập 250 kg × 108.000 | 27.000.000 |
| PR-0107 (Purchase Receipt) | VL_NHOM | 621 | Nhập 146,2 kg × 112.500 | 16.447.500 |
| LCV-0009 (Landed Cost Voucher) | VL_NHOM | 621 | Vận chuyển 1.950 đ × 396,2 kg | 772.590 |
| SE-0455 (Stock Entry – bán phế liệu) | SCRAP_REC | 621 | 22,4 kg × 38.000 (ghi giảm giá thành) | -851.200 |
| SE-0460.. (Material Transfer/Consumption) | VL_KINH | 621 | L1: 24,7 m² × 705.000 (có 2,1 m² cắt bù kính vỡ) | 17.413.500 |
| SE-0471.. (Material Consumption) | VL_KINH | 621 | L2: 14,0 m² × 622.000 | 8.708.000 |
| SE-0462.. (Consumption) | VL_VTP | 621 | Vật tư phụ thực xuất | 3.310.000 |
| SE-0463.. (Consumption) | VL_PK | 621 | Phụ kiện thực xuất (giá Draho tăng + 2 bản lề bổ sung) | 9.240.000 |
| JC-0210..0233 (Job Card × payroll) | NC_SX | 622 | Cắt 8,1h × 98.000 | 793.800 |
| JC-0210..0233 | NC_SX | 622 | Lắp ráp 33,9h × 118.000 (có tăng ca) | 4.000.200 |
| JC-0210..0233 | NC_SX | 622 | Lắp kính 19,4h × 112.000 (có làm lại) | 2.172.800 |
| AL-IC-0031 (AL Installation Cost Actual) | NC_LD | 622 | Nhân công đội lắp đặt | 5.100.000 |
| AL-IC-0032 | NC_LD | 622 | Đi lại – ăn ở | 640.000 |
| PI-3301 (Purchase Invoice – cước xe) | OH_VC | 641 | Vận chuyển giao hàng | 1.260.000 |
| JE-ALLOC-2026-10 (Cost Allocation Run) | OH_SX | 627 | Phân bổ CP chung SX: 61,4 giờ × 31.000 | 1.903.400 |
| JE-ALLOC-2026-10 | OH_QLY | 642 | Phân bổ CP quản lý | 2.150.000 |
| PI-3315 (Purchase Invoice – thuê cẩu) | KHAC | 627 | **Phát sinh ngoài báo giá** | 2.400.000 |

Σ Cost Fact = **102.460.590 đ** = giá thành thực tế của dự án (khớp `Ax`).

### 9.5 So sánh 3 lớp theo Cost Bucket (bộ phận sản xuất / mua hàng / quản lý)

| Bucket | Q báo giá | S định mức | A thực tế | A−S | % | A−Q | % |
|---|---:|---:|---:|---:|---:|---:|---:|
| `VL_NHOM` Nhôm | 47.500.680 | 42.744.756 | 44.220.090 | +1.475.334 | +3,5% | -3.280.590 | -6,9% |
| `VL_KINH` Kính | 24.856.650 | 23.704.524 | 26.121.500 | +2.416.976 | +10,2% | +1.264.850 | +5,1% |
| `VL_VTP` Vật tư phụ | 3.760.000 | 3.605.000 | 3.310.000 | -295.000 | -8,2% | -450.000 | -12,0% |
| `VL_PK` Phụ kiện | 9.100.000 | 8.872.000 | 9.240.000 | +368.000 | +4,1% | +140.000 | +1,5% |
| `SCRAP_REC` Thu hồi phế liệu | 0 | 0 | -851.200 | -851.200 | — | -851.200 | — |
| `NC_SX` Nhân công SX | 6.817.386 | 5.680.000 | 6.966.800 | +1.286.800 | +22,7% | +149.414 | +2,2% |
| `NC_LD` Nhân công lắp đặt | 5.299.286 | 4.680.000 | 5.740.000 | +1.060.000 | +22,6% | +440.714 | +8,3% |
| `OH_SX` CP chung SX | 0 | 1.495.200 | 1.903.400 | +408.200 | +27,3% | +1.903.400 | — |
| `OH_VC` Vận chuyển | 2.556.520 | 1.243.200 | 1.260.000 | +16.800 | +1,4% | -1.296.520 | -50,7% |
| `OH_QLY` Quản lý | 2.920.020 | 2.232.157 | 2.150.000 | -82.157 | -3,7% | -770.020 | -26,4% |
| `KHAC` Phát sinh ngoài báo giá | 0 | 0 | 2.400.000 | +2.400.000 | — | +2.400.000 | — |
| **Giá thành** | 102.810.542 | 94.256.837 | 102.460.590 | +8.203.753 | +8,7% | -349.952 | -0,3% |
| **Doanh thu (trước VAT)** | 119.260.229 | — | 117.471.325 | — | — | -1.788.903 | -1,5% |
| **Lợi nhuận gộp** | 16.449.687 | 25.003.392 ¹ | 15.010.735 | — | — | -1.438.952 | -8,7% |

¹ Lợi nhuận "kế hoạch thực" = doanh thu báo giá − giá thành định mức: cho biết biên lợi nhuận đang giấu trong ước lượng của báo giá.

**Đọc kết quả:**
- Tổng giá thành A (102.460.590) gần bằng Q (102.810.542) — **nhìn tổng thì "ổn"**, nhưng nhìn bucket thì vật liệu thấp hơn báo giá (+ thu hồi phế liệu) bù cho **nhân công, chi phí chung và khoản phát sinh** đang cao hơn.
- **`OH_SX`** không tồn tại trong báo giá (Q = 0): báo giá gộp vào `OH_QLY`. Phải **map nhiều–một** (xem §7) mới so sánh công bằng.
- **`KHAC` (thuê cẩu)**: Q = S = 0 ⇒ phát sinh 100% → cần cảnh báo "chi phí ngoài kế hoạch".
- Kính vượt định mức chủ yếu do **lượng** (2,9 m² cắt bù), không do giá.

### 9.6 Phân tích chênh lệch A − S (giá / lượng / hiệu suất)

| Hạng mục | Chênh lệch giá (rate) | Chênh lệch lượng/hiệu suất | Tổng A−S | Ghi chú |
|---|---:|---:|---:|---|
| Nhôm | +717.330 | +758.004 | +1.475.334 | giá thực 111.611 (gồm landed cost 1.950) vs định mức 109.800; lượng 396,2 vs 389,3 kg |
| Kính | +202.839 | +2.214.137 | +2.416.976 | lượng 38,7 vs 35,4 m² (kính vỡ + cắt bù) |
| NC cắt | +24.300 | +47.500 | +71.800 | 8,1h vs 7,6h; 98.000 vs 95.000 |
| NC lắp ráp | +271.200 | +451.000 | +722.200 | 33,9h vs 29,8h; 118.000 vs 110.000 (tăng ca) |
| NC lắp kính | +135.800 | +357.000 | +492.800 | 19,4h vs 16,0h (làm lại kính vỡ) |

Công thức (cấu hình bằng Formula Builder, §8): `PRICE_VAR = (A_PRICE − S_PRICE) × A_QTY`; `USAGE_VAR = (A_QTY − S_QTY) × S_PRICE`; `RATE_VAR = (A_RATE − S_RATE) × A_HOURS`; `EFFICIENCY_VAR = (A_HOURS − S_HOURS) × S_RATE`. Tổng 2 thành phần = chênh lệch bucket (kiểm tra đóng: nhôm +1.475.334 = +717.330 + +758.004).

### 9.7 So sánh theo tài khoản (P&L) — kế toán
Mapping bucket → tài khoản (ví dụ theo hệ thống tài khoản VAS; **tài khoản cụ thể do bạn cấu hình**, §7.2). Với báo giá, `OH_QLY` được **tách 40% → 627 / 60% → 642** theo trọng số mapping:

| Tài khoản | Nhóm P&L | Q | S | A | A−S | A−Q |
|---|---|---:|---:|---:|---:|---:|
| 621 Chi phí NVL trực tiếp | COGS | 85.217.330 | 78.926.280 | 82.040.390 | +3.114.110 | -3.176.940 |
| 622 Chi phí nhân công trực tiếp | COGS | 12.116.672 | 10.360.000 | 12.706.800 | +2.346.800 | +590.128 |
| 627 Chi phí sản xuất chung & dịch vụ mua ngoài | COGS | 1.168.008 | 1.495.200 | 4.303.400 | +2.808.200 | +3.135.392 |
| 641 Chi phí bán hàng (vận chuyển) | Bán hàng | 2.556.520 | 1.243.200 | 1.260.000 | +16.800 | -1.296.520 |
| 642 Chi phí quản lý doanh nghiệp | Quản lý | 1.752.012 | 2.232.157 | 2.150.000 | -82.157 | +397.988 |
| **Tổng** |  | 102.810.542 | 94.256.837 | 102.460.590 | +8.203.753 | -349.952 |

Tổng theo tài khoản **bằng** tổng theo bucket (102.460.590) — đây là **phép kiểm tra đóng** của bảng mapping (§7.4): mọi đồng chi phí đều thuộc đúng 1 bucket và đúng 1 tài khoản.

**Cầu nối sang P&L thực tế của kỳ** (chỉ lớp A; 5 bộ L1 + 1 bộ L2 đã giao, còn 1 bộ L2 nằm kho thành phẩm):

| Dòng | Số tiền (đ) | Giải thích |
|---|---:|---|
| Doanh thu ghi nhận (TK 511) | 106.684.270 | doanh thu SO sau giảm 1,5% × tỷ trọng đã giao (90,8%) |
| Giá vốn (TK 632) = COGS thực hiện | 89.531.163 | 621+622+627 = 99.050.590, trừ phần còn trong kho thành phẩm |
| **Lợi nhuận gộp** | 17.153.106 |  |
| CP bán hàng (641) | 1.260.000 | chi phí kỳ, không vào giá vốn |
| CP quản lý (642) | 2.150.000 | chi phí kỳ |
| **Lợi nhuận hoạt động** | 13.743.106 |  |
| *Tồn kho thành phẩm (TK 155)* | 9.519.427 | 1 bộ L2 chưa giao = 9,61% chi phí SX (theo tỷ trọng định mức) |
| *Kiểm tra*: COGS thực hiện + tồn FG + 641 + 642 | 102.460.590 | = tổng giá thành thực tế 102.460.590 ✔ |

### 9.8 Cầu nối lợi nhuận: Báo giá → Thực tế

| Bước | Cơ sở | Tác động lợi nhuận (đ) | Luỹ kế (đ) |
|---|---|---:|---:|
| Lợi nhuận gộp theo báo giá |  | 16.449.687 | 16.449.687 |
| Giảm giá khách (1,5%) | Q − A doanh thu | -1.788.903 | 14.660.783 |
| Nhôm | `VL_NHOM` A−Q | +3.280.590 | 17.941.373 |
| Kính | `VL_KINH` A−Q | -1.264.850 | 16.676.523 |
| Vật tư phụ | `VL_VTP` A−Q | +450.000 | 17.126.523 |
| Phụ kiện | `VL_PK` A−Q | -140.000 | 16.986.523 |
| Thu hồi phế liệu | `SCRAP_REC` A−Q | +851.200 | 17.837.723 |
| Nhân công SX | `NC_SX` A−Q | -149.414 | 17.688.310 |
| Nhân công lắp đặt | `NC_LD` A−Q | -440.714 | 17.247.595 |
| CP chung SX | `OH_SX` A−Q | -1.903.400 | 15.344.195 |
| Vận chuyển | `OH_VC` A−Q | +1.296.520 | 16.640.715 |
| Quản lý | `OH_QLY` A−Q | +770.020 | 17.410.735 |
| Phát sinh ngoài báo giá | `KHAC` A−Q | -2.400.000 | 15.010.735 |
| **Lợi nhuận gộp thực tế** |  | 15.010.735 | 15.010.735 |

Biên lợi nhuận gộp: báo giá **13,8%** → thực tế **12,8%** (thấp hơn 1,0 điểm %).

### 9.9 Hệ thống tạo ra các bảng trên như thế nào (vết mapping)

Ba ví dụ cụ thể áp thuật toán §7.3:

| Nguồn | Số tiền | Quy tắc mapping áp dụng | Kết quả vào lưới `(bucket, tài khoản, cost center)` |
|-------|---------|--------------------------|----------------------------------------------------|
| **Q** — dòng `OH_QLY` của báo giá (tổng SO) | 2.920.020 | `TEMPLATE_LINE_TO_BUCKET: OH_QLY → OH_QLY (100%)`; `BUCKET_TO_ACCOUNT` lớp Q: `OH_QLY → 627 (40%) + 642 (60%)` | `(OH_QLY, 627, Sản xuất)` = **1.168.008**; `(OH_QLY, 642, Quản lý)` = **1.752.012** |
| **S** — dòng `OH_SX` của Cost Plan | 1.495.200 | `OH_SX → OH_SX (100%)`; `OH_SX → 627 (100%)` | `(OH_SX, 627, Sản xuất)` = 1.495.200 |
| **A** — `PI-3315` thuê cẩu, chỉ có `Project`, **chưa gắn bucket** | 2.400.000 | `ACCOUNT_TO_BUCKET`: TK 627 + `voucher_type = Purchase Invoice` + chưa có dimension → `KHAC`. *Nếu không có rule này → bucket `UNMAPPED`* | `(KHAC, 627, theo chứng từ)` = 2.400.000, `unplanned_flag = 1` vì Q = S = 0 |

Một dòng của lưới `AL Cost Comparison` sau khi gộp (bucket `VL_NHOM`, tài khoản 621):

```json
{
  "project": "P-HN-0042", "cost_bucket": "VL_NHOM", "account": "621", "cost_center": "Sản xuất",
  "report_group": "Vật liệu",
  "q_amount": 47500680, "s_amount": 42744756, "a_amount": 44220090,
  "q_qty": 420.36, "s_qty": 389.2965, "a_qty": 396.2,
  "a_minus_s": 1475334, "a_minus_q": -3280590,
  "price_variance": 717330, "usage_variance": 758004, "unplanned_flag": 0
}
```

### 9.10 Công thức chênh lệch chạy bằng Formula Builder (dòng `VL_NHOM`)

Ngữ cảnh đầu vào: `S_AMOUNT = 42.744.756`, `S_QTY = 389,2965`, `A_AMOUNT = 44.220.090`, `A_QTY = 396,2`.

| Rule | Tính | Kết quả |
|------|------|--------:|
| `MAT_PRICE_VAR` | `(44.220.090/396,2 − 42.744.756/389,2965) × 396,2 = (111.610,5 − 109.800) × 396,2` | **717.330** |
| `MAT_USAGE_VAR` | `(396,2 − 389,2965) × 109.800` | **758.004** |
| Kiểm tra đóng | `717.330 + 758.004` so với `A_AMOUNT − S_AMOUNT = 1.475.334` | ✔ |

Đọc cho từng bộ phận: **Mua hàng** thấy giá thực cao hơn định mức 1.810 đ/kg (phần lớn do Landed Cost 1.950 đ/kg chưa nằm trong giá valuation định mức) → cân nhắc đặt `include_landed_cost = 1` cho profile S. **Sản xuất** thấy dùng nhiều hơn 6,9 kg → xem Cutting Plan (cắt lại 1 thanh) và 22,4 kg phế liệu đã bán thu hồi 851.200.

### 9.11 Ba điều ví dụ này cho thấy

1. **Tổng gần bằng nhau nhưng cấu trúc khác**: A − Q chỉ −0,3%, trong khi A − S là +8,7% — vì **báo giá đã "pha loãng"** (vật liệu ước cao, nhân công ước thấp so với bảng ngoài thực tế). Chỉ nhìn tổng sẽ kết luận sai.
2. **Báo giá nên cập nhật gì**: `NC_SX` định mức cao hơn nhiều so với 8% × vật liệu ở dòng cửa; vách kính thì ngược lại → nên chuyển công thức báo giá sang nhân công theo giờ (dùng bảng `operations` của S) hoặc tách `NC_SX_PCT` theo loại sản phẩm.
3. **Chi phí ngoài kế hoạch** (thuê cẩu) không thuộc dòng nào của báo giá → cần ô "Phát sinh/Dự phòng" trong báo giá hoặc điều khoản tính riêng cho khách; hệ thống chỉ ra nó nhờ `unplanned_flag`.

---

## 10. BÁO CÁO, DASHBOARD, PHÂN QUYỀN, KIỂM SOÁT

### 10.1 Báo cáo đề xuất (Script Report/Prepared Report)

| Báo cáo | Nội dung | Người dùng |
|---------|----------|-----------|
| **So sánh 3 lớp theo Bucket** | lưới Q·S·A·chênh lệch, lọc Project/SO/kỳ, drill-down đến Cost Fact → chứng từ | Quản lý, Sản xuất |
| **So sánh theo Tài khoản (P&L)** | cùng số liệu theo tài khoản; cột "khớp GL" so với P&L chuẩn của ERPNext | Kế toán |
| **Phân tích giá/lượng** | theo item (Mua hàng) và theo Operation/Workstation (Sản xuất) | Mua hàng, Sản xuất |
| **Cầu nối lợi nhuận** | Q → A theo bucket (§9.8) | BGĐ, Kinh doanh |
| **Cảnh báo ngoài kế hoạch** | `unplanned_flag`, `UNMAPPED`, vượt ngưỡng % | Kế toán dự án |
| **Độ tươi định mức** | Cost Plan lâu chưa tính lại, có lỗi | Kế hoạch |
| **Nhu cầu vật tư** | từ Cost Plan (gồm hao hụt) − tồn − PO | Mua hàng |

### 10.2 Dashboard/Workspace

Thẻ số (giá thành S, A, biên lợi nhuận), biểu đồ cột Q·S·A theo bucket, biểu đồ xu hướng chênh lệch theo tháng, danh sách dự án vượt ngưỡng; realtime qua `frappe.publish_realtime`.

### 10.3 Phân quyền

| Vai trò | Q | S | A | Mapping/Cấu hình |
|---------|---|---|---|------------------|
| AL Sales User | đọc giá bán | **không thấy** giá thành | không | — |
| AL BOM Manager | đọc | đọc | không | profile, template |
| **AL Cost Controller** (mới) | đọc | đọc/ghi | đọc | mapping, allocation, so sánh |
| Kế toán (Accounts User/Manager) | đọc | đọc | đọc/chạy collector | mapping tài khoản |
| Quản lý SX/Mua hàng | đọc | đọc | đọc theo bucket | — |

Giá thành định mức và thực tế là **thông tin nhạy cảm** — phải ẩn khỏi người báo giá (hiện `get_result_display` trả cả `cost_template` giá thành; nên chia quyền).

### 10.4 Kiểm soát & nhật ký

- Mọi Cost Plan/Comparison có `mapping_set`, `profile`, `calculated_on`, `checksum`; thay đổi mapping/profile có `track_changes` + duyệt (workflow).
- Khoá kỳ: sau **Period Closing** không cho đổi snapshot A của kỳ đó (chỉ tạo bản điều chỉnh).
- Chạy lại collector phải cho **cùng kết quả** nếu GL không đổi (kiểm thử idempotent).

---

## 11. LỘ TRÌNH, RỦI RO, QUYẾT ĐỊNH CẦN CHỐT

### 11.1 Lộ trình (đề xuất theo giá trị)

| Pha | Nội dung | Kết quả nghiệm thu |
|-----|----------|--------------------|
| **0 — Nền** (vài ngày) | Vá khoảng trống G1 (custom field Sales Order Item + test tạo SO từ Quotation), bật `strict` cho tính giá (lỗi không còn thành 0), lưu `resolved_inputs`/`price_basis` vào snapshot (G7) | SO mang đủ `al_bom*`; Cost Plan tái lập được |
| **1 — Lớp S** | Tách `compute`/`persist` (G6); `AL Cost Profile`, `AL Cost Plan` (+Line/Bucket/Operation); PriceResolver (valuation), ScrapResolver (Cutting Plan); trigger SO Submit + Item Price; nối `AL Material Plan` (G2) | Mở SO thấy giá thành định mức realtime; kế hoạch mua dùng số lượng gồm hao hụt |
| **2 — Gắn nhãn & thu thập A** | Accounting Dimension `AL Cost Bucket` (xử lý trùng tên field, G4); hook tự gán bucket/cost center; collector + `AL Cost Actual Snapshot`; mapping rule cơ bản | Báo cáo chi phí thực tế theo bucket **khớp GL** (kiểm tra đóng) |
| **3 — So sánh & mapping** | `AL Cost Mapping Set/Rule` đầy đủ; `AL Cost Comparison`; công thức chênh lệch FB; báo cáo bucket + tài khoản; cầu nối P&L | So sánh Q·S·A cho 1 dự án thật, kế toán xác nhận số khớp |
| **4 — Hấp thụ & phân bổ** | Cost Allocation Rule/Run (JE phân bổ), hấp thụ qua Manufacture Entry, vật liệu hoá BOM ERPNext + Work Order | Chi phí chung và nhân công phân bổ đúng, không đếm trùng |
| **5 — Vận hành** | Dashboard, cảnh báo, phân quyền, tài liệu, đào tạo; phản hồi ngược sang báo giá (cập nhật `NC_SX_PCT`, hao hụt…) | Báo giá được hiệu chỉnh bằng dữ liệu thực tế |

### 11.2 Rủi ro chính

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|--------|-----------|-----------|
| Đếm trùng chi phí (hấp thụ + phân bổ + GL) | số A sai | quy tắc `fact_type`/`fact_basis`, kiểm tra đóng §7.4, test đối chiếu GL |
| Dimension `AL Cost Bucket` trùng tên field với `Journal Entry.al_cost_bucket` | lỗi migrate/mất dữ liệu | kiểm tra trước trên bản sao; đổi tên field cũ, patch chuyển dữ liệu |
| Số bucket/mapping phình, người dùng gán sai | số liệu nhiễu | bucket mặc định tự gán theo item/account; `UNMAPPED` hiển thị; duyệt thay đổi mapping |
| Tính lại realtime quá tải | chậm hệ thống | debounce theo item, hàng đợi, ngưỡng tạo revision, đo trên dữ liệu thật |
| Giá thành định mức "thấp giả" vì lỗi công thức/thiếu giá | quyết định sai | `strict_errors`, banner, chặn Release khi còn lỗi |
| Reposting/chứng từ lùi ngày làm đổi A | snapshot lệch | đánh dấu `Stale`, chạy lại idempotent; khoá kỳ |
| Phân bổ sản phẩm dùng chung nhiều dự án | A theo dòng SO kém chính xác | quy ước driver; chấp nhận độ chính xác theo Project, dòng SO dùng tỷ trọng định mức |
| UOM nhôm kg ↔ cây | sai số lượng mua/kho | chuẩn hoá UOM và quy đổi, dùng Cutting Plan |
| Phụ thuộc phiên bản ERPNext | cơ chế hấp thụ/field có thể khác | xác minh trên site trước pha 4 |

### 11.3 Quyết định cần bạn chốt

| # | Câu hỏi | Ảnh hưởng |
|---|---------|-----------|
| 1 | Hệ thống tài khoản dùng cho mapping (VAS 621/622/627/641/642 hay cấu trúc nội bộ)? | `BUCKET_TO_ACCOUNT` |
| 2 | Có bật **perpetual inventory** (kế toán kho theo thời gian thực) không? | cách A vật tư lên GL, cầu nối giá vốn |
| 3 | Phương pháp valuation (Moving Average hay FIFO) và có dùng **Landed Cost** thường xuyên? | giá định mức S |
| 4 | Giá định mức S lấy theo: valuation, giá mua gần nhất, hay bảng giá mua? | `price_basis` |
| 5 | Lương nhân công ghi thế nào (Payroll → JE theo bộ phận hay theo công trình)? | cách `ALLOCATED` |
| 6 | Đơn vị chi phí theo dõi: **Project** hay từng dòng Sales Order? | độ chi tiết lưới |
| 7 | Có vật liệu hoá BOM ERPNext cho mọi dòng SO hay chỉ khi thả sản xuất? | số lượng BOM, hiệu năng |
| 8 | Chi phí bán hàng/quản lý có muốn so với báo giá ở mức dự án không? | `pnl_section`, driver |
| 9 | Ngưỡng cảnh báo chênh lệch (±%) theo bucket? | cảnh báo/duyệt |

### 11.4 Những điểm tôi **chưa xác minh** (cần thử trên site)

1. Hành vi map field Quotation Item → Sales Order Item khi chỉ có custom field ở Quotation Item (G1).
2. Fieldname và cơ chế Accounting Dimension khi tạo từ doctype `AL Cost Bucket`; việc dimension có đi vào GL Entry cho Stock Entry/Job Card trên phiên bản của bạn.
3. Chi tiết cơ chế "Expenses Included In Valuation" và `additional_costs` trong Manufacture Entry theo phiên bản.
4. Tên field giá giờ của `Workstation` (`hour_rate` và các thành phần) theo phiên bản.
5. Schema chính xác của Formula Variable Binding (`source_config`) và khả năng truy vấn `Bin`/`GL Entry` của các source type hiện có.
6. Hiệu năng tính lại hàng loạt trên dữ liệu thật.

> **Gợi ý bước tiếp theo:** chốt các câu hỏi §11.3 (nhất là #1, #2, #5), sau đó làm Pha 0–1 (nhanh, ít rủi ro, cho giá trị ngay là "giá thành định mức realtime" và kế hoạch vật tư đúng). Tôi có thể viết tiếp đặc tả chi tiết cho từng DocType (JSON field), pseudo-code engine `compute/persist`, và bộ test đối chiếu số liệu.


#=======================================================================================
#  PHÂN TÍCH CHI TIẾT

# GIẢI THÍCH LỚP ĐỊNH MỨC (S) & THỰC TẾ (A) — FLOW VÀ VÍ DỤ TỪNG BƯỚC

> Tài liệu bổ trợ cho `PHUONG_AN_GIA_THANH_3_LOP_QUOTATION_STANDARD_ACTUAL.md`. Viết lại theo hướng **dễ hiểu**: giải thích S và A từ gốc, rồi đi qua **một ví dụ duy nhất, từng bước, từ báo giá đến đối chiếu**.
> **Lưu ý trung thực:** lớp Q (tính giá bán) là code đã có trong repo AlumGlass. Lớp **S và A là phương án thiết kế đề xuất — chưa có code**. Các bước dùng chứng từ ERPNext (Purchase Receipt, Stock Entry, Job Card, Delivery Note…) mô tả theo hành vi chuẩn của ERPNext; bút toán minh hoạ cần đối chiếu với Chart of Accounts và phiên bản ERPNext của bạn (⚠). Số liệu là **minh hoạ tự dựng**, được script kiểm tra để mọi tổng khớp nhau; tiền làm tròn tới đồng ở từng dòng.

---

## 0. TRẢ LỜI NHANH

### 0.1 Giá thành định mức (S) là gì?

**Là câu trả lời cho "làm sản phẩm này hết bao nhiêu tiền?" — tính từ chính BOM động đã dùng để báo giá, nhưng đổi sang góc nhìn của nhà máy.** Báo giá (Q) trả lời "bán bao nhiêu"; S trả lời "tốn bao nhiêu và cần mua/làm những gì".

Cùng một BOM, cùng công thức chiều dài–diện tích–số lượng, **chỉ thay 4 thứ**:

| Thay đổi | Báo giá (Q) | Định mức (S) | Vì sao |
|----------|-------------|--------------|--------|
| 1. **Giá vật tư** | giá bán trong bảng giá | **giá vốn thực của kho** (Valuation Rate) | S là chi phí của mình, không phải giá chào khách |
| 2. **Hao hụt** | % ước lượng theo nhóm vật tư (nhôm 20%) | **kết quả bài toán cắt** (Cutting Plan: 11,5%) | để mua đúng số lượng cần |
| 3. **Nhân công** | % × vật liệu (8%) | **số giờ × đơn giá giờ** của từng công đoạn | để giao việc, đo năng suất |
| 4. **Lợi nhuận, VAT** | có | **không có** | S là giá thành, chưa cộng lãi |

**S không phải sổ kế toán.** Nó là một **bảng dự toán sống** (`AL Cost Plan`): không tạo bút toán, không ảnh hưởng báo cáo tài chính. Nó "sống" vì **tự tính lại** khi giá vốn, định mức cắt hay đơn giá giờ thay đổi (§1.3).

### 0.2 Giá thực tế (A) có phải là "ghi nhận chi phí thực tế gắn tài khoản + cost bucket" không?

**Đúng, đó là bản chất — kèm 6 điểm cần hiểu cho chính xác:**

1. **Mỗi đồng chi phí thực tế là một dòng của chứng từ đã ghi sổ** (nhập kho, xuất kho sản xuất, phiếu công việc, hoá đơn mua, bút toán phân bổ…). Hệ thống **không có chỗ nhập "chi phí thực tế" riêng**.
2. **Tài khoản và Cost Bucket là hai nhãn khác nhau trên cùng dòng đó.** *Tài khoản* là ngôn ngữ kế toán (bắt buộc, quyết định lên báo cáo tài chính). *Cost Bucket* là nhãn quản trị (để sản xuất/mua hàng so sánh với S và Q). Dòng chi phí còn mang **Project** và **Cost Center**.
3. **Bucket thường tự suy ra**, không bắt người dùng chọn tay: từ vật tư → Material Category → bucket; từ tài khoản → bucket theo bảng mapping. Người dùng chỉ sửa ngoại lệ.
4. **Chi phí không gắn được vào bucket không bị bỏ sót** — rơi vào bucket `UNMAPPED` để bạn nhìn thấy và xử lý.
5. **Vật tư đi qua kho trước rồi mới thành giá vốn:** Kho nguyên vật liệu → Sản xuất dở dang → Thành phẩm → Giá vốn (khi giao hàng). Vì vậy có 2 khái niệm: *chi phí đã phát sinh cho đơn hàng* (A) và *giá vốn đã ghi nhận vào P&L* (cầu nối ở Bước 10).
6. **Lớp A do một "collector" đọc từ sổ để tổng hợp, không ghi thêm bút toán.** Nguồn sự thật vẫn là sổ của ERPNext.

### 0.3 So sánh nhanh ba lớp

| | **Q — Báo giá** | **S — Định mức** | **A — Thực tế** |
|---|---|---|---|
| Trả lời | bán bao nhiêu | làm tốn bao nhiêu (dự kiến), cần mua gì | thực tế đã tốn bao nhiêu |
| Tính từ | BOM động + giá bán | **cùng BOM** + giá vốn + giờ công | **chứng từ đã ghi sổ** |
| Chạy khi | lúc báo giá | tự động khi đơn hàng/giá/định mức đổi | khi có chứng từ; tổng hợp theo kỳ |
| Lưu ở | `al_bom_result`, `ConfigSnapshot` | `AL Cost Plan` (có revision) | sổ ERPNext; `AL Cost Actual Snapshot` |
| Ghi sổ kế toán? | không | **không** | **có** (chính là sổ) |
| Dùng cho | chào giá | mua hàng, kế hoạch SX, kiểm soát | kế toán, đối chiếu, rút kinh nghiệm |

---

## 1. HIỂU LỚP S TỪ GỐC

### 1.1 S giống và khác báo giá ở đâu — hình dung bằng một "bộ lọc"

```
            ┌─────────────────────────────────────────────┐
  BOM động  │ dòng vật tư + công thức chiều dài/diện tích │   ← DÙNG CHUNG (một nguồn)
 (version)  │ + số lượng + nhóm chi phí (Cost Bucket)     │
            └───────────────┬─────────────────────────────┘
        ┌───────────────────┴──────────────────────┐
        ▼                                          ▼
  PROFILE "QUOTATION"                        PROFILE "STANDARD"
  giá = bảng giá bán                         giá = giá vốn kho
  hao hụt = % theo nhóm                      hao hụt = bài toán cắt
  NC = 8% vật liệu                           NC = giờ × đơn giá giờ
  + lợi nhuận + VAT                          không lãi, không VAT
        ▼                                          ▼
   GIÁ BÁN                                  GIÁ THÀNH ĐỊNH MỨC
```

Vì dùng chung BOM và công thức số lượng, **không thể có hai bản "BOM" lệch nhau**; chênh lệch Q–S chỉ đến từ 4 thay đổi ở bảng trên — dễ giải thích.

### 1.2 S được tính theo 4 khối

| Khối | Cách tính | Lấy dữ liệu từ đâu |
|------|-----------|--------------------|
| **Vật tư** | `số lượng tịnh × (1 + hao hụt) × giá vốn` | công thức Bom Item; Cutting Plan; Valuation Rate của kho |
| **Nhân công sản xuất** | `Σ giờ công từng công đoạn × đơn giá giờ` | định mức giờ (Operation/BOM), đơn giá Workstation |
| **Lắp đặt** | `số người × giờ × đơn giá đội × hệ số độ cao` | biến cấu hình + rule hệ số có sẵn |
| **Chi phí chung** | theo **tiêu thức phân bổ** (m² giao hàng, giờ công trực tiếp, % giá trị) | Global Variable / quy tắc phân bổ |

Tất cả được đặt thành công thức trong một **Cost Template loại STANDARD** (Formula Builder) — đổi cách tính = đổi công thức, không sửa code. Ví dụ đầy đủ ở Bước 2.

### 1.3 "Realtime" nghĩa là gì?

Không phải "tính liên tục từng giây", mà là: **mọi thay đổi làm giá thành đổi đều tự đẩy vào hàng đợi tính lại**, nên người dùng mở đơn hàng là thấy số mới.

| Sự kiện | Hệ thống làm gì |
|---------|-----------------|
| Sales Order được Submit | tạo `AL Cost Plan` bản 1 cho từng dòng có BOM động |
| Nhập kho / Landed Cost làm **giá vốn đổi** | tìm các Cost Plan đang mở có dùng vật tư đó → tính lại |
| Đổi Cutting Plan, đơn giá giờ, hệ số, biến toàn cục | tương tự |
| Bấm "Thả sản xuất" | **khoá** bản hiện tại làm mốc đo lường |

Mỗi lần tính lại lưu **đầu vào đã dùng và giá đã dùng** để trả lời "vì sao số này đổi?". Ví dụ cụ thể ở Bước 3.

### 1.4 S dùng để làm gì (ra quyết định tức thì)

| Người dùng | Câu hỏi | S cho gì |
|-----------|---------|----------|
| Mua hàng | Cần mua bao nhiêu nhôm/kính/phụ kiện? | số lượng **gồm hao hụt** − tồn kho − PO đang về |
| Kế hoạch SX | Cần bao nhiêu giờ cắt/lắp ráp/lắp kính? | giờ theo công đoạn, theo trạm làm việc |
| Quản lý | Đơn này lãi hay lỗ **nếu làm đúng định mức**? | doanh thu − giá thành định mức |
| Kinh doanh | Báo giá đang ước lượng đúng/sai chỗ nào? | so sánh Q–S theo bucket |
| Sản xuất | Mục tiêu hao hụt/giờ công là bao nhiêu? | định mức làm chuẩn để đo A |

### 1.5 S khác gì "BOM cost" của ERPNext?

ERPNext có tính giá thành trên BOM tĩnh (cộng vật tư + chi phí vận hành). Ở AlumGlass mỗi sản phẩm là **BOM động theo kích thước**, nên cần engine riêng tính theo từng đơn hàng. Phương án **không thay thế** ERPNext: khi thả sản xuất, kết quả S được **"vật liệu hoá" thành BOM/Work Order chuẩn của ERPNext** để dùng Production Plan, Job Card, kho.

---

## 2. HIỂU LỚP A TỪ GỐC

### 2.1 Mỗi dòng chi phí thực tế mang 4 nhãn

```
 Chứng từ ERPNext (đã ghi sổ)
   └─ dòng bút toán:   Tài khoản   │ Số tiền │ Project │ Cost Center │ Cost Bucket
                       (kế toán)      (VND)    (công trình) (bộ phận)   (quản trị)
```

| Nhãn | Ai quan tâm | Lấy từ đâu |
|------|-------------|-----------|
| **Tài khoản** | Kế toán | do chứng từ/kế toán chọn (bắt buộc) |
| **Project** | Quản lý dự án | field `project` của chứng từ |
| **Cost Center** | Từng bộ phận | cost center của chứng từ/trạm làm việc |
| **Cost Bucket** | Sản xuất, mua hàng, so sánh với Q/S | tự suy từ vật tư/tài khoản; hoặc chọn tay (Accounting Dimension) |

### 2.2 Ba nhóm nguồn thực tế

| Nhóm | Chứng từ | Đo bằng | Bucket suy từ |
|------|----------|---------|---------------|
| **Vật tư** | Stock Entry (xuất cho sản xuất), Purchase Receipt + Landed Cost | giá trị kho theo giá vốn bình quân | vật tư → nhóm vật tư → bucket |
| **Nhân công/máy** | Job Card (giờ thực tế), lương, bút toán phân bổ | giờ × đơn giá | công đoạn/trạm → bucket |
| **Chi phí khác** | Purchase Invoice, Journal Entry, chi phí lắp đặt, phân bổ chi phí chung | số tiền dòng chi phí | tài khoản → bucket (mapping) hoặc `UNMAPPED` |

### 2.3 Đường đi của vật tư và thời điểm "chi phí" xuất hiện trong P&L

```
 Mua vật tư            Xuất cho SX              Sản xuất xong             Giao hàng
 Kho NVL (152)  ───►  SX dở dang (154)  ───►  Thành phẩm (155)  ───►  Giá vốn (632)
  (tài sản)            (tài sản)                (tài sản)             (CHI PHÍ trong P&L)
                          ▲                         ▲
            + nhân công, chi phí chung hấp thụ vào tại đây
```

→ Chi phí vật tư **chỉ vào P&L khi giao hàng**. Vì thế để so với S và Q, ta tính **chi phí đã phát sinh cho đơn hàng** từ các chứng từ kho/sản xuất, rồi có một bảng **cầu nối** về P&L (Bước 10).

### 2.4 Hấp thụ và phân bổ — chỗ dễ nhầm nhất

ERPNext khi hoàn thành sản xuất **cộng chi phí vận hành theo đơn giá chuẩn × giờ thực tế vào giá trị thành phẩm** ("hấp thụ"). Nhưng **tiền lương thực tế** trả theo cách khác. Khác biệt giữa hai con số là **chênh lệch**:

```
  Chi phí nhân công thực tế (A) =  phần đã hấp thụ vào thành phẩm  +  chênh lệch (đơn giá, năng suất)
                                   └ theo đơn giá chuẩn × giờ thực   └ ghi thẳng vào giá vốn kỳ này
```

Cùng logic cho chi phí chung sản xuất. Nhờ vậy A không bị đếm hai lần và vẫn phân tích được nguyên nhân. Có số ở Bước 5.

### 2.5 Câu hỏi thường gặp

| Câu hỏi | Trả lời |
|---------|---------|
| Quên gắn bucket thì sao? | Hệ thống tự suy theo vật tư/tài khoản; không suy được → `UNMAPPED` (hiện trên báo cáo, có nút gán). Không mất tiền nào |
| Chi phí không có trong báo giá (thuê cẩu)? | Vẫn ghi nhận bình thường; vì Q = S = 0 nên bị đánh dấu **"ngoài kế hoạch"** |
| Kế toán có phải làm thêm việc không? | Gần như không: dùng chứng từ như cũ; chỉ cần dimension/mapping được cấu hình một lần |
| Số A có khớp báo cáo tài chính không? | Có kiểm tra đóng tự động: tổng theo bucket = tổng theo tài khoản = tổng chứng từ nguồn |
| Chứng từ hạch toán lùi ngày? | Snapshot đánh dấu `Stale` và tính lại; chạy lại cho kết quả như nhau (idempotent) |

---

## 3. FLOW TỔNG THỂ

```
 ① BÁO GIÁ (Q)            ② ĐẶT HÀNG → ĐỊNH MỨC (S)        ③ MUA HÀNG       ④ SẢN XUẤT & LẮP ĐẶT      ⑤ GIAO & THU TIỀN
 Quotation Item           Sales Order Submit               PO / PR / PI      Work Order, Job Card      Delivery Note
  └ BomOrchestrator         └ AL Cost Plan rev 1             └ Landed Cost     └ Stock Entry (xuất,       └ Sales Invoice
     profile QUOTATION          profile STANDARD               giá vốn đổi        hoàn thành)            
  └ GIA_BAN + ConfigSnapshot    └ nhu cầu vật tư/giờ công        ▼              └ Chi phí lắp đặt, phát sinh
                                   ▲                      ★ S TỰ TÍNH LẠI              │
                                   └──────── rev 2 ───────────┘                          ▼
                                                                         ⑥ COLLECTOR: gom chứng từ → Cost Fact (A)
                                                                                    │ mapping bucket ↔ tài khoản
                                                                                    ▼
                                                                         ⑦ SO SÁNH Q · S · A  (+ P&L, + phân tích chênh lệch)
```

| Bước | Việc | Lớp |
|------|------|-----|
| 0 | Cấu hình một lần (bucket, mapping, profile) | nền |
| 1 | Tính giá bán | **Q** |
| 2 | Đặt hàng → giá thành định mức & nhu cầu vật tư | **S** |
| 3 | Mua hàng → giá vốn đổi → S tự tính lại | **S** |
| 4 | Thả sản xuất, xuất vật tư | **A** (vật tư) |
| 5 | Sản xuất: giờ công, hoàn thành | **A** (nhân công/chung) |
| 6 | Lắp đặt, chi phí phát sinh | **A** |
| 7 | Giao hàng, xuất hoá đơn | **A** + doanh thu |
| 8 | Collector tạo Cost Fact | **A** |
| 9 | Mapping & lưới so sánh | Q·S·A |
| 10 | Đọc kết quả, cầu nối P&L, phân tích | Q·S·A |

---

## 4. VÍ DỤ TỪNG BƯỚC

**Bối cảnh:** Sales Order `SO-DEMO-01`, Project `P-DEMO`, **2 bộ cửa đi mở quay 2 cánh** `CDMQ-2C`, kích thước **2400 × 2600 mm**, `n_panel = 2`, lắp ở độ cao 3 m (`RULE-HEIGHT-MULT = 1,0`). `OFFSET_FRAME = 48`, `OFFSET_GLASS = 66`.

### Bước 0 — Cấu hình một lần

| Hạng mục | Cấu hình | Ghi chú |
|----------|----------|---------|
| **Cost Bucket** | `VL_NHOM`, `VL_KINH`, `VL_VTP`, `VL_PK` (vật liệu); `NC_SX`, `NC_LD` (nhân công); `OH_SX`, `OH_VC`, `OH_QLY` (chi phí chung); `KHAC` (ngoài kế hoạch); `SCRAP_REC` (thu hồi phế liệu, âm); `UNMAPPED` | `UNMAPPED` luôn tồn tại để không sót tiền |
| **Material Category → bucket mặc định** | NHOM→`VL_NHOM`, KINH→`VL_KINH`, VTP→`VL_VTP`, PK→`VL_PK` | để vật tư tự gắn bucket |
| **Accounting Dimension** | `AL Cost Bucket` gắn vào Stock Entry, Purchase Invoice, Journal Entry và GL | bucket đi vào sổ cái |
| **Mapping bucket → tài khoản** (ví dụ theo VAS) | vật liệu & `SCRAP_REC` → **621**; `NC_SX`, `NC_LD` → **622**; `OH_SX`, `KHAC` → **627**; `OH_VC` → **641**; `OH_QLY` → **642** (riêng **Q**: `OH_QLY` = 40% **627** + 60% **642**) | tài khoản do bạn chọn |
| **Profile** | `QUOTATION` (giá bán, hao hụt %, NC %, có lãi/VAT); `STANDARD` (giá vốn, Cutting Plan, giờ công, không lãi/VAT, `strict_errors`) | |
| **Đơn giá giờ chuẩn** | cắt 95.000 · lắp ráp 110.000 · lắp kính 105.000 · đội lắp đặt 120.000 đ/giờ-người | Workstation / biến FB |
| **Chi phí chung chuẩn** | `OH_VC` 28.000 đ/m² giao; `OH_SX` 28.000 đ/giờ công TT; `OH_QLY` 2,5% × (VL+NC) | Global Variable |
| **Kho ban đầu** | 60 kg nhôm đại diện `NHOM-XINGFA`, giá vốn **109.800 đ/kg** | Bin |

### Bước 1 — Tính giá bán (Q) · profile `QUOTATION`

Engine chạy B0→B6 như hiện tại. Mỗi dòng BOM: công thức rộng/cao/số lượng → pattern → số lượng tịnh → hao hụt theo nhóm → × giá bán.

| Slug | Công thức rộng (mm) | Rộng | Số lượng | Pattern | Đơn vị/chiếc | Số lượng tịnh | Hao hụt | Gồm hao hụt | Đơn giá (đ) | Thành tiền (đ) | Bucket |
|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| `khung_ngang` | `W_mm - 2*OFFSET_FRAME` | 2304 | 2 | LENGTH_TO_WEIGHT (kg) | 2,7648 | 5,5296 | 20% | 6,6355 | 113.000 | 749.814 | VL_NHOM |
| `khung_dung` | `H_mm - OFFSET_FRAME` | 2552 | 2 | LENGTH_TO_WEIGHT (kg) | 3,7004 | 7,4008 | 20% | 8,8810 | 113.000 | 1.003.548 | VL_NHOM |
| `canh_dung` | `H_mm - OFFSET_FRAME - 72` | 2480 | 2*n_panel = 4 | LENGTH_TO_WEIGHT (kg) | 3,9680 | 15,8720 | 20% | 19,0464 | 113.000 | 2.152.243 | VL_NHOM |
| `canh_ngang` | `(W_mm-2*OFFSET_FRAME)/n_panel - 52` | 1100 | 2*n_panel = 4 | LENGTH_TO_WEIGHT (kg) | 1,4300 | 5,7200 | 20% | 6,8640 | 113.000 | 775.632 | VL_NHOM |
| `kinh_canh` | `(W_mm-2*OFFSET_FRAME)/n_panel - 2*OFFSET_GLASS` × `H_mm-300` | 1020 | n_panel = 2 | AREA_M2 (m²) | 2,3460 | 4,6920 | 5% | 4,9266 | 725.000 | 3.571.785 | VL_KINH |
| `gioang` | như kính (chu vi) | 1020 | n_panel = 2 | PERIMETER_M (m) | 6,6400 | 13,2800 | 2% | 13,5456 | 6.500 | 88.046 | VL_VTP |
| `bo_vit` | — | — | 1 | COUNT (bộ) | 1,0000 | 1,0000 | 2% | 1,0200 | 120.000 | 122.400 | VL_VTP |
| `ban_le` | — | — | 3*n_panel = 6 | COUNT (cái) | 1,0000 | 6,0000 | 10% | 6,6000 | 85.000 | 561.000 | VL_PK |
| `khoa` | — | — | 1 | COUNT (cái) | 1,0000 | 1,0000 | 10% | 1,1000 | 640.000 | 704.000 | VL_PK |
| `tay_nam` | — | — | 2 | COUNT (cái) | 1,0000 | 2,0000 | 10% | 2,2000 | 180.000 | 396.000 | VL_PK |

Ví dụ `khung_ngang`: rộng = 2400 − 2×48 = **2304 mm**; pattern `LENGTH_TO_WEIGHT` = 2,304 m × 1,2 kg/m = **2,7648 kg/chiếc**; × 2 chiếc = 5,5296 kg; hao hụt nhôm 20% → 6,6355 kg; × 113.000 = **749.814 đ**.

**Gom bucket → Cost Template** (1 bộ):

| Dòng | Công thức | Giá trị (đ) |
|---|---|---:|
| `VL_NHOM` | Σ line_total nhôm | 4.681.237 |
| `VL_KINH` | Σ line_total kính | 3.571.785 |
| `VL_VTP` | Σ vật tư phụ | 210.446 |
| `VL_PK` | Σ phụ kiện | 1.661.000 |
| `TONG_VL` | tổng 4 bucket | 10.124.468 |
| `NC_SX` | 8% × TONG_VL | 809.957 |
| `NC_LD` | 6% × TONG_VL × 1,0 | 607.468 |
| `OH_VC` | 3% × TONG_VL | 303.734 |
| `OH_QLY` | 3% × (TONG_VL+TONG_NC) | 346.257 |
| `GIA_THANH` | VL + NC + OH | 12.191.884 |
| `PROFIT` | 16% × GIA_THANH | 1.950.701 |
| **`GIA_BAN`** | trước VAT (`is_pre_vat_price`) | 14.142.585 |
| `GIA_VAT` | + 10% VAT | 15.556.843 |

→ **Quotation (2 bộ):** `GIA_BAN` = **28.285.170 đ** (giá thành theo báo giá 24.383.768 đ, lợi nhuận 3.901.402 đ). Khi Submit, `ConfigSnapshot` đóng băng kết quả: đây là **lớp Q**.

### Bước 2 — Khách đặt hàng → giá thành định mức (S) rev 1

Sales Order Submit → hệ thống tạo `AL Cost Plan` rev 1 bằng **cùng BOM, cùng số lượng tịnh** của Bước 1, profile `STANDARD`:

| Slug | Tịnh | Hao hụt | Gồm hao hụt | Giá vốn (đ) | Thành tiền (đ) | Bucket | Nguồn |
|---|---:|---:|---:|---:|---:|---|---|
| `khung_ngang` | 5,5296 | 11,5% | 6,1655 | 109.800 | 676.972 | VL_NHOM | giá vốn kho 109.800; hao hụt từ Cutting Plan |
| `khung_dung` | 7,4008 | 11,5% | 8,2519 | 109.800 | 906.058 | VL_NHOM | giá vốn kho 109.800; hao hụt từ Cutting Plan |
| `canh_dung` | 15,8720 | 11,5% | 17,6973 | 109.800 | 1.943.161 | VL_NHOM | giá vốn kho 109.800; hao hụt từ Cutting Plan |
| `canh_ngang` | 5,7200 | 11,5% | 6,3778 | 109.800 | 700.282 | VL_NHOM | giá vốn kho 109.800; hao hụt từ Cutting Plan |
| `kinh_canh` | 4,6920 | 3,8% | 4,8703 | 702.000 | 3.418.948 | VL_KINH | giá vốn 702.000; hao hụt cắt kính 3,8% |
| `gioang` | 13,2800 | 2,0% | 13,5456 | 6.200 | 83.983 | VL_VTP | giá vốn; hao hụt 2% |
| `bo_vit` | 1,0000 | 2,0% | 1,0200 | 115.000 | 117.300 | VL_VTP | giá vốn; hao hụt 2% |
| `ban_le` | 6,0000 | 2,0% | 6,1200 | 81.000 | 495.720 | VL_PK | giá vốn; hao hụt 2% |
| `khoa` | 1,0000 | 2,0% | 1,0200 | 612.000 | 624.240 | VL_PK | giá vốn; hao hụt 2% |
| `tay_nam` | 2,0000 | 2,0% | 2,0400 | 171.000 | 348.840 | VL_PK | giá vốn; hao hụt 2% |

**Nhân công, lắp đặt, chi phí chung (1 bộ):**

| Khối | Định mức | Giá trị (đ) |
|---|---|---:|
| `NC_SX` cắt nhôm | 1,2 giờ × 95.000 | 114.000 |
| `NC_SX` lắp ráp | 5,0 giờ × 110.000 | 550.000 |
| `NC_SX` lắp kính | 2,4 giờ × 105.000 | 252.000 |
| **`NC_SX`** | 8,6 giờ công trực tiếp | 916.000 |
| `NC_LD` | 2 người × 2,5 giờ × 120.000 × hệ số 1,0 | 600.000 |
| `OH_VC` | 6,24 m² × 28.000 | 174.720 |
| `OH_SX` | 8,6 giờ × 28.000 | 240.800 |
| `OH_QLY` | 2,5% × (VL + NC) | 270.788 |
| **GIÁ THÀNH ĐỊNH MỨC (1 bộ)** | VL 9.315.504 + NC 1.516.000 + OH 686.308 | **11.517.812** |

→ **S rev 1 (2 bộ) = 23.035.624 đ** (so với Q = 24.383.768 đ). Không có lợi nhuận/VAT.

**Dùng S để lập kế hoạch ngay** (AL Material Plan đọc số lượng *gồm hao hụt* từ Cost Plan, không phải số lượng tịnh):

| Vật tư | Cần (gồm hao hụt) | Tồn kho | Thiếu | Hành động |
|---|---|---|---|---|
| Nhôm `NHOM-XINGFA` | 76,98 kg | 60 kg | 16,98 kg | Mua **78 kg** (làm tròn theo cây) |
| Kính `kinh_canh` | 9,74 m² | 0 | 9,74 m² | Mua **11,5 m²** (theo khổ tấm) |
| Giờ công | cắt 2,4 h · lắp ráp 10,0 h · lắp kính 4,8 h | — | — | Lập lịch theo Workstation |

### Bước 3 — Mua hàng → giá vốn đổi → S tự tính lại (rev 2)

**Chứng từ và bút toán** (nhãn ở cột cuối là Project / Bucket được gắn tự động):

| # | Chứng từ | Bút toán (Nợ / Có) | Số tiền (đ) | Nhãn |
|---|---|---|---:|---|
| 3a | Purchase Receipt: nhôm 78 kg × 111.200 | Nợ **Kho NVL (152)** / Có Hàng mua chưa có hoá đơn | 8.673.600 | P-DEMO · `VL_NHOM` |
| 3b | Purchase Receipt: kính 11,5 m² × 705.000 | Nợ **Kho NVL (152)** / Có Hàng mua chưa có hoá đơn | 8.107.500 | P-DEMO · `VL_KINH` |
| 3c | Purchase Invoice tương ứng | Nợ Hàng mua chưa có hoá đơn / Có Phải trả NCC (331) | — | (không qua P&L) |
| 3d | Landed Cost Voucher: cước vận chuyển nhôm 1.950 đ × 78 kg | Nợ **Kho NVL (152)** / Có Chi phí tính vào giá trị tồn kho | 152.100 | P-DEMO · `VL_NHOM` |

**Giá vốn nhôm trong kho (bình quân gia quyền) thay đổi:**

| Thời điểm | Công thức | Giá vốn (đ/kg) |
|---|---|---:|
| Trước nhập | 60 kg × 109.800 / 60 | 109.800,00 |
| Sau Purchase Receipt (3a) | (60×109.800 + 78×111.200) / 138 | 110.591,30 |
| Sau Landed Cost (3d) | (60×109.800 + 78×111.200 + 152.100) / 138 | 111.693,48 |

**Chuỗi sự kiện:** giá vốn đổi → hook đưa các Cost Plan *Active* có dùng `NHOM-XINGFA` vào hàng đợi → engine tính lại (rất nhanh nhờ cache công thức) → tạo **rev 2**, trigger `PRICE_CHANGE`, lưu `price_basis_json` = "nhôm: valuation 111.693,48".

| Chỉ tiêu (1 bộ) | rev 1 | rev 2 | Thay đổi |
|---|---:|---:|---:|
| `VL_NHOM` | 4.226.473 | 4.299.360 | +72.887 |
| `OH_QLY` (2,5% × (VL+NC)) | 270.788 | 272.610 | +1.822 |
| **Giá thành định mức** | 11.517.812 | 11.592.521 | +74.709 |

→ **S rev 2 (2 bộ) = 23.185.042 đ.** Người mua hàng thấy ngay đơn này đắt thêm 149.418 đ vì giá nhôm và cước vận chuyển. Đây là ý nghĩa của "định mức realtime".

### Bước 4 — Thả sản xuất, xuất vật tư (A: vật tư)

Bấm **Release**: khoá S rev 2 làm mốc; hệ thống tạo **BOM ERPNext** (vật tư = số lượng gồm hao hụt, công đoạn = 3 bước) và **Work Order** (`project = P-DEMO`). Kho xuất vật tư cho sản xuất bằng Stock Entry *Material Transfer for Manufacture*:

| Vật tư xuất | Số lượng | Giá vốn | Giá trị (đ) | Bucket (tự gắn) | S rev 2 cần |
|---|---|---:|---:|---|---|
| Nhôm | 79,5 kg | 111.693,48 | 8.879.632 | `VL_NHOM` | 76,98 kg |
| Kính | 11,0 m² | 705.000 | 7.755.000 | `VL_KINH` | 9,74 m² |
| Vật tư phụ (gioăng, vít) | — | — | 452.000 | `VL_VTP` | — |
| Phụ kiện (bản lề, khoá, tay nắm) | 2 bộ + 1 bản lề bổ sung | — | 2.961.000 | `VL_PK` | — |

**Bút toán 4a:** Nợ **SX dở dang (154)** / Có **Kho NVL (152)** = **20.047.632 đ**, mỗi dòng mang Project `P-DEMO` và bucket tương ứng.

Trong sản xuất xảy ra 2 việc ngoài định mức: **cắt lại 1 thanh nhôm** (nhôm xuất 79,5 kg > 76,99 kg định mức) và **vỡ 1 tấm kính khi lắp** (kính xuất 11,0 m² > 9,74 m² định mức). Phế liệu nhôm 4,0 kg được bán **38.000 đ/kg = 152.000 đ** → ghi giảm chi phí vật tư (bucket `SCRAP_REC`, số âm).

### Bước 5 — Sản xuất: giờ công & hoàn thành (A: nhân công/chung)

Công nhân ghi giờ trên **Job Card** của từng công đoạn:

| Công đoạn | Giờ định mức | Giờ thực tế | Đơn giá chuẩn | Đơn giá thực (lương TB kể cả tăng ca) | Hấp thụ (giờ thực × giá chuẩn) | Thực tế (giờ thực × giá thực) |
|---|---:|---:|---:|---:|---:|---:|
| Cắt nhôm | 2,4 | 2,6 | 95.000 | 98.000 | 247.000 | 254.800 |
| Lắp ráp khung/cánh | 10,0 | 10,8 | 110.000 | 118.000 | 1.188.000 | 1.274.400 |
| Lắp kính | 4,8 | 5,4 | 105.000 | 112.000 | 567.000 | 604.800 |
| **Tổng** | 17,2 | 18,8 |  |  | 2.002.000 | 2.134.000 |

**Khi hoàn thành (Stock Entry *Manufacture*)** ERPNext ghi thành phẩm = vật tư + chi phí vận hành hấp thụ:

| # | Bút toán | Số tiền (đ) | Ghi chú |
|---|---|---:|---|
| 5a | Nợ **Thành phẩm (155)** / Có SX dở dang (154) — vật tư | 19.895.632 | vật tư 20.047.632 − phế liệu 152.000 |
| 5b | Nợ Thành phẩm (155) / Có Chi phí tính vào giá trị tồn kho — nhân công **hấp thụ** | 2.002.000 | giờ thực × giá chuẩn |
| 5c | Nợ Thành phẩm (155) / Có Chi phí tính vào giá trị tồn kho — chi phí chung SX **hấp thụ** | 526.400 | 18,8 giờ × 28.000 |
|  | **Giá trị thành phẩm nhập kho** | **22.424.032** |  |

**Cuối kỳ, kế toán chạy `Cost Allocation Run`** phân bổ chi phí thực tế về dự án theo giờ công:

| # | Việc | Tính | Số tiền (đ) |
|---|---|---|---:|
| 5d | Lương thực tế phân bổ cho P-DEMO | theo giờ Job Card × lương TB thực | 2.134.000 |
| 5e | Chi phí chung SX thực tế phân bổ | 18,8 giờ × 31.000 (pool TK 627 / tổng giờ kỳ) | 582.800 |
|  | **Chênh lệch nhân công** = thực tế − hấp thụ | 2.134.000 − 2.002.000 | 132.000 |
|  | **Chênh lệch chi phí chung** = thực tế − hấp thụ | 582.800 − 526.400 | 56.400 |

Hai khoản chênh lệch này **không vào giá trị thành phẩm** mà ghi thẳng vào giá vốn kỳ; nhưng vẫn thuộc chi phí thực tế của đơn hàng (A).

### Bước 6 — Lắp đặt và chi phí phát sinh (A)

| Chứng từ | Nội dung | Bút toán | Số tiền (đ) | Bucket | Có trong báo giá/định mức? |
|---|---|---|---:|---|---|
| AL Installation Cost Actual + Purchase Invoice | Nhân công đội lắp đặt | Nợ **622** / Có 331 | 1.350.000 | `NC_LD` | Có (Q 1.214.936 · S 1.200.000) |
| Purchase Invoice (nhà thầu cẩu) | **Thuê cẩu** — không lường trước | Nợ **627** / Có 331 | 600.000 | `KHAC` | **Không** (Q = S = 0) |

Hóa đơn thuê cẩu chỉ có Project, chưa chọn bucket → rule `ACCOUNT_TO_BUCKET` (TK 627 + Purchase Invoice) gán `KHAC`; nếu không có rule đó nó sẽ rơi vào `UNMAPPED`.

### Bước 7 — Giao hàng, hoá đơn, chi phí kỳ (A + doanh thu)

| # | Chứng từ | Bút toán | Số tiền (đ) |
|---|---|---|---:|
| 7a | Delivery Note (giao 2 bộ) | Nợ **Giá vốn (632)** / Có Thành phẩm (155) | 22.424.032 |
| 7b | Sales Invoice (khách được giảm 1%) | Nợ Phải thu (131) / Có **Doanh thu (511)** / Có Thuế GTGT |  |
|  |    • Doanh thu (trước VAT) | = 28.285.170 × 99% | 28.002.318 |
| 7c | Purchase Invoice cước giao hàng | Nợ **Chi phí bán hàng (641)** / Có 331 | 380.000 |
| 7d | Allocation Run: chi phí quản lý | Nợ **Chi phí quản lý (642)** / Có 6xx (kết chuyển pool) | 640.000 |

Giá vốn trên P&L **= 22.424.032 (7a) + các khoản đã ghi thẳng vào giá vốn** (chênh lệch nhân công 132.000, chênh lệch chung 56.400, lắp đặt 1.350.000, thuê cẩu 600.000) = **24.562.432 đ**.

### Bước 8 — Collector tạo Cost Fact (lớp A)

Collector đọc sổ của dự án `P-DEMO` và tạo mỗi dòng một **Cost Fact** `(bucket, tài khoản, cost center, số tiền, nguồn)`. Đây là bảng *đọc được* để người dùng truy ngược về chứng từ:

| Nguồn | Bucket | TK | Loại | Số tiền (đ) |
|---|---|---|---|---:|
| Stock Entry xuất nhôm | `VL_NHOM` | 621 | DIRECT | 8.879.632 |
| Stock Entry xuất kính | `VL_KINH` | 621 | DIRECT | 7.755.000 |
| Stock Entry vật tư phụ | `VL_VTP` | 621 | DIRECT | 452.000 |
| Stock Entry phụ kiện | `VL_PK` | 621 | DIRECT | 2.961.000 |
| Bán phế liệu nhôm | `SCRAP_REC` | 621 | DIRECT | -152.000 |
| Job Card × giá chuẩn (đã vào thành phẩm) | `NC_SX` | 622 | ABSORBED | 2.002.000 |
| Allocation Run: chênh lệch nhân công | `NC_SX` | 622 | VARIANCE | 132.000 |
| Allocation Run: CP chung SX hấp thụ | `OH_SX` | 627 | ABSORBED | 526.400 |
| Allocation Run: chênh lệch CP chung | `OH_SX` | 627 | VARIANCE | 56.400 |
| Chi phí đội lắp đặt | `NC_LD` | 622 | DIRECT | 1.350.000 |
| Thuê cẩu (PI) | `KHAC` | 627 | DIRECT | 600.000 |
| Cước giao hàng (PI) | `OH_VC` | 641 | DIRECT | 380.000 |
| Phân bổ chi phí quản lý | `OH_QLY` | 642 | ALLOCATED | 640.000 |

**Σ Cost Fact = 25.582.432 đ = chi phí thực tế của đơn hàng.** Nhìn bucket `NC_SX` = hấp thụ 2.002.000 + chênh lệch 132.000 = 2.134.000.

### Bước 9 — Mapping và lưới so sánh

Mapping đưa Q, S, A về cùng lưới `(bucket, tài khoản)`. Hai điểm đáng chú ý trong ví dụ:
- **Q** có `OH_QLY` gộp: tách **40% → 627, 60% → 642** → 277.006 / 415.508.
- `OH_SX`, `KHAC`, `SCRAP_REC` **không có trong Q**: Q = 0 ở các bucket này (nhưng A, S có).

**Bảng theo Cost Bucket** (2 bộ) — dùng cho sản xuất, mua hàng, quản lý:

| Bucket | Q báo giá | S rev 1 (lúc đặt hàng) | S rev 2 (lúc thả SX) | A thực tế | A − S rev 2 | A − Q |
|---|---:|---:|---:|---:|---:|---:|
| `VL_NHOM` Nhôm | 9.362.474 | 8.452.946 | 8.598.720 | 8.879.632 | +280.912 | -482.842 |
| `VL_KINH` Kính | 7.143.570 | 6.837.896 | 6.837.896 | 7.755.000 | +917.104 | +611.430 |
| `VL_VTP` Vật tư phụ | 420.892 | 402.566 | 402.566 | 452.000 | +49.434 | +31.108 |
| `VL_PK` Phụ kiện | 3.322.000 | 2.937.600 | 2.937.600 | 2.961.000 | +23.400 | -361.000 |
| `SCRAP_REC` Thu hồi phế liệu | 0 | 0 | 0 | -152.000 | -152.000 | -152.000 |
| `NC_SX` Nhân công SX | 1.619.914 | 1.832.000 | 1.832.000 | 2.134.000 | +302.000 | +514.086 |
| `NC_LD` Nhân công lắp đặt | 1.214.936 | 1.200.000 | 1.200.000 | 1.350.000 | +150.000 | +135.064 |
| `OH_SX` CP chung SX | 0 | 481.600 | 481.600 | 582.800 | +101.200 | +582.800 |
| `OH_VC` Vận chuyển | 607.468 | 349.440 | 349.440 | 380.000 | +30.560 | -227.468 |
| `OH_QLY` Quản lý | 692.514 | 541.576 | 545.220 | 640.000 | +94.780 | -52.514 |
| `KHAC` Phát sinh ngoài KH | 0 | 0 | 0 | 600.000 | +600.000 | +600.000 |
| **Giá thành** | 24.383.768 | 23.035.624 | 23.185.042 | 25.582.432 | +2.397.390 | +1.198.664 |

**Bảng theo Tài khoản** (kế toán):

| Tài khoản | Q | S rev 2 | A | A − S | A − Q |
|---|---:|---:|---:|---:|---:|
| 621 NVL trực tiếp | 20.248.936 | 18.776.782 | 19.895.632 | +1.118.850 | -353.304 |
| 622 Nhân công trực tiếp | 2.834.850 | 3.032.000 | 3.484.000 | +452.000 | +649.150 |
| 627 Chi phí SX chung & dịch vụ ngoài | 277.006 | 481.600 | 1.182.800 | +701.200 | +905.794 |
| 641 Chi phí bán hàng | 607.468 | 349.440 | 380.000 | +30.560 | -227.468 |
| 642 Chi phí quản lý | 415.508 | 545.220 | 640.000 | +94.780 | +224.492 |
| **Tổng** | 24.383.768 | 23.185.042 | 25.582.432 | +2.397.390 | +1.198.664 |

**Kiểm tra đóng (tự động):** Σ theo bucket = Σ theo tài khoản = Σ Cost Fact: Q **24.383.768** ✔ · S **23.185.042** ✔ · A **25.582.432** ✔; mọi Cost Fact thuộc đúng một bucket (không còn `UNMAPPED`).

### Bước 10 — Đọc kết quả

#### 10.1 Cầu nối sang P&L của kế toán

| Dòng P&L | Số tiền (đ) | Nguồn / giải thích |
|---|---:|---|
| Doanh thu (511) | 28.002.318 | Sales Invoice sau giảm 1% |
| Giá vốn (632) | 24.562.432 | giá trị thành phẩm 22.424.032 + chênh lệch NC/chung 188.400 + lắp đặt 1.350.000 + thuê cẩu 600.000 |
| **Lợi nhuận gộp** | 3.439.886 | = doanh thu − giá vốn 632 (632 = 621 + 622 + 627 của lớp A) |
| Chi phí bán hàng (641) | 380.000 |  |
| Chi phí quản lý (642) | 640.000 |  |
| **Lợi nhuận hoạt động** | 2.419.886 | = doanh thu − chi phí thực tế A (25.582.432) |

→ Chi phí thực tế A (25.582.432) **đúng bằng** giá vốn + chi phí kỳ trên P&L (24.562.432 + 380.000 + 640.000): lớp A khớp sổ cái.

#### 10.2 Phân tích chênh lệch (S rev 2 → A)

| Vật tư | Định mức (S rev 2) | Thực tế (A) | Chênh lệch giá | Chênh lệch lượng | Tổng A−S |
|---|---|---|---:|---:|---:|
| Nhôm | 76,98 kg × 111.693,48 | 79,50 kg × 111.693,48 | 0 | +280.914 | +280.912 |
| Kính | 9,74 m² × 702.000 | 11,00 m² × 705.000 | +33.000 | +884.104 | +917.104 |

- **Nhôm: chênh lệch giá ≈ 0** vì S đã tự cập nhật theo giá nhập + cước ở Bước 3 (đó là lợi ích của định mức realtime). Phần lệch là **lượng** (cắt lại 1 thanh). (Chênh 2 đ giữa các cột là do làm tròn từng dòng.)
- **Kính:** lệch lượng lớn (kính vỡ) + lệch giá nhỏ (705.000 vs 702.000).

| Công đoạn | Định mức | Thực tế | Chênh lệch đơn giá giờ | Chênh lệch hiệu suất (giờ) | Tổng |
|---|---|---|---:|---:|---:|
| Cắt nhôm | 2,4 h × 95.000 | 2,6 h × 98.000 | +7.800 | +19.000 | +26.800 |
| Lắp ráp khung/cánh | 10,0 h × 110.000 | 10,8 h × 118.000 | +86.400 | +88.000 | +174.400 |
| Lắp kính | 4,8 h × 105.000 | 5,4 h × 112.000 | +37.800 | +63.000 | +100.800 |

Tổng nhân công SX: **+302.000** (= A 2.134.000 − S 1.832.000). Bộ phận sản xuất thấy rõ: lắp ráp tốn thêm 0,8 giờ và tăng ca đẩy đơn giá; lắp kính tốn thêm 0,6 giờ do làm lại tấm kính vỡ.

#### 10.3 Cầu nối lợi nhuận: Báo giá → Thực tế

| Bước | Tác động (đ) | Luỹ kế (đ) |
|---|---:|---:|
| Lợi nhuận theo báo giá (doanh thu − giá thành đầy đủ) | 3.901.402 | 3.901.402 |
| Giảm giá cho khách (1%) | -282.852 | 3.618.550 |
| Nhôm | +482.842 | 4.101.392 |
| Kính | -611.430 | 3.489.962 |
| Vật tư phụ | -31.108 | 3.458.854 |
| Phụ kiện | +361.000 | 3.819.854 |
| Thu hồi phế liệu | +152.000 | 3.971.854 |
| Nhân công SX | -514.086 | 3.457.768 |
| Nhân công lắp đặt | -135.064 | 3.322.704 |
| CP chung SX | -582.800 | 2.739.904 |
| Vận chuyển | +227.468 | 2.967.372 |
| Quản lý | +52.514 | 3.019.886 |
| Phát sinh ngoài KH | -600.000 | 2.419.886 |
| **Lợi nhuận thực tế** (= lợi nhuận hoạt động ở 10.1) |  | 2.419.886 |

Biên lợi nhuận (trên doanh thu): báo giá **13,8%** → thực tế **8,6%**.

#### 10.4 Kết luận quản trị từ ví dụ

| Bộ phận | Điều thấy được | Hành động |
|---------|----------------|-----------|
| **Mua hàng** | giá nhôm tăng do nhập + cước (đã phản ánh vào S) | đàm phán lại, hoặc đưa cước vào bảng giá chuẩn của báo giá |
| **Sản xuất** | hao hụt kính vượt (vỡ), nhôm cắt lại, giờ lắp ráp/lắp kính vượt | xem quy trình vận chuyển/lắp kính; cập nhật định mức nếu hợp lý |
| **Kinh doanh** | `NC_SX` 8% × vật liệu của báo giá lệch so với giờ công thật; thuê cẩu không có trong báo giá | tách nhân công theo giờ; thêm khoản "thiết bị nâng/phát sinh" |
| **Kế toán** | khớp 621/622/627/641/642 giữa Q–S–A, khoản `KHAC` bất thường | duyệt mapping; kiểm soát chi phí ngoài kế hoạch |
| **Quản lý** | biên lợi nhuận từ 13,8% xuống 8,6% | quyết định điều chỉnh giá/định mức cho đơn sau |

---

## 5. THIẾT LẬP TỐI THIỂU ĐỂ LỚP A ĐÚNG

| # | Việc | Kiểm tra |
|---|------|----------|
| 1 | Mọi chứng từ chi phí của công trình có **Project** | báo cáo "chứng từ thiếu Project" = 0 |
| 2 | Có Accounting Dimension `AL Cost Bucket` + tự gán theo vật tư/tài khoản | Stock Entry/PI mới tự có bucket |
| 3 | Bảng mapping bucket ↔ tài khoản ↔ cost center đầy đủ, tỷ trọng = 100% | kiểm tra đóng không báo lệch |
| 4 | Workstation/Operation có đơn giá giờ; Job Card được ghi giờ thật | có giờ thực tế để tính hiệu suất |
| 5 | Chạy `Cost Allocation Run` cuối mỗi kỳ | chi phí chung/lương được phân bổ |
| 6 | Collector chạy theo kỳ và khi có chứng từ lùi ngày | không còn snapshot `Stale` |
| 7 | Bucket `UNMAPPED` được xử lý hằng tuần | số dư `UNMAPPED` ≈ 0 |

## 6. NHỮNG ĐIỂM CÒN PHỤ THUỘC XÁC MINH TRÊN SITE (⚠)

1. Tên và cách ghi các tài khoản chênh lệch/hấp thụ (Expenses Included In Valuation, TK chênh lệch) theo Chart of Accounts và phiên bản ERPNext của bạn.
2. Việc Accounting Dimension `AL Cost Bucket` đi vào GL Entry cho Stock Entry/Job Card (và xung đột tên field với `Journal Entry.al_cost_bucket` hiện có).
3. Cách Sales Order Item nhận `al_bom*` từ Quotation Item (hiện repo chưa có custom field cho Sales Order Item).
4. Cách tính chi phí vận hành của Workstation theo phiên bản (một giá giờ hay nhiều thành phần).
5. Toàn bộ lớp S và A là **thiết kế đề xuất**, chưa có code trong repo.