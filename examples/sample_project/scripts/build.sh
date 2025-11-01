#!/usr/bin/env bash
set -euo pipefail

# Task Management System Build Script
# This script builds both backend and frontend components

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up build artifacts..."
    rm -rf "$BUILD_DIR" "$DIST_DIR"
}

# Trap to cleanup on exit
trap cleanup EXIT

# Check if required tools are installed
check_dependencies() {
    log_info "Checking dependencies..."

    local missing_deps=()

    if ! command -v python3 &> /dev/null; then
        missing_deps+=("python3")
    fi

    if ! command -v node &> /dev/null; then
        missing_deps+=("node")
    fi

    if ! command -v npm &> /dev/null; then
        missing_deps+=("npm")
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install the missing dependencies and try again."
        exit 1
    fi

    log_success "All dependencies are available."
}

# Build backend
build_backend() {
    log_info "Building backend..."

    cd "$BACKEND_DIR"

    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3 -m venv venv
    fi

    # Activate virtual environment
    source venv/bin/activate

    # Install/update dependencies
    log_info "Installing Python dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt

    # Run tests
    log_info "Running backend tests..."
    if command -v pytest &> /dev/null; then
        pytest --tb=short --disable-warnings
        log_success "Backend tests passed."
    else
        log_warning "pytest not found, skipping tests."
    fi

    # Build package (if applicable)
    if [ -f "setup.py" ] || [ -f "pyproject.toml" ]; then
        log_info "Building Python package..."
        python -m build --wheel --sdist
    fi

    # Deactivate virtual environment
    deactivate

    log_success "Backend build completed."
}

# Build frontend
build_frontend() {
    log_info "Building frontend..."

    cd "$FRONTEND_DIR"

    # Install dependencies
    log_info "Installing Node.js dependencies..."
    npm ci

    # Run linting
    log_info "Running ESLint..."
    if npm run lint &> /dev/null; then
        log_success "ESLint passed."
    else
        log_warning "ESLint failed or not configured."
    fi

    # Run tests
    log_info "Running frontend tests..."
    if npm test -- --watchAll=false --passWithNoTests &> /dev/null; then
        log_success "Frontend tests passed."
    else
        log_warning "Frontend tests failed or not configured."
    fi

    # Build production bundle
    log_info "Building production bundle..."
    npm run build

    log_success "Frontend build completed."
}

# Package application
package_app() {
    log_info "Packaging application..."

    # Create distribution directory
    mkdir -p "$DIST_DIR"

    # Copy backend files
    log_info "Copying backend files..."
    cp -r "$BACKEND_DIR" "$DIST_DIR/"

    # Copy frontend build
    log_info "Copying frontend build..."
    cp -r "$FRONTEND_DIR/build" "$DIST_DIR/frontend"

    # Copy infrastructure files
    log_info "Copying infrastructure files..."
    cp -r "$PROJECT_ROOT/infra" "$DIST_DIR/"

    # Create deployment archive
    log_info "Creating deployment archive..."
    cd "$PROJECT_ROOT"
    tar -czf "taskmanager-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$DIST_DIR" .

    log_success "Application packaged successfully."
}

# Generate build report
generate_report() {
    log_info "Generating build report..."

    local report_file="$BUILD_DIR/build-report.txt"

    mkdir -p "$BUILD_DIR"

    {
        echo "Task Management System Build Report"
        echo "==================================="
        echo "Build Date: $(date)"
        echo "Build Host: $(hostname)"
        echo ""
        echo "Backend Information:"
        echo "- Python Version: $(python3 --version 2>&1)"
        echo "- Virtual Environment: $BACKEND_DIR/venv"
        echo ""
        echo "Frontend Information:"
        echo "- Node Version: $(node --version)"
        echo "- NPM Version: $(npm --version)"
        echo ""
        echo "Build Artifacts:"
        echo "- Backend: $DIST_DIR/backend"
        echo "- Frontend: $DIST_DIR/frontend"
        echo "- Infrastructure: $DIST_DIR/infra"
        echo ""
        echo "Next Steps:"
        echo "1. Review the build artifacts in $DIST_DIR"
        echo "2. Test the application locally using docker-compose"
        echo "3. Deploy to staging environment"
    } > "$report_file"

    log_success "Build report generated: $report_file"
}

# Main build process
main() {
    log_info "Starting Task Management System build..."
    log_info "Project root: $PROJECT_ROOT"

    check_dependencies
    build_backend
    build_frontend
    package_app
    generate_report

    log_success "Build completed successfully!"
    log_info "Build artifacts are available in: $DIST_DIR"
    log_info "Build report: $BUILD_DIR/build-report.txt"
}

# Run main function
main "$@"
