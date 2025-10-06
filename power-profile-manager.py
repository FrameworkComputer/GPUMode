#!/usr/bin/env python3
import subprocess
import logging
import sys
from pathlib import Path

LOG_DIR = Path("/var/log/power-profile-manager")
LOG_FILE = LOG_DIR / "power-profile-manager.log"

class PowerProfileManager:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info("Power Profile Manager started")
        
        self.power_manager = self.detect_power_manager()
        if self.power_manager is None:
            logging.error("No power manager detected, exiting")
            sys.exit(1)
        
        logging.info(f"Using power manager: {self.power_manager}")
    
    def detect_power_manager(self):
        """Detect which power profile manager is available"""
        try:
            result = subprocess.run(['systemctl', 'is-active', 'power-profiles-daemon'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip() == "active":
                return "power-profiles-daemon"
        except:
            pass
        
        try:
            result = subprocess.run(['systemctl', 'is-active', 'tuned'],
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0 and result.stdout.strip() == "active":
                return "tuned"
        except:
            pass
        
        return None
    
    def is_on_ac_power(self):
        """Check if system is on AC power"""
        try:
            power_supply_path = Path("/sys/class/power_supply")
            for adapter in power_supply_path.glob("AC*"):
                online_file = adapter / "online"
                if online_file.exists():
                    return online_file.read_text().strip() == "1"
            
            for adapter in power_supply_path.glob("A*"):
                if adapter.name.startswith("AC") or adapter.name.startswith("ADP"):
                    online_file = adapter / "online"
                    if online_file.exists():
                        return online_file.read_text().strip() == "1"
            
            return False
        except Exception as e:
            logging.error(f"Error checking AC power status: {e}")
            return False
    
    def set_power_profile_ppd(self, profile):
        """Set power profile using power-profiles-daemon D-Bus"""
        try:
            import dbus
            bus = dbus.SystemBus()
            ppd = bus.get_object('net.hadess.PowerProfiles', '/net/hadess/PowerProfiles')
            ppd_interface = dbus.Interface(ppd, 'org.freedesktop.DBus.Properties')
            ppd_interface.Set('net.hadess.PowerProfiles', 'ActiveProfile', profile)
            logging.info(f"Set PPD profile to {profile}")
            return True
        except ImportError:
            logging.error("python3-dbus not installed")
            return False
        except Exception as e:
            logging.error(f"Failed to set PPD profile: {e}")
            return False
    
    def set_power_profile_tuned(self, profile):
        """Set tuned profile"""
        try:
            result = subprocess.run(['tuned-adm', 'profile', profile],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logging.info(f"Set tuned profile to {profile}")
                return True
            else:
                logging.error(f"Failed to set tuned profile: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Error setting tuned profile: {e}")
            return False
    
    def set_profile_for_current_state(self):
        """Set appropriate power profile based on current AC status"""
        on_ac = self.is_on_ac_power()
        power_state = "AC" if on_ac else "Battery"
        logging.info(f"Current power state: {power_state}")
        
        if self.power_manager == "power-profiles-daemon":
            profile = "performance" if on_ac else "power-saver"
            return self.set_power_profile_ppd(profile)
        
        elif self.power_manager == "tuned":
            profile = "throughput-performance" if on_ac else "powersave"
            return self.set_power_profile_tuned(profile)
        
        return False

if __name__ == "__main__":
    manager = PowerProfileManager()
    manager.set_profile_for_current_state()
