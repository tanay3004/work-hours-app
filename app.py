import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime, timedelta

# --- Title and UI ---
st.set_page_config(page_title="WhatsApp Work Hours Calculator", layout="centered")
st.markdown("## 🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person.")
st.markdown("📁 **Upload WhatsApp .txt file**")

# --- File Upload ---
uploaded_file = st.file_uploader("Drag and drop file here", type="txt")

# --- Regex Pattern ---
message_pattern = re.compile(r"^\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2} (?:AM|PM))\] (.*?): (.*)")

def parse_messages(file):
    content = file.read().decode('utf-8', errors='ignore')
    messages = []
    for line in content.split('\n'):
        match = message_pattern.match(line.strip())
        if match:
            date_str, time_str, name, message = match.groups()
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%y %I:%M:%S %p")
            except:
                try:
                    dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%Y %I:%M:%S %p")
                except:
                    continue
            messages.append({"DateTime": dt, "Name": name.strip(), "Message": message.strip()})
    return pd.DataFrame(messages)

def extract_shifts(df):
    shift_data = []
    for name, group in df.groupby("Name"):
        group = group.sort_values("DateTime")
        day_groups = group.groupby(group["DateTime"].dt.date)
        for date, daily_msgs in day_groups:
            ins = daily_msgs[daily_msgs["Message"].str.lower().str.contains("in")]
            outs = daily_msgs[daily_msgs["Message"].str.lower().str.contains("out")]
            for in_msg, out_msg in zip(ins["DateTime"], outs["DateTime"]):
                shift_data.append({
                    "Name": name,
                    "Date": date.strftime("%b %d, %Y"),
                    "Day": in_msg.strftime("%A"),
                    "Clock In": in_msg.strftime("%I:%M %p"),
                    "Clock Out": out_msg.strftime("%I:%M %p"),
                    "Hours Worked": round((out_msg - in_msg).total_seconds() / 3600, 2)
                })
    return pd.DataFrame(shift_data)

def calculate_weekly_hours(df):
    df["DateObj"] = pd.to_datetime(df["Date"])
    df["WeekStart"] = df["DateObj"] - pd.to_timedelta(df["DateObj"].dt.weekday, unit='d')
    weekly_hours = df.groupby(["Name", "WeekStart"])["Hours Worked"].sum().reset_index()
    weekly_hours.rename(columns={"Hours Worked": "Total Hours This Week"}, inplace=True)
    return df.merge(weekly_hours, on=["Name", "WeekStart"], how="left")

def format_for_display(df):
    df["Name"] = df["Name"].astype(str)
    df["Date_display"] = df["Date"]
    df["Day_display"] = df["Day"]
    df.loc[:, "Date_display"] = df.groupby(["Name", "Date_display"])["Date_display"].transform(
        lambda x: [""] * (len(x) - 1) + [x.iloc[-1]]
    )
    df.loc[:, "Day_display"] = df.groupby(["Name", "Day_display"])["Day_display"].transform(
        lambda x: [""] * (len(x) - 1) + [x.iloc[-1]]
    )
    df.drop(columns=["DateObj", "WeekStart"], inplace=True, errors='ignore')
    df = df[["Name", "Date_display", "Day_display", "Clock In", "Clock Out", "Hours Worked", "Total Hours This Week"]]
    df.fillna("", inplace=True)
    return df.rename(columns={"Date_display": "Date", "Day_display": "Day"})

# --- Process File ---
if uploaded_file:
    try:
        df = parse_messages(uploaded_file)
        if df.empty:
            st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
        else:
            shift_df = extract_shifts(df)
            shift_df = calculate_weekly_hours(shift_df)
            final_df = format_for_display(shift_df)
            st.success("✅ Successfully processed the file!")
            st.dataframe(final_df, use_container_width=True)
    except Exception as e:
        st.error(f"⚠️ An unexpected error occurred: {str(e)}")
