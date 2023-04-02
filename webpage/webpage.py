# Very bad and messy code.
# Will rewrite this when PCB arrives
# Note: use /?embed=true to hide the status bar

import time 

import numpy as np 
import pandas as pd
from pandas.tseries.offsets import MonthEnd
from scipy import integrate
import altair as alt
import streamlit as st
from streamlit.components.v1 import html
import glob
from datetime import timedelta, datetime

# Sunrise and sunset info
from astral import LocationInfo, zoneinfo
from astral.sun import sun


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


# Returns astral location of solar panel location
@st.cache_data
def get_location():
    return LocationInfo("Duiven", "Netherlands", "Europe/Amsterdam", 51.9445121, 5.9943684)

    
# Returns dawn and dusk datetimes in Amsterdam timezone
@st.cache_data
def get_dawn_dusk(location, date):
    s = sun(location.observer, date=date, tzinfo=zoneinfo.ZoneInfo("Europe/Amsterdam"))
    return s["dawn"], s["dusk"]


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

    # Drop rows with nan
    df.dropna(inplace=True)

    return df


@st.cache_data(ttl=LIVE_VIEW_INTERVAL)
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

    # Drop rows with nan
    df.dropna(inplace=True)

    return df


def print_day_graphs(df, selected_day):
    """
    Only show between dusk and dawn of selected day.
    """
    st.markdown("## Day overview")

    # Get dawn and dusk times
    dawn, dusk = get_dawn_dusk(get_location(), selected_day)
    
    # Get data of selected day only
    df_selected_day = df[
            (df.index >= dawn) &
            (df.index <= dusk)
        ].resample("30s").mean()

    # Somehow resample and mean can generate Nan rows
    #  so drop rows with nan
    df_selected_day.dropna(inplace=True)

    # Selector for graphs
    selector = alt.selection_single(
        fields=['key'], 
        empty='all',
        bind='legend'
    )

    tab_power, tab_voltage, tab_current, tab_energy = st.tabs(["Power", "Voltage", "Current", "Energy"])

    with tab_voltage:
        # Voltage
        fig = alt.Chart(df_selected_day.reset_index()).transform_fold(
            ["PV Voltage", "Battery Voltage", "LDO Voltage"],
        ).mark_line().encode(
            x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S', title='')),
            y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " V"')),
            color=alt.Color('key:N',
                scale=alt.Scale(domain=["PV Voltage", "Battery Voltage", "LDO Voltage"]),
                legend=alt.Legend(
                            title="",
                            orient="top",
                            direction='horizontal')
                ),
            opacity=alt.condition(selector, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d %H:%M'),
                alt.Tooltip("value:Q", title="Voltage", format='.2f'),
                ]
        ).add_selection(
            selector
        ).transform_filter(
            selector
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


    with tab_power:
        # Power
        fig = alt.Chart(df_selected_day.reset_index()).transform_fold(
            ["PV Power", "Output Power"],
        ).mark_line().encode(
            x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M', title='')),
            y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " W"')),
            color=alt.Color('key:N',
                scale=alt.Scale(domain=["PV Power", "Output Power"]),
                legend=alt.Legend(
                            title="",
                            orient="top",
                            direction='horizontal')
                ),
            opacity=alt.condition(selector, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d %H:%M'),
                alt.Tooltip("value:Q", title="Power", format='.2f'),
                ]
        ).add_selection(
            selector
        ).transform_filter(
            selector
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


    with tab_current:
        # Current
        fig = alt.Chart(df_selected_day.reset_index()).transform_fold(
            ["PV Current", "Output Current"],
        ).mark_line().encode(
            x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M', title='')),
            y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " mA"')),
            color=alt.Color('key:N',
                scale=alt.Scale(domain=["PV Current", "Output Current"]),
                legend=alt.Legend(
                            title="",
                            orient="top",
                            direction='horizontal')
                ),
            opacity=alt.condition(selector, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d %H:%M'),
                alt.Tooltip("value:Q", title="Current", format='.2f'),
                ]
        ).add_selection(
            selector
        ).transform_filter(
            selector
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


    with tab_energy:
        # Energy

        # Slow and dirty method of calculating watt hour graph
        df_selected_day["PV Energy"] = (integrate.cumtrapz(df_selected_day["PV Power"], df_selected_day.index, initial=0))
        df_selected_day["PV Energy"] = df_selected_day["PV Energy"].apply(lambda row : row.total_seconds() if not isinstance(row, int) else 0.0)
        df_selected_day["PV Energy"] = df_selected_day["PV Energy"] / 3600

        fig = alt.Chart(df_selected_day.reset_index()).transform_fold(
            ["PV Energy"],
        ).mark_line().encode(
            x=alt.X('Date:T', axis=alt.Axis(format='%b %d %H:%M', title='')),
            y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " Wh"')),
            color=alt.Color('key:N',
                scale=alt.Scale(domain=["PV Energy"]),
                legend=alt.Legend(
                            title="",
                            orient="top",
                            direction='horizontal')
                ),
            opacity=alt.condition(selector, alt.value(1), alt.value(0)),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d %H:%M'),
                alt.Tooltip("value:Q", title="Energy", format='.2f'),
                ]
        ).add_selection(
            selector
        ).transform_filter(
            selector
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


@st.cache_data
def get_metrics_per_day(df):
    grouped_by_day = df.groupby(df.index.date)

    # Build df as dictionary and convert later
    df_by_day = {
        "Date": [],
        "PV Energy": [],
        "PV Max Power": [],
        }

    for day, df_day in grouped_by_day:
        # Resample to get more speed for energy calculations(but less accuracy)
        df_day_resampled = df_day.resample("30s").mean()
        # Somehow resample and mean can generate Nan rows
        #  so drop rows with nan
        df_day_resampled.dropna(inplace=True)

        # Get PV energy
        pv_energy_day = np.trapz(df_day_resampled["PV Power"], df_day_resampled.index).total_seconds() / 3600
        
        # Get PV max power
        pv_max_power = df_day["PV Power"].max()

        # Fill df_by_day
        df_by_day["Date"].append(day)
        df_by_day["PV Energy"].append(pv_energy_day)
        df_by_day["PV Max Power"].append(pv_max_power)

    # Actually convert to dataframe
    df_by_day = pd.DataFrame.from_dict(df_by_day)
    df_by_day["Date"] = pd.to_datetime(df_by_day["Date"])
    df_by_day.set_index("Date", inplace=True)

    return df_by_day


@st.cache_data
def get_metrics_per_month(df):
    grouped_by_month = df.groupby(pd.Grouper(freq='M'))

    # Build df as dictionary and convert later
    df_by_month = {
        "Month": [],
        "PV Energy": [],
        "PV Max Power": [],
        }

    for month, df_month in grouped_by_month:
        # Resample to get more speed for energy calculations(but less accuracy)
        df_month_resampled = df_month.resample("30s").mean()
        # Somehow resample and mean can generate Nan rows
        #  so drop rows with nan
        df_month_resampled.dropna(inplace=True)

        # Get PV energy
        pv_energy_month = np.trapz(df_month_resampled["PV Power"], df_month_resampled.index).total_seconds() / 3600
        
        # Get PV max power
        pv_max_power = df_month["PV Power"].max()

        # Fill df_by_month
        df_by_month["Month"].append(month)
        df_by_month["PV Energy"].append(pv_energy_month)
        df_by_month["PV Max Power"].append(pv_max_power)

    # Actually convert to dataframe
    df_by_month = pd.DataFrame.from_dict(df_by_month)
    df_by_month["Month"] = pd.to_datetime(df_by_month["Month"])
    df_by_month.set_index("Month", inplace=True)

    return df_by_month


def print_week_graphs(df, selected_day):
    """
    Shows stats for week of selected day
    """
    st.markdown("## Week overview")

    # Get week number
    selected_week = selected_day.isocalendar()[1]

    # Get data of selected week only
    df_selected_week = df[(df.index.isocalendar().week == selected_week)]

    # Get metrics for each day of the week
    df_by_day = get_metrics_per_day(df_selected_week)

    tab_energy, tab_power_max= st.tabs(["PV Energy", "PV Max Power"])

    with tab_energy:
        # Daily pv energy
        fig = alt.Chart(df_by_day["PV Energy"].reset_index()).mark_bar().encode(
            x=alt.X('monthdate(Date):O', axis=alt.Axis(title="")),
            y=alt.Y('PV Energy:Q', axis=alt.Axis(title="", labelExpr='datum.value + " Wh"')),
            color=alt.condition(
                alt.datum.Date == alt.expr.toDate(str(selected_day)),
                alt.value('orange'),
                alt.value('steelblue')
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d'),
                alt.Tooltip("PV Energy:Q", title="Energy", format='.2f'),
                ]
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)

    with tab_power_max:
        # Daily pv max power
        fig = alt.Chart(df_by_day["PV Max Power"].reset_index()).mark_bar().encode(
            x=alt.X('monthdate(Date):O', axis=alt.Axis(title="")),
            y=alt.Y('PV Max Power:Q', axis=alt.Axis(title="", labelExpr='datum.value + " W"')),
            color=alt.condition(
                alt.datum.Date == alt.expr.toDate(str(selected_day)),
                alt.value('orange'),
                alt.value('steelblue')
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date", format='%b %d'),
                alt.Tooltip("PV Max Power:Q", title="Energy", format='.2f'),
                ]
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


def print_year_graphs(df, selected_day):
    """
    Shows stats for year of selected day by month
    """
    st.markdown("## Year overview")

    # Get year of selected day
    selected_year = selected_day.year

    # Get data of selected year only
    df_selected_year = df[(df.index.year == selected_year)]

    # Get metrics for each month of the year
    df_by_month = get_metrics_per_month(df_selected_year)

    tab_energy, tab_power_max= st.tabs(["PV Energy", "PV Max Power"])

    with tab_energy:
        # Daily pv energy
        fig = alt.Chart(df_by_month["PV Energy"].reset_index()).mark_bar().encode(
            x=alt.X('yearmonth(Month):O', axis=alt.Axis(title="")),
            y=alt.Y('PV Energy:Q', axis=alt.Axis(title="", labelExpr='datum.value + " Wh"')),
            color=alt.condition(
                # Set to last day of month, because that is the index returned by get_metrics_per_month
                alt.datum.Month == alt.expr.toDate(str(selected_day.replace(day=1) + MonthEnd(0))),
                alt.value('orange'),
                alt.value('steelblue')
            ),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format='%b %Y'),
                alt.Tooltip("PV Energy:Q", title="Energy", format='.2f'),
                ]
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)

    with tab_power_max:
        # Daily pv max power
        fig = alt.Chart(df_by_month["PV Max Power"].reset_index()).mark_bar().encode(
            x=alt.X('yearmonth(Month):O', axis=alt.Axis(title="")),
            y=alt.Y('PV Max Power:Q', axis=alt.Axis(title="", labelExpr='datum.value + " W"')),
            color=alt.condition(
                # Set to last day of month, because that is the index returned by get_metrics_per_month
                alt.datum.Month == alt.expr.toDate(str(selected_day.replace(day=1) + MonthEnd(0))),
                alt.value('orange'),
                alt.value('steelblue')
            ),
            tooltip=[
                alt.Tooltip("Month:T", title="Month", format='%b %Y'),
                alt.Tooltip("PV Max Power:Q", title="Energy", format='.2f'),
                ]
        )

        st.altair_chart(fig, theme="streamlit", use_container_width=True)


def start_live_view_loop(live_view):
    # Center metrics
    css='''
    [data-testid="metric-container"] {
        width: fit-content;
        margin: auto;
    }

    [data-testid="metric-container"] > div {
        width: fit-content;
        margin: auto;
    }

    [data-testid="metric-container"] label {
        width: fit-content;
        margin: auto;
    }
    '''
    st.markdown(f'<style>{css}</style>',unsafe_allow_html=True)

    while True:
        time.sleep(LIVE_VIEW_INTERVAL)

        with live_view.container():
            df_today = get_today_data()
            # Make sure we have data
            if len(df_today) >= 2:
                last_row = df_today.iloc[-1]


                # Energy metrics
                col_pv_energy, col_output_energy = st.columns(2)

                energy = np.trapz(df_today["PV Power"], df_today.index).total_seconds() / 3600

                col_pv_energy.metric(
                    label="Today's PV Energy",
                    value="{:.3f} Wh".format(energy),
                    delta=None
                )

                col_output_energy.metric(
                    label="Today's Output Energy",
                    value="{:.3f} Wh".format(0.0),
                    delta=None
                )

                # Voltage metrics
                col_pv_volt, col_bat_volt = st.columns(2)

                col_pv_volt.metric(
                    label="PV Voltage",
                    value="{:.2f} V".format(last_row["PV Voltage"]),
                    delta=None
                )

                col_bat_volt.metric(
                    label="Battery Voltage",
                    value="{:.2f} V".format(last_row["Battery Voltage"]),
                    delta=None
                )

                # Power metrics
                col_pv_power, col_output_power = st.columns(2)

                col_pv_power.metric(
                    label="PV Current & Power",
                    value="{:.0f} mA | {:.2f} W".format(last_row["PV Current"], last_row["PV Power"]),
                    delta=None
                )
                
                col_output_power.metric(
                    label="Output Current & Power",
                    value="{:.0f} mA | {:.2f} W".format(last_row["Output Current"], last_row["Output Power"]),
                    delta=None
                )
                
                # Get last 5 minutes
                last_ts = df_today.index[-1]
                first_ts = last_ts - pd.Timedelta(5, 'minutes')
                df_past_five_minutes = df_today[(df_today.index >= first_ts) & (df_today.index <= last_ts)]

                # Selector for graphs
                selector = alt.selection_single(
                    fields=['key'], 
                    empty='all',
                    bind='legend'
                )

                tab_power, tab_voltage, tab_current = st.tabs(["Power", "Voltage", "Current"])

                with tab_power:
                    # Power
                    fig = alt.Chart(df_past_five_minutes.reset_index()).transform_fold(
                        ["PV Power", "Output Power"],
                    ).mark_line().encode(
                        x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S', title='')),
                        y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " W"')),
                        color=alt.Color('key:N',
                            scale=alt.Scale(domain=["PV Power", "Output Power"]),
                            legend=alt.Legend(
                                        title="",
                                        orient="top",
                                        direction='horizontal')
                            )
                    )

                    st.altair_chart(fig, theme="streamlit", use_container_width=True)

                with tab_voltage:
                    # Voltage
                    fig = alt.Chart(df_past_five_minutes.reset_index()).transform_fold(
                        ["PV Voltage", "Battery Voltage", "LDO Voltage"],
                    ).mark_line().encode(
                        x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S', title='')),
                        y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " V"')),
                        color=alt.Color('key:N',
                            scale=alt.Scale(domain=["PV Voltage", "Battery Voltage", "LDO Voltage"]),
                            legend=alt.Legend(
                                title="",
                                orient="top",
                                direction='horizontal')
                            )
                    )
                    st.altair_chart(fig, theme="streamlit", use_container_width=True)

                with tab_current:
                    # Current
                    fig = alt.Chart(df_past_five_minutes.reset_index()).transform_fold(
                        ["PV Current", "Output Current"],
                    ).mark_line().encode(
                        x=alt.X('Date:T', axis=alt.Axis(format='%H:%M:%S', title='')),
                        y=alt.Y('value:Q', axis=alt.Axis(title="", labelExpr='datum.value + " mA"')),
                        color=alt.Color('key:N',
                            scale=alt.Scale(domain=["PV Current", "Output Current"]),
                            legend=alt.Legend(
                                        title="",
                                        orient="top",
                                        direction='horizontal')
                            )
                    )

                    st.altair_chart(fig, theme="streamlit", use_container_width=True)

def display_title():
    st.markdown("# SolarDuino Dashboard")


def main():
    display_title()

    selected_day = st.date_input("Selected day")

    # Set selected day to yesterday if today is selected and not yet dawn
    dawn, _ = get_dawn_dusk(get_location(), selected_day)
    current_datetime = datetime.now()
    if current_datetime.date == selected_day:
        if current_datetime.time < dawn.time:
            # Set the day to yesterday
            selected_day -= timedelta(days=1)

    df = get_data()

    print_day_graphs(df, selected_day)
    print_week_graphs(df, selected_day)
    print_year_graphs(df, selected_day)

    # Live view placeholder
    st.write("## Live view")
    live_view = st.empty()

    start_live_view_loop(live_view)


main()
