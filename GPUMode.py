#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
gi.require_version('Notify', '0.7')
gi.require_version('UPowerGlib', '1.0')
from gi.repository import Gtk, AppIndicator3, Notify, GLib, UPowerGlib
import subprocess
import threading
import os
import sys
import fcntl
import logging
from pathlib import Path

VERSION = "1.01"
LOCK_FILE = "/tmp/gpumode.lock"
LOG_DIR = Path.home() / ".local/share/gpumode"
LOG_FILE = LOG_DIR / "gpumode.log"
SETTINGS_FILE = LOG_DIR / "settings.conf"

class GPUIndicator:
    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.info("GPUMode started")
        
        if not self.check_envycontrol():
            self.show_error_and_exit("envycontrol not found", 
                                    "Please install envycontrol:\ninstall envycontrol\nfrom https://github.com/bayasdev/envycontrol, releases/assets")
            return
        
        Notify.init("GPUMode")
        
        self.indicator = AppIndicator3.Indicator.new(
            "gpumode",
            "video-display",
            AppIndicator3.IndicatorCategory.HARDWARE
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        
        self.switching = False
        self.current_mode = self.get_current_mode()
        self.update_icon()
        
        self.power_prompts_enabled = self.load_power_prompts_setting()
        
        self.indicator.set_menu(self.build_menu())
        
        self.upower_client = UPowerGlib.Client.new()
        self.upower_client.connect('notify::on-battery', self.on_power_changed)
        self.last_power_state = self.upower_client.get_on_battery()
        
        logging.info(f"Initial GPU mode: {self.current_mode}")
        logging.info(f"Initial power state: {'battery' if self.last_power_state else 'AC'}")
        logging.info(f"Power prompts enabled: {self.power_prompts_enabled}")
        
        GLib.timeout_add(2000, self.check_startup_mismatch)

    def check_startup_mismatch(self):
        """Check if GPU mode mismatches power state at startup"""
        if not self.power_prompts_enabled:
            logging.info("Power prompts disabled, skipping startup check")
            return False
        
        on_battery = self.upower_client.get_on_battery()
        
        if on_battery and self.current_mode in ['nvidia', 'hybrid']:
            logging.info("Startup mismatch: On battery but using NVIDIA/Hybrid")
            self.prompt_switch_on_battery()
        elif not on_battery and self.current_mode == 'integrated':
            logging.info("Startup mismatch: On AC but using Integrated")
            self.prompt_switch_on_ac()
        else:
            logging.info("No startup mismatch detected")
        
        return False

    def load_power_prompts_setting(self):
        """Load power prompts enabled setting from file"""
        if not SETTINGS_FILE.exists():
            return True
        
        try:
            content = SETTINGS_FILE.read_text().strip()
            return content == "enabled"
        except:
            return True

    def save_power_prompts_setting(self, enabled):
        """Save power prompts enabled setting to file"""
        try:
            SETTINGS_FILE.write_text("enabled" if enabled else "disabled")
            logging.info(f"Power prompts {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            logging.error(f"Failed to save power prompts setting: {e}")

    def toggle_power_prompts(self, widget):
        """Toggle power change prompts on/off"""
        self.power_prompts_enabled = widget.get_active()
        self.save_power_prompts_setting(self.power_prompts_enabled)
        
        notification = Notify.Notification.new(
            "Power Prompts " + ("Enabled" if self.power_prompts_enabled else "Disabled"),
            "You will " + ("now" if self.power_prompts_enabled else "no longer") + " be prompted to switch GPU when AC power changes.",
            "dialog-information"
        )
        notification.show()

    def on_power_changed(self, client, pspec):
        """Handle AC/battery power changes"""
        on_battery = client.get_on_battery()
        
        if on_battery == self.last_power_state:
            return
        
        logging.info(f"Power state changed: {'AC->Battery' if on_battery else 'Battery->AC'}")
        self.last_power_state = on_battery
        
        if not self.power_prompts_enabled:
            logging.info("Power prompts disabled, skipping")
            return
        
        if on_battery:
            self.prompt_switch_on_battery()
        else:
            self.prompt_switch_on_ac()

    def prompt_switch_on_battery(self):
        """Prompt to switch to integrated when on battery"""
        if self.current_mode == "integrated":
            logging.info("Already on integrated, skipping battery prompt")
            return
        
        logging.info("Prompting switch to integrated on battery")
        
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Switch to Integrated GPU?"
        )
        dialog.format_secondary_text(
            "You're now on battery power.\n\n"
            "Would you like to switch to Integrated GPU mode for better battery life?\n\n"
            "This will require a reboot."
        )
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            logging.info("User accepted battery switch prompt")
            self.switch_and_reboot('integrated')
        else:
            logging.info("User declined battery switch prompt")

    def prompt_switch_on_ac(self):
        """Prompt to switch to Hybrid when on AC"""
        if self.current_mode == "hybrid":
            logging.info("Already on Hybrid, skipping AC prompt")
            return
        
        logging.info("Prompting switch to Hybrid on AC")
        
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Switch to Hybrid Mode?"
        )
        dialog.format_secondary_text(
            "You're now on AC power.\n\n"
            "Would you like to switch to Hybrid mode for balanced performance?\n\n"
            "This will require a reboot."
        )
        
        response = dialog.run()
        dialog.destroy()
        
        if response == Gtk.ResponseType.YES:
            logging.info("User accepted AC switch prompt")
            self.switch_and_reboot('hybrid')
        else:
            logging.info("User declined AC switch prompt")

    def switch_and_reboot(self, mode):
        """Switch GPU mode and reboot"""
        self.switching = True
        self.update_icon()
        self.indicator.set_menu(self.build_menu())
        
        notification = Notify.Notification.new(
            "GPUMode",
            f"Switching to {mode} mode and rebooting...",
            "emblem-synchronizing"
        )
        notification.show()
        
        def switch_reboot_thread():
            try:
                cmd = ['pkexec', 'envycontrol', '-s', mode]
                if mode == 'hybrid':
                    cmd.extend(['--rtd3', '2'])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                
                if result.returncode == 0:
                    logging.info(f"Switched to {mode}, initiating reboot")
                    subprocess.run(['systemctl', 'reboot'], timeout=5)
                else:
                    logging.error(f"Failed to switch: {result.stderr}")
                    GLib.idle_add(self.switch_complete, mode, False, result.stderr)
                    
            except Exception as e:
                logging.error(f"Switch and reboot error: {e}")
                GLib.idle_add(self.switch_complete, mode, False, str(e))
        
        thread = threading.Thread(target=switch_reboot_thread)
        thread.daemon = True
        thread.start()

    def check_envycontrol(self):
        """Check if envycontrol is installed"""
        try:
            result = subprocess.run(['which', 'envycontrol'], 
                                  capture_output=True, timeout=2)
            return result.returncode == 0
        except:
            return False

    def show_error_and_exit(self, title, message):
        """Show error dialog and exit"""
        logging.error(f"{title}: {message}")
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
        sys.exit(1)

    def get_current_mode(self):
        """Query current GPU mode - checks glxinfo first to detect BIOS-set NVIDIA mode"""
        try:
            # Check glxinfo OpenGL renderer line specifically
            glx_result = subprocess.run(['sh', '-c', 'glxinfo | grep "OpenGL renderer"'], 
                                      capture_output=True, text=True, timeout=2)
            if glx_result.returncode == 0:
                renderer = glx_result.stdout.strip()
                logging.info(f"glxinfo renderer string: {renderer}")
                
                # Check the actual OpenGL renderer string
                if 'NVIDIA' in renderer and 'AMD' not in renderer:
                    logging.info("Detected NVIDIA-only mode via glxinfo (BIOS-set)")
                    return "nvidia"
                elif 'AMD' in renderer and 'NVIDIA' not in renderer:
                    # AMD only - check envycontrol to confirm integrated mode
                    try:
                        result = subprocess.run(['envycontrol', '--query'], 
                                              capture_output=True, text=True, timeout=2)
                        if result.returncode == 0:
                            mode = result.stdout.strip().lower()
                            logging.info(f"Queried GPU mode from envycontrol: {mode}")
                            return mode
                    except:
                        pass
                    logging.info("Detected integrated mode via glxinfo")
                    return "integrated"
                elif 'AMD' in renderer and 'NVIDIA' in renderer:
                    # Both GPUs in renderer string - likely hybrid
                    logging.info("Detected hybrid mode via glxinfo")
                    return "hybrid"
        except Exception as e:
            logging.error(f"Failed to query GPU mode with glxinfo: {e}")
            
            # Final fallback to envycontrol only
            try:
                result = subprocess.run(['envycontrol', '--query'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    mode = result.stdout.strip().lower()
                    logging.info(f"Queried GPU mode from envycontrol (fallback): {mode}")
                    return mode
            except:
                pass
        
        return "unknown"

    def update_icon(self):
        """Update tray icon based on current state"""
        if self.switching:
            self.indicator.set_icon("emblem-synchronizing-symbolic")
        elif self.current_mode == "integrated":
            self.indicator.set_icon("drive-harddisk-solidstate-symbolic")
        elif self.current_mode == "nvidia":
            self.indicator.set_icon("video-display-symbolic")
        elif self.current_mode == "hybrid":
            self.indicator.set_icon("video-single-display-symbolic")
        else:
            self.indicator.set_icon("dialog-question-symbolic")

    def refresh_mode(self):
        """Refresh current GPU mode"""
        if not self.switching:
            old_mode = self.current_mode
            self.current_mode = self.get_current_mode()
            if old_mode != self.current_mode:
                logging.info(f"GPU mode changed: {old_mode} -> {self.current_mode}")
                self.update_icon()
                self.indicator.set_menu(self.build_menu())

    def build_menu(self):
        """Build the indicator menu"""
        menu = Gtk.Menu()
        
        menu.connect('show', lambda _: self.refresh_mode())
        
        if self.switching:
            status = Gtk.MenuItem(label='━━━ SWITCHING... ━━━')
        else:
            status = Gtk.MenuItem(label=f'━━━ Current: {self.current_mode.upper()} ━━━')
        status.set_sensitive(False)
        menu.append(status)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        # If in NVIDIA mode, show blocking message
        if self.current_mode == 'nvidia':
            blocked_warning = Gtk.MenuItem(label='⚠ NVIDIA Mode Active')
            blocked_warning.set_sensitive(False)
            menu.append(blocked_warning)
            
            blocked_msg = Gtk.MenuItem(label='Set BIOS to Hybrid (F2) to enable switching')
            blocked_msg.set_sensitive(False)
            menu.append(blocked_msg)
            
            menu.append(Gtk.SeparatorMenuItem())
            
            # Show all modes as disabled
            integrated = Gtk.MenuItem(label='⚪ Integrated GPU')
            integrated.set_sensitive(False)
            menu.append(integrated)
            
            hybrid = Gtk.MenuItem(label='⚪ Hybrid Mode')
            hybrid.set_sensitive(False)
            menu.append(hybrid)
            
            nvidia = Gtk.MenuItem(label='● NVIDIA GPU (ACTIVE)')
            nvidia.set_sensitive(False)
            menu.append(nvidia)
        else:
            # Normal mode - Warning about NVIDIA mode
            warning = Gtk.MenuItem(label='⚠ NVIDIA mode: Use BIOS (F2)')
            warning.set_sensitive(False)
            menu.append(warning)
            
            menu.append(Gtk.SeparatorMenuItem())
            
            # Integrated - switchable
            integrated = Gtk.MenuItem(
                label='⚪ Integrated GPU' if self.current_mode != 'integrated' 
                else '● Integrated GPU (ACTIVE)'
            )
            integrated.connect('activate', self.switch_integrated)
            if self.current_mode == 'integrated' or self.switching:
                integrated.set_sensitive(False)
            menu.append(integrated)
            
            # Hybrid - switchable
            hybrid = Gtk.MenuItem(
                label='⚪ Hybrid Mode' if self.current_mode != 'hybrid' 
                else '● Hybrid Mode (ACTIVE)'
            )
            hybrid.connect('activate', self.switch_hybrid)
            if self.current_mode == 'hybrid' or self.switching:
                hybrid.set_sensitive(False)
            menu.append(hybrid)
            
            # NVIDIA - show status only, not switchable
            nvidia = Gtk.MenuItem(label='⚪ NVIDIA GPU')
            nvidia.set_sensitive(False)
            menu.append(nvidia)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        power_prompts_item = Gtk.CheckMenuItem(label='Prompt on Power Change')
        power_prompts_item.set_active(self.power_prompts_enabled)
        power_prompts_item.connect('activate', self.toggle_power_prompts)
        if self.switching or self.current_mode == 'nvidia':
            power_prompts_item.set_sensitive(False)
        menu.append(power_prompts_item)
        
        about_item = Gtk.MenuItem(label='About')
        about_item.connect('activate', self.show_about)
        menu.append(about_item)
        
        menu.append(Gtk.SeparatorMenuItem())
        
        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', Gtk.main_quit)
        if self.switching:
            quit_item.set_sensitive(False)
        menu.append(quit_item)
        
        menu.show_all()
        return menu

    def switch_integrated(self, _):
        self.switch_gpu('integrated')

    def switch_hybrid(self, _):
        self.switch_gpu('hybrid')

    def switch_gpu(self, mode):
        """Switch GPU mode"""
        if self.switching:
            return
        
        logging.info(f"Switching to {mode} mode")
        self.switching = True
        self.update_icon()
        self.indicator.set_menu(self.build_menu())
        
        notification = Notify.Notification.new(
            "GPUMode",
            f"Switching to {mode} mode...",
            "emblem-synchronizing"
        )
        notification.show()
        
        def switch_thread():
            try:
                cmd = ['pkexec', 'envycontrol', '-s', mode]
                if mode == 'hybrid':
                    cmd.extend(['--rtd3', '2'])
                
                result = subprocess.run(
                    cmd,
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                
                if result.returncode == 126 or result.returncode == 127:
                    GLib.idle_add(self.switch_cancelled)
                elif result.returncode == 0:
                    GLib.idle_add(self.switch_complete, mode, True, None)
                else:
                    GLib.idle_add(self.switch_complete, mode, False, result.stderr)
                    
            except subprocess.TimeoutExpired:
                logging.error("Switch command timed out")
                GLib.idle_add(self.switch_complete, mode, False, "Command timed out")
            except Exception as e:
                logging.error(f"Switch error: {e}")
                GLib.idle_add(self.switch_complete, mode, False, str(e))
        
        thread = threading.Thread(target=switch_thread)
        thread.daemon = True
        thread.start()

    def switch_cancelled(self):
        """Handle user cancelling pkexec password prompt"""
        logging.info("User cancelled authentication")
        self.switching = False
        self.update_icon()
        self.indicator.set_menu(self.build_menu())
        
        notification = Notify.Notification.new(
            "Switch Cancelled",
            "Authentication was cancelled. GPU mode unchanged.",
            "dialog-information"
        )
        notification.show()
        return False

    def switch_complete(self, mode, success, error_msg):
        """Handle switch completion"""
        self.switching = False
        
        if success:
            logging.info(f"Successfully switched to {mode}")
            self.current_mode = mode
            self.update_icon()
            self.indicator.set_menu(self.build_menu())
            
            notification = Notify.Notification.new(
                "✓ GPU Switched Successfully!",
                f"Switched to {mode.upper()} mode.\n\n⚠️  REBOOT NOW for changes to take effect!",
                "dialog-warning"
            )
            notification.set_urgency(Notify.Urgency.CRITICAL)
            notification.set_timeout(10000)
            notification.show()
        else:
            logging.error(f"Failed to switch to {mode}: {error_msg}")
            self.update_icon()
            self.indicator.set_menu(self.build_menu())
            
            notification = Notify.Notification.new(
                "✗ GPU Switch Failed",
                f"Error: {error_msg if error_msg else 'Command failed'}",
                "dialog-error"
            )
            notification.show()
        
        return False

    def show_about(self, _):
        """Show about dialog"""
        dialog = Gtk.AboutDialog()
        dialog.set_program_name("GPUMode")
        dialog.set_version(VERSION)
        dialog.set_comments("Automatic GPU mode switching for laptops with NVIDIA graphics.\n\nNOTE: NVIDIA-only mode must be set in BIOS (F2).")
        dialog.set_website("https://github.com/FrameworkComputer/GPUMode")
        dialog.set_website_label("GPUMode on GitHub")
        dialog.set_logo_icon_name("video-display")
        dialog.run()
        dialog.destroy()

def single_instance():
    """Ensure only one instance is running"""
    try:
        lock_file = open(LOCK_FILE, 'w')
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        return False

if __name__ == "__main__":
    if not single_instance():
        dialog = Gtk.MessageDialog(
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text="GPUMode is already running"
        )
        dialog.format_secondary_text("Check your system tray for the GPUMode icon.")
        dialog.run()
        dialog.destroy()
        sys.exit(0)
    
    GPUIndicator()
    Gtk.main()
