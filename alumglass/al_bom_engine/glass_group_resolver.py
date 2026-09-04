"""Glass group rep resolver — DÙNG CHUNG giữa api.get_variable_set_for_bom
(dựng dialog "Kính theo vị trí") và engine.BomOrchestrator (đọc lại lựa chọn
kính user đã lưu). Tách riêng để 2 nơi KHÔNG BAO GIỜ lệch công thức tính khoá
`rep` — nếu lệch, `glass_master_map` lưu từ dialog sẽ không khớp key khi
engine tra cứu lúc tính giá → chọn kính không có tác dụng (tái phát y hệt bug
glass_master_map trước đây).
"""


def glass_group_rep(item):
    """Rep key nhóm/chọn kính theo vị trí cho 1 dòng AL Bom Item (category=KINH).

    Ưu tiên `default_glass_master` khi AL Bom Set CÓ cấu hình sẵn — cho phép
    nhiều dòng dùng CHUNG 1 selector nếu cố tình set cùng 1 mã (case hiếm).

    Khi dòng KHÔNG cấu hình `default_glass_master` (trường hợp phổ biến nhất
    trong thực tế — quá nhiều loại kính, KHÔNG thể hardcode 1 mã mặc định
    trong AL Bom Set, sản xuất/báo giá phải tự chọn đúng lúc lập báo giá) →
    fallback dùng CHÍNH slug của dòng làm rep. Đảm bảo MỖI vị trí luôn có
    đúng 1 selector độc lập, KHÔNG cần tạo Glass Master placeholder nào.

    Returns:
        (rep: str, is_real_master: bool)
        is_real_master=True  → rep chính là 1 mã AL Glass Master thật, có
            thể dùng làm fallback hiển thị/tra cứu mặc định.
        is_real_master=False → rep chỉ là khoá tổng hợp theo slug, KHÔNG có
            ý nghĩa tra cứu Glass Master. Nếu user chưa chọn kính cho vị trí
            này (`glass_master_map` chưa có key này) → PHẢI trả về None ở
            nơi gọi, không được coi rep là item_code.
    """
    rep = (item.get("default_glass_master") or "").strip()
    if rep:
        return rep, True
    slug = item.get("slug") or ""
    return "__slug__%s" % slug, False
