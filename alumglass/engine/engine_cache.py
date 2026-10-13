"""Cache `FormulaEngine` theo NỘI DUNG công thức — 1 BOM phục vụ nhiều sản phẩm.

VÌ SAO CẦN
──────────
`FormulaEngine.__init__` là chỗ đắt: nó parse + biên dịch từng công thức và
sắp topo (DAG). Đo trên chính hình dạng công thức BOM của AlumGlass (156
công thức — kính/khung/phụ kiện + cross-reference + synthetic trio):

    khởi tạo FormulaEngine :  2 018 µs   ← 97 % thời gian
    calculate()            :     37 µs
    build + calculate      :  2 072 µs

`BomOrchestrator` dựng LẠI engine ở mỗi lần tính (B4 và B6), cho MỖI dòng
báo giá. Một báo giá 20 dòng cùng BOM ⇒ 20 lần biên dịch lại **cùng một danh
sách công thức y hệt**. Cache bỏ hẳn phần đó: **56×** nhanh hơn ở đường B4.

VÌ SAO KHOÁ THEO NỘI DUNG LÀ ĐÚNG (⛔ không phải theo `al_bom_version`)
──────────────────────────────────────────────────────────────────────
BOM (bản chất) chỉ chứa **thuần biến và hằng**, ⛔ không chứa giá trị đầu vào:
`{slug}__width` là một CÔNG THỨC, còn 2400 là giá trị nằm trong `context`.
Đo được: đổi `W`/`H` giữa 2 lần gọi KHÔNG đổi một ký tự nào của danh sách
công thức (tập biến phụ `extra_items` lấy từ config của `calc_pattern` +
`input_vars` của Bom Item — xem `bom_orchestrator.b3_build_formulas`).

⇒ Vân tay của danh sách `(name, formula)` CHÍNH LÀ danh tính của BOM. Kèm
hệ quả tốt: sửa 1 công thức trong Bom Item là vân tay đổi ⇒ **cache tự vô
hiệu**, ⛔ không cần ai nhớ gọi `clear()`.

VÌ SAO DÙNG LẠI ENGINE LÀ AN TOÀN
─────────────────────────────────
Đã đọc mã lõi `FormulaEngine.calculate()` (`engine_core.py:861`):
  • `local = inputs.copy()` — ⛔ không sửa dict người gọi;
  • `self._last_errors = {}` / `_last_warnings = []` — RESET đầu mỗi lần gọi,
    nên lỗi/cảnh báo ⛔ không tích luỹ qua các lần;
  • trả dict MỚI dựng từ `_topo_order`.
Đối chứng chạy thật: gọi lại engine với context cũ trả về kết quả **trùng
khít** lần đầu, còn context khác cho kết quả khác (540 000 vs 950 400).

⚠️ GIỚI HẠN — ⛔ CHỈ dùng cho đường `formulas=`. Đường `child_tables` của
`FlexibleFormulaEngine` KHÔNG cache được bằng khoá nội dung: nó nhúng GIÁ TRỊ
cột vào chuỗi công thức (`_inject_row_values`) và ghi ngược vào dòng
(`_write_back`) ⇒ cùng tên công thức mà nội dung khác nhau theo dữ liệu. Đã
đo được ca sai im lặng: 700 thật vs 400 lấy từ cache.
"""

import hashlib
import threading
from collections import OrderedDict

# Số engine giữ lại mặc định. Đo bộ nhớ THẬT bằng `tracemalloc` (mỗi mục là
# 1 FormulaEngine đã biên dịch + topo):
#     50 công thức → 175 KB   |  250 công thức → 429 KB  |  400 công thức → 607 KB
# ⇒ 16 mục ≈ 3–10 MB/cache; 2 cache (BOM + cost) ⇒ ~6–20 MB/worker. Đủ rộng cho
# một site nhiều BOM đang dùng mà vẫn chặn phình bộ nhớ. Chỉnh được qua
# `frappe.conf.alumglass_engine_cache_size`.
DEFAULT_MAXSIZE = 16

#: Số lần build / trúng cache — để `stats()` trả lời được "cache có chạy không".
#: ⚠️ Cộng dồn suốt đời tiến trình; muốn số của riêng một lượt đo thì gọi
#: `reset_engine_cache_stats()` (hoặc `clear_engine_caches()`) TRƯỚC khi đo.
_STATS = {"hits": 0, "misses": 0, "builds": 0, "evictions": 0}
_STATS_LOCK = threading.Lock()


def formula_fingerprint(formulas):
    """Vân tay nội dung của danh sách công thức `[{"name","formula"}, ...]`.

    Băm cả TÊN lẫn THÂN công thức, và băm theo THỨ TỰ (⛔ không sort): thứ tự
    là một phần của cấu hình đang có, giữ nguyên thì khoá chặt hơn — thà trượt
    cache còn hơn gộp nhầm hai cấu hình khác nhau vào một mục.
    """
    h = hashlib.blake2b(digest_size=16)
    for f in formulas or []:
        name = f.get("name", "") if isinstance(f, dict) else ""
        expr = f.get("formula", "") if isinstance(f, dict) else ""
        h.update(str(name).encode("utf-8", "replace"))
        h.update(b"\x00")
        h.update(str(expr).encode("utf-8", "replace"))
        h.update(b"\x01")
    return h.hexdigest()


def make_key(kind, formulas, funcset, **behaviour):
    """Khoá cache = (loại engine, vân tay công thức, bộ hàm, tham số hành vi).

    `behaviour` phải chứa MỌI tham số đổi kết quả tính (`on_error`,
    `default_value`, `deterministic`…) — hai engine khác hành vi mà chung khoá
    là lỗi im lặng ở đúng chỗ khó thấy nhất: tiền.
    """
    parts = [str(kind), formula_fingerprint(formulas), str(funcset)]
    for k in sorted(behaviour):
        parts.append("%s=%r" % (k, behaviour[k]))
    return "|".join(parts)


def cache_enabled():
    """Công tắc tắt cache — `frappe.conf.alumglass_engine_cache = 0`.

    Có công tắc vì đây là đường tính giá đang phục vụ khách: khi nghi ngờ,
    người vận hành phải tắt được ngay mà ⛔ không phải sửa mã.
    """
    try:
        import frappe
        conf = getattr(frappe, "conf", None)
        if conf is None:
            return True
        val = conf.get("alumglass_engine_cache")
        if val is None:
            return True
        return str(val).strip().lower() not in ("0", "false", "no", "off", "")
    except Exception:
        # Không đọc được conf (test stub, ngoài request) → cache vẫn đúng,
        # nên mặc định BẬT. Nuốt lỗi ở đây là chủ đích: hỏng conf không được
        # làm hỏng việc tính giá.
        return True


class FormulaEngineCache:
    """LRU có khoá theo nội dung, an toàn đa luồng.

    ⛔ Không cache ngoại lệ: factory ném lỗi thì lỗi đi thẳng ra ngoài và
    ⛔ không có mục rác nào được ghi lại.
    """

    def __init__(self, maxsize=DEFAULT_MAXSIZE, name="engine"):
        self.maxsize = max(1, int(maxsize))
        self.name = name
        self._items = OrderedDict()
        self._lock = threading.RLock()
        self._maxsize_synced = False

    def _sync_maxsize(self):
        """Đọc `frappe.conf.alumglass_engine_cache_size` MỘT LẦN.

        Đọc LƯỜI (⛔ không ở `__init__`): cache được tạo ngay lúc import module,
        còn `frappe.conf` chỉ chắc chắn có sau khi Frappe khởi tạo xong. Đọc ở
        `__init__` sẽ luôn nhận giá trị mặc định và công tắc chỉnh size thành
        đồ trang trí.
        """
        if self._maxsize_synced:
            return
        self._maxsize_synced = True
        try:
            import frappe
            val = (getattr(frappe, "conf", None) or {}).get(
                "alumglass_engine_cache_size")
            if val is not None:
                self.maxsize = max(1, int(val))
        except Exception:
            # Conf hỏng/không đọc được ⇒ giữ mặc định. Hỏng cấu hình ⛔ không
            # được làm hỏng việc tính giá.
            pass

    def get_or_build(self, key, factory):
        self._sync_maxsize()
        if not cache_enabled():
            _STATS["builds"] += 1
            return factory()

        with self._lock:
            hit = self._items.get(key)
            if hit is not None:
                self._items.move_to_end(key)
                _STATS["hits"] += 1
                return hit

        # Dựng NGOÀI lock: biên dịch công thức tốn ~2 ms, giữ lock suốt lúc đó
        # sẽ chặn mọi luồng khác. Hai luồng cùng trượt thì cùng dựng — chấp
        # nhận được (kết quả như nhau), đổi lại ⛔ không có khoá dài.
        engine = factory()
        _STATS["builds"] += 1

        with self._lock:
            existing = self._items.get(key)
            if existing is not None:
                # Luồng khác vừa dựng xong cùng khoá → dùng bản của nó, bỏ bản
                # này. Kết quả y hệt nhau nên ⛔ không mất gì.
                self._items.move_to_end(key)
                return existing
            _STATS["misses"] += 1
            self._items[key] = engine
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)
                _STATS["evictions"] += 1
            return engine

    def clear(self):
        with self._lock:
            self._items.clear()

    def stats(self):
        with self._lock:
            size = len(self._items)
        out = dict(_STATS)
        out.update({"name": self.name, "size": size, "maxsize": self.maxsize})
        return out


#: Cache dùng chung cho BOM (B4) — xem `bom_orchestrator.b4_calculate_bom_items`.
BOM_ENGINE_CACHE = FormulaEngineCache(name="alumglass-bom-items")

#: Cache cho cost template (B6) — xem `bom_orchestrator.b6_calculate_cost_template`.
COST_ENGINE_CACHE = FormulaEngineCache(name="alumglass-cost-template")


def engine_cache_stats():
    """Số liệu 2 cache — gọi tay khi cần xem cache có thật sự trúng."""
    return {"bom_items": BOM_ENGINE_CACHE.stats(),
            "cost_template": COST_ENGINE_CACHE.stats()}


def clear_engine_caches(reset_stats=True):
    """Xoá tay cả 2 cache (dùng khi gỡ rối; bình thường ⛔ không cần —
    sửa công thức là vân tay đổi nên cache tự vô hiệu).

    `reset_stats=True` (mặc định) đưa bộ đếm về 0. ⚠️ Trước đây hàm này ⛔
    KHÔNG reset `_STATS`, mà `_STATS` là biến cấp module **cộng dồn suốt đời
    tiến trình** ⇒ số đọc ra sau khi `clear()` vẫn là số luỹ kế, ⛔ không phải
    số của lượt đo đang chạy. Đã một lần đọc sai vì việc này: tưởng công tắc
    tắt cache hỏng (thấy "hits" vẫn tăng ở lượt TẮT), thật ra là số CŨ cộng dồn
    — xem docs/review-alumglass.md mục 10.

    Truyền `reset_stats=False` khi muốn giữ bộ đếm (ví dụ đọc số rồi mới dọn).
    """
    BOM_ENGINE_CACHE.clear()
    COST_ENGINE_CACHE.clear()
    if reset_stats:
        return reset_engine_cache_stats()


def reset_engine_cache_stats():
    """Đưa `_STATS` về 0. Tách riêng để gọi được mà ⛔ không đụng cache."""
    with _STATS_LOCK:
        for key in _STATS:
            _STATS[key] = 0
    return dict(_STATS)
