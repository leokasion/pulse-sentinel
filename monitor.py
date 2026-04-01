import os
import time
import logging
from imap_tools import MailBox, AND

# --- CONFIG ---
PULSE_DIR = "./pulses"
MAX_AGE_SECONDS = 600  # 10 minute threshold
CHECK_INTERVAL = 45    # How often the whole cycle runs

ACCOUNTS = [
    {
        "name": "gmail_pulse",
        "host": "imap.gmail.com",
        "user": "mailx@gmail.com",
        "pass": "abcdefgh",
        "sender": "alert@pipe.com"
    },
    {
        "name": "latvia_pulse",
        "host": "mail.inbox.lv",
        "user": "mailx@inbox.lv",
        "pass": "abcdegh",
        "sender": "alert@pipe.com"
    }
]

if not os.path.exists(PULSE_DIR):
    os.makedirs(PULSE_DIR)

# --- LOGGING SETUP ---
log_format = logging.Formatter('%(asctime)s [%(name)-8s] [%(levelname)s] %(message)s')
fh = logging.FileHandler('monitor.log')
fh.setFormatter(log_format)

logger = logging.getLogger("Monitor") # The Sentinel
logger.setLevel(logging.DEBUG)
logger.addHandler(fh)

loggerIMAP = logging.getLogger("IMAP") # The Tracker
loggerIMAP.setLevel(logging.INFO)
loggerIMAP.addHandler(fh)

# --- TRACKER FUNCTIONS ---

def touch_pulse_file(account_name):
    """Updates the content of a file with the current Unix timestamp."""
    filepath = os.path.join(PULSE_DIR, f"{account_name}.last")
    with open(filepath, 'w') as f:
        f.write(str(time.time()))
    loggerIMAP.info(f"Heartbeat updated for {account_name}")

def check_account(acc):
    """Connects, checks for unread pulse emails, and updates local pulse files."""
    try:
        with MailBox(acc['host']).login(acc['user'], acc['pass']) as mailbox:
            criteria = AND(from_=acc['sender'], seen=False)
            messages = list(mailbox.fetch(criteria))
            
            if messages:
                loggerIMAP.info(f"[{acc['name']}] Received {len(messages)} new pulse(s).")
                touch_pulse_file(acc['name'])
                for msg in messages:
                    mailbox.flag(msg.uid, '\\Seen', True)
            else:
                loggerIMAP.debug(f"[{acc['name']}] No new pulses found.")
                
    except Exception as e:
        loggerIMAP.error(f"[{acc['name']}] Connection/Auth error: {e}")

def perform_check():
    """Loops through all configured accounts to update pulses."""
    loggerIMAP.info("--- Starting IMAP Check Cycle ---")
    for account in ACCOUNTS:
        check_account(account)

# --- MONITOR FUNCTIONS ---

def check_pulses():
    """Scans the pulse directory and returns labels that are STALE."""
    stale_labels = []
    now = time.time()
    
    pulse_files = [f for f in os.listdir(PULSE_DIR) if f.endswith(".last")]
    if not pulse_files:
        logger.info("Monitoring active: No pulse files detected yet.")
        return []

    for filename in pulse_files:
        filepath = os.path.join(PULSE_DIR, filename)
        account_label = filename.replace(".last", "")
        try:
            with open(filepath, 'r') as f:
                content = f.read().strip()
                if not content: continue
                last_pulse_ts = float(content)
            
            age_seconds = now - last_pulse_ts
            if age_seconds > MAX_AGE_SECONDS:
                logger.debug(f"STALE Check: [{account_label}] Age: {int(age_seconds)}s")
                stale_labels.append(account_label)
            else:
                logger.info(f"STATUS OK: [{account_label}] active. Age: {int(age_seconds)}s")
        except Exception as e:
            logger.error(f"Failed to read pulse file {filename}: {e}")
    return stale_labels

# --- UNIFIED MAIN LOOP ---

if __name__ == "__main__":
    last_success_times = {} 
    account_states = {} 
    
    logger.info("Unified Monitor & Tracker Daemon started.")
    
    try:
        while True:
            # 1. Update pulses from the network
            perform_check()
            
            # 2. Analyze the local pulse files
            stale_accounts = check_pulses() 
            
            # Get current active labels from the directory
            all_known_labels = [f.replace(".last", "") for f in os.listdir(PULSE_DIR) if f.endswith(".last")]

            for label in all_known_labels:
                if label not in last_success_times:
                    last_success_times[label] = time.time()
                    account_states[label] = "OK"

                if label not in stale_accounts:
                    # RECOVERY
                    if account_states[label] != "OK":
                        logger.info(f"RECOVERY: Account [{label}] pulse detected.")
                        account_states[label] = "OK"
                    last_success_times[label] = time.time()
                else:
                    # ESCALATION
                    elapsed_minutes = (time.time() - last_success_times[label]) / 60
                    
                    if elapsed_minutes >= 9:
                        target = "CRITICAL"
                    elif elapsed_minutes >= 6:
                        target = "RED"
                    elif elapsed_minutes >= 3:
                        target = "YELLOW"
                    else:
                        target = "OK"

                    if target != account_states[label]:
                        if target == "CRITICAL":
                            logger.critical(f"Account [{label}] 9m silence reached.")
                        elif target == "RED":
                            logger.error(f"Account [{label}] 6m silence reached.")
                        elif target == "YELLOW":
                            logger.warning(f"Account [{label}] 3m silence reached.")
                        account_states[label] = target

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logger.info("Manual stop. Cleaning up and exiting.")
