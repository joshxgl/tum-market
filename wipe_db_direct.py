import os
import psycopg2

# Paste your actual external database URL from Render between the quotes below:
# Hardcoded URL removed for security. Ensure DATABASE_URL is set in your environment.
DB_URL = os.environ.get("DATABASE_URL")

if not DB_URL:
    print("❌ Error: DATABASE_URL environment variable is not set. Cannot wipe database.")
    exit(1)

try:
    print("⏳ Connecting directly to Render PostgreSQL...")
    connection = psycopg2.connect(DB_URL)
    cursor = connection.cursor()
    
    # 1. This dynamic SQL fetches every single user table in your database
    find_all_tables_sql = """
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public';
    """
    cursor.execute(find_all_tables_sql)
    tables = cursor.fetchall()
    
    if not tables:
        print("ℹ️ Your database is already completely empty! No tables found.")
    else:
        print(f"📦 Found {len(tables)} tables. Destroying data...")
        
        # 2. Extract the names and build a dynamic DROP statement
        table_names = ", ".join([f'"{table[0]}"' for table in tables])
        drop_sql = f"DROP TABLE {table_names} CASCADE;"
        
        cursor.execute(drop_sql)
        connection.commit()
        print("✨ Success! Everything has been permanently wiped from the database.")
        
    cursor.close()
    connection.close()

except Exception as e:
    print(f"❌ Error wiping database: {e}")