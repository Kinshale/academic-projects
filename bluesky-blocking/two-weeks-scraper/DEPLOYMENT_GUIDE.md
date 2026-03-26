# Deploying Bluesky Scraper to Digital Ocean

## Complete Deployment Guide for Linux Mint

This guide will walk you through deploying your 14-day scraper to a Digital Ocean droplet using SSH keys and tmux.

---

## Part 1: Local Setup (Your Linux Mint Machine)

### Step 1: Generate SSH Key (if you don't have one)

```bash
# Check if you already have SSH keys
ls -la ~/.ssh/id_*.pub

# If no keys exist, generate a new one
ssh-keygen -t ed25519 -C "your_email@example.com"
# Press Enter to accept default location (~/.ssh/id_ed25519)
# Optional: Enter a passphrase for extra security

# Display your public key (you'll need this for Digital Ocean)
cat ~/.ssh/id_ed25519.pub
```

**Copy the output** - you'll paste this into Digital Ocean.

---

## Part 2: Digital Ocean Setup

### Step 2: Create a Droplet

1. **Log in** to [Digital Ocean](https://cloud.digitalocean.com/)

2. **Create Droplet**:
   - Click **"Create"** → **"Droplets"**
   
3. **Choose Image**:
   - Select **Ubuntu 22.04 LTS** (recommended)
   
4. **Choose Plan**:
   - **Basic** plan
   - **Regular CPU** - $6/month (1 GB RAM, 25 GB SSD)
   - Or **$12/month** (2 GB RAM, 50 GB SSD) - recommended for 14-day scrape
   
5. **Choose Datacenter**:
   - Pick closest region to you (e.g., Frankfurt, London, New York)
   
6. **Authentication**:
   - Select **"SSH keys"**
   - Click **"New SSH Key"**
   - Paste your public key from Step 1
   - Give it a name (e.g., "Linux Mint Laptop")
   
7. **Finalize Details**:
   - Hostname: `bluesky-scraper` (or any name)
   - Enable backups: **No** (save money)
   - Click **"Create Droplet"**

8. **Wait ~60 seconds** for droplet to start

9. **Copy the IP address** shown (e.g., `164.90.123.456`)

---

## Part 3: Initial Connection & Server Setup

### Step 3: Connect to Your Droplet

```bash
# SSH into your droplet (replace with your IP)
ssh root@164.90.123.456

# Type 'yes' when asked about fingerprint
```

You should now be connected to your Digital Ocean server! 🎉

### Step 4: Update System & Install Dependencies

```bash
# Update package lists
apt update && apt upgrade -y

# Install Python 3.11, pip, tmux, and git
sudo apt install python3 python3-venv python3-pip tmux git htop vim -y

# Verify installations
python3.11 --version
tmux -V
```

### Step 5: Create Project Directory

```bash
# Create a directory for your scraper
mkdir -p /opt/bluesky-scraper
cd /opt/bluesky-scraper
```

---

## Part 4: Transfer Your Scraper Files

### Step 6: Copy Files from Your Local Machine

**Open a NEW terminal on your Linux Mint machine** (keep the SSH session open):

```bash
# Navigate to your project
cd /home/ale/Documents/uni/mp/two-weeks-scraper

# Copy files to droplet (replace IP address)
scp -r scraper.py config.json requirements.txt deploy.sh root@134.122.94.36:/opt/bluesky-scraper/

# Verify transfer
ssh root@164.90.123.456 "ls -lh /opt/bluesky-scraper"
```

---

## Part 5: Python Environment Setup

### Step 7: Create Virtual Environment & Install Packages

**Back in your SSH session on the droplet**:

```bash
cd /opt/bluesky-scraper

# Create virtual environment
python3.11 -m venv bluesky-venv

# Activate virtual environment
source bluesky-venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt

# Verify atproto installation
python -c "import atproto; print('atproto version:', atproto.__version__)"
```

---

## Part 6: Configuration for Production

### Step 8: Review & Adjust Configuration

```bash
# Check current config
cat config.json

# Edit if needed (optional)
nano config.json
```

**Important settings to verify**:
- `time_limit`: 1209600 (14 days in seconds) ✅
- `compress_old_files`: true ✅
- `max_disk_usage_percent`: 85 ✅
- `verbose`: false (reduce terminal spam) ✅

Press `Ctrl+X`, then `Y`, then `Enter` to save changes in nano.

---

## Part 7: Running with tmux

### Step 9: Start Scraper in tmux Session

```bash
# Create a new tmux session named "scraper"
tmux new-session -s scraper

# Inside tmux, activate virtualenv and run scraper
cd /opt/bluesky-scraper
source bluesky-venv/bin/activate
python scraper.py

# You should see: "Starting Bluesky firehose scraper..."
```

### Step 10: Detach from tmux (Keep it Running)

Press: **`Ctrl+B`** then **`D`** (detach)

Your scraper is now running in the background! 🎉

### Step 11: tmux Cheat Sheet

```bash
# Reattach to your scraper session
tmux attach -t scraper

# List all tmux sessions
tmux ls

# Kill the scraper session (when done)
tmux kill-session -t scraper

# Inside tmux, scroll up to see logs:
# Press Ctrl+B then [ (enter scroll mode)
# Use arrow keys or Page Up/Down
# Press 'q' to exit scroll mode
```

---

## Part 8: Monitoring & Maintenance

### Step 12: Check Scraper Status

```bash
# Reattach to see live output
tmux attach -t scraper

# Check log files
cd /opt/bluesky-scraper
tail -f scraper.log

# Check stats file
cat stats.json | python -m json.tool

# Monitor disk usage
df -h

# Monitor system resources
htop
```

### Step 13: Check Data Collection

```bash
# List collected data files
ls -lh /opt/bluesky-scraper/*.jsonl*

# Count records in today's file
wc -l $(date +%Y-%m-%d).jsonl

# Check file sizes
du -sh *.jsonl*

# View compression in action (after day 1)
ls -lh *.jsonl.gz
```

---

## Part 9: Automated Monitoring (Optional)

### Step 14: Create Monitoring Script

```bash
# Create a simple monitoring script
cat > /opt/bluesky-scraper/check_scraper.sh << 'EOF'
#!/bin/bash
echo "=== Scraper Status ==="
tmux has-session -t scraper 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Scraper is running"
else
    echo "❌ Scraper is NOT running"
fi

echo -e "\n=== Disk Usage ==="
df -h / | tail -1

echo -e "\n=== Data Files ==="
ls -lh /opt/bluesky-scraper/*.jsonl* 2>/dev/null | tail -5

echo -e "\n=== Latest Stats ==="
cat /opt/bluesky-scraper/stats.json 2>/dev/null | python3 -m json.tool

echo -e "\n=== Recent Errors ==="
tail -5 /opt/bluesky-scraper/scraper.log | grep -i error
EOF

chmod +x /opt/bluesky-scraper/check_scraper.sh

# Run it
./check_scraper.sh
```

---

## Part 10: After 14 Days - Retrieve Data

### Step 15: Download Data to Your Local Machine

**On your Linux Mint machine**:

```bash
# Create local directory for downloaded data
mkdir -p ~/bluesky_data_2025

# Download all data files (replace IP)
scp root@164.90.123.456:/opt/bluesky-scraper/*.jsonl* ~/bluesky_data_2025/
scp root@164.90.123.456:/opt/bluesky-scraper/stats.json ~/bluesky_data_2025/
scp root@164.90.123.456:/opt/bluesky-scraper/scraper.log ~/bluesky_data_2025/

# Check what you downloaded
ls -lh ~/bluesky_data_2025/
```

### Step 16: Cleanup & Destroy Droplet

```bash
# SSH into droplet
ssh root@164.90.123.456

# Stop scraper
tmux kill-session -t scraper

# Verify data is backed up locally, then:
# Log out and destroy droplet from Digital Ocean dashboard
# This stops billing!
```

---

## Troubleshooting

### Problem: Can't connect via SSH
```bash
# Test connection
ssh -v root@YOUR_IP

# Check if key is loaded
ssh-add -l

# Add key manually if needed
ssh-add ~/.ssh/id_ed25519
```

### Problem: Scraper stops unexpectedly
```bash
# Check logs
tail -100 /opt/bluesky-scraper/scraper.log

# Check if process is running
ps aux | grep scraper.py

# Restart in tmux
tmux attach -t scraper
# Ctrl+C to stop, then restart:
source venv/bin/activate
python scraper.py
```

### Problem: Disk full
```bash
# Check disk usage
df -h

# Manually compress old files
cd /opt/bluesky-scraper
gzip -9 *.jsonl

# Delete oldest compressed files if needed
rm 2025-12-*.jsonl.gz
```

### Problem: Out of memory
```bash
# Check memory usage
free -h

# If needed, upgrade droplet:
# Digital Ocean Dashboard → Droplet → Resize
# Choose next tier ($12/month for 2 GB RAM)
```

---

## Cost Estimate

**14-day scrape**:
- Droplet: $12/month (2 GB RAM) = ~$6 for 14 days
- Bandwidth: Free (1 TB included)
- Storage: ~500 MB (well within 50 GB SSD)

**Total cost**: ~$6 (you have $200 in credits!) ✅

---

## Quick Reference Commands

```bash
# SSH into droplet
ssh root@YOUR_IP

# Attach to scraper session
tmux attach -t scraper

# Detach from tmux
Ctrl+B, then D

# Check scraper status
./check_scraper.sh

# View live logs
tail -f scraper.log

# Download data when done
scp root@YOUR_IP:/opt/bluesky-scraper/*.jsonl* ~/bluesky_data_2025/
```

---

## Security Best Practices

1. **Never share your private key** (`~/.ssh/id_ed25519`)
2. **Only share public key** (`~/.ssh/id_ed25519.pub`)
3. **Use strong passphrase** for SSH key
4. **Disable password authentication** (optional):
   ```bash
   nano /etc/ssh/sshd_config
   # Set: PasswordAuthentication no
   systemctl restart sshd
   ```
5. **Enable firewall** (optional):
   ```bash
   ufw allow ssh
   ufw enable
   ```

---

## Next Steps

1. ✅ Generate SSH key (Part 1)
2. ✅ Create Digital Ocean droplet (Part 2)
3. ✅ Connect and setup server (Part 3)
4. ✅ Transfer files (Part 4)
5. ✅ Install dependencies (Part 5)
6. ✅ Configure scraper (Part 6)
7. ✅ Start in tmux (Part 7)
8. 🔄 Monitor for 14 days (Part 8)
9. ⏳ Download data (Part 10)
10. ⏳ Destroy droplet (Part 10)

**Good luck with your deployment! 🚀**
