from dbconnection import MySQLConnection
import random


class Agent:

    def __init__(self):
        self.db = MySQLConnection()
        self.agent_id = self._fetch_max_agent_id()

    def _fetch_max_agent_id(self):
        """
        Fetches the highest agent_id using an SQL function.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT GetMaxAgentId() AS max_id"  # Call the SQL function
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] if result else 202400  # Default value if the result is None
        except Exception as e:
            print(f"Error fetching max agent ID: {e}")
            return 202400  # Default value if error occurs
        finally:
            self.db.disconnect()

    def get_agent_id(self):
        return self.agent_id

    def register_agent(self, agent_name, agent_password, agent_contact):
        """
        Registers a new agent in the database.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()

            # Fetch the latest agent_id dynamically
            query_max_id = "SELECT GetMaxAgentId() AS max_id"
            cursor.execute(query_max_id)
            result = cursor.fetchone()
            current_max_id = result[0] if result and result[0] is not None else 202400

            # Increment the agent_id for the new agent
            new_agent_id = current_max_id + 1

            # Insert the new agent into the database
            query = """
            INSERT INTO Agent (agent_id, agent_name, agent_password, agent_contact)
            VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (new_agent_id, agent_name, agent_password, agent_contact))
            self.db.connection.commit()
            print("Agent registered successfully!")

            # Update the class attribute `self.agent_id` to reflect the new ID
            self.agent_id = new_agent_id
        except Exception as e:
            print(f"Error registering agent: {e}")
        finally:
            self.db.disconnect()

    def check_agentid(self, agentid):
        """
        Checks if an agentid exists or not.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT agent_id FROM Agent WHERE agent_id = %s"
            cursor.execute(query, (agentid,))
            if cursor.fetchone():
                print("Agent ID exists.")
                return False
            else:
                print("Agent ID does not exists.")
                return True
        except Exception as e:
            print(f"hello")
        finally:
            self.db.disconnect()

    def load_agent_login_info(self, agent_id):
        self.db.connect()
        try:
            cursor = self.db.connection.cursor(dictionary=True)
            query = "SELECT agent_id, agent_password FROM Agent WHERE agent_id = %s"
            cursor.execute(query, (agent_id,))
            result = cursor.fetchone()
            return result
        except Exception as e:
            print(f"Error loading agent login info: {e}")
            return None
        finally:
            self.db.disconnect()

    def forgot_password(self,new_password, agent_id, agent_contact):
        """
        Resets the password for an agent after verifying their contact information.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT agent_contact FROM Agent WHERE agent_id = %s AND agent_contact = %s"
            cursor.execute(query, (agent_id, agent_contact))
            if cursor.fetchone():
                update_query = "UPDATE Agent SET agent_password = %s WHERE agent_id = %s"
                cursor.execute(update_query, (new_password, agent_id))
                self.db.connection.commit()
                print("Password reset successfully!")
            else:
                print("Invalid agent ID or contact information!")
        except Exception as e:
            print(f"Error resetting password: {e}")
        finally:
            self.db.disconnect()

    def check_password(self, agent_id, password):
        """
        Checks if the given password matches the agent's current password.
        """
        self.db.connect()
        try:
            cursor = self.db.connection.cursor()
            query = "SELECT agent_password FROM Agent WHERE agent_id = %s"
            cursor.execute(query, (agent_id,))
            result = cursor.fetchone()
            if result and result[0] == password:
                print("Password is correct.")
                return True
            else:
                print("Password is incorrect.")
                return False
        except Exception as e:
            print(f"Error checking password: {e}")
        finally:
            self.db.disconnect()

    def change_password(self, agent_id, old_password, new_password):
        """
        Changes an agent's password after validating the old password.
        """
        if self.check_password(agent_id, old_password):
            self.db.connect()
            try:
                cursor = self.db.connection.cursor()
                query = "UPDATE Agent SET agent_password = %s WHERE agent_id = %s"
                cursor.execute(query, (new_password, agent_id))
                self.db.connection.commit()
                print("Password updated successfully!")
            except Exception as e:
                print(f"Error changing password: {e}")
            finally:
                self.db.disconnect()
        else:
            print("Old password validation failed. Password not changed.")
