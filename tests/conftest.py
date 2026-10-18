import os

# Tests must not pick up the user's ~/.config/campus-assistant/env.
os.environ["CAMPUS_ENV_FILE"] = os.devnull
