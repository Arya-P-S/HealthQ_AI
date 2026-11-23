import pandas as pd
import streamlit as st

st.title("Data Profile")

data = st.session_state.get("healthq_data")

if data is None:
    st.info("Open the main app and load a CSV first.")
else:
    profile = pd.DataFrame({
        "Column": data.columns,
        "Data type": [str(data[column].dtype) for column in data.columns],
        "Missing values": [
            int(data[column].isna().sum()) for column in data.columns
        ],
        "Unique values": [
            int(data[column].nunique()) for column in data.columns
        ],
    })

    st.dataframe(profile, use_container_width=True, hide_index=True)