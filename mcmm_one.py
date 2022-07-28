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

st.write("wait ah")

if master_file is not None and tdb_file is not None:
    
    master = pd.read_excel(master_file, engine='openpyxl')
    
    tdb = pd.read_excel(tdb_file, engine='openpyxl')
    
    @st.experimental_memo(suppress_st_warning=True)
    def get_database(master, tdb):
        
        tdb["RMDS"] = tdb["DS"] + tdb["RM"]
        tdb["RMDSHWSP"] = tdb["DS"] + tdb["RM"] + tdb["SP"] + tdb["HW"]
        tdb["Non-RMDSHWSP"] = 100 - tdb["RMDSHWSP"]
        tdb["Firm-All"] = 100
        tdb.loc[tdb["Asset Class"] == "Rates", "Firm-Rates"] = 100
        tdb["Firm-Rates"].fillna(0, inplace = True)

        master = pd.merge(master, tdb, on='Trade Name', how='inner')
        Trader_DB = master[["Trade Name", "Theme_y", "Asset Class_y", "Trade Category", "RiskCountry_y"]].copy()
        Trader_DB.rename(columns = {"Theme_y": "Theme", "Asset Class_y": "Asset Class", "RiskCountry_y": "RiskCountry"}, inplace =True)
        
        trader_start_name = master.columns.get_loc("DS") 
        trader_names = master.iloc[:,trader_start_name:]
        
        idt = master.columns.get_loc(pd.Timestamp('2021-01-08')) 
        pl = master.iloc[:,5:idt+1]
        
        Trader_DB = pd.concat([Trader_DB, trader_names/100], axis = 1)
        Trader_DB = pd.melt(Trader_DB, id_vars =list(Trader_DB.columns[:5]), value_vars =list(Trader_DB.columns[5:]),
                            var_name= "Trader" , value_name= "weights")
        
        Trader_DB = pd.merge(Trader_DB, pl, on='Trade Name', how='left')
        
        Trader_DB = pd.melt(Trader_DB, id_vars =list(Trader_DB.columns[:7]), value_vars =list(Trader_DB.columns[7:]),
                            var_name= "Dates" , value_name= "PL")
        
        Trader_DB = Trader_DB[(Trader_DB[['weights']] != 0).all(axis=1)]
        Trader_DB["Daily-pl"] = Trader_DB["weights"]*Trader_DB["PL"]
        Trader_DB.drop(['weights', 'PL'], axis=1, inplace = True)
        
        Rates = ["DS", "RM", "SP", "HW", "RMDS", "RMDSSPHW"]
        FX = ["SK", "YZ", "HC", "SW"]
        Credit = ["RR", "HL", "ND"]
        Others = ["TL", "AS", "TR", "DXS", "Firm-Rates", "Non-RMDSHWSP", "Firm-All"]
        
        Trader_DB.loc[Trader_DB["Trader"].isin(Rates), "Desk"] = "Rates"
        Trader_DB.loc[Trader_DB["Trader"].isin(FX), "Desk"] = "FX"
        Trader_DB.loc[Trader_DB["Trader"].isin(Credit), "Desk"] = "Credit"
        Trader_DB.loc[Trader_DB["Trader"].isin(Others), "Desk"] = "Others"
        
        Trader_DB.sort_values(by=['Desk'], inplace = True)
        
        return Trader_DB
        
    Trader_DB = get_database(master, tdb)
    st.dataframe(Trader_DB.head(50))
    
    # ---- HIDE STREAMLIT STYLE ----
    hide_st_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(hide_st_style, unsafe_allow_html=True)
