import pandas as pd
import numpy as np
from annotated_text import annotated_text
import re 
import datetime
from datetime import timedelta
from pandas.tseries.offsets import MonthEnd

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

import streamlit.components.v1 as components
import pivottablejs
from functools import reduce

import time
import shutil
import glob
import os

st.set_page_config(page_title = "MCMM Dashboard", page_icon = ":bar_chart:", layout = "wide")

if "dates_ran" not in st.session_state:
    st.session_state["dates_ran"] = False

today = datetime.date.today()
    
if st.session_state["dates_ran"] and st.session_state["dates_ran"] != today:
    for key in st.session_state.keys():
        del st.session_state[key]
    
if "load_state" not in st.session_state:
    st.session_state["load_state"] = False
    
if "cut" not in st.session_state:
    st.session_state.cut = False
    
tdb = None
master = None

mcmm_pnl_path = r'Z:\Business\Personnel\Saswat\MCMM Recon\Whole Portfolio' 
tdb_path = r'Z:\Business\Portfolio\Mapping Tables\TradeDB_MCMM.xlsx'

def rerun():
    
    for key in st.session_state.keys():
        del st.session_state[key]
        
with st.sidebar.container():
    
    upload_tdb = st.sidebar.checkbox('Self-Upload Trade Blotter File', on_change=rerun)
    
@st.experimental_memo(suppress_st_warning=True)
def get_files(tdb, omega_map):    
    
    theme_map_ = tdb.loc[:, ['Asset Class', 'Theme', 'RiskCountry', 'Trade Name']]
    
    omega_map.loc[:,'Unnamed: 2'] = "RV_" + omega_map.iloc[:,0].astype(str) 
    omega_map = omega_map.rename( columns = {'Unnamed: 2': 'MICRO STRATEGY'})
    omega_map_ = omega_map .iloc[:,[2,1]]
    
    def pnl_pivot_ytd(filename_prefix , master_dir , startdate = None , enddate = '03/16/2022', start_date_auto = True): 
        
        #  startdate = '11/30/2021'

        master = pd.read_excel(master_dir, engine='openpyxl')
        master = master.set_index('index')
        
        if start_date_auto == True: 
            if startdate is not None: print('initial startdate input will be overriden')
            startdate_obj = max([i for i in master.columns.tolist() if isinstance(i, datetime.datetime)])       
            
        else: 
            startdate_obj = datetime.datetime.strptime(startdate, '%m/%d/%Y')
    
        datestr = str("{:02d}".format(startdate_obj.month))+str("{:02d}".format(startdate_obj.day))+str(startdate_obj.year-2000)
    
        filename = filename_prefix + datestr + '.xlsx'
        df_ = pd.read_excel(filename, engine='openpyxl')
        
        df_.columns = df_.iloc[0,:]
        df_ = df_.iloc[1:,[1,11]] # ,9]]
        # df_ = df_.rename( columns = {'DTD TOTAL PNL': startdate_obj }) 
        df_['Date'] =  startdate_obj
        
        df_ = df_.groupby(['MICRO STRATEGY','Date'], as_index = False).sum()
        df_ = df_.loc[df_['MICRO STRATEGY'] != 0, :]
        df_  = df_ .loc [ : , ['MICRO STRATEGY', 'YTD TOTAL PNL', "Date"]] 
        df = df_  
        df_first = df.copy()
        date_obj = startdate_obj
    
        enddate_obj = datetime.datetime.strptime(enddate, '%m/%d/%Y')
        enddatestr = str("{:02d}".format(enddate_obj.month))+str("{:02d}".format(enddate_obj.day))+str(enddate_obj.year-2000)
        
        # loop for future dates ... 
        while datestr != enddatestr:
            
            #enddate = '11/30/2021'; datestr = enddatestr
        
            date_obj = date_obj + datetime.timedelta(days=1)
            datestr = str("{:02d}".format(date_obj .month))+str("{:02d}".format(date_obj .day))+str(date_obj .year-2000)
        
            filename = filename_prefix + datestr + '.xlsx'
    
            try:
                df_ = pd.read_excel(filename, engine='openpyxl')
            except: 
                print('date not found: ' + datestr)
                continue
        
            df_.columns = df_.iloc[0,:]
            df_ = df_.iloc[1:,[1,11]] # ,9]]
            df_['Date'] =  date_obj
            
            df_ = df_.groupby(['MICRO STRATEGY','Date'], as_index = False).sum()
            df_ = df_.loc[df_['MICRO STRATEGY'] != 0, :]
            df_  = df_ .loc [ : , ['MICRO STRATEGY', 'YTD TOTAL PNL', "Date"]]
        
            df = pd.concat( (df, df_) )
        
        df['YTD TOTAL PNL'] = df['YTD TOTAL PNL'].astype(float)
        df_pivot_ = pd.pivot_table ( df , index = ['MICRO STRATEGY'], values = 'YTD TOTAL PNL', columns = ['Date'])
    
        # create daily numbers 
        
        df_pivot_ytd = df_pivot_.fillna(0)
        df_pivot_ = df_pivot_ytd - df_pivot_ytd.shift(1, axis = 1)
        
        # create genesis YTD num 
        
        df_first_ = df_first.iloc[:,:2]
        df_first_ = df_first_.rename(columns = {'YTD TOTAL PNL': startdate_obj} )
        
        df_first_  = df_first_ .dropna()        
        df_first_ = df_first_.set_index( df_first_['MICRO STRATEGY'])
    
        df_first_ = df_first_ .iloc[:, 1:]
    
        # replace first date column with the YTD num 
        df_pivot_  = pd.merge(df_pivot_ .iloc[:,  1:] , df_first_ , on = 'MICRO STRATEGY' , how ='outer' )
        df_pivot_  = df_pivot_ .loc[:, df_pivot_.columns.sort_values(ascending = False)  ]
        
        # clean out all nas / 0s 
        df_pivot_ = df_pivot_ .fillna(0)
        df_pivot_ = df_pivot_.loc[(df_pivot_!=0).any(axis=1)]
    
        # map the omega IDs
        df_pivot_final = pd.merge(omega_map_, df_pivot_, on = 'MICRO STRATEGY', how = 'inner') # intersection with trades available on omega
    
        # map the themes etc from tdb
        df_pivot_final = pd.merge(theme_map_, df_pivot_final, on = 'Trade Name', how = 'inner') # intersection with trades available on omega
    
        # swap tradename / microstrategy columns 
        col_list = df_pivot_final.columns.tolist()
        col_list [3] , col_list [4] = col_list [4] , col_list [3] 
        df_pivot_final = df_pivot_final .loc[:, col_list ]
       
        ###MERGING ONTO MASTER###
        
        # columns to merge on (new df to master)
        merge_cols = master.columns.tolist()[:5]
        
        # trim off the first date since it gives the YTD of trade on that date instead of the daily change 
        df_pivot_final_ = df_pivot_final.loc [: , df_pivot_final.columns[:-1]]
    
        master_ = master.merge(df_pivot_final_, how = 'outer')
        master_ = master_.dropna(how= 'all')
        
        master_  = master_ .loc [ master_ ['MICRO STRATEGY'].isin(master_ ['MICRO STRATEGY'].drop_duplicates()) , : ]  
        col_list_master = master_.columns.tolist()
        
        col_list_master [5:] = master_.columns[5:].sort_values(ascending = False)
        master_ = master_.loc[:, col_list_master].fillna(0)
    
        return master_, df_pivot_final
    
    filename_prefix = 'Z:\Business\Personnel\Henry\Daily\MCMM PnL\DAILY_PNL_DUMP\RV_CAP_GROUP_DAILYPNL_' 
    master_dir = r'Z:\Business\Personnel\Henry\Daily\MCMM PnL\PNL_TimeSeries_Raw\master\master.xlsx'
    
    today = datetime.datetime.today().date()
    today_mmddyyyy = today.strftime('%m') + '/' + today.strftime('%d') +'/' + today.strftime('%Y')
    today_ddmmmyyyy = today.strftime('%d') + today.strftime('%b') + today.strftime('%Y')
    
    # start_dt = '01/08/2021'
    start_dt = None 
    end_dt = today_mmddyyyy
    
    master, df_pivot = pnl_pivot_ytd(filename_prefix , master_dir,  startdate = start_dt , enddate = end_dt, start_date_auto = True) 
    
    if start_dt == None: 
        start_dt = df_pivot.columns[-1].strftime('%d') + df_pivot.columns[-1].strftime('%b') + df_pivot.columns[-1].strftime('%Y')
    
    return tdb, master, df_pivot, start_dt, end_dt, master_dir, today_ddmmmyyyy
    
if not st.session_state["load_state"] and not st.session_state.cut:
    
    if upload_tdb:
        
        tdb_file = st.file_uploader("Upload the blotter file (xlsx)")
        if tdb_file is not None:
            
            def update_data():
                tdb = pd.read_excel(tdb_file, engine='openpyxl')
                omega_map = pd.read_excel(tdb_path, sheet_name = 1, engine='openpyxl')
                tdb_bar.progress(0.1)
                path = r'Z:\Business\Portfolio\NAV\NAV Calculations\MCMM\MLP Consolidated Reports'
                newest = max([f for f in os.listdir(path)], key=lambda x: os.stat(os.path.join(path,x)).st_mtime)
                tdb_bar.progress(0.2)
                folder_path = path + "\\" + newest
                files = glob.glob(folder_path + r'\*xlsx')
                tdb_bar.progress(0.3)
                max_file = max(files, key=os.path.getctime)
                if "~$" in max_file:
                    max_file = max_file.split("~$")[0] + max_file.split("~$")[-1]
                tdb_bar.progress(0.4)
                destination_path = "Z:\Business\Personnel\Henry\Daily\MCMM PnL\DAILY_PNL_DUMP"
                
                if '_final' not in max_file:
                    new_path = destination_path + "\\" + max_file.split('\\')[-1]
                else:
                    new_path = destination_path + "\\" + max_file.split('\\')[-1].split('_final')[0] + max_file.split('\\')[-1].split('_final')[1]
                    
                if os.path.exists(max_file): 
                    if not os.path.exists(new_path):
                        tdb_bar.progress(0.5)
                        new_location = shutil.copyfile(max_file, new_path)
                    else:
                        tdb_bar.progress(0.5)
                        os.remove(new_path)
                        new_location = shutil.copyfile(max_file, new_path)
                
                tdb_bar.progress(0.6)
                tdb, master, df_pivot, start_dt, end_dt, master_dir, today_ddmmmyyyy = get_files(tdb, omega_map)
                tdb_bar.progress(0.7)
                #df_pivot.reset_index().to_excel(r'Z:\Business\Personnel\Henry\Daily\MCMM PnL\PNL_TimeSeries_Raw\MCMM_PNL_TimeSeries_YTD_' 
                                                #+ re.sub("/", '', start_dt)  + '_' + re.sub("/", '', end_dt) + '_v1'+ '.xlsx',  index = False)
                tdb_bar.progress(0.8)
                #master.reset_index().to_excel(master_dir,  index = False)
                #master.to_excel(r'Z:\Business\Personnel\Henry\Daily\MCMM PnL\PNL_TimeSeries_Raw\master\master_backup'+ today_ddmmmyyyy  + '.xlsx',  index = False)
                tdb_bar.progress(0.9)
                # master.reset_index().to_excel('Z:\Business\Personnel\Henry\Daily\MCMM PnL\--MCMM Report--\master.xlsx',  index = False)
                
                return tdb, master, max_file

            tdb_bar = st.progress(0)
            tdb, master, max_file = update_data()
            tdb_bar.progress(1.0)
            tdb_bar.empty()
         
    else:     
    
        #@st.cache(ttl=60)
        def update_data():
            tdb = pd.read_excel(tdb_path, engine='openpyxl')
            omega_map = pd.read_excel(tdb_path, sheet_name = 1, engine='openpyxl')
            tdb_bar.progress(0.1)
            path = r'Z:\Business\Portfolio\NAV\NAV Calculations\MCMM\MLP Consolidated Reports'
            newest = max([f for f in os.listdir(path)], key=lambda x: os.stat(os.path.join(path,x)).st_mtime)
            tdb_bar.progress(0.2)
            folder_path = path + "\\" + newest
            files = glob.glob(folder_path + r'\*xlsx')
            tdb_bar.progress(0.3)
            max_file = max(files, key=os.path.getctime)
            if "~$" in max_file:
                max_file = max_file.split("~$")[0] + max_file.split("~$")[-1]
            tdb_bar.progress(0.4)
            destination_path = "Z:\Business\Personnel\Henry\Daily\MCMM PnL\DAILY_PNL_DUMP"

            if '_final' not in max_file:
                new_path = destination_path + "\\" + max_file.split('\\')[-1]
            else:
                new_path = destination_path + "\\" + max_file.split('\\')[-1].split('_final')[0] + max_file.split('\\')[-1].split('_final')[1]
                
            if os.path.exists(max_file): 
                if not os.path.exists(new_path):
                    tdb_bar.progress(0.5)
                    new_location = shutil.copyfile(max_file, new_path)
                else:
                    tdb_bar.progress(0.5)
                    os.remove(new_path)
                    new_location = shutil.copyfile(max_file, new_path)
                
            tdb_bar.progress(0.6)
            tdb, master, df_pivot, start_dt, end_dt, master_dir, today_ddmmmyyyy = get_files(tdb, omega_map)
            tdb_bar.progress(0.7)
            #df_pivot.reset_index().to_excel(r'Z:\Business\Personnel\Henry\Daily\MCMM PnL\PNL_TimeSeries_Raw\MCMM_PNL_TimeSeries_YTD_' 
                                            #+ re.sub("/", '', start_dt)  + '_' + re.sub("/", '', end_dt) + '_v1'+ '.xlsx',  index = False)
            tdb_bar.progress(0.8)
            #master.reset_index().to_excel(master_dir,  index = False)
            #master.to_excel(r'Z:\Business\Personnel\Henry\Daily\MCMM PnL\PNL_TimeSeries_Raw\master\master_backup'+ today_ddmmmyyyy  + '.xlsx',  index = False)
            tdb_bar.progress(0.9)
            # master.reset_index().to_excel('Z:\Business\Personnel\Henry\Daily\MCMM PnL\--MCMM Report--\master.xlsx',  index = False)

            return tdb, master, max_file

        tdb_bar = st.progress(0)
        tdb, master, max_file = update_data()
        tdb_bar.progress(1.0)
        tdb_bar.empty()

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
    pl = master.iloc[:,4:idt+1]

    Trader_DB = pd.concat([Trader_DB, trader_names/100], axis = 1)
    Trader_DB = pd.melt(Trader_DB, id_vars =list(Trader_DB.columns[:5]), value_vars =list(Trader_DB.columns[5:]),
                        var_name= "Trader" , value_name= "weights")
    
    Trader_DB = Trader_DB[(Trader_DB[['weights']] != 0).all(axis=1)]

    Rates = ["DS", "RM", "SP", "HW", "RMDS", "RMDSHWSP"]
    FX = ["SK", "YZ", "HC", "SW"]
    Credit = ["RR", "HL", "ND"]
    Others = ["TL", "AS", "TR", "DXS", "Firm-Rates", "Non-RMDSHWSP", "Firm-All"]
    
    # Drop Traders
    traders_left = ["UB", "MS", "RD"]
    Trader_DB.drop(Trader_DB[Trader_DB["Trader"].isin(traders_left)].index, inplace = True)
    
    Trader_DB.loc[Trader_DB["Trader"].isin(Rates), "Desk"] = "Rates"
    Trader_DB.loc[Trader_DB["Trader"].isin(FX), "Desk"] = "FX"
    Trader_DB.loc[Trader_DB["Trader"].isin(Credit), "Desk"] = "Credit"
    Trader_DB.loc[Trader_DB["Trader"].isin(Others), "Desk"] = "Others"

    Trader_DB.loc[Trader_DB["Trade Name"].str.endswith("SP1") ,"Trader"] = "AS"
    
    Trader_DB = pd.merge(Trader_DB, pl, on='Trade Name', how='left')
    
    Trader_DB.update(Trader_DB.iloc[:, 8:].mul(Trader_DB.weights, 0))
    Trader_DB.drop(['weights'], axis=1, inplace = True)
    
    return Trader_DB
    
if st.session_state.cut:
    
    if "tdb" not in st.session_state:
        st.session_state["tdb"] = False
        
    if "master" not in st.session_state:
        st.session_state["master"] = False
        
    if "max_file" not in st.session_state:
        st.session_state["max_file"] = False
        
    tdb = st.session_state["tdb"]
    master = st.session_state["master"]
    max_file = st.session_state["max_file"]
    
if (tdb is not None and master is not None) or st.session_state["load_state"]:
    
    st.session_state.cut = True
    
    if not st.session_state["load_state"] or st.session_state.cut:
        
        if "tdb" not in st.session_state:
            st.session_state["tdb"] = False
        st.session_state["tdb"] = tdb
        
        if "master" not in st.session_state:
            st.session_state["master"] = False
        st.session_state["master"] = master
        
        if "max_file" not in st.session_state:
            st.session_state["max_file"] = False
        st.session_state["max_file"] = max_file
        
        def restart_on_live(tdb, master, max_file, pass_live):

            for key in st.session_state.keys():
                del st.session_state[key]
                
            if pass_live == True:
    
                if "cut" not in st.session_state:
                    st.session_state.cut = False
                st.session_state.cut = True
                
                if "tdb" not in st.session_state:
                    st.session_state["tdb"] = False
                st.session_state["tdb"] = tdb
                
                if "master" not in st.session_state:
                    st.session_state["master"] = False
                st.session_state["master"] = master
                
                if "max_file" not in st.session_state:
                    st.session_state["max_file"] = False
                st.session_state["max_file"] = max_file
            
        with st.sidebar.container():
            
            data_type = st.sidebar.radio("PNL Type", ('None', 'Live', 'Official'), on_change=restart_on_live, args=(st.session_state["tdb"], st.session_state["master"], st.session_state["max_file"], st.session_state.cut, ))
            
        if data_type == "Live":
            
            live_bar = st.progress(0)
            dates = []
            results = []

            files = os.listdir(mcmm_pnl_path)
                
            #get all excel files from official to live (unique most updated file of the day)
            for file in sorted(os.listdir(mcmm_pnl_path), key=lambda x: os.path.getctime(os.path.join(mcmm_pnl_path, x)), reverse = True):
                for date in pd.date_range(list(master.columns)[5].date(),datetime.date.today(),freq='d'):
                    if "pnl_output_" in file and str(date.date() + timedelta(days=1)) in file and (date.date() + timedelta(days=1)) not in dates:
                        if "~$" in file:
                            file = file.split("~$")[-1] 
                        dates.append(date.date() + timedelta(days=1))
                        data = pd.read_excel(mcmm_pnl_path + '/' + file, engine='openpyxl')
                        data.rename(columns = {"Strategy": "MICRO STRATEGY"}, inplace =True)
                        data = data[["MICRO STRATEGY", "Trade Name", "YTD"]]
                        results.append(data)
                        live_bar.progress(0.3)
            
            live_bar.progress(0.5)
            if len(results) == 1: 
                last_official = pd.read_excel(max_file, engine='openpyxl')
                last_official = last_official.rename(columns=last_official.iloc[0]).loc[1:]
                live_bar.progress(0.6)
                last_official.dropna(subset=["MICRO STRATEGY"], inplace = True)
                df = pd.merge(results[0], last_official, on = 'MICRO STRATEGY', how ='outer')
                df['YTD'].fillna(0, inplace = True)
                df['YTD TOTAL PNL'].fillna(0, inplace = True)
                live_bar.progress(0.7)
                df[dates[0]] = df["YTD"] - df["YTD TOTAL PNL"]
                df = df[["MICRO STRATEGY","Trade Name", dates[0]]]
            
            elif len(results) >=2:
                res = []
                for i in range(len(results)-1):
                    df = pd.merge(results[i+1], results[i], on = 'Trade Name', how ='outer')
                    df.dropna(axis=0, how='any', inplace=True)
                    df[dates[i]] = df["YTD_y"] - df["YTD_x"]
                    df = df[["Trade Name", dates[i]]]
                    res.append(df)
                    live_bar.progress(0.6)
                    
                last_official = pd.read_excel(max_file, engine='openpyxl')
                last_official = last_official.rename(columns=last_official.iloc[0]).loc[1:]
                last_official.dropna(subset=["MICRO STRATEGY"], inplace = True)
                df = pd.merge(results[-1], last_official, on = 'MICRO STRATEGY', how ='outer')
                live_bar.progress(0.7)
                df['YTD'].fillna(0, inplace = True)
                df['YTD TOTAL PNL'].fillna(0, inplace = True)
                df[dates[-1]] = df["YTD"] - df["YTD TOTAL PNL"]
                df = df[["MICRO STRATEGY","Trade Name", dates[-1]]]
                res.append(df)
                
                df = reduce(lambda x,y: pd.merge(x,y, on='Trade Name', how='outer'), res)

            live_bar.progress(0.8)
            master = pd.merge(master, df, on = ["MICRO STRATEGY", "Trade Name"], how ='outer')
            sep = master.iloc[:, 5:]
            sep.columns = pd.to_datetime(sep.columns)
            live_bar.progress(0.9)
            sep = sep[sorted(sep.columns, reverse=True)]
            master = pd.concat([master.iloc[:, :5], sep], axis = 1)
            master.fillna(0, inplace = True)
            live_bar.progress(1.0)
            live_bar.empty()
        
        if data_type == "None" and st.session_state["load_state"]:
            st.warning('PNL Type not chosen', icon="⚠️")
        else:
            master = pd.concat([master[["Asset Class","Theme", "RiskCountry", "MICRO STRATEGY", "Trade Name"]].astype('string'), master[list(master.columns)[6:]].astype(int)], axis = 1)
            Trader_DB = get_database(master, tdb)
    
    @st.experimental_memo(suppress_st_warning=True)
    def get_MCMM_table(mcmm_pnl_path, tdb_path, mcmm_map, end_date):

        mcmm_pnl_files = glob.glob(mcmm_pnl_path + r'\*xlsx')
        pnl_output_files = [file for file in mcmm_pnl_files if 'pnl_output_' and str(end_date) in file]
        if len(pnl_output_files)==0:
            
            final_1 = pd.DataFrame()
            final_2 = pd.DataFrame()
            ytd_pl_firm = 0 
            ytd_pl_rmdshwsp = 0
            
        else:
            latest_mcmm_pnl_file = max(pnl_output_files, key=os.path.getmtime)
            if "~$" in latest_mcmm_pnl_file:
                latest_mcmm_pnl_file = latest_mcmm_pnl_file.split("~$")[0] + latest_mcmm_pnl_file.split("~$")[-1]
                
            tdb = pd.read_excel(tdb_path, sheet_name = "UserData", engine='openpyxl')
    
            out = pd.read_excel(r'Z:\Business\Personnel\Saswat\Sizing and Capital Calculator/mcmm_dashboard_out.xlsx', engine='openpyxl')
            mcmm_pnl = pd.read_excel(latest_mcmm_pnl_file, engine='openpyxl')
            mcmm_pnl_time = time.ctime(os.path.getmtime(latest_mcmm_pnl_file))
            mcmm_pnl_time = time.strftime("%Y-%m-%d", time.strptime(mcmm_pnl_time))
            out_time = time.ctime(os.path.getmtime(r'Z:\Business\Personnel\Saswat\Sizing and Capital Calculator/mcmm_dashboard_out.xlsx'))
            out_time = time.strftime("%Y-%m-%d", time.strptime(out_time))
            #streamlit input category and country
            cat_mapping = pd.DataFrame({'Cat': [wor for wor in mcmm_map.split(", ")]})

            out = out[out["Trade Name"] != "Total"]
            out["Cat"] = out["Category"] + "_" + out["Country"]
            out.loc[out["Cat"].isin(cat_mapping["Cat"]), "Category_Final"] = out["Cat"]

            fx_trade = ["Dual European Digi_China", "Call Spread_Taiwan", "Call Spread_China", "Vanilla Option_Korea", 
            "FX swap_Indonesia", "Call Spread_Korea", "FX swap_China", "FX outright_India", "FX swap_Philippines",
            "Vanilla Option_Philippines", "European Digi_Japan", "FX outright_Taiwan", "FX outright_Japan", 
            "FX outright_Singapore", "Vanilla Option_Europe", "FX swap_India", "FX outright_Indonesia", "FX outright_China", 
            "One Touch_Japan", "FX outright_Philippines"]
            
            out.loc[out["Category_Final"].isin(fx_trade), "Category_Final"] = "FX Trade"
            out.loc[~out["Cat"].isin(cat_mapping["Cat"]), "Category_Final"] = "Others"
            out["Dv01"] = out["MCMM"]
            
            extract = tdb.columns.get_loc("Trade Name") 
            extract_weights = tdb.iloc[:,extract:]

            join = out.merge(extract_weights, on = 'Trade Name', how = 'left')
            join["Dv01 RMDSHWSP"] = (join["DS"] + join["RM"] + join["HW"] + join["SP"])/100 * join["Dv01"]
            out = join[["Trade Name", "Dv01 RMDSHWSP"]].merge(out, on = 'Trade Name')
            out["Nav/bp"] = out["Dv01"]/50000
            out["Nav/bp RMDSHWSP"] = out["Dv01 RMDSHWSP"]/50000
            out.fillna(0, inplace = True)

            mcmm_pnl["Daily Bp"] = mcmm_pnl["Daily"]/50000
            mcmm_pnl["MTD bp"] = mcmm_pnl["MTD"]/50000
            mcmm_pnl["YTD Bp"] = mcmm_pnl["YTD"]/50000
            mcmm_pnl["Cat"] = mcmm_pnl["Trade Category"] + "_" + mcmm_pnl["RiskCountry"]
            mcmm_pnl.loc[mcmm_pnl["Cat"].isin(cat_mapping["Cat"]), "Category_Final"] = mcmm_pnl["Cat"]
            mcmm_pnl.loc[mcmm_pnl["Category_Final"].isin(fx_trade), "Category_Final"] = "FX Trade"
            mcmm_pnl.loc[~mcmm_pnl["Cat"].isin(cat_mapping["Cat"]), "Category_Final"] = "Others"
            
            join_2 = mcmm_pnl.merge(extract_weights, on = 'Trade Name', how = 'left')
            join_2["RMDSHWSP"] = (join_2["DS"] + join_2["RM"] + join_2["HW"] + join_2["SP"])
            mcmm_pnl["RMDSHWSP"] = join_2["RMDSHWSP"]
    
            mcmm_pnl["Daily RMDSHWSP"] = mcmm_pnl["Daily"]*mcmm_pnl["RMDSHWSP"]/100
            mcmm_pnl["MTD RMDSHWSP"] = mcmm_pnl["MTD"]*mcmm_pnl["RMDSHWSP"]/100
            mcmm_pnl["YTD RMDSHWSP"] = mcmm_pnl["YTD"]*mcmm_pnl["RMDSHWSP"]/100
            mcmm_pnl["Daily RMDSHWSP bp"] = mcmm_pnl["Daily RMDSHWSP"]/50000
            mcmm_pnl["MTD RMDSHWSP bp"] = mcmm_pnl["MTD RMDSHWSP"]/50000
            mcmm_pnl["YTD RMDSHWSP Bp"] = mcmm_pnl["YTD RMDSHWSP"]/50000
            # mcmm_pnl = mcmm_pnl[mcmm_pnl["Asset Class"] == "Rates"]

            pivot_1 = pd.pivot_table(mcmm_pnl[mcmm_pnl["Asset Class"] == "Rates"], values = ["Daily Bp", "MTD bp"], index =['Category_Final'], 
                                   aggfunc = np.sum)

            pivot_2 = pd.pivot_table(mcmm_pnl, values = ["Daily RMDSHWSP bp", "MTD RMDSHWSP bp"], index =['Category_Final'], 
                                    aggfunc = np.sum)

            pivot_3 = pd.pivot_table(out, values = ["Nav/bp", "Nav/bp RMDSHWSP"], index =['Category_Final'], 
                                    aggfunc = np.sum)

            final_1 = pivot_1.merge(pivot_3, left_index=True, right_index=True)
            final_1.drop(columns=['Nav/bp RMDSHWSP'], inplace=True)
            final_2 = pivot_2.merge(pivot_3, left_index=True, right_index=True)
            final_2.drop(columns=['Nav/bp'], inplace=True)
            final_1.loc['Total',:]= final_1.sum(axis=0)
            final_2.loc['Total',:]= final_2.sum(axis=0)
    
            ytd_pl_firm = mcmm_pnl[mcmm_pnl["MLP_Port"] == "RCMR"]["YTD"].sum()/50000
            ytd_pl_rmdshwsp = mcmm_pnl["YTD RMDSHWSP"].sum()/50000
        
        return final_1, final_2, ytd_pl_firm, ytd_pl_rmdshwsp, mcmm_pnl_time, out_time
    
    @st.experimental_memo(suppress_st_warning=True)
    def spx_ret():  
        
        spx = pd.read_csv(r'Z:\Business\Research\Dashboard\DataSources\BBG\FUTURES\ES/FUTS_ES.csv')
        spx.columns = spx.iloc[1]
        spx = spx.iloc[2:]
        spx.rename(columns = {"Date": "Dates"}, inplace = True)
        
        return spx
    
    def use_stored_data(Trader_DB):
        
        if "load_state" not in st.session_state:
            st.session_state.load_state = False
            
        st.session_state.load_state = True
            
        if "Trader_Database" not in st.session_state:
            st.session_state["Trader_Database"] = False
        
        st.session_state["Trader_Database"] = Trader_DB
        
        st.session_state["dates_ran"] = today

    if st.session_state["load_state"]:
        
        Trader_DB = st.session_state["Trader_Database"]
        
    # ---- SIDEBAR ----
    with st.sidebar.form("Specify"):
    
        st.subheader("Please Filter Here:")

        start_date = st.date_input("Start Date: ", value = list(Trader_DB.columns)[-1].date(), 
                                        min_value = list(Trader_DB.columns)[-1].date(), max_value = list(Trader_DB.columns)[7].date())
        
        end_date = st.date_input("End Date: ", value = list(Trader_DB.columns)[7].date(), 
                                        min_value = list(Trader_DB.columns)[-1].date(), max_value = list(Trader_DB.columns)[7].date())
        
        trader = st.multiselect(
            "Select the Trader:",
            options=Trader_DB["Trader"].unique(),
            default="Firm-All")
        
        with st.expander("Edit Category Mappings"):
          
            mcmm_map = st.text_area('MCMM Category Mappings:', "Receive/Pay_Australia, Receive/Pay_India, Receive/Pay_Korea, Receive/Pay_New Zealand, Receive/Pay_US, Receive/Pay_China, Steepener/Flattener_US, Steepener/Flattener_Korea, Inflation_Australia, Inflation_Japan, ASW/MMS_Korea, Receive/Pay_Europe, Steepener/Flattener_Australia, Receive/Pay_Japan, Steepener/Flattener_India, Receive/Pay_Taiwan, Steepener/Flattener_Europe, Dual European Digi_China, Call Spread_Taiwan, Call Spread_China, Vanilla Option_Korea, FX swap_Indonesia, Call Spread_Korea, FX swap_China, FX outright_India, FX swap_Philippines, Vanilla Option_Philippines, European Digi_Japan, FX outright_Taiwan, FX outright_Japan, FX outright_Singapore, Vanilla Option_Europe, FX swap_India, FX outright_Indonesia, FX outright_China, One Touch_Japan, FX outright_Philippines")
        
        number = int(st.number_input('No. of charts to add: ', min_value=1, max_value=20, step=1))

        loaded = st.form_submit_button("Analyse", on_click = use_stored_data, args=(Trader_DB, ))
    
    if st.session_state["load_state"] and data_type != "None":
        
        if trader == "":
            st.error('Empty Trader')
        if start_date >= end_date:
            st.error('Start Date After End Date')
        if start_date.weekday() > 4 or end_date.weekday() > 4:
            st.error('Weekend Chosen')
            
        if trader != "" and start_date < end_date and start_date.weekday() <= 4 or end_date.weekday() <= 4:
            plot_bar = st.progress(0)

            @st.experimental_memo(suppress_st_warning=True)
            def filter_dates(Trader_DB):
                
                idtdbs = Trader_DB.columns.get_loc(pd.Timestamp(start_date))
                idtdbe = Trader_DB.columns.get_loc(pd.Timestamp(end_date))

                dates_filter = Trader_DB.iloc[:,idtdbe:idtdbs+1]
                dates_filter.iloc[:, -1] = 0 #first date 0 pl
                
                Trader_DB_select = pd.concat([Trader_DB.iloc[:, :7], dates_filter], axis = 1)
                Trader_DB_select = Trader_DB_select[(Trader_DB_select.iloc[:, 7:].T != 0).any()]
                
                return Trader_DB_select
            
            Trader_DB_select = filter_dates(Trader_DB)
            
            # ---- MAINPAGE ----
            st.title(":bar_chart: MCMM Dashboard")
            st.markdown("##")
                
            # st.write("Memory usage of Overall database: ", str(Trader_DB.memory_usage(index=True, deep=True).sum()), "MB")
            
            st.header(":pushpin: Analysis across Traders")

            tab1, tab2 = st.tabs(["Daily Correlation", "Weekly Correlation"])
            
            @st.experimental_memo(suppress_st_warning=True)
            def sort_names(daily_pnl):
                our_list = ["Firm-All", "RR", "HL", "YS", "AS", "TR", "RM", "DS", "HW", "SP", "TL", "RMDSHWSP", "Non-RMDSHWSP", "Firm-Rates"]
                main_list = list(set(list(daily_pnl.Trader.unique())) - set(our_list))
                our_list[11:11] = main_list
                return our_list
            
            with tab1:
                
                @st.experimental_memo(suppress_st_warning=True)
                def daily_traderspl_corr(Trader_DB_select):
                    
                    Order_Daily = Trader_DB_select.groupby(["Trader"]).aggregate("sum").T
                    our_list = sort_names(Trader_DB_select)
                    daily_pnl_update = Order_Daily.reindex(columns=our_list)
                    corr = daily_pnl_update.corr()
    
        # =============================================================================
        #             mask = np.triu(np.ones_like(corr, dtype=bool))
        #             df_mask = corr.mask(mask)
        # =============================================================================
            
                    fig = px.imshow(corr.to_numpy(), x=corr.columns.tolist(),
                                              y=corr.columns.tolist(), text_auto=".0%",
                                              color_continuous_scale='Temps_r', 
                                              aspect="auto")
                    
                    fig.update_xaxes(side="bottom")
                    
                    fig.update_layout(
                        title_text='Daily Correlation of PM', 
                        title_x=0.5, 
                        width=1000, 
                        height=1000,
                        xaxis_showgrid=False,
                        yaxis_showgrid=False,
                        xaxis_zeroline=False,
                        yaxis_zeroline=False,
                        yaxis_autorange='reversed',
                        template='simple_white'
                        )
                    
                    fig.update_traces(text = corr.to_numpy(), hovertemplate="%{x} <br>%{y} </br> %{text:.0%}")
                    
                    return daily_pnl_update, fig
                
                daily_pnl_update, fig = daily_traderspl_corr(Trader_DB_select)
                
                tab1.plotly_chart(fig, use_container_width=True)
                
                col1, col2, col3 = tab1.columns(3)
                col2.markdown("Data is between **" + str(start_date) + "** and **" + str(end_date) + "**")
                
            with tab2:
                
                if (end_date - start_date).days >= 7:
                        
                    @st.experimental_memo(suppress_st_warning=True)
                    def weekly_traderspl_corr(Trader_DB_select):
                        
                        def next_weekday(d, weekday):
                            days_ahead = weekday - d.weekday()
                            if days_ahead <= 0:
                                days_ahead += 7
                            return d + datetime.timedelta(days_ahead)
                        
                        def get_fri_data(daily_pnl_copy):
                            
                            daily_pnl_copy['weekday'] = daily_pnl_copy['Dates'].dt.dayofweek
                            daily_pnl_copy = daily_pnl_copy[daily_pnl_copy['weekday'] < 5].copy()
                            daily_pnl_copy['end_of_week'] = daily_pnl_copy['Dates'].map(lambda x: next_weekday(x, 4) if  x.weekday() < 4 else x)
                            daily_pnl_copy = daily_pnl_copy[daily_pnl_copy['end_of_week'] == daily_pnl_copy['Dates']]
                            daily_pnl_copy.drop(columns = ["weekday", "end_of_week"], inplace = True)
                            
                            return daily_pnl_copy
                            
                        Trader_DB_select_wkly = Trader_DB_select.iloc[:, 7:].T.reset_index().rename(columns = {"index": "Dates"})
                        Trader_DB_select_copy = get_fri_data(Trader_DB_select_wkly)
                        Trader_DB_impt_dates = Trader_DB_select_copy.set_index("Dates").T
                        Trader_DB_select_map = pd.merge(Trader_DB_select.iloc[:, :7], Trader_DB_impt_dates, left_index=True, right_index=True)
                        
                        Order_Weekly = Trader_DB_select_map.groupby(["Trader"]).aggregate("sum").T
                        our_list = sort_names(Trader_DB_select_map)
                        weekly_pnl_update = Order_Weekly.reindex(columns=our_list)
                        corr = weekly_pnl_update.corr()
    
                        #corr.dropna(axis = 0, how = "all", inplace=True)
                        #corr.dropna(axis = 1, how = "all", inplace=True)
    
        # =============================================================================
        #                 mask = np.triu(np.ones_like(corr, dtype=bool))
        #                 df_mask = corr.mask(mask)
        # =============================================================================
            
                        fig = px.imshow(corr.to_numpy(), x=corr.columns.tolist(),
                                                  y=corr.columns.tolist(), text_auto=".0%", 
                                                      color_continuous_scale='Temps_r', aspect="auto")
                        
                        fig.update_xaxes(side="bottom")
                        
                        fig.update_layout(
                            title_text='Weekly Correlation of PM', 
                            title_x=0.5, 
                            width=1000, 
                            height=1000,
                            xaxis_showgrid=False,
                            yaxis_showgrid=False,
                            xaxis_zeroline=False,
                            yaxis_zeroline=False,
                            yaxis_autorange='reversed',
                            template='simple_white'
                            )
                        
                        fig.update_traces(text = corr.to_numpy(), hovertemplate="%{x} <br>%{y} </br> %{text:.0%}")
                        
                        return weekly_pnl_update, fig
                    
                    weekly_pnl_update, fig = weekly_traderspl_corr(Trader_DB_select)
                    
                    tab2.plotly_chart(fig, use_container_width=True)
                    
                    col4, col5, col6 = tab2.columns(3)
                    col5.markdown("Data is between **" + str(list(weekly_pnl_update.index)[0].strftime("%Y-%m-%d")) + "** and **" + str(list(weekly_pnl_update.index)[-1].strftime("%Y-%m-%d")) + "**")
                           
                else:
                    tab2.warning('Not enough data to calculate Weekly Stats')

            plot_bar.progress(0.05)
                
            tab3, tab4 = st.tabs(["Daily Std.Dev", "Weekly Std.Dev"])

            with tab3:
                
                tab3.subheader("Daily Std.Dev of PM")
                
                @st.experimental_memo(suppress_st_warning=True)
                def daily_std(daily_pnl_update):
                    
                    pnl_std_daily = daily_pnl_update.std().to_frame(name="PNL (USD $)")
                    pnl_std_daily.index.name="Traders"
                    pnl_std_daily.drop(index=['RMDS','Firm-All'], inplace = True)
                    pnl_std_daily.sort_values("PNL (USD $)", inplace = True)
                
                    fig_pl_std_daily = px.bar(
                        pnl_std_daily,
                        x=pnl_std_daily.index,
                        y="PNL (USD $)",
                        text_auto='0.2s',
                        color_discrete_sequence=["#0083B8"], #* len(daily_pnl.std()),
                        template="plotly_white",
                    )
                    fig_pl_std_daily.update_traces(textfont_size=12, textangle=0, 
                                                   textposition="outside", cliponaxis=False,
                                                   hovertemplate="%{x} <br> %{y:.2s}")
                    
                    fig_pl_std_daily.update_layout(
                        xaxis=dict(tickmode="linear"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=(dict(showgrid=False)),
                        )
                    
                    return fig_pl_std_daily
               
                fig_pl_std_daily = daily_std(daily_pnl_update)
                
                tab3.plotly_chart(fig_pl_std_daily, use_container_width=True)
                
                col7, col8, col9 = tab3.columns(3)
                col8.markdown("Data is between **" + str(start_date) + "** and **" + str(end_date) + "**")
                  
            with tab4:
                
                if (end_date - start_date).days >= 7:
                    
                    tab4.subheader("Weekly Std.Dev of PM")
                    
                    @st.experimental_memo(suppress_st_warning=True)
                    def weekly_std(weekly_pnl_update):
                        
                        pnl_std_weekly = weekly_pnl_update.std().to_frame(name="PNL (USD $)")
                        pnl_std_weekly.index.name="Traders"
                        pnl_std_weekly.drop(index=['RMDS','Firm-All'], inplace = True)
                        pnl_std_weekly.sort_values("PNL (USD $)", inplace = True)
                    
                        fig_pl_std_weekly = px.bar(
                            pnl_std_weekly,
                            x=pnl_std_weekly.index,
                            y="PNL (USD $)",
                            text_auto='0.2s',
                            color_discrete_sequence=["#0083B8"], #* len(daily_pnl.std()),
                            template="plotly_white",
                        )
                        fig_pl_std_weekly.update_traces(textfont_size=12, textangle=0, 
                                                        textposition="outside", cliponaxis=False,
                                                        hovertemplate="%{x} <br> %{y:.2s}")
                        
                        fig_pl_std_weekly.update_layout(
                            xaxis=dict(tickmode="linear"),
                            plot_bgcolor="rgba(0,0,0,0)",
                            yaxis=(dict(showgrid=False)),
                            )
                        
                        return fig_pl_std_weekly
                   
                    fig_pl_std_weekly = daily_std(weekly_pnl_update)
                    
                    tab4.plotly_chart(fig_pl_std_weekly, use_container_width=True)
                    
                    col10, col11, col12 = tab4.columns(3)
                    col11.markdown("Data is between **" + str(list(weekly_pnl_update.index)[0].strftime("%Y-%m-%d")) + "** and **" + str(list(weekly_pnl_update.index)[-1].strftime("%Y-%m-%d")) + "**")
                    
                else:
                    tab4.warning('Not enough data to calculate Weekly Stats')
            
            st.subheader("PM Performance - Firm")

            plot_bar.progress(0.1)
                
            first_t, second_t, third_t = st.tabs(["Top_5", "Top_10", "All"])

            pm_perf = daily_pnl_update.rename_axis(None,axis=1)
            
            @st.experimental_memo(suppress_st_warning=True)
            def get_pm_perf_data(pm_perf, num):
                
                if num != 0:
                    get_names = pm_perf.T.sort_values(by= pm_perf.index.to_list()[-1]).iloc[:, -1]
                    full_names = get_names.index.to_list()[:num] + get_names.index.to_list()[-num:]
                    pm_perf = pm_perf[full_names]
                
                pm_perf["Dates"]=pm_perf.index
                pm_perf = pd.melt(pm_perf, id_vars="Dates", value_vars=pm_perf.columns[:-1],
                                      var_name= "Trader" , value_name= "PNL")
                
                pm_perf['Dates'] = pd.to_datetime(pm_perf['Dates'], format = '%Y-%m-%d')
                
                return pm_perf
            
            @st.experimental_memo(suppress_st_warning=True)
            def add_line_pm_perf(pm_perf):
                
                all_names = list(pm_perf["Trader"].unique())
                groups = ["Firm-All", "Firm-Rates", "Non-RMDSHWSP", "RMDSHWSP"]
                non_groups = list(set(all_names) - set(groups))
                pm_perf_month = pm_perf.groupby(['Dates','Trader']).sum().groupby('Trader').cumsum().reset_index()
                pm_perf_line = pm_perf_month[pm_perf_month["Trader"].isin(non_groups)]
                
                return pm_perf_month, pm_perf_line, groups
            
            @st.experimental_memo(suppress_st_warning=True)
            def add_bar_pm_perf(pm_perf):
                
                all_names = list(pm_perf["Trader"].unique())
                groups = ["Firm-All"]
                non_groups = list(set(all_names) - set(groups))
                
                pm_perf_month = pm_perf.copy()
                pm_perf_month["month_date"] = pd.to_datetime(pm_perf_month.Dates.dt.strftime('%Y-%m'))
                pm_perf_month['last_date'] = (pm_perf_month["month_date"] + MonthEnd(1)).dt.strftime("%d-%m-%Y")
                pm_perf_month['last_date'] = pd.to_datetime(pm_perf_month['last_date']).apply(lambda x: x.replace(day=15))
                pm_perf_month['last_date'] = pm_perf_month['last_date'].astype('datetime64')
            
                pm_perf_month = pm_perf_month.groupby([pm_perf_month.last_date, "Trader"]).sum().reset_index()
                pm_perf_bar = pm_perf_month[pm_perf_month["Trader"].isin(groups)]
                
                return pm_perf_month, pm_perf_bar, non_groups
                
            with first_t:
                
                @st.experimental_memo(suppress_st_warning=True)
                def pm_perf_top5(pm_perf):
                    
                    pm_perf_first = get_pm_perf_data(pm_perf, 5)
    
                    if (pd.to_datetime(end_date) - pd.to_datetime(start_date))/np.timedelta64(1,"M") < 1:
                        
                        pm_perf_first_month, pm_perf_first_on_line, groups = add_line_pm_perf(pm_perf_first)
    
                        fig_pm_perf_first = px.line(pm_perf_first_on_line, x="Dates", y="PNL", color = "Trader")
                        
                        for name in groups:
                            
                            pm_perf_first_off_line = pm_perf_first_month[pm_perf_first_month["Trader"] == name]
                            fig_pm_perf_first.add_trace(go.Scatter(x=pm_perf_first_off_line["Dates"], y=pm_perf_first_off_line["PNL"], name=name, visible='legendonly'))
                        
                    else:
                        
                        pm_perf_first_month, pm_perf_first_on_bar, non_groups = add_bar_pm_perf(pm_perf_first)
                        
                        fig_pm_perf_first = px.bar(pm_perf_first_on_bar, x="last_date", y="PNL", color = "Trader", 
                                                   category_orders={'last_date': pm_perf_first_on_bar["last_date"]},
                                                 barmode='relative', template="plotly_white")
                    
                        fig_pm_perf_first.update_layout(
                            updatemenus=[
                        		dict(
                        			type="buttons",
                        			direction="left",
                        			buttons=list([
                        				dict(
                        					args=["type", "bar"],
                        					label="Bar Chart",
                        					method="restyle"
                        				),
                        				dict(
                        					args=["type", "line"],
                        					label="Line Plot",
                        					method="restyle"
                        				)
                        			]),
                        		),
                        	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
    # =============================================================================
    #                     fig_pm_perf_first.update_xaxes(
    #                             rangebreaks=[dict(bounds=["sat", "mon"]),])
    # =============================================================================
                    
                        for name in non_groups:
                            
                            pm_perf_first_off_bar = pm_perf_first_month[pm_perf_first_month["Trader"] == name]
                            fig_pm_perf_first.add_trace(go.Bar(x=pm_perf_first_off_bar["last_date"], y=pm_perf_first_off_bar["PNL"], name=name, visible='legendonly'))
                        
                        pm_perf_first_month.rename(columns={'last_date':'Dates'}, inplace = True)
                                                  
                    # Add range slider
                    fig_pm_perf_first.update_layout(
                        xaxis=dict(
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1,
                                          label="1m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=6,
                                          label="6m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=1,
                                          label="YTD",
                                          step="year",
                                          stepmode="todate"),
                                    dict(count=1,
                                          label="1y",
                                          step="year",
                                          stepmode="backward"),
                                    dict(step="all")
                                ])
                            ),
                            rangeslider=dict(
                                visible=True
                            ),
                            type="date"
                        )
                    )
                    
                    fig_pm_perf_first.update_traces(hovertemplate = "Dates: %{x} <br>PNL: %{y:.2s}")
                    
                    return pm_perf_first_month, fig_pm_perf_first
                
                pm_perf_first_month, fig_pm_perf_first = pm_perf_top5(pm_perf)
                
                first_t.plotly_chart(fig_pm_perf_first, use_container_width=True)
                
                with st.expander("See Data Table"):
                    pm_perf_first_pivot = pm_perf_first_month.pivot(index='Dates', columns='Trader')
                    st.dataframe(pm_perf_first_pivot.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=pm_perf_first_pivot.to_csv(),
                      file_name= 'PM_Perf_Top_5_Matrix.csv',
                      mime="text/csv")
                
            with second_t:
                
                @st.experimental_memo(suppress_st_warning=True)
                def pm_perf_top10(pm_perf):
                    
                    pm_perf_second = get_pm_perf_data(pm_perf, 10)
                    
                    if (pd.to_datetime(end_date) - pd.to_datetime(start_date))/np.timedelta64(1,"M") < 1:
                        
                        pm_perf_second_month, pm_perf_second_on_line, groups = add_line_pm_perf(pm_perf_second)
                        
                        fig_pm_perf_second = px.line(pm_perf_second_on_line, x="Dates", y="PNL", color = "Trader")
                        
                        for name in groups:
                            
                            pm_perf_second_off_line = pm_perf_second_month[pm_perf_second_month["Trader"] == name]
                            fig_pm_perf_second.add_trace(go.Scatter(x=pm_perf_second_off_line["Dates"], y=pm_perf_second_off_line["PNL"], name=name, visible='legendonly'))
                    
                    else:
                        
                        pm_perf_second_month, pm_perf_second_on_bar, non_groups = add_bar_pm_perf(pm_perf_second)
                       
                        fig_pm_perf_second = px.bar(pm_perf_second_on_bar, x="last_date", y="PNL", color = "Trader", 
                                                   category_orders={'last_date': pm_perf_second_on_bar["last_date"]},
                                                 barmode='relative', template="plotly_white")
                    
                        fig_pm_perf_second.update_layout(
                            updatemenus=[
                        		dict(
                        			type="buttons",
                        			direction="left",
                        			buttons=list([
                        				dict(
                        					args=["type", "bar"],
                        					label="Bar Chart",
                        					method="restyle"
                        				),
                        				dict(
                        					args=["type", "line"],
                        					label="Line Plot",
                        					method="restyle"
                        				)
                        			]),
                        		),
                        	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
    # =============================================================================
    #                     fig_pm_perf_second.update_xaxes(
    #                             rangebreaks=[dict(bounds=["sat", "mon"]),])
    # =============================================================================
                        
                        for name in non_groups:
                            
                            pm_perf_second_off_bar = pm_perf_second_month[pm_perf_second_month["Trader"] == name]
                            fig_pm_perf_second.add_trace(go.Bar(x=pm_perf_second_off_bar["last_date"], y=pm_perf_second_off_bar["PNL"], name=name, visible='legendonly'))
                        
                        pm_perf_second_month.rename(columns={'last_date':'Dates'}, inplace = True)
                    
                    # Add range slider
                    fig_pm_perf_second.update_layout(
                        xaxis=dict(
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1,
                                          label="1m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=6,
                                          label="6m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=1,
                                          label="YTD",
                                          step="year",
                                          stepmode="todate"),
                                    dict(count=1,
                                          label="1y",
                                          step="year",
                                          stepmode="backward"),
                                    dict(step="all")
                                ])
                            ),
                            rangeslider=dict(
                                visible=True
                            ),
                            type="date"
                        )
                    )
    
                    fig_pm_perf_second.update_traces(hovertemplate = "Dates: %{x} <br>PNL: %{y:.2s}")
                    
                    return pm_perf_second_month, fig_pm_perf_second
                
                pm_perf_second_month, fig_pm_perf_second = pm_perf_top10(pm_perf)
                
                second_t.plotly_chart(fig_pm_perf_second, use_container_width=True)
                
                with st.expander("See Data Table"):
                    pm_perf_second_pivot = pm_perf_second_month.pivot(index='Dates', columns='Trader')
                    st.dataframe(pm_perf_second_pivot.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=pm_perf_second_pivot.to_csv(),
                      file_name= 'PM_Perf_Top_10_Matrix.csv',
                      mime="text/csv")
                    
    
            with third_t:
                
                @st.experimental_memo(suppress_st_warning=True)
                def pm_perf_all(pm_perf):
                    
                    pm_perf_all = get_pm_perf_data(pm_perf, 0)
                    
                    if (pd.to_datetime(end_date) - pd.to_datetime(start_date))/np.timedelta64(1,"M") < 1:
                        
                        pm_perf_month, pm_perf_on_line, groups = add_line_pm_perf(pm_perf_all)
                        
                        fig_pm_perf = px.line(pm_perf_on_line, x="Dates", y="PNL", color = "Trader")
                        
                        for name in groups:
                            
                            pm_perf_off_line = pm_perf_month[pm_perf_month["Trader"] == name]
                            fig_pm_perf.add_trace(go.Scatter(x=pm_perf_off_line["Dates"], y=pm_perf_off_line["PNL"], name=name, visible='legendonly'))
                        
                    else:
                        
                        pm_perf_month, pm_perf_on_bar, non_groups = add_bar_pm_perf(pm_perf_all)
                        
                        fig_pm_perf = px.bar(pm_perf_on_bar, x="last_date", y="PNL", color = "Trader", 
                                                   category_orders={'last_date': pm_perf_on_bar["last_date"]},
                                                 barmode='relative', template="plotly_white")
                    
                        fig_pm_perf.update_layout(
                            updatemenus=[
                        		dict(
                        			type="buttons",
                        			direction="left",
                        			buttons=list([
                        				dict(
                        					args=["type", "bar"],
                        					label="Bar Chart",
                        					method="restyle"
                        				),
                        				dict(
                        					args=["type", "line"],
                        					label="Line Plot",
                        					method="restyle"
                        				)
                        			]),
                        		),
                        	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
    # =============================================================================
    #                     fig_pm_perf.update_xaxes(
    #                             rangebreaks=[dict(bounds=["sat", "mon"]),])
    # =============================================================================
                    
                        for name in non_groups:
                            
                            pm_perf_off_bar = pm_perf_month[pm_perf_month["Trader"] == name]
                            fig_pm_perf.add_trace(go.Scatter(x=pm_perf_off_bar["last_date"], y=pm_perf_off_bar["PNL"], name=name, visible='legendonly'))
                        
                        pm_perf_month.rename(columns={'last_date':'Dates'}, inplace = True)
                    
                    # Add range slider
                    fig_pm_perf.update_layout(
                        xaxis=dict(
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1,
                                          label="1m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=6,
                                          label="6m",
                                          step="month",
                                          stepmode="backward"),
                                    dict(count=1,
                                          label="YTD",
                                          step="year",
                                          stepmode="todate"),
                                    dict(count=1,
                                          label="1y",
                                          step="year",
                                          stepmode="backward"),
                                    dict(step="all")
                                ])
                            ),
                            rangeslider=dict(
                                visible=True
                            ),
                            type="date"
                        )
                    )
    
                    fig_pm_perf.update_traces(hovertemplate = "Dates: %{x} <br>PNL: %{y:.2s}")
                    
                    return pm_perf_month, fig_pm_perf
                
                pm_perf_month, fig_pm_perf = pm_perf_all(pm_perf)

                third_t.plotly_chart(fig_pm_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    pm_perf_pivot = pm_perf_month.pivot(index='Dates', columns='Trader')
                    st.dataframe(pm_perf_pivot.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=pm_perf_pivot.to_csv(),
                      file_name= 'PM_Perf_Matrix.csv',
                      mime="text/csv")
        
            st.markdown("""---""")

            plot_bar.progress(0.15)
            
            @st.experimental_memo(suppress_st_warning=True)
            def drop_groups(Trader_DB_select):
                Trader_DB_select_pure = Trader_DB_select[(Trader_DB_select["Trader"] != "RMDS") &
                                                      (Trader_DB_select["Trader"] != "RMDSHWSP") & 
                                                      (Trader_DB_select["Trader"] != "Non-RMDSHWSP") & 
                                                      (Trader_DB_select["Trader"] != "Firm-All") & 
                                                      (Trader_DB_select["Trader"] != "Firm-Rates")]
                
                return Trader_DB_select_pure
            
            Trader_DB_select_pure = drop_groups(Trader_DB_select)
            
            st.header(":calendar: Analysis by Investment types")

            st.subheader("Firm Asset Class Performance")
            
            @st.experimental_memo(suppress_st_warning=True)
            def asset_class_pl(Trader_DB_select_pure):
                
                daily_asset = Trader_DB_select_pure.groupby(["Asset Class"]).aggregate("sum").T.sort_index() 
                
                daily_asset_cumsum = daily_asset.cumsum() 
                daily_asset_cumsum["Dates"]=daily_asset_cumsum.index
                daily_asset_cumsum = pd.melt(daily_asset_cumsum, id_vars="Dates", value_vars=daily_asset_cumsum.columns[:-1],
                                      var_name= "Assets" , value_name= "PNL")
                fig_asset_perf = px.line(daily_asset_cumsum, x="Dates", y="PNL", color = "Assets")
                
                return daily_asset_cumsum, fig_asset_perf
            
            daily_asset_cumsum, fig_asset_perf = asset_class_pl(Trader_DB_select_pure)
            
            st.plotly_chart(fig_asset_perf, use_container_width=True)
            
            with st.expander("See Data Table"):
                daily_asset_cumsum = daily_asset_cumsum.pivot(index='Dates', columns='Assets')
                st.dataframe(daily_asset_cumsum.style.format("{:,.0f}"))
                
                st.download_button(label="Export Table",
                  data=daily_asset_cumsum.to_csv(),
                  file_name= 'Asset_Class_Matrix.csv',
                  mime="text/csv")

            plot_bar.progress(0.2)
            st.subheader("Country Exposure Performance")
                
            top5_CE, top10_CE, get_all_CE = st.tabs(["Top_5", "Top_10", "All"])
            
            @st.experimental_memo(suppress_st_warning=True)
            def country_pl_data(Trader_DB_select_pure):
                
                daily_cty = Trader_DB_select_pure.groupby(["RiskCountry"]).aggregate("sum").T.sort_index() 
                daily_cty.fillna(0, inplace = True)
                
                return daily_cty
            
            daily_cty = country_pl_data(Trader_DB_select_pure)
                
            with top5_CE:
                
                @st.experimental_memo(suppress_st_warning=True)
                def country_pl_top5(daily_cty):
                    
                    daily_cty_cumsum = daily_cty.cumsum()
                    
                    bot_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).head(5).index)
                    top_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).tail(5).index)
                    daily_cty_cumsum = daily_cty_cumsum[bot_names + top_names]
                    daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                    daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                          var_name= "Country" , value_name= "PNL")
                    fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                    
                    return daily_cty_cumsum, fig_cty_perf
                
                daily_cty_cumsum, fig_cty_perf = country_pl_top5(daily_cty)
                
                top5_CE.plotly_chart(fig_cty_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    
                    daily_cty_cumsum = daily_cty_cumsum.pivot(index='Dates', columns='Country')
                    st.dataframe(daily_cty_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_cty_cumsum.to_csv(),
                      file_name= 'Country_Matrix.csv',
                      mime="text/csv")
                
            with top10_CE:
                
                @st.experimental_memo(suppress_st_warning=True)
                def country_pl_top10(daily_cty):
                    
                    daily_cty_cumsum = daily_cty.cumsum()
                    
                    bot_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).head(10).index)
                    top_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).tail(10).index)
                    daily_cty_cumsum = daily_cty_cumsum[bot_names + top_names]
                    daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                    daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                          var_name= "Country" , value_name= "PNL")
                    fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                    
                    return daily_cty_cumsum, fig_cty_perf
                
                daily_cty_cumsum, fig_cty_perf = country_pl_top10(daily_cty)
                
                top10_CE.plotly_chart(fig_cty_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_cty_cumsum = daily_cty_cumsum.pivot(index='Dates', columns='Country')
                    st.dataframe(daily_cty_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_cty_cumsum.to_csv(),
                      file_name= 'Country_Matrix.csv',
                      mime="text/csv")
                
            with get_all_CE:
                
                @st.experimental_memo(suppress_st_warning=True)
                def country_pl_all(daily_cty):
                    
                    daily_cty_cumsum = daily_cty.cumsum()
                    
                    daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                    daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                          var_name= "Country" , value_name= "PNL")
                    fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                    
                    return daily_cty_cumsum, fig_cty_perf
                
                daily_cty_cumsum, fig_cty_perf = country_pl_all(daily_cty)
                
                get_all_CE.plotly_chart(fig_cty_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_cty_cumsum = daily_cty_cumsum.pivot(index='Dates', columns='Country')
                    st.dataframe(daily_cty_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_cty_cumsum.to_csv(),
                      file_name= 'Country_Matrix.csv',
                      mime="text/csv")
            
            @st.experimental_memo(suppress_st_warning=True)
            def theme_pl_data(Trader_DB_select_pure):
                
                daily_theme = Trader_DB_select_pure.groupby(["Theme"]).aggregate("sum").T.sort_index() 
                daily_theme.fillna(0, inplace = True)
                
                return daily_theme
            
            daily_theme = theme_pl_data(Trader_DB_select_pure)

            plot_bar.progress(0.25)
            st.subheader("Firm's Themes Performance")
            
            top5_T, top10_T, get_all_T = st.tabs(["Top_5", "Top_10", "All"])
            
            with top5_T:
                
                @st.experimental_memo(suppress_st_warning=True)
                def theme_pl_top5(daily_theme):
                    
                    daily_theme_cumsum = daily_theme.cumsum()
                    bot_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).head(5).index)
                    top_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).tail(5).index)
                    daily_theme_cumsum = daily_theme_cumsum[bot_names + top_names]
                    daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                    daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                          var_name= "Theme" , value_name= "PNL")
            
                    fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                    
                    return daily_theme_cumsum, fig_theme_perf
                
                daily_theme_cumsum, fig_theme_perf = theme_pl_top5(daily_theme)
                
                top5_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_theme_cumsum = daily_theme_cumsum.pivot(index='Dates', columns='Theme')
                    st.dataframe(daily_theme_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_theme_cumsum.to_csv(),
                      file_name= 'Theme_Matrix.csv',
                      mime="text/csv")
                
            with top10_T:
                
                @st.experimental_memo(suppress_st_warning=True)
                def theme_pl_top10(daily_theme):
                    
                    daily_theme_cumsum = daily_theme.cumsum()
                    bot_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).head(10).index)
                    top_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).tail(10).index)
                    daily_theme_cumsum = daily_theme_cumsum[bot_names + top_names]
                    daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                    daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                          var_name= "Theme" , value_name= "PNL")
                    fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                    
                    return daily_theme_cumsum, fig_theme_perf
                
                daily_theme_cumsum, fig_theme_perf = theme_pl_top10(daily_theme)
                
                top10_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_theme_cumsum = daily_theme_cumsum.pivot(index='Dates', columns='Theme')
                    st.dataframe(daily_theme_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_theme_cumsum.to_csv(),
                      file_name= 'Theme_Matrix.csv',
                      mime="text/csv")
                
            with get_all_T:
                
                @st.experimental_memo(suppress_st_warning=True)
                def theme_pl_all(daily_theme):
                    
                    daily_theme_cumsum = daily_theme.cumsum()
                    daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                    daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                          var_name= "Theme" , value_name= "PNL")
                    fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                    
                    return daily_theme_cumsum, fig_theme_perf
                
                daily_theme_cumsum, fig_theme_perf = theme_pl_all(daily_theme)
                    
                get_all_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_theme_cumsum = daily_theme_cumsum.pivot(index='Dates', columns='Theme')
                    st.dataframe(daily_theme_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_theme_cumsum.to_csv(),
                      file_name= 'Theme_Matrix.csv',
                      mime="text/csv")
                
            @st.experimental_memo(suppress_st_warning=True)
            def assettype_pl_data(Trader_DB_select_pure):
                
                daily_asset_type = Trader_DB_select_pure.groupby(["Trade Category"]).aggregate("sum").T.sort_index() 
                daily_asset_type.fillna(0, inplace = True)
                
                return daily_asset_type
            
            daily_asset_type = assettype_pl_data(Trader_DB_select_pure)

            plot_bar.progress(0.3)
            st.subheader("Firm's Asset Type Performance")
            
            top5_A, top10_A, get_all_A = st.tabs(["Top_5", "Top_10", "All"])
            
            with top5_A:
                
                @st.experimental_memo(suppress_st_warning=True)
                def assettype_pl_top5(daily_asset_type):
                    
                    daily_asset_type_cumsum = daily_asset_type.cumsum()
                    bot_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).head(5).index)
                    top_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).tail(5).index)
                    daily_asset_type_cumsum = daily_asset_type_cumsum[bot_names + top_names]
                    daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                    daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                          var_name= "Asset Type" , value_name= "PNL")
                    fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                    
                    return daily_asset_type_cumsum, fig_asset_type_perf
                
                daily_asset_type_cumsum, fig_asset_type_perf = assettype_pl_top5(daily_asset_type)
                top5_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_asset_type_cumsum = daily_asset_type_cumsum.pivot(index='Dates', columns='Asset Type')
                    st.dataframe(daily_asset_type_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_asset_type_cumsum.to_csv(),
                      file_name= 'Asset_Type_Matrix.csv',
                      mime="text/csv")
                
            with top10_A:
                
                @st.experimental_memo(suppress_st_warning=True)
                def assettype_pl_top10(daily_asset_type):
                    
                    daily_asset_type_cumsum = daily_asset_type.cumsum()
                    bot_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).head(10).index)
                    top_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).tail(10).index)
                    daily_asset_type_cumsum = daily_asset_type_cumsum[bot_names + top_names]
                    daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                    daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                          var_name= "Asset Type" , value_name= "PNL")
                    fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                    
                    return daily_asset_type_cumsum, fig_asset_type_perf
                
                daily_asset_type_cumsum, fig_asset_type_perf = assettype_pl_top10(daily_asset_type)
                
                top10_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_asset_type_cumsum = daily_asset_type_cumsum.pivot(index='Dates', columns='Asset Type')
                    st.dataframe(daily_asset_type_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_asset_type_cumsum.to_csv(),
                      file_name= 'Asset_Type_Matrix.csv',
                      mime="text/csv")
                
            with get_all_A:
                
                @st.experimental_memo(suppress_st_warning=True)
                def assettype_pl_all(daily_asset_type):
                    
                    daily_asset_type_cumsum = daily_asset_type.cumsum()
                    daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                    daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                          var_name= "Asset Type" , value_name= "PNL")
                    fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                    return daily_asset_type_cumsum, fig_asset_type_perf
                
                daily_asset_type_cumsum, fig_asset_type_perf = assettype_pl_all(daily_asset_type)
                
                get_all_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
                
                with st.expander("See Data Table"):
                    daily_asset_type_cumsum = daily_asset_type_cumsum.pivot(index='Dates', columns='Asset Type')
                    st.dataframe(daily_asset_type_cumsum.style.format("{:,.0f}"))
                    
                    st.download_button(label="Export Table",
                      data=daily_asset_type_cumsum.to_csv(),
                      file_name= 'Asset_Type_Matrix.csv',
                      mime="text/csv")
            
            mcmm_table_firm, mcmm_table_rmdshwsp, ytd_pl_firm, ytd_pl_rmdshwsp, mcmm_pnl_time, out_time = get_MCMM_table(mcmm_pnl_path, tdb_path, mcmm_map, end_date)
            
            if mcmm_table_firm.empty and mcmm_table_rmdshwsp.empty and ytd_pl_firm == 0 and ytd_pl_rmdshwsp == 0:
                st.markdown("**pnl_output file not updated as of latest date**")
            else:
                plot_bar.progress(0.35)
                st.subheader("Firm's NAV Basis Point")
                st.markdown("MCMM-PL Data as of **" + str(mcmm_pnl_time) + "** and Out-PL Data as of **" + str(out_time) + "**")
                split1, split2 = st.columns(2)
                
                ytd_pl_firm = "{:,}".format(int(ytd_pl_firm))
                
                with split1:
                    annotated_text(("Firm - Rates", ""))
                    #st.markdown("**Firm - Rates**")
                    st.markdown("")
                    st.metric("YTD P/L (bps)", f"{ytd_pl_firm}")
                    st.dataframe(mcmm_table_firm.style.format({"Daily Bp": "{0:.0f}", "MTD bp": "{0:.0f}", "Nav/bp": "{0:.2f}"}))
                    
                ytd_pl_rmdshwsp = "{:,}".format(int(ytd_pl_rmdshwsp))
            
                with split2:
                    annotated_text(("RMDSHWSP", ""))
                    #st.markdown("**RMDSHWSP**")
                    st.markdown("")  
                    st.metric("YTD P/L (bps)", f"{ytd_pl_rmdshwsp}")
                    st.dataframe(mcmm_table_rmdshwsp.style.format({"Daily RMDSHWSP bp": "{0:.0f}", "MTD RMDSHWSP bp": "{0:.0f}", "Nav/bp RMDSHWSP": "{0:.2f}"}))
            
            st.markdown("""---""")
                
            # ---- SIDEBAR TRADER ----
            Trader_DB_selection = Trader_DB_select[Trader_DB_select['Trader'].isin(list(trader))]
            Trader_DB_ytd = Trader_DB_selection.drop(Trader_DB_selection.columns[7], axis=1)
            
            # ---- INFO ----
    
            st.header(":male-office-worker: Analysis by Trader")
            
            # TOP KPI's
            @st.experimental_memo(suppress_st_warning=True)
            def calc_metrics(Trader_DB_selection):
                
                cum_pnl = int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().cumsum().values[-1]) 
                change_cum_pnl = int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().cumsum().values[-1] - Trader_DB_ytd.groupby(by=["Trader"]).sum().T.sort_index().cumsum().values[-1]) 
                average_pnl = "{:,}".format(int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().mean().values[-1]))
                change_average_pnl = "{:,}".format(int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().mean().values[-1] - 
                                                              Trader_DB_ytd.groupby(by=["Trader"]).sum().T.sort_index().mean().values[-1]))
                greatest_drawdown = "{:,}".format(int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().min().values[-1]))
                change_greatest_drawdown = "{:,}".format(int(Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().min().values[-1] - 
                                                              Trader_DB_ytd.groupby(by=["Trader"]).sum().T.sort_index().min().values[-1]))
        
                return cum_pnl, change_cum_pnl, average_pnl, change_average_pnl, greatest_drawdown, change_greatest_drawdown
            
            cum_pnl, change_cum_pnl, average_pnl, change_average_pnl, greatest_drawdown, change_greatest_drawdown = calc_metrics(Trader_DB_selection)
            
            left_col, middle_col, right_col = st.columns(3)
            left_col.metric("Cumulative Returns", f"US $ {cum_pnl:,}", f"{change_cum_pnl:,} US $")
            middle_col.metric("Average Daily Return", f"US $ {average_pnl}", f"{change_average_pnl} US $")
            right_col.metric("Max Daily Loss", f"US $ {greatest_drawdown}", f"{change_greatest_drawdown} US $")
            
            st.markdown("""---""")
            
            plot_bar.progress(0.4)

            @st.cache
            def calc_beta(df):
                covariance = np.cov(df["Daily-pl"], df["Return"]) 
                return covariance[0,1]/covariance[1,1]
            
            @st.cache
            def rolling(df, period, function):
                result = pd.Series(np.nan, index=df.index)
                
                for i in range(1, len(df)+1):
                    df2 = df.iloc[max(i-period, 0):i,:] 
                    if len(df2) >= period:
                        idx = df2.index[-1]
                        result[idx] = function(df2)
                        
                return result
            
            @st.experimental_memo(suppress_st_warning=True)
            def func(x):
                return datetime.datetime.strptime(x.Dates, '%d/%m/%Y').strftime('%Y-%m-%d')
            
            @st.experimental_memo(suppress_st_warning=True)
            def get_metrics(Trader_DB_selection, spx, Freq):
                
                ps, pf = 125, 250
                
                if Freq == "Daily":
                    pl = Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index()
                    t, s, f = 60, 125, 250
                    period_break = 4
                elif Freq == "Weekly":
                    pl = Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().reset_index().groupby(by=[pd.Grouper(key='index', freq='W-FRI')]).sum()
                    t, s, f = 13, 26, 52
                    period_break = 20
                elif Freq == "Monthly":
                    pl = Trader_DB_selection.groupby(by=["Trader"]).sum().T.sort_index().reset_index().groupby(by=[pd.Grouper(key='index', freq='BM')]).sum()
                    t, s, f = 3, 6, 12
                    period_break = 80
                    
                cum_pl = pl.cumsum()
                
                if Freq == "Daily":
                    ret = (cum_pl.diff()/cum_pl.abs().shift()).iloc[2:, :] 
                else:
                    ret = (cum_pl.diff()/cum_pl.abs().shift()).iloc[1:, :] 
                
                vol_60 = pl.rolling(t).std()
                vol_125 = pl.rolling(s).std()
                vol_250 = pl.rolling(f).std()

                vol_inception_list = [pl[:i+1].rolling(i+1).std().iloc[-1:] for i in range(1, len(pl))]
                vol_inception = pd.concat(vol_inception_list, axis = 0)

                dd = cum_pl.diff(axis = 0, periods = 1).dropna().cummin()

                if np.busday_count(start_date, end_date) <= ps:
                    dd_125 = pd.DataFrame()
                else:
                    dd_125 = pd.concat([cum_pl.diff(axis = 0, periods = 1).dropna()[i:i+s].rolling(s).min().iloc[-1:] for i in range(len(cum_pl) - s)], axis = 0)
                if np.busday_count(start_date, end_date) <= pf:
                    dd_250 = pd.DataFrame()
                else:
                    dd_250 = pd.concat([cum_pl.diff(axis = 0, periods = 1).dropna()[i:i+f].rolling(f).min().iloc[-1:] for i in range(len(cum_pl) - f)], axis = 0)
                
                if np.busday_count(start_date, end_date) >= period_break:
                    ret_mean_list = [ret[:i+1].rolling(i+1).mean().iloc[-1:] for i in range(1, len(ret))]
                    ret_mean = pd.concat(ret_mean_list, axis = 0)
                    ret_std_list = [ret[:i+1].rolling(i+1).std().iloc[-1:] for i in range(1, len(ret))]
                    ret_std = pd.concat(ret_std_list, axis = 0)
                    sharpe_cum = ret_mean/ret_std
                else:
                    sharpe_cum = pd.DataFrame()
                
                #Daily sharpe
                sharpe_6m = ret.rolling(s).mean()/ret.rolling(s).std()
                sharpe_1y = ret.rolling(f).mean()/ret.rolling(f).std()
                
                if Freq == "Daily":
                    ret = ret.reset_index()
                    ret['index'] = ret['index'].astype(str).str[:10]
                    ret['index'] = pd.to_datetime(ret['index']).dt.strftime('%d/%m/%Y') 
                else:
                    spx['Dates'] = spx.apply(func, axis=1)
                    spx['Dates'] = pd.to_datetime(spx['Dates'])
                    spx['Return'] = spx['Return'].astype(float)
                    if Freq == "Weekly":
                        spx = spx.groupby(by=[pd.Grouper(key='Dates', freq='W-FRI')]).sum()
                    elif Freq == "Monthly":
                        spx = spx.groupby(by=[pd.Grouper(key='Dates', freq='BM')]).sum()
                    ret = ret.reset_index()
    
                #Daily Beta
                ret.rename(columns = {ret.columns[0]: "Dates", ret.columns[1]: "Daily-pl"}, inplace = True)
                cov_df = spx.merge(ret, how='inner', on='Dates')
                cov_df.dropna(inplace = True)
                cov_df["Return"] = cov_df["Return"].astype(float)
                
                beta_3m = rolling(cov_df, t, calc_beta)
                beta_6m = rolling(cov_df, s, calc_beta)
                beta_1y = rolling(cov_df, f, calc_beta)
                if np.busday_count(start_date, end_date) >= period_break:
                    beta_inception = pd.concat([rolling(cov_df[:i+1],i+1,calc_beta).iloc[-1:] for i in range(1, len(cov_df))], axis = 0)
                else:
                    beta_inception = pd.DataFrame()

                return pl, cum_pl, vol_60, vol_125, vol_250, vol_inception, dd, dd_125, dd_250, sharpe_cum, sharpe_6m, sharpe_1y, beta_3m, beta_6m, beta_1y, beta_inception             
        
            if np.busday_count(start_date, end_date) >= 2:
                
                st.subheader("Daily Stats")
                
                spx = spx_ret()
                
                daily_pl, daily_cum_pl, daily_vol_60, daily_vol_125, daily_vol_250, daily_vol_inception,\
                    daily_dd, daily_dd_125, daily_dd_250, daily_sharpe_cum, daily_sharpe_6m, \
                        daily_sharpe_1y, daily_beta_3m, daily_beta_6m, daily_beta_1y, \
                            daily_beta_inception = get_metrics(Trader_DB_selection, spx, "Daily")             
                
                tab11, tab12, tab13, tab14, tab15 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe", "Beta"])
                
                # PNL OVER TIME [LINE CHART]
                with tab11:
                    
                    tab11.subheader("Trader's Cumulative PNL")
                    
                    @st.experimental_memo(suppress_st_warning=True)
                    def daily_cumpl(daily_pl, daily_cum_pl):
                        
                        daily_roll_pnl = pd.concat([daily_pl, daily_cum_pl], axis = 1, join='outer')
                        daily_roll_pnl.columns = ['Returns', 'Cumulative Returns']
                        daily_roll_pnl["Dates"]=daily_roll_pnl.index
                        daily_roll_pnl_cum = daily_roll_pnl.drop(['Returns'], axis=1)
                        daily_rolling_PNL = pd.melt(daily_roll_pnl_cum, id_vars ="Dates", value_vars =list(daily_roll_pnl_cum.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "pl")
                        
                        fig_daily_cum_pl = px.line(
                            daily_rolling_PNL,
                            x="Dates",
                            y="pl",
                            color = "Rolling days",
                            title="<b>Cumulative PL</b>",
                            template="plotly_white",
                        )
                        
                        fig_daily_cum_pl.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        fig_daily_cum_pl.update_xaxes(
                                rangebreaks=[dict(bounds=["sat", "mon"]),])
                        
                        return daily_roll_pnl, fig_daily_cum_pl
                    
                    daily_roll_pnl, fig_daily_cum_pl = daily_cumpl(daily_pl, daily_cum_pl)
                    
                    tab11.plotly_chart(fig_daily_cum_pl, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = daily_roll_pnl.pop('Dates')
                        ret_col = daily_roll_pnl.columns[0]
                        cum_col = daily_roll_pnl.columns[1]
                        daily_roll_pnl[list(daily_roll_pnl.columns)] = 5 * round(daily_roll_pnl[list(daily_roll_pnl.columns)]/1000/5) * 1000
                        st.dataframe(daily_roll_pnl.style.format({str(ret_col): "{:,.0f}", str(cum_col): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                          data=daily_roll_pnl.to_csv(),
                          file_name= 'Daily_PL.csv',
                          mime="text/csv")

                plot_bar.progress(0.45)

                with tab12:
                    
                    tab12.subheader("Trader's Volatility")
                    
                    @st.experimental_memo(suppress_st_warning=True)
                    def daily_vol(daily_vol_60, daily_vol_125, daily_vol_250, daily_vol_inception):
                        
                        daily_roll_vol = pd.concat([daily_vol_60, daily_vol_125, daily_vol_250, daily_vol_inception], axis = 1, join='outer')
                        daily_roll_vol.columns = ['Vol 60', 'Vol 125', 'Vol 250', 'Vol Inception']
                        daily_roll_vol["Dates"]=daily_roll_vol.index
                        daily_rolling_VOL = pd.melt(daily_roll_vol, id_vars ="Dates", value_vars =list(daily_roll_vol.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "vol")
                        
                        fig_daily_vol = px.line(
                            daily_rolling_VOL,
                            x="Dates",
                            y="vol",
                            color = "Rolling days",
                            title="<b>Rolling Volatility</b>",
                            template="plotly_white",
                        )
                        
                        fig_daily_vol.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        # fig_daily_vol.update_xaxes(
                        #         rangebreaks=[dict(bounds=["sat", "mon"]),])
                        
                        return daily_roll_vol, fig_daily_vol
                    
                    daily_roll_vol, fig_daily_vol = daily_vol(daily_vol_60, daily_vol_125, daily_vol_250, daily_vol_inception)
                    tab12.plotly_chart(fig_daily_vol, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = daily_roll_vol.pop('Dates')
                        vol_col_60 = daily_roll_vol.columns[0]
                        vol_col_125 = daily_roll_vol.columns[1]
                        vol_col_250 = daily_roll_vol.columns[2]
                        vol_col_inc = daily_roll_vol.columns[3]
                        daily_roll_vol[list(daily_roll_vol.columns)] = 5 * round(daily_roll_vol[list(daily_roll_vol.columns)]/1000/5) * 1000
                        st.dataframe(daily_roll_vol.style.format({str(vol_col_60): "{:,.0f}", str(vol_col_125): "{:,.0f}", str(vol_col_250): "{:,.0f}", str(vol_col_inc): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                          data=daily_roll_vol.to_csv(),
                          file_name= 'Daily_Vol.csv',
                          mime="text/csv")
                        
                with tab13:
                    
                    tab13.subheader("Trader's Max Drawdown")
                    
                    daily_roll_dd = pd.concat([daily_dd, daily_dd_125, daily_dd_250], axis = 1, join='outer')
    
                    if np.busday_count(start_date, end_date) <= 125:
                        daily_roll_dd.columns = ['MDD']
                    elif np.busday_count(start_date, end_date) <= 250:
                        daily_roll_dd.columns = ['MDD', 'MDD 125']
                    else:
                        daily_roll_dd.columns = ['MDD', 'MDD 125', 'MDD 250']
                    daily_roll_dd["Dates"]=daily_roll_dd.index
                    daily_rolling_DD = pd.melt(daily_roll_dd, id_vars ="Dates", value_vars =list(daily_roll_dd.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "DD")
                    
                    fig_daily_dd = px.line(
                        daily_rolling_DD,
                        x="Dates",
                        y="DD",
                        color = "Rolling days",
                        title="<b>Drawdown</b>",
                        template="plotly_white",
                    )
                    
                    fig_daily_dd.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    # fig_daily_dd.update_xaxes(
                    #         rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab13.plotly_chart(fig_daily_dd, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = daily_roll_dd.pop('Dates')
                        if np.busday_count(start_date, end_date) <= 125:
                            dd_col = daily_roll_dd.columns[0]
                            daily_roll_dd[list(daily_roll_dd.columns)] = 5 * round(daily_roll_dd[list(daily_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(daily_roll_dd.style.format({str(dd_col): "{:,.0f}"}))
                        elif np.busday_count(start_date, end_date) <= 250:
                            dd_col = daily_roll_dd.columns[0]
                            dd_col_125 = daily_roll_dd.columns[1]
                            daily_roll_dd[list(daily_roll_dd.columns)] = 5 * round(daily_roll_dd[list(daily_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(daily_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}"}))
                        else:
                            dd_col = daily_roll_dd.columns[0]
                            dd_col_125 = daily_roll_dd.columns[1]
                            dd_col_250 = daily_roll_dd.columns[2]
                            daily_roll_dd[list(daily_roll_dd.columns)] = 5 * round(daily_roll_dd[list(daily_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(daily_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}", str(dd_col_250): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                          data=daily_roll_dd.to_csv(),
                          file_name= 'Daily_DD.csv',
                          mime="text/csv")
                
                with tab14:
                    if len(daily_sharpe_cum) != 0:
                        tab14.subheader("Trader's Sharpe Ratio")
    
                        daily_roll_sharpe = pd.concat([daily_sharpe_6m, daily_sharpe_1y, daily_sharpe_cum], axis = 1, join='outer')
                        daily_roll_sharpe.columns = ['Sharpe 6m', 'Sharpe 1y', 'Sharpe Cumulative']
                        daily_roll_sharpe["Dates"]=daily_roll_sharpe.index
                        daily_rolling_SHARPE = pd.melt(daily_roll_sharpe, id_vars ="Dates", value_vars =list(daily_roll_sharpe.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "sharpe")
                        
                        fig_daily_sharpe = px.line(
                            daily_rolling_SHARPE,
                            x="Dates",
                            y="sharpe",
                            color = "Rolling days",
                            title="<b>Sharpe Ratio</b>",
                            template="plotly_white",
                        )
                        
                        fig_daily_sharpe.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        # fig_daily_sharpe.update_xaxes(
                        #         rangebreaks=[dict(bounds=["sat", "mon"]),])
                        
                        tab14.plotly_chart(fig_daily_sharpe, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = daily_roll_sharpe.pop('Dates')
                            daily_roll_sharpe = daily_roll_sharpe.applymap('{:,.2f}'.format)
                            st.dataframe(daily_roll_sharpe)
                            
                            st.download_button(label="Export Table",
                              data=daily_roll_sharpe.to_csv(),
                              file_name= 'Daily_Sharpe.csv',
                              mime="text/csv")
                
                    else:
                        st.warning('Not enough data to calculate Sharpe')
                    
                with tab15:
                    if len(daily_beta_inception) != 0:
                        
                        tab15.subheader("Trader's Beta with SPX")
                        
                        daily_roll_beta = pd.concat([daily_beta_3m, daily_beta_6m, daily_beta_1y, daily_beta_inception], axis = 1, join='outer')
                        daily_roll_beta.columns = ['Beta 3m', 'Beta 6m', 'Beta 1y', 'Beta Inception']
                        daily_roll_beta["Dates"]=daily_roll_beta.index
                        daily_rolling_BETA = pd.melt(daily_roll_beta, id_vars ="Dates", value_vars =list(daily_roll_beta.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "beta")
                        
                        fig_daily_beta = px.line(
                            daily_rolling_BETA,
                            x="Dates",
                            y="beta",
                            color = "Rolling days",
                            title="<b>Beta with SPX</b>",
                            template="plotly_white",
                        )
                        
                        fig_daily_beta.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        tab15.plotly_chart(fig_daily_beta, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = daily_roll_beta.pop('Dates')
                            daily_roll_beta = daily_roll_beta.applymap('{:,.2f}'.format)
                            st.dataframe(daily_roll_beta)
                            
                            st.download_button(label="Export Table",
                              data=daily_roll_beta.to_csv(),
                              file_name= 'Daily_Beta.csv',
                              mime="text/csv")
            
                    else:
                        st.warning('Not enough data to calculate Beta')

            plot_bar.progress(0.5)
            if np.busday_count(start_date, end_date) >= 10:
    
                st.subheader("Weekly Stats")
                
                spx = spx_ret()

                weekly_pl, weekly_cum_pl, weekly_vol_60, weekly_vol_125, weekly_vol_250, weekly_vol_inception,\
                    weekly_dd, weekly_dd_125, weekly_dd_250, weekly_sharpe_cum, weekly_sharpe_6m, \
                        weekly_sharpe_1y, weekly_beta_3m, weekly_beta_6m, weekly_beta_1y, \
                            weekly_beta_inception = get_metrics(Trader_DB_selection, spx, "Weekly") 
                            
                tab16, tab17, tab18, tab19, tab20 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe", "Beta"])
                
                # PNL OVER TIME [LINE CHART]
                with tab16:
                    
                    tab16.subheader("Trader's Cumulative PNL")
                    
                    weekly_roll_pnl = pd.concat([weekly_pl, weekly_cum_pl], axis = 1, join='outer')
                    weekly_roll_pnl.columns = ['Returns', 'Cumulative Returns']
                    weekly_roll_pnl["Dates"]=weekly_roll_pnl.index
                    weekly_roll_pnl_cum = weekly_roll_pnl.drop(['Returns'], axis=1)
                    weekly_rolling_PNL = pd.melt(weekly_roll_pnl_cum, id_vars ="Dates", value_vars =list(weekly_roll_pnl_cum.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "pl")
        
                    fig_weekly_cum_pl = px.line(
                        weekly_rolling_PNL,
                        x="Dates",
                        y="pl",
                        color = "Rolling days",
                        title="<b>Cumulative PL</b>",
                        template="plotly_white",
                    )
                    
                    fig_weekly_cum_pl.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_weekly_cum_pl.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab16.plotly_chart(fig_weekly_cum_pl, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = weekly_roll_pnl.pop('Dates')
                        ret_col = weekly_roll_pnl.columns[0]
                        cum_col = weekly_roll_pnl.columns[1]
                        weekly_roll_pnl[list(weekly_roll_pnl.columns)] = 5 * round(weekly_roll_pnl[list(weekly_roll_pnl.columns)]/1000/5) * 1000
                        st.dataframe(weekly_roll_pnl.style.format({str(ret_col): "{:,.0f}", str(cum_col): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=weekly_roll_pnl.to_csv(),
                              file_name= 'Weekly_PL.csv',
                              mime="text/csv")

                plot_bar.progress(0.55)
                    
                with tab17:
                    
                    tab17.subheader("Trader's Volatility")
                    
                    weekly_roll_vol = pd.concat([weekly_vol_60, weekly_vol_125, weekly_vol_250, weekly_vol_inception], axis = 1, join='outer')
                    weekly_roll_vol.columns = ['Vol 13', 'Vol 26', 'Vol 52', 'Vol Inception']
                    weekly_roll_vol["Dates"]=weekly_roll_vol.index
                    weekly_rolling_VOL = pd.melt(weekly_roll_vol, id_vars ="Dates", value_vars =list(weekly_roll_vol.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "vol")
                    
                    fig_weekly_vol = px.line(
                        weekly_rolling_VOL,
                        x="Dates",
                        y="vol",
                        color = "Rolling days",
                        title="<b>Rolling Volatility</b>",
                        template="plotly_white",
                    )
                    
                    fig_weekly_vol.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_weekly_vol.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab17.plotly_chart(fig_weekly_vol, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = weekly_roll_vol.pop('Dates')
                        vol_col_60 = weekly_roll_vol.columns[0]
                        vol_col_125 = weekly_roll_vol.columns[1]
                        vol_col_250 = weekly_roll_vol.columns[2]
                        vol_col_inc = weekly_roll_vol.columns[3]
                        weekly_roll_vol[list(weekly_roll_vol.columns)] = 5 * round(weekly_roll_vol[list(weekly_roll_vol.columns)]/1000/5) * 1000
                        st.dataframe(weekly_roll_vol.style.format({str(vol_col_60): "{:,.0f}", str(vol_col_125): "{:,.0f}", str(vol_col_250): "{:,.0f}", str(vol_col_inc): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=weekly_roll_vol.to_csv(),
                              file_name= 'Weekly_Vol.csv',
                              mime="text/csv")
                        
                with tab18:
                    
                    tab18.subheader("Trader's Max Drawdown")
                    
                    weekly_roll_dd = pd.concat([weekly_dd, weekly_dd_125, weekly_dd_250], axis = 1, join='outer')
                    if np.busday_count(start_date, end_date) <= 125:
                        weekly_roll_dd.columns = ['MDD']
                    elif np.busday_count(start_date, end_date) <= 250:
                        weekly_roll_dd.columns = ['MDD', 'MDD 26']
                    else:
                        weekly_roll_dd.columns = ['MDD', 'MDD 26', 'MDD 52']
                    weekly_roll_dd["Dates"]=weekly_roll_dd.index
                    weekly_rolling_DD = pd.melt(weekly_roll_dd, id_vars ="Dates", value_vars =list(weekly_roll_dd.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "DD")
                    
                    fig_weekly_dd = px.line(
                        weekly_rolling_DD,
                        x="Dates",
                        y="DD",
                        color = "Rolling days",
                        title="<b>Drawdown</b>",
                        template="plotly_white",
                    )
                    
                    fig_weekly_dd.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_weekly_dd.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab18.plotly_chart(fig_weekly_dd, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = weekly_roll_dd.pop('Dates')
                        if np.busday_count(start_date, end_date) <= 125:
                            dd_col = weekly_roll_dd.columns[0]
                            weekly_roll_dd[list(weekly_roll_dd.columns)] = 5 * round(weekly_roll_dd[list(weekly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(weekly_roll_dd.style.format({str(dd_col): "{:,.0f}"}))
                        elif np.busday_count(start_date, end_date) <= 250:
                            dd_col = weekly_roll_dd.columns[0]
                            dd_col_125 = weekly_roll_dd.columns[1]
                            weekly_roll_dd[list(weekly_roll_dd.columns)] = 5 * round(weekly_roll_dd[list(weekly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(weekly_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}"}))
                        else:
                            dd_col = weekly_roll_dd.columns[0]
                            dd_col_125 = weekly_roll_dd.columns[1]
                            dd_col_250 = weekly_roll_dd.columns[2]
                            weekly_roll_dd[list(weekly_roll_dd.columns)] = 5 * round(weekly_roll_dd[list(weekly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(weekly_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}", str(dd_col_250): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=weekly_roll_dd.to_csv(),
                              file_name= 'Weekly_DD.csv',
                              mime="text/csv")
                        
                with tab19:
                    if len(weekly_sharpe_cum) != 0:
                        
                        tab19.subheader("Trader's Sharpe Ratio")
                        
                        weekly_roll_sharpe = pd.concat([weekly_sharpe_6m, weekly_sharpe_1y, weekly_sharpe_cum], axis = 1, join='outer')
                        weekly_roll_sharpe.columns = ['Sharpe 6m', 'Sharpe 1y', 'Sharpe Cumulative']
                        weekly_roll_sharpe["Dates"]=weekly_roll_sharpe.index
                        weekly_rolling_SHARPE = pd.melt(weekly_roll_sharpe, id_vars ="Dates", value_vars =list(weekly_roll_sharpe.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "sharpe")
                        
                        fig_weekly_sharpe = px.line(
                            weekly_rolling_SHARPE,
                            x="Dates",
                            y="sharpe",
                            color = "Rolling days",
                            title="<b>Sharpe Ratio</b>",
                            template="plotly_white",
                        )
                        
                        fig_weekly_sharpe.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        fig_weekly_sharpe.update_xaxes(
                                rangebreaks=[dict(bounds=["sat", "mon"]),])
                        
                        tab19.plotly_chart(fig_weekly_sharpe, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = weekly_roll_sharpe.pop('Dates')
                            weekly_roll_sharpe = weekly_roll_sharpe.applymap('{:,.2f}'.format)
                            st.dataframe(weekly_roll_sharpe)
                            
                            st.download_button(label="Export Table",
                                  data=weekly_roll_sharpe.to_csv(),
                                  file_name= 'Weekly_Sharpe.csv',
                                  mime="text/csv")
                        
                    else:
                        st.warning('Not enough data to calculate Sharpe')
                    
                with tab20:
                    if len(weekly_beta_inception) != 0:
                        
                        tab20.subheader("Trader's Beta with SPX")
                        
                        weekly_roll_beta = pd.concat([weekly_beta_3m, weekly_beta_6m, weekly_beta_1y, weekly_beta_inception], axis = 1, join='outer')
                        weekly_roll_beta.columns = ['Beta 3m', 'Beta 6m', 'Beta 1y', 'Beta Inception']
                        weekly_roll_beta["Dates"]=weekly_roll_beta.index
                        weekly_rolling_BETA = pd.melt(weekly_roll_beta, id_vars ="Dates", value_vars =list(weekly_roll_beta.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "beta")
                        
                        fig_weekly_beta = px.line(
                            weekly_rolling_BETA,
                            x="Dates",
                            y="beta",
                            color = "Rolling days",
                            title="<b>Beta with SPX</b>",
                            template="plotly_white",
                        )
                        
                        fig_weekly_beta.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        tab20.plotly_chart(fig_weekly_beta, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = weekly_roll_beta.pop('Dates')
                            weekly_roll_beta = weekly_roll_beta.applymap('{:,.2f}'.format)
                            st.dataframe(weekly_roll_beta)
                            
                            st.download_button(label="Export Table",
                                  data=weekly_roll_beta.to_csv(),
                                  file_name= 'Weekly_Beta.csv',
                                  mime="text/csv")
                    else:
                        st.warning('Not enough data to calculate Beta')

            plot_bar.progress(0.6)
            if np.busday_count(start_date, end_date) >= 40:
    
                st.subheader("Monthly Stats")
                
                spx = spx_ret()

                monthly_pl, monthly_cum_pl, monthly_vol_60, monthly_vol_125, monthly_vol_250, \
                    monthly_vol_inception, monthly_dd, monthly_dd_125, monthly_dd_250, \
                        monthly_sharpe_cum, monthly_sharpe_6m, monthly_sharpe_1y, monthly_beta_3m, \
                            monthly_beta_6m, monthly_beta_1y, monthly_beta_inception = get_metrics(Trader_DB_selection, spx, "Monthly") 
                    
                tab21, tab22, tab23, tab24, tab25 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe", "Beta"])
            
                # PNL OVER TIME [LINE CHART]
                with tab21:
                    
                    tab21.subheader("Trader's Cumulative PNL")
                    
                    monthly_roll_pnl = pd.concat([monthly_pl, monthly_cum_pl], axis = 1, join='outer')
                    monthly_roll_pnl.columns = ['Returns', 'Cumulative Returns']
                    monthly_roll_pnl["Dates"]=monthly_roll_pnl.index
                    monthly_roll_pnl_cum = monthly_roll_pnl.drop(['Returns'], axis=1)
                    monthly_rolling_PNL = pd.melt(monthly_roll_pnl_cum, id_vars ="Dates", value_vars =list(monthly_roll_pnl_cum.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "pl")
                    
                    fig_monthly_cum_pl = px.line(
                        monthly_rolling_PNL,
                        x="Dates",
                        y="pl",
                        color = "Rolling days",
                        title="<b>Cumulative PL</b>",
                        template="plotly_white",
                    )
                    
                    fig_monthly_cum_pl.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_monthly_cum_pl.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab21.plotly_chart(fig_monthly_cum_pl, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = monthly_roll_pnl.pop('Dates')
                        ret_col = monthly_roll_pnl.columns[0]
                        cum_col = monthly_roll_pnl.columns[1]
                        monthly_roll_pnl[list(monthly_roll_pnl.columns)] = 5 * round(monthly_roll_pnl[list(monthly_roll_pnl.columns)]/1000/5) * 1000
                        st.dataframe(monthly_roll_pnl.style.format({str(ret_col): "{:,.0f}", str(cum_col): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=monthly_roll_pnl.to_csv(),
                              file_name= 'Monthly_PL.csv',
                              mime="text/csv")

                plot_bar.progress(0.65)
                    
                with tab22:
                    
                    tab22.subheader("Trader's Volatility")
                    
                    monthly_roll_vol = pd.concat([monthly_vol_60, monthly_vol_125, monthly_vol_250, monthly_vol_inception], axis = 1, join='outer')
                    monthly_roll_vol.columns = ['Vol 3', 'Vol 6', 'Vol 12', 'Vol Inception']
                    monthly_roll_vol["Dates"]=monthly_roll_vol.index
                    monthly_rolling_VOL = pd.melt(monthly_roll_vol, id_vars ="Dates", value_vars =list(monthly_roll_vol.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "vol")
                    
                    fig_monthly_vol = px.line(
                        monthly_rolling_VOL,
                        x="Dates",
                        y="vol",
                        color = "Rolling days",
                        title="<b>Rolling Volatility</b>",
                        template="plotly_white",
                    )
                    
                    fig_monthly_vol.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_monthly_vol.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab22.plotly_chart(fig_monthly_vol, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = monthly_roll_vol.pop('Dates')
                        vol_col_60 = monthly_roll_vol.columns[0]
                        vol_col_125 = monthly_roll_vol.columns[1]
                        vol_col_250 = monthly_roll_vol.columns[2]
                        vol_col_inc = monthly_roll_vol.columns[3]
                        monthly_roll_vol[list(monthly_roll_vol.columns)] = 5 * round(monthly_roll_vol[list(monthly_roll_vol.columns)]/1000/5) * 1000
                        st.dataframe(monthly_roll_vol.style.format({str(vol_col_60): "{:,.0f}", str(vol_col_125): "{:,.0f}", str(vol_col_250): "{:,.0f}", str(vol_col_inc): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=monthly_roll_vol.to_csv(),
                              file_name= 'Monthly_Vol.csv',
                              mime="text/csv")
                        
                with tab23:
                    
                    tab23.subheader("Trader's Max Drawdown")
                    
                    monthly_roll_dd = pd.concat([monthly_dd, monthly_dd_125, monthly_dd_250], axis = 1, join='outer')
                    if np.busday_count(start_date, end_date) <= 125:
                        monthly_roll_dd.columns = ['MDD']
                    elif np.busday_count(start_date, end_date) <= 250:
                        monthly_roll_dd.columns = ['MDD', 'MDD 6']
                    else:
                        monthly_roll_dd.columns = ['MDD', 'MDD 6', 'MDD 12']
                    monthly_roll_dd["Dates"]=monthly_roll_dd.index
                    monthly_rolling_DD = pd.melt(monthly_roll_dd, id_vars ="Dates", value_vars =list(monthly_roll_dd.columns[:-1]),
                                        var_name= "Rolling days" , value_name= "DD")
                    
                    fig_monthly_dd = px.line(
                        monthly_rolling_DD,
                        x="Dates",
                        y="DD",
                        color = "Rolling days",
                        title="<b>Drawdown</b>",
                        template="plotly_white",
                    )
                    
                    fig_monthly_dd.update_layout(
                        updatemenus=[
                    		dict(
                     			type="buttons",
                     			direction="left",
                     			buttons=list([
                    				dict(
                     					args=["type", "line"],
                     					label="Line Plot",
                     					method="restyle"
                    				),
                    				dict(
                     					args=["type", "bar"],
                     					label="Bar Chart",
                     					method="restyle"
                    				)
                     			]),
                    		),
                     	],
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    fig_monthly_dd.update_xaxes(
                            rangebreaks=[dict(bounds=["sat", "mon"]),])
                    
                    tab23.plotly_chart(fig_monthly_dd, use_container_width=True)
                    
                    with st.expander("See Data Table"):
                        first_column = monthly_roll_dd.pop('Dates')
                        if np.busday_count(start_date, end_date) <= 125:
                            dd_col = monthly_roll_dd.columns[0]
                            monthly_roll_dd[list(monthly_roll_dd.columns)] = 5 * round(monthly_roll_dd[list(monthly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(monthly_roll_dd.style.format({str(dd_col): "{:,.0f}"}))
                        elif np.busday_count(start_date, end_date) <= 250:
                            dd_col = monthly_roll_dd.columns[0]
                            dd_col_125 = monthly_roll_dd.columns[1]
                            monthly_roll_dd[list(monthly_roll_dd.columns)] = 5 * round(monthly_roll_dd[list(monthly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(monthly_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}"}))
                        else:
                            dd_col = monthly_roll_dd.columns[0]
                            dd_col_125 = monthly_roll_dd.columns[1]
                            dd_col_250 = monthly_roll_dd.columns[2]
                            monthly_roll_dd[list(monthly_roll_dd.columns)] = 5 * round(monthly_roll_dd[list(monthly_roll_dd.columns)]/1000/5) * 1000
                            st.dataframe(monthly_roll_dd.style.format({str(dd_col): "{:,.0f}", str(dd_col_125): "{:,.0f}", str(dd_col_250): "{:,.0f}"}))
                        
                        st.download_button(label="Export Table",
                              data=monthly_roll_dd.to_csv(),
                              file_name= 'Monthly_DD.csv',
                              mime="text/csv")
                
                with tab24:
                    if len(monthly_sharpe_cum) != 0:
                        
                        tab24.subheader("Trader's Sharpe Ratio")
    
                        monthly_roll_sharpe = pd.concat([monthly_sharpe_6m, monthly_sharpe_1y, monthly_sharpe_cum], axis = 1, join='outer')
                        monthly_roll_sharpe.columns = ['Sharpe 6m', 'Sharpe 1y', 'Sharpe Cumulative']
                        monthly_roll_sharpe["Dates"]=monthly_roll_sharpe.index
                        monthly_rolling_SHARPE = pd.melt(monthly_roll_sharpe, id_vars ="Dates", value_vars =list(monthly_roll_sharpe.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "sharpe")
                        
                        fig_monthly_sharpe = px.line(
                            monthly_rolling_SHARPE,
                            x="Dates",
                            y="sharpe",
                            color = "Rolling days",
                            title="<b>Sharpe Ratio</b>",
                            template="plotly_white",
                        )
                        
                        fig_monthly_sharpe.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        fig_monthly_sharpe.update_xaxes(
                                rangebreaks=[dict(bounds=["sat", "mon"]),])
                        
                        tab24.plotly_chart(fig_monthly_sharpe, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = monthly_roll_sharpe.pop('Dates')
                            monthly_roll_sharpe = monthly_roll_sharpe.applymap('{:,.2f}'.format)
                            st.dataframe(monthly_roll_sharpe)
                            
                            st.download_button(label="Export Table",
                                  data=monthly_roll_sharpe.to_csv(),
                                  file_name= 'Monthly_Sharpe.csv',
                                  mime="text/csv")
                    else:
                        st.warning('Not enough data to calculate Sharpe')
                       
                with tab25:
                    if len(monthly_beta_inception) != 0:  
                        
                        tab25.subheader("Trader's Beta with SPX")
                        
                        monthly_roll_beta = pd.concat([monthly_beta_3m, monthly_beta_6m, monthly_beta_1y, monthly_beta_inception], axis = 1, join='outer')
                        monthly_roll_beta.columns = ['Beta 3m', 'Beta 6m', 'Beta 1y', 'Beta Inception']
                        monthly_roll_beta["Dates"]=monthly_roll_beta.index
                        monthly_rolling_BETA = pd.melt(monthly_roll_beta, id_vars ="Dates", value_vars =list(monthly_roll_beta.columns[:-1]),
                                            var_name= "Rolling days" , value_name= "beta")
                        
                        fig_monthly_beta = px.line(
                            monthly_rolling_BETA,
                            x="Dates",
                            y="beta",
                            color = "Rolling days",
                            title="<b>Beta with SPX</b>",
                            template="plotly_white",
                        )
                        
                        fig_monthly_beta.update_layout(
                            updatemenus=[
                        		dict(
                         			type="buttons",
                         			direction="left",
                         			buttons=list([
                        				dict(
                         					args=["type", "line"],
                         					label="Line Plot",
                         					method="restyle"
                        				),
                        				dict(
                         					args=["type", "bar"],
                         					label="Bar Chart",
                         					method="restyle"
                        				)
                         			]),
                        		),
                         	],
                            plot_bgcolor="rgba(0,0,0,0)",
                            xaxis=(dict(showgrid=False))
                        )
                        
                        tab25.plotly_chart(fig_monthly_beta, use_container_width=True)
                        
                        with st.expander("See Data Table"):
                            first_column = monthly_roll_beta.pop('Dates')
                            monthly_roll_beta = monthly_roll_beta.applymap('{:,.2f}'.format)
                            st.dataframe(monthly_roll_beta)
                            
                            st.download_button(label="Export Table",
                                  data=monthly_roll_beta.to_csv(),
                                  file_name= 'Monthly_Beta.csv',
                                  mime="text/csv")
                    else:
                        st.warning('Not enough data to calculate Beta')
                    
            st.markdown("""---""")

            plot_bar.progress(0.7)
            
            @st.experimental_memo(suppress_st_warning=True)
            def corr_selected(Trader_DB_selection, days):
                
                Trader_Order = Trader_DB_selection.groupby(["Theme"]).aggregate("sum").T.reset_index()
                theme_order = Trader_Order[((Trader_Order['index'].dt.date >= end_date + datetime.timedelta(-days)) & (Trader_Order['index'].dt.date <= end_date))]
                theme_order.set_index('index', inplace = True)
                
                theme_order = pd.merge(theme_order, Trader_DB_selection.groupby(["Trader"]).sum().T, left_index=True, right_index=True)
                theme_order.rename(columns = {theme_order.columns[-1]: "Daily-pl"}, inplace = True)

                corr = pd.DataFrame(theme_order.corrwith(theme_order["Daily-pl"]), columns = ["Corr"]).drop(index=["Daily-pl"])
                corr.dropna(inplace = True)
                
                fig_theme_corr_sel = px.bar(corr, y = "Corr", color = "Corr", text_auto=".0%",
                                            color_continuous_scale = 'Temps_r')
                
                fig_theme_corr_sel.update_xaxes(side="bottom")
                
                fig_theme_corr_sel.update_layout(
                    title_text='Past {0} Days Theme Correlation'.format(days), 
                    title_x=0.5, 
                    width=1000, 
                    height=1000,
                    xaxis_showgrid=False,
                    yaxis_showgrid=False,
                    xaxis_zeroline=False,
                    yaxis_zeroline=False,
                    yaxis_autorange='reversed',
                    template='simple_white'
                    )
                
                fig_theme_corr_sel.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                
                return fig_theme_corr_sel
            
            @st.experimental_memo(suppress_st_warning=True)
            def corr_overall(Trader_DB_selection, days):
                
                Trader_Order = Trader_DB_selection.groupby(["Theme"]).aggregate("sum").T.reset_index()
                theme_order = Trader_Order[((Trader_Order['index'].dt.date >= end_date + datetime.timedelta(-days)) & (Trader_Order['index'].dt.date <= end_date))]
                theme_order.set_index('index', inplace = True)
                
                corr = theme_order.corr()
                corr = corr.dropna(how = "all", axis = 0)
                corr = corr.dropna(how = "all", axis = 1)
                
                fig_theme_corr = px.imshow(corr.to_numpy(), x=corr.columns.tolist(),
                                          y=corr.columns.tolist(), text_auto=".0%",
                                          color_continuous_scale='Temps_r', 
                                          aspect="auto")
                
                fig_theme_corr.update_xaxes(side="bottom")
                
                fig_theme_corr.update_layout(
                    title_text='Past {0} Days Theme Correlation'.format(days), 
                    title_x=0.5, 
                    width=1000, 
                    height=1000,
                    xaxis_showgrid=False,
                    yaxis_showgrid=False,
                    xaxis_zeroline=False,
                    yaxis_zeroline=False,
                    yaxis_autorange='reversed',
                    template='simple_white'
                    )
                
                fig_theme_corr.update_traces(text = corr.to_numpy(), hovertemplate="%{x} <br>%{y} </br> %{text:.0%}")
                
                return fig_theme_corr
            
            tab30, tab60, tab90, tab252 = st.tabs(["Corr Past 30 Days", "Corr Past 60 Days", "Corr Past 90 Days", "Corr Past 252 Days"])

            with tab30:
                
                if (end_date - start_date).days >= 30:
                    
                    tab301, tab302 = st.tabs(["Correlation with Selected Traders", "Overall Correlation"])
                    
                    with tab301:
                        
                        st.subheader("Theme Correlation with Trader PNL")
    
                        fig_theme_corr_sel = corr_selected(Trader_DB_selection, 30)
                        
                        st.plotly_chart(fig_theme_corr_sel, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-30)) + "** and **" + str(end_date) + "**")
                        
                    with tab302:
                        
                        st.subheader("Overall Theme Correlation")
                    
                        fig_theme_corr = corr_overall(Trader_DB_selection, 30)
                
                        st.plotly_chart(fig_theme_corr, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-30)) + "** and **" + str(end_date) + "**")
            
                else:
                    st.warning('Not enough data to calculate 30 days Stats')
                    
            with tab60:
                
                if (end_date - start_date).days >= 60:
                    tab601, tab602 = st.tabs(["Correlation with Selected Traders", "Overall Correlation"])
                    
                    with tab601:
                        
                        st.subheader("Theme Correlation with Trader PNL")
    
                        fig_theme_corr_sel = corr_selected(Trader_DB_selection, 60)
                        
                        st.plotly_chart(fig_theme_corr_sel, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-60)) + "** and **" + str(end_date) + "**")
                        
                    with tab602:
                        
                        st.subheader("Overall Theme Correlation")
                        
                        fig_theme_corr = corr_overall(Trader_DB_selection, 60)
                        
                        st.plotly_chart(fig_theme_corr, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-60)) + "** and **" + str(end_date) + "**")
                
                else:
                    st.warning('Not enough data to calculate 60 days Stats')
                    
            with tab90:
                
                if (end_date - start_date).days >= 90:
                    
                    tab901, tab902 = st.tabs(["Correlation with Selected Traders", "Overall Correlation"])
                    
                    with tab901:
                        
                        st.subheader("Theme Correlation with Trader PNL")
    
                        fig_theme_corr_sel = corr_selected(Trader_DB_selection, 90)
                        
                        st.plotly_chart(fig_theme_corr_sel, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-90)) + "** and **" + str(end_date) + "**")
                        
                    with tab902:
                        
                        st.subheader("Overall Theme Correlation")
                        
                        fig_theme_corr = corr_overall(Trader_DB_selection, 90)
                        
                        st.plotly_chart(fig_theme_corr, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-90)) + "** and **" + str(end_date) + "**")
                
                else:
                    st.warning('Not enough data to calculate 90 days Stats')
                    
            with tab252:
                
                if (end_date - start_date).days >= 252:
                    
                    tab2521, tab2522 = st.tabs(["Correlation with Selected Traders", "Overall Correlation"])
                    
                    with tab2521:
                        
                        st.subheader("Theme Correlation with Trader PNL")
    
                        fig_theme_corr_sel = corr_selected(Trader_DB_selection, 252)
                        
                        st.plotly_chart(fig_theme_corr_sel, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-252)) + "** and **" + str(end_date) + "**")
                        
                    with tab2522:
                        
                        st.subheader("Overall Theme Correlation")
                        
                        fig_theme_corr = corr_overall(Trader_DB_selection, 252)
                        
                        st.plotly_chart(fig_theme_corr, use_container_width=True)
                        
                        col1, col2, col3 = st.columns(3)
                        col2.markdown("Data is between **" + str(end_date + datetime.timedelta(-252)) + "** and **" + str(end_date) + "**")
                
                else:
                    st.warning('Not enough data to calculate 252 days Stats')
                    
            # ---- ADD SIDEBAR ----
            st.sidebar.download_button(label="📥 Export Database",
              data=Trader_DB_selection.to_csv(),
              file_name= 'Trader_DB.csv',
              mime="text/csv")
        
            #Trader_DB_selection.drop(['Trader', 'Dates'], axis=1, inplace = True)

            plot_bar.progress(0.75)
            # PNL BY ASSET CLASS [BAR CHART]
            cols1, cols2 = st.columns((3, 1))
            
            pl_by_assetclass = Trader_DB_selection.groupby(by=["Asset Class"]).sum().T.sum().T
            pl_by_assetclass = pd.DataFrame(pl_by_assetclass, columns = ["PNL (USD $)"])
            pl_by_assetclass = pl_by_assetclass.sort_values(by="PNL (USD $)")
            
            with cols1:
            # with tabs1:
                cols1.markdown("**Bar Chart**")
    
                fig_pl_assetclass = px.bar(
                    pl_by_assetclass,
                    x=pl_by_assetclass.index,
                    y="PNL (USD $)",
                    color=pl_by_assetclass.index,
                    text_auto='0.2s',
                    title="<b>PNL by Asset Class</b>",
                    color_discrete_sequence=["#0083B8"] * len(pl_by_assetclass),
                    template="plotly_white",
                    width=800, height=400,
                )
                
                fig_pl_assetclass.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                
                fig_pl_assetclass.update_layout(
                    xaxis=dict(tickmode="linear"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=(dict(showgrid=False)),
                    )
                
                cols1.plotly_chart(fig_pl_assetclass, use_container_width=True)
                
            with cols2:
        
                cols2.markdown("**Table**")
                cols2.dataframe(pl_by_assetclass.style.format({"PNL (USD $)": "{:,.0f}"}))
            
            # PNL BY THEMES [BAR CHART]
  
            plot_bar.progress(0.8)
            tabs3, tabs4 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_themes = Trader_DB_selection.groupby(by=["Theme"]).sum().T.sum().T
            pl_by_themes = pd.DataFrame(pl_by_themes, columns = ["PNL (USD $)"])
            pl_by_themes = pl_by_themes.sort_values(by="PNL (USD $)")
            
            with tabs3:
                
                tabs3i, tabs3ii, tabs3iii = tabs3.tabs(["Top_5", "Top_10", "All"])
                
                with tabs3i:
                    
                    pl_by_themes_3i = pd.concat([pl_by_themes.head(5), pl_by_themes.tail(5)])
                    
                    fig_pl_themes_3i = px.bar(
                        pl_by_themes_3i,
                        x="PNL (USD $)",
                        y=pl_by_themes_3i.index,
                        color=pl_by_themes_3i.index,
                        text_auto='0.1s',
                        title="<b>PNL by Themes</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_themes_3i),
                        template="plotly_white",
                        width=800, height=800,
                    )
                    
                    fig_pl_themes_3i.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_themes_3i.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    tabs3i.plotly_chart(fig_pl_themes_3i, use_container_width=True)
                    
                with tabs3ii:
                    
                    pl_by_themes_3ii= pd.concat([pl_by_themes.head(10), pl_by_themes.tail(10)])
                    
                    fig_pl_themes_3ii = px.bar(
                        pl_by_themes_3ii,
                        x="PNL (USD $)",
                        y=pl_by_themes_3ii.index,
                        color=pl_by_themes_3ii.index,
                        text_auto='0.1s',
                        title="<b>PNL by Themes</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_themes_3ii),
                        template="plotly_white",
                        width=800, height=800,
                    )
                    
                    fig_pl_themes_3ii.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_themes_3ii.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    tabs3ii.plotly_chart(fig_pl_themes_3ii, use_container_width=True)
                    
                with tabs3iii:
                    
                    fig_pl_themes = px.bar(
                        pl_by_themes,
                        x="PNL (USD $)",
                        y=pl_by_themes.index,
                        color=pl_by_themes.index,
                        text_auto='0.1s',
                        title="<b>PNL by Themes</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_themes),
                        template="plotly_white",
                        width=800, height=1400,
                    )
                    
                    fig_pl_themes.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_themes.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                    
                    tabs3iii.plotly_chart(fig_pl_themes, use_container_width=True)
                
            with tabs4:
                
                st.markdown("**PNL by Themes**")
                pl_by_themes["PNL (USD $)"] = 5 * round(pl_by_themes["PNL (USD $)"]/1000/5) * 1000
                tabs4.dataframe(pl_by_themes.style.format({"PNL (USD $)": "{:,.0f}"}))
            
            # PNL BY COUNTRY [BAR CHART]

            plot_bar.progress(0.85)
            tabs5, tabs6 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_cty_trade = Trader_DB_selection.groupby(by=["RiskCountry", "Trade Category"]).sum().T.sum().T
            pl_by_cty_trade = pd.DataFrame(pl_by_cty_trade, columns = ["PNL (USD $)"])
            pl_by_cty_trade.reset_index(inplace=True)

            pl_by_cty = Trader_DB_selection.groupby(by=["RiskCountry"]).sum().T.sum().T
            pl_by_cty = pd.DataFrame(pl_by_cty, columns = ["PNL (USD $)"])
            pl_by_cty = pl_by_cty.sort_values(by="PNL (USD $)")
            
            with tabs5:
                
                tabs5i, tabs5ii, tabs5iii = tabs5.tabs(["Top_5", "Top_10", "All"])
                
                with tabs5i:
                    
                    pl_by_cty_5i = pd.concat([pl_by_cty.head(5), pl_by_cty.tail(5)])
                    pl_by_cty_trade_5i = pl_by_cty_trade[pl_by_cty_trade["RiskCountry"].isin(pl_by_cty_5i.index)]
    
                    pl_by_cty_trade_sort = pl_by_cty_trade_5i.copy()
                    pl_by_cty_trade_sort["PNL (USD $)"] = pl_by_cty_trade_sort["PNL (USD $)"].abs()
                    cat_ord = list(pl_by_cty_trade_sort.groupby(by=["Trade Category"]).sum()[["PNL (USD $)"]].sort_values(by="PNL (USD $)", ascending=False).index)
                    
                    fig_pl_cty_trade_5i = px.bar(
                         pl_by_cty_trade_5i,
                         x="RiskCountry",
                         y="PNL (USD $)",
                         color="Trade Category",
                         category_orders={"RiskCountry": pl_by_cty_trade_5i["RiskCountry"], "Trade Category": cat_ord},
                         barmode='relative',
                         title="<b>PNL by Country</b>",
                         template="plotly_white",
                         width=800, height=600,
                         )
        
                    pl_by_cty_trade_5i = pl_by_cty_trade_5i.groupby(['RiskCountry']).sum().reset_index()
                    pl_by_cty_trade_5i = pl_by_cty_trade_5i.sort_values(by="PNL (USD $)")
                    
                    fig_pl_cty_trade_5i.add_hline(y=0, line_width=1, line_dash="dash")
                    fig_pl_cty_trade_5i.add_trace(go.Scatter(x=pl_by_cty_trade_5i["RiskCountry"], y=pl_by_cty_trade_5i["PNL (USD $)"], 
                                                    mode="lines+markers+text", name="Top 5", text = pl_by_cty_trade_5i["PNL (USD $)"], 
                                                    textposition="top center", texttemplate='<b>%{text:.2s}</b>', 
                                                    marker= dict(size=9, color="black"), line=dict(color="black")))
        
                    fig_pl_cty_trade_5i.update_layout(xaxis={'categoryorder':'total ascending'}, 
                                                      yaxis=(dict(showgrid=False)), plot_bgcolor="rgba(0,0,0,0)")
                    
                    tabs5i.plotly_chart(fig_pl_cty_trade_5i, use_container_width=True)
                    
                with tabs5ii:
                    
                    pl_by_cty_5ii = pd.concat([pl_by_cty.head(10), pl_by_cty.tail(10)])
                    pl_by_cty_trade_5ii = pl_by_cty_trade[pl_by_cty_trade["RiskCountry"].isin(pl_by_cty_5ii.index)]
                    
                    pl_by_cty_trade_sort = pl_by_cty_trade_5ii.copy()
                    pl_by_cty_trade_sort["PNL (USD $)"] = pl_by_cty_trade_sort["PNL (USD $)"].abs()
                    cat_ord = list(pl_by_cty_trade_sort.groupby(by=["Trade Category"]).sum()[["PNL (USD $)"]].sort_values(by="PNL (USD $)", ascending=False).index)
                    
                    fig_pl_cty_trade_5ii = px.bar(
                        pl_by_cty_trade_5ii,
                        x="RiskCountry",
                        y="PNL (USD $)",
                        color="Trade Category",
                        category_orders={"RiskCountry": pl_by_cty_trade_5i["RiskCountry"], "Trade Category": cat_ord},
                        barmode='relative',
                        title="<b>PNL by Country</b>",
                        template="plotly_white",
                        width=800, height=600,
                    )
                    
                    pl_by_cty_trade_5ii = pl_by_cty_trade_5ii.groupby(['RiskCountry']).sum().reset_index()
                    pl_by_cty_trade_5ii = pl_by_cty_trade_5ii.sort_values(by="PNL (USD $)")
                    
                    fig_pl_cty_trade_5ii.add_hline(y=0, line_width=1, line_dash="dash")
                    fig_pl_cty_trade_5ii.add_trace(go.Scatter(x=pl_by_cty_trade_5ii["RiskCountry"], y=pl_by_cty_trade_5ii["PNL (USD $)"], 
                                                    mode="lines+markers+text", name="Top 10", text = pl_by_cty_trade_5ii["PNL (USD $)"], 
                                                    textposition="top center", texttemplate='<b>%{text:.2s}</b>', 
                                                    marker= dict(size=9, color="black"), line=dict(color="black")))
                    
                    fig_pl_cty_trade_5ii.update_layout(xaxis={'categoryorder':'total ascending'},
                                                       yaxis=(dict(showgrid=False)), plot_bgcolor="rgba(0,0,0,0)")
                    
                    tabs5ii.plotly_chart(fig_pl_cty_trade_5ii, use_container_width=True)
                    
                with tabs5iii:
                    
                    pl_by_cty_trade_5 = pl_by_cty_trade
                    
                    pl_by_cty_trade_sort = pl_by_cty_trade_5.copy()
                    pl_by_cty_trade_sort["PNL (USD $)"] = pl_by_cty_trade_sort["PNL (USD $)"].abs()
                    cat_ord = list(pl_by_cty_trade_sort.groupby(by=["Trade Category"]).sum()[["PNL (USD $)"]].sort_values(by="PNL (USD $)", ascending=False).index)
                    
                    fig_pl_cty_trade = px.bar(
                        pl_by_cty_trade_5,
                        x="RiskCountry",
                        y="PNL (USD $)",
                        color="Trade Category",
                        category_orders={"RiskCountry": pl_by_cty_trade_5["RiskCountry"], "Trade Category": cat_ord},
                        barmode='relative',
                        title="<b>PNL by Country</b>",
                        template="plotly_white",
                        width=800, height=600,
                    )
                    
                    pl_by_cty_trade_5 = pl_by_cty_trade_5.groupby(['RiskCountry']).sum().reset_index()
                    pl_by_cty_trade_5 = pl_by_cty_trade_5.sort_values(by="PNL (USD $)")
                    
                    fig_pl_cty_trade.add_hline(y=0, line_width=1, line_dash="dash")
                    fig_pl_cty_trade.add_trace(go.Scatter(x=pl_by_cty_trade_5["RiskCountry"], y=pl_by_cty_trade_5["PNL (USD $)"], 
                                                    mode="lines+markers+text", name="All", text = pl_by_cty_trade_5["PNL (USD $)"], 
                                                    textposition="top center", texttemplate='<b>%{text:.2s}</b>', 
                                                    marker= dict(size=9, color="black"), line=dict(color="black")))
                    
                    fig_pl_cty_trade.update_layout(xaxis={'categoryorder':'total ascending'},
                                                   yaxis=(dict(showgrid=False)), plot_bgcolor="rgba(0,0,0,0)")
                    
                    tabs5iii.plotly_chart(fig_pl_cty_trade, use_container_width=True)
            
            with tabs6:
                
                st.markdown("**PNL by Country**")
                pl_by_cty_trade["PNL (USD $)"] = 5 * round(pl_by_cty_trade["PNL (USD $)"]/1000/5) * 1000
                tabs6.dataframe(pl_by_cty_trade.style.format({"PNL (USD $)": "{:,.0f}"}))
            
            # PNL BY ASSET TYPE [BAR CHART]
  
            plot_bar.progress(0.9)
            tabs7, tabs8 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_assettype = Trader_DB_selection.groupby(by=["Trade Category"]).sum().T.sum().T
            pl_by_assettype = pd.DataFrame(pl_by_assettype, columns = ["PNL (USD $)"])
            pl_by_assettype = pl_by_assettype.sort_values(by="PNL (USD $)")
            
            with tabs7:
                
                tabs7i, tabs7ii, tabs7iii = tabs7.tabs(["Top_5", "Top_10", "All"])
                
                with tabs7i:
                    
                    pl_by_assettype_7i = pd.concat([pl_by_assettype.head(5), pl_by_assettype.tail(5)])
                
                    fig_pl_assettype_7i = px.bar(
                        pl_by_assettype_7i,
                        x="PNL (USD $)",
                        y=pl_by_assettype_7i.index,
                        color=pl_by_assettype_7i.index,
                        text_auto='0.1s',
                        title="<b>PNL by Asset Type</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_assettype_7i),
                        template="plotly_white",
                        width=800, height=800,
                    )
                    
                    fig_pl_assettype_7i.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_assettype_7i.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                
                    tabs7i.plotly_chart(fig_pl_assettype_7i, use_container_width=True)
                    
                with tabs7ii:
                    
                    pl_by_assettype_7ii = pd.concat([pl_by_assettype.head(10), pl_by_assettype.tail(10)])
                
                    fig_pl_assettype_7ii = px.bar(
                        pl_by_assettype_7ii,
                        x="PNL (USD $)",
                        y=pl_by_assettype_7ii.index,
                        color=pl_by_assettype_7ii.index,
                        text_auto='0.1s',
                        title="<b>PNL by Asset Type</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_assettype_7ii),
                        template="plotly_white",
                        width=800, height=800,
                    )
                    
                    fig_pl_assettype_7ii.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_assettype_7ii.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                
                    tabs7ii.plotly_chart(fig_pl_assettype_7ii, use_container_width=True)
                    
                with tabs7iii:
                    
                    fig_pl_assettype = px.bar(
                        pl_by_assettype,
                        x="PNL (USD $)",
                        y=pl_by_assettype.index,
                        color=pl_by_assettype.index,
                        text_auto='0.1s',
                        title="<b>PNL by Asset Type</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_assettype),
                        template="plotly_white",
                        width=800, height=1400,
                    )
                    
                    fig_pl_assettype.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_assettype.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=(dict(showgrid=False))
                    )
                
                    tabs7iii.plotly_chart(fig_pl_assettype, use_container_width=True)
                    
            with tabs8:
                
                st.markdown("**PNL by Asset Type**")
                pl_by_assettype["PNL (USD $)"] = 5 * round(pl_by_assettype["PNL (USD $)"]/1000/5) * 1000
                tabs8.dataframe(pl_by_assettype.style.format({"PNL (USD $)": "{:,.0f}"}))
            
            # st.write("Memory usage of Trader's database: ", str(Trader_DB_selection.memory_usage(index=True, deep=True).sum()), "MB")
            
            plot_bar.progress(0.95)
            
            @st.experimental_memo(suppress_st_warning=True)
            def pivot_table(Trader_DB):
                
                Trader_DB = pd.melt(Trader_DB, id_vars =list(Trader_DB.columns[:7]), value_vars =list(Trader_DB.columns[7:]),
                                    var_name= "Dates" , value_name= "Daily-pl")
                
                Trader_DB = Trader_DB[(Trader_DB[['Daily-pl']] != 0).all(axis=1)]
                
                return Trader_DB
            
            Trader_DB_pivot = pivot_table(Trader_DB_select)
            
            @st.experimental_memo(suppress_st_warning=True)
            def pivot_ui(df, **kwargs):
        
                class _DataFrame(pd.DataFrame):
                    def to_csv(self, **kwargs):
                        return super().to_csv(**kwargs).replace("\r\n", "\n")
                    
                return pivottablejs.pivot_ui(_DataFrame(df), **kwargs)
        
            for i in range(number):
            
                st.subheader("Pivot Table " + str(i+1))
                t = pivot_ui(Trader_DB_pivot)
            
                with open(t.src) as t:
                    components.html(t.read(), width=1500, height=1500, scrolling=True)

            plot_bar.progress(1.0)
            plot_bar.empty()
                
        # ---- HIDE STREAMLIT STYLE ----
        hide_st_style = """
                    <style>
                    #MainMenu {visibility: hidden;}
                    footer {visibility: hidden;}
                    header {visibility: hidden;}
                    </style>
                    """
        st.markdown(hide_st_style, unsafe_allow_html=True)
