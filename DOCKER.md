# Docker Setup

## Quick Start (One-Liner)

```bash
docker-compose up --build
```

This will:
- Build the Docker image
- Start the webapp on port 5555
- Mount your `.env` file for Strava credentials
- Persist generated images in `static/generated/`

## Access the Webapp

Once running, open your browser to:
```
http://localhost:5555
```

## Manual Docker Commands

If you prefer not to use docker-compose:

### Build the image:
```bash
docker build -t strava-wrapped .
```

### Run the container:
```bash
docker run -d \
  --name strava-wrapped \
  -p 5555:5555 \
  -v $(pwd)/.env:/app/.env:ro \
  -v $(pwd)/static/generated:/app/static/generated \
  strava-wrapped
```

### Stop the container:
```bash
docker-compose down
# or
docker stop strava-wrapped && docker rm strava-wrapped
```

## Environment Variables

Make sure you have a `.env` file in the project root with your Strava credentials:
```
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret
STRAVA_REFRESH_TOKEN=your_refresh_token
```

## Debug Mode

To run in debug mode, set the environment variable:
```bash
FLASK_DEBUG=true docker-compose up
```

Or in docker-compose.yml, add:
```yaml
environment:
  - FLASK_DEBUG=true
```

## Troubleshooting

### Port already in use
If port 5555 is already in use, change it in `docker-compose.yml`:
```yaml
ports:
  - "8080:5555"  # Use port 8080 on host
```

### .env file not found
Make sure your `.env` file exists in the project root and contains your Strava credentials.

### Permission errors
If you get permission errors with generated images, you may need to adjust permissions:
```bash
chmod -R 777 static/generated
```

---

## 🌍 Deploying to the Internet (Free!)

Want to share your Strava Wrapped instance with friends? Use **Cloudflare Tunnel** to expose your local app to the internet for free!

### Quick Tunnel (Testing - URL changes each time)

```bash
# 1. Download cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# 2. Start the tunnel (assumes app is running on port 5556)
./cloudflared tunnel --url http://localhost:5556
```

You'll get a URL like: `https://random-words.trycloudflare.com`

### Update Strava API Settings

1. Go to https://www.strava.com/settings/api
2. Click **Edit**
3. Set **Authorization Callback Domain** to: `trycloudflare.com`
4. Save

### Update Your .env

```bash
STRAVA_REDIRECT_URI=https://your-tunnel-url.trycloudflare.com/callback
```

Then restart Docker:
```bash
docker-compose restart
```

### Permanent Tunnel (Production - Fixed URL)

For a permanent URL that doesn't change:

1. Create a free Cloudflare account at https://cloudflare.com
2. Set up a named tunnel:

```bash
# Login to Cloudflare
./cloudflared tunnel login

# Create a named tunnel
./cloudflared tunnel create strava-wrapped

# Route traffic (requires a domain on Cloudflare)
./cloudflared tunnel route dns strava-wrapped wrapped.yourdomain.com

# Run the tunnel
./cloudflared tunnel run strava-wrapped
```

### Run Tunnel as a Service (Auto-start on boot)

```bash
sudo ./cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

