import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime, timedelta

st.set_page_config(page_title="WhatsApp Work Hours Calculator", layout="wide")

st.markdown("## 🕒 WhatsApp Work Hours Calculator")
st.markdown(
    "Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person."
)

# File Upload
uploaded_file = st.file_uploader("📁 Upload WhatsApp .txt file", type=["txt"])

# Correct regex pattern for WhatsApp messages like: [7/23/25, 8:33:10 AM] Name: Message
pattern = re.compile(
    r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2} [APMapm]{2})\] (.*?): (.*)"
)
time_format = "%m/%d/%y, %I:%M:%S %p"

def extract_messages(text):
    messages = []
    for match in re.finditer(pattern, text):
        date_str = match.group(1)
        time_str = match.group(2)
        name = match.group(3).strip()
        message = match.group(4).strip()
        try:
            dt = datetime.strptime(f"{date_str}, {time_str}", time_format)
            messages.append((dt, name, message))
        except Exception:
            continue
    return pd.DataFrame(messages, columns=["DateTime", "Name", "Message"])

def preprocess_data(df):
    df["Date"] = df["DateTime"].dt.date
    df["Time"] = df["DateTime"].dt.time
    df["Action"] = df["Message"].apply(lambda x: "Clock In" if "in" in x.lower() else ("Clock Out" if "out" in x.lower() else "Other"))
    df = df[df["Action"].isin(["Clock In", "Clock Out"])]
    return df.sort_values(by=["Name", "DateTime"])

def calculate_hours(df):
    result = []
    for (name, date), group in df.groupby(["Name", "Date"]):
        group = group.sort_values("DateTime")
        clock_pairs = []
        temp = []

        for _, row in group.iterrows():
            if row["Action"] == "Clock In":
                temp = [row["DateTime"]]
            elif row["Action"] == "Clock Out" and temp:
                temp.append(row["DateTime"])
                if len(temp) == 2:
                    clock_pairs.append(temp)
                temp = []

        for in_time, out_time in clock_pairs:
            hours = round((out_time - in_time).total_seconds() / 3600, 2)
            result.append({
                "Name": name,
                "Date": in_time.date().strftime("%b %d, %Y"),
                "Day": in_time.strftime("%A"),
                "Clock In": in_time.strftime("%I:%M %p"),
                "Clock Out": out_time.strftime("%I:%M %p"),
                "Hours Worked": hours,
                "Date_Parsed": in_time.date()
            })

    return pd.DataFrame(result)

def get_last_week_data(daily_df):
    if daily_df.empty:
        return pd.DataFrame(), None, None

    temp_df = daily_df.copy()
    latest_date = temp_df['Date_Parsed'].max()
    week_monday = latest_date - timedelta(days=latest_date.weekday())
    week_sunday = week_monday + timedelta(days=6)

    week_df = temp_df[
        temp_df["Date_Parsed"].between(week_monday, week_sunday)
    ].copy()

    if not week_df.empty:
        # Add total hours this week
        totals = week_df.groupby("Name")["Hours Worked"].sum().reset_index()
        totals.rename(columns={"Hours Worked": "Total Hours This Week"}, inplace=True)
        week_df = week_df.merge(totals, on="Name")

        # Hide repeated Name, Date, Day
        week_df["Name"] = week_df["Name"].mask(week_df["Name"].duplicated())
        week_df["Date"] = week_df.groupby("Name")["Date"].transform(lambda x: x.mask(x.duplicated()))
        week_df["Day"] = week_df.groupby(["Name", "Date"])["Day"].transform(lambda x: x.mask(x.duplicated()))
        week_df["Total Hours This Week"] = week_df.groupby("Name")["Total Hours This Week"].transform(
            lambda x: [x.iloc[0]] + [''] * (len(x) - 1)
        )

        week_df = week_df.drop(columns=["Date_Parsed", "Week"], errors='ignore')
        week_df = week_df.fillna("")

    return week_df, week_monday, week_sunday

def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Work Hours')
    return output.getvalue()

# Main logic
if uploaded_file is not None:
    try:
        try:
            text = uploaded_file.read().decode("utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            text = uploaded_file.read().decode("utf-16")

        df = extract_messages(text)

        if df.empty:
            st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
        else:
            processed_df = preprocess_data(df)
            daily_df = calculate_hours(processed_df)
            final_df, monday, sunday = get_last_week_data(daily_df)

            if not final_df.empty:
                st.markdown(f"### 📅 Week Period WORKDAY TIMESHEET ({monday.strftime('%b %d')} - {sunday.strftime('%b %d')})")
                st.dataframe(final_df, use_container_width=True)

                st.download_button(
                    label="📥 Download Excel",
                    data=to_excel_bytes(final_df),
                    file_name="WorkHours_LastWeek.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("⚠️ No work hours found for the most recent week.")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
