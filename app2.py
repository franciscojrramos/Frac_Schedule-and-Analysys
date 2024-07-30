import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import io

# Set page configuration
st.set_page_config(page_title="Enhanced Frac Job Scheduling and Analysis", page_icon=":oil_drum:", layout="wide")

# Apply custom CSS for ConocoPhillips branding and text styling
st.markdown("""
    <style>
    .sidebar .sidebar-content {
        background-color: #e10000;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
        padding-right: 2rem;
        padding-left: 2rem;
        padding-bottom: 2rem;
    }
    .reportview-container .main {
        color: #1e1e1e;
        background-color: #ffffff;
    }
    .sidebar .sidebar-content h2 {
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# Add ConocoPhillips logo
st.image("conocophillips_logo.png", width=200)

st.title("Enhanced Frac Job Scheduling and Analysis")

# Instructions
st.header("Instructions for Formatting Your Excel Sheet")
st.markdown("""
1. **Column Headers:** Ensure your Excel sheet has the following columns: 
    - Well List
    - Site
    - Start (Job Start Date)
    - Expected Stages (Planned Stages)
    - Expected Pounds of Proppant (Planned lbs of Proppant)
2. **Data Format:** Make sure the data in each column is properly formatted:
    - **Job Start Date:** Date format (e.g., YYYY-MM-DD)
    - **Planned Stages:** Numeric
    - **Planned lbs of Proppant:** Numeric
3. **Order of Columns:** The columns should be in the following order:
    - Well List
    - Site
    - Job Start Date
    - Planned Stages
    - Planned lbs of Proppant
""")

# File uploader
uploaded_file = st.file_uploader("Upload your frac spreadsheet", type=["xlsx", "csv"])

if uploaded_file is not None:
    try:
        # Read the file
        df_willow = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
        st.write("Column names:", df_willow.columns)
        
        # Adjust column names based on actual names in your DataFrame
        df_willow.rename(columns={
            'Well List': 'Well List',
            'Start': 'Job Start Date',
            'Expected Stages': 'Planned Stages',
            'Expected Pounds of Proppant ': 'Planned lbs of Proppant',
            'Site': 'Site'
        }, inplace=True)

        # Convert columns to appropriate types
        df_willow['Planned Stages'] = pd.to_numeric(df_willow['Planned Stages'], errors='coerce').fillna(0).astype(int)
        df_willow['Planned lbs of Proppant'] = pd.to_numeric(df_willow['Planned lbs of Proppant'], errors='coerce').fillna(0).astype(float)
        df_willow['Job Start Date'] = pd.to_datetime(df_willow['Job Start Date'], errors='coerce')

        # Ensure the DataFrame is sorted by 'Job Start Date' before calculations
        df_willow = df_willow.sort_values(by='Job Start Date', ascending=True).reset_index(drop=True)

        # Streamlit input for parameters
        st.sidebar.header("Parameters")
        rurd_duration = st.sidebar.number_input(label="RURD DURATION (Days)", min_value=0.0, max_value=10.0, value=4.9, step=0.1, key='rurd_duration')
        
        # Toggle for Batch Frac'ing
        enable_batch_frac = st.sidebar.checkbox("Enable Batch Frac'ing", value=True)
        if enable_batch_frac:
            batch_fracing_factor = st.sidebar.slider("Batch Frac'ing (if same site)", min_value=0.0, max_value=1.0, value=0.5, step=0.1)

        # Choice for calculation type
        st.sidebar.header("Calculation Type")
        use_stages = st.sidebar.checkbox("Use Stages/Day", value=True)
        use_proppant = st.sidebar.checkbox("Use Proppant/Day", value=False)

        if use_stages:
            use_proppant = False
        elif use_proppant:
            use_stages = False

        stages_per_day = st.sidebar.number_input(label="Stages/Day", min_value=1.0, max_value=10.0, value=3.5, step=0.1, key='stages_per_day', disabled=use_proppant)
        proppant_per_day = st.sidebar.number_input(label="Proppant/Day", min_value=100000, max_value=1500000, value=555000, step=25000, key='proppant_per_day', disabled=use_stages)

        # Add options to include NPT and Crew Change Out
        include_npt = st.sidebar.checkbox("Include NPT Duration", value=True)
        include_crew_change = st.sidebar.checkbox("Include Crew Change Out", value=True)

        # NPT durations for each quarter
        if include_npt:
            st.sidebar.header("NPT Duration (Days) per Quarter")
            npt_q1 = st.sidebar.number_input(label="NPT Duration Q1", min_value=0, max_value=30, value=0, step=1, key='npt_q1')
            npt_q2 = st.sidebar.number_input(label="NPT Duration Q2", min_value=0, max_value=30, value=0, step=1, key='npt_q2')
            npt_q3 = st.sidebar.number_input(label="NPT Duration Q3", min_value=0, max_value=30, value=0, step=1, key='npt_q3')
            npt_q4 = st.sidebar.number_input(label="NPT Duration Q4", min_value=0, max_value=30, value=0, step=1, key='npt_q4')
        else:
            npt_q1 = npt_q2 = npt_q3 = npt_q4 = 0

        # Custom Crew Change Out Duration
        if include_crew_change:
            crew_change_duration = st.sidebar.number_input(label="Crew Change Out Duration (Days per Period)", min_value=0.0, max_value=30.0, value=1.4, step=0.1)
        else:
            crew_change_duration = 0

        # Filter options
        st.sidebar.header("Filter Options")
        select_all = st.sidebar.checkbox("Select All Wells", value=True)
        if select_all:
            well_list = st.sidebar.multiselect("Select Well List", options=df_willow['Well List'].unique(), default=df_willow['Well List'].unique())
        else:
            well_list = st.sidebar.multiselect("Select Well List", options=df_willow['Well List'].unique())

        # Add default columns for Stages per Day and Proppant per Day
        df_willow['Stages per Day'] = stages_per_day
        df_willow['Proppant per Day'] = proppant_per_day

        # Function to estimate durations based on stages per day
        def estimate_durations_stages(df):
            df['Estimated_Stages_Duration'] = (df['Planned Stages'] / df['Stages per Day']).round(2)
            return df

        # Function to estimate durations based on proppant per day
        def estimate_durations_proppant(df):
            df['Estimated_Pump_Duration'] = (df['Planned lbs of Proppant'] / df['Proppant per Day']).round(2)
            return df

        # Determine the number of wells per quarter
        df_willow['Quarter'] = pd.to_datetime(df_willow['Job Start Date']).dt.quarter
        wells_per_quarter = df_willow['Quarter'].value_counts().to_dict()

        # Function to get NPT duration per well based on the quarter
        def get_npt_per_well(quarter):
            total_npt = 0
            if quarter == 1:
                total_npt = npt_q1
            elif quarter == 2:
                total_npt = npt_q2
            elif quarter == 3:
                total_npt = npt_q3
            elif quarter == 4:
                total_npt = npt_q4
            
            wells = wells_per_quarter.get(quarter, 1)
            return total_npt / wells if wells > 0 else 0

        # Function to generate crew change out periods
        def generate_crew_change_periods(year):
            periods = []
            start_date = datetime(year, 1, 1)
            while start_date.year == year:
                end_date = start_date + timedelta(weeks=3)
                periods.append((start_date, end_date))
                start_date = end_date + timedelta(weeks=3)
            return periods

        # Function to calculate crew change out days for a well
        def calculate_crew_change_out_days(start_date, end_date, crew_change_periods, crew_change_duration):
            total_days = 0
            for period_start, period_end in crew_change_periods:
                # Check if the job period overlaps with the crew change period
                if start_date <= period_end and end_date >= period_start:
                    # If the job overlaps with a crew change period, add the crew change duration
                    total_days += crew_change_duration
            return total_days

        # Function to check delays and add RURD, NPT, and Crew Change Out columns
        def check_delays(df, duration_column, delay_column_name, projected_end_column_name):
            df['Job Start Date'] = pd.to_datetime(df['Job Start Date'])
            df['End_Date'] = df['Job Start Date'] + pd.to_timedelta(df[duration_column], unit='D')
            df[projected_end_column_name] = df['End_Date']
            df[delay_column_name] = 0
            df['RURD Duration'] = float(rurd_duration)  # Ensure RURD Duration is treated as a float
            df['NPT Duration'] = df['Quarter'].apply(get_npt_per_well) if include_npt else 0
            df['Crew Change Out'] = 0.0  # Initialize Crew Change Out column as float

            if include_crew_change:
                # Generate crew change periods for the year of the job start date
                year = df['Job Start Date'].dt.year.mode()[0]
                crew_change_periods = generate_crew_change_periods(year)

            for i in range(len(df)):
                # Calculate the adjusted RURD Duration
                if i > 0 and df.loc[i, 'Site'] == df.loc[i - 1, 'Site']:
                    adjusted_rurd_duration = float(rurd_duration) * batch_fracing_factor if enable_batch_frac else float(rurd_duration)
                else:
                    adjusted_rurd_duration = float(rurd_duration)

                df.at[i, 'RURD Duration'] = adjusted_rurd_duration

                # Calculate Crew Change Out days if included
                if include_crew_change:
                    crew_change_out_days = calculate_crew_change_out_days(df.loc[i, 'Job Start Date'], df.loc[i, 'End_Date'], crew_change_periods, crew_change_duration)
                    df.at[i, 'Crew Change Out'] = float(crew_change_out_days)

                # Check and adjust for delays, but do not modify the Job Start Date
                if i > 0 and df.loc[i, 'Job Start Date'] < df.loc[i - 1, 'End_Date']:
                    df.loc[i, delay_column_name] = (df.loc[i - 1, 'End_Date'] - df.loc[i, 'Job Start Date']).days
                df.loc[i, 'End_Date'] = df.loc[i, 'Job Start Date'] + pd.to_timedelta(df.loc[i, duration_column] + adjusted_rurd_duration + df.loc[i, 'NPT Duration'] + df.loc[i, 'Crew Change Out'], unit='D')
                df.loc[i, projected_end_column_name] = df.loc[i, 'End_Date']

            return df

        # Apply the functions to the DataFrame based on user selection
        if use_stages:
            df_willow = estimate_durations_stages(df_willow.copy())
            df_willow = check_delays(df_willow, 'Estimated_Stages_Duration', 'Delay_Stages', 'Projected_End_Stages')
        elif use_proppant:
            df_willow = estimate_durations_proppant(df_willow.copy())
            df_willow = check_delays(df_willow, 'Estimated_Pump_Duration', 'Delay_Proppant', 'Projected_End_Proppant')

        filtered_df = df_willow[df_willow['Well List'].isin(well_list)]

        # Display results
        st.subheader("Calculated Durations and Delays")
        st.write(filtered_df)

        st.subheader("Total Days of Delay")
        total_delay = filtered_df['Delay_Stages'].sum() if use_stages else filtered_df['Delay_Proppant'].sum()
        st.markdown(f"**Total Delays:** {total_delay} days")

        # Plot a bar chart for delays using Plotly
        st.subheader("Total Delays For Each Well Bar Chart")
        delay_column = 'Delay_Stages' if use_stages else 'Delay_Proppant'
        fig = px.bar(filtered_df, x='Well List', y=delay_column, title='Delays per Well',
                     labels={delay_column:'Delay (days)', 'Well List':'Well List'},
                     color=delay_column, color_continuous_scale=px.colors.sequential.Inferno)
        fig.update_layout(xaxis_title="Well", yaxis_title="Delay (days)",
                          xaxis=dict(tickfont=dict(size=15, color='black')),
                          yaxis=dict(tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig)

        # Gantt Chart for Job Schedule and Delays using Plotly
        st.subheader("Gantt Chart - Job Schedule")
        end_column = 'Projected_End_Stages' if use_stages else 'Projected_End_Proppant'
        fig_gantt = px.timeline(filtered_df, x_start="Job Start Date", x_end=end_column, y="Well List",
                                color="Well List", hover_data=[delay_column], title="Job Schedule and Delays")
        fig_gantt.update_layout(xaxis_title="Date", yaxis_title="Well", yaxis=dict(autorange="reversed", tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig_gantt)

        # Provide an option to download the processed data
        st.subheader("Download Updated Job Schedule")
        buffer = io.BytesIO()
        
        filtered_df.to_csv(buffer, index=False)
        
        buffer.seek(0)
        
        st.download_button(
            label="Download Updated Job Schedule Data as CSV",
            data=buffer,
            file_name='Updated_Job_Schedule_data.csv',
            mime='text/csv',
        )
                
    except Exception as e:
        st.error(f"Error: {e}")
