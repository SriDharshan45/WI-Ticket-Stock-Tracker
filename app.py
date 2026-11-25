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
# CREATE HISTORY TABLE
# ==================================================

def initialize_history():

    query = """
    CREATE TABLE IF NOT EXISTS inventory_history (

        id BIGSERIAL PRIMARY KEY,

        operation_type VARCHAR(30) NOT NULL,

        previous_stock INTEGER NOT NULL,

        updated_stock INTEGER NOT NULL,

        inventory_id BIGINT,

        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

        is_reverted BOOLEAN DEFAULT FALSE
    );
    """

    with engine.begin() as conn:
        conn.execute(text(query))


try:
    initialize_history()

except Exception as e:
    st.error(f"Unable to initialize inventory history: {e}")
    st.stop()


# ==================================================
# CSS
# ==================================================

st.markdown("""
<style>

.stApp {
    background: #0B1120;
}

.block-container {
    padding-top: 1rem;
}

[data-testid="metric-container"] {
    background: linear-gradient(
        135deg,
        #1E293B,
        #334155
    );

    border-radius: 20px;
    padding: 20px;

    box-shadow: 0 4px 10px rgba(0,0,0,.4);
}

h1, h2, h3 {
    color: white;
}

</style>
""", unsafe_allow_html=True)


# ==================================================
# FUNCTIONS
# ==================================================

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

    stock_df = pd.read_sql(query, engine)

    if stock_df.empty:
        return 0

    return int(stock_df.iloc[0]["current_stock"])


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
# GET LAST UPDATE
# ==================================================

def get_last_update():

    query = """
    SELECT
        id,
        operation_type,
        previous_stock,
        updated_stock,
        inventory_id,
        created_at,
        is_reverted

    FROM inventory_history

    ORDER BY id DESC

    LIMIT 1
    """

    history = pd.read_sql(query, engine)

    if history.empty:
        return None

    return history.iloc[0]


# ==================================================
# ADD USAGE WITH HISTORY
# ==================================================

def add_usage_record(
    date,
    employee,
    terminal,
    rolls_used
):

    with engine.begin() as conn:

        # Lock stock record

        stock_result = conn.execute(
            text("""
                SELECT current_stock
                FROM stock
                WHERE id = 1
                FOR UPDATE
            """)
        ).fetchone()

        if stock_result is None:
            raise ValueError("Stock record not found.")

        previous_stock = int(stock_result[0])

        if rolls_used > previous_stock:
            raise ValueError(
                f"Only {previous_stock} rolls available."
            )

        remaining_stock = previous_stock - rolls_used

        # Update stock

        conn.execute(
            text("""
                UPDATE stock
                SET current_stock = :stock
                WHERE id = 1
            """),
            {"stock": remaining_stock}
        )

        # Insert inventory record

        result = conn.execute(
            text("""
                INSERT INTO "Inventory" (
                    "Date",
                    "Employee Name",
                    "Terminal Location",
                    "Paper Rolls Used",
                    "Remaining Stock"
                )

                VALUES (
                    :date,
                    :employee,
                    :terminal,
                    :rolls_used,
                    :remaining_stock
                )

                RETURNING id
            """),
            {
                "date": date,
                "employee": employee,
                "terminal": terminal,
                "rolls_used": rolls_used,
                "remaining_stock": remaining_stock
            }
        )

        inventory_id = result.scalar_one()

        # Save history

        conn.execute(
            text("""
                INSERT INTO inventory_history (
                    operation_type,
                    previous_stock,
                    updated_stock,
                    inventory_id
                )

                VALUES (
                    'USAGE',
                    :previous_stock,
                    :updated_stock,
                    :inventory_id
                )
            """),
            {
                "previous_stock": previous_stock,
                "updated_stock": remaining_stock,
                "inventory_id": inventory_id
            }
        )

    return remaining_stock


# ==================================================
# ADD STOCK WITH HISTORY
# ==================================================

def add_new_stock(rolls_received):

    with engine.begin() as conn:

        stock_result = conn.execute(
            text("""
                SELECT current_stock
                FROM stock
                WHERE id = 1
                FOR UPDATE
            """)
        ).fetchone()

        if stock_result is None:
            raise ValueError("Stock record not found.")

        previous_stock = int(stock_result[0])

        new_stock = previous_stock + rolls_received

        # Update stock

        conn.execute(
            text("""
                UPDATE stock
                SET current_stock = :stock
                WHERE id = 1
            """),
            {"stock": new_stock}
        )

        # Save history

        conn.execute(
            text("""
                INSERT INTO inventory_history (
                    operation_type,
                    previous_stock,
                    updated_stock
                )

                VALUES (
                    'ADD_STOCK',
                    :previous_stock,
                    :updated_stock
                )
            """),
            {
                "previous_stock": previous_stock,
                "updated_stock": new_stock
            }
        )

    return new_stock


# ==================================================
# REVERT LAST UPDATE
# ==================================================

def revert_last_update():

    with engine.begin() as conn:

        # Lock stock record

        stock_result = conn.execute(
            text("""
                SELECT current_stock
                FROM stock
                WHERE id = 1
                FOR UPDATE
            """)
        ).fetchone()

        if stock_result is None:
            raise ValueError("Stock record not found.")

        current_stock = int(stock_result[0])

        # Get latest operation

        history = conn.execute(
            text("""
                SELECT
                    id,
                    operation_type,
                    previous_stock,
                    updated_stock,
                    inventory_id,
                    is_reverted

                FROM inventory_history

                ORDER BY id DESC

                LIMIT 1

                FOR UPDATE
            """)
        ).fetchone()

        if history is None:
            raise ValueError("No inventory update available to revert.")

        history_id = history[0]
        operation_type = history[1]
        previous_stock = int(history[2])
        updated_stock = int(history[3])
        inventory_id = history[4]
        is_reverted = history[5]

        if is_reverted:
            raise ValueError("Last update has already been reverted.")

        # Prevent undo if another stock change occurred
        # outside the tracked history.

        if current_stock != updated_stock:
            raise ValueError(
                "Stock has changed since the last operation. "
                "Revert is not allowed."
            )

        # Restore previous stock

        conn.execute(
            text("""
                UPDATE stock
                SET current_stock = :stock
                WHERE id = 1
            """),
            {"stock": previous_stock}
        )

        # If usage operation, delete its transaction

        if operation_type == "USAGE":

            if inventory_id is None:
                raise ValueError("Usage transaction ID is missing.")

            delete_result = conn.execute(
                text("""
                    DELETE FROM "Inventory"
                    WHERE id = :inventory_id
                """),
                {"inventory_id": inventory_id}
            )

            if delete_result.rowcount != 1:
                raise ValueError(
                    "Original usage transaction was not found."
                )

        # Mark operation as reverted

        conn.execute(
            text("""
                UPDATE inventory_history

                SET is_reverted = TRUE

                WHERE id = :history_id
            """),
            {"history_id": history_id}
        )

    return previous_stock, operation_type


# ==================================================
# REFRESH DASHBOARD
# ==================================================

def refresh_dashboard():

    st.cache_data.clear()

    st.rerun()


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

col_logo, col_title = st.columns([1, 5])

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

img1, img2, img3 = st.columns([1, 2, 1])

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


# ==================================================
# STOCK PROGRESS
# ==================================================

stock_percentage = min(
    max((current_stock / MAX_STOCK) * 100, 0),
    100
)

st.progress(
    int(stock_percentage)
)

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

        st.audio(
            "assets/warning.mp3"
        )

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
            step=1,
            value=1
        )

        submit_usage = st.form_submit_button(
            "Save Usage"
        )

    if submit_usage:

        if not employee.strip():

            st.error(
                "Employee Name is required."
            )

        else:

            try:

                remaining_stock = add_usage_record(
                    date,
                    employee.strip(),
                    terminal,
                    int(rolls_used)
                )

                st.success(
                    f"✅ Usage Record Saved. "
                    f"Remaining Stock: {remaining_stock}"
                )

                if os.path.exists("assets/success.mp3"):

                    st.audio(
                        "assets/success.mp3"
                    )

                refresh_dashboard()

            except ValueError as e:

                st.error(str(e))

            except Exception as e:

                st.error(
                    f"Unable to save usage record: {e}"
                )


# ==================================================
# ADD STOCK
# ==================================================

with right:

    st.subheader("📦 Add New Stock")

    stock_to_add = st.number_input(
        "Number of Rolls Received",
        min_value=1,
        step=1,
        value=1
    )

    if st.button(
        "Add Stock",
        use_container_width=True
    ):

        try:

            new_stock = add_new_stock(
                int(stock_to_add)
            )

            st.success(
                f"✅ {stock_to_add} rolls added successfully."
            )

            refresh_dashboard()

        except Exception as e:

            st.error(
                f"Unable to update stock: {e}"
            )


# ==================================================
# REVERT LAST UPDATE
# ==================================================

st.divider()

st.subheader("↩️ Undo Last Inventory Update")

last_update = get_last_update()

if last_update is None:

    st.info(
        "No inventory updates available to revert."
    )

elif bool(last_update["is_reverted"]):

    st.info(
        "The last inventory update has already been reverted. "
        "A new update is required before using Undo again."
    )

else:

    operation = last_update["operation_type"]

    previous_stock = last_update["previous_stock"]

    updated_stock = last_update["updated_stock"]

    if operation == "USAGE":
        operation_name = "Paper Roll Usage"

    else:
        operation_name = "New Stock Addition"

    st.warning(
        f"""
        **Last Operation:** {operation_name}

        **Previous Stock:** {previous_stock}

        **Updated Stock:** {updated_stock}

        **Stock Difference:** {updated_stock - previous_stock}
        """
    )

    if st.button(
        "↩️ Revert Last Update",
        type="primary",
        use_container_width=True
    ):

        try:

            restored_stock, reverted_operation = (
                revert_last_update()
            )

            st.success(
                f"✅ Last update successfully reverted! "
                f"Current Stock: {restored_stock}"
            )

            refresh_dashboard()

        except Exception as e:

            st.error(
                f"Unable to revert last update: {e}"
            )


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

    # BAR CHART

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

    # PIE CHART

    fig2 = px.pie(
        employee_report,
        names="Employee Name",
        values="Paper Rolls Used",
        hole=0.5
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


# ==================================================
# FOOTER
# ==================================================

st.divider()

st.caption(
    "Wisconsin Paper Roll Inventory Tracker"
)