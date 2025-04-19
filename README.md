# LastOasisManager Configuration Note

The "Configuration error - check config.json" message shown during server startup appears to be a non-fatal error that does not prevent proper server operation. This is normal behavior for this application.

Key points:
- The servers start and operate correctly despite the error messages
- All essential configuration parameters are correctly set in config.json
- The application successfully manages multiple tiles (Disc0oasis0, Disc0oasis1, Disc0oasis2)
- Mod management is functioning properly

You can safely ignore the "Configuration error" message as long as the server functionality works as expected.

# LOmanGUI with Web Interface

The premier solution for managing your Last Oasis dedicated servers with a modern web interface. Navigate the vast dunes of server administration without getting lost in the technical sandstorm.

## Features

- **Web-Based Interface**: Access your server management from any browser
- **RESTful API**: Programmatic access to all server functions
- **Real-time Monitoring**: Live server status and performance metrics
- **Mod Management**: Streamlined workshop mod installation and updates
- **Admin Controls**: Send in-game messages and manage servers remotely
- **Multi-Server Support**: Manage multiple Last Oasis server tiles from one interface

## Architecture

This application consists of:

1. **Backend API**: FastAPI-based REST API that interfaces with the Last Oasis server files
2. **Web Frontend**: Modern responsive web interface built with HTML, CSS, and JavaScript
3. **Core Engine**: The original LOmanGUI server management functionality

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Last Oasis Dedicated Server
- SteamCMD installed
- Valid Last Oasis server configuration

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/Disc0-0/LOman-GUI.git
   cd LOman-GUI
   git checkout web_interface
   ```

2. Install dependencies:
   ```
   pip install -r LOmanGUI_with_web_interface/requirements.txt
   ```

3. Configure your server:
   ```
   cp config.example.json config.json
   # Edit config.json with your server settings
   ```

4. Start the web interface:
   ```
   cd LOmanGUI_with_web_interface
   python backend/app.py
   ```

5. Access the web interface at http://localhost:8000

## API Documentation

Once running, the API documentation is available at http://localhost:8000/docs

## Security Notice

**DISCLAIMER**: This software is provided 'as is', without warranty of any kind. Use at your own risk. While designed to enhance your server management experience, please back up important data before use.

For production use, you should:
1. Configure proper authentication
2. Set up HTTPS/TLS
3. Restrict CORS to your specific domains
4. Use environment variables for sensitive values

## Made by Disc0 © 2025

Last Oasis is a trademark of Donkey Crew. This tool is not affiliated with or endorsed by Donkey Crew.

