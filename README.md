# 🛡️ pulse-sentinel

**pulse-sentinel** is a unified, state-aware daemon that monitors remote "heartbeats" via IMAP and manages a deterministic **3/6/9 minute escalation protocol**. 

By combining the **Producer** (network checker) and the **Consumer** (alert manager) into a single loop, it eliminates synchronization drift and provides a single source of truth for service health.

## 📦 Quick Start (Installation)

### 1. Environment Setup
It is highly recommended to run this in a virtual environment to avoid conflicts with system-wide Python packages.

```
# Navigate to your project folder
cd /home/user/pulse-sentinel

# Create the virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install imap-tools
```

### 2. Configuration

Open monitor.py in Vim and update the ACCOUNTS list with your IMAP credentials and the PULSE_DIR path.
⚙️ Service Deployment (Systemd)

To ensure the sentinel runs 24/7 and survives system reboots, deploy it as a system service.

Create the service file:
sudo vim /etc/systemd/system/pulse-sentinel.service

Paste the following configuration:
(Ensure the paths match your actual venv location)

```
[Unit]
Description=Pulse Sentinel Unified Daemon
After=network.target

[Service]
User=user
WorkingDirectory=/home/user/pulse-sentinel
ExecStart=/home/user/pulse-sentinel/venv/bin/python3 monitor.py
Restart=always
StandardOutput=append:/home/user/pulse-sentinel/monitor.log
StandardError=append:/home/user/pulse-sentinel/monitor.log

[Install]
WantedBy=multi-user.target
```
### 3. Enable and Start

```
sudo systemctl daemon-reload
sudo systemctl enable pulse-sentinel
sudo systemctl start pulse-sentinel
```

### 🧠 How the Logic Works (The 3/6/9 Protocol)

If you are new to the Sentinel, the logic is broken down into two simple stages that repeat every 45 seconds.

Stage 1: The Pulse Check
The script connects to your "monitoring" email accounts (can be 1 or 15, different providers too), and looks for new "Pulse" emails (emails that haven't been "open" in the IMAP protocol sense). If it finds one, it updates a local "Heartbeat" file with the current system time. This is the Proof of Life.

Stage 2: The Escalation Ladder

The Sentinel calculates the "Age" of that "Heartbeat" file (Current Time minus Last Heartbeat). If the age exceeds your threshold (10 minutes by default), it begins climbing the ladder:

| Time Since Failure | State | Severity | Intent |
| :--- | :--- | :--- | :--- |
| **0 - 3 Minutes** | `OK` | Normal | Silence. We assume transient network latency. |
| **3 - 6 Minutes** | `YELLOW` | Warning | The first alert. A "heads up" of potential issues. |
| **6 - 9 Minutes** | `RED` | Error | High priority. Significant downtime detected. |
| **9+ Minutes** | `CRITICAL` | Critical | Maximum alert level. Requires immediate intervention. |

Stage Reset: The Problem it's fixed

When a new mail arrives to some of the configured IMAP mail accounts, monitor.py will update the last time of a mail from that specific mail account arriving; if the monitoring state corresponding to that account was `YELLOW` or `RED`, the monitoring state of that account will automatically switch back to `OK` again, repeating the system known as 'dead man's switch' cycle.

The "Anti-Spam" Rule: The Sentinel only logs when the state changes (e.g., when moving from Yellow to Red). It will not fill your logs with repetitive errors.

### 🪵 Log Management

  [IMAP] Tags: Show when the script is talking to the network.

  [Monitor] Tags: Show when the script is making decisions about alerts.

  Real-time Monitoring: Use tail -f monitor.log to watch the heartbeat age and recovery status.
