#!/usr/bin/env bash
set -euo pipefail

# Task Management System Deployment Script
# Supports deployment to staging and production environments

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

# Environment variables with defaults
ENVIRONMENT="${ENVIRONMENT:-staging}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-ghcr.io}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ROLLBACK_ENABLED="${ROLLBACK_ENABLED:-true}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Validate environment
validate_environment() {
    case "$ENVIRONMENT" in
        staging|production)
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT. Must be 'staging' or 'production'"
            exit 1
            ;;
    esac
}

# Create backup
create_backup() {
    log_info "Creating backup before deployment..."

    mkdir -p "$BACKUP_DIR"

    # Backup database if running
    if docker ps | grep -q "taskmanager-db"; then
        log_info "Backing up database..."
        docker exec taskmanager-db pg_dump -U taskuser taskmanager > "$BACKUP_DIR/db-backup-$TIMESTAMP.sql"
    fi

    # Backup current deployment
    if [ -d "$PROJECT_ROOT/current" ]; then
        cp -r "$PROJECT_ROOT/current" "$BACKUP_DIR/backup-$TIMESTAMP"
    fi

    log_success "Backup created: $BACKUP_DIR/backup-$TIMESTAMP"
}

# Pull latest images
pull_images() {
    log_info "Pulling latest Docker images..."

    docker pull $DOCKER_REGISTRY/$GITHUB_REPOSITORY/backend:$IMAGE_TAG
    docker pull $DOCKER_REGISTRY/$GITHUB_REPOSITORY/frontend:$IMAGE_TAG

    log_success "Images pulled successfully"
}

# Deploy services
deploy_services() {
    log_info "Deploying services to $ENVIRONMENT..."

    # Set environment-specific variables
    case "$ENVIRONMENT" in
        staging)
            COMPOSE_FILE="infra/docker-compose.yml"
            PROJECT_NAME="taskmanager-staging"
            ;;
        production)
            COMPOSE_FILE="infra/docker-compose.prod.yml"
            PROJECT_NAME="taskmanager-prod"
            ;;
    esac

    # Stop existing services gracefully
    log_info "Stopping existing services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down --timeout 30

    # Start new services
    log_info "Starting new services..."
    docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d

    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps | grep -q "healthy\|running"; then
            log_success "Services are healthy"
            break
        fi

        log_info "Waiting for services to be healthy... (attempt $attempt/$max_attempts)"
        sleep 10
        ((attempt++))
    done

    if [ $attempt -gt $max_attempts ]; then
        log_error "Services failed to become healthy within timeout"
        return 1
    fi
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."

    case "$ENVIRONMENT" in
        staging)
            PROJECT_NAME="taskmanager-staging"
            ;;
        production)
            PROJECT_NAME="taskmanager-prod"
            ;;
    esac

    # Run migrations in backend container
    docker-compose -f "infra/docker-compose.yml" -p "$PROJECT_NAME" exec -T backend python manage.py migrate

    log_success "Database migrations completed"
}

# Run smoke tests
run_smoke_tests() {
    log_info "Running smoke tests..."

    # Test backend health endpoint
    if curl -f -s "http://localhost:8000/health" > /dev/null; then
        log_success "Backend health check passed"
    else
        log_error "Backend health check failed"
        return 1
    fi

    # Test frontend
    if curl -f -s -I "http://localhost:3000" | grep -q "200 OK"; then
        log_success "Frontend health check passed"
    else
        log_error "Frontend health check failed"
        return 1
    fi
}

# Rollback deployment
rollback() {
    log_error "Deployment failed. Initiating rollback..."

    if [ "$ROLLBACK_ENABLED" = "true" ]; then
        log_info "Rolling back to previous version..."

        # Find latest backup
        local latest_backup=$(ls -t "$BACKUP_DIR" | grep "backup-" | head -1)

        if [ -n "$latest_backup" ]; then
            log_info "Restoring from backup: $latest_backup"

            # Restore database
            if [ -f "$BACKUP_DIR/db-backup-$TIMESTAMP.sql" ]; then
                docker exec -i taskmanager-db psql -U taskuser taskmanager < "$BACKUP_DIR/db-backup-$TIMESTAMP.sql"
            fi

            # Restore services
            case "$ENVIRONMENT" in
                staging)
                    PROJECT_NAME="taskmanager-staging"
                    ;;
                production)
                    PROJECT_NAME="taskmanager-prod"
                    ;;
            esac

            docker-compose -f "infra/docker-compose.yml" -p "$PROJECT_NAME" up -d
            log_success "Rollback completed"
        else
            log_error "No backup found for rollback"
        fi
    else
        log_warning "Rollback disabled"
    fi
}

# Send notifications
send_notification() {
    local status="$1"
    local message="$2"

    log_info "Sending deployment notification..."

    # Here you could integrate with Slack, email, etc.
    # For now, just log the notification
    echo "Deployment $status: $message"

    if [ "$status" = "success" ]; then
        log_success "Deployment completed successfully!"
    else
        log_error "Deployment failed!"
    fi
}

# Main deployment process
main() {
    log_info "Starting deployment to $ENVIRONMENT environment..."
    log_info "Image tag: $IMAGE_TAG"

    # Validate environment
    validate_environment

    # Create backup
    create_backup

    # Pull images
    pull_images

    # Deploy services
    if deploy_services; then
        # Run migrations
        run_migrations

        # Run smoke tests
        if run_smoke_tests; then
            send_notification "success" "Deployment to $ENVIRONMENT completed successfully"
        else
            rollback
            send_notification "failure" "Smoke tests failed after deployment to $ENVIRONMENT"
            exit 1
        fi
    else
        rollback
        send_notification "failure" "Service deployment failed for $ENVIRONMENT"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment|-e)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --image-tag|-t)
            IMAGE_TAG="$2"
            shift 2
            ;;
        --no-rollback)
            ROLLBACK_ENABLED="false"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -e, --environment ENV    Deployment environment (staging|production)"
            echo "  -t, --image-tag TAG      Docker image tag to deploy"
            echo "  --no-rollback           Disable automatic rollback on failure"
            echo "  -h, --help              Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main deployment
main "$@"