import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="WhatsApp Work Hours", layout="wide")
st.title("🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person.")

uploaded_file = st.file_uploader("📁 Upload WhatsApp .txt file", type=["txt"])

# WhatsApp regex pattern based on your actual file
pattern = re.compile(r"\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2}) (AM|PM)\] (.*?): (.*)")

def extract_messages(text):
    messages = []
    for match in re.finditer(pattern, text):
        date_str = match.group(1)
        time_str = match.group(2)
        am_pm = match.group(3)
        name = match.group(4).strip()
        message = match.group(5).strip()
        try:
            dt = datetime.strptime(f"{date_str}, {time_str} {am_pm}", "%m/%d/%y, %I:%M:%S %p")
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
                "SortDate": in_time.date()
            })

    return pd.DataFrame(result)

def get_last_week_data(daily_df):
    if daily_df.empty:
        return pd.DataFrame(), None, None

    daily_df["SortDate"] = pd.to_datetime(daily_df["SortDate"])
    latest_date = daily_df["SortDate"].max().date()
    week_monday = latest_date - timedelta(days=latest_date.weekday())
    week_sunday = week_monday + timedelta(days=6)

    last_week_df = daily_df[
        daily_df["SortDate"].dt.date.between(week_monday, week_sunday)
    ].copy()

    if last_week_df.empty:
        return pd.DataFrame(), None, None

    total_hours = last_week_df.groupby("Name")["Hours Worked"].sum().reset_index()
    total_hours.rename(columns={"Hours Worked": "Total Hours This Week"}, inplace=True)
    last_week_df = last_week_df.merge(total_hours, on="Name")

    # Collapse Name, Date, Day for neat formatting
    last_week_df["Name"] = last_week_df["Name"].mask(last_week_df["Name"].duplicated())
    last_week_df["Date"] = last_week_df.groupby("Name")["Date"].transform(lambda x: x.mask(x.duplicated()))
    last_week_df["Day"] = last_week_df.groupby(["Name", "Date"])["Day"].transform(lambda x: x.mask(x.duplicated()))
    last_week_df["Total Hours This Week"] = last_week_df.groupby("Name")["Total Hours This Week"].transform(
        lambda x: [x.iloc[0]] + [''] * (len(x) - 1)
    )

    last_week_df.drop(columns=["SortDate"], inplace=True)
    last_week_df.fillna("", inplace=True)

    return last_week_df, week_monday, week_sunday

def to_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='LastWeekData')
    return output.getvalue()

# Streamlit main logic
if uploaded_file is not None:
    try:
        text = uploaded_file.read().decode("utf-8")
        df = extract_messages(text)
        if df.empty:
            st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
        else:
            processed_df = preprocess_data(df)
            daily_df = calculate_hours(processed_df)
            last_week_df, week_monday, week_sunday = get_last_week_data(daily_df)

            if not last_week_df.empty:
                title = f"{week_monday.strftime('%b %d')} - {week_sunday.strftime('%b %d')} {week_sunday.year} WORKDAY TIMESHEET"
                st.subheader(f"📆 {title}")
                st.dataframe(last_week_df, use_container_width=True)

                st.download_button(
                    label="📥 Download Excel",
                    data=to_excel_bytes(last_week_df),
                    file_name="WorkHours_LastWeek.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("No work hours found for the most recent week in the data.")
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
