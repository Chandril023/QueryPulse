from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import pandas as pd
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory to save uploaded files
UPLOAD_DIRECTORY = "uploaded_files"
DB_DIRECTORY = "databases"

# Create the directories if they don't exist
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(DB_DIRECTORY, exist_ok=True)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Delete any existing files in the UPLOAD_DIRECTORY
        for filename in os.listdir(UPLOAD_DIRECTORY):
            file_path = os.path.join(UPLOAD_DIRECTORY, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        # Save the uploaded file
        file_location = os.path.join(UPLOAD_DIRECTORY, file.filename)
        with open(file_location, "wb") as f:
            f.write(await file.read())

        # Define the new database name
        db_name = "example.db"
        db_location = os.path.join(DB_DIRECTORY, db_name)
        
        # Convert the uploaded file to an SQLite database
        convert_to_sqlite(file_location, db_location)

        return JSONResponse(content={"filename": file.filename, "database": db_name})
    except Exception as e:
        logger.error(f"Error during file upload or conversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def convert_to_sqlite(input_file, output_db, table_name='data'):
    try:
        # Read CSV or Excel file into pandas DataFrame
        if input_file.endswith('.csv'):
            df = pd.read_csv(input_file)
        elif input_file.endswith('.xlsx') or input_file.endswith('.xls'):
            df = pd.read_excel(input_file)
        else:
            raise ValueError("Unsupported file format. Please provide a CSV or Excel file.")

        # Connect to SQLite database
        conn = sqlite3.connect(output_db)
        
        # Write the data to a SQLite table
        df.to_sql(table_name, conn, if_exists='replace', index=False)

        # Commit changes and close connection
        conn.commit()
        conn.close()

        logger.info(f"Successfully converted {input_file} to {output_db} in table {table_name}")

    except Exception as e:
        logger.error(f"Error converting file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


prompt = """You are an expert in converting English questions to SQL queries. The SQL database is fixed as example.db. Please extract information from this database.

Instructions:

Basic Queries:

To get all information from the fixed table data: SELECT * FROM data;
To get rows where a column column_name has a value value: SELECT * FROM data WHERE "column_name" = 'value';
Column Information:

To get all columns from the table: PRAGMA table_info(data);
Complex Queries:

Joins: To join data with another table other_table: SELECT * FROM data JOIN other_table ON data.common_column = other_table.common_column;
Aggregations: To get the count of rows: SELECT COUNT(*) FROM data; To get the average of a numeric column: SELECT AVG(numeric_column) FROM data; To group by a column and get counts: SELECT column_name, COUNT(*) FROM data GROUP BY column_name;
Filtering and Sorting: To filter rows with multiple conditions: SELECT * FROM data WHERE column1 = 'value1' AND column2 > 10; To sort rows by a column in descending order: SELECT * FROM data ORDER BY column_name DESC; To filter and sort: SELECT * FROM data WHERE column_name = 'value' ORDER BY another_column ASC;
Subqueries:

To use a subquery: SELECT * FROM data WHERE column_name IN (SELECT column_name FROM other_table WHERE condition);
Please Note:

Replace column_name, value, other_table, common_column, numeric_column, etc., with actual names based on the database schema.
The SQL code should not have ``` at the beginning or end.
Do not include the word SQL in the output.
Always generate the response in a single line.

Please note:
- Replace `column_name` and `value` with the actual column name and value you want to query.
- The SQL code should not have ``` at the beginning or end.
- Do not include the word SQL in the output.
- The database name will always be example.db.
- The table name is fixed as 'data'.
- Always generate the response in a single line.
- This is the most important point: Always generate the SQL queries in a single line.
"""

# Configure Google Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

class QueryRequest(BaseModel):
    question: str
    database: str

@app.post("/process-prompt/")
async def process_prompt(request: QueryRequest):
    try:
        question = request.question
        db_location = os.path.join(DB_DIRECTORY, 'example.db')

        sql_query = get_gemini_response(question, prompt)
        logger.info(f"Generated SQL Query: {sql_query}")

        # Validate the SQL query and ensure it is correct
        if not validate_sql_query(sql_query):
            return {"sql_query": sql_query, "results": "Invalid SQL query."}

        # Execute the SQL query and handle the results
        result = execute_sql_query(sql_query, db_location)

        if isinstance(result, str) and "does not retrieve data" in result:
            return {"sql_query": sql_query, "results": result}
        elif isinstance(result, pd.DataFrame) and result.empty:
            return {"sql_query": sql_query, "results": "No data retrieved by the query"}
        else:
            result = result.fillna('') if isinstance(result, pd.DataFrame) else result
            results = result.to_dict(orient="records") if isinstance(result, pd.DataFrame) else result
            return {"sql_query": sql_query, "results": results}

    except Exception as e:
        logger.error(f"Error processing the prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
def execute_sql_query(sql: str, db: str):
    try:
        conn = sqlite3.connect(db)
        # Handle PRAGMA queries differently
        if "PRAGMA" in sql:
            result = pd.read_sql_query(sql, conn)
        else:
            result = pd.read_sql_query(sql, conn)
            if result.empty:
                return "Query does not retrieve data from the 'data' table."
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        return str(e)    

def get_gemini_response(question: str, prompt: str) -> str:
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content([prompt, question])
    sql_query = response.text.strip()
    
    # Clean the SQL query
    sql_query = clean_sql_query(sql_query)
    
    # Log the query for debugging
    logger.info(f"Generated SQL Query: {sql_query}")
    
    return sql_query

def clean_sql_query(sql_query: str) -> str:
    # Remove or replace literal backslashes
    sql_query = sql_query.replace('\\', '')
    
    # Ensure the query is in a single line
    sql_query = sql_query.replace('\n', ' ')
    
    return sql_query

def validate_sql_query(sql_query: str) -> bool:
    # Accept PRAGMA queries as valid
    return "SELECT" in sql_query or "PRAGMA" in sql_query

def read_sql_query(sql: str, db: str) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(db)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except Exception as e:
        logger.error(f"Error executing SQL query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    host = os.getenv("HOST", "0.0.0.0")  # Use 0.0.0.0 as a default if HOST is not set
    port = 8000  # Default to 8000 if PORT is not set

    try:
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"Error running the server: {e}")
