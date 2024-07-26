import sqlite3

##Connect to SQLite Database
connection=sqlite3.connect("student.db")
#Create a cursor object to insert records and create table
cursor=connection.cursor()

##create a table with cursor
table_info="""
Create table STUDENT(NAME VARCHAR(25),CLASS VARCHAR(25),SECTION VARCHAR(25),CGPA INT,X INT,XII INT);
"""
cursor.execute(table_info)
cursor.execute('''Insert into STUDENT values('Chandril','Generative AI','A','9.25','95.2','89')''')
cursor.execute('''Insert into STUDENT values('Soujanya','Full Stack','B','8.5','93','90')''')
cursor.execute('''Insert into STUDENT values('Sunnidhya','Biology','B','9.5','88','82')''')
cursor.execute('''Insert into STUDENT values('Mohor','Biology','B','7.2','56','97')''')
cursor.execute('''Insert into STUDENT values('Ashmit','Data Science','A','8.9','97','98')''')
cursor.execute('''Insert into STUDENT values('Pattotri','Chartered Accountant','A','9.6','85','96')''')

##generate records

print("the inserted records are")
data=cursor.execute('''Select * from STUDENT''')
for row in data:
    print(row)

connection.commit()
connection.close()