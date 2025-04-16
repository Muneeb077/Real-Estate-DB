import mysql.connector
from mysql.connector import Error

class MySQLConnection:

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host = 'localhost',
                user = 'root',
                password = 'root1234',
                database = 'real_estate'
            )
        except Error as e:
            print(f'Error while connecting to MySQL: {e}')

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()
            # print("Disconnected from MySQL Database")
        else:
            print("No active connection to disconnect")
