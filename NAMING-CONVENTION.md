# AlumGlass Naming Convention — English Standard (v28.2)
## Thay thế tất cả tên Việt/pha trộn bằng tiếng Anh chuẩn

---

## 1. DOCTYPE NAMES

| Tên cũ (pha trộn) | Tên mới (English) | Ghi chú |
|---|---|---|
| AL PK Set | **AL Accessory Set** | PK = Phụ kiện |
| AL PK Item | **AL Accessory Item** | Được thay thế bởi AL Bom Item |
| *(còn lại giữ nguyên)* | AL Slug Library, AL Bom Item, AL Bom Set, AL Glass Master, AL Glass Type, AL Product Type, AL Cost Bucket, AL Cost Template, AL Material Category, AL Pricing Dimension, AL Quantity Calc Method, AL Calculation Rule, AL Dynamic Item Rule, AL Cutting Standard, AL Installation Team, AL Warranty Policy, AL Supplier Price List, AL Profile System, AL Color Standard, AL BOM, AL BOM Version | Đã là tiếng Anh |

---

## 2. CATEGORY CODES (AL Material Category)

| Mã cũ | Mã mới | Tên hiển thị |
|---|---|---|
| NHOM | **ALUMINUM** | Aluminum |
| KINH | **GLASS** | Glass |
| VTP | **SUPPLIES** | Supplies / Auxiliary Materials |
| PK | **ACCESSORY** | Accessories |
| THEP | **STEEL** | Steel |
| INOX | **STAINLESS_STEEL** | Stainless Steel |
| NHUA | **PLASTIC** | Plastic |
| ALU_COMPOSITE | *(giữ nguyên)* | Alu Composite |
| GO | **WOOD** | Wood |

---

## 3. COST BUCKET CODES (AL Cost Bucket)

| Mã cũ | Mã mới | Ghi chú |
|---|---|---|
| VL_NHOM | **VL_ALUMINUM** | Vật liệu Nhôm |
| VL_KINH | **VL_GLASS** | Vật liệu Kính |
| VL_VTP | **VL_SUPPLIES** | Vật liệu VTP |
| VL_PK | **VL_ACCESSORY** | Vật liệu Phụ kiện |
| VL_THEP | **VL_STEEL** | Vật liệu Thép |
| VL_INOX | **VL_STAINLESS_STEEL** | Vật liệu Inox |
| VL_NHUA | **VL_PLASTIC** | Vật liệu Nhựa |
| VL_ALU | **VL_ALU_COMPOSITE** | Vật liệu Alu |
| VL_GO | **VL_WOOD** | Vật liệu Gỗ |
| TONG_VL | **TOTAL_MATERIAL** | Tổng vật liệu |
| NC_SX | **PRODUCTION_LABOR** | Nhân công sản xuất |
| NC_LD | **INSTALLATION_LABOR** | Nhân công lắp đặt |
| TONG_NC | **TOTAL_LABOR** | Tổng nhân công |
| OH_HH | **HANDLING_OVERHEAD** | Overhead hao hụt |
| OH_VC | **TRANSPORT_OVERHEAD** | Overhead vận chuyển |
| OH_QLY | **ADMIN_OVERHEAD** | Overhead quản lý |
| OH_BH | **WARRANTY_OVERHEAD** | Overhead bảo hành |
| OH_CUT_KINH | **GLASS_CUTTING_OVERHEAD** | Overhead cắt kính |
| TONG_OH | **TOTAL_OVERHEAD** | Tổng overhead |
| GIA_THANH | **COST_PRICE** | Giá thành |
| GIA_BAN | **SELLING_PRICE** | Giá bán |
| GIA_VAT | **VAT_PRICE** | Giá sau VAT |
| DON_GIA_M2 | **UNIT_PRICE_M2** | Đơn giá / m2 |

---

## 4. COST TEMPLATE LINE CODES

| Mã cũ | Mã mới |
|---|---|
| TONG_VL | TOTAL_MATERIAL |
| TONG_M2 | TOTAL_M2 |
| NC_SX | PRODUCTION_LABOR |
| NC_LD | INSTALLATION_LABOR |
| TONG_NC | TOTAL_LABOR |
| OH_VC | TRANSPORT_OVERHEAD |
| OH_QLY | ADMIN_OVERHEAD |
| OH_HH | HANDLING_OVERHEAD |
| OH_BH | WARRANTY_OVERHEAD |
| OH_CUT_KINH | GLASS_CUTTING_OVERHEAD |
| TONG_OH | TOTAL_OVERHEAD |
| GIA_THANH | COST_PRICE |
| PROFIT | PROFIT |
| GIA_BAN | SELLING_PRICE |
| DON_GIA_M2 | UNIT_PRICE_M2 |
| VAT | VAT |
| GIA_VAT | VAT_PRICE |

---

## 5. FIELD NAMES (DocType columns)

### AL Slug Library
| Tên cũ | Tên mới | Ghi chú |
|---|---|---|
| slug | *(giữ nguyên)* | |
| label | *(giữ nguyên)* | |
| category | *(giữ nguyên)* | Link → AL Material Category |
| group_tag | *(giữ nguyên)* | |

### AL Bom Item
| Tên cũ | Tên mới | Ghi chú |
|---|---|---|
| slug | *(giữ nguyên)* | |
| category | *(giữ nguyên)* | |
| trong_luong_rieng | **weight_per_unit** | kg/m — ERPNext Item field |
| don_gia | **unit_price** | |
| thanh_tien | **line_total** | |
| so_luong_don_vi | **unit_qty** | |
| tong_so_luong | **total_qty** | |
| calc_pattern | *(giữ nguyên)* | |
| price_base_item | *(giữ nguyên)* | |
| ctx_inject_prefix | *(giữ nguyên)* | |
| panel_count_formula | *(giữ nguyên)* | |
| rule_input_expr | *(giữ nguyên)* | |
| formula_set | *(giữ nguyên)* | |

### Item (custom fields)
| Tên cũ | Tên mới |
|---|---|
| al_item_type | **al_material_category** (Link) |
| al_kg_per_m | **al_weight_per_m** |
| al_glass_master | *(giữ nguyên)* |
| al_is_color_variable | *(giữ nguyên)* |

### Item Price (custom fields — replaced by Pricing Dimension)
| Tên cũ (hardcode) | Tên mới (auto-generated) |
|---|---|
| custom_mau_sac | **custom_pd_COLOR** |
| custom_xuat_xu | **custom_pd_ORIGIN** |
| custom_do_day | **custom_pd_THICKNESS** |
| custom_be_mat | **custom_pd_SURFACE_FINISH** |

### AL Pricing Dimension (data values)
| dimension_code cũ | dimension_code mới |
|---|---|
| MAU_SAC | **COLOR** |
| XUAT_XU | **ORIGIN** |
| DO_DAY | **THICKNESS** |
| BE_MAT | **SURFACE_FINISH** |
| DO_BONG | **GLOSS_LEVEL** |

### AL Glass Master
| Tên cũ | Tên mới |
|---|---|
| total_thick_mm | *(giữ nguyên)* |
| glass_type | *(giữ nguyên)* |
| glass_code | *(giữ nguyên)* |
| glass_name | *(giữ nguyên)* |

### AL Quantity Calc Method
| Tên cũ | Tên mới |
|---|---|
| calc_pattern_code | *(giữ nguyên)* |
| calc_pattern_name | *(giữ nguyên)* |
| calc_formula | *(giữ nguyên)* |
| calc_fn | *(giữ nguyên)* |
| input_vars | *(giữ nguyên)* |
| output_unit | *(giữ nguyên)* |

### AL Material Category
| Tên cũ | Tên mới | Ghi chú |
|---|---|---|
| category_code | *(giữ nguyên)* | |
| category_name | *(giữ nguyên)* | |
| default_calc_pattern | *(giữ nguyên)* | |
| default_cost_bucket | *(giữ nguyên)* | |

### AL Cost Bucket
| Tên cũ | Tên mới |
|---|---|
| bucket_code | *(giữ nguyên)* |
| bucket_name | *(giữ nguyên)* |
| bucket_role | *(giữ nguyên)* |
| parent_bucket | *(giữ nguyên)* |
| source_type | *(giữ nguyên)* |
| source_config | *(giữ nguyên)* |
| report_group | *(giữ nguyên)* |

### AL Pricing Dimension
| Tên cũ | Tên mới |
|---|---|
| dimension_code | *(giữ nguyên)* |
| dimension_name | *(giữ nguyên)* |
| dimension_type | *(giữ nguyên)* |
| link_doctype | *(giữ nguyên)* |
| select_options | *(giữ nguyên)* |
| applies_to_category | *(giữ nguyên)* |

---

## 6. FORMULA VARIABLES / INPUT NAMES

| Tên cũ | Tên mới | Ghi chú |
|---|---|---|
| W_mm | *(giữ nguyên)* | Width in mm |
| H_mm | *(giữ nguyên)* | Height in mm |
| W_m | *(giữ nguyên)* | Width in m |
| H_m | *(giữ nguyên)* | Height in m |
| n_canh | **n_panel** | Number of panels/leaves |
| TransomHeight_mm | *(giữ nguyên)* | |
| mau_nhom | **aluminum_color** | |
| xuat_xu_nhom | **aluminum_origin** | |
| do_day_nhom | **aluminum_thickness** | |
| be_mat_nhom | **aluminum_surface** | |
| trong_luong_rieng | **weight_per_unit** | |
| don_gia_nhom | **aluminum_unit_price** | |
| don_gia_kinh | **glass_unit_price** | |
| NC_SX_PCT | **PRODUCTION_LABOR_PCT** | |
| NC_LD_PCT | **INSTALLATION_LABOR_PCT** | or `nc_ld_rate` → `installation_labor_rate` |
| OH_VC_PCT | **TRANSPORT_OVERHEAD_PCT** | |
| OH_QLY_PCT | **ADMIN_OVERHEAD_PCT** | |
| OH_HH_PCT | **HANDLING_OVERHEAD_PCT** | |
| OH_BH_PCT | **WARRANTY_OVERHEAD_PCT** | |
| VAT_RATE | *(giữ nguyên)* | |
| PROFIT_MARGIN | *(giữ nguyên)* | |
| OFFSET_FRAME | *(giữ nguyên)* | |
| OFFSET_GLASS | *(giữ nguyên)* | |
| OFFSET_FIXED | *(giữ nguyên)* | |
| OFFSET_DO_NGANG | **OFFSET_CROSSBAR** | Đố ngang = crossbar |

---

## 7. SLUG NAMES (giữ nguyên — domain identifiers)

Các slug như `khung_ngang_tren`, `kinh_tren`, `nep_kinh_tren`... được giữ nguyên vì:
- Là định danh nghiệp vụ đặc thù ngành nhôm kính Việt Nam
- Được dùng làm biến trong công thức cross-row reference
- Người dùng cuối là thợ nhôm kính Việt Nam

Nếu cần bản tiếng Anh cho thị trường quốc tế, tạo alias `slug_en` trong AL Slug Library.

---

## 8. GROUP TAG VALUES

| Tên cũ | Tên mới |
|---|---|
| KHUNG | **FRAME** |
| CANH | **SASH** |
| NEP | **BEAD** |
| KINH | **GLASS** |
| KEO | **ADHESIVE** |
| GIOANG | **GASKET** |
| VIT | **SCREW** |
| PK | **ACCESSORY** |

---

## 9. PRODUCT TYPE CODES

| Tên cũ | Tên mới |
|---|---|
| CUA_DI | **DOOR** |
| CUA_SO | **WINDOW** |
| VACH_KINH | **CURTAIN_WALL** |

---

## 10. AL Quantity Calc Method — PATTERN CODES

| Mã cũ | Mã mới | Ghi chú |
|---|---|---|
| LENGTH_TO_WEIGHT | *(giữ nguyên)* | |
| AREA | *(giữ nguyên)* | |
| LENGTH_ONLY | *(giữ nguyên)* | |
| COUNT | *(giữ nguyên)* | |
| VOLUME | *(giữ nguyên)* | |

---

## 11. AL Calculation Rule — RULE TYPE VALUES

| Mã cũ | Mã mới |
|---|---|
| CONSTANT | *(giữ nguyên)* |
| THRESHOLD | *(giữ nguyên)* |
| LOOKUP | *(giữ nguyên)* |
| SEQUENCE | *(giữ nguyên)* |

---

## 12. SOURCE TYPE VALUES (AL Cost Bucket)

| Mã cũ | Mã mới |
|---|---|
| aggregate_from_items | *(giữ nguyên)* |
| formula | *(giữ nguyên)* |
| doctype_query | *(giữ nguyên)* |
| custom_function | *(giữ nguyên)* |
| constant | *(giữ nguyên)* |
| pipeline | *(giữ nguyên)* |
| conditional | *(giữ nguyên)* |
| fallback_chain | *(giữ nguyên)* |

---

*Document version: 1.0 — 2026-07-27*
