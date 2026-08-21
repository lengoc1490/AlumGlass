# -*- coding: utf-8 -*-
"""C5 — Tạo Print Format 'Báo giá AlumGlass'.

App chưa có cơ chế fixture Print Format → dùng patch (chạy 1 lần qua patches.txt).
Idempotent: helper `create_bao_gia_print_format()` bỏ qua nếu Print Format đã tồn tại.
"""


def execute():
    from alumglass.setup.print_format import create_bao_gia_print_format
    create_bao_gia_print_format()
