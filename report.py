import os
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd


def read_all_monitor_csv(folder_path):
    """
    Read all *_monitor_results.csv files from a folder
    
    Args:
        folder_path (str): Path to the folder containing CSV files
        
    Returns:
        Combined DataFrame with all data
    """
    folder = Path(folder_path)
    
    if not folder.exists():
        return pd.DataFrame()
    
    if not folder.is_dir():
        return pd.DataFrame()
    
    # Find all CSV files matching the pattern *_monitor_results.csv
    csv_files = list(folder.glob("*_monitor_results.csv"))
    
    if not csv_files:
        return pd.DataFrame()
    
    all_dataframes = []
    
    # Loop through each CSV file
    for csv_file in csv_files:
        try:
            # Read CSV file
            df = pd.read_csv(csv_file)
            
            if len(df) > 0:
                # First filter by Mode = "normal" (case insensitive)
                if 'Mode' in df.columns:
                    normal_df = df[df['Mode'].str.lower() == 'normal'].copy()
                    
                    if len(normal_df) > 0:
                        # Get the latest 28 records from filtered data
                        latest_records = normal_df.tail(28).copy() if len(normal_df) > 28 else normal_df.copy()
                        all_dataframes.append(latest_records)
                        
        except Exception as e:
            continue
    
    # Combine all DataFrames
    if all_dataframes:
        combined_df = pd.concat(all_dataframes, ignore_index=True)
        return combined_df
    else:
        return pd.DataFrame()

def process_and_export_data(df, folder_path):
    """
    Process the combined DataFrame and export to CSV with specified format
    
    Args:
        df: Combined DataFrame from all CSV files
        folder_path (str): Path to the folder where output will be saved
        
    Returns:
        Path to the exported CSV file
    """
    if df.empty:
        return None
    
    try:
        # Define the required columns in the specified order
        required_columns = [
            'Timestamp',
            'PC_Name', 
            'CPU_Usage_%',
            'CPU_Threshold_%',
            'RAM_Used_%',
            'RAM_Threshold_%',
            'Disk1_Used_%',
            'Disk1_Threshold_%',
            'Disk2_Used_%',
            'Disk2_Threshold_%'
        ]
        
        # Check if all required columns exist
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return None
        
        # Select only the required columns
        processed_df = df[required_columns].copy()
        
        # Convert Timestamp to datetime for proper sorting
        try:
            processed_df['Timestamp'] = pd.to_datetime(processed_df['Timestamp'])
        except Exception as e:
            pass
        
        # Sort by Timestamp first, then by PC_Name
        processed_df = processed_df.sort_values(['Timestamp', 'PC_Name'], ascending=[True, True])
        
        # Reset index after sorting
        processed_df = processed_df.reset_index(drop=True)
        
        # Generate output file path in the same folder with timestamp
        folder = Path(folder_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = folder / f"monitor_result_{timestamp}.csv"
        
        # Export to CSV
        processed_df.to_csv(output_path, index=False)
        
        return str(output_path)
        
    except Exception as e:
        return None


def generate_monitor_report(folder_path):
    """
    Main function to generate monitor report
    
    Args:
        folder_path (str): Path to the folder containing CSV files
        
    Returns:
        Path to the exported CSV file
    """
    # Read CSV data from all files in folder
    combined_df = read_all_monitor_csv(folder_path)
    
    if combined_df.empty:
        return None
    
    # Process and export the data
    output_path = process_and_export_data(combined_df, folder_path)
    
    return output_path


def main():
    """Main function to run the script."""
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = "."
    
    generate_monitor_report(folder_path)


if __name__ == "__main__":
    main()