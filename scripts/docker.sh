#!/bin/bash

# Med-Analyst Docker Management Script
# This script helps manage the Docker environment for development and production

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if .env file exists
check_env_file() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Please create one from .env.example"
        if [ -f .env.example ]; then
            print_status "Copying .env.example to .env..."
            cp .env.example .env
            print_warning "Please edit .env file with your actual values before proceeding"
            return 1
        else
            print_error ".env.example not found. Please create .env file manually"
            return 1
        fi
    fi
    return 0
}

# Function to display usage
usage() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  dev              Start development environment with hot reloading"
    echo "  prod             Start production environment"
    echo "  build            Build all services"
    echo "  up               Start services (production mode)"
    echo "  down             Stop and remove containers"
    echo "  logs             Show logs from all services"
    echo "  logs-backend     Show logs from backend service"
    echo "  logs-frontend    Show logs from frontend service"
    echo "  reset            Stop containers and remove volumes (destructive)"
    echo "  status           Show status of all containers"
    echo "  shell-backend    Open shell in backend container"
    echo "  shell-frontend   Open shell in frontend container"
    echo "  help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 dev           # Start development environment"
    echo "  $0 prod          # Start production environment"
    echo "  $0 logs          # View logs from all services"
    echo "  $0 reset         # Reset everything (careful!)"
}

# Main command handling
case "${1:-help}" in
    "dev")
        print_status "Starting development environment..."
        if check_env_file; then
            docker-compose -f docker-compose.dev.yml up --build
        fi
        ;;
    
    "prod")
        print_status "Starting production environment..."
        if check_env_file; then
            docker-compose up --build -d
            print_success "Production environment started in detached mode"
            print_status "View logs with: $0 logs"
        fi
        ;;
    
    "build")
        print_status "Building all services..."
        docker-compose build
        print_success "All services built successfully"
        ;;
    
    "up")
        print_status "Starting services..."
        if check_env_file; then
            docker-compose up -d
            print_success "Services started in detached mode"
        fi
        ;;
    
    "down")
        print_status "Stopping services..."
        docker-compose down
        docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
        print_success "Services stopped"
        ;;
    
    "logs")
        print_status "Showing logs from all services..."
        docker-compose logs -f
        ;;
    
    "logs-backend")
        print_status "Showing backend logs..."
        docker-compose logs -f backend
        ;;
    
    "logs-frontend")
        print_status "Showing frontend logs..."
        docker-compose logs -f frontend
        ;;
    
    "reset")
        print_warning "This will stop all containers and remove volumes (destructive operation)"
        read -p "Are you sure? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Resetting environment..."
            docker-compose down -v
            docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || true
            docker system prune -f
            print_success "Environment reset complete"
        else
            print_status "Reset cancelled"
        fi
        ;;
    
    "status")
        print_status "Container status:"
        docker-compose ps
        ;;
    
    "shell-backend")
        print_status "Opening shell in backend container..."
        docker-compose exec backend /bin/bash
        ;;
    
    "shell-frontend")
        print_status "Opening shell in frontend container..."
        docker-compose exec frontend /bin/sh
        ;;
    
    "help")
        usage
        ;;
    
    *)
        print_error "Unknown command: $1"
        echo ""
        usage
        exit 1
        ;;
esac