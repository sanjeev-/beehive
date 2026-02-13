#!/bin/bash
# Basic usage examples for Beehive

# Example 1: Create a simple session
echo "Creating a session to fix a bug..."
beehive create fix-login-bug \
  -i "Fix the login bug where users can't log in with special characters in password" \
  -w ~/code/myproject

# Example 2: Create a session with file-based instructions
echo "Creating a session with detailed instructions from file..."
cat > /tmp/refactor-instructions.txt << 'EOF'
Refactor the authentication module:

1. Extract common authentication logic into reusable functions
2. Add comprehensive error handling
3. Improve code documentation
4. Ensure all existing tests still pass
5. Add new tests for edge cases

Follow the existing code style and patterns.
EOF

beehive create refactor-auth \
  -i @/tmp/refactor-instructions.txt \
  -w ~/code/myproject \
  -p "Start by analyzing the current authentication code structure"

# Example 3: Monitor multiple sessions
echo "Listing all active sessions..."
beehive list --status running

# Example 4: Interact with a session
echo "Sending additional instructions to a session..."
beehive send fix-login-bug "Also add validation for email format"

# Example 5: View logs
echo "Viewing logs in real-time..."
beehive logs fix-login-bug -f

# Example 6: Create PR when done
echo "Creating a pull request..."
beehive pr fix-login-bug \
  -t "Fix login bug with special characters" \
  --draft

# Example 7: Clean up
echo "Stopping and deleting completed sessions..."
beehive stop refactor-auth
beehive delete refactor-auth --force
