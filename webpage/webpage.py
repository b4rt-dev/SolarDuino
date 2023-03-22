# Very bad and messy code.

import time 

import numpy as np 
import pandas as pd 
import plotly.express as px
import altair as alt
import streamlit as st
import glob
from datetime import timedelta, datetime


# How long in seconds to cache the data
CACHE_TTL = 60*15

CSV_PATH = "/home/bart/Documents/Development/SolarDuino/pythonLogger/output/"

# List of columns for data files (changing this will break things!)
COLUMNS_LIST = ["Date", "PV Voltage", "PV Current", "Battery Voltage", "Output Current", "LDO Voltage", "Flags"]

# Interval for updating live view in seconds
LIVE_VIEW_INTERVAL = 2


st.set_page_config(
    page_title="SolarDuino Dashboard",
    page_icon="✅",
    layout="wide",
)


@st.cache_data(ttl=CACHE_TTL)
def get_data() -> pd.DataFrame:
    """(Cached) Read all daily CSV files and combine into one DF.
    Also applies pre-processing, so that does not happen every refresh."""

    # Get list of all data files
    files = glob.glob(CSV_PATH + "*.csv")

    # Read and concat all the data files
    df = pd.concat((pd.read_csv(file, header=None) for file in files))

    # Set columns
    df.columns = COLUMNS_LIST

    # Convert date to the local timezone of solarDuino and set it as index
    df["Date"] = pd.to_datetime(df["Date"],unit='s').dt.tz_localize("UTC").dt.tz_convert("Europe/Amsterdam")
    df.set_index("Date", inplace=True)

    # Make sure the dates are sorted
    df.sort_index(inplace=True)

    # Calculate power
    df["PV Power"] = df["PV Voltage"] * (df["PV Current"]/1000)
    df["Output Power"] = df["Battery Voltage"] * (df["Output Current"]/1000)

    return df


def get_today_data() -> pd.DataFrame:
    """(Not cached) Read today's CSV file into a DF.
    Also applies pre-processing."""

    # Get list of all data files
    files = glob.glob(CSV_PATH + "*.csv")
    files.sort()
    
    # Load last file (should be from today if sorting works)
    df = pd.read_csv(files[-1], header=None)

    # Set columns
    df.columns = COLUMNS_LIST

    # Convert date to the local timezone of solarDuino and set it as index
    df["Date"] = pd.to_datetime(df["Date"],unit='s').dt.tz_localize("UTC").dt.tz_convert("Europe/Amsterdam")
    df.set_index("Date", inplace=True)

    # Make sure the dates are sorted
    df.sort_index(inplace=True)

    # Calculate power
    df["PV Power"] = df["PV Voltage"] * (df["PV Current"]/1000)
    df["Output Power"] = df["Battery Voltage"] * (df["Output Current"]/1000)

    return df


def get_energy_per_period(df, freq, days, column):
    # Group per period
    df_by_period = df.groupby(pd.PeriodIndex(df.index, freq=freq))

    # Calculate mean per period of selected column
    period_power_mean = df_by_period[column].mean()

    # Divide by number of days * 24 to get energy per hour
    period_energy = period_power_mean / (days*24)

    # Convert to dataframe and fix index
    period_energy = period_energy.to_frame()
    period_energy.index = period_energy.index.to_timestamp()
    return period_energy


def get_max_per_period(df, freq, column):
    # Group per period
    df_by_period = df.groupby(pd.PeriodIndex(df.index, freq=freq))

    # Calculate max per period of selected column
    period_max = df_by_period[column].max()

    # Convert to dataframe and fix index
    period_max = period_max.to_frame()
    period_max.index = period_max.index.to_timestamp()
    return period_max


def print_daily_stats(df):
    daily_pv_max = get_max_per_period(df, "d", "PV Power")
    daily_pv_energy = get_energy_per_period(df, "d", 1, "PV Power")

    st.markdown("### Daily PV max Power")
    fig = px.bar(
        data_frame=daily_pv_max,
        y="PV Power",
    ).update_layout(yaxis_title="W")
    st.write(fig)

    st.markdown("### Daily PV Energy")
    fig = px.bar(
        data_frame=daily_pv_energy,
        y="PV Power",
    ).update_layout(yaxis_title="Wh")
    st.write(fig)


def print_main_graphs(df, selected_day):
    df_past_day = df[
            (df.index.date > selected_day - timedelta(days=1)) & 
            (df.index.date <= selected_day)
        ].resample("20s").mean()

    # Voltage
    st.markdown("### Voltage")

    fig = alt.Chart(df_past_day.reset_index()).transform_fold(
        ["PV Voltage", "Battery Voltage", "LDO Voltage"],
    ).mark_line().encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M')),
        y='value:Q',
        color='key:N'
    )

    st.altair_chart(fig, use_container_width=True)


    # Current
    st.markdown("### Current")

    fig = alt.Chart(df_past_day.reset_index()).transform_fold(
        ["PV Current", "Output Current"],
    ).mark_line().encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M')),
        y='value:Q',
        color='key:N'
    )

    st.altair_chart(fig, use_container_width=True)


    # Power
    st.markdown("### Power")

    fig = alt.Chart(df_past_day.reset_index()).transform_fold(
        ["PV Power", "Output Power"],
    ).mark_line().encode(
        x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M')),
        y='value:Q',
        color='key:N'
    )

    st.altair_chart(fig, use_container_width=True)


def start_live_view_loop(live_view):
    while True:
        time.sleep(LIVE_VIEW_INTERVAL)

        with live_view.container():
            df_today = get_today_data()
            # Make sure we have data
            if len(df_today) >= 2:
                second_last_row = df_today.iloc[-2]
                last_row = df_today.iloc[-1]

                # Create three columns
                kpi1, kpi2, kpi3 = st.columns(3)

                # Fill columns
                # TODO for delta use average of last minute
                kpi1.metric(
                    label="PV Voltage",
                    value="{:.2f} V".format(last_row["PV Voltage"]),
                    delta="{:.2f} V".format(last_row["PV Voltage"] - second_last_row["PV Voltage"])
                )
                
                kpi2.metric(
                    label="PV Current",
                    value="{:.1f} mA".format(last_row["PV Current"]),
                    delta="{:.1f} mA".format(last_row["PV Current"] - second_last_row["PV Current"])
                )
                
                kpi3.metric(
                    label="PV Power",
                    value="{:.2f} W".format(last_row["PV Power"]),
                    delta="{:.2f} W".format(last_row["PV Power"] - second_last_row["PV Power"])
                )
                
                # Get last 5 minutes
                last_ts = df_today.index[-1]
                first_ts = last_ts - pd.Timedelta(5, 'minutes')
                df_past_five_minutes = df_today[(df_today.index >= first_ts) & (df_today.index <= last_ts)]

                # Create two columns
                col1, col2 = st.columns(2)

                # Voltage
                col1.markdown("### Voltage")

                fig = alt.Chart(df_past_five_minutes.reset_index()).transform_fold(
                    ["PV Voltage", "Battery Voltage", "LDO Voltage"],
                ).mark_line().encode(
                    x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S')),
                    y='value:Q',
                    color='key:N'
                )
                col1.altair_chart(fig, use_container_width=True)

                # Current
                col2.markdown("### Current")

                fig = alt.Chart(df_past_five_minutes.reset_index()).transform_fold(
                    ["PV Current", "Output Current"],
                ).mark_line().encode(
                    x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S')),
                    y='value:Q',
                    color='key:N'
                )
                col2.altair_chart(fig, use_container_width=True)

    st.altair_chart(fig, use_container_width=True)

def main():
    # Live view placeholder
    live_view = st.empty()

    df = get_data()

    selected_day = st.date_input("Day to view")

    print_main_graphs(df, selected_day)

    start_live_view_loop(live_view)
    

main()
