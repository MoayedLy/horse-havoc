#!/usr/bin/env bash
# ==============================================================================
# HORSE HAVOC - Linux Crontab Setup (Tripoli Time: 12:00 AM & 12:00 PM EET / UTC+2)
# ==============================================================================
# Automatically registers:
# 1. Twice-Daily Publishing (12:00 AM & 12:00 PM Tripoli EET = 22:00 & 10:00 UTC)
# 2. Hourly Video Retention Cleanup (Minute 15 of every hour, purges .mp4 > 24 hours old)
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"

if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3 || command -v python)"
fi

LOG_PATH="$PROJECT_DIR/logs/cron.log"
mkdir -p "$PROJECT_DIR/logs"

# Timezone Conversion for Tripoli, Libya (EET, UTC+2) on standard UTC VPS:
# - Tripoli 12:00 AM Midnight (00:00 EET) = 22:00 (10:00 PM) UTC
# - Tripoli 12:00 PM Noon     (12:00 EET) = 10:00 (10:00 AM) UTC
# Publishing Hours in UTC: 10,22

# 1. Twice-Daily Publishing Job
CRON_PUBLISH="0 10,22 * * * cd $PROJECT_DIR && SDL_VIDEODRIVER=\"dummy\" $PYTHON_BIN $PROJECT_DIR/auto_run.py --public --all >> $LOG_PATH 2>&1"

# 2. Hourly Video Retention Cleanup Job (prunes any .mp4 older than 24 hours / 1440 minutes)
CRON_CLEANUP="15 * * * * find $PROJECT_DIR -maxdepth 3 -type f -name \"*.mp4\" -mmin +1440 -delete"

echo "======================================================================"
echo " [HORSE HAVOC] CRONTAB CONFIGURATION (TRIPOLI EET / UTC+2)"
echo "======================================================================"
echo " * Project Directory : $PROJECT_DIR"
echo " * Python Executable : $PYTHON_BIN"
echo " * Tripoli Schedule  : 12:00 AM (Midnight) & 12:00 PM (Noon) EET"
echo " * Server Clock (UTC): 22:00 (10:00 PM) & 10:00 (10:00 AM) UTC"
echo " * Publishing Cron   : $CRON_PUBLISH"
echo " * Cleanup Cron      : $CRON_CLEANUP"
echo " * Log Destination   : $LOG_PATH"
echo "----------------------------------------------------------------------"

# Remove any existing duplicate auto_run or cleanup jobs and append the new schedule
(crontab -l 2>/dev/null | grep -v "auto_run.py" | grep -v "run_pipeline.py" | grep -v "mmin +1440" || true; echo "$CRON_PUBLISH"; echo "$CRON_CLEANUP") | crontab -

echo "SUCCESS: Crontab jobs installed cleanly!"
echo ""
echo "Active Crontab:"
crontab -l
echo "======================================================================"
