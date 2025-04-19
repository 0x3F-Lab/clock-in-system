import psycopg2
import os
from dotenv import load_dotenv


# Load environment variables from the .env file
load_dotenv()

# Database connection details from .env
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_HOST = "localhost"
POSTGRES_PORT = os.getenv("POSTGRES_PORT")


# Establish the database connection
def get_db_connection():
    connection = psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
    )
    return connection


# Check if the database is accessible
def check_db_connection():
    try:
        connection = get_db_connection()
        connection.close()
        print("Database connection successful.\n\n\n")
    except psycopg2.OperationalError as e:
        print(f"Error: {e}")
        print(
            "\nCould not connect to the database. Please ensure the Docker container is running."
        )
        exit(1)


# Function to insert or update key-value pairs in the KeyValueStore table
def upsert_key_value(key, value):
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # SQL query to insert or update key-value pair
        cursor.execute(
            """
            INSERT INTO auth_app_keyvaluestore (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE
            SET value = EXCLUDED.value;
        """,
            (key, value),
        )

        # Commit the transaction
        connection.commit()

        # Close the cursor and connection
        cursor.close()
        connection.close()
        print(f"\nSuccessfully upserted key: {key} with value: {value}")

    except Exception as e:
        print(f"Error: {e}")
        if "connection" in locals() and connection:
            connection.rollback()
        if "cursor" in locals() and cursor:
            cursor.close()
        if "connection" in locals() and connection:
            connection.close()


# Function to prompt the user for values for the preset keys
def get_user_input():
    preset_keys = {
        "store_latitude": "Enter the latitude of the store as a float (e.g. for 5.1°N enter 5.1): ",
        "store_longitude": "Enter the longitude of the store as a float (e.g. for -2.2°W enter -2.2): ",
        "allowable_clocking_dist_m": "Enter the allowable clocking distance in meters as an integer (e.g., 5): ",
    }

    for key, prompt in preset_keys.items():
        value = input(prompt)

        # Upsert the value for each preset key
        upsert_key_value(key, value)
        print("\n\n\n\n\n")

    print("All required keys have been inserted/updated successfully.")


if __name__ == "__main__":
    # Check database connection before proceeding
    check_db_connection()

    # Prompt the user for input
    get_user_input()
