import os
import psycopg2

# Paste your actual external database URL from Render between the quotes below:
DB_URL = "postgresql://tummarketdb_3zvv_user:h2drFowx6C48PLUJ0KnnT85PqS6o2F9D@dpg-d8a5023eo5us739e999g-a.oregon-postgres.render.com/tum_market_db"

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