"""
Gunicorn runtime settings for the Render Flask service.

The Gemini report-analysis request can take longer than Gunicorn's default
30-second worker timeout. Allow up to 120 seconds for a response. Render's
service root directory should be set to "backend" so this file is loaded
automatically by `gunicorn app:app`.
"""

timeout = 120
graceful_timeout = 30
keepalive = 5
