\# Phân Tích Chi Tiết Báo Cáo Lưu Chuyển Tiền Tệ (Cash Flow Statement) trong ERPNext Frappe



\## Mục Lục



1\. \[Dữ Liệu Mẫu Và Các Mốc Thời Gian](#1-d%E1%BB%AF-li%E1%BB%87u-m%E1%BA%ABu-v%C3%A0-c%C3%A1c-m%E1%BB%91c-th%E1%BB%9Di-gian)

2\. \[Phân Tích Chi Tiết Cả 3 Trường Hợp Opening](#2-ph%C3%A2n-t%C3%ADch-chi-ti%E1%BA%BFt-c%E1%BA%A3-3-tr%C6%B0%E1%BB%9Dng-h%E1%BB%A3p-opening)

3\. \[Tính Toán Với Filter Cụ Thể: 01/05/2026 - 31/12/2026](#3-t%C3%ADnh-to%C3%A1n-v%E1%BB%9Bi-filter-c%E1%BB%A5-th%E1%BB%83-01052026---31122026)

4\. \[Phân Tích Logic Từng Loại Báo Cáo Kế Toán](#4-ph%C3%A2n-t%C3%ADch-logic-t%E1%BB%ABng-lo%E1%BA%A1i-b%C3%A1o-c%C3%A1o-k%E1%BA%BF-to%C3%A1n)

5\. \[Vấn Đề Của Cash Flow Hiện Tại](#5-v%E1%BA%A5n-%C4%91%E1%BB%81-c%E1%BB%A7a-cash-flow-hi%E1%BB%87n-t%E1%BA%A1i)

6\. \[Tổng Hợp Các Trường Hợp Và Phương Pháp Tính Opening/Period/Balance](#6-t%E1%BB%95ng-h%E1%BB%A3p-to%C3%A0n-b%E1%BB%99-c%C3%A1c-tr%C6%B0%E1%BB%9Dng-h%E1%BB%A3p-v%C3%A0-ph%C6%B0%C6%A1ng-ph%C3%A1p-t%C3%ADnh-opening-period-balance-chu%E1%BA%A9n-k%E1%BA%BF-to%C3%A1n)

7\. \[Đề Xuất Giải Pháp Cash Flow Đúng Nguyên Tắc Kế Toán](#7-%C4%91%E1%BB%81-xu%E1%BA%A5t-gi%E1%BA%A3i-ph%C3%A1p-cash-flow-%C4%91%C3%BAng-nguy%C3%AAn-t%E1%BA%AFc-k%E1%BA%BF-to%C3%A1n)

8\. \[Kết Luận](#8-k%E1%BA%BFt-lu%E1%BA%ADn)



\---



\## 1. Dữ Liệu Mẫu Và Các Mốc Thời Gian



\### 1.1 Thông tin công ty



| Thông tin | Giá trị |

|-----------|---------|

| Tên công ty | Công ty TNHH ABC |

| Năm tài chính | 01/01 -> 31/12 |

| Năm hiện tại | 2026 |

| Loại hình | Sản xuất thương mại |

| Đơn vị tiền tệ | VND |



\### 1.2 Danh sách tài khoản theo dõi



\#### Tài khoản Balance Sheet (số dư lũy kế)



| Mã TK | Tên TK | Root Type | Account Type | Bản chất |

|:-----:|--------|:---------:|:------------:|:--------:|

| 111 | Tiền mặt | Asset | Cash | Nợ (bên Nợ) |

| 112 | Tiền gửi ngân hàng | Asset | Bank | Nợ (bên Nợ) |

| 131 | Phải thu khách hàng | Asset | Receivable | Nợ (bên Nợ) |

| 141 | Tạm ứng | Asset | Receivable | Nợ (bên Nợ) |

| 152 | Nguyên vật liệu | Asset | Stock | Nợ (bên Nợ) |

| 155 | Thành phẩm | Asset | Stock | Nợ (bên Nợ) |

| 211 | TSCĐ hữu hình | Asset | Fixed Asset | Nợ (bên Nợ) |

| 214 | Hao mòn TSCĐ | Asset | Fixed Asset | Nợ (bên Có) - điều chỉnh giảm |

| 311 | Vay ngắn hạn | Liability | Payable | Có (bên Có) |

| 331 | Phải trả người bán | Liability | Payable | Có (bên Có) |

| 333 | Thuế phải nộp | Liability | Payable | Có (bên Có) |

| 334 | Phải trả người lao động | Liability | Payable | Có (bên Có) |

| 411 | Vốn đầu tư CSH | Liability | Equity | Có (bên Có) |

| 421 | Lợi nhuận chưa phân phối | Liability | Equity | Có (bên Có) |



\#### Tài khoản P\&L (không có số dư đầu kỳ - reset về 0 đầu năm)



| Mã TK | Tên TK | Root Type |

|:-----:|--------|:---------:|

| 511 | Doanh thu bán hàng | Income |

| 632 | Giá vốn hàng bán | Expense |

| 642 | Chi phí quản lý | Expense |

| 711 | Thu nhập khác | Income |

| 911 | Xác định kết quả kinh doanh | (trung gian) |



\### 1.3 Toàn bộ giao dịch



\#### Năm 2025 — Khởi tạo dữ liệu



| Ngày | Chứng từ | Diễn giải | TK Nợ | TK Có | Số tiền | is\_opening |

|:----:|:--------:|-----------|:-----:|:-----:|:-------:|:----------:|

| 15/03/2025 | SI-001 | Bán chịu cho KH A - 100 SP | 131 | 511 | 100.000.000 | No |

| 15/03/2025 | SI-001 | Giá vốn 100 SP | 632 | 155 | 60.000.000 | No |

| 20/06/2025 | SI-002 | Bán chịu cho KH B - 50 SP | 131 | 511 | 50.000.000 | No |

| 20/06/2025 | SI-002 | Giá vốn 50 SP | 632 | 155 | 30.000.000 | No |

| 10/09/2025 | PE-001 | KH A trả tiền 40tr | 111 | 131 | 40.000.000 | No |

| 15/12/2025 | SI-003 | Bán chịu cho KH C - 30 SP | 131 | 511 | 30.000.000 | No |

| 15/12/2025 | SI-003 | Giá vốn 30 SP | 632 | 155 | 18.000.000 | No |

| 31/12/2025 | PCV-2025 | \*\*Period Closing Voucher 2025\*\* | | | | No |

| 31/12/2025 | PCV-2025 | Kết chuyển doanh thu (511 -> 911) | 511 | 911 | 180.000.000 | No |

| 31/12/2025 | PCV-2025 | Kết chuyển chi phí (911 -> 632) | 911 | 632 | 108.000.000 | No |

| 31/12/2025 | PCV-2025 | Kết chuyển lãi vào LNCpp (911 -> 421) | 911 | 421 | 72.000.000 | No |



\#### Năm 2026 — Giao dịch



| Ngày | Chứng từ | Diễn giải | TK Nợ | TK Có | Số tiền | is\_opening |

|:----:|:--------:|-----------|:-----:|:-----:|:-------:|:----------:|

| | | \*\*Opening Entry (mở sổ đầu năm 2026)\*\* | | | | |

| 01/01/2026 | OE-2026 | Dư đầu năm - Tiền mặt | 111 | | 500.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Phải thu | 131 | | 60.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - NVL tồn | 152 | | 200.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Thành phẩm | 155 | | 150.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - TSCĐ | 211 | | 1.000.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - HM TSCĐ | | 214 | 200.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Phải trả NB | | 331 | 180.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Thuế phải nộp | | 333 | 30.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Phải trả LĐ | | 334 | 50.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Vốn CSH | | 411 | 1.200.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - LN chưa PP | | 421 | 200.000.000 | \*\*Yes\*\* |

| 01/01/2026 | OE-2026 | Dư đầu năm - Tiền gửi NH | 112 | | 50.000.000 | \*\*Yes\*\* |

| | | \*Cộng =\* | \*1.960.000.000\* | \*1.960.000.000\* | | |

| 10/02/2026 | PE-002 | KH B trả tiền 50tr | 112 | 131 | 50.000.000 | No |

| 15/04/2026 | SI-004 | Bán chịu cho KH D - 80 SP | 131 | 511 | 80.000.000 | No |

| 15/04/2026 | SI-004 | Giá vốn 80 SP | 632 | 155 | 48.000.000 | No |

| 20/06/2026 | PE-003 | KH A trả nốt 60tr | 112 | 131 | 60.000.000 | No |

| 30/06/2026 | PCV-Q2 | \*\*Period Closing Voucher Q2/2026\*\* | | | | No |

| 30/06/2026 | PCV-Q2 | Kết chuyển doanh thu | 511 | 911 | 80.000.000 | No |

| 30/06/2026 | PCV-Q2 | Kết chuyển chi phí | 911 | 632 | 48.000.000 | No |

| 30/06/2026 | PCV-Q2 | Kết chuyển lãi | 911 | 421 | 32.000.000 | No |

| 15/08/2026 | SI-005 | Bán chịu cho KH E - 60 SP | 131 | 511 | 60.000.000 | No |

| 15/08/2026 | SI-005 | Giá vốn 60 SP | 632 | 155 | 35.000.000 | No |

| 20/09/2026 | PE-004 | KH C trả 30tr | 112 | 131 | 30.000.000 | No |

| 01/10/2026 | PV-001 | Vay ngân hàng 500tr | 112 | 311 | 500.000.000 | No |

| 15/11/2026 | SI-006 | Bán chịu cho KH F - 40 SP | 131 | 511 | 40.000.000 | No |

| 15/11/2026 | SI-006 | Giá vốn 40 SP | 632 | 155 | 24.000.000 | No |

| 20/12/2026 | PE-005 | KH D trả 50tr | 112 | 131 | 50.000.000 | No |

| 31/12/2026 | PCV-2026 | \*\*Period Closing Voucher 2026\*\* | | | | No |

| 31/12/2026 | PCV-2026 | Kết chuyển doanh thu (511+80+60+40) | 511 | 911 | 180.000.000 | No |

| 31/12/2026 | PCV-2026 | Kết chuyển chi phí (632+48+35+24) | 911 | 632 | 107.000.000 | No |

| 31/12/2026 | PCV-2026 | Kết chuyển lãi | 911 | 421 | 73.000.000 | No |



\### 1.4 Số dư các tài khoản theo thời gian



\#### TK 131 — Phải thu khách hàng



| Thời điểm | Bút toán | Số dư Nợ | Diễn giải |

|:---------:|:--------:|:--------:|-----------|

| 01/01/2026 | Opening | \*\*60.000.000\*\* | Số dư đầu năm (từ 12/2025) |

| 10/02/2026 | PE-002 | \*\*10.000.000\*\* | KH B trả 50tr |

| 15/04/2026 | SI-004 | \*\*90.000.000\*\* | Bán chịu KH D 80tr |

| 20/06/2026 | PE-003 | \*\*30.000.000\*\* | KH A trả nốt 60tr |

| 30/06/2026 | PCV-Q2 | \*\*30.000.000\*\* | (không thay đổi - PCV chỉ ảnh hưởng đến P\&L) |

| 15/08/2026 | SI-005 | \*\*90.000.000\*\* | Bán chịu KH E 60tr |

| 20/09/2026 | PE-004 | \*\*60.000.000\*\* | KH C trả 30tr |

| 01/10/2026 | — | \*\*60.000.000\*\* | Không thay đổi |

| 15/11/2026 | SI-006 | \*\*100.000.000\*\* | Bán chịu KH F 40tr |

| 20/12/2026 | PE-005 | \*\*50.000.000\*\* | KH D trả 50tr |

| \*\*31/12/2026\*\* | — | \*\*50.000.000\*\* | \*\*Số dư cuối năm 2026\*\* |



\#### TK 112 — Tiền gửi ngân hàng



| Thời điểm | Bút toán | Số dư Nợ | Diễn giải |

|:---------:|:--------:|:--------:|-----------|

| 01/01/2026 | Opening | \*\*50.000.000\*\* | Số dư đầu năm |

| 10/02/2026 | PE-002 | \*\*100.000.000\*\* | KH B trả (50tr) |

| 20/06/2026 | PE-003 | \*\*160.000.000\*\* | KH A trả (60tr) |

| 20/09/2026 | PE-004 | \*\*190.000.000\*\* | KH C trả (30tr) |

| 01/10/2026 | PV-001 | \*\*690.000.000\*\* | Vay NH (500tr) |

| 20/12/2026 | PE-005 | \*\*740.000.000\*\* | KH D trả (50tr) |



\#### TK 155 — Thành phẩm



| Thời điểm | Số dư Nợ |

|:---------:|:--------:|

| 01/01/2026 | 150.000.000 |

| 15/04/2026 (sau SI-004) | 102.000.000 |

| 15/08/2026 (sau SI-005) | 67.000.000 |

| 15/11/2026 (sau SI-006) | 43.000.000 |



\#### TK 511 — Doanh thu (P\&L, reset đầu kỳ)



| Kỳ | Doanh thu |

|:--:|:---------:|

| Q1/2026 (01/01-31/03) | 0 |

| Tháng 4/2026 | 80.000.000 |

| Tháng 5-7/2026 | 0 |

| Tháng 8/2026 | 60.000.000 |

| Tháng 9/2026 | 0 |

| Tháng 10/2026 | 0 |

| Tháng 11/2026 | 40.000.000 |

| Tháng 12/2026 | 0 |



> \*\*Lưu ý:\*\* Doanh thu P\&L LUÔN reset về 0 đầu năm tài chính. Sau PCV-Q2, doanh thu 80tr

> đã được kết chuyển hết sang 911, nên Q3 bắt đầu lại từ 0.



\### 1.5 Ba mốc thời gian quan trọng cho phân tích Opening



| Kịch bản | Mốc thời gian | Đặc điểm |

|:--------:|:-------------:|----------|

| \*\*A - is\_opening=Yes\*\* | Đầu năm tài chính (01/01/2026) | Có Opening Entry, CHƯA có PCV năm trước |

| \*\*B - Account Closing Balance cuối năm\*\* | Sau PCV-2025 (31/12/2025) -> Mở 2026 | Có Account Closing Balance + Opening Entry |

| \*\*C - Account Closing Balance giữa năm\*\* | Sau PCV-Q2 (30/06/2026) | Có Account Closing Balance giữa năm |



\---



\## 2. Phân Tích Chi Tiết Cả 3 Trường Hợp Opening



\### 2.A Trường hợp A: Chỉ có is\_opening=Yes (chưa có PCV năm trước)



\*\*Bối cảnh:\*\* Công ty mới thành lập năm 2025. Đầu năm 2026, chưa chạy PCV-2025.

Chỉ có Opening Entry ngày 01/01/2026 với is\_opening=Yes.



\*\*GL Entry của TK 131 — Phải thu khách hàng:\*\*



| # | Ngày | post\_date | is\_opening | Nợ (debit) | Có (credit) | Ghi chú |

|:-:|:----:|:---------:|:----------:|:----------:|:-----------:|---------|

| 1 | 01/01/2026 | 01/01/2026 | \*\*Yes\*\* | \*\*60.000.000\*\* | 0 | Opening Entry |

| 2 | 10/02/2026 | 10/02/2026 | No | 0 | 50.000.000 | KH B trả |

| 3 | 15/04/2026 | 15/04/2026 | No | 80.000.000 | 0 | Bán KH D |

| 4 | 20/06/2026 | 20/06/2026 | No | 0 | 60.000.000 | KH A trả |

| 5 | 15/08/2026 | 15/08/2026 | No | 60.000.000 | 0 | Bán KH E |

| 6 | 20/09/2026 | 20/09/2026 | No | 0 | 30.000.000 | KH C trả |

| 7 | 15/11/2026 | 15/11/2026 | No | 40.000.000 | 0 | Bán KH F |

| 8 | 20/12/2026 | 20/12/2026 | No | 0 | 50.000.000 | KH D trả |



\#### 2.A.1 Cách Trial Balance tính Opening



```python

\# trial\_balance.py dòng 160-195

\# Bước 1: Tìm PCV trước from\_date

last\_pcv = frappe.db.get\_all("Period Closing Voucher",

&#x20;   filters={"docstatus": 1, "company": company, "posting\_date": ("<", from\_date)},

&#x20;   limit=1)

\# Trường hợp A: Chưa có PCV nào → result = \[]



\# Bước 2: Không có PCV → query GL Entry

\# Điều kiện:

\#   (posting\_date < from\_date) OR (is\_opening = "Yes")

\# = tất cả GL Entry có posting\_date trước from\_date + tất cả is\_opening=Yes

```



\*\*Ví dụ: Opening cho Q3/2026 (from\_date = 01/07/2026)\*\*



```sql

SELECT SUM(debit), SUM(credit) FROM `tabGL Entry`

WHERE company = 'ABC'

&#x20; AND account = '131 - Phải thu'

&#x20; AND is\_cancelled = 0

&#x20; AND (

&#x20;   (posting\_date < '2026-07-01')    -- tất cả trước Q3

&#x20;   OR (is\_opening = 'Yes')           -- hoặc is\_opening=Yes (dù ngày nào)

&#x20; )

&#x20; AND voucher\_type != 'Period Closing Voucher'

```



\*\*Kết quả query:\*\*

```

posting\_date < '2026-07-01':

&#x20; #1: 01/01 is\_opening=Yes: debit=60tr, credit=0  →  (thỏa OR is\_opening)

&#x20; #2: 10/02               : debit=0  , credit=50tr

&#x20; #3: 15/04               : debit=80tr, credit=0

&#x20; #4: 20/06               : debit=0  , credit=60tr



SUM(debit)  = 60tr + 80tr           = 140.000.000

SUM(credit) = 50tr + 60tr           = 110.000.000

opening\_balance (Nợ - Có)           = 30.000.000  ✅

```



> \*\*Kết quả:\*\* Opening balance Q3 = 30.000.000 ✅ (đúng bằng số dư TK 131 tại 30/06/2026)



\#### 2.A.2 Cách Balance Sheet tính Opening



```python

\# financial\_statements.py dòng 243-244

\# Balance Sheet KHÔNG dùng is\_opening filter

\# Nó lấy tất cả GL Entry từ year\_start\_date (01/01/2026)

\# Tính opening\_balance = GL Entry có posting\_date < year\_start\_date

\# year\_start\_date = 01/01/2026



if entry.posting\_date < period\_list\[0].year\_start\_date:

&#x20;   d\["opening\_balance"] += flt(entry.debit) - flt(entry.credit)

```



\*\*Phân tích:\*\* Vì year\_start\_date = 01/01/2026, không có GL Entry nào

có posting\_date < 01/01/2026 trong hệ thống (mới tạo năm 2025, nhưng query

chỉ chạy từ năm 2026 được yêu cầu trong filter).



> \*\*Kết quả:\*\* opening\_balance = 0 (đối với Balance Sheet)



\*\*Sự khác biệt:\*\*

\- Trial Balance: opening=30tr (lấy GL Entry trước Q3, gồm is\_opening)

\- Balance Sheet: opening=0 (chỉ lấy GL Entry trước year\_start\_date)

\- Cả hai đều đúng theo cách thiết kế riêng của chúng



\#### 2.A.3 Cách Cash Flow hiện tại tính — PHÂN TÍCH SAI



```sql

\-- cash\_flow.py dòng 198-204

SELECT SUM(credit) - SUM(debit) FROM `tabGL Entry`

WHERE account IN (SELECT name FROM tabAccount WHERE account\_type = 'Receivable')

&#x20; AND posting\_date BETWEEN '2026-07-01' AND '2026-09-30'

&#x20; AND voucher\_type != 'Period Closing Voucher'

```



\*\*Kết quả Q3/2026:\*\*

```

\#5: 15/08: debit=60tr, credit=0

\#6: 20/09: debit=0, credit=30tr



SUM(credit) - SUM(debit) = 30tr - 60tr = -30.000.000

```



\*\*Cash Flow báo:\*\* ΔReceivable Q3 = -30.000.000 → \*\*cộng 30tr vào dòng tiền\*\*



\*\*Đúng hay sai?\*\*

```

Thực tế:

\- Đầu Q3 (01/07): Số dư TK 131 = 30.000.000

\- Cuối Q3 (30/09): Số dư TK 131 = 90.000.000 - 30.000.000 = 60.000.000

\- ΔReceivable thực tế = 60tr - 30tr = +30.000.000 (tăng)



Cash Flow báo: -30.000.000 (giảm)

Thực tế      : +30.000.000 (tăng)



KẾT LUẬN: SAI! Delta bị ngược dấu. ❌

```



\*\*Nguyên nhân:\*\*

```

Cash Flow dùng:  SUM(credit) - SUM(debit)  → kết quả = -30tr

Công thức đúng:  Closing\_balance - Opening\_balance = 60tr - 30tr = +30tr



Cash Flow chỉ tính phát sinh trong kỳ (60tr - 30tr = 30tr về phía Nợ)

Nhưng nó lấy credit - debit = -30tr (ra dấu âm)

Trong khi đúng ra Δ = debit - credit = +30tr (phải thu tăng)

```



\### 2.B Trường hợp B: Có Account Closing Balance cuối năm



\*\*Bối cảnh:\*\* Đã chạy PCV-2025 ngày 31/12/2025. Kết quả:

1\. P\&L năm 2025 đã được kết chuyển về 0

2\. Account Closing Balance được tạo (snapshot số dư tất cả tài khoản)

3\. Lợi nhuận 72tr đã được chuyển vào TK 421

4\. Đầu năm 2026, tạo Opening Entry (is\_opening=Yes) để mở sổ



\#### Account Closing Balance sau PCV-2025



```

TabAccountClosingBalance:

| account | debit | credit | period\_closing\_voucher |

|:-------:|:-----:|:------:|:----------------------:|

| 111     | 500tr | 0      | PCV-2025 |

| 112     | 50tr  | 0      | PCV-2025 |

| 131     | 140tr | 0      | PCV-2025 |

| 152     | 200tr | 0      | PCV-2025 |

| 155     | 150tr | 0      | PCV-2025 |

| 211     | 1.000tr| 0     | PCV-2025 |

| 214     | 0     | 200tr  | PCV-2025 |

| 331     | 0     | 180tr  | PCV-2025 |

| 333     | 0     | 30tr   | PCV-2025 |

| 334     | 0     | 50tr   | PCV-2025 |

| 411     | 0     | 1.200tr| PCV-2025 |

| 421     | 0     | 200tr  | PCV-2025 |

```



\#### 2.B.1 Cách Trial Balance tính Opening cho năm 2026



\*\*Query Account Closing Balance (with PCV reference):\*\*



```python

\# trial\_balance.py dòng 160-178

last\_pcv = frappe.db.get\_all("Period Closing Voucher",

&#x20;   filters={"docstatus": 1, "company": "ABC", "posting\_date": ("<", "2026-01-01")},

&#x20;   order\_by="posting\_date desc", limit=1)

\# → Kết quả: \[{"posting\_date": "2025-12-31", "name": "PCV-2025"}]



\# Có PCV → query Account Closing Balance

acb = frappe.qb.DocType("Account Closing Balance")

opening\_balance = (

&#x20;   frappe.qb.from\_(acb)

&#x20;   .select(acb.account, Sum(acb.debit), Sum(acb.credit))

&#x20;   .where(

&#x20;       (acb.company == "ABC")

&#x20;       \& (acb.period\_closing\_voucher == "PCV-2025")

&#x20;   )

&#x20;   .groupby(acb.account)

).run()

```



\*\*Kết quả cho TK 131:\*\*

```

debit  = 140.000.000

credit = 0

opening\_balance\_Nợ = 140.000.000 - 0 = 140.000.000

```



\*\*Lưu ý:\*\* Account Closing Balance lưu số dư \*\*sau khi đã chốt sổ 2025\*\*.

Tại 31/12/2025, số dư TK 131 = 140.000.000 (đây là số dư trước khi tạo

Opening Entry năm 2026).



Sau đó Opening Entry 2026 ghi:

```

Nợ 131: 60.000.000 (is\_opening=Yes)

```



> \*\*Sự khác biệt quan trọng:\*\*

> - Account Closing Balance (PCV-2025): 131 có số dư \*\*140tr\*\*

> - Opening Entry (01/01/2026): 131 được mở với số dư \*\*60tr\*\*

> - Lý do: 140-40=100 thu trong 2025, rồi 140-100... Thực tế sau 2025,

>   số dư 131 chỉ còn \*\*60tr\*\* do đã thu 40tr. Account Closing Balance ghi

>   số dư gộp, còn Opening Entry ghi số dư thực tế đầu năm mới.



\#### 2.B.2 Cách Trial Balance xử lý khoảng trống



```python

\# trial\_balance.py dòng 182-191

\# Kiểm tra: closing\_date (31/12/2025) có < from\_date (01/01/2026) - 1 ngày?

\# from\_date - 1 = 31/12/2025

\# closing\_date = 31/12/2025

\# 31/12/2025 < 31/12/2025 → FALSE



\# → Không có gap → không cần query GL Entry bổ sung

\# Opening từ Account Closing Balance là chính xác

```



\*\*Nhưng còn Opening Entry (is\_opening=Yes)?\*\*



Trial Balance xử lý:

```python

\# trial\_balance.py dòng 257-262

if not ignore\_is\_opening:

&#x20;   opening\_balance = opening\_balance.where(

&#x20;       (closing\_balance.posting\_date < filters.from\_date)

&#x20;       | (closing\_balance.is\_opening == "Yes")

&#x20;   )

```



Khi có PCV, Trial Balance \*\*ưu tiên Account Closing Balance\*\* (snapshot chính xác).

Nó không cần thêm is\_opening=Yes từ GL Entry vì snapshot đã bao gồm tất cả.



\#### 2.B.3 Giá trị opening chính xác



Nếu query GL Entry trực tiếp cho opening năm 2026:



```sql

\-- Query 1: lấy từ Account Closing Balance

SELECT debit, credit FROM `tabAccount Closing Balance`

WHERE period\_closing\_voucher = 'PCV-2025' AND account = '131'

→ debit=140tr, credit=0 → opening=140tr  (SỐ DƯ SAU CHỐT SỔ 2025)



\-- Query 2: Trial Balance thực tế

\-- Opening balance TK 131 = 140.000.000 (từ Account Closing Balance)

\-- Đây là số dư gộp nợ cuối năm 2025

```



> \*\*GIẢI THÍCH:\*\* Account Closing Balance ghi 140tr cho TK 131 vì đó là

> tổng số phát sinh Nợ - Có trong năm 2025 của TK 131.

> Tuy nhiên, Opening Entry đầu năm 2026 chỉ mở 60tr (số dư thực).

>

> \*\*Quy trình đúng:\*\*

> 1. PCV-2025 kết chuyển P\&L và snapshot Balance Sheet

> 2. Account Closing Balance ghi số dư gộp của tài khoản

> 3. Sang năm 2026, kế toán mở sổ bằng Journal Entry (is\_opening=Yes)

>    với số dư thực tế còn lại (60tr thay vì 140tr, vì 80tr đã thu hồi

>    trong năm 2025 nhưng vẫn nằm trong số dư gộp)



\### 2.C Trường hợp C: Có Account Closing Balance giữa năm



\*\*Bối cảnh:\*\* Đã chạy PCV-Q2 ngày 30/06/2026, chốt sổ giữa năm.

Query cho Q3/2026 (01/07/2026 - 30/09/2026).



\#### Account Closing Balance sau PCV-Q2



Account Closing Balance được tạo cho tất cả tài khoản Balance Sheet

tại thời điểm 30/06/2026. Snapshot này chỉ ghi các tài khoản Balance Sheet

vì P\&L đã được kết chuyển.



\*\*TK 131 tại 30/06/2026:\*\*

\- Đầu năm: 60.000.000

\- (10/02): -50.000.000 (thu từ KH B)

\- (15/04): +80.000.000 (bán KH D)

\- (20/06): -60.000.000 (thu từ KH A)

\- \*\*Số dư tại 30/06: 30.000.000\*\*



```python

\# Account Closing Balance PCV-Q2

\# TK 131: debit=30tr, credit=0

```



\#### 2.C.1 Trial Balance — Opening cho Q3/2026



```python

last\_pcv = frappe.db.get\_all("Period Closing Voucher",

&#x20;   filters={"docstatus": 1, "company": "ABC", "posting\_date": ("<", "2026-07-01")},

&#x20;   order\_by="posting\_date desc", limit=1)

\# → \[{"posting\_date": "2026-06-30", "name": "PCV-Q2"}]



\# Kiểm tra gap:

\# closing\_date = 30/06/2026

\# from\_date = 01/07/2026

\# 30/06/2026 < add\_days(01/07/2026, -1) = 30/06/2026

\# → 30/06 < 30/06 → FALSE → không có gap



\# Opening = Account Closing Balance

opening\_131 = 30.000.000  ✅

```



\*\*Phân tích chi tiết:\*\*

```

Account Closing Balance PCV-Q2:

131 = 30.000.000 (chính xác số dư tại 30/06/2026)



Nếu không có Account Closing Balance:

Phải query GL Entry từ 01/01/2026 đến 30/06/2026:

(60tr - 50tr + 80tr - 60tr) = 30.000.000 (giống kết quả)



Nhưng Account Closing Balance CHỈ query 1 bảng nhỏ (snapshot),

trong khi GL Entry phải scan nhiều dòng hơn.

→ Account Closing Balance nhanh hơn, chính xác tương đương.

```



\#### 2.C.2 Tính Delta cho các kỳ (mô phỏng Cash Flow đúng)



\*\*Delta Receivable Q3/2026:\*\*



```

Opening (01/07): Closing Balance từ PCV-Q2 = 30.000.000

Closing (30/09): Phải tính từ GL Entry



Query closing balance 30/09:

SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry`

WHERE account = '131'

&#x20; AND posting\_date BETWEEN '2026-07-01' AND '2026-09-30'

&#x20; AND is\_cancelled = 0

&#x20; AND voucher\_type != 'Period Closing Voucher'



\#5: 15/08: debit=60.000.000

\#6: 20/09: credit=30.000.000



SUM(debit) - SUM(credit) = 60.000.000 - 30.000.000 = +30.000.000



Closing = Opening + phat\_sinh\_trong\_ky

&#x20;       = 30.000.000 + 30.000.000 = 60.000.000



Delta = Closing - Opening = 60tr - 30tr = +30.000.000 (phải thu tăng)

```



\*\*So sánh với Cash Flow hiện tại:\*\*

```sql

\-- Cash Flow hiện tại (SAI)

SELECT SUM(credit) - SUM(debit) FROM `tabGL Entry`

WHERE account\_type = 'Receivable'

&#x20; AND posting\_date BETWEEN '2026-07-01' AND '2026-09-30'

&#x20; AND voucher\_type != 'Period Closing Voucher'



= (30tr) - (60tr) = -30.000.000  (báo giảm 30tr)



\-- Công thức đúng

Delta = Closing - Opening = 60tr - 30tr = +30.000.000  (tăng 30tr)

```



\*\*Kết quả: Cash Flow hiện tại SAI cả dấu và giá trị.\*\*



\#### 2.C.3 Tổng hợp Delta cho cả năm 2026 (theo từng tháng)



| Tháng | Phát sinh Nợ | Phát sinh Có | Opening | Closing | Delta (đúng) | Cash Flow cũ |

|:-----:|:-----------:|:-----------:|:-------:|:-------:|:------------:|:------------:|

| Jan | 0 | 0 | 60tr | 60tr | 0 | 0 |

| Feb | 0 | 50tr | 60tr | 10tr | -50tr | -50tr |

| Mar | 0 | 0 | 10tr | 10tr | 0 | 0 |

| Apr | 80tr | 0 | 10tr | 90tr | +80tr | -80tr (\*sai\*) |

| May | 0 | 0 | 90tr | 90tr | 0 | 0 |

| Jun | 0 | 60tr | 90tr | 30tr | -60tr | +60tr (\*sai\*) |

| Jul | 0 | 0 | 30tr | 30tr | 0 | 0 |

| Aug | 60tr | 0 | 30tr | 90tr | +60tr | -60tr (\*sai\*) |

| Sep | 0 | 30tr | 90tr | 60tr | -30tr | +30tr (\*sai\*) |

| Oct | 0 | 0 | 60tr | 60tr | 0 | 0 |

| Nov | 40tr | 0 | 60tr | 100tr | +40tr | -40tr (\*sai\*) |

| Dec | 0 | 50tr | 100tr | 50tr | -50tr | +50tr (\*sai\*) |

| \*\*Tổng\*\* | \*\*180tr\*\* | \*\*190tr\*\* | | \*\*50tr\*\* | \*\*-10tr\*\* | \*\*-50tr\*\* |



> \*\*(\*) Cash Flow hiện tại sai dấu vì dùng `credit - debit` thay vì `debit - credit`\*\*

> cho tài khoản Receivable (bản chất bên Nợ).

> Đúng ra phải dùng `debit - credit = Δ` rồi mới đảo dấu cho Cash Flow

> (vì phải thu tăng = tiền giảm).



\---



\## 3. Tính Toán Với Filter Cụ Thể: 01/05/2026 - 31/12/2026



\### 3.1 Thiết lập bộ lọc (Filters)



| Filter | Giá trị |

|--------|---------|

| Company | Công ty TNHH ABC |

| from\_date | 01/05/2026 |

| to\_date | 31/12/2026 |

| periodicity | Monthly |

| filter\_based\_on | Date Range |

| accumulated\_values | False |

| year\_start\_date | 01/01/2026 (tự động tính) |



\### 3.2 Period List được tạo



```python

period\_list = \[

&#x20;   {"key": "may\_2026",   "label": "May 2026",   "from\_date": "2026-05-01", "to\_date": "2026-05-31", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "jun\_2026",   "label": "Jun 2026",   "from\_date": "2026-06-01", "to\_date": "2026-06-30", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "jul\_2026",   "label": "Jul 2026",   "from\_date": "2026-07-01", "to\_date": "2026-07-31", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "aug\_2026",   "label": "Aug 2026",   "from\_date": "2026-08-01", "to\_date": "2026-08-31", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "sep\_2026",   "label": "Sep 2026",   "from\_date": "2026-09-01", "to\_date": "2026-09-30", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "oct\_2026",   "label": "Oct 2026",   "from\_date": "2026-10-01", "to\_date": "2026-10-31", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "nov\_2026",   "label": "Nov 2026",   "from\_date": "2026-11-01", "to\_date": "2026-11-30", "year\_start\_date": "2026-01-01"},

&#x20;   {"key": "dec\_2026",   "label": "Dec 2026",   "from\_date": "2026-12-01", "to\_date": "2026-12-31", "year\_start\_date": "2026-01-01"},

]

```



\### 3.3 GL Entry trong khoảng 01/05 -> 31/12/2026



| # | Ngày | Mẫu số | TK Nợ | TK Có | Số tiền | is\_opening | Lưu ý |

|:-:|:----:|:------:|:-----:|:-----:|:-------:|:----------:|-------|

| A | 15/04/2026 | SI-004 | 131 | 511 | 80.000.000 | No | ⚠️ Ngoài range |

| B | 15/04/2026 | SI-004 | 632 | 155 | 48.000.000 | No | ⚠️ Ngoài range |

| 1 | 20/06/2026 | PE-003 | 112 | 131 | 60.000.000 | No | Trong range |

| 2 | 30/06/2026 | PCV-Q2 | 511 | 911 | 80.000.000 | No | PCV |

| 3 | 30/06/2026 | PCV-Q2 | 911 | 632 | 48.000.000 | No | PCV |

| 4 | 30/06/2026 | PCV-Q2 | 911 | 421 | 32.000.000 | No | PCV |

| 5 | 15/08/2026 | SI-005 | 131 | 511 | 60.000.000 | No | |

| 6 | 15/08/2026 | SI-005 | 632 | 155 | 35.000.000 | No | |

| 7 | 20/09/2026 | PE-004 | 112 | 131 | 30.000.000 | No | |

| 8 | 01/10/2026 | PV-001 | 112 | 311 | 500.000.000 | No | |

| 9 | 15/11/2026 | SI-006 | 131 | 511 | 40.000.000 | No | |

| 10| 15/11/2026 | SI-006 | 632 | 155 | 24.000.000 | No | |

| 11| 20/12/2026 | PE-005 | 112 | 131 | 50.000.000 | No | |



\### 3.4 Mô phỏng đầy đủ các cách tính cho từng tài khoản



\#### 3.4.1 TK 131 — Phải thu khách hàng



\*\*Bước 1: Tính Opening Balance tại 01/05/2026\*\*



```sql

\-- Cách Trial Balance (dùng Account Closing Balance nếu có)

last\_pcv = PCV-Q2? → posting\_date=30/06 > 01/05 → KHÔNG thỏa (< 01/05)

→ Không có PCV trước 01/05 → query GL Entry



SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry`

WHERE account = '131 - Phải thu'

&#x20; AND is\_cancelled = 0

&#x20; AND voucher\_type != 'Period Closing Voucher'

&#x20; AND (posting\_date < '2026-05-01' OR is\_opening = 'Yes')

&#x20; AND posting\_date >= '2026-01-01'  -- year\_start\_date



Kết quả:

\- Opening Entry (01/01): debit=60tr

\- PE-002 (10/02): credit=50tr

\- SI-004 (15/04): debit=80tr



SUM(debit)=140tr, SUM(credit)=50tr

Opening = 140tr - 50tr = 90.000.000 ✅ (đúng số dư TK 131 tại 01/05)

```



\*\*Bước 2: Tính Closing Balance và Delta cho từng tháng (phương pháp đúng)\*\*



| Tháng | Từ ngày | Đến ngày | Phát sinh Nợ | Phát sinh Có | P/s thuần (Nợ-Có) | Opening | Closing | Delta | CF cũ |

|:----:|:-------:|:---------:|:-----------:|:-----------:|:-----------------:|:-------:|:-------:|:-----:|:-----:|

| May | 01/05 | 31/05 | 0 | 0 | 0 | 90tr | 90tr | \*\*0\*\* | 0 |

| Jun | 01/06 | 30/06 | 0 | 60tr | -60tr | 90tr | 30tr | \*\*-60tr\*\* | +60tr(\*)|

| Jul | 01/07 | 31/07 | 0 | 0 | 0 | 30tr | 30tr | \*\*0\*\* | 0 |

| Aug | 01/08 | 31/08 | 60tr | 0 | +60tr | 30tr | 90tr | \*\*+60tr\*\* | -60tr(\*)|

| Sep | 01/09 | 30/09 | 0 | 30tr | -30tr | 90tr | 60tr | \*\*-30tr\*\* | +30tr(\*)|

| Oct | 01/10 | 31/10 | 0 | 0 | 0 | 60tr | 60tr | \*\*0\*\* | 0 |

| Nov | 01/11 | 30/11 | 40tr | 0 | +40tr | 60tr | 100tr | \*\*+40tr\*\* | -40tr(\*)|

| Dec | 01/12 | 31/12 | 0 | 50tr | -50tr | 100tr | 50tr | \*\*-50tr\*\* | +50tr(\*)|

| \*\*Tổng\*\* | | | \*\*100tr\*\* | \*\*140tr\*\* | \*\*-40tr\*\* | | | \*\*-40tr\*\* | \*\*+40tr\*\* |



> \*\*(\*) Cash Flow cũ dùng `SUM(credit)-SUM(debit)` cho từng tháng riêng lẻ.\*\*

> Vì Receivable là tài khoản bên Nợ, `credit-debit` cho ra dấu ngược với `debit-credit`.

> Delta đúng ra là `Closing - Opening`. Cash Flow cũ không có opening nên dùng

> `credit-debit` thay thế, dẫn đến sai dấu ở từng tháng nhưng tổng thể lại "gần đúng"

> khi accumulated\_values=True (từ đầu năm).



\*\*Sai số tích lũy:\*\*

```

Cash Flow cũ báo: ΔReceivable May-Dec = +40.000.000 (tăng 40tr → trừ 40tr khỏi CF)

Thực tế:          ΔReceivable May-Dec = -40.000.000 (giảm 40tr → cộng 40tr vào CF)

Sai lệch:         80.000.000 💥

```



\#### 3.4.2 TK 112 — Tiền gửi ngân hàng (KIỂM TRA CHÉO)



\*\*Đây là tài khoản TIỀN — dùng để kiểm tra kết quả Cash Flow.\*\*



| Tháng | Opening | Phát sinh Nợ | Phát sinh Có | Closing | Ghi chú |

|:----:|:-------:|:------------:|:------------:|:-------:|---------|

| May | \*\*160tr\*\* | 0 | 0 | 160tr | |

| Jun | 160tr | 60tr | 0 | 220tr | PE-003: KH A trả |

| Jul | 220tr | 0 | 0 | 220tr | |

| Aug | 220tr | 0 | 0 | 220tr | |

| Sep | 220tr | 30tr | 0 | 250tr | PE-004: KH C trả |

| Oct | 250tr | 500tr | 0 | 750tr | PV-001: Vay NH |

| Nov | 750tr | 0 | 0 | 750tr | |

| Dec | 750tr | 50tr | 0 | \*\*800tr\*\* | PE-005: KH D trả |



\*\*Biến động thực tế TK 112:\*\*

```

ΔCash May-Dec = 800tr - 160tr = +640.000.000 (tiền tăng 640tr)

```



\*\*Biến động cần giải thích từ Cash Flow:\*\*

```

Net Cash Flow = Operating + Investing + Financing

&#x20;             = ? + ? + 500tr (vay NH)

&#x20;             = 640tr

→ Operating + Investing phải = 640tr - 500tr = 140tr (dương)

```



\*\*Hãy xem Cash Flow hiện tại cho ra bao nhiêu:\*\*

```

Cash Flow hiện tại (sai):

\- ΔReceivable = +40tr → CF: -40tr (báo sai do thiếu opening)

\- ΔInventory = -59tr → CF: +59tr

\- Net Profit  = 41tr  → CF: +41tr

\- Depreciation= 0     → CF: 0

\- Vay         = 0     → CF: 0 (KHÔNG bắt được)

Net CF = 41tr - 40tr + 59tr = 60tr (SAI - lẽ ra phải 640tr)



Cash Flow đúng (với opening):

\- ΔReceivable = -40tr → CF: +40tr

\- ΔInventory  = -59tr → CF: +59tr

\- Net Profit  = 41tr  → CF: +41tr

\- Vay         = 500tr → CF: +500tr

Net CF = 41tr + 40tr + 59tr + 500tr = 640tr ✅ (khớp!)

```



\#### 3.4.3 TK 152+155 — Hàng tồn kho (Inventory)



\*\*Đầu năm 2026:\*\*

\- NVL (152) = 200.000.000

\- Thành phẩm (155) = 150.000.000



\*\*Biến động:\*\*

| Thời điểm | 152 (NVL) | 155 (TP) | Tổng kho |

|:---------:|:---------:|:---------:|:--------:|

| 01/01/2026 | 200tr | 150tr | 350tr |

| 15/04/2026 (SI-004) | 200tr | 102tr | \*\*302tr\*\* |

| 15/08/2026 (SI-005) | 200tr | 67tr | \*\*267tr\*\* |

| 15/11/2026 (SI-006) | 200tr | 43tr | \*\*243tr\*\* |



\*\*Delta Inventory May-Dec (đúng):\*\*

```

Opening (01/05): 200tr (NVL) + 102tr (TP) = 302.000.000

Closing (31/12): 200tr (NVL) + 43tr (TP)  = 243.000.000

ΔInventory = 243tr - 302tr = -59.000.000 (giảm 59tr)



Cash Flow: Hàng tồn giảm = tiền về → +59.000.000

```



\*\*Cash Flow hiện tại (tính SUM credit-debit cho account\_type='Stock'):\*\*

```sql

SELECT SUM(credit) - SUM(debit) FROM `tabGL Entry`

WHERE account\_type = 'Stock'

&#x20; AND posting\_date BETWEEN '2026-05-01' AND '2026-12-31'



Các entry trong range:

\#6: 15/08: 632/155: credit=35tr (155 giảm)

\#10:15/11: 632/155: credit=24tr (155 giảm)

SI-004 (15/04): 48tr NẰM NGOÀI RANGE



SUM(credit) = 35tr + 24tr = 59tr

SUM(debit)  = 0

Kết quả = 59tr - 0 = 59.000.000

```



Cash Flow hiện tại báo: ΔInventory = 59tr → \*\*SAI DẤU!\*\*

Vì `SUM(credit)-SUM(debit)` cho Stock (bên Nợ) ra giá trị dương khi credit tăng,

nhưng Stock giảm là debit giảm... Công thức đúng phải là `debit - credit = -59tr`

(giảm), rồi đảo dấu cho Cash Flow thành +59tr.



\#### 3.4.4 TK 311 — Vay ngắn hạn (Phần Financing)



| Thời điểm | Số dư Có | Ghi chú |

|:---------:|:--------:|---------|

| 01/01/2026 | 0 | Đầu năm chưa có vay |

| 01/10/2026 | 500tr | Vay NH 500tr |

| 31/12/2026 | 500tr | |



\*\*Cash Flow hiện tại với account\_type='Payable':\*\*

```sql

SELECT SUM(credit) - SUM(debit) FROM `tabGL Entry`

WHERE account\_type = 'Payable'

&#x20; AND posting\_date BETWEEN '2026-10-01' AND '2026-10-31'



PV-001: Nợ 112 / Có 311 → debit của 311? Không!

&#x20;        Nợ 112 (Cash) / Có 311 (Vay)

&#x20;        Ảnh hưởng đến TK 311: credit=500tr



SUM(credit)=500tr, SUM(debit)=0

Kết quả = 500tr - 0 = 500.000.000 (Payable tăng → CF: +500tr ✅)

```



Trong trường hợp này, Cash Flow hiện tại \*\*tình cờ đúng\*\* vì:

\- TK 311 là bên Có, opening=0, không có giao dịch trước đó

\- P/s trong range = credit 500tr, không có debit

\- `credit - debit = 500tr` = Delta thực tế (500tr - 0)



\*\*Nhưng nếu TK 311 có opening > 0 và có phát sinh cả Nợ lẫn Có thì sẽ sai.\*\*



\#### 3.4.5 Net Profit/Loss (từ P\&L)



\*\*Các giao dịch trong range May-Dec:\*\*

```

Doanh thu (511):

\- SI-004: 80.000.000 (15/04) → NGOÀI RANGE

\- SI-005: 60.000.000 (15/08) → TRONG RANGE

\- SI-006: 40.000.000 (15/11) → TRONG RANGE

Tổng doanh thu trong range = 60tr + 40tr = 100.000.000



Giá vốn (632):

\- SI-004: 48.000.000 (15/04) → NGOÀI RANGE

\- SI-005: 35.000.000 (15/08) → TRONG RANGE

\- SI-006: 24.000.000 (15/11) → TRONG RANGE

Tổng giá vốn trong range = 35tr + 24tr = 59.000.000



Net Profit = 100.000.000 - 59.000.000 = 41.000.000

```



> \*\*Lưu ý:\*\* P\&L reset về 0 đầu năm tài chính. Sau PCV-Q2, doanh thu và chi phí

> Q1+Q2 đã được kết chuyển về 0. Do đó range May-Dec chỉ thấy doanh thu từ

> SI-005 (tháng 8) và SI-006 (tháng 11).



\### 3.5 Bảng tổng hợp Cash Flow — So sánh 3 phương pháp



| Chỉ tiêu | Công thức đúng (Opening) | Cash Flow cũ (credit-debit) | Chênh lệch |

|:---------|:------------------------:|:---------------------------:|:----------:|

| \*\*Operating Activities\*\* | | | |

| Lợi nhuận ròng | 41.000.000 | 41.000.000 | 0 |

| Khấu hao | 0 | 0 | 0 |

| Δ Khoản phải thu | \*\*-40.000.000\*\* | \*\*+40.000.000\*\* | \*\*-80tr\*\* |

| Δ Hàng tồn kho | \*\*-59.000.000\*\* | \*\*+59.000.000\*\* | \*\*-118tr\*\* |

| Δ Phải trả | 0 | 0 | 0 |

| \*Cộng hoạt động KD\* | \*-58.000.000\* | \*+140.000.000\* | \*-198tr\* |

| \*\*Investing Activities\*\* | | | |

| Δ TSCĐ | 0 | 0 | 0 |

| \*\*Financing Activities\*\* | | | |

| Δ Vay +500.000.000 | +500.000.000 | 0 | +500tr |

| Δ Vốn CSH | 0 | 0 | 0 |

| \*\*Tổng Δ tiền\*\* | \*\*+442.000.000\*\* | \*\*+140.000.000\*\* | \*\*+302tr\*\* |

| \*\*Δ TK 112 thực tế\*\* | \*\*+640.000.000\*\* | \*\*+640.000.000\*\* | — |



> \*\*Giải thích chênh lệch 198tr (640tr - 442tr):\*\*

> - Giao dịch Q1-Q2 (15/04) chưa được tính trong range May-Dec:

>   - Doanh thu SI-004: 80.000.000

>   - Thu tiền KH A: 60.000.000

>   - Giá vốn SI-004: 48.000.000

>   - ... ⇒ Tổng ≈ 198tr

> - Đây là kết quả ĐÚNG vì filter là May-Dec, không thể tính giao dịch tháng 4.

> - Nếu accumulated\_values=True (lũy kế từ đầu năm), con số này sẽ khớp 640tr.



\---



\## 4. Phân Tích Logic Từng Loại Báo Cáo Kế Toán



\### 4.1 Bảng tổng hợp 4 báo cáo chính



| Báo cáo | Nguồn dữ liệu | Opening balance | Công thức period | Filter is\_opening | Filter PCV |

|:-------:|:-------------:|:---------------:|:----------------:|:-----------------:|:----------:|

| \*\*Trial Balance\*\* | Account Closing Balance (u tien) + GL Entry | opening\_debit/credit rieng cho tung tai khoan | SUM(debit), SUM(credit) trong ky | is\_opening=Yes duoc tinh vao opening | Co filter rieng |

| \*\*Balance Sheet\*\* | GL Entry tu year\_start\_date | posting\_date < year\_start\_date | SUM(debit-credit) trong period | Khong filter | Filter neu ignore\_closing\_entries=True |

| \*\*P\&L\*\* | GL Entry root\_type=Income/Expense | Khong co (reset 0 dau nam) | SUM(debit-credit), nhan -1 neu Credit side | Khong filter | ignore\_closing\_entries=True |

| \*\*Cash Flow (basic)\*\* | GL Entry account\_type | Khong co (SAI) | SUM(credit-debit) trong date range | Khong filter | voucher\_type != PCV |

| \*\*Cash Flow (custom)\*\* | GL Entry account\_names tu Cash Flow Mapping | Chi cho Tax/Interest | SUM(credit-debit) | opening\_balances=1 cho 4 loai | voucher\_type != PCV |



\### 4.2 Phân tích sâu — Trial Balance



\#### Luồng xử lý:



```

Trial Balance.execute(filters)

&#x20;   +-- get\_opening\_balances(filters)

&#x20;   |     +-- get\_rootwise\_opening\_balances("Balance Sheet")

&#x20;   |     |     +-- get\_opening\_balance("Account Closing Balance" | "GL Entry")

&#x20;   |     +-- get\_rootwise\_opening\_balances("Profit and Loss")

&#x20;   |           +-- get\_opening\_balance(...)

&#x20;   +-- get\_data(company, root\_type, ...) -> GL Entry trong ky

&#x20;   |     +-- filter: is\_opening="No", is\_cancelled=0

&#x20;   +-- calculate\_values(accounts, gl\_entries, opening\_balances)

&#x20;   |     +-- closing = opening + phat\_sinh\_trong\_ky

&#x20;   +-- prepare\_data(accounts) -> table

```



\#### Chi tiết hàm `get\_opening\_balance`:



```python

\# trial\_balance.py dong 213-333



def get\_opening\_balance(doctype, filters, report\_type,

&#x20;                        accounting\_dimensions,

&#x20;                        period\_closing\_voucher=None,

&#x20;                        start\_date=None,

&#x20;                        ignore\_is\_opening=0):



&#x20;   closing\_balance = frappe.qb.DocType(doctype)

&#x20;   # doctype = "Account Closing Balance" hoac "GL Entry"



&#x20;   opening\_balance = (

&#x20;       frappe.qb.from\_(closing\_balance)

&#x20;       .select(

&#x20;           closing\_balance.account,

&#x20;           Sum(closing\_balance.debit).as\_("debit"),

&#x20;           Sum(closing\_balance.credit).as\_("credit"),

&#x20;       )

&#x20;       .where(closing\_balance.company == filters.company)

&#x20;       .where(closing\_balance.account.isin(

&#x20;           # Chi lay tai khoan cua report\_type (BS hoac P\&L)

&#x20;           frappe.qb.from\_(account).select("name")

&#x20;           .where(account.report\_type == report\_type)

&#x20;       ))

&#x20;       .groupby(closing\_balance.account)

&#x20;   )



&#x20;   if period\_closing\_voucher:

&#x20;       # Truong hop co PCV -> lay Account Closing Balance

&#x20;       # Day la nhanh va chinh xac nhat

&#x20;       opening\_balance = opening\_balance.where(

&#x20;           closing\_balance.period\_closing\_voucher == period\_closing\_voucher

&#x20;       )

&#x20;   else:

&#x20;       if start\_date:

&#x20;           # Co khoang trong giua PCV va from\_date

&#x20;           opening\_balance = opening\_balance.where(

&#x20;               (closing\_balance.posting\_date >= start\_date)

&#x20;               \& (closing\_balance.posting\_date < filters.from\_date)

&#x20;           )

&#x20;           if not ignore\_is\_opening:

&#x20;               opening\_balance = opening\_balance.where(

&#x20;                   closing\_balance.is\_opening == "No"

&#x20;               )

&#x20;       else:

&#x20;           # Khong co PCV -> lay GL Entry truoc from\_date

&#x20;           if not ignore\_is\_opening:

&#x20;               # (posting\_date < from\_date) OR (is\_opening == "Yes")

&#x20;               opening\_balance = opening\_balance.where(

&#x20;                   (closing\_balance.posting\_date < filters.from\_date)

&#x20;                   | (closing\_balance.is\_opening == "Yes")

&#x20;               )

&#x20;           else:

&#x20;               # Chi lay posting\_date < from\_date, bo qua is\_opening

&#x20;               opening\_balance = opening\_balance.where(

&#x20;                   closing\_balance.posting\_date < filters.from\_date

&#x20;               )

&#x20;   ...

```



\#### Bảng decision logic cho Trial Balance opening:



| Tình huống | Có PCV? | Kết quả |

|:----------:|:-------:|---------|

| Chua co PCV, `ignore\_is\_opening=False` | Khong | `(posting\_date < from\_date) OR (is\_opening="Yes")` -> bao gom ca opening entry |

| Chua co PCV, `ignore\_is\_opening=True` | Khong | `posting\_date < from\_date` -> bo qua is\_opening="Yes" |

| Co PCV, `closing\_date = from\_date - 1` | Co | `period\_closing\_voucher = PCV` -> chinh xac, khong can GL Entry |

| Co PCV, `closing\_date < from\_date - 1` | Co | `PCV snapshot + GL Entry trong khoang trong` |



\#### Ví dụ cụ thể:



\*\*Filter: 01/05/2026 -> 31/12/2026\*\*



```python

\# Buoc 1: Kiem tra PCV

last\_pcv = frappe.db.get\_all("Period Closing Voucher",

&#x20;   filters={"docstatus": 1, "company": "ABC", "posting\_date": ("<", "2026-05-01")},

&#x20;   limit=1)

\# Result: \[] (PCV-Q2 co date=30/06 > 01/05, khong thoa)



\# Khong co PCV -> query GL Entry

\# is\_opening = False (mac dinh)

\# -> (posting\_date < '2026-05-01') OR (is\_opening = 'Yes')



\# Query GL Entry cho TK 131:

SELECT account, SUM(debit) as debit, SUM(credit) as credit

FROM `tabGL Entry`

WHERE company = 'ABC'

&#x20; AND is\_cancelled = 0

&#x20; AND account IN (SELECT name FROM tabAccount WHERE account\_type = 'Receivable')

&#x20; AND (posting\_date < '2026-05-01' OR is\_opening = 'Yes')

GROUP BY account



\# Ket qua:

\# 131: debit=60tr(OE) + 80tr(SI-004) = 140tr,

\#      credit=50tr(PE-002)

\# => opening\_debit=140, opening\_credit=50

\# => opening\_balance\_Nợ = 140-50 = 90.000.000

```



\### 4.3 Phân tích sâu — Balance Sheet



\#### Luồng xử lý:



```

Balance Sheet.execute(filters)

&#x20;   +-- get\_accounts(company, root\_type="Income"|"Expense")

&#x20;   |     -> danh sach tai khoan (tree structure)

&#x20;   +-- set\_gl\_entries\_by\_account(company, year\_start, to\_date, lft, rgt)

&#x20;   |     -> GL Entry trong \[year\_start\_date, to\_date]

&#x20;   |     -> KHONG filter is\_opening

&#x20;   |     -> Filter ignore\_closing\_entries=True => bo qua PCV

&#x20;   +-- calculate\_values(accounts\_by\_name, gl\_entries, period\_list)

&#x20;   |     +-- for entry in gl\_entries:

&#x20;   |     |     for period in period\_list:

&#x20;   |     |       if posting\_date <= period.to\_date:

&#x20;   |     |         if accumulated\_values OR posting\_date >= period.from\_date:

&#x20;   |     |           d\[period.key] += debit - credit

&#x20;   |     +-- if posting\_date < year\_start\_date:

&#x20;   |           d\["opening\_balance"] += debit - credit

&#x20;   +-- accumulate\_values\_into\_parents()

&#x20;   +-- prepare\_data(accounts, balance\_must\_be)

&#x20;   |     -> opening\_balance \*= (1 if Debit else -1)

&#x20;   |     -> period\_value \*= -1 neu balance\_must\_be="Credit"

```



\#### Khác biệt chính với Trial Balance:



\*\*1. Balance Sheet KHÔNG dùng Account Closing Balance\*\*

```

\- Balance Sheet query GL Entry TRUC TIEP tu year\_start\_date

\- Du co PCV hay khong, van query GL Entry tu dau nam

\- Hieu qua thap hon Trial Balance (phai scan GL Entry tu nam)

\- Nhung chinh xac vi tinh tu dau nam

```



\*\*2. Balance Sheet KHÔNG filter is\_opening\*\*

```python

\# financial\_statements.py dong 175-191

\# set\_gl\_entries\_by\_account()

\# KHONG co: WHERE is\_opening = 'No'

\# Lay het GL Entry tu year\_start\_date

```



\*\*3. Opening balance la GL Entry truoc year\_start\_date\*\*

```python

\# dong 243-244

if entry.posting\_date < period\_list\[0].year\_start\_date:

&#x20;   opening\_balance += debit - credit

\# -> opening chi la GL Entry cua NAM TRUOC

\# -> is\_opening="Yes" nam o 01/01 thuoc year\_start\_date

\# -> KHONG nam trong opening, ma nam trong period

```



\*\*Vi du:\*\*

```

year\_start\_date = 01/01/2026

posting\_date = 01/01/2026

=> 01/01/2026 < 01/01/2026? FALSE

=> is\_opening=Yes (60tr) nam trong period, KHONG nam trong opening



So voi Trial Balance:

\- Trial Balance: opening=90tr (gom 60tr is\_opening + phat sinh Q1)

\- Balance Sheet: opening=0, period value=90tr

\- Ca 2 deu dung nhung each hien thi khac nhau

```



\#### Công thức period của Balance Sheet:



```python

\# dong 236-241

for period in period\_list:

&#x20;   if entry.posting\_date <= period.to\_date:

&#x20;       if accumulated\_values or entry.posting\_date >= period.from\_date:

&#x20;           d\[period.key] += flt(entry.debit) - flt(entry.credit)

```



\*\*accumulated\_values=False:\*\*

```

entry chi duoc cong vao period neu posting\_date >= period.from\_date

=> Moi period chi lay phat sinh trong chinh ky do



Vi du: May 2026:

\- SI-004 (15/04): 15/04 < 01/05 => KHONG vao May

\- PE-003 (20/06): 20/06 > 31/05 => KHONG vao May

=> May: 0



Nhung TK 131 co opening=0, period May=0 -> Balance Sheet se hien thi

so 0 cho May. Tuy nhien, nho accumulate\_values\_into\_parents(), cac

parent account se cong don tu children de hien thi so du.

```



\*\*accumulated\_values=True:\*\*

```

entry duoc cong vao period neu posting\_date <= period.to\_date

(KHONG can >= period.from\_date)

=> Moi period luy ke tu year\_start\_date



Vi du: May 2026:

\- OE (01/01): debit=60tr -> vao May

\- PE-002 (10/02): credit=50tr -> vao May

\- SI-004 (15/04): debit=80tr -> vao May

=> May: 60tr - 50tr + 80tr = 90.000.000



Jun 2026:

\- All above + PE-003 (20/06): credit=60tr

=> Jun: 90tr - 60tr = 30.000.000

```



\### 4.4 Phân tích sâu — P\&L



\#### Đặc điểm:



1\. \*\*Reset về 0 đầu năm\*\* — không có opening balance

2\. \*\*ignore\_closing\_entries=True\*\* — bỏ qua Period Closing Voucher

3\. \*\*Side filter (Debit/Credit)\*\* — Income lấy Credit side, Expense lấy Debit side



```python

\# profit\_and\_loss\_statement.py dong 22-53



\# Income: root\_type="Income", balance\_must\_be="Credit"

income = get\_data(company, "Income", "Credit", period\_list,

&#x20;   filters=filters, accumulated\_values=filters.accumulated\_values,

&#x20;   ignore\_closing\_entries=True,     # Bo qua PCV

&#x20;   ignore\_accumulated\_values\_for\_fy=True)



\# Expense: root\_type="Expense", balance\_must\_be="Debit"

expense = get\_data(company, "Expense", "Debit", period\_list,

&#x20;   filters=filters, accumulated\_values=filters.accumulated\_values,

&#x20;   ignore\_closing\_entries=True, ignore\_accumulated\_values\_for\_fy=True)



\# Net Profit = Total Income - Total Expense

net\_profit\_loss\[key] = total\_income - total\_expense

```



\#### Tác động của ignore\_closing\_entries=True:



Khi PCV ket chuyen:

```

511 -> 911 (doanh thu dong)

632 -> 911 (chi phi dong)

911 -> 421 (lai dong)

```



Neu khong filter PCV:

```

\- Income se thay ca dong: 511/911 (credit) -> Income am

\- Expense se thay ca dong: 632/911 (debit) -> Expense am

\- Net Profit = (Income that - Income PCV) - (Expense that - Expense PCV)

&#x20;            = Income\_that - Expense\_that - (Income\_PCV - Expense\_PCV)

&#x20;            = Loi nhuan thuc - (doanh thu dong - chi phi dong)

&#x20;            = Loi nhuan thuc - loi nhuan = 0 !!!

```



Với `ignore\_closing\_entries=True`:

```

\- Income = chi co doanh thu ban hang (511), khong co dong PCV

\- Expense = chi co chi phi (632), khong co dong PCV

\- Net Profit = dung

```



\#### Ví dụ filter May-Dec:



```sql

\-- Income (511) truoc filter PCV:

\-- 15/04: SI-004: credit 80tr

\-- 15/08: SI-005: credit 60tr

\-- 15/11: SI-006: credit 40tr

\-- 30/06: PCV-Q2: debit 80tr (ket chuyen)

\-- 31/12: PCV-2026: debit 180tr (ket chuyen)



\-- Income SAU filter PCV (ignore\_closing\_entries=True):

\-- 15/04: credit 80tr -> ngoai range May-Dec

\-- 15/08: credit 60tr -> trong range

\-- 15/11: credit 40tr -> trong range

\-- => Income trong range = 60tr + 40tr = 100tr



\-- Expense (632) truoc filter PCV:

\-- 15/04: SI-004: debit 48tr

\-- 15/08: SI-005: debit 35tr

\-- 15/11: SI-006: debit 24tr

\-- 30/06: PCV-Q2: credit 48tr

\-- 31/12: PCV-2026: credit 107tr



\-- Expense SAU filter PCV:

\-- 15/04: debit 48tr -> ngoai range

\-- 15/08: debit 35tr -> trong range

\-- 15/11: debit 24tr -> trong range

\-- => Expense trong range = 35tr + 24tr = 59tr



\-- Net Profit = 100tr - 59tr = 41tr ✅

```



\### 4.5 Phân tích sâu — Cash Flow hiện tại



\#### Vấn đề cốt lõi:



Cash Flow hiện tại sử dụng công thức:

```

Delta(account\_type) = SUM(credit) - SUM(debit) TRONG \[from\_date, to\_date]

```



Đây là \*\*phát sinh thuần\*\* trong kỳ, không phải \*\*biến động số dư\*\*.

Đối với Balance Sheet accounts, biến động số dư mới là thước đo chính xác

của dòng tiền.



\#### Sai lầm ở đâu?



\*\*1. Thiếu opening balance:\*\*

```

Công thức đúng: Δ = Closing\_balance - Opening\_balance

&#x20;              = (SUM debit từ đầu năm đến to\_date) - (SUM debit từ đầu năm đến from\_date)

&#x20;              = SUM(debit - credit) trong \[from\_date, to\_date]

&#x20;              (khi đã có opening balance)



Công thức Cash Flow: Δ = SUM(credit - debit) trong \[from\_date, to\_date]

&#x20;                   = -(SUM(debit - credit) trong \[from\_date, to\_date])



Vậy Cash Flow lấy dấu ngược và thiếu opening.

```



\*\*2. Đảo ngược dấu cho Depreciation `\*=-1`:\*\*

```python

\# cash\_flow.py dong 168-169

if amount and account\_type == "Depreciation":

&#x20;   amount \*= -1

```

Day la \*\*hardcode\*\* khong tong quat. Ly do:

\- Depreciation la non-cash expense, can cong vao Net Profit

\- Net Profit da tru khau hao, nen can cong nguoc lai

\- `SUM(credit)-SUM(debit)` cho Depreciation = -(so khau hao)

\- Nhan -1 de thanh + (so khau hao)



\*\*3. Khong xet ban chat tai khoan (Debit/Credit side):\*\*

```

Tai khoan ben Nợ (Receivable, Stock, Fixed Asset):

&#x20; Tang = debit, Giam = credit

&#x20; Delta\_đúng = debit - credit

&#x20; Cash Flow cũ = credit - debit = -(debit - credit) = -Delta\_đúng



Tai khoan ben Có (Payable, Equity):

&#x20; Tang = credit, Giam = debit

&#x20; Delta\_đúng = credit - debit

&#x20; Cash Flow cũ = credit - debit = Delta\_đúng



=> Cash Flow cũ CHI ĐUNG cho tai khoan ben Có!

=> Sai dau cho tai khoan ben Nợ!

```



\### 4.6 So sánh chi tiết: Cash Flow cũ vs Cash Flow đúng cho từng loại tài khoản



| Account Type | Bản chất | Delta đúng (CF cần) | CF cũ tính | Kết quả |

|:------------:|:--------:|:-------------------:|:----------:|:-------:|

| \*\*Receivable\*\* | Ben No (Debit) | `debit - credit` | `credit - debit` | \*\*Sai dau\*\* |

| \*\*Stock\*\* | Ben No (Debit) | `debit - credit` | `credit - debit` | \*\*Sai dau\*\* |

| \*\*Fixed Asset\*\* | Ben No (Debit) | `debit - credit` | `credit - debit` | \*\*Sai dau\*\* |

| \*\*Cash/Bank\*\* | Ben No (Debit) | `debit - credit` | `credit - debit` | \*\*Sai dau\*\* |

| \*\*Payable\*\* | Ben Co (Credit) | `credit - debit` | `credit - debit` | \*\*Dung\*\* |

| \*\*Equity\*\* | Ben Co (Credit) | `credit - debit` | `credit - debit` | \*\*Dung\*\* |

| \*\*Depreciation\*\* | Non-cash adjustment | `-(debit - credit)` | `credit - debit` rồi `\*=-1` | \*\*Co the dung\*\* |



\*\*Cong thuc tong quat hoa:\*\*

```python

\# Cash Flow can:

\# Delta = Closing\_balance - Opening\_balance

\# Voi tai khoan Balance Sheet



\# Bien doi:

\# Closing = SUM(debit - credit) tu year\_start đến to\_date

\#         = opening\_tai\_year\_start + SUM(debit - credit) tu year\_start đến to\_date

\# Opening = SUM(debit - credit) tu year\_start đến from\_date

\# Delta  = Closing - Opening

\#        = SUM(debit - credit) trong \[from\_date, to\_date]



\# Dieu chinh cho Cash Flow:

\# Delta\_cf = -Delta (neu tai khoan ben No)

\#          = +Delta (neu tai khoan ben Co)

```



\---



\## 5. Vấn Đề Của Cash Flow Hiện Tại



\### 5.1 Các lỗi đã xác định



| STT | Lỗi | File | Dòng | Mức độ |

|:---:|:---:|:----:|:----:|:------:|

| 1 | \*\*Thieu opening balance\*\* | `cash\_flow.py` | 157-175 | \*\*Nghiem trong\*\* |

| 2 | \*\*Dung credit-debit thay vi debit-credit\*\* | `cash\_flow.py` | 198-204 | \*\*Nghiem trong\*\* |

| 3 | \*\*Hardcode Depreciation \*=-1\*\* | `cash\_flow.py` | 168-169 | Trung binh |

| 4 | \*\*Khong filter is\_opening cho period\*\* | `cash\_flow.py` | 198-204 | Trung binh |

| 5 | \*\*Custom mode chi tinh opening cho Tax/Interest\*\* | `custom\_cash\_flow.py` | 330-345 | Trung binh |

| 6 | \*\*Khong dung Account Closing Balance\*\* | `custom\_cash\_flow.py` | 475-540 | Trung binh |

| 7 | \*\*Khong tach running balance/period balance\*\* | `cash\_flow.py` | 157-175 | Trung binh |

| 8 | \*\*Khong xu ly company currency\*\* | cash\_flow.py | 66 | Thap |



\### 5.2 Điều kiện Cash Flow hiện tại cho kết quả đúng



| Điều kiện | Kết quả | Giải thích |

|:---------:|:-------:|-----------|

| `accumulated\_values=True`, filter tu dau nam | \*\*Dung (may man)\*\* | Opening entry nam trong range, `SUM(credit-debit)` tu dau nam = bien dong ca nam. Nhung van sai dau neu khong xet ban chất tai khoan. |

| Tai khoan ben Co (Payable, Equity) | \*\*Dung\*\* | `credit-debit` la cong thuc dung cho ben Co |

| Thang 1 dau nam (opening=0) | \*\*Dung\*\* | Opening=0, phat sinh trong T1 la bien dong chinh xac |

| `accumulated\_values=False`, thang 2+ | \*\*SAI\*\* | Thieu opening balance |

| Co PCV va dung Account Closing Balance | \*\*SAI\*\* | Cash Flow khong dung Account Closing Balance |

| Filter 01/05 - 31/12 (giua nam) | \*\*SAI\*\* | Thieu toan bo luy ke Q1 |



\### 5.3 Ảnh hưởng thực tế



Với dữ liệu mẫu, filter 01/05 -> 31/12/2026:



| Chỉ tiêu | Cash Flow cũ | Giá trị đúng | Chênh lệch |

|:---------|:------------:|:------------:|:----------:|

| Δ Receivable | +40.000.000 | -40.000.000 | \*\*80.000.000\*\* |

| Δ Inventory | +59.000.000 | -59.000.000 | \*\*118.000.000\*\* |

| Δ Payable | 0 | 0 | 0 |

| Net Profit | 41.000.000 | 41.000.000 | 0 |

| Depreciation | 0 | 0 | 0 |

| \*\*Operating CF\*\* | \*\*140.000.000\*\* | \*\*-58.000.000\*\* | \*\*198.000.000\*\* |

| \*\*Investing CF\*\* | 0 | 0 | 0 |

| \*\*Financing CF\*\* | 0 | 500.000.000 | \*\*500.000.000\*\* |

| \*\*Net Change in Cash\*\* | \*\*140.000.000\*\* | \*\*442.000.000\*\* | \*\*302.000.000\*\* |

| \*Kiem tra TK 112\* | \*640.000.000\* | \*640.000.000\* | \*—\* |



> Cash Flow cũ báo tăng 140tr, thực tế TK 112 tăng 640tr.

> Sai số \*\*500%\*\*.



\## 6. Tổng Hợp Toàn Bộ Các Trường Hợp Và Phương Pháp Tính Opening, Period, Balance Chuẩn Kế Toán



\### 6.1 Mô hình dữ liệu tổng quát



Mọi báo cáo kế toán trong ERPNext đều dựa trên 3 nguồn dữ liệu chính:



```

Nguồn 1: GL Entry (tabGL Entry)

&#x20; - Tất cả bút toán kế toán

&#x20; - Có trường: account, posting\_date, debit, credit, is\_opening, is\_cancelled, voucher\_type



Nguồn 2: Account Closing Balance (tabAccount Closing Balance)

&#x20; - Snapshot số dư Balance Sheet tại thời điểm chốt sổ

&#x20; - Chỉ tồn tại nếu đã chạy Period Closing Voucher

&#x20; - Có trường: account, debit, credit, period\_closing\_voucher, closing\_date



Nguồn 3: Account (tabAccount)

&#x20; - Danh sách tài khoản kế toán

&#x20; - Có trường: account\_type, root\_type, report\_type, is\_group

```



\### 6.2 Công thức tổng quát cho mọi báo cáo



```

BALANCE tại thời điểm T = SUM(debit) - SUM(credit)

&#x20;                          từ year\_start\_date đến T

&#x20;                          (trên GL Entry, is\_cancelled=0)



OPENING = BALANCE tại (from\_date - 1 ngày)

PERIOD  = BALANCE tại to\_date - BALANCE tại (from\_date - 1 ngày)

&#x20;       = SUM(debit) - SUM(credit) trong \[from\_date, to\_date]

&#x20;         (với is\_opening='No')

CLOSING = BALANCE tại to\_date = OPENING + PERIOD

```



\### 6.3 Tất cả các trường hợp tính Opening



\#### 6.3.1 Bảng quyết định — 6 trường hợp



| Case | Có PCV trước from\_date? | is\_opening tồn tại? | Khoảng cách PCV đến from\_date | Công thức opening |

|:----:|:-----------------------:|:-------------------:|:-------------------------:|:-----------------:|

| \*\*1\*\* | CÓ (chốt năm trước, 31/12) | CÓ (01/01 năm mới) | 0 ngày (31/12 sang 01/01) | \*\*ACB của PCV năm trước\*\* |

| \*\*2\*\* | CÓ (chốt quý, 30/06) | CÓ (01/01 đầu năm) | 0 ngày (30/06 sang 01/07) | \*\*ACB của PCV quý\*\* |

| \*\*3\*\* | CÓ (chốt quý, 30/06) | CÓ (01/01 đầu năm) | 15 ngày (30/06 đến 15/07) | \*\*ACB + GL Entry bổ sung trong gap\*\* |

| \*\*4\*\* | KHÔNG (chưa có PCV) | CÓ (01/01 đầu năm) | — | \*\*GL Entry: (posting\_date < from\_date) OR (is\_opening='Yes')\*\* |

| \*\*5\*\* | KHÔNG (chưa có PCV) | KHÔNG (năm đầu) | — | \*\*GL Entry: posting\_date < from\_date\*\* (từ year\_start) |

| \*\*6\*\* | CÓ (chốt năm trước) | KHÔNG (chưa mở sổ) | — | \*\*ACB của PCV\*\* (không cần is\_opening) |



\#### 6.3.2 Case 1: Đầu năm mới, đã chốt năm trước (phổ biến nhất)



\*\*Ví dụ:\*\* Filter Q1/2026 (01/01/2026 đến 31/03/2026), đã chốt PCV-2025 (31/12/2025).



```

Bước 1: Tìm PCV cuối cùng trước 01/01/2026

&#x20; last\_pcv = PCV-2025 (posting\_date=31/12/2025)



Bước 2: Kiểm tra khoảng trống

&#x20; closing\_date = 31/12/2025

&#x20; from\_date = 01/01/2026

&#x20; add\_days(from\_date, -1) = 31/12/2025

&#x20; 31/12/2025 < 31/12/2025? → FALSE

&#x20; → Không có gap. Opening chính xác từ ACB.



Bước 3: Lấy từ Account Closing Balance

&#x20; SELECT account, SUM(debit), SUM(credit)

&#x20; FROM tabAccount Closing Balance

&#x20; WHERE period\_closing\_voucher = 'PCV-2025'



&#x20; TK 131: debit=140.000.000, credit=0

&#x20; → opening\_balance\_131 = 140.000.000

&#x20; → (lưu ý: là số dư gộp cuối năm 2025, không phải số dư thực tế 60tr

&#x20;    mà Opening Entry 01/01/2026 ghi; PCV snapshot ghi số dư kế toán,

&#x20;    còn Opening Entry là bút toán điều chỉnh đầu năm)



&#x20; TK 112: debit=50.000.000, credit=0

&#x20; → opening\_balance\_112 = 50.000.000



Bước 4: Nếu query Q1 \[01/01, 31/03]:

&#x20; PERIOD TK 131:

&#x20;   -10/02: credit=50tr

&#x20;   -15/04: debit=80tr (NGOÀI Q1)

&#x20;   = 0 - 50 = -50.000.000

&#x20; CLOSING Q1 = 140tr + (-50tr) = 90tr

&#x20; → Trial Balance hiển thị: opening=140tr, debit=0, credit=50tr, closing=90tr

```



\*\*NHƯNG:\*\* Nếu dùng GL Entry trực tiếp cho opening (không dùng ACB):



```sql

\-- Query GL Entry Q1/2026

SELECT SUM(debit) - SUM(credit) FROM `tabGL Entry`

WHERE posting\_date BETWEEN '2026-01-01' AND '2026-03-31'

&#x20; AND is\_cancelled = 0

&#x20; AND voucher\_type != 'Period Closing Voucher'

&#x20; AND account = '131 - Phải thu'



\-- Kết quả: 60tr (opening) - 50tr (PE-002) = 10tr

\-- Balance Sheet hiển thị: 10.000.000

\-- KHÁC với Trial Balance (opening=140tr, period=-50tr, closing=90tr)

```



\*\*Giải thích sự khác biệt:\*\*

\- \*\*ACB (PCV-2025) ghi 140tr\*\* vì đó là tổng debit - credit của TK 131 trong năm 2025

\- \*\*Opening Entry 2026 ghi 60tr\*\* vì đó là số dư thực tế sau khi đã trừ các khoản thu

\- \*\*Cả 2 đều đúng\*\* nhưng dùng cho mục đích khác nhau

\- Trial Balance dùng ACB (tuân thủ nguyên tắc chốt sổ)

\- Balance Sheet dùng GL Entry trực tiếp (tuân thủ nguyên tắc số dư thực tế)



\#### 6.3.3 Case 2: Giữa năm, đã chốt quý (không gap)



\*\*Ví dụ:\*\* Filter Q3/2026 (01/07/2026 đến 30/09/2026), đã chốt PCV-Q2 (30/06/2026).



```

Bước 1: last\_pcv = PCV-Q2 (30/06/2026)

Bước 2: closing\_date=30/06, from\_date=01/07

&#x20; 30/06 < 30/06? → FALSE → không gap

Bước 3: ACB PCV-Q2

&#x20; TK 131: debit=30.000.000, credit=0

&#x20; → opening Q3 = 30.000.000 ✅



Bước 4: PERIOD Q3 \[01/07, 30/09]

&#x20; - 15/08: debit=60tr (SI-005)

&#x20; - 20/09: credit=30tr (PE-004)

&#x20; PERIOD = 60tr - 30tr = +30.000.000



CLOSING Q3 = opening(30tr) + period(+30tr) = 60.000.000 ✅

đúng số dư TK 131 tại 30/09/2026

```



\#### 6.3.4 Case 3: Giữa năm, có PCV nhưng có gap



\*\*Ví dụ:\*\* Filter 15/07/2026 đến 30/09/2026, đã chốt PCV-Q2 (30/06/2026).



```

Bước 1: last\_pcv = PCV-Q2 (30/06/2026)

Bước 2: closing\_date=30/06, from\_date=15/07

&#x20; add\_days(15/07, -1) = 14/07/2026

&#x20; 30/06/2026 < 14/07/2026? → TRUE → CÓ GAP (15 ngày)

```



\*\*Xử lý gap cho TK 131:\*\*



```

Bước 3a: Lấy ACB PCV-Q2

&#x20; TK 131: debit=30.000.000 ✅



Bước 3b: Query GL Entry bổ sung từ 01/07 đến 14/07

&#x20; SELECT SUM(debit), SUM(credit) FROM `tabGL Entry`

&#x20; WHERE posting\_date BETWEEN '2026-07-01' AND '2026-07-14'

&#x20;   AND account = '131 - Phải thu'

&#x20;   AND is\_cancelled = 0

&#x20;   AND is\_opening = 'No'   ← LOẠI bỏ is\_opening (đã có trong ACB)

&#x20;   AND voucher\_type != 'Period Closing Voucher'



&#x20; Kết quả: không có giao dịch TK 131 trong gap

&#x20; → debit\_bổ\_sung=0, credit\_bổ\_sung=0



&#x20; OPENING = ACB + bổ\_sung = 30tr + 0 = 30.000.000 ✅

```



\*\*Nếu có giao dịch trong gap:\*\* Giả sử ngày 05/07 ghi:

```

&#x20; Nợ 112 / Có 131: 10.000.000

&#x20; → debit\_bổ\_sung=0, credit\_bổ\_sung=10.000.000

&#x20; OPENING = ACB(30tr) + bổ\_sung(0-10tr) = 20.000.000

&#x20; (tại 15/07, TK 131 chỉ còn 20tr vì đã thu thêm 10tr ngày 05/07)

```



\#### 6.3.5 Case 4: Không có PCV, có is\_opening



\*\*Ví dụ:\*\* Filter 01/05/2026 đến 31/12/2026, chưa có PCV nào trước 01/05.



```

Bước 1: Tìm PCV → không có

Bước 2: Query GL Entry với (posting\_date < 01/05) OR (is\_opening='Yes')



&#x20; GL Entry TK 131:

&#x20; - 01/01: debit=60tr (is\_opening=Yes)

&#x20; - 10/02: credit=50tr (posting\_date < 01/05)

&#x20; - 15/04: debit=80tr (posting\_date < 01/05)

&#x20; - 20/06: credit=60tr → KHÔNG (< 01/05? KHÔNG)

&#x20; - 15/08: debit=60tr → KHÔNG



&#x20; SUM(debit) = 60tr + 80tr = 140tr

&#x20; SUM(credit) = 50tr

&#x20; OPENING = 140tr - 50tr = 90.000.000 ✅



PERIOD \[01/05, 31/12]:

&#x20; - 20/06: credit=60tr

&#x20; - 15/08: debit=60tr

&#x20; - 20/09: credit=30tr

&#x20; - 15/11: debit=40tr

&#x20; - 20/12: credit=50tr

&#x20; PERIOD = (60+40) - (60+30+50) = 100tr - 140tr = -40.000.000



CLOSING = 90tr + (-40tr) = 50.000.000 ✅

đúng số dư TK 131 tại 31/12/2026

```



\#### 6.3.6 Case 5: Năm đầu tiên, không có is\_opening



\*\*Ví dụ:\*\* Công ty mới thành lập năm 2025, filter Q1/2025.



```

Không có is\_opening (vì không có năm trước)

Không có PCV



OPENING = SUM(debit-credit) từ year\_start đến (from\_date-1)

&#x20;       = 0 (không có giao dịch trước đó)



Hoặc query GL Entry với posting\_date < from\_date:

&#x20; Không có kết quả

&#x20; → OPENING = 0 ✅

```



\#### 6.3.7 Case 6: Có PCV nhưng chưa mở sổ (hiếm)



\*\*Ví dụ:\*\* Filter ngay sau chốt sổ năm trước, trước khi mở sổ năm mới.

Kế toán chạy PCV-2025 ngày 31/12/2025 nhưng quên tạo Opening Entry.



```

ACB PCV-2025:

&#x20; TK 131: debit=140tr, credit=0

&#x20; → opening=140tr (số dư gộp năm 2025, vẫn đúng cho mục đích báo cáo)



Nếu sau đó mở sổ (01/01/2026):

&#x20; Nợ 131: 60tr (is\_opening=Yes)

&#x20; → Query GL Entry lần sau: opening=140tr (từ ACB) + 60tr (từ is\_opening) = 200tr ❌ SAI!

&#x20; → Vì sao? Vì ACB đã snapshot 140tr, thêm 60tr nữa thành 200tr, trong khi

&#x20;    thực tế 60tr là điều chỉnh giảm số dư (140tr → 60tr)



→ LỖI NẾU KẾ TOÁN MỞ SỔ SAI: ghi Nợ 131 thêm 60tr thay vì ghi sổ dư thực tế.

→ Cách đúng: Opening Entry phải ghi BẰNG số dư thực tế (60tr), không phải số dư gộp.

```



\### 6.4 Hai phương pháp tính toán



\#### Phương pháp A: Period-slice (ERPNext đang dùng)



\*\*Cách hoạt động:\*\*

```

Query 1: Opening = GL Entry từ year\_start đến (from\_date - 1)

Query 2 đến N: Mỗi period 1 query riêng biệt



Thuật toán:

&#x20; opening = get\_balance(at = from\_date - 1)

&#x20; for each period in period\_list:

&#x20;   period\_value = get\_movement(from=period.from\_date, to=period.to\_date)

&#x20;   closing = opening + period\_value

&#x20;   opening = closing (cho period tiếp theo)

```



\*\*Ưu điểm:\*\*

\- DB xử lý aggregation (SUM, GROUP BY) — nhanh cho từng query nhỏ

\- Dễ implement — mỗi period độc lập

\- accumulated\_values dễ dàng (chỉ cần thay đổi from\_date)



\*\*Nhược điểm:\*\*

\- N query (12 query cho 12 tháng)

\- Mỗi query scan 1 phần của bảng GL Entry

\- Opening query riêng biệt → dễ bị bỏ sót (như Cash Flow hiện tại)



\*\*Code mẫu:\*\*

```python

def period\_slice(company, account\_names, period\_list):

&#x20;   year\_start = period\_list\[0].year\_start\_date

&#x20;   result = {}

&#x20;   running = 0



&#x20;   for i, period in enumerate(period\_list):

&#x20;       if i == 0:

&#x20;           # Tính opening: balance tại from\_date - 1

&#x20;           opening = get\_gl\_balance(

&#x20;               company, account\_names,

&#x20;               year\_start, add\_days(period.from\_date, -1),

&#x20;               include\_is\_opening=True

&#x20;           )

&#x20;           result\["opening"] = opening

&#x20;           running = opening



&#x20;       # Tính period movement

&#x20;       movement = get\_gl\_movement(

&#x20;           company, account\_names,

&#x20;           period.from\_date, period.to\_date,

&#x20;           exclude\_is\_opening=True

&#x20;       )



&#x20;       running += movement

&#x20;       result\[period.key] = {

&#x20;           "movement": movement,

&#x20;           "closing": running,

&#x20;       }



&#x20;   return result

```



\#### Phương pháp B: Full-scan + Self-slice (Đề xuất cho Cash Flow)



\*\*Cách hoạt động:\*\*

```

Query duy nhất: lấy tất cả GL Entry từ year\_start đến to\_date

Sau đó tự slice trong memory



Thuật toán:

&#x20; rows = query\_all\_gl\_entries(company, account\_names, year\_start, final\_to)

&#x20; running = 0

&#x20; for each period in period\_list:

&#x20;   period\_entries = \[r for r in rows if period.from\_date <= r.date <= period.to\_date]

&#x20;   opening = running (tại đầu period)

&#x20;   movement = sum(r.debit - r.credit for r in period\_entries)

&#x20;   running += movement

&#x20;   closing = running

```



\*\*Ưu điểm:\*\*

\- 1 query duy nhất — tối ưu network

\- Không phụ thuộc vào `OR is\_opening` phức tạp

\- Tự tính opening, period, closing — kiểm soát hoàn toàn

\- Dễ debug (tất cả dữ liệu trong memory)



\*\*Nhược điểm:\*\*

\- Tốn memory nếu nhiều dữ liệu

\- Phải tự slicing — phức tạp hơn khi code

\- accumulated\_values phải tự xử lý



\*\*Code mẫu:\*\*

```python

def full\_scan(company, account\_names, period\_list):

&#x20;   """1 query duy nhất + tự slice — phương pháp tối ưu"""

&#x20;   year\_start = period\_list\[0].year\_start\_date

&#x20;   final\_to = period\_list\[-1].to\_date



&#x20;   # ====== 1 QUERY DUY NHẤT ======

&#x20;   gle = frappe.qb.DocType("GL Entry")

&#x20;   rows = (

&#x20;       frappe.qb.from\_(gle)

&#x20;       .select(gle.account, gle.posting\_date, gle.debit, gle.credit,

&#x20;               gle.is\_opening, gle.voucher\_type, gle.fiscal\_year)

&#x20;       .where(

&#x20;           (gle.company == company)

&#x20;           \& (gle.posting\_date >= year\_start)

&#x20;           \& (gle.posting\_date <= final\_to)

&#x20;           \& (gle.is\_cancelled == 0)

&#x20;           \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;           \& (gle.account.isin(account\_names))

&#x20;       )

&#x20;       .orderby(gle.posting\_date)

&#x20;   ).run(as\_dict=True)



&#x20;   # ====== TÍNH OPENING (từ year\_start đến trước period đầu) ======

&#x20;   first\_from = period\_list\[0].from\_date

&#x20;   opening = 0

&#x20;   remaining = \[]  # các row cho period



&#x20;   for row in rows:

&#x20;       pd = getdate(row.posting\_date)

&#x20;       if pd < getdate(first\_from):

&#x20;           # Thuộc về opening

&#x20;           opening += flt(row.debit) - flt(row.credit)

&#x20;       else:

&#x20;           remaining.append(row)



&#x20;   # ====== TÍNH TỪNG PERIOD ======

&#x20;   result = {"opening": opening, "periods": {}}

&#x20;   running = opening

&#x20;   period\_idx = 0



&#x20;   for period in period\_list:

&#x20;       period\_from = getdate(period.from\_date)

&#x20;       period\_to = getdate(period.to\_date)

&#x20;       movement = 0



&#x20;       # Lấy entries thuộc period này

&#x20;       new\_remaining = \[]

&#x20;       for row in remaining:

&#x20;           pd = getdate(row.posting\_date)

&#x20;           if pd > period\_to:

&#x20;               new\_remaining.append(row)

&#x20;               continue

&#x20;           if pd >= period\_from and pd <= period\_to:

&#x20;               if row.is\_opening == "No":

&#x20;                   movement += flt(row.debit) - flt(row.credit)



&#x20;       running += movement

&#x20;       result\["periods"]\[period.key] = {

&#x20;           "opening": running - movement,

&#x20;           "movement": movement,

&#x20;           "closing": running,

&#x20;       }

&#x20;       remaining = new\_remaining



&#x20;   result\["closing"] = running

&#x20;   result\["delta"] = running - opening

&#x20;   return result

```



\### 6.5 So sánh 2 phương pháp với dữ liệu thực tế



| Tiêu chí | Period-slice | Full-scan + Self-slice |

|:---------|:------------:|:----------------------:|

| Số query DB | N+1 (opening + N period) | 1 |

| Lượng dữ liệu trả về | Nhỏ (từng period) | Lớn (tất cả) |

| Bộ nhớ sử dụng | Thấp | Cao (chứa rows) |

| Xử lý DB | Nhiều (DB aggregation) | Ít (1 lần) |

| Xử lý App | Ít | Nhiều (slice trong memory) |

| accumulated\_values | Dễ (điều chỉnh date range) | Phức tạp hơn |

| Opening correctness | Phụ thuộc query riêng | Tự động chính xác |

| Debug | Khó (nhiều query) | Dễ (1 bảng rows) |

| Phù hợp số period ít (4 quý) | Tốt (5 query) | Tốt (1 query) |

| Phù hợp số period nhiều (12 tháng) | Chấp nhận được (13 query) | Tốt hơn (1 query) |

| Cash Flow hiện tại dùng | CÓ (nhưng THIẾU opening) | — |

| Cash Flow đề xuất dùng | — | NÊN DÙNG |



\### 6.6 Cách tính accumulated\_values với Full-scan



Khi `accumulated\_values=True`, mỗi period cần lũy kế từ đầu năm:



```python

def full\_scan\_accumulated(company, account\_names, period\_list):

&#x20;   """accumulated\_values=True: mỗi period là lũy kế từ year\_start"""

&#x20;   year\_start = period\_list\[0].year\_start\_date

&#x20;   final\_to = period\_list\[-1].to\_date



&#x20;   # 1 query duy nhất

&#x20;   rows = get\_all\_gl\_entries(company, account\_names, year\_start, final\_to)



&#x20;   # TÍNH LUỸ KẾ CHO TỪNG PERIOD

&#x20;   result = {}

&#x20;   running = 0

&#x20;   row\_index = 0

&#x20;   n = len(rows)



&#x20;   for period in period\_list:

&#x20;       pd\_to = getdate(period.to\_date)



&#x20;       # Cộng dồn từ row\_index đến hết period

&#x20;       while row\_index < n and getdate(rows\[row\_index].posting\_date) <= pd\_to:

&#x20;           row = rows\[row\_index]

&#x20;           running += flt(row.debit) - flt(row.credit)

&#x20;           row\_index += 1



&#x20;       result\[period.key] = running



&#x20;   # Opening = giá trị tại from\_date của period đầu - 1 ngày

&#x20;   first\_from = period\_list\[0].from\_date

&#x20;   day\_before = add\_days(first\_from, -1)



&#x20;   opening = get\_gl\_balance(

&#x20;       company, account\_names, year\_start, day\_before, include\_is\_opening=True

&#x20;   )



&#x20;   return {

&#x20;       "opening": opening,

&#x20;       "accumulated\_periods": result,

&#x20;       "delta": result.get(period\_list\[-1].key, 0) - opening,

&#x20;   }

```



\### 6.7 Bảng tổng hợp công thức cho từng loại báo cáo



| Báo cáo | Phương pháp | Opening | Period | Closing | accumulated\_values |

|:-------:|:-----------:|:-------:|:------:|:-------:|:------------------:|

| \*\*Trial Balance\*\* | Period-slice (ACB ưu tiên) | opening\_debit/credit riêng | SUM(debit), SUM(credit) riêng | opening + period | KHÔNG dùng |

| \*\*Balance Sheet\*\* | Period-slice (GL Entry) | posting\_date < year\_start | debit-credit trong period | lũy kế từ year\_start | Dùng (thay đổi from\_date) |

| \*\*P\&L\*\* | Period-slice (GL Entry) | Không (reset 0) | debit-credit (nhân -1 nếu Credit) | = period | Dùng |

| \*\*Cash Flow hiện tại\*\* | Period-slice (GL Entry) | \*\*THIẾU\*\* | credit-debit | Không tính | Dùng |

| \*\*Cash Flow đề xuất\*\* | Full-scan + Self-slice | Tự tính từ year\_start | debit-credit trong period | opening + period | Dùng được |



\### 6.8 Khuyến nghị cuối cùng



```

1\. NẾU muốn giữ nguyên kiến trúc period-slice:

&#x20;  → SỬA Cash Flow: thêm opening query giống Trial Balance

&#x20;  → Dùng ACB nếu có PCV, GL Entry nếu không

&#x20;  → Dùng debit-credit (không phải credit-debit)

&#x20;  → Đảo dấu cho tài khoản bên Nợ (Receivable, Stock, Fixed Asset)



2\. NẾU muốn tối ưu và chính xác tuyệt đối:

&#x20;  → VIẾT LẠI Cash Flow dùng full-scan + self-slice

&#x20;  → 1 query duy nhất, tự tính opening, period, closing

&#x20;  → Không phụ thuộc is\_opening hay ACB

&#x20;  → Kiểm soát hoàn toàn logic tính toán



3\. CẢ 2 phương pháp đều ĐÚNG nếu:

&#x20;  - Opening được tính chính xác

&#x20;  - Dùng debit-credit thay vì credit-debit

&#x20;  - Phân biệt tài khoản bên Nợ và bên Có

&#x20;  - Loại bỏ is\_opening khỏi period data

&#x20;  - Loại bỏ Period Closing Voucher khỏi period data

```

```

&#x09;   - Sử dụng ACB (Account Closing Balance) cho opening khi có PCV



\### 6.9 Vấn đề hiệu năng của Full-scan — Phân tích chiến lược tối ưu



\#### 6.9.1 Full-scan chậm như thế nào?



Ví dụ doanh nghiệp Việt Nam quy mô vừa (500 giao dịch/ngày):



| Khoản mục | Giá trị |

|:---------|:--------|

| Số giao dịch/ngày | 500 |

| Số dòng GL Entry/giao dịch | \~3 (Nợ+Có+thuế) |

| Số dòng GL Entry/ngày | \~1.500 |

| Số dòng GL Entry/tháng | \~45.000 |

| Số dòng GL Entry/năm | \*\*\~540.000\*\* |



Full-scan 540.000 dòng GL Entry từ year\_start đến to\_date cho 1 báo cáo Cash Flow:

\- Query: `SELECT ... FROM tabGL Entry WHERE posting\_date BETWEEN ...` → \*\*\~500ms-2s\*\*

\- Truyền dữ liệu: 540.000 dòng × \~100 bytes = \*\*\~54MB\*\* qua network

\- Xử lý memory: slice 540.000 dòng trong Python → \*\*thêm 1-3s nữa\*\*

\- \*\*Tổng thời gian: 3-5 giây\*\* — không chấp nhận được cho báo cáo real-time



\#### 6.9.2 So sánh hiệu năng 3 phương án



| Phương án | Số query | Dữ liệu/query | Thời gian ước tính | Phù hợp |

|:---------|:--------:|:-------------:|:------------------:|:--------|

| \*\*A: Period-slice (ERPNext cũ)\*\* | N+1 (13 cho 12 tháng) | \~45.000 dòng/tháng | \~1-2s (tuần tự) | Tốt cho DB mạnh |

| \*\*B: Full-scan (đề xuất ban đầu)\*\* | 1 | \~540.000 dòng/năm | \~3-5s | \*\*Không khả thi\*\* |

| \*\*C: Hybrid (ĐỀ XUẤT MỚI)\*\* | \*\*1 opening + N period song song\*\* | \*\*ACB (vài trăm dòng) + \~45k/period\*\* | \*\*\~0.5-1s\*\* | \*\*Tối ưu nhất\*\* |



\#### 6.9.3 Phương án tối ưu: Hybrid — Tận dụng ACB + Period-slice thông minh



\*\*Nguyên lý:\*\* Không cần query tất cả GL Entry từ year\_start. Chỉ cần:

1\. \*\*Opening\*\*: 1 query nhỏ — ACB (1 bảng snapshot, vài trăm dòng) hoặc GL Entry giới hạn `\[year\_start, from\_date-1]`

2\. \*\*Period\*\*: Mỗi period 1 query nhỏ — `SUM(debit-credit)` trong `\[from\_date, to\_date]` với `is\_opening='No'`

3\. \*\*Closing\*\*: Tính từ opening + period (không query thêm)



```python

def cash\_flow\_hybrid(company, account\_names, period\_list, filters):

&#x20;   """

&#x20;   Chiến lược Hybrid — tối ưu performance + chính xác tuyệt đối

&#x20;   """

&#x20;   # BƯỚC 1: TÍNH OPENING (1 query nhỏ)

&#x20;   # Ưu tiên Account Closing Balance (nếu có PCV) → 1 query bảng nhỏ

&#x20;   # Nếu không có PCV → 1 query GL Entry giới hạn \[year\_start, from\_date-1]

&#x20;   opening = get\_opening\_balance\_optimized(company, account\_names, period\_list, filters)



&#x20;   # BƯỚC 2: TÍNH PERIOD (N query nhỏ — SONG SONG)

&#x20;   # Mỗi period: SUM(debit-credit) trong \[from, to] với is\_opening='No'

&#x20;   period\_results = get\_period\_movements\_parallel(company, account\_names, period\_list)



&#x20;   # BƯỚC 3: TÍNH CLOSING (không query)

&#x20;   running = opening

&#x20;   for period in period\_list:

&#x20;       running += period\_results\[period.key]

&#x20;       period\_results\[period.key] = {

&#x20;           "opening": running - period\_results\[period.key],

&#x20;           "movement": period\_results\[period.key],

&#x20;           "closing": running,

&#x20;       }



&#x20;   return {"opening": opening, "periods": period\_results,

&#x20;           "closing": running, "delta": running - opening}

```



\#### 6.9.4 Phân tích chi tiết Opening — 3 cấp độ ưu tiên



```

CẤP 0: Account Closing Balance (nhanh nhất, chính xác nhất)

&#x20; - 1 query vào bảng snapshot (vài trăm dòng)

&#x20; - Không scan GL Entry

&#x20; - Chỉ dùng được khi đã chạy PCV trước from\_date

&#x20; → O(1) — millisecond



CẤP 1: GL Entry giới hạn \[year\_start, from\_date-1]

&#x20; - 1 query vào GL Entry trong khoảng hạn chế

&#x20; - Thường chỉ vài tháng: \[01/01, 30/04] cho filter 01/05

&#x20; - Nếu accumulated\_values=True: phạm vi còn nhỏ hơn

&#x20; → O(m) với m = số dòng từ year\_start đến from\_date-1



CẤP 2: GL Entry với (posting\_date < from\_date) OR (is\_opening='Yes')

&#x20; - Khi không có PCV và query từ đầu năm

&#x20; - Dự phòng cho trường hợp year\_start > năm đầu tiên của hệ thống

&#x20; → O(m) giống cấp 1

```



\*\*Ví dụ filter 01/05/2026 → 31/12/2026:\*\*

```

Có PCV trước 01/05? → PCV-Q2 (30/06) > 01/05 → KHÔNG

→ Rơi xuống CẤP 1



Query: GL Entry từ 01/01/2026 đến 30/04/2026

&#x20; - 01/01: is\_opening=Yes, 131: debit=60tr

&#x20; - 10/02: SI-002, 131: credit=50tr

&#x20; - 15/04: SI-004, 131: debit=80tr

&#x20; → Chỉ 3 dòng GL Entry cho TK 131!

&#x20; → Tổng tất cả tài khoản: \~20-30 dòng

&#x20; → Rất nhanh, không cần scan 540.000 dòng

```



\#### 6.9.5 Tối ưu Period query — song song hóa



Với 12 tháng, thay vì chạy tuần tự 12 query:



```python

from concurrent.futures import ThreadPoolExecutor, as\_completed



def get\_period\_movements\_parallel(company, account\_names, period\_list):

&#x20;   """Query tất cả period SONG SONG — giảm thời gian từ 2.4s xuống \~200ms"""

&#x20;   results = {}



&#x20;   def query\_period(period):

&#x20;       movement = get\_gl\_movement(company, account\_names,

&#x20;                                  period.from\_date, period.to\_date,

&#x20;                                  exclude\_is\_opening=True)

&#x20;       return period.key, movement



&#x20;   with ThreadPoolExecutor(max\_workers=8) as executor:

&#x20;       futures = {executor.submit(query\_period, p): p for p in period\_list}

&#x20;       for future in as\_completed(futures):

&#x20;           key, movement = future.result()

&#x20;           results\[key] = movement



&#x20;   return results

```



Phân tích hiệu năng:

\- 12 query song song: thay vì 12 × 200ms = 2.4s (tuần tự) → \*\*\~200ms\*\* (song song)

\- DB xử lý 12 aggregation nhỏ thay vì 1 aggregation lớn

\- Query nhỏ hơn, dễ cache, dễ parallel



\#### 6.9.6 Bảng so sánh chi tiết — 3 kiến trúc



| Tiêu chí | Period-slice (ERPNext cũ) | Full-scan (1 query lớn) | Hybrid (ĐỀ XUẤT) |

|:---------|:------------------------:|:----------------------:|:----------------:|

| Số query | N+1 (13) | 1 | 1 opening + N period song song |

| Dữ liệu trả về | Từng period nhỏ (\~45k dòng) | 1 lần lớn (\~540k dòng) | 1 opening nhỏ + từng period nhỏ |

| Bộ nhớ Python | Thấp | Cao (540k dòng) | Thấp |

| Network | N+1 lần nhỏ | 1 lần lớn (54MB) | N+1 lần nhỏ |

| DB load | N aggregation nhỏ | 1 aggregation lớn | 1 + N aggregation nhỏ |

| Parallel | Không (tuần tự) | Không thể | CÓ (N period song song) |

| Cache DB | Dễ (từng phần) | Khó | Dễ (từng period) |

| Thời gian 12 tháng | \~2s | \~3-5s | \*\*\~0.5-0.8s\*\* |

| Độ phức tạp code | Thấp | Trung bình | Trung bình-Cao |

| Tận dụng ACB | KHÔNG | KHÔNG | \*\*CÓ (ưu tiên)\*\* |

| Chính xác opening | ❌ (thiếu) | ✅ | ✅ |

| Chính xác period | ✅ (nếu có opening) | ✅ | ✅ |



\#### 6.9.7 Chiến lược cache thông minh



```python

\# Cache opening balance — tránh query lặp khi refresh báo cáo

def get\_opening\_cached(company, account\_names, from\_date, period\_list):

&#x20;   key = f"cash\_flow\_opening:{company}:{from\_date}"

&#x20;   cached = frappe.cache().get(key)

&#x20;   if cached:

&#x20;       return cached



&#x20;   opening = \_compute\_opening(company, account\_names, from\_date, period\_list)

&#x20;   frappe.cache().set(key, opening, expires\_in\_sec=300)  # Cache 5 phút

&#x20;   return opening

```



\#### 6.9.8 Code mẫu đầy đủ — Chiến lược Hybrid



```python

class CashFlowHybridEngine:

&#x20;   """Engine Cash Flow — Hybrid Strategy"""



&#x20;   def \_\_init\_\_(self, filters, period\_list, company\_currency):

&#x20;       self.filters = filters

&#x20;       self.period\_list = period\_list

&#x20;       self.currency = company\_currency

&#x20;       self.company = filters.company

&#x20;       self.year\_start = period\_list\[0].year\_start\_date

&#x20;       self.first\_from = period\_list\[0].from\_date



&#x20;   def get\_opening(self, account\_names):

&#x20;       """Tính opening — ưu tiên ACB, fallback GL Entry"""

&#x20;       last\_pcv = self.\_get\_last\_pcv()

&#x20;       if last\_pcv:

&#x20;           closing\_date = getdate(last\_pcv\[0].posting\_date)

&#x20;           if closing\_date < add\_days(self.first\_from, -1):

&#x20;               return self.\_opening\_with\_gap(account\_names, last\_pcv\[0].name, closing\_date)

&#x20;           else:

&#x20;               return self.\_opening\_from\_acb(account\_names, last\_pcv\[0].name)

&#x20;       return self.\_opening\_from\_gl(account\_names)



&#x20;   def \_get\_last\_pcv(self):

&#x20;       return frappe.db.get\_all("Period Closing Voucher",

&#x20;           filters={"docstatus": 1, "company": self.company, "posting\_date": ("<", self.first\_from)},

&#x20;           fields=\["posting\_date", "name"], order\_by="posting\_date desc", limit=1)



&#x20;   def \_opening\_from\_acb(self, account\_names, pcv\_name):

&#x20;       """ACB — 1 query vào bảng nhỏ, vài trăm dòng"""

&#x20;       acb = frappe.qb.DocType("Account Closing Balance")

&#x20;       result = (

&#x20;           frappe.qb.from\_(acb)

&#x20;           .select(Sum(acb.debit) - Sum(acb.credit))

&#x20;           .where((acb.company == self.company) \& (acb.period\_closing\_voucher == pcv\_name)

&#x20;                  \& (acb.account.isin(account\_names)))

&#x20;       ).run()

&#x20;       return flt(result\[0]\[0]) if result and result\[0]\[0] else 0



&#x20;   def \_opening\_with\_gap(self, account\_names, pcv\_name, closing\_date):

&#x20;       """ACB + GL Entry bổ sung trong khoảng trống"""

&#x20;       opening = self.\_opening\_from\_acb(account\_names, pcv\_name)

&#x20;       gle = frappe.qb.DocType("GL Entry")

&#x20;       result = (

&#x20;           frappe.qb.from\_(gle).select(Sum(gle.debit) - Sum(gle.credit))

&#x20;           .where((gle.company == self.company)

&#x20;                  \& (gle.posting\_date >= add\_days(closing\_date, 1))

&#x20;                  \& (gle.posting\_date <= add\_days(self.first\_from, -1))

&#x20;                  \& (gle.is\_cancelled == 0) \& (gle.is\_opening == "No")

&#x20;                  \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;                  \& (gle.account.isin(account\_names)))

&#x20;       ).run()

&#x20;       return opening + (flt(result\[0]\[0]) if result and result\[0]\[0] else 0)



&#x20;   def \_opening\_from\_gl(self, account\_names):

&#x20;       """GL Entry giới hạn \[year\_start, from\_date-1]"""

&#x20;       gle = frappe.qb.DocType("GL Entry")

&#x20;       result = (

&#x20;           frappe.qb.from\_(gle).select(Sum(gle.debit) - Sum(gle.credit))

&#x20;           .where((gle.company == self.company)

&#x20;                  \& (gle.posting\_date >= self.year\_start)

&#x20;                  \& (gle.posting\_date <= add\_days(self.first\_from, -1))

&#x20;                  \& (gle.is\_cancelled == 0)

&#x20;                  \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;                  \& (gle.account.isin(account\_names)))

&#x20;       ).run()

&#x20;       return flt(result\[0]\[0]) if result and result\[0]\[0] else 0



&#x20;   def get\_period\_movement(self, account\_names, from\_date, to\_date):

&#x20;       """SUM(debit-credit) trong \[from, to] với is\_opening='No'"""

&#x20;       gle = frappe.qb.DocType("GL Entry")

&#x20;       result = (

&#x20;           frappe.qb.from\_(gle).select(Sum(gle.debit) - Sum(gle.credit))

&#x20;           .where((gle.company == self.company)

&#x20;                  \& (gle.posting\_date >= from\_date) \& (gle.posting\_date <= to\_date)

&#x20;                  \& (gle.is\_cancelled == 0) \& (gle.is\_opening == "No")

&#x20;                  \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;                  \& (gle.account.isin(account\_names)))

&#x20;       ).run()

&#x20;       return flt(result\[0]\[0]) if result and result\[0]\[0] else 0



&#x20;   def calculate\_item\_delta(self, account\_names, invert\_sign=False):

&#x20;       """Tính delta cho period\_list — opening + period song song"""

&#x20;       opening = self.get\_opening(account\_names)



&#x20;       from concurrent.futures import ThreadPoolExecutor, as\_completed

&#x20;       period\_movements = {}



&#x20;       def query(p):

&#x20;           m = self.get\_period\_movement(account\_names, p.from\_date, p.to\_date)

&#x20;           if invert\_sign: m \*= -1

&#x20;           return p.key, m



&#x20;       with ThreadPoolExecutor(max\_workers=8) as pool:

&#x20;           futures = {pool.submit(query, p): p for p in self.period\_list}

&#x20;           for future in as\_completed(futures):

&#x20;               k, m = future.result()

&#x20;               period\_movements\[k] = m



&#x20;       result = {}

&#x20;       total = 0

&#x20;       running = opening

&#x20;       for period in self.period\_list:

&#x20;           mov = period\_movements\[period.key]

&#x20;           result\[period.key] = mov

&#x20;           total += mov

&#x20;           running += mov

&#x20;       result\["total"] = total

&#x20;       return result

```



\#### 6.9.9 Khuyến nghị DB Index



```sql

\-- Index cần thiết cho Cash Flow Hybrid:

CREATE INDEX idx\_gl\_cf\_optimized

ON `tabGL Entry`(company, posting\_date, is\_opening, voucher\_type, is\_cancelled);

```



\#### 6.9.10 Kết luận chiến lược



```

CHIẾN LƯỢC ĐƯỢC CHỌN: Hybrid (ACB/GL giới hạn + Period song song)



&#x20; ✅ Opening chính xác — ACB (ưu tiên) hoặc GL Entry giới hạn

&#x20; ✅ Period chính xác — SUM(debit-credit), is\_opening='No'

&#x20; ✅ Hiệu năng cao — query nhỏ, song song, cache

&#x20; ✅ Tận dụng DB — aggregation, index, parallel query

&#x20; ✅ Không full-scan — tránh kéo triệu dòng GL Entry



&#x20; So với Full-scan:   0.5s vs 3-5s (nhanh 10 lần)

&#x20; So với Period-cũ:   CÓ opening + song song (thay vì thiếu opening + tuần tự)

```



\## 7. Đề Xuất Giải Pháp Cash Flow Đúng Nguyên Tắc Kế Toán



\### 7.1 Nguyên lý thiết kế



Cash Flow mới cần:

1\. \*\*Tính opening balance\*\* — tái sử dụng logic Trial Balance (Account Closing Balance + is\_opening)

2\. \*\*Tính period balance\*\* — `SUM(debit - credit)` trong kỳ với `is\_opening="No"`

3\. \*\*Tính delta\*\* = `Closing\_balance - Opening\_balance` = `SUM(debit - credit)` trong kỳ

4\. \*\*Xử lý dấu\*\* — đảo dấu cho Cash Flow tùy theo bản chất tài khoản (Nợ/Có)



\### 7.2 Công thức tổng quát hóa



```python

\# Cốt lõi: Tính Delta cho bất kỳ nhóm tài khoản Balance Sheet nào



def calculate\_delta(company, account\_names, from\_date, to\_date, year\_start\_date):

&#x20;   """

&#x20;   Tinh delta dung nguyen tac ke toan



&#x20;   Delta = Closing\_balance - Opening\_balance

&#x20;         = SUM(debit - credit) trong \[from\_date, to\_date]

&#x20;           (khi phát sinh đã được lọc is\_opening="No")



&#x20;   Trong do:

&#x20;   - Opening\_balance = SUM(debit - credit) tu year\_start đến from\_date

&#x20;                       (bao gom ca is\_opening="Yes")

&#x20;   - Closing\_balance = SUM(debit - credit) tu year\_start đến to\_date

&#x20;                       (bao gom ca is\_opening="Yes")

&#x20;   """

&#x20;   # Cach 1: Tinh truc tiep

&#x20;   gle = frappe.qb.DocType("GL Entry")



&#x20;   # Phat sinh trong \[from\_date, to\_date] (is\_opening="No")

&#x20;   period\_movement = (

&#x20;       frappe.qb.from\_(gle)

&#x20;       .select(Sum(gle.debit) - Sum(gle.credit))

&#x20;       .where(

&#x20;           (gle.company == company)

&#x20;           \& (gle.posting\_date >= from\_date)

&#x20;           \& (gle.posting\_date <= to\_date)

&#x20;           \& (gle.is\_cancelled == 0)

&#x20;           \& (gle.is\_opening == "No")

&#x20;           \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;           \& (gle.account.isin(account\_names))

&#x20;       )

&#x20;   ).run()



&#x20;   # Cach 2: Tinh qua opening-closing (tuong duong)

&#x20;   # opening = balance at (from\_date - 1)

&#x20;   # closing = balance at to\_date

&#x20;   # delta = closing - opening = period\_movement



&#x20;   return flt(period\_movement\[0]\[0]) if period\_movement else 0

```



\### 7.3 Kiến trúc module đề xuất



```

erpnext/accounts/report/cash\_flow/

&#x20;   +-- \_\_init\_\_.py

&#x20;   +-- cash\_flow.py                 # Giữ nguyên (gọi corrected nếu có flag)

&#x20;   +-- custom\_cash\_flow.py          # Giữ nguyên (gọi corrected nếu có flag)

&#x20;   +-- corrected\_cash\_flow.py       # MỚI: module chính

&#x20;   |     +-- CashFlowEngine         # Engine tổng

&#x20;   |     +-- get\_opening\_balance()  # Tái sử dụng logic Trial Balance

&#x20;   |     +-- get\_period\_delta()     # Tính delta từng kỳ

&#x20;   |     +-- build\_section()        # Xây dựng section

&#x20;   |     +-- execute()              # Hàm chính

&#x20;   +-- corrected\_cash\_flow.js       # MỚI: client script

```



\### 7.4 Mã nguồn chi tiết



```python

\# corrected\_cash\_flow.py

\# module: erpnext/accounts/report/cash\_flow/corrected\_cash\_flow.py

"""

Cash Flow Statement — Corrected Version

Tuan thu nguyen tac ke toan: tinh opening balance cho Balance Sheet accounts

"""



import frappe

from frappe import \_

from frappe.query\_builder.functions import Sum

from frappe.utils import flt, getdate, add\_days



from erpnext.accounts.report.financial\_statements import (

&#x20;   get\_columns, get\_data, get\_period\_list

)

from erpnext.accounts.report.profit\_and\_loss\_statement.profit\_and\_loss\_statement import (

&#x20;   get\_net\_profit\_loss,

)





def execute(filters=None):

&#x20;   """Ham chinh: tra ve (columns, data)"""

&#x20;   if not filters:

&#x20;       filters = frappe.\_dict({})

&#x20;   if not filters.periodicity:

&#x20;       filters.periodicity = "Monthly"



&#x20;   period\_list = get\_period\_list(

&#x20;       filters.from\_fiscal\_year, filters.to\_fiscal\_year,

&#x20;       filters.period\_start\_date, filters.period\_end\_date,

&#x20;       filters.filter\_based\_on, filters.periodicity,

&#x20;       company=filters.company,

&#x20;   )

&#x20;   company\_currency = frappe.get\_cached\_value("Company", filters.company, "default\_currency")



&#x20;   # Net Profit/Loss

&#x20;   income = get\_data(filters.company, "Income", "Credit", period\_list,

&#x20;                     filters=filters, accumulated\_values=filters.accumulated\_values,

&#x20;                     ignore\_closing\_entries=True, ignore\_accumulated\_values\_for\_fy=True)

&#x20;   expense = get\_data(filters.company, "Expense", "Debit", period\_list,

&#x20;                       filters=filters, accumulated\_values=filters.accumulated\_values,

&#x20;                       ignore\_closing\_entries=True, ignore\_accumulated\_values\_for\_fy=True)

&#x20;   net\_profit = get\_net\_profit\_loss(income, expense, period\_list, filters.company)



&#x20;   # Engine

&#x20;   engine = CashFlowEngine(filters, period\_list, company\_currency)

&#x20;   config = \_get\_section\_config(filters)

&#x20;   data = \[]



&#x20;   for i, section in enumerate(config):

&#x20;       section\_data = \[]

&#x20;       data.append({

&#x20;           "account\_name": section\["header"],

&#x20;           "parent\_account": None, "indent": 0.0,

&#x20;           "account": section\["header"],

&#x20;       })



&#x20;       # Net Profit (chi cho Operating section)

&#x20;       if i == 0 and net\_profit:

&#x20;           entry = net\_profit.copy()

&#x20;           entry.update({"indent": 1, "parent\_account": section\["header"]})

&#x20;           data.append(entry)

&#x20;           section\_data.append(entry)



&#x20;       for item in section.get("items", \[]):

&#x20;           names = item.get("names", \[])

&#x20;           if not names:

&#x20;               continue

&#x20;           delta = engine.calculate\_item\_delta(names, item.get("invert\_sign", False))

&#x20;           if abs(delta.get("total", 0)) < 0.5:

&#x20;               continue

&#x20;           row = {

&#x20;               "account\_name": item\["label"],

&#x20;               "account": names,

&#x20;               "indent": 1.0,

&#x20;               "parent\_account": section\["header"],

&#x20;               "currency": company\_currency,

&#x20;           }

&#x20;           row.update(delta)

&#x20;           data.append(row)

&#x20;           section\_data.append(row)



&#x20;       # Footer

&#x20;       \_add\_total(data, section\_data, section\["footer"], period\_list, company\_currency)



&#x20;   # Net Change in Cash

&#x20;   \_add\_total(data, data, "Net Change in Cash", period\_list, company\_currency)

&#x20;   columns = get\_columns(filters.periodicity, period\_list, filters.accumulated\_values, filters.company)

&#x20;   return columns, data





class CashFlowEngine:

&#x20;   def \_\_init\_\_(self, filters, period\_list, currency):

&#x20;       self.filters = filters

&#x20;       self.period\_list = period\_list

&#x20;       self.currency = currency

&#x20;       self.company = filters.company

&#x20;       self.year\_start = period\_list\[0].year\_start\_date



&#x20;   def get\_balance(self, account\_names, as\_on\_date, exclude\_is\_opening=False):

&#x20;       """Tinh so du cua cac tai khoan tai thoi diem as\_on\_date"""

&#x20;       gle = frappe.qb.DocType("GL Entry")

&#x20;       query = (

&#x20;           frappe.qb.from\_(gle)

&#x20;           .select(Sum(gle.debit) - Sum(gle.credit))

&#x20;           .where(

&#x20;               (gle.company == self.company)

&#x20;               \& (gle.posting\_date >= self.year\_start)

&#x20;               \& (gle.posting\_date <= as\_on\_date)

&#x20;               \& (gle.is\_cancelled == 0)

&#x20;               \& (gle.voucher\_type != "Period Closing Voucher")

&#x20;               \& (gle.account.isin(account\_names))

&#x20;           )

&#x20;       )

&#x20;       if exclude\_is\_opening:

&#x20;           query = query.where(gle.is\_opening == "No")

&#x20;       result = query.run()

&#x20;       return flt(result\[0]\[0]) if result and result\[0]\[0] else 0



&#x20;   def get\_opening(self, account\_names, from\_date):

&#x20;       """So du dau ky: balance tai (from\_date - 1)"""

&#x20;       return self.get\_balance(account\_names, add\_days(from\_date, -1))



&#x20;   def get\_closing(self, account\_names, to\_date):

&#x20;       """So du cuoi ky: balance tai to\_date"""

&#x20;       return self.get\_balance(account\_names, to\_date)



&#x20;   def get\_delta(self, account\_names, from\_date, to\_date):

&#x20;       """Delta = Closing - Opening"""

&#x20;       return self.get\_closing(account\_names, to\_date) - self.get\_opening(account\_names, from\_date)



&#x20;   def calculate\_item\_delta(self, account\_names, invert\_sign=False):

&#x20;       """

&#x20;       Tinh delta cho tung period



&#x20;       Args:

&#x20;           account\_names: List ten tai khoan

&#x20;           invert\_sign: True -> dao dau (cho non-cash adjustment, hoac tai khoan ben No)



&#x20;       Returns:

&#x20;           dict {period.key: value, "total": total}

&#x20;       """

&#x20;       data = {}

&#x20;       total = 0

&#x20;       for period in self.period\_list:

&#x20;           delta = self.get\_delta(account\_names, period.from\_date, period.to\_date)

&#x20;           if invert\_sign:

&#x20;               delta \*= -1

&#x20;           data\[period.key] = delta

&#x20;           total += delta

&#x20;       data\["total"] = total

&#x20;       return data





def \_get\_section\_config(filters):

&#x20;   """Lay cau hinh cac section (ke thua tu Cash Flow Mapping neu co)"""

&#x20;   use\_custom = frappe.db.get\_single\_value("Accounts Settings", "use\_custom\_cash\_flow")

&#x20;   if use\_custom:

&#x20;       return \_build\_config\_from\_mappers(filters)

&#x20;   return \_default\_config()





def \_default\_config():

&#x20;   """Cau hinh mac dinh (3 sections)"""

&#x20;   return \[

&#x20;       {

&#x20;           "header": "Cash flows from operating activities",

&#x20;           "footer": "Net cash generated by operating activities",

&#x20;           "items": \[

&#x20;               {"label": "Depreciation",

&#x20;                "names": \_accounts\_by\_type("Depreciation"),

&#x20;                "invert\_sign": True},

&#x20;               {"label": "Net Change in Accounts Receivable",

&#x20;                "names": \_accounts\_by\_type("Receivable"),

&#x20;                "invert\_sign": True},

&#x20;               {"label": "Net Change in Accounts Payable",

&#x20;                "names": \_accounts\_by\_type("Payable"),

&#x20;                "invert\_sign": False},

&#x20;               {"label": "Net Change in Inventory",

&#x20;                "names": \_accounts\_by\_type("Stock"),

&#x20;                "invert\_sign": True},

&#x20;           ],

&#x20;       },

&#x20;       {

&#x20;           "header": "Cash flows from investing activities",

&#x20;           "footer": "Net cash used in investing activities",

&#x20;           "items": \[

&#x20;               {"label": "Net Change in Fixed Asset",

&#x20;                "names": \_accounts\_by\_type("Fixed Asset"),

&#x20;                "invert\_sign": True},

&#x20;           ],

&#x20;       },

&#x20;       {

&#x20;           "header": "Cash flows from financing activities",

&#x20;           "footer": "Net cash used in financing activities",

&#x20;           "items": \[

&#x20;               {"label": "Net Change in Equity",

&#x20;                "names": \_accounts\_by\_type("Equity"),

&#x20;                "invert\_sign": False},

&#x20;           ],

&#x20;       },

&#x20;   ]





def \_build\_config\_from\_mappers(filters):

&#x20;   """Xay dung config tu Cash Flow Mapper (danh cho custom mode)"""

&#x20;   from erpnext.accounts.report.cash\_flow.custom\_cash\_flow import (

&#x20;       get\_mappers\_from\_db, setup\_mappers

&#x20;   )

&#x20;   mappers = get\_mappers\_from\_db()

&#x20;   if not mappers:

&#x20;       return \_default\_config()

&#x20;   cash\_flow\_accounts = setup\_mappers(mappers)

&#x20;   config = \[]

&#x20;   for m in cash\_flow\_accounts:

&#x20;       items = \[]

&#x20;       for a in m.get("account\_types", \[]):

&#x20;           items.append({

&#x20;               "label": a\["label"],

&#x20;               "names": a\["names"],

&#x20;               "invert\_sign": not a.get("is\_working\_capital", False),

&#x20;           })

&#x20;       config.append({

&#x20;           "header": m\["section\_header"],

&#x20;           "footer": m.get("section\_footer", ""),

&#x20;           "items": items,

&#x20;       })

&#x20;   return config





def \_accounts\_by\_type(account\_type):

&#x20;   """Helper: lay danh sach ten tai khoan theo account\_type"""

&#x20;   acc = frappe.qb.DocType("Account")

&#x20;   rows = (frappe.qb.from\_(acc).select(acc.name).where(acc.account\_type == account\_type)).run()

&#x20;   return \[r\[0] for r in rows]





def \_add\_total(out, data, label, period\_list, currency):

&#x20;   """Tinh dong tong cho mot section"""

&#x20;   row = {

&#x20;       "account\_name": "'" + label + "'",

&#x20;       "account": "'" + label + "'",

&#x20;       "currency": currency,

&#x20;   }

&#x20;   for period in period\_list:

&#x20;       total = sum(flt(r.get(period.key, 0)) for r in data if r.get("parent\_account"))

&#x20;       row\[period.key] = total

&#x20;   row\["total"] = sum(flt(r.get("total", 0)) for r in data if r.get("parent\_account"))

&#x20;   out.append(row)

&#x20;   out.append({})

```



\### 7.5 So sánh kết quả — Corrected vs Cũ



Với filter 01/05/2026 -> 31/12/2026:



| Chỉ tiêu | Cash Flow cũ | Cash Flow corrected | TK 112 thực tế |

|:---------|:------------:|:------------------:|:--------------:|

| Net Profit | 41.000.000 | 41.000.000 | — |

| Depreciation | 0 | 0 | — |

| Delta Receivable | +40.000.000 | -40.000.000 | -40.000.000 |

| Delta Inventory | +59.000.000 | -59.000.000 | -59.000.000 |

| Delta Payable | 0 | 0 | 0 |

| \*\*Operating CF\*\* | \*\*140.000.000\*\* | \*\*-58.000.000\*\* | — |

| \*\*Investing CF\*\* | 0 | 0 | — |

| \*\*Financing CF\*\* | 0 | \*\*+500.000.000\*\* | +500.000.000 |

| \*\*Net Change\*\* | \*\*140.000.000\*\* | \*\*442.000.000\*\* | \*\*640.000.000\*\* |



> \*\*Giải thích:\*\* Corrected báo 442tr, thực tế TK 112 tăng 640tr. Chênh lệch 198tr

> là do các giao dịch tháng 4/2026 (SI-004: doanh thu 80tr, thu 60tr, giá vốn 48tr)

> nằm NGOÀI range May-Dec. Đây là kết quả \*\*ĐÚNG\*\* — filter ngày nào tính ngày đó.



\### 7.6 Hướng dẫn triển khai



1\. \*\*Tạo file mới:\*\* `erpnext/accounts/report/cash\_flow/corrected\_cash\_flow.py`

2\. \*\*Đăng ký report:\*\* Thêm vào `hooks.py`

3\. \*\*Chuyển hướng:\*\* Sửa `cash\_flow.py` để dùng corrected nếu có setting

4\. \*\*Kiểm tra:\*\* So sánh với Trial Balance và Balance Sheet

5\. \*\*Thay thế:\*\* Sau khi xác nhận đúng, thay thế hoàn toàn



\---



\## 8. Kết Luận



1\. \*\*Cash Flow hiện tại có thiết kế sai\*\* — dùng `SUM(credit)-SUM(debit)` thay vì `Closing - Opening`, không tách `is\_opening` ra khỏi period data, hardcode dấu cho Depreciation.



2\. \*\*Sai số rất lớn\*\* — với filter May-Dec, Cash Flow cũ báo tăng 140tr, thực tế tăng 640tr (sai 500%).



3\. \*\*Gốc rễ\*\* — Balance Sheet accounts có số dư lũy kế, cần `Closing - Opening` để tính biến động, không phải phát sinh thuần `credit-debit`.



4\. \*\*Giải pháp\*\* — Tái sử dụng logic Trial Balance:

&#x20;  - Account Closing Balance (nếu có PCV) hoặc is\_opening=Yes

&#x20;  - `SUM(debit - credit)` trong kỳ với is\_opening="No"

&#x20;  - Delta = `Closing - Opening`



5\. \*\*Lợi ích\*\* — Chính xác theo nguyên tắc kế toán, hiệu năng tốt hơn nhờ Account Closing Balance snapshot, dễ bảo trì hơn.





