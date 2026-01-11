"""
Script to check monitor_results.csv status across multiple hosts
"""

import os
import csv
import threading
import subprocess
import platform
from pathlib import Path
from datetime import datetime, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd


class HostChecker:
    def __init__(self, csv_file="list_tool.csv", max_workers=30):
        self.csv_file = csv_file
        self.max_workers = max_workers
        self.timeout = 10
        self.results = []
        self.lock = threading.Lock()
        
        # Folder and file to check
        self.target_folder = "disk_ram_v2"
        self.target_file = "monitor_results.csv"
        
        # Determine ping command based on OS
        self.ping_cmd = self._get_ping_command()
    
    def _get_ping_command(self):
        """Get appropriate ping command for the OS"""
        system = platform.system().lower()
        if system == "windows":
            return ["ping", "-n", "1", "-w", str(self.timeout * 1000)]
        else:
            return ["ping", "-c", "1", "-W", str(self.timeout)]
    
    def load_hosts(self):
        """Load hosts from CSV file"""
        hosts = []
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    hosts.append({
                        'host': row.get('host', ''),
                        'user': row.get('user', ''),
                        'pwd': row.get('pwd', '')
                    })
            return hosts
        except FileNotFoundError:
            return []
        except Exception as e:
            return []
    
    def ping_hostname(self, hostname):
        """Ping a single hostname and return success/failure"""
        try:
            cmd = self.ping_cmd + [hostname]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 2
            )
            return result.returncode == 0
        except Exception as e:
            return False
    
    def check_file_modified_time(self, hostname):
        """
        Check for monitor_results.csv file in C or C2 drive and get modified time
        
        Returns:
            tuple: (found, modified_datetime, location)
        """
        # Try both possible paths
        paths_to_check = [
            f"\\\\{hostname}\\C\\{self.target_folder}",
            f"\\\\{hostname}\\C2\\{self.target_folder}"
        ]
        
        for path in paths_to_check:
            try:
                folder = Path(path)
                if folder.exists() and folder.is_dir():
                    csv_file = folder / self.target_file
                    
                    if csv_file.exists() and csv_file.is_file():
                        # Get modified time
                        modified_timestamp = csv_file.stat().st_mtime
                        modified_datetime = datetime.fromtimestamp(modified_timestamp)
                        
                        location = "C" if "\\C\\" in path else "C2"
                        return True, modified_datetime, location
            except Exception as e:
                continue
        
        return False, None, None
    
    def check_single_host(self, host_info):
        """
        Check a single host:
        1. Ping
        2. Check file if pingable
        3. Determine status based on logic
        """
        hostname = host_info['host']
        
        # Step 1: Ping the host
        if not self.ping_hostname(hostname):
            return {
                'name': hostname,
                'status': 'not pingable',
                'last modified': ''
            }
        
        # Step 2: Check for file
        file_found, modified_datetime, location = self.check_file_modified_time(hostname)
        
        if not file_found:
            return {
                'name': hostname,
                'status': 'not installed',
                'last modified': ''
            }
        
        # Step 3: Check if modified at 6am today
        today = datetime.now().date()
        target_time = datetime.combine(today, time(6, 0, 0))  # 6am today
        
        # Check if modified at 6am today (within 1 minute tolerance)
        if modified_datetime.date() == today and abs((modified_datetime - target_time).total_seconds()) < 60:
            status = "normal"
        else:
            status = "need check"
        
        return {
            'name': hostname,
            'status': status,
            'last modified': modified_datetime.strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def print_progress_bar(self, completed, total, bar_length=50):
        """Print a progress bar"""
        percent = float(completed) / total
        filled_length = int(bar_length * percent)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        print(f'\rProgress: |{bar}| {completed}/{total} ({percent:.1%})', end='', flush=True)
    
    def check_all_hosts(self):
        """Check all hosts using multithreading"""
        hosts = self.load_hosts()
        
        if not hosts:
            return pd.DataFrame()
        
        total_hosts = len(hosts)
        completed = 0
        
        self.print_progress_bar(0, total_hosts)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_host = {
                executor.submit(self.check_single_host, host): host
                for host in hosts
            }
            
            for future in as_completed(future_to_host):
                try:
                    result = future.result()
                    
                    with self.lock:
                        self.results.append(result)
                        completed += 1
                    
                    self.print_progress_bar(completed, total_hosts)
                        
                except Exception as e:
                    with self.lock:
                        completed += 1
                    self.print_progress_bar(completed, total_hosts)
        
        print()  # New line after progress bar
        
        # Create DataFrame and sort by name
        df = pd.DataFrame(self.results)
        df = df.sort_values('name').reset_index(drop=True)
        
        return df
    
    def export_report(self, df, output_file="monitor_status_report.csv"):
        """Export the results to CSV file"""
        if df.empty:
            return None
        
        # Generate output file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"monitor_status_report_{timestamp}.csv"
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        return output_path


def main():
    """Main function to run the script."""
    checker = HostChecker()
    
    # Check all hosts
    df = checker.check_all_hosts()
    
    if not df.empty:
        # Export report
        _ = checker.export_report(df)
    

if __name__ == "__main__":
    main()
