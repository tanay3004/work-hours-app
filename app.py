import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="WhatsApp Work Hours", layout="centered")
st.title("🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person.")

uploaded_file = st.file_uploader("📂 Upload WhatsApp .txt file", type=["txt"])

# --- Updated Helper Function to parse both formats ---
def parse_custom_format(file_text):
    pattern1 = r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2})\s?(AM|PM)\] (.*?): (.*)"
    pattern2 = r"(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2})\s?(AM|PM) - (.*?): (.*)"

    records = []

    for line in file_text.splitlines():
        m1 = re.match(pattern1, line)
        m2 = re.match(pattern2, line)

        if m1:
            date_str, time_str, ampm, name, message = m1.groups()
            fmt = "%m/%d/%y %I:%M:%S %p"
        elif m2:
            date_str, time_str, ampm, name, message = m2.groups()
            fmt = "%m/%d/%y %I:%M %p"
        else:
            continue

        try:
            timestamp = datetime.strptime(f"{date_str} {time_str} {ampm}", fmt)
            records.append({
                "name": name.strip(),
                "timestamp": timestamp,
                "message": message.strip().lower()
            })
        except ValueError:
            continue

    return pd.DataFrame(records)

# --- Rest of the code remains UNCHANGED ---

def get_week_range(date):
    monday = date - timedelta(days=date.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday, f"{monday.strftime('%b %d')} - {sunday.strftime('%b %d')} {sunday.year}"

def calculate_hours(df):
    df = df[df['message'].str.contains(r'\bin\b|\bout\b|\blunch\b|\bback\b|\breturn\b', na=False)].copy()
    df['date'] = df['timestamp'].dt.date
    df['week'] = df['timestamp'].dt.isocalendar().week
    df['year'] = df['timestamp'].dt.isocalendar().year

    latest_weeks = df[['year', 'week']].drop_duplicates().sort_values(['year', 'week'], ascending=False).head(4)
    df = df.merge(latest_weeks, on=['year', 'week'])

    daily_records = []

    for (name, date), group in df.groupby(['name', 'date']):
        group = group.sort_values(by='timestamp')
        times = group['timestamp'].tolist()
        messages = group['message'].tolist()
        i = 0
        while i < len(messages) - 1:
            msg1 = messages[i]
            msg2 = messages[i + 1]
            if any(x in msg1 for x in ['in', 'back', 'return']) and any(x in msg2 for x in ['out', 'lunch']):
                duration = times[i + 1] - times[i]
                clock_in = times[i].strftime('%I:%M %p')
                clock_out = times[i + 1].strftime('%I:%M %p')
                week_range = get_week_range(times[i])[2]
                daily_records.append({
                    'Name': name,
                    'Date': date.strftime('%b %d, %Y'),
                    'Day': times[i].strftime('%A'),
                    'Week': week_range,
                    'Clock In': clock_in,
                    'Clock Out': clock_out,
                    'Hours Worked': round(duration.total_seconds() / 3600, 2)
                })
                i += 2
            else:
                i += 1

    daily_df = pd.DataFrame(daily_records)

    if not daily_df.empty:
        weekly_summary = (
            daily_df.groupby(['Name', 'Week'])['Hours Worked']
            .sum().reset_index()
            .rename(columns={'Hours Worked': 'Total Hours'})
        )
    else:
        weekly_summary = pd.DataFrame()

    return daily_df, weekly_summary

def get_last_week_data(daily_df):
    if daily_df.empty:
        return pd.DataFrame(), None, None

    daily_df['Date_Parsed'] = pd.to_datetime(daily_df['Date'])
    max_date = daily_df['Date_Parsed'].max().date()
    last_monday = max_date - timedelta(days=max_date.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)

    last_week_df = daily_df[
        daily_df['Date_Parsed'].dt.date.between(last_monday, last_sunday)
    ].copy()

    if not last_week_df.empty:
        total_hours = last_week_df.groupby("Name")["Hours Worked"].sum().reset_index()
        total_hours.rename(columns={"Hours Worked": "Total Hours This Week"}, inplace=True)
        last_week_df = last_week_df.merge(total_hours, on="Name")
        last_week_df["Total Hours This Week"] = last_week_df.groupby("Name")["Total Hours This Week"].transform(
            lambda x: [x.iloc[0]] + [''] * (len(x) - 1)
        )

    return last_week_df, last_monday, last_sunday

# --- Main Execution ---
if uploaded_file:
    file_text = uploaded_file.read().decode("utf-8")
    df = parse_custom_format(file_text)

    if df.empty or "message" not in df.columns:
        st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
    else:
        daily_df, weekly_df = calculate_hours(df)

        if daily_df.empty:
            st.warning("⚠️ No valid IN/OUT pairs found.")
        else:
            st.success("✅ Successfully processed the chat file!")

            st.subheader("🧾 Daily Work Log")
            st.dataframe(daily_df)
            st.download_button("📥 Download Daily Logs",
                               data=daily_df.to_csv(index=False).encode('utf-8'),
                               file_name="Daily_Work_Log.csv",
                               mime="text/csv")

            st.subheader("📊 Weekly Total Hours per Person")
            st.dataframe(weekly_df)
            st.download_button("📥 Download Weekly Summary",
                               data=weekly_df.to_csv(index=False).encode('utf-8'),
                               file_name="Weekly_Total_Hours_Summary.csv",
                               mime="text/csv")

            last_week_df, last_monday, last_sunday = get_last_week_data(daily_df)
            if not last_week_df.empty:
                title = f"{last_monday.strftime('%b %d')} - {last_sunday.strftime('%b %d')} {last_sunday.year} WORKDAY TIMESHEET"
                st.subheader(f"📆 {title}")
                st.dataframe(last_week_df)

                csv_name = title.replace(" ", "_") + ".csv"
                st.download_button(f"📥 Download {title}",
                                   data=last_week_df.to_csv(index=False).encode('utf-8'),
                                   file_name=csv_name,
                                   mime="text/csv")
