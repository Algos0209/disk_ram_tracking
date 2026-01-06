import json
import os
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

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

class InstallManager:
    def __init__(self, config_path="config/config.json", settings_path="config/settings.json", log_dir="logs", max_workers=30):
        # Get the parent directory (one level up from function directory)
        self.parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.parent_dir, config_path)
        self.settings_path = os.path.join(self.parent_dir, settings_path)
        self.log_dir = os.path.join(self.parent_dir, log_dir)
        self.max_workers = max_workers
        self.successful_copies = 0
        self.completed_count = 0
        self.total_hosts = 0
        self.lock = threading.Lock()
        
        # Load settings first
        self.load_settings()
        
        # Setup logging
        self._setup_logging()
        
    def load_settings(self):
        """Load settings from settings.json"""
        try:
            with open(self.settings_path, 'r') as f:
                settings = json.load(f)
            
            # Set dynamic variables from settings
            self.source_path = settings.get('source', '')
            self.target_path = settings.get('target', '')
            self.setup_file = settings.get('setup_file', '')
            
        except FileNotFoundError:
            print(f"Settings file not found: {self.settings_path}")

        except json.JSONDecodeError as e:
            print(f"Error parsing settings JSON: {e}")
        
    def _setup_logging(self):
        """Setup logging configuration - file only, no console output"""
        # Create logs directory if it doesn't exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # Create main logger for install operations
        self.logger = logging.getLogger('install_logger')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(self.log_dir, f'install_operation_{timestamp}.log')
        
        install_handler = logging.FileHandler(
            log_file, 
            mode='w', 
            encoding='utf-8'
        )
        install_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        install_handler.setFormatter(install_formatter)
        self.logger.addHandler(install_handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
        
        # Log session start
        self.logger.info("=== Install Operation Session Started ===")
        
        # Only show log location in console
        print(f"Logs will be saved to: {log_file}")
        
    def load_config(self):
        """Load and filter configuration"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Filter only pingable Windows hosts with successful protocol connection
            windows_hosts = [host for host in config 
                           if host.get('pingable', False) and 
                           host.get('platform', '').lower() == 'windows_nt' and
                           host.get('protocol') in ['winrm', 'ssh']]
            
            self.logger.info(f"Loaded {len(windows_hosts)} pingable Windows hosts with remote access from config")
            
            return windows_hosts
            
        except FileNotFoundError:
            self.logger.error(f"Config file not found: {self.config_path}")
            return []
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing JSON config: {e}")
            return []
    
    def print_progress_bar(self, completed, total, successful_count, bar_length=50):
        """Print a progress bar"""
        percent = float(completed) / total
        filled_length = int(bar_length * percent)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)
        
        print(f'\rProgress: |{bar}| {completed}/{total} ({percent:.1%}) | Successful: {successful_count}', end='', flush=True)

    def create_winrm_session(self, hostname, username, password):
        """Create WinRM session"""
        try:
            session = winrm.Session(
                f'http://{hostname}:5985/wsman',
                auth=(username, password),
                transport='ntlm'
            )
            return session
        except Exception as e:
            self.logger.error(f"Failed to create WinRM session for {hostname}: {e}")
            return None
    
    def create_ssh_session(self, hostname, username, password):
        """Create SSH session"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=hostname,
                username=username,
                password=password,
                timeout=30,
                look_for_keys=False,
                allow_agent=False
            )
            return ssh
        except Exception as e:
            self.logger.error(f"Failed to create SSH session for {hostname}: {e}")
            return None

    def copy_bat_winrm(self, session, target_dir, hostname, username, password):
        """Copy .bat file to target directory via WinRM"""
        try:
            # Copy existing bat file from source
            bat_copy_cmd = f'net use B: "{self.source_path}" /user:{username} {password} && copy "B:\\{self.setup_file}" "{target_dir}\\{self.setup_file}" /Y && net use B: /delete'
            
            self.logger.info(f"Copying .bat file to {hostname}: {bat_copy_cmd}")
            result = session.run_cmd(bat_copy_cmd)
            
            if result.status_code != 0:
                error_output = result.std_err.decode('utf-8', errors='ignore') if result.std_err else "No error output"
                self.logger.error(f"Failed to copy .bat file to {hostname}: {error_output}")
                return False
            
            self.logger.info(f".bat file ready on {hostname}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error preparing .bat file on {hostname} via WinRM: {e}")
            return False

    def copy_bat_ssh(self, ssh, target_dir, hostname, username, password):
        """Copy .bat file to target directory via SSH"""
        try:
            # Copy existing bat file from source
            bat_copy_cmd = f'net use B: "{self.source_path}" /user:{username} {password} && copy "B:\\{self.setup_file}" "{target_dir}\\{self.setup_file}" /Y && net use B: /delete'
            
            self.logger.info(f"Copying .bat file to {hostname} via SSH")
            _, stdout, stderr = ssh.exec_command(bat_copy_cmd, timeout=60)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code != 0:
                stderr_output = stderr.read().decode('utf-8', errors='ignore')
                self.logger.error(f"Failed to copy .bat file to {hostname} via SSH: {stderr_output}")
                return False
            
            self.logger.info(f".bat file ready on {hostname} via SSH")
            return True
            
        except Exception as e:
            self.logger.error(f"Error preparing .bat file on {hostname} via SSH: {e}")
            return False

    def execute_bat_winrm(self, session, target_dir, hostname):
        """Execute .bat file via WinRM"""
        try:
            # Execute the .bat file
            execute_cmd = f'cd /d "{target_dir}" && {self.setup_file}'
            
            self.logger.info(f"Executing {self.setup_file} on {hostname}: {execute_cmd}")
            
            result = session.run_cmd(execute_cmd)
            
            # Get output for logging
            stdout_output = result.std_out.decode('utf-8', errors='ignore').strip() if result.std_out else ""
            stderr_output = result.std_err.decode('utf-8', errors='ignore').strip() if result.std_err else ""
            
            self.logger.info(f"{self.setup_file} execution completed for {hostname} (exit code: {result.status_code})")
            
            if stdout_output:
                self.logger.info(f"{self.setup_file} output for {hostname}: {stdout_output}")
            if stderr_output:
                self.logger.debug(f"{self.setup_file} stderr for {hostname}: {stderr_output}")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error executing {self.setup_file} on {hostname} via WinRM: {e}")
            return False

    def execute_bat_ssh(self, ssh, target_dir, hostname):
        """Execute .bat file via SSH"""
        try:
            # Execute the .bat file
            execute_cmd = f'cd /d "{target_dir}" && {self.setup_file}'
            
            self.logger.info(f"Executing {self.setup_file} on {hostname} via SSH: {execute_cmd}")
            
            stdin, stdout, stderr = ssh.exec_command(execute_cmd, timeout=120)
            exit_code = stdout.channel.recv_exit_status()
            
            # Get output for logging
            stdout_output = stdout.read().decode('utf-8', errors='ignore').strip()
            stderr_output = stderr.read().decode('utf-8', errors='ignore').strip()
            
            self.logger.info(f"{self.setup_file} execution completed for {hostname} via SSH (exit code: {exit_code})")
            
            if stdout_output:
                self.logger.info(f"{self.setup_file} output for {hostname}: {stdout_output}")
            if stderr_output:
                self.logger.debug(f"{self.setup_file} stderr for {hostname}: {stderr_output}")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error executing {self.setup_file} on {hostname} via SSH: {e}")
            return False
    
    def process_host(self, host_config):
        """Process a single host"""
        hostname = host_config['host']
        username = host_config['user']
        password = host_config['pwd']
        protocol = host_config['protocol']
        
        try:
            self.logger.info(f"Processing host: {hostname} via {protocol}")
            
            bat_copy_success = False
            success = False
            
            if protocol == 'winrm' and WINRM_AVAILABLE:
                # Use WinRM
                session = self.create_winrm_session(hostname, username, password)
                if session:
                    # Step 1: Copy/create .bat file
                    bat_copy_success = self.copy_bat_winrm(session, self.target_path, hostname, username, password)
                    
                    # Step 2: Execute .bat if it was created successfully
                    if bat_copy_success:
                        success = self.execute_bat_winrm(session, self.target_path, hostname)
                        
            elif protocol == 'ssh' and SSH_AVAILABLE:
                # Use SSH
                ssh = self.create_ssh_session(hostname, username, password)
                if ssh:
                    try:
                        # Step 1: Copy/create .bat file
                        bat_copy_success = self.copy_bat_ssh(ssh, self.target_path, hostname, username, password)
                        
                        # Step 2: Execute .bat if it was created successfully
                        if bat_copy_success:
                            success = self.execute_bat_ssh(ssh, self.target_path, hostname)
                        
                    finally:
                        ssh.close()
            else:
                self.logger.error(f"Protocol {protocol} not available or supported for {hostname}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error processing host {hostname}: {e}")
            return False
        finally:
            # Update counters
            with self.lock:
                self.completed_count += 1
                if 'success' in locals() and success:
                    self.successful_copies += 1
                
                # Update progress bar
                self.print_progress_bar(self.completed_count, self.total_hosts, self.successful_copies)

    def validate_settings(self):
        """Validate that settings are properly loaded"""
        if not self.source_path:
            self.logger.error("Source path not configured in settings")
            return False
            
        # Check if required libraries are available
        if not WINRM_AVAILABLE and not SSH_AVAILABLE:
            self.logger.error("Neither WinRM nor SSH libraries are available")
            return False
            
        return True
    
    def process_all_hosts(self):
        """Process all hosts using multithreading"""
        # Validate settings first
        if not self.validate_settings():
            self.logger.error("Settings validation failed")
            return
            
        hosts = self.load_config()
        
        if not hosts:
            self.logger.error("No pingable Windows hosts with remote access to process")
            return
        
        self.total_hosts = len(hosts)
        
        self.logger.info(f"Starting operation for {len(hosts)} hosts with {self.max_workers} workers")
        self.logger.info(f"Source path: {self.source_path}")
        self.logger.info(f"Setup file: {self.setup_file}")
        self.logger.info(f"WinRM Available: {WINRM_AVAILABLE}")
        self.logger.info(f"SSH Available: {SSH_AVAILABLE}")
        
        # Initialize progress bar
        print(f"Processing {len(hosts)} hosts with setup operations...")
        self.print_progress_bar(0, self.total_hosts, 0)
        
        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_host = {
                executor.submit(self.process_host, host): host['host'] 
                for host in hosts
            }
            
            # Wait for completion
            for future in as_completed(future_to_host):
                host_name = future_to_host[future]
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Exception processing {host_name}: {e}")
        
        # Final progress update and results
        print()  # New line after progress bar
        
        # Export verification results to CSV
        self.export_verification_results_to_csv()
        
        self.logger.info("="*50)
        self.logger.info("OPERATION COMPLETED")
        self.logger.info(f"Total hosts processed: {len(hosts)}")
        self.logger.info(f"Copy success rate: {(self.successful_copies/len(hosts)*100):.1f}%")
        self.logger.info("="*50)


def main():
    if not WINRM_AVAILABLE and not SSH_AVAILABLE:
        print("Error: Neither pywinrm nor paramiko is installed.")
        print("Install with: pip install pywinrm paramiko")
        return
    
    manager = InstallManager()
    manager.process_all_hosts()

if __name__ == "__main__":
    main()