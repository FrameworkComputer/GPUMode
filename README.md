# GPUMode Ubuntu

System tray application for manual GPU mode switching on Ubuntu laptops with AMD integrated and NVIDIA discrete graphics.

---

## What It Does

- **Manual GPU Mode Switching**: Switch between Integrated and Hybrid modes via system tray
- **Power Change Prompts**: Optional prompts to switch GPU modes when AC power plugs/unplugs
- **Automatic Power Profiles**: Automatically switches system power profiles (performance/power-saver) based on AC/battery status
- **NVIDIA Mode Detection**: Detects when BIOS is set to NVIDIA-only mode and provides guidance

---

## Prerequisites

- AMD integrated GPU + NVIDIA discrete GPU
- NVIDIA proprietary drivers installed
- Ubuntu Linux
- [envycontrol](https://github.com/bayasdev/envycontrol) installed

---

## Graphics Modes

### Hybrid Mode (Recommended)
- Both GPUs active
- AMD handles desktop/light tasks
- NVIDIA handles games/heavy applications
- Moderate battery impact
- **Power consumption:** ~14.4W at idle (3 min idle, powersave mode, D0 power state, with **or** without envycontrol installed)
- **Switchable via this app**

### Integrated Mode (AMD-only)
- NVIDIA completely off
- Best battery life
- Cannot run GPU-intensive applications
- **Power consumption:** ~6.7W at idle (3 min idle, powersave mode)
- **Power savings:** ~7.7W less than Hybrid mode (53% reduction at idle)
- **Switchable via this app**

### NVIDIA Mode (Discrete-only)
- NVIDIA handles everything
- AMD disabled
- Maximum performance
- High battery drain
- **Must be set in BIOS (F2) - not switchable in app**

---

## Installation

1. Download latest .deb [from releases](https://github.com/FrameworkComputer/GPUMode/releases)
2. Install:

    sudo dpkg -i gpumode_*.deb

3. Reboot

The tray icon will auto-start on login.

---

## Usage

### Switching GPU Modes

1. Click GPUMode tray icon
2. Select mode (Integrated/Hybrid)
3. Authenticate when prompted
4. **Reboot** for changes to take effect

**Note:** If the system is in NVIDIA mode (set via BIOS), the app will detect this and disable switching. To regain switching functionality, reboot and set BIOS to Hybrid mode (F2 during boot).

### Power Change Prompts

Toggle "Prompt on Power Change" in the tray menu to enable/disable prompts when AC power changes.

### Checking Current Mode

Click tray icon to see current mode, or run:

    glxinfo | grep "OpenGL renderer"

or
    
    nvidia-smi

---

## Framework Laptop 16 AI 300 Series

GPU modes can be set in BIOS (F2 during boot):
- **Hybrid mode** (recommended): Enables app switching between Hybrid and Integrated
- **NVIDIA mode**: App will detect this and block switching until BIOS is set back to Hybrid
- **Integrated mode**: Can be set via BIOS or via this app

For best experience, set BIOS to Hybrid and use this app for switching.

---

## Troubleshooting

### envycontrol not found
Install envycontrol from https://github.com/bayasdev/envycontrol

### Mode didn't change after reboot
- Check BIOS graphics settings (may override in-OS)
- Verify with: nvidia-smi or glxinfo

### Authentication cancelled
Click the mode again and enter password when prompted.

### App shows "NVIDIA Mode Active" and blocks switching
Your BIOS is set to NVIDIA-only mode. To regain switching functionality:
1. Reboot and press F2 to enter BIOS
2. Navigate to graphics settings
3. Set mode to Hybrid
4. Save and exit
5. App will detect Hybrid mode and enable switching

---

## How GPU Mode Detection Works

The app uses glxinfo to detect the active GPU:
- **NVIDIA-only detected**: App shows NVIDIA mode is active and blocks switching (BIOS setting required)
- **AMD-only detected**: Checks envycontrol to confirm Integrated mode
- **Both GPUs detected**: Confirms Hybrid mode

This ensures accurate mode detection regardless of whether the mode was set via BIOS or the app.

---

## Automatic Power Profile Management

The power-profile-manager service runs automatically and switches between:
- **Performance mode** when on AC power
- **Power-saver mode** when on battery

This happens independently of GPU mode switching and works with power-profiles-daemon.

---

## Uninstallation

    sudo apt remove gpumode
    sudo apt autoremove

---

## Reporting Bugs

Include:
- Ubuntu version (Needs to be 25.10+)
- GPU models
- Driver versions (nvidia-smi output)
- BIOS graphics setting (Framework Laptop 16 users)
- Steps to reproduce
- Log file: ~/.local/share/gpumode/gpumode.log

---

## License

GPL-3.0
