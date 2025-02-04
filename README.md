# Instagram Comments Manager

A web-based tool for managing Instagram comments efficiently and securely.

A web application that allows you to manage and respond to Instagram comments through a simple interface.

## Features

- View recent Instagram posts with thumbnails
- Display comments and their replies
- Respond to comments directly from the interface
- Real-time UI updates
- Docker support for easy deployment

## Prerequisites

- Docker and Docker Compose installed on your system
- Instagram account credentials
- Instagram Business Account ID
- Instagram App ID and Secret

## Quick Start

1. Create a `.env` file with your credentials:

```env
INSTAGRAM_USERNAME=your_username
INSTAGRAM_PASSWORD=your_password
INSTAGRAM_APP_ID=your_app_id
APP_SECRET=your_app_secret
BUSINESS_ACCOUNT_ID=your_business_account_id
```

2. Run the application:

```bash
docker-compose up -d
```

The application will be available at http://localhost:51968

## Environment Variables

| Variable | Description |
|----------|-------------|
| INSTAGRAM_USERNAME | Your Instagram username |
| INSTAGRAM_PASSWORD | Your Instagram password |
| INSTAGRAM_APP_ID | Your Instagram App ID |
| APP_SECRET | Your App Secret |
| BUSINESS_ACCOUNT_ID | Your Instagram Business Account ID |
| DOCKER_IMAGE | (Optional) Custom Docker image name |

## Building the Docker Image

To build and push the Docker image:

```bash
# Build the image
docker build -t quecreate/instagram-comments:latest .

# Push to Docker Hub
docker push quecreate/instagram-comments:latest
```

## Development

To run the application locally without Docker:

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app_private.py
```

## Security Notes

- Store sensitive credentials securely
- Use environment variables for configuration
- The application runs as a non-root user in Docker
- Consider using Docker secrets in production

## Data Persistence

The application uses a Docker volume (`instagram_data`) to persist data between container restarts.

## Health Checks

The Docker container includes health checks that monitor the application's status every 30 seconds.

## Troubleshooting

1. If the container fails to start, check the logs:
```bash
docker-compose logs -f instagram-comments
```

2. To restart the service:
```bash
docker-compose restart instagram-comments
```

3. To rebuild the container:
```bash
docker-compose up -d --build
```

## License

MIT License

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request