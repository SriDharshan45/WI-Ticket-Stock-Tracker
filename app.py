import streamlit as st
import pandas as pd
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

try:
    with engine.connect() as conn:
        st.success("✅ Database Connected")
except Exception as e:
    st.error(f"Database Connection Failed: {e}")

# ==================================================
# CONFIGURATION
# ==================================================
LOW_STOCK_THRESHOLD = 10

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="Paper Roll Inventory Tracker",
    page_icon="📦",
    layout="wide"
)

# ==================================================
# CUSTOM CS
# ==================================================
st.markdown("""
<style>

.stApp {
    background-color: #0E1117;
}

[data-testid="metric-container"] {
    background-color: #262730;
    border: 1px solid #444;
    padding: 15px;
    border-radius: 15px;
    text-align: center;
}

h1,h2,h3 {
    color: white;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# STOCK FUNCTIONS
# ==================================================

# ==================================================
# STOCK FUNCTIONS
# ==================================================
def get_stock():

    query = """
    SELECT current_stock
    FROM stock
    WHERE id = 1
    """

    stock_df = pd.read_sql(query, engine)
    if df.empty:
        total_used = 0
    else:
        total_used = df["Paper Rolls Used"].sum()

    return int(stock_df.iloc[0]["current_stock"])


def update_stock(stock):

    with engine.begin() as conn:

        conn.execute(
            text("""
                UPDATE stock
                SET current_stock = :stock
                WHERE id = 1
            """),
            {"stock": stock}
        )


# ==================================================

# ==================================================
# LOAD DATA
# ==================================================
df = pd.read_sql(
    'SELECT * FROM "Inventory"',
    engine
)
current_stock = get_stock()

if df.empty:
    total_used = 0
else:
    total_used = df["Paper Rolls Used"].sum()

# ==================================================
current_stock = get_stock()
# HEADER
# ==================================================
st.markdown("""
<h1 style='text-align:center'>
📦 Wisconsin Paper Roll Inventory Tracker
</h1>
""", unsafe_allow_html=True)

st.divider()

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
        int(total_used)
    )

with col3:
    st.metric(
        "Low Stock Level",
        LOW_STOCK_THRESHOLD
    )

with col4:

    avg_daily = total_used / 30 if total_used > 0 else 0

    days_left = int(current_stock / avg_daily) if avg_daily > 0 else 0

    st.metric(
        "Est. Days Left",
        days_left
    )

# ==================================================
# ALERT SECTION
# ==================================================
if current_stock <= LOW_STOCK_THRESHOLD:

    st.error(
        f"⚠ LOW STOCK ALERT! ONLY {current_stock} ROLLS REMAINING!"
    )

    # OPTIONAL SOUND
    if os.path.exists("warning.mp3"):
        st.audio("warning.mp3")

else:

    st.success(
        "✅ Stock Level Healthy"
    )

st.divider()

# ==================================================
# MAIN SECTIONS
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

            stock = get_stock()

            if rolls_used > stock:

                st.error(
                    f"Only {stock} rolls available."
                )

            else:

                remaining_stock = stock - rolls_used

                update_stock(remaining_stock)

                record = pd.DataFrame({

                    "Date": [
                        date.strftime("%Y-%m-%d")
                    ],

                    "Employee Name": [
                        employee
                    ],

                    "Terminal Location": [
                        terminal
                    ],

                    "Paper Rolls Used": [
                        rolls_used
                    ],

                    "Remaining Stock": [
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

        current = get_stock()

        new_stock = current + stock_to_add

        update_stock(new_stock)

        st.success(
            f"✅ {stock_to_add} rolls added successfully"
        )
        st.rerun()


st.divider()

# ==================================================
# RECENT RECORDS
# ==================================================
st.subheader("📋 Recent Transactions")

if not df.empty:

    st.dataframe(
        df.tail(20),
        use_container_width=True,
        height=350
    )

else:

    st.info("No records available yet.")

# ==================================================
# EMPLOYEE REPORT
# ==================================================
if not df.empty:

    st.divider()

    st.subheader("👨‍💼 Employee Usage Report")

    employee_report = (
        df.groupby("Employee Name")
        ["Paper Rolls Used"]
        .sum()
        .reset_index()
    )

    st.dataframe(
        employee_report,
        use_container_width=True
    )

    st.bar_chart(
        employee_report.set_index(
            "Employee Name"
        )
    )

# ==================================================
# DOWNLOAD REPORT
# ==================================================
csv_data = df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="📥 Download Usage Report",
    data=csv_data,
    file_name="WI_paper_roll_usage.csv",
    mime="text/csv"
)
