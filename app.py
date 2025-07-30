import streamlit as st
import pandas as pd
import re
from datetime import datetime
from io import StringIO

st.set_page_config(page_title="WhatsApp Work Hours Calculator", layout="wide")

st.title("🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person.")

uploaded_file = st.file_uploader("📂 Upload WhatsApp .txt file", type=["txt"])

# --------------------------
# ✅ Flexible Regex Parser
# --------------------------
def parse_messages(text):
    pattern1 = r'\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}(?::\d{2})? (?:AM|PM))\] (.*?): (.*)'
    pattern2 = r'(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}(?::\d{2})? (?:AM|PM)) - (.*?): (.*)'

    messages = []
    for match in re.findall(pattern1, text):
        messages.append({"Date": match[0], "Time": match[1], "Name": match[2].strip(), "Message": match[3].strip()})
    for match in re.findall(pattern2, text):
        messages.append({"Date": match[0], "Time": match[1], "Name": match[2].strip(), "Message": match[3].strip()})

    return pd.DataFrame(messages)

# --------------------------
# ⏱ Clock-In/Clock-Out Logic
# --------------------------
def extract_hours(df):
    df["DateTime"] = df["Date"] + " " + df["Time"]
    df["DateTime"] = pd.to_datetime(df["DateTime"], errors="coerce")

    # Filter messages like "Tanay in" or "Tanay out"
    df = df[df["Message"].str.contains("in|out", case=False, na=False)]

    records = []
    for name, group in df.groupby("Name"):
        group = group.sort_values("DateTime")
        for date, day_df in group.groupby(group["DateTime"].dt.date):
            day_msgs = day_df["Message"].str.lower().tolist()
            day_times = day_df["DateTime"].tolist()

            # Handle multiple ins and outs per day
            in_times = [t for m, t in zip(day_msgs, day_times) if "in" in m]
            out_times = [t for m, t in zip(day_msgs, day_times) if "out" in m]

            for i in range(min(len(in_times), len(out_times))):
                clock_in = in_times[i]
                clock_out = out_times[i]
                hours = round((clock_out - clock_in).total_seconds() / 3600, 2)
                records.append({
                    "Name": name,
                    "Date": clock_in.strftime("%b %d, %Y"),
                    "Day": clock_in.strftime("%A"),
                    "Clock In": clock_in.strftime("%I:%M %p"),
                    "Clock Out": clock_out.strftime("%I:%M %p"),
                    "Hours Worked": hours
                })

    result = pd.DataFrame(records)

    # ➕ Total hours per person for the week
    if not result.empty:
        weekly = result.groupby("Name")["Hours Worked"].sum().round(2).reset_index()
        weekly.columns = ["Name", "Total Hours This Week"]
        result = result.merge(weekly, on="Name", how="left")

    return result

# --------------------------
# 📦 Handle Upload
# --------------------------
if uploaded_file is not None:
    stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
    raw_text = stringio.read()

    try:
        parsed_df = parse_messages(raw_text)
        if parsed_df.empty:
            st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
        else:
            hours_df = extract_hours(parsed_df)

            # Replace NaN with blank
            hours_df = hours_df.fillna("")

            # Only show day once per person per date
            hours_df["Day"] = hours_df.groupby(["Name", "Date"])["Day"].transform(
                lambda x: [x.iloc[0]] + [""] * (len(x) - 1)
            )

            # Format 'Total Hours This Week' to 2 decimals, show only once per Name
            hours_df["Total Hours This Week"] = hours_df.groupby("Name")["Total Hours This Week"]\
                .transform(lambda x: [f"{x.iloc[0]:.2f}"] + [""] * (len(x) - 1))

            st.success("✅ File parsed successfully!")
            st.dataframe(hours_df, use_container_width=True)
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
