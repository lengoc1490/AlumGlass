# -*- coding: utf-8 -*-
"""Unit test THUẦN PYTHON cho bộ luật Variable Catalog.

Không import frappe, không cần site — chỉ test `variable_sources/rules.py`.

CÁCH CHẠY
---------
    cd ~/myfrappe/apps/alumglass
    python3 -I alumglass/tests/test_variable_catalog_rules.py -v

(`python3 -I` bỏ qua PYTHONPATH/user-site; file tự thêm app root vào sys.path.)
"""
import os
import sys
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)

from alumglass.variable_sources.rules import (  # noqa: E402
    EXCLUDE_ALL,
    INCLUDE_ALL,
    active_source_kinds,
    build_groups,
    dedupe_candidates,
    parse_json_list,
    rule_matches,
    select_candidates,
    split_pipe,
)


def candidate(**overrides):
    """Candidate tối thiểu — đủ các khoá mà bộ luật đọc."""
    base = {
        "name": "VL_NHOM",
        "label": "VL Nhôm",
        "type": "Float",
        "value": 0,
        "has_value": True,
        "source_kind": "cost_bucket",
        "source_ref": "VL_NHOM",
        "group": "Cost Bucket",
        "sort_order": 100,
        "source_type": "cost_bucket",
        "category": "",
        "adapter_order": 20,
    }
    base.update(overrides)
    return base


def rule(**overrides):
    """Rule tối thiểu — mặc định là Include, đang bật."""
    base = {
        "action": "Include",
        "source_kind": "cost_bucket",
        "source_ref": "*",
        "group_label": "01 · Chi phí",
        "sort_order": 10,
        "is_active": 1,
        "require_value": 0,
    }
    base.update(overrides)
    return base


class TestHelpers(unittest.TestCase):
    def test_split_pipe(self):
        self.assertEqual(split_pipe("A|B | C"), ["A", "B", "C"])
        self.assertEqual(split_pipe(""), [])
        self.assertEqual(split_pipe(None), [])
        self.assertEqual(split_pipe("A||B"), ["A", "B"])

    def test_parse_json_list(self):
        self.assertEqual(parse_json_list('["qty","width"]'), ["qty", "width"])
        self.assertEqual(parse_json_list('["qty", ""]'), ["qty"])
        self.assertIsNone(parse_json_list(""))
        self.assertIsNone(parse_json_list(None))
        # Dữ liệu cấu hình hỏng KHÔNG được ném lỗi ra UI.
        self.assertIsNone(parse_json_list("[qty,width"))
        self.assertIsNone(parse_json_list('{"a":1}'))


class TestRuleMatches(unittest.TestCase):
    def test_source_kind(self):
        self.assertTrue(rule_matches(rule(), candidate()))
        self.assertFalse(rule_matches(rule(source_kind="formula_global"),
                                      candidate()))

    def test_source_kind_rong_khop_moi_nguon(self):
        self.assertTrue(rule_matches(rule(source_kind=""), candidate()))

    def test_source_ref_star_va_auto(self):
        self.assertTrue(rule_matches(rule(source_ref="*"), candidate()))
        self.assertTrue(rule_matches(rule(source_ref="AUTO"), candidate()))
        self.assertTrue(rule_matches(rule(source_ref=""), candidate()))
        self.assertTrue(rule_matches(rule(source_ref="VL_NHOM|VL_KINH"),
                                     candidate()))
        self.assertFalse(rule_matches(rule(source_ref="VL_KINH"),
                                      candidate()))

    def test_name_prefix(self):
        self.assertTrue(rule_matches(rule(name_prefix="OFFSET_|VL_"),
                                     candidate()))
        self.assertFalse(rule_matches(rule(name_prefix="OFFSET_"),
                                      candidate()))
        # Tiền tố phân biệt hoa thường (theo spec).
        self.assertFalse(rule_matches(rule(name_prefix="vl_"), candidate()))

    def test_name_regex(self):
        self.assertTrue(rule_matches(rule(name_regex=r"^VL_"), candidate()))
        self.assertFalse(rule_matches(rule(name_regex=r"^XX_"), candidate()))
        # Regex hỏng ⇒ không khớp, không ném.
        self.assertFalse(rule_matches(rule(name_regex="[unclosed"),
                                      candidate()))

    def test_category_tag_khong_phan_biet_hoa_thuong(self):
        cand = candidate(category="OFFSET")
        self.assertTrue(rule_matches(rule(category_tag="offset"), cand))
        self.assertTrue(rule_matches(rule(category_tag="NC|OFFSET"), cand))
        self.assertFalse(rule_matches(rule(category_tag="NC"), cand))

    def test_var_type_va_source_type(self):
        self.assertTrue(rule_matches(rule(var_type="Float"), candidate()))
        self.assertFalse(rule_matches(rule(var_type="Data"), candidate()))
        self.assertTrue(rule_matches(rule(source_type="cost_bucket"),
                                     candidate()))
        self.assertFalse(rule_matches(rule(source_type="constant"),
                                      candidate()))

    def test_only_fields(self):
        r = rule(only_fields='["qty","width"]')
        # Có fieldname và nằm trong danh sách ⇒ khớp.
        self.assertTrue(rule_matches(r, candidate(), "qty"))
        # Có fieldname nhưng KHÔNG nằm trong danh sách ⇒ loại.
        self.assertFalse(rule_matches(r, candidate(), "unit_price"))
        # Client không gửi fieldname ⇒ bỏ qua điều kiện (an toàn ngược).
        self.assertTrue(rule_matches(r, candidate(), None))
        self.assertTrue(rule_matches(r, candidate(), ""))

    def test_require_value(self):
        r = rule(require_value=1)
        self.assertTrue(rule_matches(r, candidate(value=0, has_value=True)))
        self.assertFalse(rule_matches(r, candidate(value="—", has_value=False)))
        self.assertFalse(rule_matches(r, candidate(value=None, has_value=False)))

    def test_is_active(self):
        self.assertFalse(rule_matches(rule(is_active=0), candidate()))
        # is_active có thể là chuỗi "0" từ HTTP.
        self.assertFalse(rule_matches(rule(is_active="0"), candidate()))


class TestSelectCandidates(unittest.TestCase):
    def test_include_all_giu_nguyen_ca_khong_khop(self):
        cands = [candidate(),
                 candidate(name="X", source_kind="formula_global",
                           source_ref="X")]
        selected, stats = select_candidates(
            cands, [], default_action=INCLUDE_ALL)
        self.assertEqual(len(selected), 2)
        self.assertEqual(stats["excluded_by_rules"], 0)

    def test_exclude_thang_include(self):
        cands = [candidate()]
        rules = [rule(), rule(action="Exclude", group_label="")]
        selected, stats = select_candidates(cands, rules)
        self.assertEqual(selected, [])
        self.assertEqual(stats["excluded_by_rules"], 1)

    def test_exclude_all_chi_giu_cai_khop(self):
        cands = [candidate(),
                 candidate(name="GLOB", source_kind="formula_global",
                           source_ref="GLOB")]
        rules = [rule()]
        selected, stats = select_candidates(
            cands, rules, default_action=EXCLUDE_ALL)
        self.assertEqual([c["name"] for c in selected], ["VL_NHOM"])
        self.assertEqual(stats["excluded_by_rules"], 1)

    def test_gan_group_va_sort_order_tu_rule(self):
        cands = [candidate(group="Cost Bucket", sort_order=100)]
        selected, _ = select_candidates(
            [cands[0]], [rule(group_label="01 · Chi phí", sort_order=7)],
            default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["group"], "01 · Chi phí")
        self.assertEqual(selected[0]["sort_order"], 7)
        self.assertEqual(selected[0]["only_fields"], [])
        # Không được sửa candidate gốc.
        self.assertEqual(cands[0]["group"], "Cost Bucket")

    def test_only_fields_duoc_gan_cho_client(self):
        """DEV3 lọc client-side theo `only_fields` — key phải luôn có."""
        cands = [candidate(name="width")]
        selected, _ = select_candidates(
            cands, [rule(only_fields='["qty","width"]')],
            fieldname="width", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], ["qty", "width"])

        # Candidate không khớp rule nào (INCLUDE_ALL) vẫn phải có key rỗng.
        selected, _ = select_candidates(cands, [], default_action=INCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], [])

    def test_only_fields_gop_tu_nhieu_rule_include(self):
        """Nhiều rule cùng khớp + cùng khai `only_fields` ⇒ lấy HỢP."""
        r1 = rule(source_kind="row_literal", only_fields='["qty","width"]',
                  sort_order=10, group_label="06 · Dòng hiện tại")
        r2 = rule(source_kind="row_literal", only_fields='["width","height"]',
                  sort_order=20, group_label="06b · Khác")
        cand = candidate(source_kind="row_literal", name="width",
                         source_ref="width")
        selected, _ = select_candidates(
            [cand], [r1, r2], fieldname="width", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"],
                         ["qty", "width", "height"])
        # group/sort vẫn lấy rule sort_order nhỏ nhất (r1).
        self.assertEqual(selected[0]["group"], "06 · Dòng hiện tại")
        self.assertEqual(selected[0]["sort_order"], 10)

    def test_mot_rule_khong_gioi_han_thi_khong_gioi_han(self):
        """Rule B không khai `only_fields` ⇒ biến hiện ở mọi field."""
        r1 = rule(source_kind="row_literal", only_fields='["qty"]', sort_order=10)
        r2 = rule(source_kind="row_literal", sort_order=20)
        cand = candidate(source_kind="row_literal", name="qty", source_ref="qty")
        selected, _ = select_candidates(
            [cand], [r1, r2], fieldname="qty", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], [])

    def test_rule_bi_loc_theo_field_khong_keo_theo_only_fields(self):
        """Rule A (chỉ qty) không khớp ở `width` ⇒ không ảnh hưởng kết quả."""
        r1 = rule(source_kind="row_literal", only_fields='["qty"]', sort_order=10)
        r2 = rule(source_kind="row_literal", sort_order=20)
        cand = candidate(source_kind="row_literal", name="width",
                         source_ref="width")
        selected, _ = select_candidates(
            [cand], [r1, r2], fieldname="width", default_action=EXCLUDE_ALL)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["only_fields"], [])


class TestOnlyFieldsGiaoNguonVaRule(unittest.TestCase):
    """Phạm vi field = GIAO của phạm vi NGUỒN (adapter) và phạm vi RULE."""

    def test_nguon_gioi_han_rule_khong_gioi_han(self):
        cand = candidate(source_kind="fvb_scope", only_fields=["width"])
        selected, _ = select_candidates(
            [cand], [rule(source_kind="fvb_scope")],
            fieldname="width", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], ["width"])
        self.assertFalse(selected[0]["hide_all"])

    def test_nguon_khong_gioi_han_rule_gioi_han(self):
        cand = candidate(source_kind="fvb_scope", only_fields=[])
        selected, _ = select_candidates(
            [cand], [rule(source_kind="fvb_scope", only_fields='["qty"]')],
            fieldname="qty", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], ["qty"])
        self.assertFalse(selected[0]["hide_all"])

    def test_ca_hai_gioi_han_thi_lay_giao(self):
        cand = candidate(source_kind="fvb_scope",
                         only_fields=["width", "qty"])
        selected, _ = select_candidates(
            [cand],
            [rule(source_kind="fvb_scope", only_fields='["qty","height"]')],
            fieldname="qty", default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], ["qty"])
        self.assertFalse(selected[0]["hide_all"])

    def test_giao_rong_thi_hide_all(self):
        """Giao rỗng ⇒ `hide_all=True`, `only_fields=[]` (KHÔNG phải unrestricted)."""
        cand = candidate(source_kind="fvb_scope", only_fields=["width"])
        selected, _ = select_candidates(
            [cand], [rule(source_kind="fvb_scope", only_fields='["qty"]')],
            fieldname=None, default_action=EXCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], [])
        self.assertTrue(selected[0]["hide_all"])

    def test_candidate_khong_khop_rule_thi_hide_all_false(self):
        cand = candidate(source_kind="cost_bucket", only_fields=[])
        selected, _ = select_candidates(
            [cand], [], default_action=INCLUDE_ALL)
        self.assertEqual(selected[0]["only_fields"], [])
        self.assertFalse(selected[0]["hide_all"])

    def test_require_value_la_cong_toan_cuc_trong_include_all(self):
        """Rule đòi giá trị, biến rỗng ⇒ loại — kể cả INCLUDE_ALL."""
        cands = [candidate(value="—", has_value=False)]
        selected, stats = select_candidates(
            cands, [rule(require_value=1)], default_action=INCLUDE_ALL)
        self.assertEqual(selected, [])
        self.assertEqual(stats["excluded_by_rules"], 1)

    def test_rule_tat_khong_tac_dung(self):
        cands = [candidate(), candidate(name="X", source_kind="formula_global")]
        selected, _ = select_candidates(
            cands, [rule(action="Exclude", is_active=0)])
        self.assertEqual(len(selected), 2)


class TestActiveSourceKinds(unittest.TestCase):
    ALL = ["cost_bucket", "formula_global", "slug_reference", "row_literal"]

    def test_exclude_all_chi_nguon_include(self):
        rules = [rule(source_kind="cost_bucket"),
                 rule(action="Exclude", source_kind="formula_global")]
        kinds = active_source_kinds(rules, EXCLUDE_ALL, self.ALL)
        self.assertEqual(kinds, {"cost_bucket"})

    def test_include_all_khong_rule_chay_tat_ca(self):
        kinds = active_source_kinds([], INCLUDE_ALL, self.ALL)
        self.assertEqual(kinds, {"cost_bucket", "formula_global",
                                 "row_literal"})

    def test_include_all_co_rule_chi_chay_nguon_do(self):
        kinds = active_source_kinds(
            [rule(source_kind="cost_bucket")], INCLUDE_ALL, self.ALL)
        self.assertEqual(kinds, {"cost_bucket"})

    def test_slug_reference_khong_bao_gio_la_adapter(self):
        kinds = active_source_kinds(
            [rule(source_kind="slug_reference")], EXCLUDE_ALL, self.ALL)
        self.assertEqual(kinds, set())


class TestDedupe(unittest.TestCase):
    def test_uu_tien_co_gia_tri(self):
        empty = candidate(name="TONG_M2", value="—", has_value=False,
                          source_kind="variable_library_system",
                          source_ref="TONG_M2", adapter_order=30)
        valued = candidate(name="TONG_M2", value=5.2, has_value=True,
                           source_kind="fvb_scope", source_ref="TONG_M2",
                           adapter_order=10)
        kept, duplicates = dedupe_candidates([empty, valued])
        self.assertEqual(kept[0]["source_kind"], "fvb_scope")
        self.assertEqual(len(duplicates), 1)
        self.assertEqual(duplicates[0]["name"], "TONG_M2")
        self.assertEqual(duplicates[0]["kept"], "fvb_scope:TONG_M2")
        self.assertEqual(duplicates[0]["dropped"],
                         ["variable_library_system:TONG_M2"])

    def test_hoa_thi_theo_sort_order_roi_adapter(self):
        a = candidate(name="X", sort_order=50, adapter_order=10)
        b = candidate(name="X", sort_order=10, adapter_order=99)
        kept, _ = dedupe_candidates([a, b])
        self.assertEqual(kept[0]["sort_order"], 10)
        self.assertEqual(kept[0]["adapter_order"], 99)

        c = candidate(name="Y", sort_order=10, adapter_order=20)
        d = candidate(name="Y", sort_order=10, adapter_order=10)
        kept, _ = dedupe_candidates([c, d])
        self.assertEqual(kept[0]["adapter_order"], 10)

    def test_khong_bao_gio_bo_im_lang(self):
        cands = [candidate(name="A"), candidate(name="B"),
                 candidate(name="A", source_kind="formula_global",
                           source_ref="A")]
        kept, duplicates = dedupe_candidates(cands)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(duplicates), 1)

    def test_bo_candidate_khong_co_ten(self):
        kept, duplicates = dedupe_candidates([candidate(name="")])
        self.assertEqual(kept, [])
        self.assertEqual(duplicates, [])

    def test_hop_pham_vi_field_khi_trung_ten(self):
        """Một nguồn không giới hạn ⇒ tên biến không giới hạn."""
        wide = candidate(name="X", only_fields=[])
        narrow = candidate(name="X", only_fields=["width"],
                           source_kind="fvb_scope", source_ref="X")
        kept, _ = dedupe_candidates([wide, narrow])
        self.assertEqual(kept[0]["only_fields"], [])
        # Không sửa candidate gốc của nguồn.
        self.assertEqual(narrow["only_fields"], ["width"])

    def test_hop_pham_vi_field_giu_thu_tu(self):
        a = candidate(name="X", only_fields=["width"])
        b = candidate(name="X", only_fields=["qty"],
                      source_kind="fvb_scope", source_ref="X")
        kept, _ = dedupe_candidates([a, b])
        self.assertEqual(kept[0]["only_fields"], ["width", "qty"])
        self.assertFalse(kept[0]["hide_all"])

    def test_hop_hide_all_voi_nguon_khong_gioi_han(self):
        """Một entry hide_all + một entry không giới hạn ⇒ unrestricted thắng."""
        hidden = candidate(name="X", only_fields=[], hide_all=True)
        wide = candidate(name="X", only_fields=[], hide_all=False,
                         source_kind="fvb_scope", source_ref="X")
        kept, _ = dedupe_candidates([hidden, wide])
        self.assertEqual(kept[0]["only_fields"], [])
        self.assertFalse(kept[0]["hide_all"])

    def test_hop_hai_entry_hide_all(self):
        """Tất cả entry đều hide_all ⇒ winner cũng hide_all."""
        a = candidate(name="X", only_fields=[], hide_all=True)
        b = candidate(name="X", only_fields=[], hide_all=True,
                      source_kind="fvb_scope", source_ref="X")
        kept, _ = dedupe_candidates([a, b])
        self.assertEqual(kept[0]["only_fields"], [])
        self.assertTrue(kept[0]["hide_all"])


class TestBuildGroups(unittest.TestCase):
    def test_gom_nhom_va_sap_xep(self):
        cands = [
            candidate(name="B", group="02", sort_order=20),
            candidate(name="A", group="01", sort_order=10),
            candidate(name="C", group="01", sort_order=15),
        ]
        groups = build_groups(cands)
        self.assertEqual([g["label"] for g in groups], ["01", "02"])
        self.assertEqual([v["name"] for v in groups[0]["variables"]],
                         ["A", "C"])
        self.assertEqual(groups[0]["sort_order"], 10)

    def test_candidate_thieu_group_vao_nhom_khac(self):
        groups = build_groups([candidate(group="")])
        self.assertEqual(groups[0]["label"], "Khác")


if __name__ == "__main__":
    unittest.main(verbosity=2)
