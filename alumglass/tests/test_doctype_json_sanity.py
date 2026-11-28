"""Test THUẦN kiểm tính NHẤT QUÁN của mọi tệp DocType JSON trong app.

VÌ SAO CẦN
──────────
2026-11-28: `al_variable_set_item/al_variable_set_item.json` bị ghi đè bằng
**nguyên nội dung** của `al_variable_library.json` (cùng một `name`). Hậu quả
trên site: DocType `AL Variable Set Item` không tồn tại ⇒ mở bảng tham số báo
giá ném `DocType AL Variable Set Item not found`, và mọi biến của bộ biến
không nạp được ⇒ tính giá thiếu tham số.

Không test nào cũ bắt được vì mọi test chạy trên stub. Test này đọc THẲNG tệp
JSON (không cần site) và bắt đúng loại hỏng đó:

  1. `name` của DocType phải khớp TÊN THƯ MỤC (và không được trùng nhau).
  2. Mọi field `Table` / `Table MultiSelect` phải trỏ tới DocType CÓ trong app
     (bảng con luôn nằm trong app, không phải doctype của app khác).
  3. Mọi tên trong `field_order` phải có trong `fields`.
  4. `AL Variable Set.items` ⛔ trỏ vào chính `AL Variable Library`, và
     `AL Variable Set Item` phải tồn tại với `istable = 1`.

Chạy:
    python3 alumglass/tests/test_doctype_json_sanity.py
"""
import glob
import json
import os
import unittest

_APP_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

TABLE_TYPES = ("Table", "Table MultiSelect")


def _all_doctype_files():
    pattern = os.path.join(_APP_ROOT, "**", "doctype", "*", "*.json")
    return sorted(glob.glob(pattern, recursive=True))


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _is_doctype(doc):
    return (doc or {}).get("doctype") == "DocType"


class TestDoctypeJson(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = {}
        for path in _all_doctype_files():
            doc = _load(path)
            if not _is_doctype(doc):
                continue
            cls.docs[path] = doc

    def test_da_doc_duoc_tep(self):
        self.assertGreater(len(self.docs), 20, "không quét được tệp DocType")

    def test_ten_khop_thu_muc(self):
        wrong = []
        for path, doc in self.docs.items():
            folder = os.path.basename(os.path.dirname(path))
            if folder.replace("_", " ").lower() != (doc.get("name") or "").lower():
                wrong.append("%s → name=%r" % (path, doc.get("name")))
        self.assertEqual(wrong, [], "tên DocType lệch thư mục:\n" + "\n".join(wrong))

    def test_khong_trung_ten(self):
        seen = {}
        for path, doc in self.docs.items():
            seen.setdefault(doc.get("name"), []).append(path)
        dupes = {name: paths for name, paths in seen.items() if len(paths) > 1}
        self.assertEqual(dupes, {}, "DocType trùng tên: %s" % dupes)

    def test_bang_con_tro_toi_doctype_co_that(self):
        names = {doc.get("name") for doc in self.docs.values()}
        missing = []
        for path, doc in self.docs.items():
            for field in doc.get("fields") or []:
                if field.get("fieldtype") not in TABLE_TYPES:
                    continue
                options = field.get("options") or ""
                # Chỉ kiểm doctype CỦA APP ("AL …") — field bảng trỏ tới
                # doctype lõi (User / Sales Order / Employee) là hợp lệ.
                if not options.startswith("AL "):
                    continue
                if options not in names:
                    missing.append("%s.%s → %r"
                                   % (doc.get("name"), field.get("fieldname"),
                                      options))
        self.assertEqual(
            missing, [],
            "field bảng con trỏ tới DocType không có trong app:\n"
            + "\n".join(missing))

    def test_field_order_co_trong_fields(self):
        wrong = []
        for path, doc in self.docs.items():
            declared = {f.get("fieldname") for f in doc.get("fields") or []}
            for name in doc.get("field_order") or []:
                if name not in declared:
                    wrong.append("%s: %r" % (doc.get("name"), name))
        self.assertEqual(wrong, [], "field_order có tên lạ: %s" % wrong)


class TestVariableSetRegression(unittest.TestCase):
    """Đúng ca đã hỏng 2026-11-28 — giữ nguyên làm đối chứng."""

    def _doc(self, *parts):
        path = os.path.join(_APP_ROOT, "alumglass", "al_master_data",
                            "doctype", *parts)
        return _load(path)

    def test_variable_set_tro_toi_doctype_con(self):
        parent = self._doc("al_variable_set", "al_variable_set.json")
        field = next(f for f in parent["fields"]
                     if f.get("fieldname") == "items")
        self.assertEqual(field.get("options"), "AL Variable Set Item")
        self.assertNotEqual(field.get("options"), "AL Variable Library")

    def test_doctype_con_la_bang_con(self):
        child = self._doc("al_variable_set_item", "al_variable_set_item.json")
        self.assertEqual(child.get("name"), "AL Variable Set Item")
        self.assertEqual(child.get("istable"), 1)
        self.assertIn("variable",
                      {f.get("fieldname") for f in child.get("fields")})


if __name__ == "__main__":
    unittest.main(verbosity=2)
