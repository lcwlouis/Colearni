#!/bin/bash

set -e

echo "Setting up AI Research App..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit .env file with your configuration"
fi

# Initialize submodules if not already done
echo "Initializing submodules..."
git submodule update --init --recursive

# Generate SearXNG secret if not set
if ! grep -q "SEARXNG_SECRET=" .env || grep -q "your-secret-key-here" .env; then
    echo "Generating SearXNG secret..."
    SECRET=$(openssl rand -hex 32)
    sed -i "s/your-secret-key-here/$SECRET/" .env
fi

# Create necessary directories
mkdir -p logs
mkdir -p ssl

echo "Setup complete! Run 'docker-compose up -d' to start the services."