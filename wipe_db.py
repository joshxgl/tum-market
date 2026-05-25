import os
import psycopg2

# Paste your actual external database URL from Render between the quotes below:
DB_URL = "postgresql://tummarketdb_3zvv_user:h2drFowx6C48PLUJ0KnnT85PqS6o2F9D@dpg-d8a5023eo5us739e999g-a.oregon-postgres.render.com/tum_market_db"

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