# Helpdesk Guide: Installing Sensors from First Principles

Welcome! If you are part of the Helpdesk team, your goal is to install the **Open Network Experience (ONE)** test software onto remote computers (sensors).

To do this successfully, we will use **First Principles Thinking**. Instead of just memorizing commands, let's break down exactly *what* we are doing and *why*.

## 🧱 The First Principles of Remote Installation

To install software on a computer that is far away, we only need three fundamental things:
1. **Access (The Door):** We need a secure way to talk to the remote computer. We use **SSH** (Secure Shell) for this.
2. **Payload (The Package):** We need to send the actual software files to the remote computer. We use **SFTP** (Secure File Transfer Protocol) to copy a `.zip` file over.
3. **Execution (The Action):** We need to tell the remote computer to unzip the files and run the installer.

That's it! Everything our automated deployment script does boils down to these three simple truths.

---

## 🛠 Prerequisites: What You Need Before Starting

Before you can run the deployment, you must have the following information:
- **The IP Addresses** of the target sensors (e.g., `10.98.2.125`, `10.98.2.141`, `10.98.2.105`).
- **The Username** for the sensors (e.g., `kern`).
- **The Password** for the sensors (e.g., `Kern1234`).
- **The Payload**: The `bench-staging-kit.zip` downloaded from the Central Monitoring Platform (CMP).

---

## 🚀 How to Run the Automated Deployment

We have written a Python script that automatically handles the Access, Payload, and Execution steps for you.

### Step 1: Open Your Terminal
Open the terminal on your admin workstation and navigate to the project directory:
```bash
cd /data/Open_Network_Experience
```

### Step 2: Review the Targets (Optional but Recommended)
Open `deploy_tests.py` in a text editor to verify that the IP addresses, username, and password match your current batch of sensors:
```python
TARGETS = [
    "10.98.2.125",
    "10.98.2.141",
    "10.98.2.105"
]
USERNAME = "kern"
PASSWORD = "Kern1234"
```

### Step 3: Execute the Deployment
Run the script to begin the process:
```bash
python3 deploy_tests.py
```

### Step 4: Understand the Output
As the script runs, it will print out its progress based on our First Principles:
1. `Uploading bench-staging-kit.zip...` -> **(The Payload)**
2. `Extracting and installing tests...` -> **(The Execution)**
3. `Deployment SUCCESSFUL!` -> The sensor is now fully provisioned and communicating with the CMP.

If an error occurs (e.g., `TimeoutError`), refer back to the First Principles:
- Did the Access fail? (Is the sensor powered on? Is the IP correct?)
- Did the Execution fail? (Is the password correct for `sudo` commands?)

---

## 🎯 Summary
By understanding the fundamental mechanics of Access, Payload, and Execution, you are not just running a script—you are managing the fleet!
