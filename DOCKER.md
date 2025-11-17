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

