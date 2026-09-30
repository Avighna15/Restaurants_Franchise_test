import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ============================================================
# LuLu / Restaurant Franchise Expansion Dashboard
# Hypothesis project:
# Food cost, labour, rent and utilities are assumed to be AED 0.
# Therefore "Illustrative Profit" = Net Revenue after platform
# commission. This is NOT a full accounting profit measure.
# ============================================================

st.set_page_config(
    page_title="Franchise Expansion Dashboard",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------- STYLE -----------------------------
st.markdown("""
<style>
.block-container {padding-top:1.3rem; padding-bottom:2rem; max-width:1500px;}
.title {font-size:2.15rem;font-weight:800;letter-spacing:-.03em;margin-bottom:.1rem;}
.subtitle {color:#667085;font-size:.98rem;margin-bottom:1rem;}
.section {font-size:1.15rem;font-weight:750;margin:.45rem 0 .35rem;}
.note {color:#667085;font-size:.82rem;}
div[data-testid="stMetric"] {
    background:#fff;border:1px solid #EAECF0;padding:15px 17px;
    border-radius:14px;box-shadow:0 2px 8px rgba(16,24,40,.05);
}
div[data-testid="stMetricLabel"] {color:#667085;font-weight:600;}
div[data-testid="stMetricValue"] {font-weight:800;}
</style>
""", unsafe_allow_html=True)

# ------------------------- DATA ------------------------------
DATA_DIR = "data"

@st.cache_data
def load_data():
    areas = pd.read_csv(f"{DATA_DIR}/areas.csv")
    menu = pd.read_csv(f"{DATA_DIR}/menu.csv")
    orders = pd.read_csv(f"{DATA_DIR}/orders.csv")
    items = pd.read_csv(f"{DATA_DIR}/order_items.csv")
    platforms = pd.read_csv(f"{DATA_DIR}/platforms.csv")

    orders["order_datetime"] = pd.to_datetime(orders["order_datetime"])
    for c in ["preparing_at", "ready_at", "dispatched_at", "completed_at"]:
        orders[c] = pd.to_datetime(orders[c], errors="coerce")

    return areas, menu, orders, items, platforms

areas, menu, orders, items, platforms = load_data()

# Only Delivered orders are treated as realised sales.
delivered_orders = orders[orders["status"].eq("Delivered")].copy()

# Attach order-level fields to every item.
item_data = items.merge(
    orders[
        [
            "order_id", "order_datetime", "channel_type", "platform",
            "order_type", "area", "status", "gross_amount",
            "commission_amount", "net_revenue"
        ]
    ],
    on="order_id",
    how="left",
)

# Attach menu characteristics.
item_data = item_data.merge(
    menu[
        ["dish", "dish_id", "cuisine", "category", "price_aed",
         "prep_minutes", "popularity"]
    ].drop_duplicates("dish"),
    on="dish",
    how="left",
    suffixes=("", "_menu"),
)

# Allocate order commission across items in proportion to item revenue.
# This creates a transparent item-level net revenue proxy.
order_item_gross = item_data.groupby("order_id")["line_total"].transform("sum")
item_data["allocated_commission"] = (
    item_data["commission_amount"]
    * item_data["line_total"]
    / order_item_gross.replace(0, pd.NA)
).fillna(0)

item_data["item_net_revenue"] = item_data["line_total"] - item_data["allocated_commission"]

# Project assumption requested by the user.
FOOD_COST = 0
LABOUR_COST = 0
RENT_COST = 0
UTILITIES_COST = 0

item_data["illustrative_profit"] = (
    item_data["item_net_revenue"]
    - FOOD_COST
    - LABOUR_COST
    - RENT_COST
    - UTILITIES_COST
)

# ------------------------- HELPERS ---------------------------
def aed(v):
    if pd.isna(v):
        return "AED 0"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"AED {v/1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"AED {v/1_000:.1f}K"
    return f"AED {v:,.0f}"

def pct(v):
    return "—" if pd.isna(v) else f"{v:.1f}%"

def growth(current, previous):
    if previous is None or previous == 0:
        return None
    return (current - previous) / previous * 100

def order_metrics(d):
    revenue = d["gross_amount"].sum()
    net = d["net_revenue"].sum()
    n = d["order_id"].nunique()
    cancellations = (d["status"] == "Cancelled").sum()
    return revenue, net, n, (cancellations / len(d) * 100 if len(d) else 0)

# ------------------------- HEADER ----------------------------
st.markdown('<div class="title">🏪 Franchise Expansion Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Using historical order, product, area and platform data to evaluate evidence for a potential new branch.</div>',
    unsafe_allow_html=True,
)

st.info(
    "Project assumption: food cost, labour cost, rent and utilities are currently set to AED 0. "
    "Therefore, Illustrative Profit = Net Revenue after platform commission. "
    "This is a hypothesis metric, not audited accounting profit."
)

# ------------------------- NAVIGATION -----------------------
tab1, tab2, tab3 = st.tabs([
    "🏢 Executive Overview",
    "📍 Expansion Analysis",
    "🍕 Product & Location Analysis",
])

# ============================================================
# TAB 1 — EXECUTIVE OVERVIEW
# ============================================================
with tab1:
    st.markdown('<div class="section">Overall business performance</div>', unsafe_allow_html=True)

    # Global date filter
    min_date = orders["order_datetime"].min().date()
    max_date = orders["order_datetime"].max().date()

    d1, d2 = st.columns([1, 2])
    with d1:
        date_range = st.date_input(
            "Analysis period",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    with d2:
        st.markdown(
            '<div class="note" style="padding-top:30px;">Cancelled orders are excluded from realised revenue and order-value KPIs, but cancellation rate is shown separately.</div>',
            unsafe_allow_html=True,
        )

    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start = pd.Timestamp(date_range[0])
        end = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    else:
        start = pd.Timestamp(date_range)
        end = start + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    period_orders = orders[
        (orders["order_datetime"] >= start) &
        (orders["order_datetime"] <= end)
    ].copy()
    period_delivered = period_orders[period_orders["status"].eq("Delivered")].copy()

    gross = period_delivered["gross_amount"].sum()
    net = period_delivered["net_revenue"].sum()
    order_count = len(period_delivered)
    aov = net / order_count if order_count else 0
    cancellation_rate = (
        (period_orders["status"] == "Cancelled").mean() * 100
        if len(period_orders) else 0
    )
    commission = period_delivered["commission_amount"].sum()
    illustrative_profit = net  # all other costs assumed zero

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    k1.metric("Gross Revenue", aed(gross))
    k2.metric("Net Revenue", aed(net))
    k3.metric("Orders", f"{order_count:,}")
    k4.metric("Average Order Value", aed(aov))
    k5.metric("Cancellation Rate", pct(cancellation_rate))
    k6.metric("Commission Cost", aed(commission))

    st.caption(
        f"Illustrative profit under current project assumptions: {aed(illustrative_profit)}."
    )

    # Revenue trend
    st.markdown('<div class="section">Revenue trend</div>', unsafe_allow_html=True)
    trend = (
        period_delivered.assign(Month=period_delivered["order_datetime"].dt.to_period("M").dt.to_timestamp())
        .groupby("Month", as_index=False)
        .agg(Gross_Revenue=("gross_amount","sum"), Net_Revenue=("net_revenue","sum"))
    )
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=trend["Month"], y=trend["Gross_Revenue"], mode="lines+markers",
        name="Gross Revenue", line=dict(width=3),
        hovertemplate="Gross: AED %{y:,.0f}<extra></extra>"
    ))
    fig.add_trace(go.Scatter(
        x=trend["Month"], y=trend["Net_Revenue"], mode="lines+markers",
        name="Net Revenue", line=dict(width=2),
        hovertemplate="Net: AED %{y:,.0f}<extra></extra>"
    ))
    fig.update_layout(height=350, margin=dict(l=10,r=10,t=15,b=10), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    c1,c2,c3 = st.columns(3)

    with c1:
        st.markdown('<div class="section">Top dishes by units</div>', unsafe_allow_html=True)
        top_dishes = (
            item_data[
                (item_data["status"] == "Delivered") &
                (item_data["order_datetime"] >= start) &
                (item_data["order_datetime"] <= end)
            ]
            .groupby("dish", as_index=False)["quantity"].sum()
            .sort_values("quantity", ascending=False).head(8)
        )
        fig = px.bar(top_dishes.sort_values("quantity"), x="quantity", y="dish", orientation="h")
        fig.update_layout(height=330, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<div class="section">Revenue by area</div>', unsafe_allow_html=True)
        area_rev = (
            period_delivered.groupby("area", as_index=False)["net_revenue"]
            .sum().sort_values("net_revenue", ascending=False)
        )
        fig = px.bar(area_rev.sort_values("net_revenue"), x="net_revenue", y="area", orientation="h")
        fig.update_layout(height=330, margin=dict(l=10,r=10,t=10,b=10), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with c3:
        st.markdown('<div class="section">Platform revenue mix</div>', unsafe_allow_html=True)
        plat = period_delivered.groupby("platform", as_index=False)["net_revenue"].sum()
        fig = px.pie(plat, names="platform", values="net_revenue", hole=.55)
        fig.update_layout(height=330, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TAB 2 — EXPANSION ANALYSIS
# ============================================================
with tab2:
    st.markdown('<div class="section">New branch expansion analysis</div>', unsafe_allow_html=True)
    st.write(
        "Use this page to compare existing areas as evidence for a potential branch. "
        "It does not assume that the strongest historical area is automatically the right location."
    )

    area_list = sorted(areas["area"].dropna().unique())
    selected_area = st.selectbox("Select a candidate area to investigate", area_list)

    candidate = orders[orders["area"] == selected_area].copy()
    network = orders.copy()

    candidate_del = candidate[candidate["status"] == "Delivered"]
    network_del = network[network["status"] == "Delivered"]

    cand_gross = candidate_del["gross_amount"].sum()
    cand_net = candidate_del["net_revenue"].sum()
    cand_orders = len(candidate_del)
    cand_aov = cand_net / cand_orders if cand_orders else 0
    cand_cancel = (candidate["status"] == "Cancelled").mean() * 100 if len(candidate) else 0
    cand_commission = candidate_del["commission_amount"].sum()

    net_share = cand_net / network_del["net_revenue"].sum() * 100 if network_del["net_revenue"].sum() else 0

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Area Gross Revenue", aed(cand_gross))
    m2.metric("Area Net Revenue", aed(cand_net))
    m3.metric("Delivered Orders", f"{cand_orders:,}")
    m4.metric("Average Order Value", aed(cand_aov))
    m5.metric("Cancellation Rate", pct(cand_cancel))

    st.caption(
        f"{selected_area} contributes {net_share:.1f}% of network net revenue in the available dataset. "
        f"Commission cost in this area is {aed(cand_commission)}."
    )

    # Area comparison table
    st.markdown('<div class="section">Area opportunity comparison</div>', unsafe_allow_html=True)

    area_summary = (
        orders.groupby("area")
        .apply(lambda g: pd.Series({
            "Orders": (g["status"] == "Delivered").sum(),
            "Gross_Revenue": g.loc[g["status"] == "Delivered", "gross_amount"].sum(),
            "Net_Revenue": g.loc[g["status"] == "Delivered", "net_revenue"].sum(),
            "AOV": (
                g.loc[g["status"] == "Delivered", "net_revenue"].sum()
                / max((g["status"] == "Delivered").sum(), 1)
            ),
            "Cancellation_Rate": (g["status"] == "Cancelled").mean() * 100,
            "Commission": g.loc[g["status"] == "Delivered", "commission_amount"].sum(),
        }), include_groups=False)
        .reset_index()
    )

    area_summary["Net_Revenue_Share"] = (
        area_summary["Net_Revenue"] / area_summary["Net_Revenue"].sum() * 100
    )

    area_summary = area_summary.merge(areas, on="area", how="left")
    area_summary = area_summary.sort_values("Net_Revenue", ascending=False)

    st.dataframe(
        area_summary,
        use_container_width=True,
        hide_index=True,
        column_config={
            "area": "Area",
            "Orders": st.column_config.NumberColumn("Orders", format="%d"),
            "Gross_Revenue": st.column_config.NumberColumn("Gross Revenue", format="AED %.0f"),
            "Net_Revenue": st.column_config.NumberColumn("Net Revenue", format="AED %.0f"),
            "AOV": st.column_config.NumberColumn("AOV", format="AED %.0f"),
            "Cancellation_Rate": st.column_config.NumberColumn("Cancellation", format="%.1f%%"),
            "Commission": st.column_config.NumberColumn("Commission", format="AED %.0f"),
            "Net_Revenue_Share": st.column_config.NumberColumn("Net Revenue Share", format="%.1f%%"),
            "distance_km": st.column_config.NumberColumn("Distance (km)", format="%.0f"),
            "order_weight": st.column_config.NumberColumn("Order Weight", format="%.0f"),
        },
    )

    # Candidate area product mix
    st.markdown(f'<div class="section">What sells in {selected_area}?</div>', unsafe_allow_html=True)

    cand_items = item_data[
        (item_data["area"] == selected_area) &
        (item_data["status"] == "Delivered")
    ].copy()

    product_mix = (
        cand_items.groupby(["dish","category","cuisine"], as_index=False)
        .agg(
            Units=("quantity","sum"),
            Item_Revenue=("line_total","sum"),
            Item_Net_Revenue=("item_net_revenue","sum"),
        )
        .sort_values("Item_Net_Revenue", ascending=False)
    )

    product_mix["Revenue_Share"] = (
        product_mix["Item_Net_Revenue"] / product_mix["Item_Net_Revenue"].sum() * 100
    )

    p1,p2 = st.columns([1.3,1])

    with p1:
        top_area_products = product_mix.head(10).sort_values("Item_Net_Revenue")
        fig = px.bar(
            top_area_products,
            x="Item_Net_Revenue",
            y="dish",
            color="category",
            orientation="h",
            labels={"Item_Net_Revenue":"Illustrative Net Revenue","dish":""}
        )
        fig.update_layout(height=390, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)

    with p2:
        st.markdown("**Top product mix**")
        st.dataframe(
            product_mix.head(10),
            use_container_width=True,
            hide_index=True,
            column_config={
                "dish":"Dish",
                "category":"Category",
                "cuisine":"Cuisine",
                "Units":st.column_config.NumberColumn("Units",format="%d"),
                "Item_Revenue":st.column_config.NumberColumn("Gross Item Revenue",format="AED %.0f"),
                "Item_Net_Revenue":st.column_config.NumberColumn("Illustrative Profit",format="AED %.0f"),
                "Revenue_Share":st.column_config.NumberColumn("Share",format="%.1f%%"),
            }
        )

    st.markdown("### Expansion evidence")
    top = product_mix.iloc[0] if not product_mix.empty else None

    if top is not None:
        overall_items = item_data[item_data["status"] == "Delivered"]
        overall_dish = overall_items[overall_items["dish"] == top["dish"]]
        overall_share = (
            overall_dish["item_net_revenue"].sum() / overall_items["item_net_revenue"].sum() * 100
            if overall_items["item_net_revenue"].sum() else 0
        )
        area_share = top["Revenue_Share"]
        concentration = area_share / overall_share if overall_share else 0

        e1,e2,e3 = st.columns(3)
        e1.metric("Top product in area", str(top["dish"]))
        e2.metric("Area product share", f"{area_share:.1f}%")
        e3.metric("Overall product share", f"{overall_share:.1f}%")

        if overall_share:
            st.info(
                f"{top['dish']} represents {area_share:.1f}% of illustrative item net revenue in "
                f"{selected_area}, versus {overall_share:.1f}% across the network "
                f"(about {concentration:.1f}× the overall concentration)."
            )

    st.caption(
        "Expansion evidence should be considered together: area demand, product concentration, "
        "AOV, cancellation rate and commission burden. The dashboard does not make an automatic "
        "branch-location decision."
    )

# ============================================================
# TAB 3 — PRODUCT & LOCATION ANALYSIS
# ============================================================
with tab3:
    st.markdown('<div class="section">Product & location intelligence</div>', unsafe_allow_html=True)
    st.write(
        "Test the core hypothesis: does a product perform disproportionately well in a particular area?"
    )

    q1,q2,q3,q4 = st.columns(4)

    cuisine_options = ["All"] + sorted(menu["cuisine"].dropna().unique().tolist())
    category_options = ["All"] + sorted(menu["category"].dropna().unique().tolist())

    with q1:
        cuisine_sel = st.selectbox("Cuisine", cuisine_options)
    with q2:
        category_sel = st.selectbox("Category", category_options)

    filtered_menu = menu.copy()
    if cuisine_sel != "All":
        filtered_menu = filtered_menu[filtered_menu["cuisine"] == cuisine_sel]
    if category_sel != "All":
        filtered_menu = filtered_menu[filtered_menu["category"] == category_sel]

    dish_options = ["All"] + sorted(filtered_menu["dish"].dropna().unique().tolist())
    with q3:
        dish_sel = st.selectbox("Dish", dish_options)
    with q4:
        area_sel = st.selectbox("Location", ["All"] + sorted(areas["area"].unique()))

    selected_items = item_data[item_data["status"] == "Delivered"].copy()

    if cuisine_sel != "All":
        selected_items = selected_items[selected_items["cuisine"] == cuisine_sel]
    if category_sel != "All":
        selected_items = selected_items[selected_items["category"] == category_sel]
    if dish_sel != "All":
        selected_items = selected_items[selected_items["dish"] == dish_sel]
    if area_sel != "All":
        selected_items = selected_items[selected_items["area"] == area_sel]

    if selected_items.empty:
        st.warning("No delivered item sales match the selected filters.")
        st.stop()

    total_units = selected_items["quantity"].sum()
    item_revenue = selected_items["line_total"].sum()
    item_net = selected_items["item_net_revenue"].sum()
    item_orders = selected_items["order_id"].nunique()
    avg_item_value = item_revenue / total_units if total_units else 0

    # Menu reference metrics when a single dish is selected.
    menu_match = menu[menu["dish"] == dish_sel] if dish_sel != "All" else pd.DataFrame()
    popularity = menu_match["popularity"].iloc[0] if not menu_match.empty else None
    prep = menu_match["prep_minutes"].iloc[0] if not menu_match.empty else None

    r1,r2,r3,r4,r5,r6 = st.columns(6)
    r1.metric("Units", f"{int(total_units):,}")
    r2.metric("Gross Item Revenue", aed(item_revenue))
    r3.metric("Illustrative Profit", aed(item_net))
    r4.metric("Orders Containing Item", f"{item_orders:,}")
    r5.metric("Avg Item Price", aed(avg_item_value))
    r6.metric("Popularity", f"{popularity:.0f}/10" if popularity is not None else "Multiple")

    if prep is not None:
        st.caption(
            f"Menu reference: preparation time {prep:.0f} minutes. "
            f"Food cost, labour, rent and utilities are assumed to be AED 0 in this project."
        )

    # Selected location vs overall benchmark
    st.markdown('<div class="section">Selected location vs overall</div>', unsafe_allow_html=True)

    benchmark_items = item_data[item_data["status"] == "Delivered"].copy()

    if dish_sel != "All":
        benchmark_items = benchmark_items[benchmark_items["dish"] == dish_sel]
    elif category_sel != "All":
        benchmark_items = benchmark_items[benchmark_items["category"] == category_sel]
    elif cuisine_sel != "All":
        benchmark_items = benchmark_items[benchmark_items["cuisine"] == cuisine_sel]

    overall_units = benchmark_items["quantity"].sum()
    overall_revenue = benchmark_items["line_total"].sum()
    overall_net = benchmark_items["item_net_revenue"].sum()
    overall_orders = benchmark_items["order_id"].nunique()

    if area_sel != "All":
        selected_bench = benchmark_items[benchmark_items["area"] == area_sel]
        location_name = area_sel
    else:
        selected_bench = benchmark_items
        location_name = "All areas"

    selected_units = selected_bench["quantity"].sum()
    selected_revenue = selected_bench["line_total"].sum()
    selected_net = selected_bench["item_net_revenue"].sum()
    selected_orders = selected_bench["order_id"].nunique()

    benchmark = pd.DataFrame({
        "Metric": ["Units", "Gross Item Revenue", "Illustrative Profit", "Orders Containing Item"],
        location_name: [selected_units, selected_revenue, selected_net, selected_orders],
        "Overall": [overall_units, overall_revenue, overall_net, overall_orders],
    })

    st.dataframe(
        benchmark,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Units": st.column_config.NumberColumn("Units", format="%.0f"),
            "Gross Item Revenue": st.column_config.NumberColumn("Gross Item Revenue", format="AED %.0f"),
            "Illustrative Profit": st.column_config.NumberColumn("Illustrative Profit", format="AED %.0f"),
            "Orders Containing Item": st.column_config.NumberColumn("Orders Containing Item", format="%.0f"),
        },
    )

    # Product distribution across areas
    st.markdown('<div class="section">Where does the selected product/category sell?</div>', unsafe_allow_html=True)

    area_product = (
        benchmark_items.groupby("area", as_index=False)
        .agg(Units=("quantity","sum"), Illustrative_Profit=("item_net_revenue","sum"))
        .sort_values("Units", ascending=False)
    )

    fig = px.bar(
        area_product,
        x="area",
        y="Units",
        hover_data=["Illustrative_Profit"],
        labels={"area":"","Units":"Units Sold"},
    )
    fig.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Compact cancellation view
    if dish_sel != "All":
        item_orders_all = item_data[item_data["dish"] == dish_sel].copy()
    elif category_sel != "All":
        item_orders_all = item_data[item_data["category"] == category_sel].copy()
    elif cuisine_sel != "All":
        item_orders_all = item_data[item_data["cuisine"] == cuisine_sel].copy()
    else:
        item_orders_all = item_data.copy()

    cancellation_by_area = (
        item_orders_all.groupby("area")
        .agg(
            Orders=("order_id","nunique"),
            Cancelled_Orders=("status", lambda s: (s == "Cancelled").sum()),
        )
        .reset_index()
    )
    cancellation_by_area["Cancellation_Rate"] = (
        cancellation_by_area["Cancelled_Orders"] / cancellation_by_area["Orders"] * 100
    ).fillna(0)

    st.markdown('<div class="section">Cancellation rate for selected product/category</div>', unsafe_allow_html=True)
    st.dataframe(
        cancellation_by_area.sort_values("Cancellation_Rate"),
        use_container_width=True,
        hide_index=True,
        column_config={
            "area":"Area",
            "Orders":st.column_config.NumberColumn("Orders",format="%d"),
            "Cancelled_Orders":st.column_config.NumberColumn("Cancelled",format="%d"),
            "Cancellation_Rate":st.column_config.NumberColumn("Cancellation",format="%.1f%%"),
        }
    )

st.divider()
st.caption(
    "Hypothesis dashboard • Source: areas, menu, orders, order_items and platforms datasets • "
    "Illustrative profit assumes AED 0 for food, labour, rent and utilities."
)
