import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ==================================================
# CONFIGURATION
# ==================================================
CSV_FILE = "WI_paper_roll_usage.csv"
STOCK_FILE = "WI_paper_roll_stock.txt"
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
# CUSTOM CSS
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
# INITIAL FILE CREATION
# ==================================================
def initialize_files():

    if not os.path.exists(CSV_FILE):

        df = pd.DataFrame(columns=[
            "Date",
            "Employee Name",
            "Terminal Location",
            "Paper Rolls Used",
            "Remaining Stock"
        ])

        df.to_csv(CSV_FILE, index=False)

    if not os.path.exists(STOCK_FILE):

        with open(STOCK_FILE, "w") as f:
            f.write("100")


# ==================================================
# STOCK FUNCTIONS
# ==================================================
def get_stock():

    with open(STOCK_FILE, "r") as f:
        return int(f.read())


def update_stock(stock):

    with open(STOCK_FILE, "w") as f:
        f.write(str(stock))


# ==================================================
# INITIALIZE
# ==================================================
initialize_files()

# ==================================================
# LOAD DATA
# ==================================================
df = pd.read_csv(CSV_FILE)

current_stock = get_stock()

if df.empty:
    total_used = 0
else:
    total_used = df["Paper Rolls Used"].sum()

# ==================================================
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

                existing = pd.read_csv(CSV_FILE)

                updated = pd.concat(
                    [existing, record],
                    ignore_index=True
                )

                updated.to_csv(
                    CSV_FILE,
                    index=False
                )

                st.success(
                    "✅ Usage Record Saved"
                )

                # OPTIONAL SUCCESS SOUND
                if os.path.exists("success.mp3"):
                    st.audio("success.mp3")

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

        # OPTIONAL SOUND
        if os.path.exists("stockadded.mp3"):
            st.audio("stockadded.mp3")

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
st.divider()

with open(CSV_FILE, "rb") as file:

    st.download_button(
        label="📥 Download Usage Report",
        data=file,
        file_name="WI_paper_roll_usage.csv",
        mime="text/csv"
    )