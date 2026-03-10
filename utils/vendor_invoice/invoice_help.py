# utils/vendor_invoice/invoice_help.py
# Help popover content for Vendor Invoice page
# Separated for maintainability — update help text here without touching main page.

import streamlit as st


def render_help_popover():
    """Render a ❓ help popover with usage guide, definitions, formulas, and Q&A."""
    with st.popover("❓", use_container_width=True):
        tab_guide, tab_defs, tab_qa = st.tabs([
            "📖 Hướng dẫn", "📐 Định nghĩa & Công thức", "💬 Q&A"
        ])

        _tab_guide(tab_guide)
        _tab_definitions(tab_defs)
        _tab_qa(tab_qa)


# ============================================================================
# TAB 1: Hướng dẫn sử dụng
# ============================================================================

def _tab_guide(tab):
    with tab:
        st.markdown("#### 📖 Hướng dẫn sử dụng")

        st.markdown("##### Tổng quan")
        st.markdown(
            "Trang **Vendor Invoice** quản lý toàn bộ hóa đơn mua hàng "
            "(Purchase Invoice) từ nhà cung cấp. Hỗ trợ hai loại hóa đơn:"
        )
        st.info(
            "🟢 **Commercial Invoice (CI)** — Hóa đơn thương mại, "
            "tạo từ hàng đã nhận (CAN lines)\n\n"
            "🔵 **Proforma Invoice (PI)** — Hóa đơn trả trước, "
            "tạo từ PO lines (chưa nhận hàng)"
        )

        st.markdown("##### Quy trình tạo hóa đơn (3 bước)")
        st.markdown(
            "**Bước 1 — Chọn nguồn & dòng hàng**\n"
            "- Chọn nguồn: *From CAN* (hàng đã nhận) hoặc *From PO* (trả trước)\n"
            "- Lọc theo Vendor, PO Number, Brand, Entity…\n"
            "- Tick chọn các dòng hàng cần invoice\n"
            "- Hệ thống validate: cùng 1 vendor, cùng 1 entity, cùng loại vendor\n\n"
            "**Bước 2 — Review Invoice**\n"
            "- Xác nhận loại hóa đơn (CI/PI) và thông tin ngày\n"
            "- Chọn currency & xem tỷ giá tự động\n"
            "- Kiểm tra payment terms → hệ thống tự tính due date\n"
            "- Nhập Commercial Invoice No. (bắt buộc với CI)\n"
            "- Xem bảng tổng hợp: Subtotal, VAT, Total\n\n"
            "**Bước 3 — Xác nhận & Tạo**\n"
            "- Review lần cuối toàn bộ thông tin\n"
            "- Đính kèm file (PDF/PNG/JPG, tối đa 10 files, 10MB/file)\n"
            "- Bấm **Create Invoice** để hoàn tất"
        )

        st.markdown("##### Quản lý hóa đơn")
        st.markdown(
            "- 👁️ **View** — Xem chi tiết hóa đơn và file đính kèm\n"
            "- ✏️ **Edit** — Sửa ngày, payment terms, commercial no., đính kèm thêm file\n"
            "- 🚫 **Void** — Hủy hóa đơn (chỉ áp dụng nếu chưa thanh toán hết)\n"
            "- 📥 **Export** — Xuất danh sách ra Excel hoặc CSV"
        )

        st.markdown("##### Phân quyền")
        st.markdown(
            "Chỉ các role **Admin**, **Inbound Manager**, **Supply Chain** "
            "mới có quyền tạo, sửa, hủy hóa đơn. "
            "Các role khác chỉ được xem (View) và xuất dữ liệu (Export)."
        )


# ============================================================================
# TAB 2: Định nghĩa & Công thức
# ============================================================================

def _tab_definitions(tab):
    with tab:
        st.markdown("#### 📐 Định nghĩa & Công thức")

        st.markdown("##### Các loại Invoice")
        st.markdown(
            "| Ký hiệu | Loại | Nguồn dữ liệu | Mô tả |\n"
            "|----------|------|----------------|-------|\n"
            "| **CI** (suffix `-P`) | Commercial Invoice | CAN lines | "
            "Hóa đơn cho hàng đã nhận, gắn với arrival_detail_id |\n"
            "| **PI** (suffix `-A`) | Proforma Invoice | PO lines | "
            "Hóa đơn trả trước, arrival_detail_id = NULL |"
        )

        st.markdown("##### Số lượng")
        st.markdown(
            "| Trường | Định nghĩa |\n"
            "|--------|------------|\n"
            "| **Eff Qty** (Effective Buying Quantity) | "
            "Số lượng mua thực tế trên PO (trừ cancelled) |\n"
            "| **Invoiced** (Total Invoiced Quantity) | "
            "Tổng số lượng đã invoice (cả PI + CI) |\n"
            "| **Uninv Qty** (Uninvoiced Quantity) | "
            "`= Eff Qty − Total Invoiced` |\n"
            "| **Arrival Qty** | Số lượng đã nhận thực tế (CAN flow) |\n"
            "| **True Remaining Qty** | "
            "`= MIN(Uninvoiced Qty, PO Pending Invoiced Qty)` — "
            "số lượng invoice an toàn, tránh over-invoice |"
        )

        st.markdown("##### Công thức tính tiền")
        st.code(
            "Line Amount     = Unit Cost × Quantity\n"
            "Converted Amt   = Line Amount × PO-to-Invoice Rate\n"
            "VAT Amount      = Converted Amt × VAT% / 100\n"
            "Line Total      = Converted Amt + VAT Amount\n"
            "─────────────────────────────────────────\n"
            "Invoice Total   = SUM(Line Total)  for all lines\n"
            "Amt Excl. VAT   = SUM(Converted Amt)",
            language=None
        )

        st.markdown("##### Tỷ giá (Exchange Rate)")
        st.markdown(
            "| Rate | Công thức | Mục đích |\n"
            "|------|-----------|----------|\n"
            "| **PO → Invoice Rate** | `1 PO_Currency = X Invoice_Currency` | "
            "Quy đổi giá trị dòng hàng sang currency hóa đơn |\n"
            "| **USD Exchange Rate** | `1 USD = X Invoice_Currency` | "
            "Luôn lưu cho báo cáo tài chính (nếu invoice không phải USD) |"
        )
        st.caption(
            "Nguồn: API → Cache 1h → Fallback DB (exchange_rates table). "
            "Nếu cùng currency thì rate = 1.0, không cần quy đổi."
        )

        st.markdown("##### Payment Terms")
        st.markdown(
            "| Loại | Ví dụ | Cách tính Due Date |\n"
            "|------|-------|--------------------|\n"
            "| **NET X DAYS** | NET 60 DAYS BY TT | Invoice Date + 60 ngày |\n"
            "| **AMS X DAYS** | AMS 60 DAYS BY TT | "
            "Ngày 1 tháng kế tiếp + 60 ngày |\n"
            "| **Advance** | TT IN ADVANCE, COD | Due Date = Invoice Date (0 ngày) |\n"
            "| **Split Payment** | 50% DP, 50% NET 30 | "
            "Lấy kỳ cuối: Invoice Date + 30 ngày ⚠️ Cần review |\n"
            "| **Special Date** | TT on the 25th | "
            "Ngày 25 tháng hiện tại hoặc kế tiếp |\n"
            "| **EOM** | EOM 90 | Cuối tháng + 90 ngày |\n"
            "| **Event-based** | TT AFTER DELIVERY | "
            "Mặc định +30 ngày ⚠️ Cần chỉnh tay |"
        )

        st.markdown("##### Trạng thái trên bảng PO Lines (PI flow)")
        st.markdown(
            "| Icon | Ý nghĩa |\n"
            "|------|----------|\n"
            "| ✅ OK | PO line bình thường, sẵn sàng invoice |\n"
            "| 🔴 OI | Over-Invoiced — đã invoice vượt PO qty |\n"
            "| ⚠️ CI | Đã có Commercial Invoice — cẩn thận double invoicing |\n"
            "| ⬜ / 🟡 / 🟢 | Arrival: chưa nhận / nhận một phần / nhận đủ |"
        )


# ============================================================================
# TAB 3: Q&A
# ============================================================================

def _tab_qa(tab):
    with tab:
        st.markdown("#### 💬 Câu hỏi thường gặp")

        with st.expander("Khi nào dùng CI, khi nào dùng PI?", expanded=True):
            st.markdown(
                "- **CI (Commercial Invoice)**: Hàng đã nhập kho (có CAN/Arrival Note). "
                "Đây là trường hợp phổ biến nhất — invoice dựa trên hàng thực nhận.\n"
                "- **PI (Proforma Invoice)**: Thanh toán trước khi nhận hàng. "
                "Thường dùng cho nhà cung cấp yêu cầu trả trước (TT IN ADVANCE, COD), "
                "hoặc khi cần đặt cọc trước khi sản xuất."
            )

        with st.expander("Tại sao 'Uninv Qty' khác với số tôi tính?"):
            st.markdown(
                "**Uninvoiced Qty** được tính ở cấp PO line, không phải CAN line.\n\n"
                "- Với **CI flow**: `Uninv Qty = Arrival Qty − (đã invoice cho CAN line đó)`\n"
                "- Với **PI flow**: `Uninv Qty = Eff Buying Qty − Total Invoiced Qty` "
                "(bao gồm cả PI + CI đã tạo trước đó)\n\n"
                "Nếu PO line đã có legacy invoice (tạo ngoài hệ thống), "
                "hệ thống sẽ hiện cảnh báo ⚠️ và dùng **True Remaining Qty** "
                "để tránh over-invoice."
            )

        with st.expander("Có thể tạo invoice cho nhiều PO cùng lúc không?"):
            st.markdown(
                "**Được**, miễn là tất cả PO lines phải:\n"
                "- Cùng **1 vendor** (cùng vendor_code)\n"
                "- Cùng **1 legal entity** (cùng consignee)\n"
                "- Cùng **loại vendor** (không mix Internal và External)\n\n"
                "Hệ thống sẽ báo lỗi nếu bạn chọn dòng từ nhiều vendor hoặc entity khác nhau."
            )

        with st.expander("PO line hiện 🔴 OI (Over-Invoiced), vẫn tạo invoice được không?"):
            st.markdown(
                "**Được**, nhưng hệ thống sẽ cảnh báo. Over-Invoice xảy ra khi:\n"
                "- Tổng invoice qty > PO effective qty\n"
                "- Có thể do legacy invoice hoặc đã tạo PI + CI cho cùng PO line\n\n"
                "Bạn nên kiểm tra lại số lượng thực tế trước khi tạo thêm invoice."
            )

        with st.expander("PO line có ⚠️ CI (đã có Commercial Invoice), tạo PI có sao không?"):
            st.markdown(
                "Hệ thống cho phép nhưng cảnh báo **risk double invoicing**. "
                "Tình huống này xảy ra khi:\n\n"
                "- Bước 1: Tạo PI trả trước cho vendor\n"
                "- Bước 2: Hàng về → tạo CI từ CAN\n"
                "→ Cùng PO line có cả PI và CI\n\n"
                "Đây có thể là đúng quy trình (trả trước rồi thanh toán phần còn lại), "
                "nhưng cần kiểm tra tổng invoice qty không vượt quá PO qty."
            )

        with st.expander("Tỷ giá bị N/A hoặc không lấy được?"):
            st.markdown(
                "Hệ thống lấy tỷ giá theo thứ tự:\n"
                "1. **API** (cache 1 giờ)\n"
                "2. **Database** (bảng exchange_rates, lấy rate mới nhất)\n"
                "3. **Inverse rate** (nếu chỉ có rate ngược, tự tính 1/rate)\n\n"
                "Nếu vẫn N/A:\n"
                "- Kiểm tra bảng `exchange_rates` có dữ liệu cho cặp currency không\n"
                "- Thêm record mới vào `exchange_rates` nếu cần\n"
                "- Chọn Invoice Currency = PO Currency để tránh cần tỷ giá"
            )

        with st.expander("Payment Terms hiện ⚠️ 'Needs review' là sao?"):
            st.markdown(
                "Một số loại payment terms không thể tính due date tự động chính xác:\n\n"
                "- **Split Payment** (50% DP, 50% NET 30): Hệ thống lấy kỳ cuối cùng, "
                "nhưng bạn cần kiểm tra lại\n"
                "- **Event-based** (TT AFTER DELIVERY): Phụ thuộc sự kiện, "
                "hệ thống mặc định +30 ngày\n"
                "- **Special Date** (25th, EOM): Tính tự động nhưng nên xác nhận\n\n"
                "Trong mọi trường hợp, bạn có thể chỉnh due date bằng tay ở bước Review."
            )

        with st.expander("File đính kèm hỗ trợ những gì?"):
            st.markdown(
                "- **Định dạng**: PDF, PNG, JPG, JPEG\n"
                "- **Giới hạn**: Tối đa 10 files, mỗi file tối đa 10MB\n"
                "- **Lưu trữ**: Upload lên S3, link vào invoice qua bảng `purchase_invoice_medias`\n"
                "- **Thêm sau**: Có thể đính kèm thêm file khi Edit invoice\n"
                "- **Xóa**: Soft-delete, không xóa file vật lý trên S3"
            )

        with st.expander("Void invoice rồi có khôi phục được không?"):
            st.markdown(
                "**Không.** Void là soft-delete (`delete_flag = 1`), "
                "dữ liệu vẫn còn trong DB nhưng hệ thống sẽ không hiển thị nữa. "
                "Uninvoiced Qty của các PO/CAN lines sẽ được hoàn lại.\n\n"
                "Nếu invoice đã **Fully Paid**, nút Void sẽ bị disable — "
                "không thể hủy hóa đơn đã thanh toán xong."
            )

        with st.expander("Invoice Number có quy tắc gì?"):
            st.markdown(
                "Format: `INV-{VendorID}-{BuyerID}-{Sequence}-{Suffix}`\n\n"
                "- **Suffix `-P`**: Commercial Invoice\n"
                "- **Suffix `-A`**: Advance Payment (Proforma Invoice)\n\n"
                "Số sequence tự tăng, đảm bảo không trùng."
            )
