# Optional helper: the staged commit workflow from the project brief.
# Run each block yourself after the stage works. Replace YOUR_USERNAME. Never use force-push.

# --- one time ---
# git init
# git branch -M main
# git remote add origin https://github.com/YOUR_USERNAME/AI-Receptionist.git

# git add . ; git commit -m "Initial project setup"
# git add . ; git commit -m "Set up PostgreSQL database"
# git add . ; git commit -m "Add clinic information APIs"
# git add . ; git commit -m "Add AI receptionist chat"
# git add . ; git commit -m "Add appointment scheduling"
# git add . ; git commit -m "Add appointment booking confirmation"
# git add . ; git commit -m "Add appointment management"
# git add . ; git commit -m "Build receptionist frontend"
# git add . ; git commit -m "Integrate frontend and backend"
# git add . ; git commit -m "Add tests and documentation"
# git push -u origin main

# Always check git status before committing: .env must NOT appear.
