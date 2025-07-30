import re
import pandas as pd
from io import BytesIO
import base64
import streamlit as st

# Streamlit Page Config
st.set_page_config(page_title="WhatsApp Work Hours Calculator", layout="wide")
st.title("🕒 WhatsApp Work Hours Calculator")
st.markdown("Upload your exported WhatsApp group chat (.txt) to calculate total hours worked per person.")
st.markdown("### 📁 Upload WhatsApp .txt file")

# File uploader
uploaded_file = st.file_uploader("Drag and drop file here", type="txt")

# Parse chat messages
def parse_messages(text):
    pattern = r'\[(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2}:\d{2} (?:AM|PM))\] (.*?): (.*)'
    matches = re.findall(pattern, text)
    messages = []
    for date, time, name, message in matches:
        messages.append({"Date": date, "Time": time, "Name": name.strip(), "Message": message.strip()})
    return pd.DataFrame(messages)

# Label as Clock In / Clock Out
def label_clock_direction(msg):
    msg = msg.lower()
    if "in" in msg and not any(word in msg for word in ["login", "join", "joining", "informed", "not in", "log in late"]):
        return "Clock In"
    elif any(x in msg for x in ["out", "done", "bye"]) and "without" not in msg:
        return "Clock Out"
    return None

# Generate downloadable Excel
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Work Hours')
    return output.getvalue()

# Main Logic
if uploaded_file:
    text = uploaded_file.read().decode("utf-8")
    df = parse_messages(text)

    if df.empty:
        st.error("❌ Format issue: Could not extract messages. Please upload a valid WhatsApp group .txt file.")
    else:
        df["Timestamp"] = pd.to_datetime(df["Date"] + " " + df["Time"])
        df["Direction"] = df["Message"].apply(label_clock_direction)
        df = df[df["Direction"].notnull()].copy()
        df.sort_values(["Name", "Timestamp"], inplace=True)

        # Pair Clock In and Clock Out
        work_entries = []
        for name, group in df.groupby("Name"):
            group = group.reset_index(drop=True)
            i = 0
            while i < len(group) - 1:
                if group.loc[i, "Direction"] == "Clock In" and group.loc[i + 1, "Direction"] == "Clock Out":
                    clock_in = group.loc[i, "Timestamp"]
                    clock_out = group.loc[i + 1, "Timestamp"]
                    hours_worked = round((clock_out - clock_in).total_seconds() / 3600, 2)
                    work_entries.append({
                        "Name": name,
                        "Date": clock_in.date(),
                        "Day": clock_in.strftime("%A"),
                        "Clock In": clock_in.strftime("%I:%M %p"),
                        "Clock Out": clock_out.strftime("%I:%M %p"),
                        "Hours Worked": hours_worked
                    })
                    i += 2
                else:
                    i += 1

        final_df = pd.DataFrame(work_entries)

        # Add total weekly hours
        final_df["Total Hours This Week"] = final_df.groupby("Name")["Hours Worked"].transform("sum")

        # Blank repeating values for readability
        final_df["Name"] = final_df.groupby("Name")["Name"].transform(lambda x: [x.iloc[0]] + [""] * (len(x) - 1))
        final_df["Date"] = final_df.groupby(["Name", "Date"])["Date"].transform(lambda x: [x.iloc[0]] + [""] * (len(x) - 1))
        final_df["Day"] = final_df.groupby(["Name", "Day"])["Day"].transform(lambda x: [x.iloc[0]] + [""] * (len(x) - 1))
        final_df["Total Hours This Week"] = final_df.groupby("Name")["Total Hours This Week"].transform(lambda x: [x.iloc[0]] + [""] * (len(x) - 1))

        # Replace any None with blank string
        final_df = final_df.fillna("")

        st.success("✅ Messages processed successfully.")
        st.dataframe(final_df, use_container_width=True)

        # Download link
        excel_data = to_excel(final_df)
        b64 = base64.b64encode(excel_data).decode()
        st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="work_hours.xlsx">📥 Download Excel File</a>', unsafe_allow_html=True)
else:
    st.info("📂 Please upload a WhatsApp chat .txt file exported from a group to begin.")
