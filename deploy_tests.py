#!/usr/bin/env python3
"""
Open Network Experience - Automated Sensor Test Deployment Script
For use by Helpdesk staff to deploy sensor tests to target computers.
"""

import paramiko

TARGETS = [
    "10.98.2.125",
    "10.98.2.141",
    "10.98.2.105"
]
USERNAME = "kern"
PASSWORD = "Kern1234"

def deploy_to_host(ip):
    print("\n==============================================")
    print(f"Deploying tests to {ip}...")
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username=USERNAME, password=PASSWORD, timeout=10)

        # 1. Open SFTP to upload the staging kit
        print(f"[{ip}] Uploading bench-staging-kit.zip...")
        sftp = ssh.open_sftp()
        sftp.put("bench-staging-kit.zip", "/home/kern/bench-staging-kit.zip")
        sftp.close()

        # 2. Extract and run setup
        print(f"[{ip}] Extracting and installing tests (this may take a minute)...")
        cmd = """
        sudo -S apt-get update -qq
        sudo -S apt-get install -y unzip
        rm -rf /home/kern/usb_staging
        unzip -q /home/kern/bench-staging-kit.zip -d /home/kern/usb_staging
        cd /home/kern/usb_staging
        sudo -S ./setup.sh
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdin.write(PASSWORD + "\n" + PASSWORD + "\n" + PASSWORD + "\n")
        stdin.flush()

        # Wait for command to finish and print output
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()

        if exit_status == 0:
            print(f"[{ip}] Deployment SUCCESSFUL!")
        else:
            print(f"[{ip}] Deployment FAILED! Exit status {exit_status}")
            print(f"[{ip}] Error output:\n{err}")
            print(f"[{ip}] Standard output:\n{out}")

        ssh.close()
    except Exception as e:
        print(f"[{ip}] ERROR: {e}")

if __name__ == "__main__":
    print("Starting ONE Sensor Test Deployment...")
    for ip in TARGETS:
        deploy_to_host(ip)
    print("\nDeployment run complete.")
