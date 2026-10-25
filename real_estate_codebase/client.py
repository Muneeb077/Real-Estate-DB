from dbconnection import get_connection
from passwords import hash_password, verify_password


class Client:

    def register_client(self, c_name, c_username, c_password, contact, postal_code, city, street, state):
        """
        Registers a new client into the Clients table. The password is stored as an Argon2id hash.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            query = """
            INSERT INTO Clients (c_name, c_username, c_password, contact, postal_code, city, street, state)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(query, (c_name, c_username, hash_password(c_password), contact,
                                   postal_code, city, street, state))
            connection.commit()

    def authenticate(self, c_username, c_password):
        """
        Returns True when the username exists and the password matches its hash.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT c_password FROM Clients WHERE c_username = %s", (c_username,))
            result = cursor.fetchone()
        return bool(result) and verify_password(result[0], c_password)

    def forgot_password(self, new_password, c_username, contact):
        """
        Resets the password when the username and contact match. Returns True on success.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            update_query = "UPDATE Clients SET c_password = %s WHERE c_username = %s AND contact = %s"
            cursor.execute(update_query, (hash_password(new_password), c_username, contact))
            connection.commit()
            return cursor.rowcount == 1

    def check_username(self, c_username):
        """
        Returns True when the username is still available.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT 1 FROM Clients WHERE c_username = %s", (c_username,))
            return cursor.fetchone() is None

    def change_password(self, c_username, old_password, new_password):
        """
        Changes the client's password after validating the old password.
        """
        if not self.authenticate(c_username, old_password):
            return False
        with get_connection() as connection:
            cursor = connection.cursor()
            update_query = "UPDATE Clients SET c_password = %s WHERE c_username = %s"
            cursor.execute(update_query, (hash_password(new_password), c_username))
            connection.commit()
            return True
