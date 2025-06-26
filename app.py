import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="WhatsApp Work Hours", layout="centered")

st.title("🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person, per week.")

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

def calculate_work_hours_by_week(df):
    df = df[df['message'].str.contains(r"\b(in|out)\b", na=False)].copy()
    df['week'] = df['timestamp'].dt.isocalendar().week
    df['year'] = df['timestamp'].dt.isocalendar().year
    df['date'] = df['timestamp'].dt.date

    # Get latest 3 weeks
    latest_weeks = df[['year', 'week']].drop_duplicates().sort_values(['year', 'week'], ascending=False).head(3)
    df = df.merge(latest_weeks, on=['year', 'week'])

    results = []
    for (name, week, year), group in df.groupby(['name', 'week', 'year']):
        group = group.sort_values(by='timestamp')
        times = group['timestamp'].tolist()
        messages = group['message'].tolist()
        total = timedelta()
        i = 0
        while i < len(messages) - 1:
            if 'in' in messages[i] and 'out' in messages[i + 1]:
                total += times[i + 1] - times[i]
                i += 2
            else:
                i += 1
        week_start = min(group['date'])
        week_end = max(group['date'])
        results.append({
            'Name': name,
            'Week': f"{week}",
            'Date Range': f"{week_start.strftime('%b %d')} - {week_end.strftime('%b %d')}",
            'Total Hours': round(total.total_seconds() / 3600, 2)
        })
    return pd.DataFrame(results)

if uploaded_file:
    file_text = uploaded_file.read().decode("utf-8")
    df = parse_custom_format(file_text)

    if df.empty or "message" not in df.columns:
        st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
    else:
        hours_df = calculate_work_hours_by_week(df)
        st.success("✅ Successfully processed the chat file!")
        st.dataframe(hours_df)

        csv = hours_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download CSV", data=csv, file_name="weekly_work_hours.csv", mime="text/csv")
