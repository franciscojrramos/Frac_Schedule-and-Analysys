import streamlit as st
import pandas as pd
from datetime import timedelta
import plotly.express as px
import io

# Set page configuration
st.set_page_config(page_title="Enhanced Frac Job Scheduling and Analysis",
                   page_icon=":oil_drum:",
                   layout="wide")

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
uploaded_file = st.file_uploader("Upload your frac spreadsheet",
                                 type=["xlsx", "csv"])

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

        # Select and rearrange the required columns
        desired_order = ['Well List', 'Site', 'Job Start Date', 'Planned Stages', 'Planned lbs of Proppant']
        df_willow = df_willow[desired_order]

        # Streamlit input for parameters
        st.sidebar.header("Parameters")
        rurd_duration = st.sidebar.number_input(label="RURD DURATION (Days)",
                                                min_value=1, max_value=10, value=2, step=1, key='rurd_duration')
        batch_fracing_factor = st.sidebar.slider("Batch Frac'ing (if same site)",
                                                 min_value=0.0, max_value=1.0, value=0.5, step=0.1)
        stages_per_day = st.sidebar.number_input(label="Stages/Day",
                                                 min_value=1.0, max_value=10.0, value=5.0, step=0.1, key='stages_per_day')
        proppant_per_day = st.sidebar.number_input(label="Proppant/Day",
                                                   min_value=100000, max_value=1500000, value=100000, step=25000, key='proppant_per_day')

        # Add NPT durations for each quarter
        st.sidebar.header("NPT Duration (Days) per Quarter")
        npt_q1 = st.sidebar.number_input(label="NPT Duration Q1", min_value=0, max_value=30, value=0, step=1, key='npt_q1')
        npt_q2 = st.sidebar.number_input(label="NPT Duration Q2", min_value=0, max_value=30, value=0, step=1, key='npt_q2')
        npt_q3 = st.sidebar.number_input(label="NPT Duration Q3", min_value=0, max_value=30, value=0, step=1, key='npt_q3')
        npt_q4 = st.sidebar.number_input(label="NPT Duration Q4", min_value=0, max_value=30, value=0, step=1, key='npt_q4')

        # Filter options
        st.sidebar.header("Filter Options")
        select_all = st.sidebar.checkbox("Select All Wells", value=True)
        well_list = st.sidebar.multiselect("Select Well List", options=df_willow['Well List'].unique(),
                                           default=df_willow['Well List'].unique() if select_all else [])

        # Add default columns for Stages per Day and Proppant per Day
        df_willow['Stages per Day'] = stages_per_day
        df_willow['Proppant per Day'] = proppant_per_day

        # Function to estimate durations based on stages per day
        def estimate_durations_stages(df):
            df['Estimated_Stages_Duration'] = df['Planned Stages'] / df['Stages per Day']
            return df

        # Function to estimate durations based on proppant per day
        def estimate_durations_proppant(df):
            df['Estimated_Pump_Duration'] = df['Planned lbs of Proppant'] / df['Proppant per Day']
            return df

        # Determine NPT duration based on quarter
        def get_npt_duration(date):
            if date.month in [1, 2, 3]:
                return npt_q1
            elif date.month in [4, 5, 6]:
                return npt_q2
            elif date.month in [7, 8, 9]:
                return npt_q3
            else:
                return npt_q4

        # Function to check delays and add RURD and NPT Duration columns, and Crew Change Out
        def check_delays(df, duration_column, delay_column_name, projected_end_column_name):
            df['Job Start Date'] = pd.to_datetime(df['Job Start Date'])
            df['End_Date'] = df['Job Start Date'] + pd.to_timedelta(df[duration_column], unit='D')
            df[projected_end_column_name] = df['End_Date']
            df[delay_column_name] = 0
            df['RURD Duration'] = rurd_duration  # Default RURD Duration
            df['NPT Duration'] = df['Job Start Date'].apply(get_npt_duration)  # Add NPT Duration
            df['Crew Change Out'] = 0  # New column for Crew Change Out

            for i in range(len(df)):
                # Calculate the adjusted RURD Duration
                if i > 0 and df.loc[i, 'Site'] == df.loc[i - 1, 'Site']:
                    adjusted_rurd_duration = rurd_duration * batch_fracing_factor
                else:
                    adjusted_rurd_duration = rurd_duration

                # Calculate Crew Change Out days: 1 day every two weeks
                job_duration_days = df.loc[i, duration_column] + adjusted_rurd_duration
                crew_change_out_days = (job_duration_days // 14)  # 1 day every 14 days
                df.at[i, 'Crew Change Out'] = crew_change_out_days

                df.at[i, 'RURD Duration'] = adjusted_rurd_duration

                # Check and adjust for delays and end date
                if i > 0 and df.loc[i, 'Job Start Date'] < df.loc[i - 1, 'End_Date']:
                    df.loc[i, delay_column_name] = (df.loc[i - 1, 'End_Date'] - df.loc[i, 'Job Start Date']).days
                    df.loc[i, 'Job Start Date'] = df.loc[i - 1, 'End_Date']
                    df.loc[i, 'End_Date'] = df.loc[i, 'Job Start Date'] + pd.to_timedelta(
                        df.loc[i, duration_column] + adjusted_rurd_duration + df.loc[i, 'NPT Duration'] + crew_change_out_days, unit='D')
                    df.loc[i, projected_end_column_name] = df.loc[i, 'End_Date']

            return df

        # Apply the functions to the DataFrame
        df_willow_stages = estimate_durations_stages(df_willow.copy())
        df_willow_proppant = estimate_durations_proppant(df_willow.copy())

        # Remove the 'Proppant per Day' column from the stages DataFrame
        df_willow_stages.drop('Proppant per Day', axis=1, inplace=True)

        # Remove the 'Stages per Day' column from the proppant DataFrame
        df_willow_proppant.drop('Stages per Day', axis=1, inplace=True)

        df_willow_stages = check_delays(df_willow_stages, 'Estimated_Stages_Duration', 'Delay_Stages', 'Projected_End_Stages')
        df_willow_proppant = check_delays(df_willow_proppant, 'Estimated_Pump_Duration', 'Delay_Proppant', 'Projected_End_Proppant')

        filtered_df_stages = df_willow_stages[df_willow_stages['Well List'].isin(well_list)]
        filtered_df_proppant = df_willow_proppant[df_willow_proppant['Well List'].isin(well_list)]

        # Display results for stages
        st.subheader("Calculated Durations and Delays - Stages/Day")
        st.write(filtered_df_stages)

        # Display results for proppant
        st.subheader("Calculated Durations and Delays - Proppant/Day")
        st.write(filtered_df_proppant)

        st.subheader("Total Days of Delay")
        total_delay_stages = filtered_df_stages['Delay_Stages'].sum()
        total_delay_proppant = filtered_df_proppant['Delay_Proppant'].sum()

        st.markdown(f"**Total Delays (Stages):** {total_delay_stages} days")
        st.markdown(f"**Total Delays (Proppant):** {total_delay_proppant} days")

        # Plot a bar chart for stages delays using Plotly
        st.subheader("Total Delays For Each Well Bar Chart - Stages/Day")
        fig_stages = px.bar(filtered_df_stages,
                            x='Well List', y='Delay_Stages',
                            title='Delays in Stages/Day per Well',
                            labels={'Delay_Stages': 'Delay (days)', 'Well List': 'Well List'},
                            color='Delay_Stages', color_continuous_scale=px.colors.sequential.Inferno)
        fig_stages.update_layout(xaxis_title="Well", yaxis_title="Delay (days)",
                                 xaxis=dict(tickfont=dict(size=15, color='black')),
                                 yaxis=dict(tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig_stages)

        # Plot a bar chart for proppant delays using Plotly
        st.subheader("Total Delays For Each Well Bar Chart - Proppant/Day")
        fig_proppant = px.bar(filtered_df_proppant,
                              x='Well List', y='Delay_Proppant',
                              title='Delays in Proppant/Day per Well',
                              labels={'Delay_Proppant': 'Delay (days)', 'Well List': 'Well List'},
                              color='Delay_Proppant', color_continuous_scale=px.colors.sequential.Inferno)
        fig_proppant.update_layout(xaxis_title="Well", yaxis_title="Delay (days)",
                                   xaxis=dict(tickfont=dict(size=15, color='black')),
                                   yaxis=dict(tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig_proppant)

        # Gantt Chart for Job Schedule and Delays - Stages using Plotly
        st.subheader("Gantt Chart - Job Schedule (Stages/Day)")
        fig_gantt_stages = px.timeline(filtered_df_stages,
                                       x_start="Job Start Date", x_end="Projected_End_Stages",
                                       y="Well List",
                                       color="Well List",
                                       hover_data=["Delay_Stages"],
                                       title="Job Schedule and Delays (Stages)")
        fig_gantt_stages.update_layout(xaxis_title="Date", yaxis_title="Well",
                                       yaxis=dict(autorange="reversed", tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig_gantt_stages)

        # Gantt Chart for Job Schedule and Delays - Proppant using Plotly
        st.subheader("Gantt Chart - Job Schedule (Proppant/Day)")
        fig_gantt_proppant = px.timeline(filtered_df_proppant,
                                         x_start="Job Start Date", x_end="Projected_End_Proppant",
                                         y="Well List",
                                         color="Well List",
                                         hover_data=["Delay_Proppant"],
                                         title="Job Schedule and Delays (Proppant)")
        fig_gantt_proppant.update_layout(xaxis_title="Date", yaxis_title="Well",
                                         yaxis=dict(autorange="reversed", tickfont=dict(size=15, color='black')))
        st.plotly_chart(fig_gantt_proppant)

        # Provide an option to download the processed data
        st.subheader("Download Updated Job Schedule")
        buffer_stages = io.BytesIO()
        buffer_proppant = io.BytesIO()

        filtered_df_stages.to_csv(buffer_stages, index=False)
        filtered_df_proppant.to_csv(buffer_proppant, index=False)

        buffer_stages.seek(0)
        buffer_proppant.seek(0)

        st.download_button(
            label="Download Updated Job Schedule (Stages/Day) Data as CSV",
            data=buffer_stages,
            file_name='Updated_Job_Schedule_data.csv',
            mime='text/csv',
        )

        st.download_button(
            label="Download Updated Job Schedule (Proppant/Day) Data as CSV",
            data=buffer_proppant,
            file_name='Updated_Job_Schedule_data.csv',
            mime='text/csv',
        )

    except Exception as e:
        st.error(f"Error: {e}")
