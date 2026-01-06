import threading
import subprocess
import platform
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import logging
import csv

# Try to import required libraries
try:
    import winrm
    WINRM_AVAILABLE = True
except ImportError:
    WINRM_AVAILABLE = False
    print("Warning: pywinrm not installed. WinRM functionality disabled.")

try:
    import paramiko
    SSH_AVAILABLE = True
except ImportError:
    SSH_AVAILABLE = False
    print("Warning: paramiko not installed. SSH functionality disabled.")

class ScanManager:
    def __init__(self):
        self.max_workers = 30
        self.timeout = 10
        self.results = []
        self.lock = threading.Lock()
        
        # Define ranges to scan
        self.ranges = [
            (1, 200),      # Range 1: 1-190
            (900, 999)     # Range 2: 900-920
        ]
        
        self.folder_name = 'disk_ram_v2'

        # Get the parent directory (one level up from function directory)
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Windows batch script in current function directory
        self.windows_batch_script = os.path.join(os.path.dirname(__file__), 'window_os.bat')
        
        # Linux shell script in current function directory
        self.linux_shell_script = os.path.join(os.path.dirname(__file__), 'linux_os.sh')
        
        # Determine ping command based on OS
        self.ping_cmd = self._get_ping_command()
        
        # Setup logging (logs will go to parent_dir/logs)
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup unified logging - logs go to parent directory"""
        # Create logs directory in parent directory if it doesn't exist
        self.logs_dir = os.path.join(self.parent_dir, 'logs')
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
        
        # Setup single unified logger
        self.logger = logging.getLogger('scan_logger')
        self.logger.setLevel(logging.INFO)
        log_handler = logging.FileHandler(
            os.path.join(self.logs_dir, f'scan_{time.time()}.log'), 
            mode='w', 
            encoding='utf-8'
        )
        log_formatter = logging.Formatter('%(message)s')
        log_handler.setFormatter(log_formatter)
        self.logger.addHandler(log_handler)
        
        print(f"Logs will be saved to: {self.logs_dir}")
    
    def _get_ping_command(self):
        """Get appropriate ping command for the OS"""
        system = platform.system().lower()
        if system == "windows":
            return ["ping", "-n", "1", "-w", str(self.timeout * 1000)]
        else:
            return ["ping", "-c", "1", "-W", str(self.timeout)]
    
    def generate_targets(self):
        """Generate all target combinations for scanning"""
        targets = []
        
        for start, end in self.ranges:
            for i in range(start, end + 1):
                if i < 10:
                    hostname = f"css01sth00{i}ts01"
                    username = f"uss01sth00{i}ts01"
                    password = f"sth@TS00{i}"
                    fallback = None
                elif i <= 99:
                    hostname = f"css01sth{i}ts01"
                    username = f"uss01sth0{i}ts01"
                    password = f"sth@TS0{i}"
                    fallback = f"css01sth0{i}ts01"
                else:
                    hostname = f"css01sth{i}ts01"
                    username = f"uss01sth{i}ts01"
                    password = f"sth@TS{i}"
                    fallback = None
                
                targets.append({
                    'hostname': hostname,
                    'username': username,
                    'password': password,
                    'number': i,
                    'fallback': fallback
                })
        
        return targets
    
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
    
    def create_folder_winrm(self, session, hostname):
        """Create folder on Windows via WinRM"""
        folder_path = f"C:\\{self.folder_name}"
        
        try:
            self.winrm_logger.info(f"Attempting to create folder {folder_path} on {hostname}")
            
            # Check if folder exists first
            check_cmd = f'if exist "{folder_path}" (echo TRUE) else (echo FALSE)'
            result = session.run_cmd(check_cmd)
            
            if result.status_code == 0:
                output = result.std_out.decode().strip()
                if "TRUE" in output:
                    self.winrm_logger.info(f"Folder {folder_path} already exists on {hostname}, skipping creation")
                    return True, "Folder already exists"
                
                # Create folder with permissions
                create_commands = [
                    f'mkdir "{folder_path}"',
                    f'icacls "{folder_path}" /grant Everyone:(OI)(CI)F /T',
                    f'icacls "{folder_path}" /setowner Users /T'
                ]
                
                for cmd in create_commands:
                    self.winrm_logger.debug(f"Running command on {hostname}: {cmd}")
                    result = session.run_cmd(cmd)
                    
                    if result.status_code != 0:
                        error_output = result.std_err.decode() if result.std_err else "No error output"
                        self.winrm_logger.warning(f"Command '{cmd}' failed on {hostname}. Status: {result.status_code}, Error: {error_output}")
                        # Continue with other commands even if one fails
                
                # Verify folder was created
                verify_result = session.run_cmd(check_cmd)
                if verify_result.status_code == 0 and "TRUE" in verify_result.std_out.decode():
                    self.winrm_logger.info(f"Successfully created folder {folder_path} on {hostname}")
                    return True, "Folder created successfully"
                else:
                    self.winrm_logger.error(f"Failed to verify folder creation on {hostname}")
                    return False, "Folder creation verification failed"
            else:
                error_output = result.std_err.decode() if result.std_err else "No error output"
                self.winrm_logger.error(f"Failed to check folder existence on {hostname}: {error_output}")
                return False, "Failed to check folder existence"
                
        except Exception as e:
            self.winrm_logger.error(f"Exception during folder creation on {hostname}: {str(e)}")
            return False, f"Exception: {str(e)}"
    
    def create_folder_ssh(self, ssh, hostname):
        """Create folder on Windows via SSH (Windows focus only)"""
        folder_path = f"C:\\{self.folder_name}"
        
        try:
            self.ssh_logger.info(f"Attempting to create folder {folder_path} on {hostname} via SSH")
            
            # Check if folder exists first
            check_cmd = f'if exist "{folder_path}" (echo TRUE) else (echo FALSE)'
            stdin, stdout, stderr = ssh.exec_command(check_cmd, timeout=10)
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output and "TRUE" in output:
                self.ssh_logger.info(f"Folder {folder_path} already exists on {hostname}, skipping creation")
                return True, "Folder already exists"
            
            # Create folder with permissions
            create_commands = [
                f'mkdir "{folder_path}"',
                f'icacls "{folder_path}" /grant Everyone:(OI)(CI)F /T',
                f'icacls "{folder_path}" /setowner Users /T'
            ]
            
            for cmd in create_commands:
                try:
                    self.ssh_logger.debug(f"Running SSH command on {hostname}: {cmd}")
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
                    
                    cmd_output = stdout.read().decode().strip()
                    cmd_error = stderr.read().decode().strip()
                    
                    if cmd_error:
                        self.ssh_logger.warning(f"SSH command '{cmd}' had error on {hostname}: {cmd_error}")
                    else:
                        self.ssh_logger.debug(f"SSH command '{cmd}' output on {hostname}: {cmd_output}")
                        
                except Exception as e:
                    self.ssh_logger.warning(f"SSH command '{cmd}' failed on {hostname}: {str(e)}")
                    continue
            
            # Verify folder was created
            stdin, stdout, stderr = ssh.exec_command(check_cmd, timeout=10)
            verify_output = stdout.read().decode().strip()
            
            if verify_output and "TRUE" in verify_output:
                self.ssh_logger.info(f"Successfully created folder {folder_path} on {hostname} via SSH")
                return True, "Folder created successfully"
            else:
                self.ssh_logger.error(f"Failed to verify folder creation on {hostname} via SSH")
                return False, "Folder creation verification failed"
                
        except Exception as e:
            self.ssh_logger.error(f"Exception during SSH folder creation on {hostname}: {str(e)}")
            return False, f"Exception: {str(e)}"
    
    def test_winrm_session(self, hostname, username, password):
        """Test WinRM connection and get platform info using batch only"""
        if not WINRM_AVAILABLE:
            self.winrm_logger.warning("WinRM library not available")
            return False, None, None
        
        self.winrm_logger.info(f"Testing WinRM connection to {hostname} with user {username}")
        
        try:
            # Create WinRM session
            session = winrm.Session(
                f'http://{hostname}:5985/wsman',
                auth=(username, password),
                transport='ntlm'
            )
            self.winrm_logger.debug(f"WinRM session created for {hostname}")
            
            # Try batch command to get OS info
            try:
                self.winrm_logger.debug(f"Trying batch command on {hostname}")
                result = session.run_cmd('echo %OS%')
                
                if result.status_code == 0:
                    platform_info = result.std_out.decode().strip()
                    if platform_info and platform_info != '%OS%':
                        self.winrm_logger.info(f"WinRM Batch SUCCESS for {hostname}: {platform_info}")
                        
                        # Create folder after successful platform detection
                        folder_success, folder_message = self.create_folder_winrm(session, hostname)
                        
                        return True, platform_info, folder_message
                else:
                    error_output = result.std_err.decode() if result.std_err else "No error output"
                    self.winrm_logger.error(f"Batch command failed for {hostname}. Status: {result.status_code}, Error: {error_output}")
            except Exception as e:
                self.winrm_logger.error(f"Batch command error on {hostname}: {str(e)}")
            
            return False, None, None
                
        except Exception as e:
            self.winrm_logger.error(f"WinRM connection failed for {hostname}: {type(e).__name__}: {str(e)}")
            return False, None, None
    
    def test_ssh_session(self, hostname, username, password):
        """Test SSH connection and get platform info - Windows focus only"""
        if not SSH_AVAILABLE:
            return False, None, None
        
        ssh = None
        try:
            # Create SSH client
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            ssh.connect(
                hostname=hostname,
                username=username,
                password=password,
                timeout=self.timeout + 5,
                look_for_keys=False,
                allow_agent=False
            )
            
            # Try Windows batch commands only (focus on Windows)
            try:
                stdin, stdout, stderr = ssh.exec_command('echo %OS%', timeout=10)
                
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                if output and not error and output != '%OS%':
                    # Parse Windows output
                    if 'Windows' in output or 'Microsoft Windows' in output or 'Windows_NT' in output:
                        platform_info = 'Windows_NT'
                    else:
                        platform_info = output
                    
                    self.logger.info(f"SSH {hostname}: connected")
                    
                    # Create folder after successful platform detection
                    folder_success, folder_message = self.create_folder_ssh(ssh, hostname)
                    
                    ssh.close()
                    return True, platform_info, folder_message
            except Exception as e:
                pass
            
            ssh.close()
            return False, None, None
                
        except paramiko.AuthenticationException as e:
            if ssh:
                ssh.close()
            return False, None, None
        except paramiko.SSHException as e:
            if ssh:
                ssh.close()
            return False, None, None
        except Exception as e:
            if ssh:
                ssh.close()
            return False, None, None
    
    def test_remote_host(self, target):
        """Test remote host with ping, then WinRM/SSH, then platform detection and folder creation"""
        hostname = target['hostname']
        fallback = target['fallback']
        username = target['username']
        password = target['password']
        
        # Try primary hostname first
        working_hostname = None
        if self.ping_hostname(hostname):
            working_hostname = hostname
        elif fallback and self.ping_hostname(fallback):
            working_hostname = fallback
        
        if not working_hostname:
            return {
                'host': hostname,
                'user': username,
                'pwd': password,
                'platform': '',
                'pingable': False,
                'protocol': '',
                'folder_status': 'N/A - Not pingable'
            }
        
        # Host is pingable, now test remote sessions
        # Try WinRM first
        winrm_success, platform_info, folder_message = self.test_winrm_session(
            working_hostname, username, password
        )
        
        if winrm_success:
            return {
                'host': working_hostname,
                'user': username,
                'pwd': password,
                'platform': platform_info or 'Unknown',
                'pingable': True,
                'protocol': 'winrm',
                'folder_status': folder_message or 'Unknown'
            }
        
        # WinRM failed, try SSH
        ssh_success, platform_info, folder_message = self.test_ssh_session(
            working_hostname, username, password
        )
        
        if ssh_success:
            return {
                'host': working_hostname,
                'user': username,
                'pwd': password,
                'platform': platform_info or 'Unknown',
                'pingable': True,
                'protocol': 'ssh',
                'folder_status': folder_message or 'Unknown'
            }
        
        # All protocols failed
        return {
            'host': working_hostname,
            'user': username,
            'pwd': password,
            'platform': '',
            'pingable': True,
            'protocol': 'none',
            'folder_status': 'N/A - Connection failed'
        }
    
    def print_progress_bar(self, completed, total, successful_count, bar_length=50):
        """Print a progress bar"""
        percent = float(completed) / total
        filled_length = int(bar_length * percent)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        print(f'\rProgress: |{bar}| {completed}/{total} ({percent:.1%}) | Successful: {successful_count}', end='', flush=True)
    
    def scan_and_test_network(self):
        """Perform network scan with remote session testing"""
        targets = self.generate_targets()
        total_targets = len(targets)
        
        print(f"Starting remote host testing with folder creation...")
        print(f"Ranges: {self.ranges}")
        print(f"Total targets: {total_targets}")
        print(f"Max Workers: {self.max_workers}")
        print(f"Timeout: {self.timeout} seconds")
        print(f"WinRM Available: {WINRM_AVAILABLE}")
        print(f"SSH Available: {SSH_AVAILABLE}")
        print(f"Folder to create: C:\\{self.folder_name}")
        print()
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_target = {
                executor.submit(self.test_remote_host, target): target
                for target in targets
            }
            
            completed = 0
            successful_count = 0
            
            self.print_progress_bar(0, total_targets, 0)
            
            for future in as_completed(future_to_target):
                try:
                    result = future.result()
                    
                    with self.lock:
                        self.results.append(result)
                        completed += 1
                        if result['pingable'] and result.get('protocol') in ['winrm', 'ssh']:
                            successful_count += 1
                    
                    self.print_progress_bar(completed, total_targets, successful_count)
                        
                except Exception as e:
                    self.general_logger.error(f"Unexpected error in thread: {str(e)}")
                    with self.lock:
                        completed += 1
                    self.print_progress_bar(completed, total_targets, successful_count)
        
        end_time = time.time()
        print(f"\n\nScan completed in {end_time - start_time:.2f} seconds")
        
        # Count results
        pingable = len([r for r in self.results if r['pingable']])
        winrm_success = len([r for r in self.results if r.get('protocol') == 'winrm'])
        ssh_success = len([r for r in self.results if r.get('protocol') == 'ssh'])
        folder_created = len([r for r in self.results if 'created successfully' in r.get('folder_status', '')])
        folder_exists = len([r for r in self.results if 'already exists' in r.get('folder_status', '')])
        
        print(f"Total: {len(self.results)} | Pingable: {pingable} | WinRM: {winrm_success} | SSH: {ssh_success}")
        print(f"Folder Results: Created: {folder_created} | Already Existed: {folder_exists}")
        
        return self.results
    
    def save_csv(self, filename=None):
        """Save results to CSV file with simplified format including folder status"""
        if filename is None:
            filename = os.path.join(self.logs_dir, f"remote_hosts_results_{time.time()}.csv")
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['host', 'user', 'pwd', 'platform', 'pingable', 'protocol', 'folder_status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result)
            
            print(f"Results saved to CSV: {filename}")
            return filename
        except Exception as e:
            print(f"Error saving CSV file: {e}")
            return None
    
    def save_json(self, filename=None):
        """Save results to JSON file"""
        if filename is None:
            filename = os.path.join(self.parent_dir, "config", "config.json")
        
        try:
            # Create config directory if it doesn't exist
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            
            print(f"Results saved to JSON: {filename}")
            return filename
        except Exception as e:
            print(f"Error saving JSON file: {e}")
            return None

def main():
    if not WINRM_AVAILABLE and not SSH_AVAILABLE:
        print("Error: Neither pywinrm nor paramiko is installed.")
        print("Install with: pip install pywinrm paramiko")
        return
    
    tester = ScanManager()
    _ = tester.scan_and_test_network()
    
    # Save all results to CSV and JSON
    tester.save_csv()
    tester.save_json()
    
    print("\nOutput files created:")
    print("- logs/remote_hosts_results.csv - All scan results with folder creation status")
    print("- config/config.json - All results in JSON format")
    print("- logs/scan.log - Execution log")

if __name__ == "__main__":
    main()