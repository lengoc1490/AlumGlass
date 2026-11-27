"""Đọc tổng hợp cấu hình một sản phẩm (B8/Đ1) — CHỈ ĐỌC.

Một sản phẩm (`AL BOM`) tham chiếu tới 6 nơi cấu hình rời nhau: bộ BOM, bộ
phụ kiện, bộ biến, mẫu tính giá, hồ sơ biến và các quy tắc (AL Rule) đang
dùng. Trước đây người dùng phải mở 4-6 form chỉ để định vị — trang "Cấu hình
sản phẩm" gom chúng về một màn. Module này là API duy nhất sau trang đó.

Nguyên tắc (theo §4.3 Đ1 của `docs/design/gop-noi-cau-hinh-bien-va-tinh-toan.md`):

  · CHỈ ĐỌC — ⛔ không ghi, ⛔ không tạo DocType mới, ⛔ không chép dữ liệu.
  · **Cô lập lỗi TỪNG khối**: một khối hỏng không được làm hỏng cả trang; nó
    phải hiện câu lỗi tiếng Việt thay vì im lặng biến mất (im lặng = trang
    "nói dối" là sản phẩm không có cấu hình).
  · ⛔ Không trả traceback/mã lỗi kỹ thuật ra người dùng — log ở server.
  · Ưu tiên tên người đọc được (`set_name`, `template_name`, `profile_name`,
    `rule_name`…); mã chỉ đi kèm làm phụ. Thiếu tên thì mới dùng mã.

Mỗi khối trả về:
    {key, title, doctype, ok, error, name, code, label, link, detail, children}

  · `link` là route Desk `/app/<doctype-slug>/<name>` để nút "Mở" nhảy đúng
    form; khối không có bản ghi (hoặc lỗi) thì `link` rỗng.
  · `children` chỉ dùng cho khối nhiều bản ghi (Quy tắc đang dùng).
"""

from urllib.parse import quote

import frappe
from frappe import _

PRODUCT_DOCTYPE = "AL BOM"


class _BlockFailure(Exception):
	"""Một khối không đọc được.

	`message` là câu tiếng Việt đã sẵn sàng hiển thị cho người dùng —
	⛔ không chứa traceback, tên class exception hay đường dẫn tệp.
	"""

	def __init__(self, message):
		super().__init__(message)
		self.message = message


# ══════════════════════════════════════════════════════════════════════
# Tiện ích
# ══════════════════════════════════════════════════════════════════════
def _text(value):
	"""Ép về chuỗi đã cắt khoảng trắng; None/0/False → ""."""
	if value is None:
		return ""
	return str(value).strip()


def _slug(doctype):
	"""Slug route Desk: 'AL Variable Profile' → 'al-variable-profile'."""
	return _text(doctype).lower().replace("_", "-").replace(" ", "-")


def _route(doctype, name):
	"""Route Desk để mở đúng form. Trả "" khi thiếu doctype hoặc tên."""
	if not doctype or not name:
		return ""
	return "/app/{0}/{1}".format(_slug(doctype), quote(_text(name), safe=""))


def _read_doc(doctype, name, noun, name_hint=None):
	"""Đọc 1 bản ghi; mọi lỗi được đổi thành `_BlockFailure` câu tiếng Việt."""
	if not frappe.db.exists(doctype, name):
		if name_hint:
			raise _BlockFailure(_("Không đọc được {0} {1} — có thể đã bị xoá.").format(noun, name_hint))
		raise _BlockFailure(_("Không đọc được {0} — {0} có thể đã bị xoá.").format(noun))

	if not frappe.has_permission(doctype, "read", doc=name):
		raise _BlockFailure(
			_("Bạn không có quyền xem {0}. Liên hệ quản trị viên để được cấp quyền.").format(noun)
		)

	try:
		return frappe.get_doc(doctype, name)
	except Exception:
		# Log đầy đủ ở server; người dùng chỉ thấy câu hành động được.
		frappe.log_error(frappe.get_traceback(), "product_config: đọc {0} {1}".format(doctype, name))
		raise _BlockFailure(
			_("Không đọc được {0} — vui lòng thử tải lại. Nếu vẫn lỗi, báo quản trị viên.").format(noun)
		)


# ══════════════════════════════════════════════════════════════════════
# Nguồn của từng khối
# ══════════════════════════════════════════════════════════════════════
def _get_bom_set(state):
	return _text((state.get("bom") or {}).get("bom_set"))


def _get_accessory_set(state):
	# Sản phẩm trỏ trực tiếp; nếu không thì lấy mặc định của bộ BOM.
	name = _text((state.get("bom") or {}).get("pk_set"))
	if name:
		return name
	return _text((state.get("bom_set") or {}).get("default_accessory_set"))


def _get_variable_set(state):
	for key in ("bom_set", "accessory_set"):
		name = _text((state.get(key) or {}).get("variable_set"))
		if name:
			return name
	return ""


def _get_cost_template(state):
	return _text((state.get("bom") or {}).get("default_cost_template"))


def _get_variable_profile(state):
	for key in ("bom_set", "accessory_set", "cost_template"):
		name = _text((state.get(key) or {}).get("variable_profile"))
		if name:
			return name
	return ""


# ── Câu mô tả phụ (detail) — đếm số dòng, KHÔNG thêm truy vấn ──────────
def _count_detail(field, noun):
	def inner(doc):
		return "{0} {1}".format(len(doc.get(field) or []), noun)

	return inner


def _product_detail(doc):
	if doc.get("is_active") in (0, "0", False):
		return _("Sản phẩm đang ngừng dùng.")
	return ""


# ══════════════════════════════════════════════════════════════════════
# Định nghĩa khối — giữ đúng thứ tự hiển thị trên trang
# ══════════════════════════════════════════════════════════════════════
_BLOCKS = (
	{
		"key": "product",
		"title": "Sản phẩm",
		"doctype": PRODUCT_DOCTYPE,
		"noun": "sản phẩm",
		"label_fields": ("bom_name",),
		"code_field": "bom_code",
		"detail": _product_detail,
	},
	{
		"key": "bom_set",
		"title": "Bộ BOM",
		"doctype": "AL Bom Set",
		"noun": "bộ BOM",
		"source": _get_bom_set,
		"label_fields": ("set_name",),
		"code_field": "set_code",
		"detail": _count_detail("items", "dòng vật tư"),
		"missing": "Sản phẩm chưa gắn bộ BOM.",
	},
	{
		"key": "accessory_set",
		"title": "Bộ phụ kiện",
		"doctype": "AL Accessory Set",
		"noun": "bộ phụ kiện",
		"source": _get_accessory_set,
		"label_fields": ("set_name",),
		"code_field": "set_code",
		"detail": _count_detail("items", "dòng phụ kiện"),
		"missing": "Sản phẩm chưa gắn bộ phụ kiện.",
	},
	{
		"key": "variable_set",
		"title": "Bộ biến",
		"doctype": "AL Variable Set",
		"noun": "bộ biến",
		"source": _get_variable_set,
		"label_fields": ("set_name",),
		"code_field": "set_code",
		"detail": _count_detail("items", "biến"),
		"missing": "Bộ BOM/phụ kiện chưa gắn bộ biến.",
	},
	{
		"key": "cost_template",
		"title": "Mẫu tính giá",
		"doctype": "AL Cost Template",
		"noun": "mẫu tính giá",
		"source": _get_cost_template,
		"label_fields": ("template_name",),
		"code_field": "template_code",
		"detail": _count_detail("items", "dòng chi phí"),
		"missing": "Sản phẩm chưa gắn mẫu tính giá mặc định.",
	},
	{
		"key": "variable_profile",
		"title": "Hồ sơ biến",
		"doctype": "AL Variable Profile",
		"noun": "hồ sơ biến",
		"source": _get_variable_profile,
		"label_fields": ("profile_name",),
		"code_field": "profile_code",
		"detail": _count_detail("rules", "quy tắc lọc"),
		"missing": ("Chưa gắn hồ sơ biến — ô công thức sẽ hiện toàn bộ biến thay vì danh sách đã thu hẹp."),
	},
	{
		"key": "rules",
		"title": "Quy tắc đang dùng",
		"doctype": "AL Rule",
		"noun": "quy tắc",
		"label_fields": ("rule_name",),
		"code_field": "rule_code",
	},
)


def _blank_block(defn):
	return {
		"key": defn["key"],
		"title": defn["title"],
		"doctype": defn["doctype"],
		"ok": False,
		"state": "error",
		"error": "",
		"fix_link": "",
		"name": "",
		"code": "",
		"label": "",
		"link": "",
		"detail": "",
		"children": [],
	}


def _fill_block(block, defn, doc):
	"""Điền 1 khối từ bản ghi đã đọc được."""
	block["name"] = _text(doc.get("name"))

	code = _text(doc.get(defn["code_field"])) or block["name"]
	label = ""
	for fieldname in defn.get("label_fields") or ():
		value = _text(doc.get(fieldname))
		if value:
			label = value
			break

	block["code"] = code
	block["label"] = label or code
	block["link"] = _route(defn["doctype"], block["name"])

	detail = defn.get("detail")
	block["detail"] = detail(doc) if detail else ""
	block["ok"] = True
	block["state"] = "ok"


def _read_error(noun):
	return _("Không đọc được {0} — vui lòng thử tải lại. Nếu vẫn lỗi, báo quản trị viên.").format(noun)


# ══════════════════════════════════════════════════════════════════════
# Khối "Quy tắc đang dùng" — nhiều bản ghi, lỗi từng quy tắc
# ══════════════════════════════════════════════════════════════════════
def _build_rules_block(defn, state):
	block = _blank_block(defn)
	bom_set = state.get("bom_set")

	if not bom_set:
		block["state"] = "error"
		block["error"] = _("Chưa xác định được quy tắc vì không đọc được sản phẩm.")
		return block

	codes = []
	for row in bom_set.get("items") or []:
		code = _text(row.get("item_rule"))
		if code and code not in codes:
			codes.append(code)

	if not codes:
		# Không dùng quy tắc nào là trạng thái HỢP LỆ, không phải lỗi.
		block["ok"] = True
		block["state"] = "ok"
		block["label"] = _("Chưa có quy tắc nào được dùng")
		block["detail"] = _("Bộ BOM hiện không dùng quy tắc nào.")
		return block

	children = []
	failures = []
	for code in codes:
		try:
			doc = _read_doc("AL Rule", code, "quy tắc", name_hint=code)
		except _BlockFailure as exc:
			failures.append(exc.message)
			children.append(
				{
					"name": "",
					"code": code,
					"label": code,  # chưa đọc được tên ⇒ dùng mã làm nhãn
					"link": "",
					"error": exc.message,
				}
			)
			continue

		children.append(
			{
				"name": _text(doc.get("name")) or code,
				"code": _text(doc.get("rule_code")) or code,
				"label": (_text(doc.get("rule_name")) or _text(doc.get("rule_code")) or code),
				"link": _route("AL Rule", code),
				"error": "",
			}
		)

	block["children"] = children

	first_ok = next((c for c in children if not c["error"]), None)
	if first_ok:
		block["name"] = first_ok["name"]
		block["code"] = first_ok["code"]
		block["label"] = first_ok["label"]
		block["link"] = first_ok["link"]

	if failures:
		block["ok"] = False
		if len(failures) == 1:
			block["error"] = failures[0]
		else:
			block["error"] = _("Không đọc được {0} quy tắc đang dùng. Xem chi tiết bên dưới.").format(
				len(failures)
			)
		return block

	block["ok"] = True
	block["state"] = "ok"
	names = ", ".join(child["label"] for child in children)
	if len(children) == 1:
		block["detail"] = _("1 quy tắc đang dùng: {0}").format(names)
	else:
		block["detail"] = _("{0} quy tắc đang dùng: {1}").format(len(children), names)
	return block


# ══════════════════════════════════════════════════════════════════════
# API
# ══════════════════════════════════════════════════════════════════════
@frappe.whitelist()
def get_product_config(doctype=None, docname=None):
	"""Trả cấu hình đầy đủ của MỘT sản phẩm — chỉ đọc, lỗi cô lập từng khối.

	:param doctype: chỉ nhận "AL BOM" (mặc định).
	:param docname: mã bản ghi AL BOM.
	"""
	doctype = _text(doctype) or PRODUCT_DOCTYPE
	docname = _text(docname)

	if doctype != PRODUCT_DOCTYPE:
		frappe.throw(_("Trang cấu hình chỉ đọc sản phẩm (AL BOM)."))
	if not docname:
		frappe.throw(_("Chưa chọn sản phẩm cần xem cấu hình."))

	read_at = frappe.utils.now()
	state = {}

	product_def = _BLOCKS[0]
	product_block = _blank_block(product_def)
	try:
		bom = _read_doc(PRODUCT_DOCTYPE, docname, product_def["noun"])
		state["bom"] = bom
		_fill_block(product_block, product_def, bom)
		if bom.get("is_active") in (0, "0", False):
			# Ngừng dùng là trạng thái NGƯỜI DÙNG phải thấy ngay, ⛔ chỉ là
			# một dòng xám nhỏ dưới mã sản phẩm.
			product_block["state"] = "warning"
			product_block["detail"] = _(
				"Sản phẩm đã ngừng dùng — báo giá mới nên cân nhắc."
			)
	except _BlockFailure as exc:
		product_block["error"] = exc.message
	except Exception:
		frappe.log_error(
			frappe.get_traceback(), "product_config: đọc {0} {1}".format(PRODUCT_DOCTYPE, docname)
		)
		product_block["error"] = _read_error(product_def["noun"])

	blocks = [product_block]

	for defn in _BLOCKS[1:]:
		if defn["key"] == "rules":
			blocks.append(_build_rules_block(defn, state))
			continue

		block = _blank_block(defn)
		if not product_block["ok"]:
			# Không đọc được sản phẩm ⇒ nói rõ phụ thuộc, ⛔ đừng nói
			# "chưa gắn" (sai sự thật, đẩy người dùng đi cấu hình lại).
			block["error"] = _("Chưa xác định được {0} vì không đọc được sản phẩm.").format(defn["noun"])
			blocks.append(block)
			continue

		try:
			name = defn["source"](state)
			if not name:
				block["state"] = "empty"
				block["error"] = defn["missing"]
				# Đường thoát ĐÚNG cho trạng thái "chưa gắn": mở sản phẩm để
				# gắn, ⛔ bắt bấm "Tải lại" (không có gì hỏng để tải lại).
				block["fix_link"] = product_block["link"] or ""
				blocks.append(block)
				continue
			doc = _read_doc(defn["doctype"], name, defn["noun"])
			state[defn["key"]] = doc
			_fill_block(block, defn, doc)
		except _BlockFailure as exc:
			block["state"] = "error"
			block["error"] = exc.message
		except Exception:
			frappe.log_error(
				frappe.get_traceback(), "product_config: đọc {0} của {1}".format(defn["doctype"], docname)
			)
			block["state"] = "error"
			block["error"] = _read_error(defn["noun"])

		blocks.append(block)

	return {
		"ok": product_block["ok"],
		"doctype": doctype,
		"docname": docname,
		"read_at": read_at,
		"read_at_display": _read_at_display(read_at),
		"blocks": blocks,
	}


def _read_at_display(read_at):
	"""Giờ đọc dạng người đọc: '27-11-2026 16:20'. Lỗi định dạng ⇒ chuỗi gốc."""
	try:
		return frappe.utils.get_datetime(read_at).strftime("%d-%m-%Y %H:%M")
	except Exception:
		return _text(read_at)
