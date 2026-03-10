# mediflow.py
# MediFlow - NGO Medicine Redistribution Tracker
# READ THIS: The app has 3 parts: data storage (CSV), UI (Streamlit), logic (Python functions)
# Understanding these 3 layers = you can answer ANY interview question about this

import streamlit as st
import pandas as pd
import os
from datetime import datetime, date

# ── CONFIG ────────────────────────────────────────────────────────────────────
CSV_FILE = "medicines.csv"
COLUMNS  = ["Medicine Name", "Quantity", "Expiry Date", "Donor NGO",
            "Status", "Date Added"]

# WHY CSV? Interviewer Q: "Why not a database?"
# Answer: "For MVP with NGOs in low-connectivity areas, a flat CSV is zero-dependency,
# portable, and can be opened by volunteers in Excel. SQLite would be the next step."

# ── DATA LAYER ────────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    """Load existing records or create empty dataframe."""
    if os.path.exists(CSV_FILE):
        return pd.read_csv(CSV_FILE, parse_dates=["Expiry Date", "Date Added"])
    return pd.DataFrame(columns=COLUMNS)

def save_data(df: pd.DataFrame) -> None:
    """Persist dataframe to CSV atomically."""
    df.to_csv(CSV_FILE, index=False)

def add_medicine(name: str, qty: int, expiry: date,
                 donor: str, df: pd.DataFrame) -> pd.DataFrame:
    """Append a new medicine record and return updated dataframe."""
    new_row = {
        "Medicine Name": name.strip().title(),
        "Quantity":      qty,
        "Expiry Date":   expiry,
        "Donor NGO":     donor.strip().title(),
        "Status":        "Available",
        "Date Added":    datetime.today().date()
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def flag_expiring(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """Return medicines expiring within `days` days."""
    if df.empty:
        return df
    today     = pd.Timestamp.today().normalize()
    threshold = today + pd.Timedelta(days=days)
    expiry_col = pd.to_datetime(df["Expiry Date"], format='mixed')
    return df[(expiry_col >= today) & (expiry_col <= threshold)]

# ── UI LAYER ──────────────────────────────────────────────────────────────────
st.set_page_config(page_title="MediFlow", page_icon="💊", layout="wide")

st.markdown("""
    <h1 style='color:#1a6b3c; font-family:sans-serif;'>
        💊 MediFlow — NGO Medicine Redistribution Tracker
    </h1>
    <p style='color:gray;'>
        Reducing medicine wastage. Maximising social impact.
    </p>
    <hr/>
""", unsafe_allow_html=True)

# Session state = keeps data in memory during a user session
# WHY: Streamlit reruns the whole script on every interaction
if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df

# ── SIDEBAR: ADD MEDICINE ─────────────────────────────────────────────────────
st.sidebar.header("➕ Add Medicine Stock")

with st.sidebar:
    med_name = st.text_input("Medicine Name", placeholder="e.g. Paracetamol 500mg")
    quantity = st.number_input("Quantity (units)", min_value=1, value=100, step=10)
    expiry   = st.date_input("Expiry Date", min_value=date.today())
    donor    = st.text_input("Donor NGO Name", placeholder="e.g. Asha Foundation")

    if st.button("✅ Add to Inventory", use_container_width=True):
        if med_name and donor:
            st.session_state.df = add_medicine(
                med_name, quantity, expiry, donor, st.session_state.df
            )
            save_data(st.session_state.df)
            st.success(f"Added {med_name} successfully!")
            df = st.session_state.df
        else:
            st.error("Medicine name and Donor NGO are required.")

# ── MAIN PANEL ────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

total     = len(df)
available = len(df[df["Status"] == "Available"]) if not df.empty else 0
expiring  = len(flag_expiring(df))

col1.metric("Total Stock Entries", total)
col2.metric("Available",           available)
col3.metric("⚠️ Expiring in 30d",  expiring,
            delta=f"-{expiring} urgent" if expiring else None,
            delta_color="inverse")

st.markdown("---")

# ── SEARCH BAR ────────────────────────────────────────────────────────────────
st.subheader("🔍 Search Inventory")

search_query = st.text_input("Search by medicine name or NGO",
                              placeholder="Type to filter...")

if not df.empty:
    display_df = df.copy()

    # Filter by search query across relevant columns
    if search_query:
        mask = (
            display_df["Medicine Name"].str.contains(search_query, case=False, na=False) |
            display_df["Donor NGO"].str.contains(search_query, case=False, na=False)
        )
        display_df = display_df[mask]

    # Status filter
    status_filter = st.selectbox("Filter by Status",
                                  ["All", "Available", "Redistributed", "Expired"])
    if status_filter != "All":
        display_df = display_df[display_df["Status"] == status_filter]

    # Colour-code expiry: red if < 30 days
    def highlight_expiry(row):
        today     = pd.Timestamp.today().normalize()
        exp       = pd.to_datetime(row["Expiry Date"])
        days_left = (exp - today).days
        if days_left <= 30:
            return ["background-color: #8b0000; color: white"] * len(row)
        return ["background-color: #1a472a; color: white"] * len(row)

    display_copy = display_df.copy()
    display_copy["Expiry Date"] = pd.to_datetime(display_copy["Expiry Date"], format='mixed').dt.strftime("%Y-%m-%d")
    display_copy["Date Added"] = pd.to_datetime(display_copy["Date Added"], format='mixed').dt.strftime("%Y-%m-%d")
    st.dataframe(
        display_copy.style.apply(highlight_expiry, axis=1),
        use_container_width=True,
        height=350
    )

    # ── STATUS UPDATE ─────────────────────────────────────────────────────────
    st.subheader("🔄 Update Medicine Status")
    if not display_df.empty:
        idx        = st.selectbox("Select entry to update",
                                   display_df.index,
                                   format_func=lambda i:
                                       f"{df.at[i,'Medicine Name']} — {df.at[i,'Donor NGO']}")
        new_status = st.radio("New Status",
                               ["Available", "Redistributed", "Expired"],
                               horizontal=True)

        if st.button("Update Status"):
            st.session_state.df.at[idx, "Status"] = new_status
            save_data(st.session_state.df)
            st.success("Status updated!")
            st.rerun()

    # ── EXPORT ───────────────────────────────────────────────────────────────
    st.markdown("---")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label     = "⬇️ Export Full Inventory as CSV",
        data      = csv_bytes,
        file_name = "mediflow_inventory.csv",
        mime      = "text/csv"
    )

else:
    st.info("No medicines in inventory yet. Add some using the sidebar!")

# ── EXPIRY ALERT PANEL ───────────────────────────────────────────────────────
if expiring > 0:
    st.markdown("---")
    st.subheader("⚠️ Medicines Expiring Within 30 Days")
    st.dataframe(flag_expiring(df), use_container_width=True)