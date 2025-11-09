# Strava Activity GPS Fetcher

This project uses the Strava API to get the GPS coordinates for your latest activity. 

It is written in Python and uses the requests library to make the API calls. It's a simple script that can be run from the command line and uses `.env` to store the Strava API credentials securely.

## Features

- Fetches your latest Strava activity
- Retrieves GPS coordinates (latitude/longitude) for the activity
- Displays activity details (name, type, distance, date)
- Shows first and last 5 GPS points with full coordinate list

## Prerequisites

- Python 3.6 or higher
- A Strava account
- Strava API credentials (Client ID, Client Secret, and Refresh Token)

## Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd strava_wrapped
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Get Strava API Credentials

1. Go to [Strava API Settings](https://www.strava.com/settings/api)
2. Create an application if you haven't already:
   - Application Name: (your choice)
   - Category: (your choice)
   - Website: http://localhost
   - Authorization Callback Domain: localhost
3. Note down your **Client ID** and **Client Secret**
4. Visit this URL (replace YOUR_CLIENT_ID):
   ```
   https://www.strava.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost&response_type=code&scope=activity:read,activity:read_all,profile:read_all&approval_prompt=force
   ```
5. Authorize the application
6. Copy the `code=` parameter from the redirect URL
7. Exchange the code for a refresh token:
   ```bash
   curl -X POST https://www.strava.com/oauth/token \
     -d client_id=YOUR_CLIENT_ID \
     -d client_secret=YOUR_CLIENT_SECRET \
     -d code=AUTHORIZATION_CODE \
     -d grant_type=authorization_code
   ```
8. The response will contain your `refresh_token`

### 4. Create .env File

Create a `.env` file in the project root with your credentials:

```bash
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here
STRAVA_REFRESH_TOKEN=your_refresh_token_here
```

## Usage

### Basic Usage

Run the script from the command line:

```bash
python strava_activity.py
```

Or make it executable and run directly:

```bash
chmod +x strava_activity.py
./strava_activity.py
```

### Troubleshooting (Debug Mode)

If you encounter errors, run with the `--debug` flag to see detailed information:

```bash
python strava_activity.py --debug
```

This will show you:
- Credential lengths and partial values
- Token exchange details
- API request/response information
- Exact error messages from Strava

### Getting a New Refresh Token

If you get a 401 error, your refresh token may have expired or been revoked. Follow the OAuth flow in the setup instructions (Step 3) to get a fresh token with the correct scopes.

## Example Output

```
Fetching latest activity...

============================================================
Latest Activity: Morning Run
Type: Run
Distance: 5.23 km
Date: 2025-11-09T08:30:00Z
============================================================

Fetching GPS coordinates for activity 123456789...
Total GPS points: 342

First 5 GPS coordinates:
  1. Latitude: 37.774929, Longitude: -122.419416
  2. Latitude: 37.774930, Longitude: -122.419420
  3. Latitude: 37.774932, Longitude: -122.419425
  4. Latitude: 37.774935, Longitude: -122.419430
  5. Latitude: 37.774938, Longitude: -122.419435

  ...

Last 5 GPS coordinates:
  338. Latitude: 37.775100, Longitude: -122.420100
  339. Latitude: 37.775105, Longitude: -122.420110
  340. Latitude: 37.775110, Longitude: -122.420120
  341. Latitude: 37.775115, Longitude: -122.420130
  342. Latitude: 37.775120, Longitude: -122.420140
```

## Project Structure

```
strava_wrapped/
├── .env                    # Your API credentials (not tracked by git)
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── requirements.txt       # Python dependencies
└── strava_activity.py     # Main script
```

## Security Note

Never commit your `.env` file or expose your API credentials. The `.gitignore` file is configured to exclude `.env` from version control.

## Troubleshooting

### 401 Unauthorized Error

If you get a 401 error:

1. **Run with debug mode first:**
   ```bash
   python strava_activity.py --debug
   ```

2. **Common causes:**
   - **Refresh token expired** - Strava refresh tokens can be revoked if you deauthorize the app
   - **Wrong scope** - Your token needs `activity:read_all` scope
   - **Whitespace in .env** - Make sure there are no extra spaces or quotes
   - **Wrong client credentials** - Client ID/Secret must match the app

3. **Solution:** Get a new refresh token with the correct scopes:
   - Follow Step 3 in the Setup section above
   - Make sure the authorization URL includes all required scopes
   - Use the authorization code immediately (they expire quickly)

### No Activities Found

- Make sure you have at least one activity on your Strava account
- Check that your activities are not set to private

### No GPS Data Available

- Some activities (like indoor workouts) don't have GPS data
- Try running the script after completing an outdoor activity

### Connection Issues

- Check your internet connection
- Verify that Strava's API is accessible (not blocked by firewall)

## Quick Start Summary

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Get your Strava API credentials
# Follow Step 3 in the Setup section to get your refresh token

# 3. Create .env file with your credentials
# STRAVA_CLIENT_ID=...
# STRAVA_CLIENT_SECRET=...
# STRAVA_REFRESH_TOKEN=...

# 4. Run the script
python strava_activity.py
```

## License

MIT