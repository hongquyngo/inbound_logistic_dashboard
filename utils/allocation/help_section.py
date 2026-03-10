"""
Allocation Planning - Help Section
====================================
Comprehensive help content for the Allocation Planning page.
Includes: Quick Start, Definitions, Formulas, Q&A, Status Reference.

Usage:
    from utils.allocation.help_section import show_help_button
    show_help_button()  # Place in header area
"""
import streamlit as st


# ==================== MAIN ENTRY POINT ====================

def show_help_button():
    """
    Render the Help button with popover containing all help sections.
    Call this in the page header area.
    """
    with st.popover("❓ Help & Guide", use_container_width=True):
        _render_help_content()


def _render_help_content():
    """Render all help content inside popover"""
    
    st.markdown("## 📦 Allocation Planning Guide")
    st.caption("Everything you need to know about the Allocation Planning system")
    
    # ==================== TAB LAYOUT ====================
    tabs = st.tabs([
        "🚀 Quick Start",
        "📖 Definitions",
        "🔢 Formulas",
        "💬 Q&A",
        "🎨 Icons & Status",
        "🔐 Permissions"
    ])
    
    with tabs[0]:
        _render_quick_start()
    
    with tabs[1]:
        _render_definitions()
    
    with tabs[2]:
        _render_formulas()
    
    with tabs[3]:
        _render_qa()
    
    with tabs[4]:
        _render_status_reference()
    
    with tabs[5]:
        _render_permissions()


# ==================== QUICK START ====================

def _render_quick_start():
    """How to use this page"""
    
    st.markdown("### 🚀 Quick Start Guide")
    
    st.markdown("""
    **Allocation Planning** giúp bạn phân bổ nguồn cung (supply) cho các đơn hàng (OC) 
    đang chờ giao hàng. Mục tiêu là đảm bảo mỗi OC có đủ hàng để giao đúng hẹn.
    """)
    
    st.markdown("---")
    
    st.markdown("""
    **Bước 1 — Xem tổng quan Dashboard**
    
    Hàng metrics phía trên cho biết toàn cảnh: bao nhiêu sản phẩm cần allocation, 
    tổng demand vs supply, các items critical, urgent, và over-allocated.
    """)
    
    st.markdown("""
    **Bước 2 — Lọc sản phẩm cần xử lý**
    
    Dùng các bộ lọc (Product, Brand, Customer, Legal Entity, Supply Status, ETD Urgency, 
    Allocation Status) để thu hẹp danh sách. Ví dụ lọc "🔴 Low" supply + "🔴 Urgent" 
    ETD để tìm các sản phẩm cần ưu tiên.
    """)
    
    st.markdown("""
    **Bước 3 — Mở chi tiết sản phẩm**
    
    Click vào tên sản phẩm để mở 2 tabs: **Demand** (danh sách OC) và **Supply** 
    (nguồn cung chi tiết). Kiểm tra supply có đủ không, có hàng expired không.
    """)
    
    st.markdown("""
    **Bước 4 — Tạo Allocation**
    
    Ở tab Demand, click "**Allocate**" trên OC cần phân bổ. Chọn nguồn cung 
    (HARD — chỉ định batch cụ thể, hoặc SOFT — không chỉ định). Nhập số lượng 
    và ETD rồi Save.
    """)
    
    st.markdown("""
    **Bước 5 — Quản lý Allocation**
    
    Click vào cột "Undelivered Alloc" để xem lịch sử allocation. Từ đó có thể 
    Update ETD, Cancel allocation, hoặc Reverse cancellation.
    """)
    
    st.info(
        "💡 **Tip**: Ưu tiên xử lý các OC có icon 🔴 (ETD urgent), "
        "❌ (over-committed), hoặc ⚠️ (pending over-allocated) trước."
    )


# ==================== DEFINITIONS ====================

def _render_definitions():
    """Key terms and definitions"""
    
    st.markdown("### 📖 Thuật ngữ & Định nghĩa")
    
    st.markdown("---")
    st.markdown("#### 📋 Đơn hàng (Demand)")
    
    st.markdown("""
    | Thuật ngữ | Định nghĩa |
    |-----------|-----------|
    | **OC (Order Confirmation)** | Xác nhận đơn hàng từ khách hàng — là nguồn demand chính |
    | **OC Effective Qty** | Số lượng OC hiệu lực = OC gốc − số lượng đã cancel ở OC level |
    | **Pending Delivery** | Số lượng còn phải giao = OC Effective − đã giao (delivered) |
    | **ETD** | Expected Time of Delivery — ngày dự kiến giao hàng cho khách |
    """)
    
    st.markdown("---")
    st.markdown("#### 📦 Nguồn cung (Supply)")
    
    st.markdown("""
    | Thuật ngữ | Định nghĩa |
    |-----------|-----------|
    | **Total Supply** | Tổng nguồn cung từ tất cả nguồn (bao gồm cả hàng expired) |
    | **Usable Supply** | Nguồn cung sử dụng được = Total Supply − Expired Inventory |
    | **Expired Inventory** | Hàng tồn kho đã quá hạn (expiry_date ≤ hôm nay). Không dùng cho SOFT allocation |
    | **Inventory** | Hàng tồn kho thực tế đang có trong warehouse |
    | **Pending CAN** | Confirmed Arrival Notice — hàng đã xác nhận sẽ về, chờ nhập kho |
    | **Pending PO** | Purchase Order — hàng đã đặt mua, chưa về |
    | **WHT** | Warehouse Transfer — hàng đang chuyển giữa các kho |
    | **Committed** | Đã phân bổ nhưng chưa giao. Tính = Σ MIN(Pending Delivery, Undelivered Allocated) |
    | **Available** | Usable Supply − Committed. Đây là số lượng có thể allocate thêm |
    """)
    
    st.markdown("---")
    st.markdown("#### 🔗 Phân bổ (Allocation)")
    
    st.markdown("""
    | Thuật ngữ | Định nghĩa |
    |-----------|-----------|
    | **SOFT Allocation** | Phân bổ mềm — không chỉ định nguồn cung cụ thể. Giới hạn bởi Usable Available |
    | **HARD Allocation** | Phân bổ cứng — chỉ định batch/PO/CAN cụ thể. Có thể dùng cho hàng expired (clearance) |
    | **Allocated Qty** | Tổng số lượng đã phân bổ (gốc) |
    | **Effective Allocated** | Allocated − Cancelled. Phân bổ hiệu lực thực tế |
    | **Undelivered Allocated** | Effective Allocated − Delivered. Số đã allocate nhưng chưa giao |
    | **Allocation Coverage** | % = Undelivered Allocated ÷ Pending Delivery × 100 |
    """)
    
    st.markdown("---")
    st.markdown("#### 📏 Đơn vị tính (UOM)")
    
    st.markdown("""
    | Thuật ngữ | Định nghĩa |
    |-----------|-----------|
    | **Standard UOM** | Đơn vị chuẩn để lưu trữ và tính toán (ví dụ: KG, BT, PCS) |
    | **Selling UOM** | Đơn vị bán hàng cho khách (có thể khác standard, ví dụ: Carton, Box) |
    | **UOM Conversion** | Tỷ lệ chuyển đổi: Standard = Selling × Conversion Ratio |
    """)


# ==================== FORMULAS ====================

def _render_formulas():
    """Formulas and calculations used"""
    
    st.markdown("### 🔢 Công thức tính toán")
    
    st.markdown("---")
    st.markdown("#### 1. Pending Delivery (Số lượng cần giao)")
    st.code("Pending Delivery = OC Effective Qty − Total Delivered", language="text")
    st.caption("OC Effective Qty = Original OC Qty − OC Cancelled Qty")
    
    st.markdown("---")
    st.markdown("#### 2. Usable Supply (Nguồn cung sử dụng được)")
    st.code(
        "Usable Supply = Inventory (non-expired) + Pending CAN + Pending PO + WHT\n"
        "Expired Inventory = Inventory where expiry_date ≤ TODAY\n"
        "Total Supply = Usable Supply + Expired Inventory",
        language="text"
    )
    st.caption(
        "⚠️ Expired inventory bị loại khỏi Usable Supply. "
        "SOFT allocation chỉ dùng Usable Supply làm giới hạn."
    )
    
    st.markdown("---")
    st.markdown("#### 3. Committed Quantity (Đã cam kết)")
    st.code("Committed = Σ MIN(Pending Delivery, Undelivered Allocated)", language="text")
    st.caption(
        "Dùng MIN để tránh over-blocking supply khi dữ liệu delivery chưa đồng bộ. "
        "Ví dụ: OC có 100 pending, allocated 150 → committed chỉ tính 100 (không phải 150)."
    )
    
    st.markdown("---")
    st.markdown("#### 4. Available for Allocation")
    st.code("Available = Usable Supply − Committed", language="text")
    st.caption("Đây là số lượng tối đa có thể tạo SOFT allocation mới.")
    
    st.markdown("---")
    st.markdown("#### 5. Over-Allocation Check")
    st.code(
        "Over-Committed:        Effective Allocated > OC Effective Qty\n"
        "Pending Over-Allocated: Undelivered Allocated > Pending Delivery",
        language="text"
    )
    st.caption(
        "Hệ thống chặn allocation mới khi phát hiện over-allocation. "
        "Giới hạn tối đa = 100% OC Effective Qty."
    )
    
    st.markdown("---")
    st.markdown("#### 6. Allocation Coverage")
    st.code("Coverage % = (Undelivered Allocated ÷ Pending Delivery) × 100", language="text")
    st.markdown("""
    | Coverage | Ý nghĩa |
    |----------|---------|
    | 0% | Chưa allocate — cần hành động gấp |
    | 1–99% | Đã allocate một phần — cần bổ sung |
    | 100% | Đã allocate đủ |
    | >100% | Over-allocated — cần review và cancel bớt |
    """)
    
    st.markdown("---")
    st.markdown("#### 7. Supply Status (trên dashboard)")
    st.code(
        "Sufficient (🟢): Usable Supply ≥ Total Demand\n"
        "Partial   (🟡): Usable Supply ≥ 50% Demand\n"
        "Low       (🔴): Usable Supply < 50% Demand (nhưng > 0)\n"
        "No Supply (⚫): Usable Supply = 0",
        language="text"
    )


# ==================== Q&A ====================

def _render_qa():
    """Common scenarios and answers"""
    
    st.markdown("### 💬 Câu hỏi thường gặp")
    
    # --- Q1 ---
    st.markdown("---")
    st.markdown("#### Q1: SOFT vs HARD allocation — khi nào dùng cái nào?")
    st.markdown("""
    **SOFT** — Dùng khi bạn muốn reserve số lượng nhưng chưa cần chỉ định batch/PO cụ thể. 
    Phù hợp cho planning trước, khi hàng chưa về kho hoặc chưa xác định lot nào sẽ dùng.
    SOFT bị giới hạn bởi **Usable Available Supply** (không bao gồm hàng expired).
    
    **HARD** — Dùng khi bạn muốn chỉ định chính xác nguồn cung (batch inventory, PO, CAN). 
    Bắt buộc cho:
    - Đơn clearance/hàng sắp hết hạn (expired stock)
    - Khi cần đảm bảo batch cụ thể cho khách hàng
    - Khi nhiều OC cùng tranh một nguồn cung
    """)
    
    # --- Q2 ---
    st.markdown("---")
    st.markdown("#### Q2: Hàng expired xuất hiện trong Total Supply — có vấn đề gì không?")
    st.markdown("""
    Hệ thống đã tách biệt:
    - **Total Supply**: bao gồm tất cả (kể cả expired) — hiển thị để tham khảo
    - **Usable Supply**: chỉ hàng dùng được — là cơ sở cho SOFT allocation
    
    Nếu sản phẩm có expired inventory, bạn sẽ thấy:
    - Banner cảnh báo ⚠️ trên Supply Overview
    - Metric "✅ Usable Supply" hiển thị riêng
    - Batch expired đánh dấu ⛔ trong danh sách inventory
    
    **Để xử lý hàng expired**: Nếu khách chấp nhận (đơn clearance/giảm giá), 
    dùng HARD allocation chọn đúng batch expired. Nếu không, bỏ qua và chỉ dùng SOFT.
    """)
    
    # --- Q3 ---
    st.markdown("---")
    st.markdown("#### Q3: OC bị cảnh báo \"Over-Committed\" — phải làm gì?")
    st.markdown("""
    **Over-Committed** (❌) nghĩa là tổng Effective Allocated > OC Effective Qty.
    
    Nguyên nhân thường gặp:
    - OC bị cancel một phần (giảm quantity) sau khi đã allocate
    - Allocate nhầm thừa
    
    **Cách xử lý:**
    1. Click vào cột "Undelivered Alloc" để mở lịch sử
    2. Xem các allocation hiện tại
    3. Cancel bớt allocation thừa (chọn allocation → ❌ Cancel)
    4. Kiểm tra lại coverage sau khi cancel
    """)
    
    # --- Q4 ---
    st.markdown("---")
    st.markdown("#### Q4: OC bị \"Pending Over-Allocated\" — khác gì Over-Committed?")
    st.markdown("""
    **Pending Over-Allocated** (⚠️) là trường hợp nhẹ hơn:
    - Undelivered Allocated > Pending Delivery
    - Nhưng Effective Allocated ≤ OC Effective Qty
    
    Thường xảy ra khi đã giao một phần rồi allocate thêm (vượt quá pending).
    
    **Ví dụ**: OC = 1000, đã giao 800, pending = 200, nhưng undelivered allocated = 250.
    → Thừa 50 so với pending, nhưng tổng allocated vẫn trong giới hạn OC.
    
    **Cách xử lý**: Cancel bớt 50 từ allocation hiện tại.
    """)
    
    # --- Q5 ---
    st.markdown("---")
    st.markdown("#### Q5: Available supply = 0 nhưng vẫn có inventory — tại sao?")
    st.markdown("""
    Có 2 nguyên nhân phổ biến:
    
    **1. Tất cả đã committed cho OC khác**
    - Supply đã được allocate hết cho các OC khác
    - Kiểm tra: Available = Usable Supply − Committed
    
    **2. Inventory toàn bộ là expired**
    - Usable Supply loại expired → Available = 0
    - Kiểm tra: xem có banner "⚠️ expired inventory detected" không
    - Giải pháp: dùng HARD allocation nếu là đơn clearance
    """)
    
    # --- Q6 ---
    st.markdown("---")
    st.markdown("#### Q6: Tôi muốn thay đổi ETD đã allocate — có được không?")
    st.markdown("""
    Có. Từ lịch sử allocation:
    1. Click "📅 Update ETD" trên allocation cần sửa
    2. Chọn ngày mới → confirm
    3. Hệ thống ghi nhận update count và gửi email thông báo
    
    **Lưu ý**: Chỉ update được ETD cho phần pending (chưa giao). 
    Phần đã giao không bị ảnh hưởng.
    """)
    
    # --- Q7 ---
    st.markdown("---")
    st.markdown("#### Q7: Cancel allocation có hoàn lại supply không?")
    st.markdown("""
    **Có**. Khi cancel allocation:
    - Committed quantity giảm tương ứng
    - Available supply tăng lên → có thể allocate cho OC khác
    - Email thông báo được gửi tự động
    
    Nếu cancel nhầm, dùng "↩️ Reverse" để khôi phục (cần quyền reverse).
    """)
    
    # --- Q8 ---
    st.markdown("---")
    st.markdown("#### Q8: Tại sao nút \"Allocate\" bị disabled?")
    st.markdown("""
    Nút Allocate bị vô hiệu hóa khi:
    
    | Lý do | Giải pháp |
    |-------|----------|
    | Role không có quyền | Liên hệ Supply Chain team |
    | OC đã Over-Committed | Cancel bớt allocation thừa |
    | OC đã Pending Over-Allocated | Cancel bớt undelivered allocation |
    | Available supply = 0 | Chờ hàng về hoặc cancel allocation OC khác |
    | OC đã Fully Allocated | Không cần thêm allocation |
    """)


# ==================== STATUS REFERENCE ====================

def _render_status_reference():
    """Icons and status indicators reference"""
    
    st.markdown("### 🎨 Bảng tra cứu Icons & Status")
    
    st.markdown("---")
    st.markdown("#### Supply Status (cột STATUS)")
    st.markdown("""
    | Icon | Trạng thái | Ý nghĩa |
    |------|-----------|---------|
    | 🟢 | Sufficient | Usable supply ≥ demand |
    | 🟡 | Partial | Usable supply ≥ 50% demand |
    | 🔴 | Low | Usable supply < 50% demand |
    | ⚫ | No Supply | Không có usable supply |
    """)
    
    st.markdown("---")
    st.markdown("#### ETD Urgency (cột ETD)")
    st.markdown("""
    | Icon | Ý nghĩa |
    |------|---------|
    | 🔴 | Urgent — ETD trong vòng 7 ngày |
    | 🟡 | Soon — ETD trong 8–14 ngày |
    | _(trống)_ | Normal — ETD > 14 ngày |
    | ⚫ | Overdue — ETD đã qua |
    """)
    
    st.markdown("---")
    st.markdown("#### Allocation Status (cột Undelivered Alloc)")
    st.markdown("""
    | Icon | Trạng thái | Ý nghĩa |
    |------|-----------|---------|
    | ⚪ | Not Allocated | Chưa allocate — cần hành động |
    | 🟡 | Partially Allocated | Đã allocate một phần |
    | 🟢 | Fully Allocated | Đã allocate đủ |
    | 🔴 | Over-Allocated | Undelivered > Pending — cần review |
    """)
    
    st.markdown("---")
    st.markdown("#### Over-Allocation Warnings")
    st.markdown("""
    | Icon | Loại | Mức độ | Hành động |
    |------|------|--------|----------|
    | ❌ | Over-Committed | Nghiêm trọng | Cancel bớt allocation ngay |
    | ⚠️ | Pending Over-Allocated | Cảnh báo | Review và cancel bớt |
    """)
    
    st.markdown("---")
    st.markdown("#### Allocation Mode")
    st.markdown("""
    | Icon | Mode | Mô tả |
    |------|------|-------|
    | 📄 | SOFT | Không chỉ định nguồn cụ thể — linh hoạt |
    | 🔒 | HARD | Chỉ định batch/PO/CAN cụ thể — chính xác |
    """)
    
    st.markdown("---")
    st.markdown("#### Inventory Expiry Status")
    st.markdown("""
    | Icon | Trạng thái | Ý nghĩa |
    |------|-----------|---------|
    | ⛔ | Expired | Đã quá hạn — chỉ dùng cho clearance (HARD) |
    | ⚠️ | Expiring Soon | Hết hạn trong 30 ngày — ưu tiên xuất trước |
    | _(trống)_ | OK / No Expiry | Bình thường |
    """)
    
    st.markdown("---")
    st.markdown("#### Delivery Status")
    st.markdown("""
    | Icon | Trạng thái |
    |------|-----------|
    | ⏳ | Pending |
    | 📦 | Dispatched |
    | 🚚 | On Delivery |
    | ✅ | Delivered / Received |
    """)


# ==================== PERMISSIONS ====================

def _render_permissions():
    """Role-based permissions reference"""
    
    st.markdown("### 🔐 Phân quyền theo Role")
    
    st.markdown("""
    Hệ thống phân quyền dựa trên role trong bảng users. 
    Mỗi role có tập hành động được phép khác nhau.
    """)
    
    st.markdown("---")
    st.markdown("#### Full Access (Toàn quyền)")
    st.markdown("""
    | Role | View | Create | Update ETD | Cancel | Reverse | Delete |
    |------|:----:|:------:|:----------:|:------:|:-------:|:------:|
    | **admin** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
    | **supply_chain_manager** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
    | **allocator** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
    """)
    
    st.markdown("---")
    st.markdown("#### Management (Quản lý)")
    st.markdown("""
    | Role | View | Create | Update ETD | Cancel | Reverse | Delete |
    |------|:----:|:------:|:----------:|:------:|:-------:|:------:|
    | **gm** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
    | **md** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
    """)
    
    st.markdown("---")
    st.markdown("#### Operational (Vận hành)")
    st.markdown("""
    | Role | View | Create | Update ETD | Cancel | Reverse | Delete |
    |------|:----:|:------:|:----------:|:------:|:-------:|:------:|
    | **supply_chain** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
    | **outbound_manager** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
    | **inbound_manager** | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
    """)
    
    st.markdown("---")
    st.markdown("#### View Only (Chỉ xem)")
    st.markdown("""
    | Role | View | Create | Update ETD | Cancel | Reverse | Delete |
    |------|:----:|:------:|:----------:|:------:|:-------:|:------:|
    | **warehouse_manager** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
    | **buyer** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
    | **sales_manager** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
    | **sales** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
    | **viewer** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
    """)
    
    st.info(
        "💡 Nếu bạn cần quyền cao hơn, vui lòng liên hệ Supply Chain Manager hoặc Admin "
        "để được cấp role phù hợp."
    )
