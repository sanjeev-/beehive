#!/bin/bash
# Example: Running multiple agents in parallel

PROJECT_DIR=~/code/myproject

echo "Starting parallel development workflow..."

# Create multiple agents working on different features
echo "1. Creating UI modernization agent..."
beehive create ui-modernize \
  -i "Modernize the UI components using the latest design system. Update buttons, forms, and navigation." \
  -w $PROJECT_DIR

echo "2. Creating API optimization agent..."
beehive create api-optimize \
  -i "Optimize database queries in the API layer. Focus on the user and product endpoints." \
  -w $PROJECT_DIR

echo "3. Creating test coverage agent..."
beehive create add-tests \
  -i "Improve test coverage to at least 80%. Focus on critical business logic." \
  -w $PROJECT_DIR

echo "4. Creating documentation agent..."
beehive create update-docs \
  -i "Update all documentation to reflect recent API changes. Include examples." \
  -w $PROJECT_DIR

echo ""
echo "All agents started! Monitoring sessions..."
echo ""

# Show all running sessions
beehive list --status running

echo ""
echo "To monitor individual sessions:"
echo "  beehive logs ui-modernize -f"
echo "  beehive attach api-optimize"
echo ""
echo "To check status:"
echo "  beehive status ui-modernize"
echo ""
echo "When agents are done, create PRs:"
echo "  beehive pr ui-modernize -t 'Modernize UI components'"
echo "  beehive pr api-optimize -t 'Optimize API database queries'"
echo "  beehive pr add-tests -t 'Improve test coverage to 80%'"
echo "  beehive pr update-docs -t 'Update API documentation'"
