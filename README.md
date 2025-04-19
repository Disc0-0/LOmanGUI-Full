# LOmanGUI - Last Oasis Server Manager

A comprehensive solution for managing Last Oasis dedicated servers, featuring both a native GUI and modern web interface. Take command of your server fleet through an intuitive dashboard while maintaining robust control over every aspect of server operation.

## Features

- **Dual Interface Control**
  - Native Qt-based GUI for desktop management
  - Modern web interface accessible from any browser
  - Real-time synchronization between interfaces

- **Advanced Server Management**
  - Multi-server tile management with individual controls
  - Real-time server status monitoring
  - Automated restart scheduling
  - Intelligent crash recovery
  - Real-time tile name tracking and updating

- **Mod Management**
  - Automated mod updates and version tracking
  - Workshop mod installation and configuration
  - Mod backup and verification
  - Real-time update notifications

- **Discord Integration**
  - Server status notifications
  - Restart announcements
  - Mod update alerts
  - Player join/leave notifications
  - In-game chat relay
  - Tile status changes

- **Backup Management**
  - Automated backup scheduling
  - Configurable retention policies
  - Pre-update safety backups
  - Mod state preservation

- **Administrative Tools**
  - In-game message broadcasting
  - Server commands via web interface
  - Real-time log monitoring
  - Performance metrics tracking

## Architecture

The application consists of three main components working in harmony:

1. **Core Backend (LastOasisManager)**
   - Server process management and monitoring
   - Mod update checking and deployment
   - Configuration management
   - Status tracking and notification dispatch

2. **Desktop GUI Interface**
   - Native Qt-based application
   - Real-time server monitoring
   - Direct server control
   - Local system integration

3. **Web Interface**
   - FastAPI-powered RESTful backend
   - Modern responsive dashboard
   - Real-time updates via websockets
   - Mobile-friendly design

## Configuration

Key `config.json` settings:

```json
{
    "folder_path": "Path to server installation",
    "steam_cmd_path": "Path to SteamCMD",
    "tile_num": "Number of server tiles",
    "identifier": "Server identifier prefix",
    "enable_discord": true,
    "server_status_webhook": "Discord webhook URL",
    "enable_restarts": true,
    "restart_hours": "0,6,12,18",
    "notify_minutes": "30,15,5,1",
    "mod_check_interval": 300,
    "server_check_interval": 3600
}
```

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Last Oasis Dedicated Server
- SteamCMD installed
- Qt libraries (for GUI interface)
- Valid Last Oasis server configuration

### Dependencies

The project requires the following main dependency groups:

**Core Dependencies**
- requests>=2.28.0
- psutil>=5.9.0
- beautifulsoup4>=4.11.0

**Web Interface Dependencies**
- fastapi>=0.95.0
- uvicorn>=0.21.0
- pydantic>=1.10.0
- python-multipart>=0.0.5
- python-jose[cryptography]>=3.3.0
- passlib[bcrypt]>=1.7.4

**Frontend Dependencies**
- jinja2>=3.1.0
- aiofiles>=0.8.0

All dependencies can be installed via:
```bash
pip install -r requirements.txt
```

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Disc0-0/LOmanGUI.git
   cd LOmanGUI
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy and configure settings:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your server settings
   ```

4. Start the application:
   - For GUI: `python main_gui.py`
   - For Web Interface: `python api.py`

5. Access interfaces:
   - GUI: Launches automatically
   - Web: http://localhost:8080

## Discord Integration

1. Create webhooks in your Discord server
2. Configure in `config.json`:
   ```json
   {
       "enable_discord": true,
       "server_status_webhook": "webhook_url",
       "discord_message_types": {
           "chat": true,
           "join": true,
           "tile": true,
           "kill": true
       }
   }
   ```

## Automatic Updates

### Server Updates
- Checks for server updates every `server_check_interval` seconds
- Automatically notifies and coordinates restarts
- Preserves server state during updates

### Mod Updates
- Monitors Steam Workshop for mod updates
- Automatically downloads and installs updates
- Configurable update intervals
- Backup of existing mods before updates

## Troubleshooting

Common configuration issues:

1. **Configuration error - check config.json**
   - Normal during first startup
   - Verify all paths in config.json
   - Check file permissions

2. **Steam Workshop Connection**
   - Verify SteamCMD installation
   - Check workshop_app_id setting
   - Ensure anonymous login works

3. **Discord Webhook Errors**
   - Verify webhook URLs
   - Check Discord server permissions
   - Ensure proper webhook format

## Security Notice

**DISCLAIMER**: This software is provided 'as is', without warranty of any kind. Use at your own risk. While designed to enhance your server management experience, please back up important data before use.

For production use, you should:
1. Configure proper authentication
2. Set up HTTPS/TLS
3. Restrict CORS to your specific domains
4. Use environment variables for sensitive values
5. Implement proper firewall rules

## Made by Disc0 © 2025

Last Oasis is a trademark of Donkey Crew. This tool is not affiliated with or endorsed by Donkey Crew.
