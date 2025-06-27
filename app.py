import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="WhatsApp Work Hours", layout="wide")
st.title("🕒 WhatsApp Weekly Clock In/Out Tracker")
st.markdown("Upload your exported WhatsApp group chat (.txt) to view individual clock in/out times and total hours per week (Monday to Sunday).")

uploaded_file = st.file_uploader("📂 Upload WhatsApp .txt file", type=["txt"])

def parse_custom_format(file_text):
    pattern = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2})\u202f([APM]+)\] (.*?): (.*)"
    records = []

    for line in file_text.splitlines():
        match = re.match(pattern, line)
        if match:
            date_str, time_str, ampm, name, message = match.groups()
            timestamp_str = f"{date_str} {time_str} {ampm}"
            try:
                timestamp = datetime.strptime(timestamp_str, "%m/%d/%y %I:%M:%S %p")
                records.append({
                    "name": name.strip(),
                    "timestamp": timestamp,
                    "message": message.strip().lower()
                })
            except ValueError:
                continue
    return pd.DataFrame(records)

def generate_clock_logs(df):
    df = df[df['message'].str.contains(r'\b(in|out)\b')].copy()
    df['Week Start'] = df['timestamp'].dt.to_period('W-MON').apply(lambda r: r.start_time)
    df['Week End'] = df['Week Start'] + timedelta(days=6)
    
    clock_logs = []

    for (name, week_start), group in df.groupby(['name', 'Week Start']):
        group = group.sort_values(by='timestamp')
        times = group['timestamp'].tolist()
        messages = group['message'].tolist()
        i = 0
        while i < len(messages) - 1:
            if 'in' in messages[i] and 'out' in messages[i + 1]:
                clock_logs.append({
                    'Name': name,
                    'Clock In': times[i],
                    'Clock Out': times[i + 1],
                    'Duration (hrs)': round((times[i + 1] - times[i]).total_seconds() / 3600, 2),
                    'Week Start': week_start,
                    'Week Range': f"{week_start.strftime('%b %d')} - {(week_start + timedelta(days=6)).strftime('%b %d')}"
                })
                i += 2
            else:
                i += 1
    return pd.DataFrame(clock_logs)

if uploaded_file:
    file_text = uploaded_file.read().decode("utf-8")
    df = parse_custom_format(file_text)

    if df.empty or "message" not in df.columns:
        st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
    else:
        log_df = generate_clock_logs(df)

        if log_df.empty:
            st.warning("No valid clock in/out pairs found.")
        else:
            st.success("✅ Successfully extracted clock in/out logs!")

            # Show full log table
            st.subheader("📋 Weekly Clock In/Out Logs")
            st.dataframe(log_df[['Name', 'Week Range', 'Clock In', 'Clock Out', 'Duration (hrs)']])

            # Group by week and person for summary
            summary_df = log_df.groupby(['Name', 'Week Range'])['Duration (hrs)'].sum().reset_index()
            summary_df = summary_df.rename(columns={'Duration (hrs)': 'Total Hours'})

            st.subheader("📊 Weekly Total Hours Per Person")
            st.dataframe(summary_df)

            # Download option
            csv = log_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Clock Log CSV", data=csv, file_name="clock_logs.csv", mime="text/csv")

            summary_csv = summary_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Weekly Summary CSV", data=summary_csv, file_name="weekly_summary.csv", mime="text/csv")
