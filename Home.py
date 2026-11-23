import streamlit as st

st.set_page_config(
    page_title="HealthQ AI",
    page_icon="🩺",
    layout="wide",
)

with st.sidebar:
    st.markdown("## 🩺 HealthQ AI")
    st.caption("Hospital data quality workspace")

pages = {
    "Workspace": [
        st.Page("Data_Upload.py", title="Data Upload", icon="📤"),
        st.Page("pages/1_Overview.py", title="Overview", icon="🏠"),
        st.Page("pages/2_Data_Profile.py", title="Data Profile", icon="🗂️"),
        st.Page("pages/9_Dataset_Catalog.py", title="Dataset Catalogue", icon="🗃️"),
    ],
    "Quality Review": [
        st.Page("pages/3_Issue_Explorer.py", title="Issue Explorer", icon="⚠️"),
        st.Page("pages/4_Risk_Scores.py", title="Risk Scores", icon="📊"),
        st.Page("pages/7_Quality_Trends.py", title="Quality Trends", icon="📈"),
    ],
    "Remediation": [
        st.Page("pages/5_Cleaning_Export.py", title="Cleaning & Export", icon="🧹"),
        st.Page("pages/6_AI_Assistant.py", title="AI Assistant", icon="🤖"),
    ],
    "Reports": [
        st.Page("pages/8_Database_Reports.py", title="Database & Reports", icon="📄"),
    ],
}

current_page = st.navigation(pages, position="sidebar", expanded=True)
current_page.run()


