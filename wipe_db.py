import os
import psycopg2

# Paste your actual external database URL from Render between the quotes below:
# Hardcoded URL removed for security. Ensure DATABASE_URL is set in your environment.
DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    print("❌ Error: DATABASE_URL environment variable is not set.")
    exit(1)

try:
    # Connect directly to Render Postgres
    connection = psycopg2.connect(DB_URL)
    cursor = connection.cursor()
    
    # We use a raw text string with double quotes around "user" so Python doesn't look for variables
    sql_command = 'TRUNCATE TABLE notification, listing, "user" RESTART IDENTITY CASCADE;'
    
    cursor.execute(sql_command)
    connection.commit()
    
    print("🚀 Success! Database tables wiped and counters reset to 1.")
    
    cursor.close()
    connection.close()

except Exception as e:
    print(f"❌ Error wiping database: {e}")