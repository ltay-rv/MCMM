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
    # @st.cache(ttl=24*60*60, persist = True)
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
    
    # ---- SIDEBAR ----
    with st.sidebar.form("Specify"):

        st.subheader("Please Filter Here:")
        
        start_date = st.date_input("Start Date: ", value = Trader_DB.Dates.min().date(), 
                                        min_value = Trader_DB.Dates.min().date(), max_value = Trader_DB.Dates.max().date())
        
        end_date = st.date_input("End Date: ", value = Trader_DB.Dates.max().date(), 
                                        min_value = Trader_DB.Dates.min().date(), max_value = Trader_DB.Dates.max().date())
        
        trader = st.multiselect(
            "Select the Trader:",
            options=Trader_DB["Trader"].unique(),
            default="Firm-All")
        
        number = int(st.number_input('No. of charts to add: ', min_value=1, max_value=20, step=1))
        
        loaded = st.form_submit_button("Analyse")
            
        if "load_state" not in st.session_state:
            st.session_state.load_state = False
                
        if loaded or st.session_state.load_state:
            st.session_state.load_state = True
    
    if st.session_state.load_state:
            
        @st.experimental_memo(suppress_st_warning=True)
        def get_graphs():
            
            Trader_DB_select = Trader_DB[((Trader_DB['Dates'].dt.date >= start_date) & (Trader_DB['Dates'].dt.date <= end_date))]
                
            # ---- MAINPAGE ----
            st.title(":bar_chart: MCMM Dashboard")
            st.markdown("##")
                
            # st.write("Memory usage of Overall database: ", str(Trader_DB.memory_usage(index=True, deep=True).sum()), "MB")
            
            st.header(":pushpin: Analysis across Traders")
        
            daily_pnl = Trader_DB_select[["Dates", "Trader", "Daily-pl"]]
            
            tab1, tab2 = st.tabs(["Daily Correlation", "Weekly Correlation"])
            
            with tab1:
                
                Order_Daily = daily_pnl.groupby(["Dates", "Trader"])["Daily-pl"].aggregate("sum")
                c = daily_pnl.Trader.unique()
                daily_pnl_update = Order_Daily.unstack().reindex(columns=c)
                
                corr = daily_pnl_update.corr()
                mask = np.triu(np.ones_like(corr, dtype=bool))
                df_mask = corr.mask(mask)

                fig = px.imshow(df_mask.to_numpy(), x=df_mask.columns.tolist(),
                                          y=df_mask.columns.tolist(), text_auto=".0%", 
                                              color_continuous_scale='Temps', aspect="auto")
                
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
                
                tab1.write(fig)
            
            with tab2:
                
                Order_Weekly = daily_pnl.groupby([pd.Grouper(key='Dates', freq='W-FRI'), "Trader"])["Daily-pl"].aggregate("sum")
                c = daily_pnl.Trader.unique()
                weekly_pnl_update = Order_Weekly.unstack().reindex(columns=c)
                
                corr = weekly_pnl_update.corr()
                mask = np.triu(np.ones_like(corr, dtype=bool))
                df_mask = corr.mask(mask)

                fig = px.imshow(df_mask.to_numpy(), x=df_mask.columns.tolist(),
                                          y=df_mask.columns.tolist(), text_auto=".0%", 
                                              color_continuous_scale='Temps', aspect="auto")
                
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
                
                # tab2.subheader("Weekly Correlation of PM")
                
                # fig, ax = plt.subplots()
                # mask = np.triu(np.ones_like(weekly_pnl_update.corr(), dtype=bool))
                # cmap = sns.diverging_palette(20, 150, s=200, l=50, as_cmap=True)
            
                # with sns.axes_style("white"):
                #     hm = sns.heatmap(weekly_pnl_update.corr(), ax=ax, mask=mask, annot=True, fmt='.0%', cmap=cmap, vmin=-0.99, vmax=.99, center=0.00,
                #                 square=True, linewidths=.5, annot_kws={"size": 4}, cbar_kws={"shrink": .5})
                    
                #     hm.set_xticklabels(hm.get_xmajorticklabels(), fontsize = 4)
                #     hm.set_yticklabels(hm.get_ymajorticklabels(), fontsize = 4)
                
                tab2.write(fig)
            
            tab3, tab4 = st.tabs(["Daily Std.Dev", "Weekly Std.Dev"])
            
            with tab3:
                
                tab3.subheader("Daily Std.Dev of PM")
                
                pnl_std_daily = daily_pnl_update.std().to_frame(name="PNL (USD $)")
                pnl_std_daily.index.name="Traders"
            
                fig_pl_std_daily = px.bar(
                    pnl_std_daily,
                    x=pnl_std_daily.index,
                    y="PNL (USD $)",
                    text_auto='0.1s',
                    # title="<b>PNL by Country</b>",
                    color_discrete_sequence=["#0083B8"] * len(daily_pnl.std()),
                    template="plotly_white",
                )
                fig_pl_std_daily.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                fig_pl_std_daily.update_layout(
                    xaxis=dict(tickmode="linear"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=(dict(showgrid=False)),
                    )
               
                tab3.plotly_chart(fig_pl_std_daily, use_container_width=True)
                
            with tab4:
                
                tab4.subheader("Weekly Std.Dev of PM")
                
                pnl_std_weekly = weekly_pnl_update.std().to_frame(name="PNL (USD $)")
                pnl_std_weekly.index.name="Traders"
            
                fig_pl_std_weekly = px.bar(
                    pnl_std_weekly,
                    x=pnl_std_weekly.index,
                    y="PNL (USD $)",
                    text_auto='0.1s',
                    # title="<b>PNL by Country</b>",
                    color_discrete_sequence=["#0083B8"] * len(daily_pnl.std()),
                    template="plotly_white",
                )
                fig_pl_std_weekly.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                fig_pl_std_weekly.update_layout(
                    xaxis=dict(tickmode="linear"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    yaxis=(dict(showgrid=False)),
                    )
               
                tab4.plotly_chart(fig_pl_std_weekly, use_container_width=True)
            
            st.subheader("PM Performance - Firm")
            
            pm_perf = daily_pnl_update.cumsum().rename_axis(None,axis=1)
            
            pm_perf["Dates"]=pm_perf.index
            pm_perf = pd.melt(pm_perf, id_vars="Dates", value_vars=pm_perf.columns[:-1],
                                  var_name= "Trader" , value_name= "PNL")
            fig_pm_perf = px.line(pm_perf, x="Dates", y="PNL", color = "Trader")
            
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
        
            st.plotly_chart(fig_pm_perf, use_container_width=True)
        
            st.markdown("""---""")
            
            Trader_DB_select_pure = Trader_DB_select[(Trader_DB_select["Trader"] != "RMDS") &
                                                      (Trader_DB_select["Trader"] != "RMDSHWSP") & 
                                                      (Trader_DB_select["Trader"] != "Non-RMDSHWSP") & 
                                                      (Trader_DB_select["Trader"] != "Firm-All") & 
                                                      (Trader_DB_select["Trader"] != "Firm-Rates")]
            
            st.header(":calendar: Analysis by Investment types")
        
            daily_asset = Trader_DB_select_pure[["Dates", "Asset Class", "Daily-pl"]]
            daily_asset = daily_asset.groupby(["Dates", "Asset Class"])["Daily-pl"].aggregate("sum").unstack()
            daily_asset = daily_asset.rename_axis(None,axis=1)
            
            st.subheader("Firm Asset Class Performance")
            
            daily_asset_cumsum = daily_asset.cumsum() 
            daily_asset_cumsum["Dates"]=daily_asset_cumsum.index
            daily_asset_cumsum = pd.melt(daily_asset_cumsum, id_vars="Dates", value_vars=daily_asset_cumsum.columns[:-1],
                                  var_name= "Assets" , value_name= "PNL")
            fig_asset_perf = px.line(daily_asset_cumsum, x="Dates", y="PNL", color = "Assets")
            
            st.plotly_chart(fig_asset_perf, use_container_width=True)
                
            daily_cty = Trader_DB_select_pure[["Dates", "RiskCountry", "Daily-pl"]]
            daily_cty = daily_cty.groupby(["Dates", "RiskCountry"])["Daily-pl"].aggregate("sum").unstack()
            daily_cty = daily_cty.rename_axis(None,axis=1)
            
            st.subheader("Country Exposure Performance")
            
            top5_CE, top10_CE, get_all_CE = st.tabs(["Top_5", "Top_10", "All"])
            
            with top5_CE:
                
                daily_cty_cumsum = daily_cty.cumsum()
                bot_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).head(5).index)
                top_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).tail(5).index)
                daily_cty_cumsum = daily_cty_cumsum[bot_names + top_names]
                daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                      var_name= "Country" , value_name= "PNL")
                fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                
                top5_CE.plotly_chart(fig_cty_perf, use_container_width=True)
                
            with top10_CE:
                
                daily_cty_cumsum = daily_cty.cumsum()
                bot_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).head(10).index)
                top_names = list(daily_cty_cumsum.tail(1).T.sort_values(list(daily_cty_cumsum.tail(1).T.columns)).tail(10).index)
                daily_cty_cumsum = daily_cty_cumsum[bot_names + top_names]
                daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                      var_name= "Country" , value_name= "PNL")
                fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                
                top10_CE.plotly_chart(fig_cty_perf, use_container_width=True)
                
            with get_all_CE:
                
                daily_cty_cumsum = daily_cty.cumsum()
                daily_cty_cumsum["Dates"]=daily_cty_cumsum.index
                daily_cty_cumsum = pd.melt(daily_cty_cumsum, id_vars="Dates", value_vars=daily_cty_cumsum.columns[:-1],
                                      var_name= "Country" , value_name= "PNL")
                fig_cty_perf = px.line(daily_cty_cumsum, x="Dates", y="PNL", color = "Country")
                
                get_all_CE.plotly_chart(fig_cty_perf, use_container_width=True)
            
            daily_theme = Trader_DB_select_pure[["Dates", "Theme", "Daily-pl"]]
            daily_theme = daily_theme.groupby(["Dates", "Theme"])["Daily-pl"].aggregate("sum").unstack()
            daily_theme = daily_theme.rename_axis(None,axis=1)
            
            st.subheader("Firm's Themes Performance")
            
            top5_T, top10_T, get_all_T = st.tabs(["Top_5", "Top_10", "All"])
            
            with top5_T:
                
                daily_theme_cumsum = daily_theme.cumsum()
                bot_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).head(5).index)
                top_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).tail(5).index)
                daily_theme_cumsum = daily_theme_cumsum[bot_names + top_names]
                daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                      var_name= "Theme" , value_name= "PNL")
                fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                
                top5_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
            with top10_T:
                
                daily_theme_cumsum = daily_theme.cumsum()
                bot_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).head(10).index)
                top_names = list(daily_theme_cumsum.tail(1).T.sort_values(list(daily_theme_cumsum.tail(1).T.columns)).tail(10).index)
                daily_theme_cumsum = daily_theme_cumsum[bot_names + top_names]
                daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                      var_name= "Theme" , value_name= "PNL")
                fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                
                top10_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
            with get_all_T:
                
                daily_theme_cumsum = daily_theme.cumsum()
                daily_theme_cumsum["Dates"]=daily_theme_cumsum.index
                daily_theme_cumsum = pd.melt(daily_theme_cumsum, id_vars="Dates", value_vars=daily_theme_cumsum.columns[:-1],
                                      var_name= "Theme" , value_name= "PNL")
                fig_theme_perf = px.line(daily_theme_cumsum, x="Dates", y="PNL", color = "Theme")
                
                get_all_T.plotly_chart(fig_theme_perf, use_container_width=True)
                
            daily_asset_type = Trader_DB_select_pure[["Dates", "Trade Category", "Daily-pl"]]
            daily_asset_type = daily_asset_type.groupby(["Dates", "Trade Category"])["Daily-pl"].aggregate("sum").unstack()
            daily_asset_type = daily_asset_type.rename_axis(None,axis=1)
            
            st.subheader("Firm's Asset Type Performance")
            
            top5_A, top10_A, get_all_A = st.tabs(["Top_5", "Top_10", "All"])
            
            with top5_A:
                
                daily_asset_type_cumsum = daily_asset_type.cumsum()
                bot_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).head(5).index)
                top_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).tail(5).index)
                daily_asset_type_cumsum = daily_asset_type_cumsum[bot_names + top_names]
                daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                      var_name= "Asset Type" , value_name= "PNL")
                fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                
                top5_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
                
            with top10_A:
                
                daily_asset_type_cumsum = daily_asset_type.cumsum()
                bot_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).head(10).index)
                top_names = list(daily_asset_type_cumsum.tail(1).T.sort_values(list(daily_asset_type_cumsum.tail(1).T.columns)).tail(10).index)
                daily_asset_type_cumsum = daily_asset_type_cumsum[bot_names + top_names]
                daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                      var_name= "Asset Type" , value_name= "PNL")
                fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                
                top10_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
                
            with get_all_A:
                
                daily_asset_type_cumsum = daily_asset_type.cumsum()
                daily_asset_type_cumsum["Dates"]=daily_asset_type_cumsum.index
                daily_asset_type_cumsum = pd.melt(daily_asset_type_cumsum, id_vars="Dates", value_vars=daily_asset_type_cumsum.columns[:-1],
                                      var_name= "Asset Type" , value_name= "PNL")
                fig_asset_type_perf = px.line(daily_asset_type_cumsum, x="Dates", y="PNL", color = "Asset Type")
                
                get_all_A.plotly_chart(fig_asset_type_perf, use_container_width=True)
            
            st.markdown("""---""")
                
            # ---- SIDEBAR TRADER ----
            Trader_DB_selection = Trader_DB[((Trader_DB['Trader'].isin(list(trader))) & (Trader_DB['Dates'].dt.date >= start_date) & (Trader_DB['Dates'].dt.date <= end_date))]
            Trader_DB_selection.sort_values(by='Dates', inplace=True)
            Trader_DB_ytd = Trader_DB[((Trader_DB['Trader'].isin(list(trader))) & (Trader_DB['Dates'].dt.date >= start_date) & (Trader_DB['Dates'].dt.date <= end_date - timedelta(days=1)))]
            Trader_DB_ytd.sort_values(by='Dates', inplace=True)
             
            # ---- INFO ----
            
            st.header(":male-office-worker: Analysis by Trader")
        
            # TOP KPI's
            cum_pnl = int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].cumsum().values[-1]) 
            change_cum_pnl = int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].cumsum().values[-1] - Trader_DB_ytd.groupby(by=["Dates"]).sum()[["Daily-pl"]].cumsum().values[-1]) 
            average_pnl = "{:,}".format(int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].mean().values[-1]))
            change_average_pnl = "{:,}".format(int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].mean().values[-1] - 
                                                          Trader_DB_ytd.groupby(by=["Dates"]).sum()[["Daily-pl"]].mean().values[-1]))
            greatest_drawdown = "{:,}".format(int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].min().values[-1]))
            change_greatest_drawdown = "{:,}".format(int(Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]].min().values[-1] - 
                                                          Trader_DB_ytd.groupby(by=["Dates"]).sum()[["Daily-pl"]].min().values[-1]))
        
            left_col, middle_col, right_col = st.columns(3)
            left_col.metric("Cumulative Returns", f"US $ {cum_pnl:,}", f"{change_cum_pnl:,} US $")
            middle_col.metric("Average Daily Return", f"US $ {average_pnl}", f"{change_average_pnl} US $")
            right_col.metric("Max Daily Loss", f"US $ {greatest_drawdown}", f"{change_greatest_drawdown} US $")
            
            st.markdown("""---""")
            
            st.subheader("Daily Stats")
            
            #Daily pl
            daily_pl = Trader_DB_selection.groupby(by=["Dates"]).sum()[["Daily-pl"]]
            daily_cum_pl = daily_pl.cumsum()
            daily_ret = daily_cum_pl.pct_change()
        
            daily_cum_pl_125 = daily_cum_pl - daily_cum_pl.shift(125)
            daily_cum_pl_250 = daily_cum_pl - daily_cum_pl.shift(250)
            
            daily_rolling_125 = daily_ret.rolling(125).mean()
            daily_rolling_250 = daily_ret.rolling(250).mean()
            
            #Daily vol
            daily_vol_60 = daily_pl.rolling(60).std()*np.sqrt(252)
            daily_vol_125 = daily_pl.rolling(125).std()*np.sqrt(252)
            daily_vol_250 = daily_pl.rolling(250).std()*np.sqrt(252)
            
            daily_vol_inception_list = [daily_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(252) for i in range(1, len(daily_pl))]
            daily_vol_inception = pd.concat(daily_vol_inception_list, axis = 0)
            daily_vol_full_list = [daily_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(i+1) for i in range(1, len(daily_pl))]
            daily_vol_full = pd.concat(daily_vol_full_list, axis = 0)
        
            #Daily dd
            daily_dd = daily_cum_pl - daily_cum_pl.cummax()
            daily_dd_125 = daily_cum_pl - daily_cum_pl.rolling(window = 125).max() 
            daily_dd_250 = daily_cum_pl - daily_cum_pl.rolling(window = 250).max()
            
            #Daily sharpe
            daily_sharpe_6m = daily_cum_pl_125/daily_vol_125
            daily_sharpe_1y = daily_cum_pl_250/daily_vol_250
            daily_sharpe_cum = daily_cum_pl/daily_vol_full
            
            tab11, tab12, tab13, tab14 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe"])
            
            # PNL OVER TIME [LINE CHART]
            with tab11:
                
                tab11.subheader("Trader's Cumulative PNL")
                
                daily_roll_pnl = pd.concat([daily_cum_pl], axis = 1, join='outer')
                daily_roll_pnl.columns = ['Cumulative Returns']
                daily_roll_pnl["Dates"]=daily_roll_pnl.index
                daily_rolling_PNL = pd.melt(daily_roll_pnl, id_vars ="Dates", value_vars =list(daily_roll_pnl.columns[:-1]),
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab11.plotly_chart(fig_daily_cum_pl, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = daily_roll_pnl.pop('Dates')
                    first_column = first_column.dt.date
                    daily_roll_pnl = daily_roll_pnl.applymap('{:,.0f}'.format)
                    daily_roll_pnl.insert(0, 'Dates', first_column)
                    AgGrid(daily_roll_pnl)
                    
            with tab12:
                
                tab12.subheader("Trader's Volatility")
                
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab12.plotly_chart(fig_daily_vol, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = daily_roll_vol.pop('Dates')
                    first_column = first_column.dt.date
                    daily_roll_vol = daily_roll_vol.applymap('{:,.0f}'.format)
                    daily_roll_vol.insert(0, 'Dates', first_column)
                    AgGrid(daily_roll_vol)
                    
            with tab13:
                
                tab13.subheader("Trader's Drawdown")
                
                daily_roll_dd = pd.concat([daily_dd, daily_dd_125, daily_dd_250], axis = 1, join='outer')
                daily_roll_dd.columns = ['DD', 'DD 125', 'DD 250']
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab13.plotly_chart(fig_daily_dd, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = daily_roll_dd.pop('Dates')
                    first_column = first_column.dt.date
                    daily_roll_dd = daily_roll_dd.applymap('{:,.0f}'.format)
                    daily_roll_dd.insert(0, 'Dates', first_column)
                    AgGrid(daily_roll_dd)
                    
            with tab14:
                
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab14.plotly_chart(fig_daily_sharpe, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = daily_roll_sharpe.pop('Dates')
                    first_column = first_column.dt.date
                    daily_roll_sharpe = daily_roll_sharpe.applymap('{:,.0f}'.format)
                    daily_roll_sharpe.insert(0, 'Dates', first_column)
                    AgGrid(daily_roll_sharpe)

            st.subheader("Weekly Stats")
            
            #Weekly pl
            weekly_pl = Trader_DB_selection.groupby(by=[pd.Grouper(key='Dates', freq='W-FRI')]).sum()[["Daily-pl"]]
            weekly_cum_pl = weekly_pl.cumsum()
            weekly_ret = weekly_cum_pl.pct_change()
        
            weekly_cum_pl_125 = weekly_cum_pl - weekly_cum_pl.shift(26)
            weekly_cum_pl_250 = weekly_cum_pl - weekly_cum_pl.shift(52)
            
            weekly_rolling_125 = weekly_ret.rolling(26).mean()
            weekly_rolling_250 = weekly_ret.rolling(52).mean()
            
            #Weekly vol
            weekly_vol_60 = weekly_pl.rolling(13).std()*np.sqrt(52)
            weekly_vol_125 = weekly_pl.rolling(26).std()*np.sqrt(52)
            weekly_vol_250 = weekly_pl.rolling(52).std()*np.sqrt(52)
            
            weekly_vol_inception_list = [weekly_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(52) for i in range(1, len(weekly_pl))]
            weekly_vol_inception = pd.concat(weekly_vol_inception_list, axis = 0)
            weekly_vol_full_list = [weekly_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(i+1) for i in range(1, len(weekly_pl))]
            weekly_vol_full = pd.concat(weekly_vol_full_list, axis = 0)
        
            #Weekly dd
            weekly_dd = weekly_cum_pl - weekly_cum_pl.cummax() 
            weekly_dd_125 = weekly_cum_pl - weekly_cum_pl.rolling(window = 26).max()
            weekly_dd_250 = weekly_cum_pl - weekly_cum_pl.rolling(window = 52).max()
            
            #Weekly sharpe
            weekly_sharpe_6m = weekly_cum_pl_125/weekly_vol_125
            weekly_sharpe_1y = weekly_cum_pl_250/weekly_vol_250
            weekly_sharpe_cum = weekly_cum_pl/weekly_vol_full
        
            tab16, tab17, tab18, tab19 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe"])
            
            # PNL OVER TIME [LINE CHART]
            with tab16:
                
                tab16.subheader("Trader's Cumulative PNL")
                
                weekly_roll_pnl = pd.concat([weekly_cum_pl], axis = 1, join='outer')
                weekly_roll_pnl.columns = ['Cumulative Returns']
                weekly_roll_pnl["Dates"]=weekly_roll_pnl.index
                weekly_rolling_PNL = pd.melt(weekly_roll_pnl, id_vars ="Dates", value_vars =list(weekly_roll_pnl.columns[:-1]),
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab16.plotly_chart(fig_weekly_cum_pl, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = weekly_roll_pnl.pop('Dates')
                    first_column = first_column.dt.date
                    weekly_roll_pnl = weekly_roll_pnl.applymap('{:,.0f}'.format)
                    weekly_roll_pnl.insert(0, 'Dates', first_column)
                    AgGrid(weekly_roll_pnl)
                    
            with tab17:
                
                tab17.subheader("Trader's Volatility")
                
                weekly_roll_vol = pd.concat([weekly_vol_60, weekly_vol_125, weekly_vol_250, weekly_vol_inception], axis = 1, join='outer')
                weekly_roll_vol.columns = ['Vol 60', 'Vol 125', 'Vol 250', 'Vol Inception']
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab17.plotly_chart(fig_weekly_vol, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = weekly_roll_vol.pop('Dates')
                    first_column = first_column.dt.date
                    weekly_roll_vol = weekly_roll_vol.applymap('{:,.0f}'.format)
                    weekly_roll_vol.insert(0, 'Dates', first_column)
                    AgGrid(weekly_roll_vol)
                    
            with tab18:
                
                tab18.subheader("Trader's Drawdown")
                
                weekly_roll_dd = pd.concat([weekly_dd, weekly_dd_125, weekly_dd_250], axis = 1, join='outer')
                weekly_roll_dd.columns = ['DD', 'DD 125', 'DD 250']
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab18.plotly_chart(fig_weekly_dd, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = weekly_roll_dd.pop('Dates')
                    first_column = first_column.dt.date
                    weekly_roll_dd = weekly_roll_dd.applymap('{:,.0f}'.format)
                    weekly_roll_dd.insert(0, 'Dates', first_column)
                    AgGrid(weekly_roll_dd)
                    
            with tab19:
                
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab19.plotly_chart(fig_weekly_sharpe, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = weekly_roll_sharpe.pop('Dates')
                    first_column = first_column.dt.date
                    weekly_roll_sharpe = weekly_roll_sharpe.applymap('{:,.0f}'.format)
                    weekly_roll_sharpe.insert(0, 'Dates', first_column)
                    AgGrid(weekly_roll_sharpe)
            
            st.subheader("Monthly Stats")
            
            #Monthly pl
            monthly_pl = Trader_DB_selection.groupby(by=[pd.Grouper(key='Dates', freq='BM')]).sum()[["Daily-pl"]]
            monthly_cum_pl = monthly_pl.cumsum()
            monthly_ret = monthly_cum_pl.pct_change()
        
            monthly_cum_pl_125 = monthly_cum_pl - monthly_cum_pl.shift(6)
            monthly_cum_pl_250 = monthly_cum_pl - monthly_cum_pl.shift(12)
            
            monthly_rolling_125 = monthly_ret.rolling(6).mean()
            monthly_rolling_250 = monthly_ret.rolling(12).mean()
            
            #Monthly vol
            monthly_vol_60 = monthly_pl.rolling(3).std()*np.sqrt(12)
            monthly_vol_125 = monthly_pl.rolling(6).std()*np.sqrt(12)
            monthly_vol_250 = monthly_pl.rolling(2).std()*np.sqrt(12)
            
            monthly_vol_inception_list = [monthly_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(12) for i in range(1, len(monthly_pl))]
            monthly_vol_inception = pd.concat(monthly_vol_inception_list, axis = 0)
            monthly_vol_full_list = [monthly_pl[:i+1].rolling(i+1).std().iloc[-1:]*np.sqrt(i+1) for i in range(1, len(monthly_pl))]
            monthly_vol_full = pd.concat(monthly_vol_full_list, axis = 0)
        
            #Monthly dd
            monthly_dd = monthly_cum_pl - monthly_cum_pl.cummax() 
            monthly_dd_125 = monthly_cum_pl - monthly_cum_pl.rolling(window = 6).max()
            monthly_dd_250 = monthly_cum_pl - monthly_cum_pl.rolling(window = 12).max()
        
            #Monthly sharpe
            monthly_sharpe_6m = monthly_cum_pl_125/monthly_vol_125
            monthly_sharpe_1y = monthly_cum_pl_250/monthly_vol_250
            monthly_sharpe_cum = monthly_cum_pl/monthly_vol_full
        
            tab21, tab22, tab23, tab24 = st.tabs(["Returns", "Volatility", "Drawdown", "Sharpe"])
            
            # PNL OVER TIME [LINE CHART]
            with tab21:
                
                tab21.subheader("Trader's Cumulative PNL")
                
                monthly_roll_pnl = pd.concat([monthly_cum_pl], axis = 1, join='outer')
                monthly_roll_pnl.columns = ['Cumulative Returns']
                monthly_roll_pnl["Dates"]=monthly_roll_pnl.index
                monthly_rolling_PNL = pd.melt(monthly_roll_pnl, id_vars ="Dates", value_vars =list(monthly_roll_pnl.columns[:-1]),
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab21.plotly_chart(fig_monthly_cum_pl, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = monthly_roll_pnl.pop('Dates')
                    first_column = first_column.dt.date
                    monthly_roll_pnl = monthly_roll_pnl.applymap('{:,.0f}'.format)
                    monthly_roll_pnl.insert(0, 'Dates', first_column)
                    AgGrid(monthly_roll_pnl)
                    
            with tab22:
                
                tab22.subheader("Trader's Volatility")
                
                monthly_roll_vol = pd.concat([monthly_vol_60, monthly_vol_125, monthly_vol_250, monthly_vol_inception], axis = 1, join='outer')
                monthly_roll_vol.columns = ['Vol 60', 'Vol 125', 'Vol 250', 'Vol Inception']
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab22.plotly_chart(fig_monthly_vol, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = monthly_roll_vol.pop('Dates')
                    first_column = first_column.dt.date
                    monthly_roll_vol = monthly_roll_vol.applymap('{:,.0f}'.format)
                    monthly_roll_vol.insert(0, 'Dates', first_column)
                    AgGrid(monthly_roll_vol)
                    
            with tab23:
                
                tab23.subheader("Trader's Drawdown")
                
                monthly_roll_dd = pd.concat([monthly_dd, monthly_dd_125, monthly_dd_250], axis = 1, join='outer')
                monthly_roll_dd.columns = ['DD', 'DD 125', 'DD 250']
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab23.plotly_chart(fig_monthly_dd, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = monthly_roll_dd.pop('Dates')
                    first_column = first_column.dt.date
                    monthly_roll_dd = monthly_roll_dd.applymap('{:,.0f}'.format)
                    monthly_roll_dd.insert(0, 'Dates', first_column)
                    AgGrid(monthly_roll_dd)
                    
            with tab24:
                
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
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=(dict(showgrid=False))
                )
                
                tab24.plotly_chart(fig_monthly_sharpe, use_container_width=True)
                
                with st.expander("See Data Table"):
                    first_column = monthly_roll_sharpe.pop('Dates')
                    first_column = first_column.dt.date
                    monthly_roll_sharpe = monthly_roll_sharpe.applymap('{:,.0f}'.format)
                    monthly_roll_sharpe.insert(0, 'Dates', first_column)
                    AgGrid(monthly_roll_sharpe)
            
            st.markdown("""---""")
            
            Trader_DB_selection.drop(['Trader', 'Dates'], axis=1, inplace = True)
        
            # PNL BY ASSET CLASS [BAR CHART]
            
            tabs1, tabs2 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_assetclass = Trader_DB_selection.groupby(by=["Asset Class"]).sum()[["Daily-pl"]].sort_values(by="Daily-pl")
            pl_by_assetclass.rename(columns = {"Daily-pl": "PNL (USD $)"}, inplace =True)
        
            with tabs1:
                
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
                
                tabs1.plotly_chart(fig_pl_assetclass, use_container_width=True)
                
            with tabs2:
        
                st.caption("PNL by Asset Class")
                pl_by_assetclass = pl_by_assetclass.astype(int)
                pl_by_assetclass['PNL (USD $)'] = pl_by_assetclass.apply(lambda x: "{:,}".format(x['PNL (USD $)']), axis=1)
                tabs2.dataframe(pl_by_assetclass)
            
            # PNL BY THEMES [BAR CHART]
            
            tabs3, tabs4 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_themes = (
                Trader_DB_selection.groupby(by=["Theme"]).sum()[["Daily-pl"]].sort_values(by="Daily-pl")
            )
            pl_by_themes.rename(columns = {"Daily-pl": "PNL (USD $)"}, inplace =True)
            
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
                        width=800, height=1400,
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
                        width=800, height=1400,
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
                
                st.caption("PNL by Themes")
                pl_by_themes = pl_by_themes.astype(int)
                pl_by_themes['PNL (USD $)'] = pl_by_themes.apply(lambda x: "{:,}".format(x['PNL (USD $)']), axis=1)
                tabs4.dataframe(pl_by_themes)
            
            # PNL BY COUNTRY [BAR CHART]
        
            tabs5, tabs6 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_cty = (
                Trader_DB_selection.groupby(by=["RiskCountry"]).sum()[["Daily-pl"]].sort_values(by="Daily-pl")
            )
            pl_by_cty.rename(columns = {"Daily-pl": "PNL (USD $)"}, inplace =True)
            
            with tabs5:
                
                tabs5i, tabs5ii, tabs5iii = tabs5.tabs(["Top_5", "Top_10", "All"])
                
                with tabs5i:
                    
                    pl_by_cty_5i = pd.concat([pl_by_cty.head(5), pl_by_cty.tail(5)])
                    
                    fig_pl_cty_5i = px.bar(
                        pl_by_cty_5i,
                        x=pl_by_cty_5i.index,
                        y="PNL (USD $)",
                        color=pl_by_cty_5i.index,
                        text_auto='0.1s',
                        title="<b>PNL by Country</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_cty_5i),
                        template="plotly_white",
                        width=800, height=600,
                    )
                    
                    fig_pl_cty_5i.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_cty_5i.update_layout(
                        xaxis=dict(tickmode="linear"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=(dict(showgrid=False)),
                        )
                    
                    tabs5i.plotly_chart(fig_pl_cty_5i, use_container_width=True)
                    
                with tabs5ii:
                    
                    pl_by_cty_5ii = pd.concat([pl_by_cty.head(10), pl_by_cty.tail(10)])
                    
                    fig_pl_cty_5ii = px.bar(
                        pl_by_cty_5ii,
                        x=pl_by_cty_5ii.index,
                        y="PNL (USD $)",
                        color=pl_by_cty_5ii.index,
                        text_auto='0.1s',
                        title="<b>PNL by Country</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_cty_5ii),
                        template="plotly_white",
                        width=800, height=600,
                    )
                    
                    fig_pl_cty_5ii.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_cty_5ii.update_layout(
                        xaxis=dict(tickmode="linear"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=(dict(showgrid=False)),
                        )
                    
                    tabs5ii.plotly_chart(fig_pl_cty_5ii, use_container_width=True)
                    
                with tabs5iii:
                    
                    fig_pl_cty = px.bar(
                        pl_by_cty,
                        x=pl_by_cty.index,
                        y="PNL (USD $)",
                        color=pl_by_cty.index,
                        text_auto='0.1s',
                        title="<b>PNL by Country</b>",
                        color_discrete_sequence=["#0083B8"] * len(pl_by_cty),
                        template="plotly_white",
                        width=800, height=600,
                    )
                    
                    fig_pl_cty.update_traces(textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    
                    fig_pl_cty.update_layout(
                        xaxis=dict(tickmode="linear"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=(dict(showgrid=False)),
                        )
                    
                    tabs5iii.plotly_chart(fig_pl_cty, use_container_width=True)
            
            with tabs6:
                
                st.caption("PNL by Country")
                pl_by_cty = pl_by_cty.astype(int)
                pl_by_cty['PNL (USD $)'] = pl_by_cty.apply(lambda x: "{:,}".format(x['PNL (USD $)']), axis=1)
                tabs6.dataframe(pl_by_cty)
            
            # PNL BY ASSET TYPE [BAR CHART]
            
            tabs7, tabs8 = st.tabs(["Bar Chart", "Table"])
            
            pl_by_assettype = Trader_DB_selection.groupby(by=["Trade Category"]).sum()[["Daily-pl"]].sort_values(by="Daily-pl")
            pl_by_assettype.rename(columns = {"Daily-pl": "PNL (USD $)"}, inplace =True)
            
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
                        width=800, height=1400,
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
                        width=800, height=1400,
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
                
                st.caption("PNL by Asset Type")
                pl_by_assettype = pl_by_assettype.astype(int)
                pl_by_assettype['PNL (USD $)'] = pl_by_assettype.apply(lambda x: "{:,}".format(x['PNL (USD $)']), axis=1)
                tabs8.dataframe(pl_by_assettype)
            
            # st.write("Memory usage of Trader's database: ", str(Trader_DB_selection.memory_usage(index=True, deep=True).sum()), "MB")
            
            # ---- ADD SIDEBAR ----
                
            for i in range(number):
            
                st.subheader("Customised Chart " + str(i+1))
                Trader_DB_selection["Daily-pl"] = Trader_DB_selection["Daily-pl"].astype(int)
                t = pivot_ui(Trader_DB_selection)
            
                with open(t.src) as t:
                    components.html(t.read(), width=1500, height=2000, scrolling=True)
            
            st.sidebar.download_button(label="Export Database",
              data=Trader_DB_selection.to_csv(),
              file_name= 'Trader_DB.csv',
              mime="text/csv")
            
        get_graphs()
    
    # ---- HIDE STREAMLIT STYLE ----
    hide_st_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                header {visibility: hidden;}
                </style>
                """
    st.markdown(hide_st_style, unsafe_allow_html=True)
