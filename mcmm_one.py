import pandas as pd
import numpy as np
from datetime import datetime
from datetime import timedelta
from st_aggrid import AgGrid

import streamlit as st
import plotly.express as px

import streamlit.components.v1 as components
from pivottablejs import pivot_ui

st.set_page_config(page_title = "MCMM Dashboard", page_icon = ":bar_chart:", layout = "wide")

master_file = st.file_uploader("Upload the master file (xlsx)")

tdb_file = st.file_uploader("Upload the blotter file (xlsx)")

if master_file is not None and tdb_file is not None:
    
    master = pd.read_excel(master_file, engine='openpyxl')
    
    tdb = pd.read_excel(tdb_file, engine='openpyxl')
    
    st.dataframe(master.head(50))
    
    # ---- HIDE STREAMLIT STYLE ----
    hide_st_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(hide_st_style, unsafe_allow_html=True)
