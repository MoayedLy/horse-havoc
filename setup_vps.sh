#!/usr/bin/env bash
# ==============================================================================
# HORSE HAVOC - Ubuntu Linux VPS One-Click 24/7 Deployment Engine
# ==============================================================================
# Sets up complete autonomous production environment on Ubuntu 22.04 / 24.04 LTS:
# 1. System packages (Python 3, pip, venv, ffmpeg, Xvfb, Mesa GL, SDL2, fonts, cron)
# 2. Isolated Python Virtual Environment (venv) with all requirements.txt libraries
# 3. Assets & credentials verification (.env, token.json, tiktok_token.json, instagram_token.json)
# 4. Twice-Daily Linux Crontab (00:00 Midnight & 12:00 Noon Server Time)
# 5. Immediate headless smoke test verification under Xvfb
# ==============================================================================

set -euo pipefail

# Visual styling
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}========================================================================${NC}"
echo -e "${CYAN} [HORSE HAVOC] UBUNTU VPS ONE-CLICK 24/7 DEPLOYMENT ENGINE             ${NC}"
echo -e "${CYAN}========================================================================${NC}"

# Detect execution directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${GREEN}* Project Directory :${NC} $PROJECT_DIR"
echo -e "${GREEN}* User Account      :${NC} $(whoami)"
echo -e "${GREEN}* Target Schedule   :${NC} Twice-Daily: 12:00 AM & 12:00 PM Tripoli Time (10:00 & 22:00 UTC)"
echo -e "${CYAN}------------------------------------------------------------------------${NC}"

# Sudo wrapper (supports both root, sudoers, and non-root unprivileged shared accounts)
CAN_SUDO=0
SUDO=""
if [ "$(id -u)" -eq 0 ]; then
    CAN_SUDO=1
    SUDO=""
elif command -v sudo >/dev/null 2>&1; then
    if sudo -n true 2>/dev/null || sudo -v 2>/dev/null; then
        CAN_SUDO=1
        SUDO="sudo"
    else
        echo -e "${YELLOW}[NOTICE] Non-root user without passwordless sudo. Skipping apt package installation.${NC}"
        echo -e "${YELLOW}         Proceeding with local virtualenv (venv) and pip dependency setup.${NC}"
    fi
else
    echo -e "${YELLOW}[NOTICE] Sudo not found. Proceeding with user-level virtualenv (venv) installation.${NC}"
fi

# ------------------------------------------------------------------------------
# STEP 1: Install System Dependencies (If root or sudo available)
# ------------------------------------------------------------------------------
if [ "$CAN_SUDO" -eq 1 ]; then
    echo -e "\n${YELLOW}[STEP 1/5] Updating apt repositories and installing system packages...${NC}"
    $SUDO apt-get update -y || true

    PRIMARY_PACKAGES=(
        python3
        python3-pip
        python3-venv
        python3-dev
        ffmpeg
        xvfb
        libsdl2-dev
        libsdl2-image-dev
        libsdl2-mixer-dev
        libsdl2-ttf-dev
        libasound2
        fonts-dejavu-core
        fonts-freefont-ttf
        fonts-liberation
        curl
        cron
    )

    if $SUDO apt-get install -y "${PRIMARY_PACKAGES[@]}" libgl1 libglx-mesa0 libgl1-mesa-dri; then
        echo -e "${GREEN}[OK] Installed modern OpenGL & SDL2 packages.${NC}"
    else
        echo -e "${YELLOW}[!] Falling back to legacy libgl1-mesa-glx...${NC}"
        $SUDO apt-get install -y "${PRIMARY_PACKAGES[@]}" libgl1-mesa-glx || true
    fi
    echo -e "${GREEN}[OK] System packages verified!${NC}"
else
    echo -e "\n${YELLOW}[STEP 1/5] Skipping system package installation (Non-root user mode active).${NC}"
fi

# ------------------------------------------------------------------------------
# STEP 2: Configure Python Virtual Environment (venv) & Dependencies
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[STEP 2/5] Creating isolated Python virtual environment (venv)...${NC}"
VENV_DIR="$PROJECT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}[OK] Virtual environment created at: $VENV_DIR${NC}"
else
    echo -e "${GREEN}[*] Existing virtual environment found at: $VENV_DIR${NC}"
fi

VENV_PYTHON="$VENV_DIR/bin/python3"
VENV_PIP="$VENV_DIR/bin/pip"

echo -e "${YELLOW}[*] Upgrading pip...${NC}"
"$VENV_PIP" install --upgrade pip --no-cache-dir --quiet

echo -e "${YELLOW}[*] Installing minimal dependencies from requirements.txt (--no-cache-dir)...${NC}"
"$VENV_PIP" install --no-cache-dir -r "$PROJECT_DIR/requirements.txt"
"$VENV_PIP" cache purge 2>/dev/null || true
rm -rf ~/.cache/pip /root/.cache/pip /tmp/pip* 2>/dev/null || true

echo -e "${GREEN}[OK] Python dependencies installed successfully!${NC}"

# ------------------------------------------------------------------------------
# STEP 3: Assets, Credentials & Directory Permissions Verification
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[STEP 3/5] Verifying assets, directories, and credentials files...${NC}"

# Ensure output directories exist
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/output"
mkdir -p "$PROJECT_DIR/assets/celebrities"
mkdir -p "$PROJECT_DIR/assets/sounds/victory"

# Set executable permissions on scripts
chmod +x "$PROJECT_DIR/auto_run.py" 2>/dev/null || true
chmod +x "$PROJECT_DIR/run_pipeline.py" 2>/dev/null || true
chmod +x "$PROJECT_DIR/publisher.py" 2>/dev/null || true
chmod +x "$PROJECT_DIR/scheduler.py" 2>/dev/null || true
chmod +x "$PROJECT_DIR/refresh_instagram_token.py" 2>/dev/null || true
chmod +x "$PROJECT_DIR/setup_vps.sh" 2>/dev/null || true

# Verify credentials files and set secure permissions
CRED_FILES=(".env" "token.json" "tiktok_token.json" "instagram_token.json" "client_secrets.json")
for cfile in "${CRED_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$cfile" ]; then
        chmod 600 "$PROJECT_DIR/$cfile" 2>/dev/null || true
        echo -e " ${GREEN}* Found credential file :${NC} $cfile (Permissions locked: 600)"
    else
        echo -e " ${YELLOW}* Notice:${NC} $cfile not present in directory."
    fi
done

# Initialize victory sound pool if missing
if [ $(ls -1 "$PROJECT_DIR/assets/sounds/victory" 2>/dev/null | wc -l) -lt 5 ]; then
    echo -e "${YELLOW}[*] Synthesizing victory SFX pool...${NC}"
    "$VENV_PYTHON" "$PROJECT_DIR/create_victory_sounds.py"
fi

# Ensure avatars exist
if [ $(ls -1 "$PROJECT_DIR/assets/celebrities" 2>/dev/null | grep -E '\.(png|jpg)' | wc -l) -lt 5 ]; then
    echo -e "${YELLOW}[*] Downloading missing celebrity portraits...${NC}"
    "$VENV_PYTHON" "$PROJECT_DIR/download_avatars.py" 2>/dev/null || true
fi

# ------------------------------------------------------------------------------
# STEP 4: Configure Crontab (Tripoli EET UTC+2: 10:00 & 22:00 UTC) & 24h Cleanup
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[STEP 4/5] Configuring Twice-Daily Crontab (Tripoli EET UTC+2) & Hourly Cleanup...${NC}"

LOG_PATH="$PROJECT_DIR/logs/cron.log"
mkdir -p "$PROJECT_DIR/logs"

# 1. Twice-Daily Publishing Job:
# Tripoli Midnight (00:00 EET) = 22:00 UTC
# Tripoli Noon (12:00 EET)     = 10:00 UTC
CRON_PUBLISH="0 10,22 * * * cd $PROJECT_DIR && SDL_VIDEODRIVER=\"dummy\" $VENV_PYTHON $PROJECT_DIR/auto_run.py --public --all >> $LOG_PATH 2>&1"

# 2. Hourly Video Retention Cleanup Job:
# Scans for and prunes any .mp4 file older than 24h (1440 minutes) to strictly respect disk quotas
CRON_CLEANUP="15 * * * * find $PROJECT_DIR -maxdepth 3 -type f -name \"*.mp4\" -mmin +1440 -delete"

# Add both cron jobs cleanly without duplicates
(crontab -l 2>/dev/null | grep -v "auto_run.py" | grep -v "run_pipeline.py" | grep -v "mmin +1440" || true; echo "$CRON_PUBLISH"; echo "$CRON_CLEANUP") | crontab -

# Ensure cron service is enabled and running if root/sudo available
if [ "$CAN_SUDO" -eq 1 ]; then
    $SUDO systemctl enable cron 2>/dev/null || $SUDO systemctl enable crond 2>/dev/null || true
    $SUDO systemctl start cron 2>/dev/null || $SUDO systemctl start crond 2>/dev/null || true
fi

echo -e "${GREEN}[OK] Crontab jobs registered successfully!${NC}"
echo -e "     Publish Cron    : ${CYAN}$CRON_PUBLISH${NC}"
echo -e "     Cleanup Cron    : ${CYAN}$CRON_CLEANUP${NC}"
echo -e "     Publish Times   : ${CYAN}12:00 AM & 12:00 PM Tripoli Time (10:00 & 22:00 UTC)${NC}"
echo -e "     Log File Path   : ${CYAN}$LOG_PATH${NC}"

# ------------------------------------------------------------------------------
# STEP 5: Verification Headless Smoke Test
# ------------------------------------------------------------------------------
echo -e "\n${YELLOW}[STEP 5/5] Running headless simulation verification test...${NC}"
echo -e "${CYAN}Executing: SDL_VIDEODRIVER=\"dummy\" $VENV_PYTHON auto_run.py --test --no-dispatch${NC}"

SDL_VIDEODRIVER="dummy" "$VENV_PYTHON" "$PROJECT_DIR/auto_run.py" --test --no-dispatch

echo -e "\n${GREEN}========================================================================${NC}"
echo -e "${GREEN} SUCCESS: HORSE HAVOC IS FULLY DEPLOYED & AUTONOMOUS ON THIS VPS!       ${NC}"
echo -e "${GREEN}========================================================================${NC}"
echo -e " * Twice-Daily Schedule: 12:00 AM & 12:00 PM Tripoli Time (10:00 & 22:00 UTC)"
echo -e " * Hourly Disk Cleanup : Minute 15 every hour (purges videos >24h old)"
echo -e " * Manual Test Match   : cd $PROJECT_DIR && ./venv/bin/python3 auto_run.py --test"
echo -e " * Full Live Match     : cd $PROJECT_DIR && ./venv/bin/python3 auto_run.py --public --all"
echo -e " * Standalone Daemon   : cd $PROJECT_DIR && ./venv/bin/python3 scheduler.py"
echo -e " * View Live Cron Logs : tail -f $PROJECT_DIR/logs/cron.log"
echo -e " * Match History Log   : cat $PROJECT_DIR/history.json"
echo -e "${GREEN}========================================================================${NC}"
