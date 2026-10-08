import streamlit as st
import pandas as pd
import os
import plotly.express as px
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="Paper Roll Inventory Tracker",
    page_icon="📦",
    layout="wide"
)

# ==================================================
# LOAD ENV
# ==================================================

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    st.error("DATABASE_URL not found.")
    st.stop()

# ==================================================
# DATABASE
# ==================================================

@st.cache_resource
def get_engine():
    return create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300
    )

engine = get_engine()

try:
    with engine.connect():
        pass
except Exception as e:
    st.error(f"Database Connection Failed: {e}")
    st.stop()

# ==================================================
# CONFIG
# ==================================================

LOW_STOCK_THRESHOLD = 10
MAX_STOCK = 40

# ==================================================
# CSS
# ==================================================

st.markdown("""
<style>

.stApp{
    background:#0B1120;
}

.block-container{
    padding-top:1rem;
}

[data-testid="metric-container"]{
    background:linear-gradient(
    135deg,
    #1E293B,
    #334155
    );

    border-radius:20px;
    padding:20px;

    box-shadow:
    0 4px 10px rgba(0,0,0,.4);
}

h1,h2,h3{
    color:white;
}

</style>
""", unsafe_allow_html=True)

# ==================================================
# FUNCTIONS
# ==================================================

@st.cache_data(ttl=60)
def load_inventory():

    query = """
    SELECT
        "Date",
        "Employee Name",
        "Terminal Location",
        "Paper Rolls Used",
        "Remaining Stock"
    FROM "Inventory"
    ORDER BY "Date" DESC
    """

    return pd.read_sql(query, engine)


def get_stock():

    query = """
    SELECT current_stock
    FROM stock
    WHERE id = 1
    """

    stock_df = pd.read_sql(
        query,
        engine
    )

    if stock_df.empty:
        return 0

    return int(
        stock_df.iloc[0]["current_stock"]
    )


def update_stock(new_stock):

    with engine.begin() as conn:

        conn.execute(
            text("""
            UPDATE stock
            SET current_stock = :stock
            WHERE id = 1
            """),
            {"stock": new_stock}
        )


# ==================================================
# LOAD DATA
# ==================================================

df = load_inventory()

current_stock = get_stock()

if df.empty:
    total_used = 0
else:
    total_used = int(
        df["Paper Rolls Used"].sum()
    )

# ==================================================
# BANNER
# ==================================================

if os.path.exists("assets/banner.png"):
    st.image(
        "assets/banner.png",
        use_container_width=True
    )

# ==================================================
# HEADER
# ==================================================

col_logo, col_title = st.columns([1,5])

with col_logo:

    if os.path.exists("assets/logo.png"):
        st.image(
            "assets/logo.png",
            width=120
        )

with col_title:

    st.markdown("""
    # 📦 Wisconsin Paper Roll Inventory Tracker
    ### Real-Time Inventory Monitoring Dashboard
    """)

st.divider()

# ==================================================
# STATUS IMAGE
# ==================================================

img1, img2, img3 = st.columns([1,2,1])

with img2:

    if current_stock > 20:

        if os.path.exists("assets/healthy.png"):
            st.image(
                "assets/healthy.png",
                use_container_width=True
            )

    elif current_stock > 10:

        if os.path.exists("assets/warning.png"):
            st.image(
                "assets/warning.png",
                use_container_width=True
            )

    else:

        if os.path.exists("assets/critical.png"):
            st.image(
                "assets/critical.png",
                use_container_width=True
            )

# ==================================================
# DASHBOARD
# ==================================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Current Stock",
        current_stock
    )

with col2:
    st.metric(
        "Total Used",
        total_used
    )

with col3:
    st.metric(
        "Low Stock Level",
        LOW_STOCK_THRESHOLD
    )

with col4:

    avg_daily = total_used / 30 if total_used else 0

    days_left = (
        int(current_stock / avg_daily)
        if avg_daily > 0
        else 0
    )

    st.metric(
        "Est. Days Left",
        days_left
    )

stock_percentage = min(
    (current_stock / MAX_STOCK) * 100,
    100
)

st.progress(int(stock_percentage))

st.caption(
    f"{stock_percentage:.0f}% stock available"
)

# ==================================================
# ALERT
# ==================================================

if current_stock <= LOW_STOCK_THRESHOLD:

    st.error(
        f"⚠ LOW STOCK ALERT! ONLY {current_stock} ROLLS REMAINING!"
    )

    if os.path.exists("assets/warning.mp3"):
        st.audio("assets/warning.mp3")

else:

    st.success(
        "✅ Stock Level Healthy"
    )

st.divider()

# ==================================================
# FORMS
# ==================================================

left, right = st.columns(2)

# ==================================================
# ADD USAGE
# ==================================================

with left:

    st.subheader("📝 Add Usage Record")

    with st.form("usage_form"):

        date = st.date_input("Date")

        employee = st.text_input(
            "Employee Name"
        )

        terminal = st.selectbox(
            "Terminal Location",
            [
                "Nitheesh place RPS2",
                "Abi Place RPS2",
                "Sharon Place RPS2",
                "GT1250",
                "WI GT20",
                "WV GT20"
            ]
        )

        rolls_used = st.number_input(
            "Paper Rolls Used",
            min_value=1,
            value=1
        )

        submit_usage = st.form_submit_button(
            "Save Usage"
        )

        if submit_usage:

            if not employee.strip():

                st.error(
                    "Employee Name is required"
                )
                st.stop()

            stock = get_stock()

            if rolls_used > stock:

                st.error(
                    f"Only {stock} rolls available."
                )

            else:

                remaining_stock = stock - rolls_used

                update_stock(
                    remaining_stock
                )

                record = pd.DataFrame({

                    "Date":[
                        date.strftime("%Y-%m-%d")
                    ],

                    "Employee Name":[
                        employee
                    ],

                    "Terminal Location":[
                        terminal
                    ],

                    "Paper Rolls Used":[
                        rolls_used
                    ],

                    "Remaining Stock":[
                        remaining_stock
                    ]
                })

                record.to_sql(
                    "Inventory",
                    engine,
                    if_exists="append",
                    index=False
                )

                st.success(
                    "✅ Usage Record Saved"
                )

                if os.path.exists(
                    "assets/success.mp3"
                ):
                    st.audio(
                        "assets/success.mp3"
                    )

                st.rerun()

# ==================================================
# ADD STOCK
# ==================================================

with right:

    st.subheader("📦 Add New Stock")

    stock_to_add = st.number_input(
        "Number of Rolls Received",
        min_value=1,
        value=1
    )

    if st.button(
        "Add Stock",
        use_container_width=True
    ):

        new_stock = (
            get_stock()
            + stock_to_add
        )

        update_stock(
            new_stock
        )

        st.success(
            f"✅ {stock_to_add} rolls added successfully"
        )

        st.rerun()

# ==================================================
# TRANSACTIONS
# ==================================================

st.divider()

st.subheader(
    "📋 Recent Transactions"
)

if not df.empty:

    st.dataframe(
        df.head(20),
        use_container_width=True,
        height=400
    )

else:

    st.info(
        "No records available yet."
    )

# ==================================================
# REPORTS
# ==================================================

if not df.empty:

    st.divider()

    st.subheader(
        "👨‍💼 Employee Usage Report"
    )

    employee_report = (
        df.groupby(
            "Employee Name"
        )["Paper Rolls Used"]
        .sum()
        .reset_index()
    )

    st.dataframe(
        employee_report,
        use_container_width=True
    )

    fig = px.bar(
        employee_report,
        x="Employee Name",
        y="Paper Rolls Used",
        color="Paper Rolls Used",
        template="plotly_dark",
        text_auto=True
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    fig2 = px.pie(
        employee_report,
        names="Employee Name",
        values="Paper Rolls Used",
        hole=.5
    )

    st.plotly_chart(
        fig2,
        use_container_width=True
    )

# ==================================================
# DOWNLOAD
# ==================================================

csv_data = (
    df.to_csv(index=False)
    .encode("utf-8")
)

st.download_button(
    label="📥 Download Usage Report",
    data=csv_data,
    file_name="WI_paper_roll_usage.csv",
    mime="text/csv"
)