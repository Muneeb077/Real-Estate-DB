from dbconnection import get_connection
from passwords import hash_password, verify_password


class Agent:

    def register_agent(self, agent_name, agent_password, agent_contact):
        """
        Registers a new agent and returns the agent_id assigned by AUTO_INCREMENT.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            query = """
            INSERT INTO Agent (agent_name, agent_password, agent_contact)
            VALUES (%s, %s, %s)
            """
            cursor.execute(query, (agent_name, hash_password(agent_password), agent_contact))
            connection.commit()
            return cursor.lastrowid

    def authenticate(self, agent_id, password):
        """
        Returns True when the agent exists and the password matches its hash.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT agent_password FROM Agent WHERE agent_id = %s", (agent_id,))
            result = cursor.fetchone()
        return bool(result) and verify_password(result[0], password)

    def forgot_password(self, new_password, agent_id, agent_contact):
        """
        Resets the password when the agent ID and contact match. Returns True on success.
        """
        with get_connection() as connection:
            cursor = connection.cursor()
            update_query = "UPDATE Agent SET agent_password = %s WHERE agent_id = %s AND agent_contact = %s"
            cursor.execute(update_query, (hash_password(new_password), agent_id, agent_contact))
            connection.commit()
            return cursor.rowcount == 1

    def change_password(self, agent_id, old_password, new_password):
        """
        Changes an agent's password after validating the old password.
        """
        if not self.authenticate(agent_id, old_password):
            return False
        with get_connection() as connection:
            cursor = connection.cursor()
            query = "UPDATE Agent SET agent_password = %s WHERE agent_id = %s"
            cursor.execute(query, (hash_password(new_password), agent_id))
            connection.commit()
            return True
