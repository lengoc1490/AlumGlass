"""Color group rep resolver — DÙNG CHUNG giữa api.get_variable_set_for_bom
(dựng dialog "Màu sắc") và engine.BomOrchestrator (đọc lại lựa chọn màu user
đã lưu). Tách riêng để 2 nơi KHÔNG BAO GIỜ lệch công thức tính khoá `rep` —
nếu lệch, `color_master_map` lưu từ dialog sẽ không khớp key khi engine tra
cứu lúc tính giá → chọn màu không có tác dụng (tái phát y hệt bug
glass_master_map/color_master_map trước đây).

KHÁC glass_group_resolver: `default_color` KHÔNG có fallback theo slug. Dòng
không cấu hình `default_color` nghĩa là dòng đó CHỦ ĐÍCH luôn dùng 1 màu cố
định (VD thanh ke/lõi bên trong không theo màu công trình) — không tham gia
nhóm màu, không có selector, không bị can thiệp gì ở đây.
"""


def color_group_rep(item):
    """Rep key nhóm/chọn màu theo vị trí cho 1 dòng AL Bom Item hoặc
    AL Accessory Item.

    Returns:
        rep: str | None — mã AL Color Standard (đã tích "Mau dai dien") cấu
            hình sẵn trên dòng, hoặc None nếu dòng KHÔNG tham gia nhóm màu
            (default_color để trống — luôn dùng 1 màu cố định).
    """
    rep = (item.get("default_color") or "").strip()
    return rep or None