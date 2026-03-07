# utils/inbound_cost/help.py
"""
User Guide Popover for Inbound Logistic Cost Management
Renders a self-contained ❓ help button with 6-tab documentation.
Imported and called from the main page header.

Usage:
    from utils.inbound_cost.help import render_help_popover
    render_help_popover()
"""

import streamlit as st


def render_help_popover():
    """Help & User Guide popover — accessible from the page header"""
    with st.popover("❓ User Guide"):
        st.markdown("## 🚛 Inbound Logistic Cost — User Guide")

        tab_overview, tab_concepts, tab_howto, tab_formula, tab_roles, tab_faq = st.tabs([
            "📌 Overview", "📚 Concepts", "🔧 How To", "📐 Formula", "👥 Roles", "❓ FAQ"
        ])

        # ── Overview ──────────────────────────────────────────────────────────
        with tab_overview:
            st.markdown("""
**Inbound Logistic Cost** cho phép ghi nhận và quản lý toàn bộ chi phí vận chuyển
đầu vào cho từng Cargo Arrival Note (CAN), bao gồm cước quốc tế và phí nội địa.
Mỗi khi thêm/sửa/xóa cost entry, hệ thống sẽ **tự động tính lại Landed Cost**
cho tất cả dòng hàng trong CAN đó.

**Luồng sử dụng cơ bản:**
1. ➕ **Tạo mới** cost entry qua nút *Add Cost Entry*
2. 👁️ **Xem chi tiết** bằng cách chọn dòng → click *View*
3. ✏️ **Chỉnh sửa** amount hoặc charge type → *Edit*
4. 📎 **Đính kèm chứng từ** (invoice, bill of lading) qua *Attachments*
5. 📈 **Phân tích** xu hướng chi phí qua tab *Analytics*

**KPI Dashboard (phần Summary):**
| Metric | Ý nghĩa |
|---|---|
| Total Entries | Tổng số cost entries trong bộ lọc hiện tại |
| Unique CANs | Số CAN có ít nhất 1 cost entry |
| Total (USD) | Tổng chi phí quy đổi USD |
| International | Tổng cước quốc tế (USD) |
| Local | Tổng phí nội địa (USD) |
""")

        # ── Concepts ──────────────────────────────────────────────────────────
        with tab_concepts:
            st.markdown("""
**Cargo Arrival Note (CAN)** — Phiếu nhập kho ghi nhận lô hàng về kho.
Mỗi CAN có thể có nhiều cost entries thuộc 2 loại: INTERNATIONAL và LOCAL.

---

**Category — INTERNATIONAL vs LOCAL:**
| Category | Ý nghĩa | Ví dụ |
|---|---|---|
| 🟦 INTERNATIONAL | Chi phí phát sinh từ nơi xuất đến cảng nhập | Cước tàu/máy bay, phí EXW-FOB, phụ phí nhiên liệu |
| 🟩 LOCAL | Chi phí từ cảng nhập đến kho | Phí thông quan, vận chuyển nội địa, phí lưu kho |

---

**Exchange Rate Convention:**
> `1 USD = X đơn vị tiền tệ` (VD: 1 USD = 25,867.5 VND)

Rate được lưu ở cấp **CAN** — tất cả cost entries trong cùng CAN dùng chung rate.
Khi tạo entry mới, hệ thống tự fetch rate từ API; bạn có thể chỉnh thủ công nếu cần.
⚠️ Thay đổi currency/rate ảnh hưởng **toàn bộ** cost entries của CAN đó.

---

**Landed Cost** — Giá thành thực tế của từng dòng sản phẩm sau khi cộng đủ chi phí:

> `Landed Cost = Taxed Cost + Local Charge per Unit`

Được tính lại **tự động** sau mỗi thao tác create/edit/delete cost entry.

---

**Cost per Unit ($/Unit)** — Chi phí logistics quy về 1 đơn vị sản phẩm:
> `$/Unit = Total Cost USD ÷ Total Arrival Qty`
""")

        # ── How To ────────────────────────────────────────────────────────────
        with tab_howto:
            st.markdown("### ➕ Tạo Cost Entry mới")
            st.markdown("""
1. Click **➕ Add Cost Entry** (cần quyền `admin`, `inbound_manager`, hoặc `supply_chain`)
2. Chọn **Category**: INTERNATIONAL hoặc LOCAL
3. Chọn **Charge Type** (danh sách tự lọc theo Category)
4. Tìm và chọn **CAN** — gõ CAN number hoặc tên sender để tìm nhanh
5. Kiểm tra / điều chỉnh **Currency và Exchange Rate**:
   - Rate được tự động fetch từ API nếu chưa set hoặc currency thay đổi
   - Format: **1 USD = X đơn vị tiền tệ**
6. Nhập **Amount** (theo đơn vị tiền tệ đã chọn) — hệ thống hiển thị quy đổi USD
7. Chọn **Logistics Vendor / Courier** (tùy chọn)
8. Đính kèm **chứng từ** nếu có (PDF, PNG, JPG — tối đa 10 MB/file)
9. Click **💾 Save** → hệ thống tự recalculate landed cost cho CAN

> ⚠️ **Anomaly Warning**: Nếu tổng chi phí logistics > 30% giá trị hàng hóa,
> hệ thống sẽ cảnh báo — vui lòng kiểm tra lại amount trước khi lưu.
""")
            st.divider()
            st.markdown("### ✏️ Chỉnh sửa Cost Entry")
            st.markdown("""
1. Click vào dòng cần sửa trong bảng → hiện Actions panel
2. Click **✏️ Edit**
3. **Tab Cost Info**: chỉnh Charge Type, Amount, Vendor
   - Currency **không thể** thay đổi ở đây (được set ở cấp CAN)
   - Hệ thống hiển thị danh sách thay đổi trước khi lưu
4. **Tab Documents**: xem/tải/xóa file đính kèm hoặc upload file mới
5. Click **💾 Save Changes** → landed cost được recalculate tự động
""")
            st.divider()
            st.markdown("### 📎 Quản lý Attachments")
            st.markdown("""
Có 2 cách đính kèm chứng từ:
- **Khi tạo mới**: Mở rộng *Attach Documents (optional)* trong Create dialog
- **Sau khi tạo**: Chọn dòng → click **📎 Attachments**

**Định dạng hỗ trợ**: PDF, PNG, JPG, JPEG  
**Giới hạn**: 10 MB/file, tối đa 10 files/lần upload  
**Tên file**: Chỉ chứa chữ cái, số, dấu `-`, `_`, `.` (không có ký tự đặc biệt)
""")
            st.divider()
            st.markdown("### 🗑️ Xóa Cost Entry")
            st.markdown("""
1. Chọn dòng → click **🗑️ Delete**
2. Đọc thông tin xác nhận
3. Tick checkbox *"I confirm I want to delete this cost entry"*
4. Click **🗑️ Delete** → entry bị soft-delete và landed cost được recalculate

> ⚠️ Thao tác này không thể hoàn tác.
""")
            st.divider()
            st.markdown("### 📥 Export dữ liệu")
            st.markdown("""
Cuối danh sách có nút export cho dữ liệu **đang hiển thị sau bộ lọc**:
- **📊 Excel** — file `.xlsx` (khuyến nghị để phân tích thêm)
- **📄 CSV** — file `.csv` (tương thích với mọi tool)
""")

        # ── Formula ───────────────────────────────────────────────────────────
        with tab_formula:
            st.markdown("### 📐 Công thức tính Landed Cost")
            st.info("Landed Cost được tính lại tự động sau mỗi thao tác create/edit/delete cost entry.")

            st.markdown("#### Bước 1 — Unit Cost quy về Landed Cost Currency")
            st.code(
                "UC_landed = PPO.unit_cost × arrival_detail.exchange_rate\n"
                "# PPO currency → Landed cost currency (VD: USD → VND)",
                language="text"
            )

            st.markdown("#### Bước 2 — Phân bổ phí INTERNATIONAL (Normal Path)")
            st.code(
                "Total Cost      = Σ (UC_landed × arrival_qty)\n"
                "Intl / Unit     = UC_landed × (Total Intl Charge / Total Cost)\n"
                "Cost Before Tax = UC_landed + Intl / Unit\n"
                "Taxed Cost      = Cost Before Tax × (1 + import_tax / 100)",
                language="text"
            )

            st.markdown("#### Bước 3 — Phân bổ phí LOCAL")
            st.code(
                "Total Taxed Cost = Σ (Taxed Cost × arrival_qty)\n"
                "Local / Unit     = Taxed Cost × (Total Local Charge / Total Taxed Cost)\n"
                "Landed Cost      = Taxed Cost + Local / Unit",
                language="text"
            )

            st.markdown("#### Fallback — Khi tất cả unit price = 0")
            st.warning("Dùng phân bổ theo **số lượng** thay vì theo giá trị khi Total Cost = 0.")
            st.code(
                "Intl / Unit  = (arrival_qty × Total Intl Charge) / Total Qty\n"
                "Local / Unit = (arrival_qty × Total Local Charge) / Total Qty",
                language="text"
            )

            st.markdown("#### Quy đổi USD cho Cost Entries")
            st.code(
                "# DB lưu: 1 USD = X đơn vị tiền tệ (VD: 25,867.5 cho VND)\n"
                "Amount USD = Amount ÷ Exchange Rate\n"
                "# VD: 2,586,750 VND ÷ 25,867.5 = 100 USD",
                language="text"
            )

            st.markdown("#### Nguồn charge totals")
            st.markdown("""
Charge totals được tổng hợp từ **`inbound_logistic_charge_full_view`**,
phân loại theo `category`:
| Category | Cột tổng |
|---|---|
| INTERNATIONAL | `total_intl_usd` |
| LOCAL | `total_local_usd` |

Sau đó quy đổi sang Landed Cost Currency:
```
total_intl_landed  = total_intl_usd  × usd_landed_cost_currency_exchange_rate
total_local_landed = total_local_usd × usd_landed_cost_currency_exchange_rate
```
""")

        # ── Roles ─────────────────────────────────────────────────────────────
        with tab_roles:
            st.markdown("### 👥 Phân quyền theo Role")
            st.markdown("""
| Role | Xem | Tạo | Sửa | Xóa | Attachments | Export |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Inbound Manager | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Supply Chain | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Các role khác | ✅ | ❌ | ❌ | ❌ | ✅* | ✅ |

> *Xem attachments không yêu cầu write permission.

**Roles có write access**: `admin`, `inbound_manager`, `supply_chain`

Nút **➕ Add Cost Entry** sẽ bị disabled với tooltip thông báo nếu không có quyền.
Các nút **✏️ Edit** và **🗑️ Delete** chỉ hiện với user có write access.
""")

        # ── FAQ ───────────────────────────────────────────────────────────────
        with tab_faq:
            st.markdown("### ❓ Câu hỏi thường gặp")

            with st.expander("Tại sao Landed Cost không cập nhật ngay sau khi Save?"):
                st.markdown("""
Landed cost được recalculate **ngay lập tức** sau khi Save thành công — bạn sẽ thấy toast notification
`"🔄 Landed cost recalculated — X line(s) updated"`.
Nếu không thấy notification này, có thể xảy ra lỗi trong quá trình tính toán — kiểm tra logs.
Refresh trang để xem giá trị mới nhất trong bảng.
""")

            with st.expander("Exchange rate tôi nhập bị reset khi chọn CAN khác?"):
                st.markdown("""
Đúng — khi chọn CAN khác, hệ thống load lại rate từ record của CAN đó.
Nếu bạn muốn dùng rate khác với rate hiện tại của CAN, hãy điều chỉnh thủ công
sau khi chọn CAN xong.
""")

            with st.expander("Thay đổi Currency có ảnh hưởng đến các cost entries cũ không?"):
                st.markdown("""
**Có** — Currency và Exchange Rate được lưu ở cấp **CAN** (`arrivals` table),
không phải ở từng cost entry. Khi bạn đổi currency/rate cho CAN,
**toàn bộ** cost entries của CAN đó sẽ dùng rate mới khi tính USD.

Vì vậy hệ thống hiển thị cảnh báo rõ ràng khi phát hiện currency thay đổi.
""")

            with st.expander("Anomaly Warning xuất hiện khi nào?"):
                st.markdown("""
Cảnh báo xuất hiện khi **tổng chi phí logistics (preview) > 30% giá trị hàng hóa**:
- ⚠️ 30–50%: "Please double-check the amount"
- 🚨 > 50%: "This is unusually high — please verify"

Goods value được tính từ: `Σ (unit_cost × arrival_qty × exchange_rate)` cho CAN đó.
Đây chỉ là cảnh báo, không chặn việc lưu — bạn vẫn có thể Save nếu số liệu đúng.
""")

            with st.expander("Tại sao USD hiển thị trong bảng khác với amount tôi nhập?"):
                st.markdown("""
Amount bạn nhập là **đơn vị tiền tệ của CAN** (VD: VND).
Cột USD trong bảng là giá trị quy đổi theo rate đã lưu trên CAN:

`Amount USD = Amount ÷ Exchange Rate`

VD: `2,586,750 VND ÷ 25,867.5 = 100 USD`

Nếu thấy sai, kiểm tra lại Exchange Rate đang set trên CAN.
""")

            with st.expander("Cost entry đã xóa có khôi phục được không?"):
                st.markdown("""
Không thể khôi phục qua giao diện. Xóa là **soft-delete** (set `delete_flag = 1`) —
record vẫn còn trong database nhưng không hiển thị. Liên hệ admin nếu cần khôi phục.
""")

            with st.expander("File đính kèm được lưu ở đâu?"):
                st.markdown("""
File được upload lên **AWS S3** tại folder `inbound-cost-file/`.
Link download là pre-signed URL có hiệu lực **1 giờ** kể từ lúc mở dialog.
Sau 1 giờ cần mở lại dialog để lấy link mới.
""")

            with st.expander("Allocation method 'cost_based' và 'quantity_based' khác gì?"):
                st.markdown("""
Hệ thống tự chọn method khi recalculate landed cost:

| Method | Khi nào áp dụng | Cách phân bổ |
|---|---|---|
| **cost_based** | Bình thường (unit price > 0) | Theo tỷ lệ giá trị hàng |
| **quantity_based** | Fallback (tất cả unit price = 0) | Theo tỷ lệ số lượng |

Method được hiển thị trong toast notification sau mỗi lần recalculate.
Nếu thấy `quantity_based` thường xuyên, kiểm tra lại unit cost trong Purchase Orders.
""")
