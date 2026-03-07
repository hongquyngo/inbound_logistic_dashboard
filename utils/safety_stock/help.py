# utils/safety_stock/help.py
"""
User Guide Popover for Safety Stock Management
Renders a self-contained ❓ help button with 6-tab documentation.
Imported and called from the main page header.

Usage:
    from utils.safety_stock.help import render_help_popover
    render_help_popover()
"""

import streamlit as st


def render_help_popover():
    """Help & User Guide popover — accessible from the page header"""
    with st.popover("❓ User Guide"):
        st.markdown("## 🛡️ Safety Stock Management — User Guide")

        tab_overview, tab_concepts, tab_howto, tab_methods, tab_roles, tab_faq = st.tabs([
            "📌 Overview", "📚 Concepts", "🔧 How To", "📐 Methods", "👥 Roles", "❓ FAQ"
        ])

        # ── Overview ──────────────────────────────────────────────────────────
        with tab_overview:
            st.markdown("""
**Safety Stock Management** cho phép bạn thiết lập và quản lý mức tồn kho đệm (buffer stock)
cho từng sản phẩm, đảm bảo không bị stockout khi có biến động về cung hoặc cầu.

**Luồng sử dụng cơ bản:**
1. 🔍 **Xem** danh sách các safety stock rules hiện tại qua bảng dữ liệu
2. ➕ **Tạo mới** rule bằng nút *Add Safety Stock*
3. ✏️ **Chỉnh sửa** bằng cách chọn dòng → click *Edit*
4. 📋 **Review** định kỳ để cập nhật số lượng theo thực tế
5. 📊 **So sánh** tồn kho thực tế vs safety stock target

**KPI Dashboard (đầu trang):**
| Metric | Ý nghĩa |
|---|---|
| Active Rules | Tổng số rule đang hiệu lực |
| Customer Rules | Rule áp dụng riêng cho 1 khách hàng |
| Needs Review | Rule chưa được review trong 30 ngày |
| Expiring in 30d | Rule sắp hết hiệu lực |
| No Reorder Point | Rule chưa có ROP — cần bổ sung |
| Manual (FIXED) % | Tỷ lệ rule dùng nhập tay thay vì tính toán |
""")

        # ── Concepts ──────────────────────────────────────────────────────────
        with tab_concepts:
            st.markdown("""
**Safety Stock (SS)** — Lượng tồn kho đệm dự phòng, giữ trên mức zero để chống lại
sự biến động của cầu và thời gian giao hàng. SS cao hơn = ít stockout hơn nhưng chi phí lưu kho cao hơn.

**Reorder Point (ROP)** — Ngưỡng tồn kho kích hoạt lệnh mua hàng mới.

> `ROP = (Lead Time × Avg Daily Demand) + Safety Stock`

Khi tồn kho thực tế **chạm ROP**, cần đặt hàng ngay để hàng về đúng lúc tồn kho hết.

---

**General Rule vs Customer-Specific Rule:**
- **General Rule** (`customer = All`): Áp dụng cho tất cả khách hàng của sản phẩm đó
- **Customer-Specific Rule**: Override General Rule cho 1 khách hàng cụ thể
- Rule nào có **Priority Level thấp hơn** sẽ được ưu tiên (VD: 50 > 100)

---

**Effective Period** — Khoảng thời gian rule có hiệu lực.
- `effective_to = ongoing` nghĩa là rule không có ngày hết hạn
- Khi tạo rule mới cho cùng sản phẩm, nên set `effective_to` cho rule cũ để tránh conflict

---

**Calculation Method:**
- **FIXED** — Nhập tay, không tính toán. Dùng khi có kinh nghiệm thực tế hoặc ít data lịch sử
- **DOS** (Days of Supply) — Tính từ số ngày muốn buffer và demand trung bình hàng ngày
- **LTB** (Lead Time Based) — Tính thống kê dựa trên độ biến động cầu và lead time
""")

        # ── How To ────────────────────────────────────────────────────────────
        with tab_howto:
            st.markdown("### ➕ Tạo Safety Stock Rule mới")
            st.markdown("""
1. Click **➕ Add Safety Stock**
2. **Tab 1 — Basic Information:**
   - Chọn **Product** (gõ PT code để tìm nhanh)
   - Chọn **Entity** (công ty bán hàng)
   - Chọn **Customer** nếu là rule riêng, để trống cho General Rule
   - Đặt **Priority Level**: Customer rules nên ≤ 500, General rules mặc định 100
   - Đặt **Effective From** và **Effective To** (để trống = không hết hạn)
3. **Tab 2 — Stock Levels & Calculation:**
   - Click **Fetch Data** để lấy lịch sử demand từ hệ thống
   - Hệ thống tự gợi ý method phù hợp dựa trên CV% (độ biến động)
   - Điền parameters và click **Calculate**
   - Kiểm tra kết quả SS và ROP ở phần Summary bên dưới
4. Click **💾 Save**
""")
            st.divider()
            st.markdown("### ✏️ Chỉnh sửa Rule")
            st.markdown("""
1. Click vào dòng cần sửa trong bảng → hiện Actions panel
2. Click **✏️ Edit**
3. Chỉnh sửa thông tin → Recalculate nếu cần → **💾 Save**

> ⚠️ Nếu đổi Calculation Method, bắt buộc phải bấm **Calculate** lại trước khi Save.
> Hệ thống sẽ cảnh báo nếu kết quả và method được chọn không khớp.
""")
            st.divider()
            st.markdown("### 📋 Review Rule")
            st.markdown("""
Review dùng để **ghi nhận sự thay đổi số lượng SS** theo tình hình thực tế,
tạo audit trail đầy đủ mà không cần edit thủ công.

1. Chọn dòng → click **📋 Review**
2. Điều chỉnh **New Safety Stock Quantity** — hệ thống tự detect INCREASED/DECREASED
3. Chọn **Review Type**: PERIODIC / EXCEPTION / EMERGENCY / ANNUAL
4. Điền **Reason** (bắt buộc, tối thiểu 10 ký tự)
5. Submit → số lượng SS tự động cập nhật

> ⚠️ Nếu cần thay đổi **Calculation Method**, dùng **Edit** thay vì Review.
""")
            st.divider()
            st.markdown("### 📊 So sánh vs Tồn kho thực tế")
            st.markdown("""
1. Chọn dòng → click **📊 Compare vs Inventory**
2. Panel hiện bên dưới, hiển thị:
   - **Total On Hand** và delta so với SS target
   - **ROP Status**: Above/Below ROP
   - Breakdown tồn kho theo từng warehouse
""")

        # ── Methods ───────────────────────────────────────────────────────────
        with tab_methods:
            st.markdown("### 📐 Chi tiết các Calculation Methods")

            st.markdown("#### 1️⃣ FIXED — Nhập tay")
            st.info("Dùng khi: không có đủ data lịch sử, hoặc đã có kinh nghiệm thực tế về mức buffer cần thiết.")
            st.code("SS  = [Nhập tay]\nROP = [Nhập tay]", language="text")

            st.markdown("#### 2️⃣ DOS — Days of Supply")
            st.info("Dùng khi: demand tương đối ổn định (CV% < 20%). Phương pháp đơn giản, dễ hiểu.")
            st.code(
                "SS  = Safety Days × Avg Daily Demand\n"
                "ROP = (Lead Time × Avg Daily Demand) + SS",
                language="text"
            )
            st.markdown("""
| Parameter | Mô tả |
|---|---|
| Safety Days | Số ngày buffer muốn duy trì (VD: 14 ngày) |
| Avg Daily Demand | Demand trung bình mỗi ngày (tự động fetch) |
| Lead Time (days) | Thời gian từ đặt hàng đến nhận hàng |
""")

            st.markdown("#### 3️⃣ LTB — Lead Time Based (Statistical)")
            st.info("Dùng khi: demand biến động cao (CV% ≥ 20%) và có đủ ≥ 30 data points. Chính xác nhất.")
            st.code(
                "SS  = Z × √Lead Time × σ_demand\n"
                "ROP = (Lead Time × Avg Daily Demand) + SS",
                language="text"
            )
            st.markdown("""
| Parameter | Mô tả |
|---|---|
| Z-score | Hệ số từ service level % (VD: 95% → Z = 1.65) |
| Lead Time | Thời gian giao hàng (ngày) |
| σ_demand | Standard deviation của daily demand (tự động fetch) |

**Service Level Reference:**
| Service Level | Z-score | Ý nghĩa |
|---|---|---|
| 90% | 1.28 | Chấp nhận stockout 10% thời gian |
| 95% | 1.65 | Thông dụng nhất |
| 99% | 2.33 | Rất an toàn, tồn kho cao |
| 99.9% | 3.09 | Cực kỳ an toàn |
""")

            st.markdown("#### 🤖 Auto-suggest Method")
            st.markdown("""
Sau khi Fetch Data, hệ thống tự gợi ý method dựa trên CV% (Coefficient of Variation):

| CV% | Gợi ý | Lý do |
|---|---|---|
| < 10 data points | FIXED | Không đủ data |
| CV% < 20% | DOS | Demand ổn định |
| CV% ≥ 20% + ≥ 30 points | LTB | Demand biến động |
| CV% ≥ 20% + < 30 points | DOS | Chưa đủ data cho statistical |
""")

        # ── Roles ─────────────────────────────────────────────────────────────
        with tab_roles:
            st.markdown("### 👥 Phân quyền theo Role")
            st.markdown("""
| Role | Xem | Tạo | Sửa | Xóa | Review | Bulk Upload | Approve |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Admin / MD / GM | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Supply Chain | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ |
| Sales Manager | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Sales | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Viewer | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Customer | ✅* | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

> *Customer chỉ xem được data của chính họ.

**Export limits theo role:**
| Role | Giới hạn |
|---|---|
| Customer | 1,000 dòng |
| Sales / Viewer | 5,000 dòng |
| Sales Manager | 10,000 dòng |
| Supply Chain / Admin / MD / GM | Không giới hạn |
""")

        # ── FAQ ───────────────────────────────────────────────────────────────
        with tab_faq:
            st.markdown("### ❓ Câu hỏi thường gặp")

            with st.expander("Tại sao Reorder Point hiển thị '—'?"):
                st.markdown("""
Rule đó chưa được set Reorder Point. Với method **FIXED**, bạn cần nhập ROP thủ công.
Với **DOS** hoặc **LTB**, ROP được tính tự động sau khi bấm Calculate.
Filter **🔴 No Reorder Point** để tìm nhanh các rule cần bổ sung.
""")

            with st.expander("Tại sao tôi thấy cảnh báo 'Method mismatch' khi Save?"):
                st.markdown("""
Bạn đã đổi dropdown method (VD từ FIXED sang DOS) nhưng chưa bấm **Calculate** lại.
Kết quả hiển thị vẫn là kết quả của method cũ. Hãy bấm Calculate trước khi Save.
""")

            with st.expander("Customer-specific rule và General rule khác gì nhau?"):
                st.markdown("""
- **General Rule**: SS mặc định cho sản phẩm đó, áp dụng cho tất cả khách hàng
- **Customer-specific Rule**: Override General Rule, chỉ áp dụng cho 1 khách hàng
- Rule nào có **Priority Level thấp hơn** được dùng trước
- Thông thường: Customer rules có Priority ≤ 500, General rules = 100
""")

            with st.expander("Fetch Data lấy dữ liệu từ đâu và trong bao lâu?"):
                st.markdown("""
Dữ liệu được lấy từ **lịch sử giao hàng thực tế** (`stock_out_delivery`),
group theo ETD date (ngày giao dự kiến, có adjust nếu có).
Mặc định lấy **180 ngày** gần nhất, có thể điều chỉnh 30–365 ngày.
Deliveries có status **PENDING** bị loại trừ mặc định.
""")

            with st.expander("CV% là gì và tại sao quan trọng?"):
                st.markdown("""
**CV% (Coefficient of Variation)** = `Std Dev / Avg × 100%`

Đo mức độ biến động của demand:
- 🟢 CV% < 20%: Demand ổn định → dùng DOS
- 🟡 CV% 20–50%: Biến động vừa → dùng LTB
- 🔴 CV% > 50%: Biến động cao → cân nhắc tăng SS buffer

CV% thấp nghĩa là demand đều đặn, dễ dự đoán.
""")

            with st.expander("Bulk Upload cần file format như thế nào?"):
                st.markdown("""
Download template từ dialog **📤 Bulk Upload → Download Template**.
Các cột bắt buộc: `product_id`, `entity_id`, `safety_stock_qty`, `effective_from`.
Các cột tùy chọn: `customer_id`, `reorder_point`, `calculation_method`, `priority_level`, `effective_to`, `business_notes`.
""")

            with st.expander("Expiring in 30 Days nghĩa là gì?"):
                st.markdown("""
Rule đó có `effective_to` trong vòng 30 ngày tới. Sau ngày đó rule sẽ không còn hiệu lực.
Bạn cần tạo rule mới hoặc cập nhật `effective_to` để đảm bảo safety stock không bị gián đoạn.
Dùng filter **📅 Expiring in 30 Days** để xem danh sách cần xử lý.
""")
