import os
import pandas as pd
import streamlit as st

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")


def get_gsheet_client():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_PATH, scope)
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID)


def load_all_data():
    sh = get_gsheet_client()
    dfs = []
    for ws in sh.worksheets():
        values = ws.get_all_values()
        if not values:
            continue
        df = pd.DataFrame(values[1:], columns=values[0])
        df["Sheet"] = ws.title
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)


def main():
    st.title("📊 Job Applications Dashboard")

    df = load_all_data()
    if df.empty:
        st.warning("No data loaded from Google Sheets.")
        return

    st.write(f"Total rows loaded: {len(df)}")

    # Standardize column names
    df.columns = [c.strip() for c in df.columns]

    # Metrics by Decision
    if "Decision" in df.columns:
        status_counts = df["Decision"].value_counts().reset_index()
        status_counts.columns = ["Decision", "Count"]
        st.subheader("Applications by Decision")
        st.bar_chart(status_counts.set_index("Decision")["Count"])

    # Metrics by Platform (if present)
    if "Platform" in df.columns:
        platform_counts = df["Platform"].value_counts().reset_index()
        platform_counts.columns = ["Platform", "Count"]
        st.subheader("Applications by Platform")
        st.bar_chart(platform_counts.set_index("Platform")["Count"])

    st.subheader("Raw Data")
    st.dataframe(df)


if __name__ == "__main__":
    main()
