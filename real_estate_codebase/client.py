from dbconnection import MySQLConnection

class Client:
    def __init__(self):
        self.db = MySQLConnection()

    def register_client(self, c_name, c_username, c_password, contact, postal_code, city, street, state):
        """
        Registers a new client into the Clients table.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = """
            INSERT INTO Clients (c_name, c_username, c_password, contact, postal_code, city, street, state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (c_name, c_username, c_password, contact, postal_code, city, street, state))
            self.db.connection.commit()
            print("Client registered successfully!")
        except Exception as e:
            print(f"Error registering client: {e}")
        finally:
            self.db.disconnect()

    def load_client_info(self, c_username):
        """
        Fetches and returns client information based on the username.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor(dictionary=True)
            query = "SELECT * FROM Clients WHERE c_username = %s"
            cursor.execute(query, (c_username,))
            client_info = cursor.fetchone()
            if client_info:
                return client_info
            else:
                print("Client not found!")
                return None
        except Exception as e:
            print(f"Error loading client information: {e}")
        finally:
            self.db.disconnect()

    def forgot_password(self, new_password, c_username, contact):
        """
        Validates the contact information for the username and resets the password.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT * FROM Clients WHERE c_username = %s AND contact = %s"
            cursor.execute(query, (c_username, contact))
            if cursor.fetchone():
                update_query = "UPDATE Clients SET c_password = %s WHERE c_username = %s"
                cursor.execute(update_query, (new_password, c_username))
                self.db.connection.commit()
            else:
                print("Invalid username or contact information!")
        except Exception as e:
            print(f"Error resetting password: {e}")
        finally:
            self.db.disconnect()

    def check_username(self, c_username):
        """
        Checks if a username is already taken.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT c_username FROM Clients WHERE c_username = %s"
            cursor.execute(query, (c_username,))
            if cursor.fetchone():
                print("Username is already taken.")
                return False
            else:
                print("Username is available.")
                return True
        except Exception as e:
            print(f"Error checking username: {e}")
        finally:
            self.db.disconnect()

    def change_password(self, c_username, old_password, new_password):
        """
        Changes the client's password after validating the old password.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT c_password FROM Clients WHERE c_username = %s"
            cursor.execute(query, (c_username,))
            result = cursor.fetchone()
            if result and result[0] == old_password:
                update_query = "UPDATE Clients SET c_password = %s WHERE c_username = %s"
                cursor.execute(update_query, (new_password, c_username))
                self.db.connection.commit()
            else:
                print("Old password is incorrect!")
        except Exception as e:
            print(f"Error changing password: {e}")
        finally:
            self.db.disconnect()