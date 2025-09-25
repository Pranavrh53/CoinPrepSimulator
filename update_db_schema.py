import mysql.connector

def update_database_schema():
    try:
        # Database connection configuration
        db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': 'Pranavrh123$',
            'database': 'crypto_tracker'
        }
        
        # Connect to the database
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Add risk_score column if it doesn't exist
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = 'crypto_tracker' 
            AND TABLE_NAME = 'users' 
            AND COLUMN_NAME = 'risk_score'
        """)
        
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                ALTER TABLE users 
                ADD COLUMN risk_score INT DEFAULT 0
            """)
            print("Added risk_score column to users table")
        
        # Modify risk_tolerance column to support longer values
        cursor.execute("""
            ALTER TABLE users 
            MODIFY COLUMN risk_tolerance VARCHAR(50) DEFAULT 'Medium'
        """)
        print("Updated risk_tolerance column")
        
        # Commit changes
        conn.commit()
        print("Database schema updated successfully!")
        
        # Show the updated table structure
        cursor.execute("DESCRIBE users")
        print("\nUpdated users table structure:")
        print("-" * 50)
        for column in cursor.fetchall():
            print(f"{column[0]:<15} {column[1]:<20} {column[2]}")
        
    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    update_database_schema()
