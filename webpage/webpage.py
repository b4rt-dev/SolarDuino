# Very bad and messy code.

import time 

import numpy as np 
import pandas as pd 
import plotly.express as px
import streamlit as st
import glob

st.set_page_config(
    page_title="SolarDuino Dashboard",
    page_icon="✅",
    layout="wide",
)

csvPath = "/home/bart/Documents/Development/SolarDuino/pythonLogger/output/"

@st.cache_data
def get_data(filePath) -> pd.DataFrame:
    df = pd.read_csv(filePath, header=None)
    df.columns = ["Date", "PV Voltage", "PV Current", "Battery Voltage", "Output Current", "LDO Voltage", "Flags"]
    df['Date'] = pd.to_datetime(df['Date'],unit='s').dt.tz_localize('UTC').dt.tz_convert('Europe/Amsterdam')
    return df

def file_selector():
    filesList = glob.glob(csvPath+"*.csv")
    selected_filename = st.selectbox('Select a file', filesList)
    return selected_filename

def main():

    filename = file_selector()
    if filename:
        df = get_data(filename)

        # Two columns
        fig_col1, fig_col2 = st.columns(2)

        with fig_col1:
            st.markdown("### PV voltage")
            fig = px.line(
                data_frame=df, x="Date", y="PV Voltage"
            )
            st.write(fig)
           
        with fig_col2:
            st.markdown("### PV current")
            fig2 = px.line(
                data_frame=df, x="Date", y="PV Current"
            )
            st.write(fig2)

main()
