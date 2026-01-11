"""
Script to check the modified datetime of CSV files matching *_monitor_results.csv pattern
and export a report with status based on modification time.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, time
import pandas as pd


def check_csv_modified_times(folder_path, output_file="monitor_status_report.csv"):
    """
    Check and export the modified datetime of CSV files matching *_monitor_results.csv pattern.
    Status is "normal" if modified at 6am today, otherwise "broken".
    
    Args:
        folder_path (str): Path to the folder containing CSV files
        output_file (str): Name of the output CSV report file
    
    Returns:
        pd.DataFrame: DataFrame containing the report data
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
    
    # Extract name and get modification times
    data = []
    today = datetime.now().date()
    target_time = datetime.combine(today, time(6, 0, 0))  # 6am today
    
    for csv_file in csv_files:
        # Extract name from filename (remove _monitor_results.csv)
        name = csv_file.name.replace("_monitor_results.csv", "")
        
        # Get modified datetime
        modified_timestamp = csv_file.stat().st_mtime
        modified_datetime = datetime.fromtimestamp(modified_timestamp)
        
        # Determine status based on logic
        # Normal if modified at 6am today (within 1 minute tolerance)
        if modified_datetime.date() == today and abs((modified_datetime - target_time).total_seconds()) < 60:
            status = "normal"
        else:
            status = "broken"
        
        data.append({
            'name': name,
            'status': status,
            'last modified': modified_datetime.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    df = df.sort_values('name').reset_index(drop=True)
    
    # Export to CSV
    output_path = folder / output_file
    df.to_csv(output_path, index=False)
    
    return df


def main():
    """Main function to run the script."""
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else "monitor_status_report.csv"
    else:
        # Use current directory if no argument provided
        folder_path = input("Enter folder path (or press Enter for current directory): ").strip()
        if not folder_path:
            folder_path = "."
        output_file = "monitor_status_report.csv"
    
    check_csv_modified_times(folder_path, output_file)


if __name__ == "__main__":
    main()
